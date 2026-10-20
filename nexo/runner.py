"""Comandos fixos em cópia de projeto, com recursos/saída/tempo limitados."""
import asyncio
import os
import subprocess
import sys
import threading
import time
import uuid
import re
from pathlib import Path

from .jobs import Job

CHECKS = {"python-tests", "python-check", "node-tests", "npm-build"}


class Runner:
    def __init__(self, max_output=128 * 1024):
        self.max_output = max_output

    async def run(self, directory, check, timeout=30):
        if check not in CHECKS:
            raise PermissionError("Comando não registrado")
        if not 0 < timeout <= 120:
            raise ValueError("Timeout fora do orçamento")
        directory = Path(directory).resolve(strict=True)
        bootstrap = Path(__file__).with_name("check_bootstrap.py").resolve()
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT"}}
        temp = directory / ".tmp"
        temp.mkdir(exist_ok=True)
        environment.update({"TEMP": str(temp), "TMP": str(temp), "PYTHONIOENCODING": "utf-8"})
        output = bytearray()
        overflow = threading.Event()
        job = Job()
        process = None
        reader = None
        started = time.monotonic()
        result = {"check": check, "timeout_seconds": timeout, "memory_limit_mb": 512,
                  "cpu_cap_percent": 25, "cancelled": False, "timed_out": False}
        try:
            # Evitar o redirecionador de venv do Windows: ele pode criar o intérprete
            # filho antes de o pai entrar no Job. O bootstrap usa somente stdlib.
            interpreter = Path(sys.base_prefix) / "python.exe"
            # Não reutilizar .pyc do baseline após patch de mesmo tamanho/segundo.
            cache_prefix = str(temp / ("bytecode-" + uuid.uuid4().hex))
            process = subprocess.Popen([str(interpreter), "-I", "-B", "-X", "pycache_prefix=" + cache_prefix, str(bootstrap), check], cwd=directory,
                env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
            result["pid"] = process.pid
            job.assign(process.pid)
            def read():
                while True:
                    chunk = process.stdout.read(4096)
                    if not chunk:
                        break
                    remaining = self.max_output - len(output)
                    output.extend(chunk[:max(remaining, 0)])
                    if len(chunk) > remaining:
                        overflow.set()
                        break
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            process.stdin.write(b"NEXO-GO\n")
            process.stdin.close()
            while process.poll() is None:
                if overflow.is_set():
                    result["output_limit_exceeded"] = True
                    break
                if time.monotonic() - started > timeout:
                    result["timed_out"] = True
                    break
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            result["cancelled"] = True
            raise
        finally:
            job.close()  # também encerra filhos ainda vivos após o processo principal sair
            if process:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                if reader:
                    reader.join(timeout=2)
                if process.stdout:
                    process.stdout.close()
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                result["exit_code"] = process.returncode
            result["output"] = output.decode("utf-8", errors="replace")
            result["output_bytes"] = len(output)
            result["output_limit_exceeded"] = overflow.is_set()
            result["elapsed_seconds"] = time.monotonic() - started
        result["passed"] = result.get("exit_code") == 0 and not any(result.get(k) for k in ("timed_out", "cancelled", "output_limit_exceeded"))
        if check == "node-tests" and not re.search(r"^# tests [1-9][0-9]*\s*$", result["output"], re.MULTILINE):
            result.update(passed=False, no_tests_confirmed=True)
        return result
