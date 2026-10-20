"""Ferramentas limitadas ao diretório configurado, sem seguir links."""
import hashlib
import os
import stat
import re
from pathlib import Path, PureWindowsPath

EXCLUDED = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".runtime"}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".toml", ".json", ".yaml", ".yml", ".ts", ".tsx", ".js", ".css", ".html", ".ini", ".cfg"}


def sensitive_name(name):
    return bool(re.search(r"(^|[_.-])(secrets?|credentials?|passwords?|private[_-]?key|(?:api|access|refresh)[_-]?(?:key|token)|tokens?)([_.-]|$)", name, re.IGNORECASE))


def contains_secret(text):
    return bool(re.search(r"\bsk-[A-Za-z0-9_-]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[A-Z0-9]{16}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:api[_-]?key|password|access[_-]?token)\s*[=:]\s*['\"]?[A-Za-z0-9_/-]{16,}", text, re.IGNORECASE))


class ScopedFiles:
    def __init__(self, root: Path, max_bytes=32768):
        self.root = root.resolve(strict=True)
        self.max_bytes = max_bytes
        if not self.root.is_dir():
            raise ValueError("Escopo deve ser diretório")

    def resolve(self, relative):
        # Windows também interpreta drive relativo, UNC, ADS e separadores alternativos.
        win = PureWindowsPath(relative)
        if not relative or win.drive or win.root or ":" in relative or "\x00" in relative:
            raise PermissionError("Caminho deve ser relativo ao projeto")
        parts = relative.replace("\\", "/").split("/")
        if any(p in {"", ".", ".."} or p.rstrip(". ") != p or p.lower() in EXCLUDED or p.startswith(".") for p in parts):
            raise PermissionError("Caminho excluído ou fora do escopo")
        current = self.root
        for part in parts:
            current /= part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise PermissionError("Links e reparse points não são permitidos")
        target = current.resolve(strict=True)
        if not target.is_relative_to(self.root):
            raise PermissionError("Fora do escopo")
        return target

    def read(self, relative):
        target = self.resolve(relative)
        if target.suffix.lower() not in TEXT_SUFFIXES or sensitive_name(target.name):
            raise PermissionError("Arquivo sensível ou tipo não permitido")
        if not target.is_file():
            raise ValueError("Não é arquivo regular")
        # Abrir no máximo limite+1; não carregar arquivo arbitrariamente grande.
        with target.open("rb") as stream:
            self.verify_open_handle(stream)
            if os.fstat(stream.fileno()).st_nlink > 1:
                raise PermissionError("Hard links não são permitidos")
            data = stream.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise ValueError("Arquivo excede limite de leitura")
        if b"\x00" in data:
            raise ValueError("Arquivo binário")
        text = data.decode("utf-8-sig")
        if contains_secret(text):
            raise PermissionError("Conteúdo parece conter credencial; leitura recusada")
        return {"path": target.relative_to(self.root).as_posix(), "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "text": text}

    def verify_open_handle(self, stream):
        # Verificar o objeto realmente aberto, não só o caminho antes da abertura.
        # Isso cobre troca de junction/symlink entre resolve() e open().
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            final_name = kernel.GetFinalPathNameByHandleW
            final_name.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
            final_name.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            size = final_name(msvcrt.get_osfhandle(stream.fileno()), buffer, len(buffer), 0)
            if not size or size >= len(buffer):
                raise PermissionError("Não foi possível verificar o arquivo aberto")
            name = buffer.value
            if name.startswith("\\\\?\\UNC\\"):
                name = "\\\\" + name[8:]
            elif name.startswith("\\\\?\\"):
                name = name[4:]
            actual = Path(name).resolve(strict=True)
        elif Path("/proc/self/fd").is_dir():
            actual = Path(os.readlink(f"/proc/self/fd/{stream.fileno()}")).resolve(strict=True)
        else:
            raise PermissionError("Verificação de handle não disponível neste sistema")
        if not actual.is_relative_to(self.root):
            raise PermissionError("Arquivo aberto fora do escopo")

    def list(self):
        result = []
        # Sem recursão inicial: só arquivos imediatamente no diretório autorizado.
        with os.scandir(self.root) as entries:
            for entry in entries:
                if len(result) >= 100:
                    break
                try:
                    target = self.resolve(entry.name)
                    if target.is_file() and target.suffix.lower() in TEXT_SUFFIXES:
                        result.append({"path": entry.name, "bytes": entry.stat(follow_symlinks=False).st_size})
                except (PermissionError, OSError):
                    continue
        return sorted(result, key=lambda item: item["path"])

    def catalog(self, limit=500):
        """Metadados limitados, sem incorporar o conteúdo dos arquivos."""
        included, excluded = [], []
        pending = [(self.root, 0)]
        visited = 0
        while pending and visited < limit:
            directory, depth = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > limit:
                        break
                    relative = Path(entry.path).relative_to(self.root).as_posix()
                    try:
                        target = self.resolve(relative)
                        info = entry.stat(follow_symlinks=False)
                        if target.is_dir():
                            if depth >= 8:
                                excluded.append({"path": relative, "reason": "depth_limit"})
                            else:
                                pending.append((target, depth + 1))
                        elif sensitive_name(entry.name):
                            excluded.append({"path": relative, "reason": "sensitive_name"})
                        elif target.suffix.lower() not in TEXT_SUFFIXES:
                            excluded.append({"path": relative, "reason": "unsupported_type"})
                        elif info.st_size > self.max_bytes:
                            excluded.append({"path": relative, "reason": "size_limit"})
                        else:
                            included.append({"path": relative, "bytes": info.st_size})
                    except (OSError, ValueError) as exc:
                        excluded.append({"path": relative, "reason": type(exc).__name__})
        return {"files": sorted(included, key=lambda row: row["path"]), "excluded": excluded,
                "truncated": bool(pending) or visited > limit, "limit": limit}
