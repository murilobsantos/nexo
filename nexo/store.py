"""Estado transacional e eventos persistentes, sem conexões globais."""
import json
import sqlite3
import uuid
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

TERMINAL = {"completed", "failed", "cancelled"}
STATES = TERMINAL | {"proposed", "ready", "running", "paused", "waiting_user", "waiting_resource"}


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            fresh = version == 0
            if version > 4:
                raise RuntimeError("Banco pertence a versão mais recente; restaure versão compatível")
            if version == 0:
                conn.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE tasks (
                        id TEXT PRIMARY KEY, prompt TEXT NOT NULL, files TEXT NOT NULL,
                        state TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '',
                        error TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        max_tokens INTEGER NOT NULL, timeout_seconds INTEGER NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE events (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                        kind TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                    );
                    CREATE INDEX events_task ON events(task_id, seq);
                    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    INSERT INTO settings VALUES ('mode', 'development');
                    PRAGMA user_version=1;
                    COMMIT;
                """)
                version = 1
            if version == 1:
                if not fresh:
                    backup_dir = path.parent / "migration-backups"
                    backup_dir.mkdir(exist_ok=True)
                    backup = sqlite3.connect(backup_dir / f"v1-{time.time_ns()}.db")
                    try:
                        conn.backup(backup)
                    finally:
                        backup.close()
                conn.executescript("""
                    BEGIN IMMEDIATE;
                    ALTER TABLE tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat';
                    CREATE TABLE development (
                        workspace_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                        created TEXT NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                    );
                    PRAGMA user_version=2;
                    COMMIT;
                """)
            from .knowledge import migrate
            migrate(conn, path, fresh)
            from .scheduling import migrate as migrate_scheduling
            migrate_scheduling(conn, path, fresh)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def event(self, conn, task_id, kind, data):
        conn.execute("INSERT INTO events(task_id,kind,data,created) VALUES (?,?,?,?)",
                     (task_id, kind, json.dumps(data, ensure_ascii=False), now()))

    def create(self, prompt, files, max_tokens=2560, timeout_seconds=180, priority=0, kind="chat"):
        if kind not in {"chat", "development"}:
            raise ValueError("Tipo de tarefa inválido")
        task_id = uuid.uuid4().hex
        stamp = now()
        with self.connect() as conn:
            conn.execute("INSERT INTO tasks(id,prompt,files,state,created,updated,max_tokens,timeout_seconds,priority,kind) VALUES (?,?,?,'ready',?,?,?,?,?,?)",
                         (task_id, prompt, json.dumps(files), stamp, stamp, max_tokens, timeout_seconds, priority, kind))
            self.event(conn, task_id, "created", {"state": "ready", "files": files, "kind": kind,
                "budget": {"max_output_tokens": max_tokens, "timeout_seconds": timeout_seconds,
                           "automatic_attempts": 2 if kind == "development" else 1}})
        return self.get(task_id)

    @staticmethod
    def decode(row):
        if row is None:
            raise KeyError("Tarefa inexistente")
        result = dict(row)
        result["files"] = json.loads(result["files"])
        return result

    def get(self, task_id):
        with self.connect() as conn:
            return self.decode(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def list(self):
        with self.connect() as conn:
            return [self.decode(row) for row in conn.execute("SELECT * FROM tasks ORDER BY created DESC LIMIT 200")]

    def events(self, task_id, after=0):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM events WHERE task_id=? AND seq>? ORDER BY seq LIMIT 500", (task_id, after)).fetchall()
            return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def history(self, before):
        with self.connect() as conn:
            cutoff = conn.execute("SELECT value FROM settings WHERE key='history_after'").fetchone()
            rows = conn.execute("SELECT prompt,answer FROM tasks WHERE state='completed' AND kind='chat' AND created<? AND created>? AND error IS NULL ORDER BY created DESC LIMIT 2", (before, cutoff[0] if cutoff else "")).fetchall()
        result = []
        remaining = 1500
        for row in reversed(rows):
            size = len(row["prompt"]) + len(row["answer"])
            if size <= remaining:
                result.extend([{"role": "user", "content": row["prompt"]}, {"role": "assistant", "content": row["answer"]}])
                remaining -= size
        return result

    def link_workspace(self, task_id, workspace_id):
        with self.connect() as conn:
            conn.execute("INSERT INTO development VALUES (?,?,?)", (workspace_id, task_id, now()))
            self.event(conn, task_id, "workspace", {"id": workspace_id, "source_unchanged": True})

    def latest_workspace(self, task_id):
        with self.connect() as conn:
            row = conn.execute("SELECT workspace_id FROM development WHERE task_id=? ORDER BY created DESC LIMIT 1", (task_id,)).fetchone()
            if row is None:
                raise KeyError("Tarefa ainda não tem cópia de desenvolvimento")
            return row[0]

    def mode(self, value=None):
        with self.connect() as conn:
            if value is not None:
                conn.execute("UPDATE settings SET value=? WHERE key='mode'", (value,))
            return conn.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]

    def bind_project(self, root):
        value = str(Path(root).resolve(strict=True))
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='project_root'").fetchone()
            if row and row[0] != value:
                raise ValueError("Banco pertence a outro projeto; use diretório de dados separado")
            if not row:
                conn.execute("INSERT INTO settings VALUES ('project_root',?)", (value,))

    def claim(self):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0] not in {"development", "away"}:
                return None
            row = conn.execute("SELECT * FROM tasks WHERE state='ready' ORDER BY priority DESC,created LIMIT 1").fetchone()
            if row is None:
                return None
            conn.execute("UPDATE tasks SET state='running',attempts=attempts+1,updated=? WHERE id=?", (now(), row["id"]))
            self.event(conn, row["id"], "state", {"state": "running"})
            return {**self.decode(row), "state": "running", "attempts": row["attempts"] + 1}

    def append(self, task_id, text):
        with self.connect() as conn:
            cursor = conn.execute("UPDATE tasks SET answer=answer||?,updated=? WHERE id=? AND state='running'", (text, now(), task_id))
            if cursor.rowcount:
                self.event(conn, task_id, "delta", {"text": text})

    def finish(self, task_id, state, error=None, evidence=None):
        if state not in STATES:
            raise ValueError("Estado inválido")
        with self.connect() as conn:
            cursor = conn.execute("UPDATE tasks SET state=?,error=?,updated=? WHERE id=? AND state NOT IN ('completed','failed','cancelled')",
                                  (state, error, now(), task_id))
            if cursor.rowcount:
                self.event(conn, task_id, "state", {"state": state, "error": error, "evidence": evidence})
        return self.get(task_id)

    def resume(self, task_id):
        task = self.get(task_id)
        if task["kind"] == "development" and task["state"] == "waiting_user":
            raise ValueError("A proposta está pronta; aplique ou rejeite o diff")
        with self.connect() as conn:
            cursor = conn.execute("UPDATE tasks SET state='ready',answer='',error=NULL,updated=? WHERE id=? AND state IN ('paused','waiting_resource','waiting_user')",
                                  (now(), task_id))
            if cursor.rowcount != 1:
                raise ValueError("Somente tarefa pausada ou em espera pode ser retomada")
            self.event(conn, task_id, "state", {"state": "ready", "reason": "explicit_resume"})
        return self.get(task_id)

    def development_resolved(self, task_id, action):
        state = "completed" if action == "publish" else "cancelled"
        with self.connect() as conn:
            conn.execute("UPDATE tasks SET state=?,updated=? WHERE id=? AND kind='development'", (state, now(), task_id))
            self.event(conn, task_id, "state", {"state": state, "reason": "development_" + action})

    def recover(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT id FROM tasks WHERE state='running'").fetchall()
            for row in rows:
                conn.execute("UPDATE tasks SET state='paused',updated=? WHERE id=?", (now(), row["id"]))
                self.event(conn, row["id"], "state", {"state": "paused", "reason": "process_restart", "answer_preserved": True})

    def backup(self, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=False)
        destination = sqlite3.connect(target)
        try:
            with self.connect() as source:
                source.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup não passou pela verificação de integridade")
        finally:
            destination.close()
        return target

    @staticmethod
    def restore_backup(source, target, deletions=None):
        source = Path(source).resolve(strict=True)
        target = Path(target)
        with Store.readonly(source) as original:
            if original.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup corrompido")
            if original.execute("PRAGMA user_version").fetchone()[0] not in {1, 2, 3, 4}:
                raise ValueError("Versão de backup incompatível")
            if original.execute("PRAGMA user_version").fetchone()[0] >= 3:
                count = original.execute("SELECT (SELECT count(*) FROM memories)+(SELECT count(*) FROM documents)").fetchone()[0]
                if count and deletions is None:
                    raise ValueError("Restauração de contexto exige diário de exclusões atual (lista explícita)")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=False)
            restored = sqlite3.connect(target)
            try:
                original.backup(restored)
            finally:
                restored.close()
        if deletions is not None:
            target.with_suffix(".deletions.json").write_text(json.dumps(deletions), encoding="utf-8")
        result = Store(target)
        from .knowledge import Knowledge
        Knowledge(result)
        return result

    @staticmethod
    @contextmanager
    def readonly(path):
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            yield conn
        finally:
            conn.close()
