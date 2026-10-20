"""Cópias isoladas, patches exatos e publicação/restauração com conflitos."""
import ctypes
import difflib
import hashlib
import json
import os
import stat
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .files import EXCLUDED, TEXT_SUFFIXES, ScopedFiles, sensitive_name


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def parts_of(relative, file=True):
    win = PureWindowsPath(relative)
    parts = relative.replace("\\", "/").split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if (not relative or len(relative) > 240 or win.drive or win.root or ":" in relative
        or any(p in {"", ".", ".."} or p.startswith(".") or p.rstrip(". ") != p
               or p.lower() in EXCLUDED or p.split(".")[0].upper() in reserved
               or any(ord(char) < 32 for char in p) for p in parts)):
        raise PermissionError("Caminho de patch fora da política")
    if file and (Path(parts[-1]).suffix.lower() not in TEXT_SUFFIXES or sensitive_name(parts[-1])):
        raise PermissionError("Tipo de arquivo ou segredo excluído")
    return parts


def raw(scope, relative):
    scope.read(relative)  # tipo, exclusões e limite
    target = scope.resolve(relative)
    with target.open("rb") as stream:
        scope.verify_open_handle(stream)
        if os.fstat(stream.fileno()).st_nlink != 1:
            raise PermissionError("Hard link não permitido")
        data = stream.read(scope.max_bytes + 1)
    if len(data) > scope.max_bytes:
        raise ValueError("Arquivo excede limite")
    data.decode("utf-8-sig")
    return data


@contextmanager
def project_lock(root):
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    name = "Local\\NEXO-write-" + digest(str(root).casefold().encode())
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        acquired = kernel.WaitForSingleObject(handle, 0) in {0, 0x80}
        if not acquired:
            raise ValueError("Outra aplicação/restauração está em andamento neste projeto")
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


@contextmanager
def parent_guard(scope, relative, create=False, on_directory=None, file=True):
    """Mantém diretórios Windows abertos sem compartilhar exclusão/renomeação."""
    if os.name != "nt":
        raise RuntimeError("Escrita aprovada somente no Windows")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    class Attributes(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]
    parts = parts_of(relative, file=file)
    handles = []
    current = scope.root
    try:
        for component in [None, *parts[:-1]]:
            if component is not None:
                current /= component
                if create and not current.exists():
                    current.mkdir()
                    if on_directory:
                        on_directory(current)
            handle = kernel.CreateFileW(str(current), 0x80, 3, None, 3, 0x02000000 | 0x00200000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
            attributes = Attributes()
            if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes.attributes & 0x400 or not attributes.attributes & 0x10:
                raise PermissionError("Diretório é link ou reparse point")
        yield current / parts[-1]
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


def write_checked(scope, relative, expected_hash, data, on_directory=None):
    with parent_guard(scope, relative, create=data is not None, on_directory=on_directory) as target:
        if expected_hash is None and data is None:
            return
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        # DELETE permite remover pelo handle validado, sem janela entre conferir e unlink.
        # Compartilhar somente leitura impede substituição/escrita concorrente.
        handle = kernel.CreateFileW(str(target), 0x80000000 | 0x40000000 | 0x10000, 1, None,
                                    1 if expected_hash is None else 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
        with os.fdopen(fd, "r+b") as stream:
            scope.verify_open_handle(stream)
            info = os.fstat(stream.fileno())
            if info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400:
                raise PermissionError("Link não permitido")
            existing = stream.read(scope.max_bytes + 1)
            if expected_hash is not None and digest(existing) != expected_hash:
                raise ValueError("Conflito: arquivo mudou depois do checkpoint")
            if data is not None:
                stream.seek(0)
                stream.write(data)
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
            else:
                disposition = ctypes.c_ubyte(1)
                if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
                    raise ctypes.WinError(ctypes.get_last_error())


def remove_created_directory(scope, relative, expected_ino):
    """Remove só o diretório criado, pelo handle, se continuar vazio e com a mesma identidade."""
    from ctypes import wintypes
    import msvcrt
    if not (scope.root / relative).exists():
        return True
    with parent_guard(scope, relative, file=False) as target:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(target), 0x80 | 0x10000, 3, None, 3, 0x02200000, None)
        if handle == ctypes.c_void_p(-1).value:
            return False
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        try:
            info = os.fstat(fd)
            if info.st_ino != expected_ino or not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                return False
            flag = ctypes.c_ubyte(1)
            return bool(kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(flag), 1))
        finally:
            os.close(fd)


class Edit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=240)
    before: str | None = Field(default=None, max_length=32768)
    after: str | None = Field(default=None, max_length=32768)

    @model_validator(mode="after")
    def valid(self):
        parts_of(self.path)
        if self.before is None and self.after is None:
            raise ValueError("Patch vazio")
        if self.before == "":
            raise ValueError("Trecho original vazio não é permitido")
        return self


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=1500)
    edits: list[Edit] = Field(min_length=1, max_length=12)


