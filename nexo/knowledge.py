"""Memórias versionadas e fontes em SQLite/FTS5. Conteúdo nunca concede ferramentas."""
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .files import EXCLUDED, TEXT_SUFFIXES, sensitive_name, contains_secret
from .workspace import project_lock


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def migrate(conn, path, fresh):
    if conn.execute("PRAGMA user_version").fetchone()[0] != 2:
        return
    if not fresh:
        directory = path.parent / "migration-backups"
        directory.mkdir(exist_ok=True)
        backup = sqlite3.connect(directory / f"v2-{time.time_ns()}.db")
        try:
            conn.backup(backup)
        finally:
            backup.close()
    conn.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE memories (
            id TEXT PRIMARY KEY, root_id TEXT NOT NULL, key TEXT NOT NULL,
            category TEXT NOT NULL, scope TEXT NOT NULL, content TEXT NOT NULL,
            source TEXT NOT NULL, evidence TEXT NOT NULL, validation TEXT NOT NULL,
            sensitivity TEXT NOT NULL, version INTEGER NOT NULL,
            created TEXT NOT NULL, updated TEXT NOT NULL, valid_until TEXT, review_at TEXT
        );
        CREATE INDEX memory_key ON memories(key,scope,validation);
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, source TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
            hash TEXT NOT NULL, kind TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL
        );
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
            position INTEGER NOT NULL, start_line INTEGER NOT NULL, body TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        CREATE TABLE exclusions (source_hash TEXT PRIMARY KEY, reason TEXT NOT NULL, created TEXT NOT NULL);
        CREATE VIRTUAL TABLE context_fts USING fts5(kind UNINDEXED,item_id UNINDEXED,position UNINDEXED,title,body,tokenize='unicode61 remove_diacritics 2');
        INSERT INTO context_fts(context_fts,rank) VALUES ('secure-delete',1);
        PRAGMA user_version=3;
        COMMIT;
    """)


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=120)
    category: Literal["profile", "project", "episode", "knowledge", "skill"] = "project"
    scope: Literal["project", "global"] = "project"
    content: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="user:explicit", min_length=1, max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    validation: Literal["candidate", "validated"] = "validated"
    sensitivity: Literal["public", "personal", "private"] = "private"
    valid_until: datetime | None = None
    review_at: datetime | None = None


def date_value(value):
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("Datas exigem fuso horário")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


STOP = set("a o as os de do da dos das em no na nos nas um uma uns umas e ou que qual quais como para por com deste desta esse essa projeto arquivo explique mostre favor the of and to in is for what how this file project".split())


def terms(query):
    return list(dict.fromkeys(word.casefold() for word in re.findall(r"\w+", query) if len(word) > 1 and word.casefold() not in STOP))[:24]


def match_query(query):
    return " OR ".join('"' + word + '"' for word in terms(query))


def invalidate_source(conn, document):
    if document is None:
        return
    rows = conn.execute("SELECT id FROM memories WHERE source=? OR evidence LIKE ?", (document['source'], '%' + document['id'] + '%')).fetchall()
    for row in rows:
        conn.execute("UPDATE memories SET validation='stale',updated=? WHERE id=?", (stamp(), row[0]))
        conn.execute("DELETE FROM context_fts WHERE kind='memory' AND item_id=?", (row[0],))


def split_chunks(text, width=1000):
    start = 0
    index = 0
    while start < len(text):
        end = min(len(text), start + width)
        if end < len(text):
            boundary = text.rfind("\n", start + width // 2, end)
            if boundary > start:
                end = boundary + 1
        yield index, text.count("\n", 0, start) + 1, text[start:end]
        index += 1
        if end == len(text):
            break
        start = max(start + 1, end - 100)


class Knowledge:
    def __init__(self, store, global_store=None):
        self.store = store
        self.global_store = global_store or store
        self.enforce_deletions()

    def owner(self, scope):
        return self.global_store if scope == "global" else self.store

    def _get(self, item_id):
        for store in dict.fromkeys([self.store, self.global_store]):
            with store.connect() as conn:
                row = conn.execute("SELECT * FROM memories WHERE id=?", (item_id,)).fetchone()
                if row and (store is self.store or row["scope"] == "global"):
                    return store, dict(row)
        raise KeyError("Memória inexistente")

    def list_memories(self):
        self.enforce_deletions()
        result = []
        for store in dict.fromkeys([self.store, self.global_store]):
            with store.connect() as conn:
                where = "" if store is self.store else "WHERE scope='global'"
                rows = conn.execute("SELECT * FROM memories " + where + " ORDER BY updated DESC LIMIT 300").fetchall()
                result.extend({**dict(row), "evidence": json.loads(row["evidence"])} for row in rows)
        return result

    def put_memory(self, value, correcting=None):
        if any(contains_secret(text) for text in [value.key, value.content, value.source, *value.evidence]):
            raise ValueError("Credenciais não podem ser guardadas em memória")
        if value.scope == "global" and value.category != "profile":
            raise ValueError("Somente perfil explícito pode ter escopo global")
        store = self.owner(value.scope)
        item_id = uuid.uuid4().hex
        created = stamp()
        root_id, version = item_id, 1
        with project_lock(store.path.resolve()), store.connect() as conn:
            if correcting:
                old_store, old = self._get(correcting)
                if old_store.path != store.path or old["scope"] != value.scope or old["key"] != value.key:
                    raise ValueError("Correção preserva chave e escopo")
                root_id = old["root_id"]
                version = conn.execute("SELECT max(version)+1 FROM memories WHERE root_id=?", (root_id,)).fetchone()[0]
                conn.execute("UPDATE memories SET validation='superseded',updated=? WHERE root_id=?", (created, root_id))
                for row in conn.execute("SELECT id FROM memories WHERE root_id=?", (root_id,)):
                    conn.execute("DELETE FROM context_fts WHERE kind='memory' AND item_id=?", (row[0],))
                conn.execute("INSERT OR REPLACE INTO settings VALUES ('history_after',?)", (created,))
            peers = conn.execute("SELECT id,content FROM memories WHERE key=? AND scope=? AND validation IN ('validated','conflict')", (value.key, value.scope)).fetchall()
            validation = value.validation
            if validation == "validated" and any(peer["content"] != value.content for peer in peers):
                validation = "conflict"
                conn.execute("UPDATE memories SET validation='conflict' WHERE key=? AND scope=? AND validation='validated'", (value.key, value.scope))
            conn.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                item_id, root_id, value.key, value.category, value.scope, value.content,
                "user:correction" if correcting else value.source, json.dumps(value.evidence), validation,
                value.sensitivity, version, created, created, date_value(value.valid_until), date_value(value.review_at)))
            if validation in {"validated", "conflict"}:
                conn.execute("INSERT INTO context_fts(kind,item_id,position,title,body) VALUES ('memory',?,0,?,?)", (item_id, value.key, value.content))
        return self._get(item_id)[1]

    def resolve(self, item_id):
        store, row = self._get(item_id)
        if row["validation"] != "conflict":
            raise ValueError("Somente conflito ativo pode ser resolvido")
        with project_lock(store.path.resolve()), store.connect() as conn:
            conn.execute("UPDATE memories SET validation='disputed' WHERE key=? AND scope=? AND validation IN ('validated','conflict')", (row["key"], row["scope"]))
            conn.execute("DELETE FROM context_fts WHERE kind='memory' AND item_id IN (SELECT id FROM memories WHERE key=? AND scope=?)", (row["key"], row["scope"]))
            conn.execute("UPDATE memories SET validation='validated',updated=? WHERE id=?", (stamp(), item_id))
            conn.execute("INSERT INTO context_fts(kind,item_id,position,title,body) VALUES ('memory',?,0,?,?)", (item_id, row["key"], row["content"]))
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('history_after',?)", (stamp(),))
        return self._get(item_id)[1]

    def _journal(self, store, entries):
        target = store.path.with_suffix(".deletions.json")
        data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
        data.extend(entries)
        temp = target.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(data, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, target)

    def delete_memory(self, item_id):
        store, row = self._get(item_id)
        with project_lock(store.path.resolve()):
            with store.connect() as conn:
                ids = [record[0] for record in conn.execute("SELECT id FROM memories WHERE root_id=?", (row["root_id"],))]
            self._journal(store, [{"kind": "memory", "id": value, "time": stamp()} for value in ids])
        self.enforce_deletions()
        return {"deleted": ids, "history_removed": True}

    def enforce_deletions(self):
        all_entries = []
        for store in dict.fromkeys([self.store, self.global_store]):
            path = store.path.with_suffix(".deletions.json")
            entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            all_entries.extend(entries)
            with store.connect() as conn:
                for entry in entries:
                    if not re.fullmatch(r"[0-9a-f]{32}", entry["id"]) or entry["kind"] not in {"memory", "document"}:
                        raise ValueError("Diário de exclusões inválido")
                    conn.execute("DELETE FROM context_fts WHERE kind=? AND item_id=?", (entry["kind"], entry["id"]))
                    table = "memories" if entry["kind"] == "memory" else "documents"
                    if table == 'documents':
                        invalidate_source(conn, conn.execute('SELECT * FROM documents WHERE id=?',(entry['id'],)).fetchone())
                    conn.execute("DELETE FROM " + table + " WHERE id=?", (entry["id"],))
                    if entry.get("source_hash"):
                        conn.execute("INSERT OR IGNORE INTO exclusions VALUES (?,?,?)", (entry["source_hash"], "deleted_by_user", entry["time"]))
        # Também apagar respostas derivadas de memória global neste projeto.
        with self.store.connect() as conn:
            for entry in all_entries:
                rows = conn.execute("SELECT DISTINCT task_id FROM events WHERE kind IN ('sources','memories') AND data LIKE ?", ('%' + entry["id"] + '%',)).fetchall()
                # Histórico pode propagar uma resposta para conversas posteriores.
                # Remover conservadoramente essa cauda evita derivados sem vínculo direto.
                if rows:
                    earliest = min(conn.execute("SELECT created FROM tasks WHERE id=?", (row[0],)).fetchone()[0] for row in rows)
                    rows = list(rows) + conn.execute("SELECT id FROM tasks WHERE kind='chat' AND created>=?", (earliest,)).fetchall()
                for row in rows:
                    conn.execute("UPDATE tasks SET answer='[Resposta removida: fonte de contexto apagada]',error='Fonte apagada',state=CASE WHEN state='running' THEN 'paused' ELSE state END WHERE id=?", (row[0],))
                    conn.execute("UPDATE events SET data='{}' WHERE task_id=? AND kind IN ('sources','memories','delta')", (row[0],))
            cutoffs = [entry['time'] for entry in all_entries]
            if self.global_store is not self.store:
                with self.global_store.connect() as global_conn:
                    row = global_conn.execute("SELECT value FROM settings WHERE key='history_after'").fetchone()
                    if row:
                        cutoffs.append(row[0])
            if cutoffs:
                row = conn.execute("SELECT value FROM settings WHERE key='history_after'").fetchone()
                conn.execute("INSERT OR REPLACE INTO settings VALUES ('history_after',?)", (max(cutoffs + ([row[0]] if row else [])),))

    def import_document(self, source, title, text, kind="web"):
        if any(contains_secret(value) for value in (text, source, title)):
            raise PermissionError("Fonte parece conter credencial; não foi indexada")
        if not text.strip() or len(text.encode("utf-8")) > 1024**2:
            raise ValueError("Fonte vazia ou excede 1 MiB")
        with self.store.connect() as conn:
            if conn.execute("SELECT 1 FROM exclusions WHERE source_hash=?", (sha(source),)).fetchone():
                raise PermissionError("Fonte excluída pelo usuário")
            previous = conn.execute("SELECT * FROM documents WHERE source=?", (source,)).fetchone()
            if previous and previous["hash"] == sha(text):
                return {**dict(previous), "changed": False}
            if previous:
                invalidate_source(conn, previous)
                conn.execute("DELETE FROM context_fts WHERE kind='document' AND item_id=?", (previous["id"],))
                conn.execute("DELETE FROM documents WHERE id=?", (previous["id"],))
                conn.execute("INSERT OR REPLACE INTO settings VALUES ('history_after',?)", (stamp(),))
            item_id, updated = uuid.uuid4().hex, stamp()
            conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", (item_id, source, title[:300], sha(text), kind, updated, updated))
            for position, line, body in split_chunks(text):
                conn.execute("INSERT INTO chunks(document_id,position,start_line,body) VALUES (?,?,?,?)", (item_id, position, line, body))
                conn.execute("INSERT INTO context_fts(kind,item_id,position,title,body) VALUES ('document',?,?,?,?)", (item_id, position, title[:300], body))
            return {"id": item_id, "source": source, "hash": sha(text), "updated": updated, "changed": True}

    def delete_document(self, item_id):
        with project_lock(self.store.path.resolve()):
            with self.store.connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE id=?", (item_id,)).fetchone()
                if row is None:
                    raise KeyError("Fonte inexistente")
            self._journal(self.store, [{"kind": "document", "id": item_id, "source_hash": sha(row["source"]), "time": stamp()}])
        self.enforce_deletions()

    def search(self, query, kind=None, limit=6):
        self.enforce_deletions()
        match = match_query(query)
        if not match:
            return []
        result = []
        for store in dict.fromkeys([self.store, self.global_store]):
            with store.connect() as conn:
                rows = conn.execute("SELECT kind,item_id,position,title,body,bm25(context_fts,0,0,0,5,1) AS score FROM context_fts WHERE context_fts MATCH ? ORDER BY score LIMIT 30", (match,)).fetchall()
                for row in rows:
                    if kind and row["kind"] != kind:
                        continue
                    value = dict(row)
                    if row["kind"] == "memory":
                        memory = conn.execute("SELECT * FROM memories WHERE id=? AND validation IN ('validated','conflict') AND (valid_until IS NULL OR valid_until>?)", (row["item_id"], stamp())).fetchone()
                        if not memory or (store is not self.store and memory["scope"] != "global"):
                            continue
                        value.update(validation=memory["validation"], version=memory["version"], source=memory["source"], sensitivity=memory["sensitivity"])
                    else:
                        if store is not self.store:
                            continue
                        document = conn.execute("SELECT * FROM documents WHERE id=?", (row["item_id"],)).fetchone()
                        chunk = conn.execute("SELECT start_line FROM chunks WHERE document_id=? AND position=?", (row["item_id"], row["position"])).fetchone()
                        if not document or not chunk:
                            continue
                        value.update(source=document["source"], sha256=document["hash"], start_line=chunk[0], updated=document["updated"])
                    result.append(value)
        return sorted(result, key=lambda row: row["score"])[:limit]

    def document_list(self):
        with self.store.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM documents ORDER BY updated DESC")]

    def context(self, query, kind=None):
        profiles = [row for row in self.list_memories() if row['category'] == 'profile'
                    and row['validation'] in {'validated', 'conflict'}
                    and (not row['valid_until'] or row['valid_until'] > stamp())]
        result = []
        budget = 3500
        for row in sorted(profiles, key=lambda row: row['updated'], reverse=True)[:3]:
            body = row['content'][:min(budget, 1000)]
            result.append({'kind':'memory','item_id':row['id'],'title':row['key'],'body':body,
                           'version':row['version'],'validation':row['validation'],'source':row['source'],
                           'scope':row['scope'],'truncated':len(body)<len(row['content'])})
            budget -= len(body)
        for row in self.search(query, kind=kind, limit=4):
            if any(item['item_id']==row['item_id'] and item.get('position')==row.get('position') for item in result):
                continue
            if len(row['body']) <= budget:
                result.append(row)
                budget -= len(row['body'])
        return result

    def sync_files(self, scope, discover=False):
        catalog = scope.catalog()
        known = {row['source'][5:]: row for row in self.document_list() if row['kind'] == 'file'}
        paths = [row['path'] for row in catalog['files']] if discover else list(known)
        result = {"indexed": [], "excluded": catalog['excluded'], "truncated": catalog['truncated']}
        budget = 2 * 1024**2
        for path in paths[:200]:
            try:
                file = scope.read(path)
                budget -= file['bytes']
                if budget < 0:
                    result['truncated'] = True
                    break
                document = self.import_document('file:' + path, path, file['text'], 'file')
                result['indexed'].append({"path": path, "id": document['id'], "changed": document['changed']})
            except (ValueError, OSError, UnicodeError) as exc:
                result['excluded'].append({"path": path, "reason": type(exc).__name__})
                if path in known:
                    with self.store.connect() as conn:
                        invalidate_source(conn, known[path])
                        conn.execute("DELETE FROM context_fts WHERE kind='document' AND item_id=?", (known[path]['id'],))
                        conn.execute("DELETE FROM documents WHERE id=?", (known[path]['id'],))
                        conn.execute("INSERT OR REPLACE INTO settings VALUES ('history_after',?)", (stamp(),))
        if len(paths) > 200:
            result['truncated'] = True
        return result

    def file_context(self, scope, paths, query, budget=5000):
        sources = []
        for path in paths:
            source = scope.read(path)
            doc = self.import_document("file:" + path, path, source["text"], "file")
            pieces = list(split_chunks(source["text"]))
            words = terms(query)
            ranked = sorted(pieces, key=lambda part: -sum(part[2].casefold().count(word) for word in words))
            chosen = ranked[:min(3, len(ranked))]
            for position, line, body in sorted(chosen):
                if len(body) > budget:
                    continue
                sources.append({"id": doc["id"], "path": path, "start_line": line, "sha256": source["sha256"], "text": body})
                budget -= len(body)
        return sources
