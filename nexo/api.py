import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

from .files import ScopedFiles
from .gateway import Ollama
from .store import Store, TERMINAL
from .worker import Worker
from .developer import Developer
from .workspace import Workspace, digest
from . import __version__
from .knowledge import Knowledge, MemoryInput
from .research import fetch_public
from .scheduling import Scheduler, ScheduleInput
from .coexistence import Coexistence, CoexistenceInput

ROOT = Path(__file__).resolve().parents[1]


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["chat", "development"] = "chat"
    prompt: str = Field(min_length=1, max_length=4000)
    files: list[str] = Field(default_factory=list, max_length=5)
    max_tokens: int = Field(default=2560, ge=128, le=2560)
    timeout_seconds: int = Field(default=180, ge=5, le=300)
    priority: int = Field(default=0, ge=0, le=10)


class ModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["paused", "personal", "development", "away"]


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2000)


def create_app(data_dir=None, project_dir=None, gateway=None, profile_dir=None):
    files = ScopedFiles(Path(project_dir or ROOT / "demo"))
    default_data = ROOT / ".runtime" / "data" if files.root == (ROOT / "demo").resolve() else ROOT / ".runtime" / "projects" / digest(str(files.root).encode())[:16]
    store = Store(Path(data_dir or default_data) / "nexo.db")
    store.bind_project(files.root)
    profile_path = Path(profile_dir or (Path(data_dir) / "profile" if data_dir else ROOT / ".runtime" / "profile")) / "nexo.db"
    knowledge = Knowledge(store, Store(profile_path))
    backend = gateway or Ollama()
    developer = Developer(store, files, backend, store.path.parent / "workspaces", knowledge)
    worker = Worker(store, files, backend, developer, knowledge)
    scheduler = Scheduler(store)
    coexistence = Coexistence(store,worker,scheduler)

    @asynccontextmanager
    async def lifespan(app):
        await coexistence.start()
        await worker.start()
        try:
            yield
        finally:
            await coexistence.close()
            await worker.close()

    app = FastAPI(title="NEXO local", lifespan=lifespan)
    app.state.store, app.state.worker = store, worker
    app.state.knowledge = knowledge
    app.state.coexistence = coexistence

    @app.get('/api/automation')
    async def automation():
        with store.connect() as conn:
            notices = [dict(row) for row in conn.execute('SELECT * FROM notices ORDER BY id DESC LIMIT 20')]
        return {'config':coexistence.config().model_dump(),'activity':coexistence.snapshot,
                'schedules':scheduler.list(),'notices':notices}

    @app.post('/api/automation/config')
    async def automation_config(body: CoexistenceInput):
        result = coexistence.configure(body)
        await coexistence.tick()
        return result

    @app.post('/api/schedules',status_code=201)
    async def create_schedule(body: ScheduleInput):
        try:
            for path in body.task.files:
                files.read(path)
        except (ValueError,OSError,UnicodeError) as exc:
            raise HTTPException(400,str(exc)) from exc
        return scheduler.create(body)

    @app.post('/api/schedules/{item_id}/disable')
    async def disable_schedule(item_id: str):
        scheduler.disable(item_id)
        return {'disabled':item_id,'existing_task_cancelled':False}

    @app.get("/api/memories")
    async def memories():
        return knowledge.list_memories()

    @app.post("/api/memories", status_code=201)
    async def remember(body: MemoryInput):
        await worker.set_mode("paused")
        return knowledge.put_memory(body)

    @app.post("/api/memories/{item_id}/correct")
    async def correct_memory(item_id: str, body: MemoryInput):
        await worker.set_mode("paused")
        return knowledge.put_memory(body, correcting=item_id)

    @app.post("/api/memories/{item_id}/resolve")
    async def resolve_memory(item_id: str):
        await worker.set_mode("paused")
        return knowledge.resolve(item_id)

    @app.post("/api/memories/{item_id}/delete")
    async def forget_memory(item_id: str):
        await worker.set_mode("paused")
        return knowledge.delete_memory(item_id)

    @app.get("/api/sources")
    async def sources():
        return knowledge.document_list()

    @app.post("/api/sources")
    async def import_source(body: SourceRequest):
        source = await asyncio.to_thread(fetch_public, body.url)
        return knowledge.import_document(source["source"], source["title"], source["text"])

    @app.post("/api/sources/{item_id}/delete")
    async def forget_source(item_id: str):
        await worker.set_mode("paused")
        knowledge.delete_document(item_id)
        return {"deleted": item_id}

    @app.get("/api/context/search")
    async def context_search(q: str = ""):
        if len(q) > 4000:
            raise ValueError("Consulta longa demais")
        return knowledge.search(q)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.url.hostname
        origin = request.headers.get("origin")
        port = request.url.port or 80
        allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if host not in {"127.0.0.1", "localhost"} or (origin and origin not in allowed):
            return JSONResponse({"detail": "Acesso somente pela interface local"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Registro inexistente"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(PermissionError)
    async def denied(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.get("/api/state")
    async def state():
        return {"mode": store.mode(), "active_task": worker.active_id,
                "scope": str(files.root), "project_name": files.root.name, "model": getattr(backend, "model", "test"),
                "backend": await backend.health(), "version": __version__}

    @app.get("/api/files")
    async def list_files():
        return files.list()

    @app.get("/api/project/map")
    async def project_map():
        return files.catalog()["files"]

    @app.get("/api/project/catalog")
    async def project_catalog():
        return files.catalog()

    @app.post("/api/project/index")
    async def project_index():
        if store.mode() not in {"development", "away"}:
            raise HTTPException(409, "Indexação exige modo de desenvolvimento ou ausente")
        return knowledge.sync_files(files, discover=True)

    @app.get("/api/project/search")
    async def project_search(q: str):
        if not 1 <= len(q) <= 200:
            raise HTTPException(400, "Busca exige de 1 a 200 caracteres")
        workspace = Workspace(files.root, developer.home)
        results = []
        for path, data in workspace.scan(files).items():
            for line, text in enumerate(data.decode("utf-8-sig").splitlines(), 1):
                if q.casefold() in text.casefold():
                    results.append({"path": path, "line": line, "text": text[:240]})
                    if len(results) == 100:
                        return results
        return results

    @app.get("/api/files/read")
    async def read_file(path: str):
        try:
            return files.read(path)
        except (ValueError, OSError, UnicodeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/tasks", status_code=201)
    async def create_task(body: TaskRequest):
        try:
            for path in body.files:
                files.read(path)
        except (ValueError, OSError, UnicodeError) as exc:
            raise HTTPException(400, str(exc)) from exc
        return store.create(**body.model_dump())

    @app.get("/api/tasks")
    async def list_tasks():
        knowledge.enforce_deletions()
        return store.list()

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        knowledge.enforce_deletions()
        return store.get(task_id)

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        return await worker.stop_task(task_id)

    @app.post("/api/tasks/{task_id}/resume")
    async def resume_task(task_id: str):
        try:
            return store.resume(task_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/tasks/{task_id}/development")
    async def development(task_id: str):
        return developer.workspace(task_id).diff()

    @app.post("/api/tasks/{task_id}/development/{action}")
    async def development_action(task_id: str, action: Literal["publish", "reject", "restore"]):
        task = store.get(task_id)
        if action == "publish" and task.get("error") == "Fonte apagada":
            raise HTTPException(409, "Contexto apagado; rejeite e gere uma nova proposta")
        if task["state"] not in TERMINAL | {"paused", "waiting_user"}:
            raise HTTPException(409, "Aguarde ou interrompa a tarefa antes de revisar")
        if action == "publish" and task["state"] != "waiting_user":
            raise HTTPException(409, "Somente proposta aguardando revisão pode ser aplicada")
        if action != "reject" and store.mode() not in {"development", "away"}:
            raise HTTPException(409, "Retome o modo de desenvolvimento para alterar o projeto")
        workspace = developer.workspace(task_id)
        try:
            result = getattr(workspace, action)()
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc
        developer.emit(task_id, "development_" + action, {"workspace_id": workspace.id})
        store.development_resolved(task_id, action)
        return result or workspace.diff()

    @app.post("/api/mode")
    async def mode(body: ModeRequest):
        await worker.set_mode(body.mode)
        return {"mode": store.mode()}

    @app.get("/api/tasks/{task_id}/events")
    async def events(task_id: str, after: int = 0):
        knowledge.enforce_deletions()
        store.get(task_id)
        return store.events(task_id, after)

    @app.get("/api/tasks/{task_id}/stream")
    async def stream(task_id: str, request: Request, after: int = 0):
        store.get(task_id)
        async def generate():
            cursor = after
            while not await request.is_disconnected():
                knowledge.enforce_deletions()
                rows = store.events(task_id, cursor)
                for row in rows:
                    cursor = row["seq"]
                    yield f"id: {cursor}\ndata: {json.dumps(row, ensure_ascii=False)}\n\n"
                task = store.get(task_id)
                if (task["state"] in TERMINAL or task["state"] in {"paused", "waiting_resource", "waiting_user"}) and not rows:
                    return
                await asyncio.sleep(0.2)
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    frontend = ROOT / "frontend" / "dist"
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
