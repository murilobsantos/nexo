import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from nexo.api import create_app
from nexo.store import Store


class PatchGateway:
    model = "patch-fixture"

    def __init__(self, forbidden=False, invalid_first=False):
        self.calls = 0
        self.forbidden = forbidden
        self.invalid_first = invalid_first

    async def health(self):
        return {"available": True, "model_installed": True}

    async def unload(self):
        pass

    async def stream(self, messages, max_tokens):
        self.calls += 1
        if self.invalid_first and self.calls == 1:
            yield {"text": "invalid json"}
        else:
            yield {"text": json.dumps({"summary": "Corrige valor", "edits": [{
                "path": "tests/test_app.py" if self.forbidden else "app.py",
                "before": "return 0", "after": "return 2"}]})}
        yield {"done": True}


class DeveloperApiTests(unittest.TestCase):
    def test_pipeline_retries_format_and_exposes_review_apply_restore(self):
        self.exercise(False)

    def test_model_cannot_change_test_oracle_and_attempts_are_bounded(self):
        self.exercise(True)

    def exercise(self, forbidden):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            (project / "tests").mkdir(parents=True)
            (project / "app.py").write_text("def value():\n    return 0\n")
            (project / "notes.txt").write_text("untracked")
            (project / "tests/test_app.py").write_text("import unittest,app\nclass T(unittest.TestCase):\n def test_value(self): self.assertEqual(app.value(),2)\n")
            backend = PatchGateway(forbidden=forbidden, invalid_first=not forbidden)
            app = create_app(root / "data", project, backend)
            with TestClient(app, base_url="http://127.0.0.1") as client:
                tree = client.get("/api/project/map").json()
                self.assertIn("tests/test_app.py", [row["path"] for row in tree])
                self.assertEqual(client.get("/api/project/search", params={"q": "return 0"}).json()[0]["line"], 2)
                task = client.post("/api/tasks", json={"kind": "development", "prompt": "Return 2", "files": ["app.py"], "timeout_seconds": 15}).json()
                for _ in range(150):
                    task = client.get("/api/tasks/" + task["id"]).json()
                    if task["state"] in {"waiting_user", "completed", "failed"}:
                        break
                    time.sleep(0.02)
                self.assertEqual(backend.calls, 2)
                self.assertIn("return 0", (project / "app.py").read_text())
                if forbidden:
                    self.assertEqual(task["state"], "failed")
                    self.assertEqual(client.post(f"/api/tasks/{task['id']}/development/publish", json={}).status_code, 409)
                    return
                self.assertEqual(task["state"], "waiting_user", task)
                path = f"/api/tasks/{task['id']}/development"
                self.assertEqual(client.get(path).json()["status"], "review")
                client.post("/api/mode", json={"mode": "paused"})
                self.assertEqual(client.post(path + "/publish", json={}).status_code, 409)
                client.post("/api/mode", json={"mode": "development"})
                self.assertEqual(client.post(path + "/publish", json={}).status_code, 200)
                self.assertEqual(client.get("/api/tasks/" + task["id"]).json()["state"], "completed")
                self.assertIn("return 2", (project / "app.py").read_text())
                self.assertEqual(client.post(path + "/restore", json={}).status_code, 200)
                self.assertEqual(client.get("/api/tasks/" + task["id"]).json()["state"], "cancelled")
                self.assertIn("return 0", (project / "app.py").read_text())
                self.assertEqual((project / "notes.txt").read_text(), "untracked")
                next_task = client.post("/api/tasks", json={"kind": "development", "prompt": "Return 2", "files": ["app.py"], "timeout_seconds": 15}).json()
                for _ in range(150):
                    next_task = client.get("/api/tasks/" + next_task["id"]).json()
                    if next_task["state"] in {"waiting_user", "failed"}:
                        break
                    time.sleep(0.02)
                self.assertEqual(next_task["state"], "waiting_user")
                next_path = f"/api/tasks/{next_task['id']}/development"
                self.assertEqual(client.post(next_path + "/reject", json={}).status_code, 200)
                self.assertEqual(client.post(next_path + "/publish", json={}).status_code, 409)
                self.assertIn("return 0", (project / "app.py").read_text())
            with self.assertRaises(ValueError):
                create_app(root / "data", root, backend)


class MigrationTests(unittest.TestCase):
    def test_v1_migrates_with_backup_before_schema_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "v1.db"
            conn = sqlite3.connect(path)
            try:
                conn.executescript("""
                    CREATE TABLE tasks (id TEXT PRIMARY KEY,prompt TEXT,files TEXT,state TEXT,answer TEXT,error TEXT,created TEXT,updated TEXT,attempts INTEGER,max_tokens INTEGER,timeout_seconds INTEGER,priority INTEGER);
                    CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,kind TEXT,data TEXT,created TEXT);
                    CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT);
                    INSERT INTO settings VALUES ('mode','personal');
                    INSERT INTO tasks VALUES ('original','pedido','[]','completed','resposta',NULL,'a','a',1,2560,180,0);
                    INSERT INTO events(task_id,kind,data,created) VALUES ('original','created','{}','a');
                    PRAGMA user_version=1;
                """)
            finally:
                conn.close()
            store = Store(path)
            self.assertEqual(store.get("original")["kind"], "chat")
            self.assertEqual(store.get("original")["answer"], "resposta")
            self.assertEqual(store.mode(), "personal")
            backup = next((root / "migration-backups").glob("v1-*.db"))
            with Store.readonly(backup.resolve()) as old:
                self.assertEqual(old.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertNotIn("kind", [row[1] for row in old.execute("PRAGMA table_info(tasks)")])
            restored = Store.restore_backup(backup, root / "restored.db")
            self.assertEqual(restored.get("original")["answer"], "resposta")
