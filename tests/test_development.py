import asyncio
import json
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil

from nexo.runner import Runner
from nexo.workspace import Edit, Patch, Workspace, project_lock


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "app.py").write_bytes(b"# user change\r\nvalue = 1\r\n")
        (self.project / "notes.txt").write_bytes(b"untracked user data\r\n")
        self.workspace = Workspace(self.project, self.root / "copies")
        self.workspace.prepare()

    def tearDown(self):
        self.temp.cleanup()

    def patch(self):
        return Patch(summary="change", edits=[Edit(path="app.py", before="value = 1", after="value = 2")])

    def ready(self):
        self.workspace.record_check({"check": "fixture", "passed": True})

    def test_isolation_publish_restore_preserves_existing_and_untracked_bytes(self):
        original = (self.project / "app.py").read_bytes()
        self.workspace.apply_patch(self.patch())
        self.assertEqual((self.project / "app.py").read_bytes(), original)
        self.assertIn("+value = 2", self.workspace.diff()["diff"])
        self.ready()
        self.workspace.publish()
        self.assertIn(b"# user change\r\nvalue = 2\r\n", (self.project / "app.py").read_bytes())
        Workspace(self.project, self.root / "copies", self.workspace.id).restore()
        self.assertEqual((self.project / "app.py").read_bytes(), original)
        self.assertEqual((self.project / "notes.txt").read_bytes(), b"untracked user data\r\n")

    def test_stale_source_and_stale_test_diff_are_rejected(self):
        self.workspace.apply_patch(self.patch())
        self.ready()
        (self.project / "notes.txt").write_text("new user change")
        with self.assertRaises(ValueError):
            self.workspace.publish()
        self.assertIn(b"value = 1", (self.project / "app.py").read_bytes())
        (self.project / "notes.txt").write_bytes(b"untracked user data\r\n")
        (self.workspace.work / "app.py").write_text("value = 3")
        with self.assertRaises(ValueError):
            self.workspace.publish()

    def test_reject_leaves_source_untouched_and_cannot_be_published(self):
        self.workspace.apply_patch(self.patch())
        self.ready()
        self.workspace.reject()
        with self.assertRaises(ValueError):
            self.workspace.publish()
        self.assertIn(b"value = 1", (self.project / "app.py").read_bytes())

    def test_restore_does_not_overwrite_later_user_changes(self):
        self.workspace.apply_patch(self.patch())
        self.ready()
        self.workspace.publish()
        (self.project / "app.py").write_text("user edited after publish")
        with self.assertRaises(ValueError):
            self.workspace.restore()
        self.assertEqual((self.project / "app.py").read_text(), "user edited after publish")

    def test_new_file_is_removed_by_restore(self):
        self.workspace.apply_patch(Patch(summary="new", edits=[Edit(path="new.py", after="value = 5\n")]))
        self.ready()
        self.workspace.publish()
        self.assertTrue((self.project / "new.py").exists())
        self.workspace.restore()
        self.assertFalse((self.project / "new.py").exists())

    def test_new_nested_directories_are_restored_and_user_files_preserved(self):
        for user_addition in [False, True]:
            with self.subTest(user_addition=user_addition):
                workspace = Workspace(self.project, self.root / "copies")
                workspace.prepare()
                workspace.apply_patch(Patch(summary="nested", edits=[Edit(path="newpkg/mod.py", after="value = 1\n")]))
                workspace.record_check({"check": "fixture", "passed": True})
                workspace.publish()
                if user_addition:
                    (self.project / "newpkg/keep.txt").write_text("user data")
                workspace.restore()
                self.assertFalse((self.project / "newpkg/mod.py").exists())
                if user_addition:
                    self.assertEqual((self.project / "newpkg/keep.txt").read_text(), "user data")
                else:
                    self.assertFalse((self.project / "newpkg").exists())

    def test_concurrent_publication_is_refused_before_writing(self):
        self.workspace.apply_patch(self.patch())
        self.ready()
        with project_lock(self.project):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.workspace.publish)
                with self.assertRaises(ValueError):
                    future.result()
        self.assertEqual(self.workspace.load()["status"], "review")

    def test_git_staged_content_and_index_are_not_changed(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.project), *args], check=True, capture_output=True)
        git("init", "-q")
        git("add", "app.py")
        index = (self.project / ".git/index").read_bytes()
        (self.project / "app.py").write_bytes(b"# user change\r\nvalue = 1\r\n# unstaged\r\n")
        workspace = Workspace(self.project, self.root / "copies")
        manifest = workspace.prepare()
        self.assertTrue(manifest["git_before"]["available"])
        self.assertIn("unstaged", manifest["git_before"]["preexisting_diff"])
        workspace.apply_patch(self.patch())
        workspace.record_check({"check": "fixture", "passed": True})
        workspace.publish()
        workspace.restore()
        self.assertEqual((self.project / ".git/index").read_bytes(), index)
        self.assertIn(b"# unstaged", (self.project / "app.py").read_bytes())

    def test_patch_batch_is_validated_before_any_write(self):
        with self.assertRaises(ValueError):
            self.workspace.apply_patch(Patch(summary="bad", edits=[
                Edit(path="app.py", before="value = 1", after="value = 2"),
                Edit(path="notes.txt", before="missing", after="oops")]))
        self.assertIn(b"value = 1", (self.workspace.work / "app.py").read_bytes())
        for path in ["../outside.py", "C:evil.py", "x/NUL.py", "x.py:ads", ".env", "node_modules/a.js"]:
            with self.subTest(path=path), self.assertRaises((ValueError, PermissionError)):
                Edit(path=path, after="text")

    def test_interrupted_publish_is_recoverable_without_repeating_writes(self):
        self.workspace.apply_patch(self.patch())
        self.ready()
        self.workspace.publish()
        manifest = self.workspace.load()
        manifest["status"] = "applying"
        manifest["applied_paths"] = []  # falha após escrita e antes do registro final
        self.workspace.save(manifest)
        recovered = Workspace(self.project, self.root / "copies", self.workspace.id)
        recovered.restore()
        self.assertIn(b"value = 1", (self.project / "app.py").read_bytes())


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_node_discovery_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            result = await Runner().run(Path(directory), "node-tests")
            self.assertFalse(result["passed"])
            self.assertTrue(result["no_tests_confirmed"])

    async def test_node_tests_and_npm_build_are_registered_and_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.test.js").write_text("const test=require('node:test');const assert=require('node:assert/strict');test('sum',()=>assert.equal(2+2,4));")
            (root / "package.json").write_text(json.dumps({"scripts": {"build": "node -e \"require('fs').writeFileSync('built.txt','ok')\""}}))
            node_result = await Runner().run(root, "node-tests")
            self.assertTrue(node_result["passed"], node_result)
            build = await Runner().run(root, "npm-build")
            self.assertTrue(build["passed"], build)
            self.assertEqual((root / "built.txt").read_text(), "ok")
    async def test_tests_and_syntax_checks_have_structured_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/test_ok.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(2+2,4)\n")
            result = await Runner().run(root, "python-tests")
            self.assertTrue(result["passed"], result)
            self.assertIn("test_ok", result["output"])
            result = await Runner().run(root, "python-check")
            self.assertTrue(result["passed"], result)
            with self.assertRaises(PermissionError):
                await Runner().run(root, "powershell")

    async def test_timeout_and_cancel_kill_descendants(self):
        for cancel in [False, True]:
            with self.subTest(cancel=cancel), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "tests").mkdir()
                (root / "tests/test_child.py").write_text(
                    "import unittest,subprocess,sys,time\nfrom pathlib import Path\n"
                    "class T(unittest.TestCase):\n def test_child(self):\n"
                    "  child=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW)\n"
                    "  Path('child.pid').write_text(str(child.pid))\n  time.sleep(60)\n")
                run = asyncio.create_task(Runner().run(root, "python-tests", timeout=1 if not cancel else 20))
                for _ in range(100):
                    if (root / "child.pid").exists():
                        break
                    await asyncio.sleep(0.02)
                self.assertTrue((root / "child.pid").exists())
                child = psutil.Process(int((root / "child.pid").read_text()))
                if cancel:
                    run.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await run
                else:
                    self.assertTrue((await run)["timed_out"])
                await asyncio.to_thread(child.wait, 3)
                self.assertFalse(child.is_running())

    async def test_output_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/test_output.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_many(self):\n  print('x'*100000,flush=True)\n")
            result = await Runner(max_output=1024).run(root, "python-tests")
            self.assertLessEqual(len(result["output"].encode()), 1024)
            self.assertFalse(result["passed"])