class Workspace:
    def __init__(self, source, home, workspace_id=None):
        self.source = ScopedFiles(Path(source))
        self.home = Path(home).resolve()
        self.id = workspace_id or uuid.uuid4().hex
        if len(self.id) != 32 or any(c not in "0123456789abcdef" for c in self.id):
            raise ValueError("ID inválido")
        self.directory = self.home / self.id
        self.work = self.directory / "work"
        self.base = self.directory / "base"
        self.metadata = self.directory / "manifest.json"

    def scan(self, scope):
        result = {}
        visited = 0
        def walk(directory, depth=0):
            nonlocal visited
            if depth > 8:
                raise ValueError("Profundidade excedida")
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 500:
                        raise ValueError("Projeto excede 500 entradas neste incremento")
                    if entry.name.startswith(".") or entry.name.lower() in EXCLUDED:
                        continue
                    relative = Path(entry.path).relative_to(scope.root).as_posix()
                    target = scope.resolve(relative)
                    if target.is_dir():
                        walk(target, depth + 1)
                    elif target.suffix.lower() in TEXT_SUFFIXES:
                        try:
                            data = raw(scope, relative)
                        except PermissionError:
                            continue
                        result[relative] = data
                        if len(result) > 200 or sum(map(len, result.values())) > 2 * 1024**2:
                            raise ValueError("Projeto excede orçamento de cópia")
        walk(scope.root)
        return result

    def save(self, manifest):
        temp = self.metadata.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.metadata)

    def load(self):
        data = json.loads(self.metadata.read_text(encoding="utf-8"))
        if data["source"] != str(self.source.root) or data["id"] != self.id:
            raise PermissionError("Manifesto não corresponde ao projeto autorizado")
        return data

    def prepare(self):
        snapshot = self.scan(self.source)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.work.mkdir()
        self.base.mkdir()
        manifest = {"id": self.id, "source": str(self.source.root), "status": "preparing",
                    "original": {path: digest(data) for path, data in snapshot.items()}, "checks": [],
                    "git_before": {"available":False,"reason":"preparing"}, "applied_paths": []}
        self.save(manifest)
        for relative, data in snapshot.items():
            for parent in (self.work, self.base):
                target = parent / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        manifest.update(status='prepared',git_before=self.git_state(list(snapshot)))
        self.save(manifest)
        return manifest

    def git_state(self, paths):
        if not paths:
            return {"available": False, "reason": "no eligible paths"}
        args = ["git", "--no-pager", "--no-optional-locks", "--literal-pathspecs", "-c", "core.fsmonitor=false", "-C", str(self.source.root)]
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            result = subprocess.run([*args, "status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
                                    capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW, env=environment)
            if result.returncode:
                return {"available": False}
            diff = subprocess.run([*args, "diff", "--no-ext-diff", "--no-textconv", "--", *paths],
                                  capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW, env=environment)
            return {"available": True, "status": result.stdout[:65536].decode("utf-8", errors="replace"), "truncated": len(result.stdout) > 65536,
                    "preexisting_diff": diff.stdout[:65536].decode("utf-8", errors="replace"), "diff_truncated": len(diff.stdout) > 65536}
        except (OSError, subprocess.TimeoutExpired):
            return {"available": False}

    def apply_patch(self, patch):
        manifest = self.load()
        if manifest["status"] not in {"prepared", "editing", "failed"}:
            raise ValueError("Workspace não aceita novas alterações neste estado")
        scope = ScopedFiles(self.work)
        # Validar e calcular o lote completo antes da primeira escrita.
        changes = {}
        for edit in patch.edits:
            parts = parts_of(edit.path)
            relative = "/".join(parts)
            if relative.casefold() in {p.casefold() for p in changes}:
                raise ValueError("Patch contém caminhos duplicados")
            path = self.work / relative
            existing = raw(scope, relative) if path.exists() else None
            if edit.before is None:
                if existing is not None:
                    raise ValueError("Criação colide com arquivo existente")
                after = edit.after.encode("utf-8")
            else:
                if existing is None:
                    raise ValueError("Trecho original não existe")
                old = existing.decode("utf-8-sig").replace("\r\n", "\n")
                before = edit.before.replace("\r\n", "\n")
                if old.count(before) != 1:
                    raise ValueError("Trecho original deve aparecer exatamente uma vez")
                if edit.after is None:
                    if old != before:
                        raise ValueError("Exclusão exige conteúdo integral do arquivo")
                    after = None
                else:
                    new = old.replace(before, edit.after.replace("\r\n", "\n"), 1)
                    if b"\r\n" in existing:
                        new = new.replace("\n", "\r\n")
                    after = (b"\xef\xbb\xbf" if existing.startswith(b"\xef\xbb\xbf") else b"") + new.encode("utf-8")
            if after is not None and len(after) > scope.max_bytes:
                raise ValueError("Resultado excede limite de arquivo")
            changes[relative] = (digest(existing), after)
        for relative, (expected, data) in changes.items():
            write_checked(scope, relative, expected, data)
        manifest.update(status="editing", summary=patch.summary)
        self.save(manifest)
        return self.diff()

    def diff(self):
        manifest = self.load()
        current = self.scan(ScopedFiles(self.work))
        rows, texts = [], []
        for relative in sorted(set(manifest["original"]) | set(current)):
            before = (self.base / relative).read_bytes() if relative in manifest["original"] else None
            if digest(before) != manifest["original"].get(relative):
                raise ValueError("Backup da cópia foi alterado")
            after = current.get(relative)
            if before == after:
                continue
            rows.append({"path": relative, "before": digest(before), "after": digest(after)})
            texts.extend(difflib.unified_diff((before or b"").decode("utf-8-sig").splitlines(keepends=True),
                         (after or b"").decode("utf-8-sig").splitlines(keepends=True),
                         fromfile="a/" + relative, tofile="b/" + relative))
        text = "".join(texts)
        if len(text.encode("utf-8")) > 128 * 1024:
            raise ValueError("Diff excede limite de revisão")
        return {"id": self.id, "status": manifest["status"], "summary": manifest.get("summary", ""), "files": rows, "diff": text,
                "checks": manifest["checks"], "git_before": manifest.get("git_before"), "kept_directories": manifest.get("kept_directories", [])}

    def record_check(self, result):
        manifest = self.load()
        manifest["checks"].append(result)
        manifest["validated_diff"] = digest(self.diff()["diff"].encode("utf-8"))
        manifest["status"] = "review" if result["passed"] else "failed"
        self.save(manifest)

    def reject(self):
        manifest = self.load()
        if manifest["status"] in {"applied", "applying", "needs_recovery"}:
            raise ValueError("Alteração aplicada exige restauração")
        manifest["status"] = "rejected"
        self.save(manifest)

    def publish(self):
        with project_lock(self.source.root):
            return self._publish()

    def _publish(self):
        manifest = self.load()
        changes = self.diff()
        if manifest["status"] != "review" or not manifest["checks"] or not manifest["checks"][-1]["passed"]:
            raise ValueError("Alteração sem verificação aprovada")
        if digest(changes["diff"].encode("utf-8")) != manifest.get("validated_diff"):
            raise ValueError("Diff mudou depois dos testes")
        if {path: digest(data) for path, data in self.scan(self.source).items()} != manifest["original"]:
            raise ValueError("Projeto original mudou; prepare nova cópia sem sobrescrever o trabalho do usuário")
        manifest.update(status="applying", publish_plan=changes["files"], created_directories=[])
        self.save(manifest)
        def created(directory):
            manifest["created_directories"].append({"path": directory.relative_to(self.source.root).as_posix(), "ino": directory.stat().st_ino})
            self.save(manifest)
        try:
            scope = ScopedFiles(self.work)
            for change in changes["files"]:
                data = raw(scope, change["path"]) if change["after"] else None
                write_checked(self.source, change["path"], change["before"], data, on_directory=created)
                manifest["applied_paths"].append(change["path"])
                self.save(manifest)
        except BaseException:
            manifest["status"] = "needs_recovery"
            self.save(manifest)
            raise
        manifest["status"] = "applied"
        self.save(manifest)
        return self.diff()

    def restore(self):
        with project_lock(self.source.root):
            return self._restore()

    def _restore(self):
        manifest = self.load()
        if manifest["status"] not in {"applied", "applying", "needs_recovery"}:
            raise ValueError("Workspace não tem publicação para restaurar")
        # Conferir efeitos existentes em todos os caminhos antes de restaurar.
        actions = []
        for change in manifest["publish_plan"]:
            path = self.source.root / change["path"]
            current = raw(self.source, change["path"]) if path.exists() else None
            current_hash = digest(current)
            if current_hash == change["before"]:
                continue
            if current_hash != change["after"]:
                raise ValueError("Conflito: alteração posterior do usuário será preservada")
            original = (self.base / change["path"]).read_bytes() if change["before"] else None
            if digest(original) != change["before"]:
                raise ValueError("Backup não corresponde ao checkpoint")
            actions.append((change["path"], change["after"], original))
        for path, expected, original in actions:
            write_checked(self.source, path, expected, original)
        kept = []
        for directory in reversed(manifest.get("created_directories", [])):
            if not remove_created_directory(self.source, directory["path"], directory["ino"]):
                kept.append(directory["path"])
        manifest["kept_directories"] = kept
        manifest["status"] = "restored"
        self.save(manifest)
        return {"id": self.id, "status": "restored"}
