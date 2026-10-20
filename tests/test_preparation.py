import asyncio
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import psutil

from nexo.developer import Developer
from nexo.files import ScopedFiles
from nexo.store import Store
from nexo.worker import Worker


class NoGeneration:
    model = 'not-used'
    async def unload(self):
        pass
    async def stream(self,*args):
        raise AssertionError('Não deve chegar à geração')
        yield


class PreparationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_kills_slow_git_descendant_and_preserves_source(self):
        compiler = Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():
            self.skipTest('Compilador C# do Windows ausente para fixture de processo lento')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root/'bin'
            binary.mkdir()
            source = binary/'SlowGit.cs'
            source.write_text('''using System; using System.IO; using System.Diagnostics; using System.Reflection; using System.Threading;
class SlowGit { static void Main() { File.WriteAllText(Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location), "started.txt"), Process.GetCurrentProcess().Id.ToString()); Thread.Sleep(30000); } }
''',encoding='utf-8')
            compiled = subprocess.run([str(compiler),'/nologo','/target:exe','/out:'+str(binary/'git.exe'),str(source)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
            self.assertEqual(compiled.returncode,0,compiled.stdout)
            project = root/'project'
            project.mkdir()
            original = b'def value():\n    return 1\n'
            (project/'app.py').write_bytes(original)
            store = Store(root/'data/nexo.db')
            gateway = NoGeneration()
            files = ScopedFiles(project)
            developer = Developer(store,files,gateway,root/'copies')
            worker = Worker(store,files,gateway,developer)
            task = store.create(kind='development',prompt='Preparar cópia',files=['app.py'])
            with patch.dict(os.environ,{'PATH':str(binary)+os.pathsep+os.environ['PATH']}):
                await worker.start()
                try:
                    deadline = time.monotonic()+10
                    while not (binary/'started.txt').exists() and time.monotonic()<deadline:
                        await asyncio.sleep(.025)
                    self.assertTrue((binary/'started.txt').exists(),'Git lento não foi iniciado')
                    pid = int((binary/'started.txt').read_text())
                    started = time.monotonic()
                    await worker.set_mode('paused')
                    elapsed = time.monotonic()-started
                    self.assertLess(elapsed,2)
                    print(f'Pause during slow Git: {elapsed:.3f}s; descendant PID {pid} terminated.',flush=True)
                    self.assertFalse(psutil.pid_exists(pid),'Descendente continuou vivo')
                    self.assertEqual(store.get(task['id'])['state'],'paused')
                    self.assertEqual((project/'app.py').read_bytes(),original)
                    self.assertEqual(developer.workspace(task['id']).load()['status'],'interrupted')
                    self.assertTrue(any(row['kind']=='checkpoint' for row in store.events(task['id'])))
                finally:
                    await worker.close()
