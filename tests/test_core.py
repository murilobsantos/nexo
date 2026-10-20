import asyncio
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from nexo.api import create_app
from nexo.files import ScopedFiles
from nexo.store import Store
from nexo.worker import Worker


class FakeGateway:
    model = "fake"

    def __init__(self, blocked=False):
        self.blocked = blocked
        self.started = asyncio.Event()
        self.closed = False
        self.unloaded = False
        self.active = 0
        self.max_active = 0

    async def stream(self, messages, max_tokens):
        self.started.set()
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.blocked:
                await asyncio.sleep(60)
            yield {"text": "Execute python app.py, conforme README.md."}
            yield {"done": True, "usage": {"eval_count": 10}}
        finally:
            self.active -= 1
            self.closed = True

    async def unload(self):
        self.unloaded = True

    async def health(self):
        return {"available": True, "model_installed": True}


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "README.md").write_text("ação", encoding="utf-8")
        self.scope = ScopedFiles(self.root, max_bytes=8)

    def tearDown(self):
        self.directory.cleanup()

    def test_reads_utf8_with_provenance(self):
        result = self.scope.read("README.md")
        self.assertEqual(result["text"], "ação")
        self.assertEqual(len(result["sha256"]), 64)

    def test_rejects_windows_escape_forms(self):
        for value in ["../README.md", "C:README.md", "C:/README.md", "\\\\host\\share", "README.md:secret", "README.md.", ".env", "x/../README.md"]:
            with self.subTest(value=value), self.assertRaises((PermissionError, FileNotFoundError)):
                self.scope.read(value)

    def test_rejects_large_and_sensitive_files(self):
        (self.root / "large.txt").write_bytes(b"x" * 9)
        (self.root / "password.txt").write_text("secret")
        for value in ["large.txt", "password.txt"]:
            with self.subTest(value=value), self.assertRaises((ValueError, PermissionError)):
                self.scope.read(value)

    def test_rejects_hardlink(self):
        os.link(self.root / "README.md", self.root / "alias.md")
        with self.assertRaises(PermissionError):
            self.scope.read("alias.md")

    def test_opened_object_is_checked_even_if_path_validation_was_raced(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside.md"
            outside.write_text("secret", encoding="utf-8")
            with patch.object(self.scope, "resolve", return_value=outside):
                with self.assertRaises(PermissionError):
                    self.scope.read("README.md")

    def test_rejects_junction_outside_scope(self):
        if os.name != "nt":
            self.skipTest("Junction específica do Windows")
        import subprocess
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "outside.md").write_text("outside")
            junction = self.root / "linked"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), outside], capture_output=True)
            self.assertEqual(result.returncode, 0)
            try:
                with self.assertRaises(PermissionError):
                    self.scope.read("linked/outside.md")
            finally:
                junction.rmdir()


class StoreTests(unittest.TestCase):
    def test_backup_restore_retains_tasks_events_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "original.db")
            task = store.create("backup", [])
            store.claim()
            store.append(task["id"], "ação preservada")
            backup = store.backup(root / "backup.db")
            restored = Store.restore_backup(backup, root / "restored.db")
            restored.recover()
            self.assertEqual(restored.get(task["id"])["answer"], "ação preservada")
            self.assertEqual(restored.get(task["id"])["state"], "paused")
            self.assertGreaterEqual(len(restored.events(task["id"])), 4)
            with self.assertRaises(FileExistsError):
                Store.restore_backup(backup, root / "original.db")
            self.assertEqual(store.get(task["id"])["state"], "running")

    def test_restart_preserves_partial_and_pauses_running_task(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.sqlite"
            first = Store(path)
            task = first.create("pedido", ["README.md"])
            first.claim()
            first.append(task["id"], "parcial")
            second = Store(path)
            second.recover()
            recovered = second.get(task["id"])
            self.assertEqual((recovered["state"], recovered["answer"]), ("paused", "parcial"))
            self.assertTrue(any(e["data"].get("reason") == "process_restart" for e in second.events(task["id"])))
            second.resume(task["id"])
            self.assertEqual(second.get(task["id"])["state"], "ready")


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_timeout_closes_stream_and_requests_unload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "state.db")
            task = store.create("timeout", [], timeout_seconds=1)
            backend = FakeGateway(blocked=True)
            worker = Worker(store, ScopedFiles(root), backend)
            await worker.start()
            await asyncio.wait_for(backend.started.wait(), 2)
            deadline = time.monotonic() + 3
            while store.get(task["id"])["state"] == "running" and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            self.assertEqual(store.get(task["id"])["state"], "failed")
            self.assertTrue(backend.closed and backend.unloaded)
            await worker.close()

    async def test_pause_blocks_new_work_and_cancels_stream_under_two_seconds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "state.db")
            first = store.create("primeira", [])
            second = store.create("segunda", [])
            backend = FakeGateway(blocked=True)
            worker = Worker(store, ScopedFiles(root), backend)
            await worker.start()
            await asyncio.wait_for(backend.started.wait(), 2)
            started = time.monotonic()
            await worker.set_mode("paused")
            self.assertLess(time.monotonic() - started, 2)
            await asyncio.sleep(0.3)
            self.assertEqual(store.get(first["id"])["state"], "paused")
            self.assertEqual(store.get(second["id"])["state"], "ready")
            self.assertTrue(backend.closed and backend.unloaded)
            self.assertEqual(backend.max_active, 1)
            await worker.close()


class ApiTests(unittest.TestCase):
    def test_http_queue_sources_events_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "README.md").write_text("Execute python app.py", encoding="utf-8")
            app = create_app(root / "data", project, FakeGateway())
            with TestClient(app, base_url="http://127.0.0.1") as client:
                self.assertEqual(client.post("/api/tasks", json={"prompt": "leia", "files": ["../outside.md"]}).status_code, 400)
                self.assertEqual(client.post("/api/mode", json={"mode": "away"}, headers={"Origin": "https://evil.example"}).status_code, 403)
                self.assertEqual(client.get("/api/state", headers={"Host": "evil.example"}).status_code, 403)
                self.assertEqual(client.get("/api/state", headers={"Host": "testserver"}).status_code, 403)
                task = client.post("/api/tasks", json={"prompt": "Como executar?", "files": ["README.md"]}).json()
                for _ in range(50):
                    current = client.get("/api/tasks/" + task["id"]).json()
                    if current["state"] == "completed":
                        break
                    time.sleep(0.02)
                self.assertEqual(current["state"], "completed")
                self.assertIn("Fontes do contexto: README.md.", current["answer"])
                events = client.get(f"/api/tasks/{task['id']}/events").json()
                self.assertTrue(any(e["kind"] == "sources" for e in events))
                self.assertTrue(any(e["kind"] == "model" for e in events))
                with client.stream("GET", f"/api/tasks/{task['id']}/stream") as response:
                    content = "".join(response.iter_text())
                self.assertIn('"kind": "delta"', content)
            reopened = create_app(root / "data", project, FakeGateway())
            with TestClient(reopened, base_url="http://127.0.0.1") as client:
                self.assertEqual(client.get("/api/tasks/" + task["id"]).json()["answer"], current["answer"])
                self.assertEqual(client.get("/api/state").json()["mode"], "paused")
