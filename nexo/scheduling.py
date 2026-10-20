"""Agenda finita por projeto; sem geração de objetivos pelo modelo."""
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal


def migrate(conn, path, fresh):
    if conn.execute('PRAGMA user_version').fetchone()[0] != 3:
        return
    if not fresh:
        directory = path.parent/'migration-backups'
        directory.mkdir(exist_ok=True)
        backup = sqlite3.connect(directory/f'v3-{time.time_ns()}.db')
        try:
            conn.backup(backup)
        finally:
            backup.close()
    conn.executescript('''
        BEGIN IMMEDIATE;
        CREATE TABLE schedules (
            id TEXT PRIMARY KEY, objective TEXT NOT NULL, task TEXT NOT NULL,
            interval_seconds INTEGER NOT NULL, next_run REAL NOT NULL,
            expires_at REAL NOT NULL, max_runs INTEGER NOT NULL, runs INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1, away_only INTEGER NOT NULL,
            last_task TEXT, last_reason TEXT, created TEXT NOT NULL
        );
        CREATE TABLE notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, text TEXT NOT NULL,
            created REAL NOT NULL, read INTEGER NOT NULL DEFAULT 0
        );
        PRAGMA user_version=4;
        COMMIT;
    ''')


class ScheduledTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['chat','development'] = 'chat'
    prompt: str = Field(min_length=1,max_length=4000)
    files: list[str] = Field(default_factory=list,max_length=5)
    max_tokens: int = Field(default=2560,ge=128,le=2560)
    timeout_seconds: int = Field(default=180,ge=5,le=300)
    priority: int = Field(default=0,ge=0,le=10)


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    objective: str = Field(min_length=1,max_length=1000)
    task: ScheduledTask
    interval_seconds: int = Field(default=3600,ge=60,le=30*86400)
    max_runs: int = Field(default=1,ge=1,le=100)
    start_at: datetime
    expires_at: datetime
    away_only: bool = True

    @field_validator('start_at','expires_at')
    @classmethod
    def timezone_required(cls,value):
        if value.tzinfo is None:
            raise ValueError('Data exige fuso horário')
        return value


class Scheduler:
    def __init__(self,store,clock=time.time):
        self.store,self.clock = store,clock

    def create(self,value):
        start,end = value.start_at.timestamp(),value.expires_at.timestamp()
        if end <= self.clock() or end < start or end-self.clock()>90*86400:
            raise ValueError('Prazo deve ser futuro, após o início e em até 90 dias')
        from .files import contains_secret
        if contains_secret(value.objective) or contains_secret(value.task.prompt):
            raise ValueError('Credenciais não podem entrar na agenda')
        item_id = uuid.uuid4().hex
        with self.store.connect() as conn:
            conn.execute('INSERT INTO schedules(id,objective,task,interval_seconds,next_run,expires_at,max_runs,away_only,created) VALUES (?,?,?,?,?,?,?,?,?)',
                (item_id,value.objective,value.task.model_dump_json(),value.interval_seconds,start,end,value.max_runs,int(value.away_only),datetime.now(timezone.utc).isoformat()))
        return next(row for row in self.list() if row['id']==item_id)

    def list(self):
        with self.store.connect() as conn:
            return [{**dict(row),'task':json.loads(row['task'])} for row in conn.execute('SELECT * FROM schedules ORDER BY created DESC LIMIT 200')]

    def disable(self,item_id):
        with self.store.connect() as conn:
            if not conn.execute("UPDATE schedules SET enabled=0,last_reason='disabled_by_user' WHERE id=?",(item_id,)).rowcount:
                raise KeyError(item_id)

    def notify(self,kind,text,cooldown=900):
        now = self.clock()
        with self.store.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            recent = conn.execute('SELECT 1 FROM notices WHERE kind=? AND created>?',(kind,now-cooldown)).fetchone()
            hourly = conn.execute('SELECT count(*) FROM notices WHERE created>?',(now-3600,)).fetchone()[0]
            if recent or hourly>=3:
                return False
            conn.execute('INSERT INTO notices(kind,text,created) VALUES (?,?,?)',(kind,text,now))
            conn.execute('DELETE FROM notices WHERE id NOT IN (SELECT id FROM notices ORDER BY id DESC LIMIT 100)')
        return True

    def tick(self):
        now = self.clock()
        with self.store.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("UPDATE schedules SET enabled=0,last_reason='expired' WHERE enabled=1 AND expires_at<=?",(now,))
            mode = conn.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
            if mode not in {'development','away'}:
                return None
            # Não acumular outra tarefa automática enquanto há trabalho ou revisão pendente.
            if conn.execute("SELECT 1 FROM tasks WHERE state IN ('ready','running','paused','waiting_resource','waiting_user') LIMIT 1").fetchone():
                return None
            schedule = conn.execute('SELECT * FROM schedules WHERE enabled=1 AND runs<max_runs AND next_run<=? AND (away_only=0 OR ?=\'away\') ORDER BY next_run LIMIT 1',(now,mode)).fetchone()
            if not schedule:
                return None
            task = ScheduledTask.model_validate_json(schedule['task'])
            task_id = uuid.uuid4().hex
            created = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO tasks(id,prompt,files,state,created,updated,max_tokens,timeout_seconds,priority,kind) VALUES (?,?,?,'ready',?,?,?,?,?,?)",
                (task_id,task.prompt,json.dumps(task.files),created,created,task.max_tokens,task.timeout_seconds,task.priority,task.kind))
            self.store.event(conn,task_id,'created',{'state':'ready','schedule_id':schedule['id'],'objective':schedule['objective'],
                'budget':{'max_output_tokens':task.max_tokens,'timeout_seconds':task.timeout_seconds,'automatic_attempts':2 if task.kind=='development' else 1}})
            runs = schedule['runs']+1
            conn.execute("UPDATE schedules SET runs=?,next_run=?,last_task=?,enabled=?,last_reason='enqueued' WHERE id=?",
                (runs,now+schedule['interval_seconds'],task_id,int(runs<schedule['max_runs']),schedule['id']))
            return task_id
