"""Prova da stack HTTP com persistência SQLite em Python disponível."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import BaseModel, Field
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "Rodar no .venv para validar FastAPI/Pydantic/HTTPX")
class StackSmoke(unittest.TestCase):
    def test_validated_http_request_survives_connection_restart(self):
        class Task(BaseModel):
            title: str = Field(min_length=1, max_length=200)

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "probe.db"
            with closing(sqlite3.connect(database)) as conn:
                conn.execute("CREATE TABLE tasks (title TEXT NOT NULL)")
                conn.commit()
            app = FastAPI()

            @app.post("/tasks")
            def create(task: Task):
                with closing(sqlite3.connect(database)) as conn:
                    conn.execute("INSERT INTO tasks VALUES (?)", (task.title,))
                    conn.commit()
                return {"title": task.title}

            with TestClient(app) as client:
                self.assertEqual(client.post("/tasks", json={"title": ""}).status_code, 422)
                self.assertEqual(client.post("/tasks", json={"title": "ação"}).json(), {"title": "ação"})
            with closing(sqlite3.connect(database)) as conn:
                self.assertEqual(conn.execute("SELECT title FROM tasks").fetchall(), [("ação",)])
