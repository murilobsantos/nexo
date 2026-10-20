"""Preparo cancelável em processo separado, sem carregar código do projeto."""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .jobs import Job


async def prepare_workspace(workspace, timeout=30):
    request = {'operation':'prepare','source':str(workspace.source.root),'home':str(workspace.home),
               'id':workspace.id,'imports':[str(Path(__file__).resolve().parents[1]),
                                          str(Path(sys.prefix)/'Lib/site-packages')]}
    environment = {key:value for key,value in os.environ.items() if key.upper() in {'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP'}}
    process, reader = None, None
    output = bytearray()
    overflow = threading.Event()
    job = Job()
    started = time.monotonic()
    try:
        process = subprocess.Popen([str(Path(sys.base_prefix)/'python.exe'),'-I','-B',str(Path(__file__).with_name('io_bootstrap.py'))],
            cwd=Path(__file__).resolve().parents[1],env=environment,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,close_fds=True)
        job.assign(process.pid)

        def read():
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                remaining = 1024**2 - len(output)
                output.extend(chunk[:max(remaining,0)])
                if len(chunk)>remaining:
                    overflow.set()
                    break

        reader = threading.Thread(target=read,daemon=True)
        reader.start()
        process.stdin.write(b'NEXO-GO\n'+json.dumps(request).encode('utf-8')+b'\n')
        process.stdin.close()
        while process.poll() is None:
            if overflow.is_set():
                raise ValueError('Saída de preparo excedeu 1 MiB')
            if time.monotonic()-started>timeout:
                raise TimeoutError('Preparo excedeu orçamento')
            await asyncio.sleep(.025)
    finally:
        job.close()
        if process:
            if process.poll() is None:
                process.kill()
            # Aguardar fora do loop da API, inclusive ao receber cancelamento.
            await asyncio.to_thread(process.wait, 2)
            if reader:
                await asyncio.to_thread(reader.join, 2)
            if process.stdout:
                process.stdout.close()
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
    if overflow.is_set():
        raise ValueError('Saída de preparo excedeu 1 MiB')
    if process.returncode:
        raise ValueError('Falha no preparo isolado: '+output.decode('utf-8',errors='replace')[-500:])
    return json.loads(output.decode('utf-8'))
