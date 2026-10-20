import asyncio
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from nexo.coexistence import Coexistence, CoexistenceInput
from nexo.files import ScopedFiles
from nexo.scheduling import Scheduler, ScheduleInput
from nexo.store import Store
from nexo.worker import Worker
from nexo.knowledge import Knowledge, MemoryInput


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/'nexo.db')
        self.now = time.time()
        self.scheduler = Scheduler(self.store,lambda:self.now)

    def schedule(self,**changes):
        values = {'objective':'Verificar progresso do projeto','task':{'prompt':'Leia README.md','files':['README.md']},
                  'start_at':datetime.fromtimestamp(self.now,timezone.utc),'expires_at':datetime.fromtimestamp(self.now+600,timezone.utc),
                  'max_runs':2,'interval_seconds':60}
        return self.scheduler.create(ScheduleInput(**(values|changes)))

    def test_modes_budget_no_overlap_and_no_catch_up_flood(self):
        schedule = self.schedule()
        self.now += .001
        for mode in ['paused','personal','development']:
            self.store.mode(mode)
            self.assertIsNone(self.scheduler.tick())
        self.store.mode('away')
        first = self.scheduler.tick()
        self.assertIsNotNone(first)
        self.now += 300
        self.assertIsNone(self.scheduler.tick())
        self.store.finish(first,'completed')
        second = self.scheduler.tick()
        self.assertIsNotNone(second)
        self.store.finish(second,'completed')
        self.now += 300
        self.assertIsNone(self.scheduler.tick())
        final = self.scheduler.list()[0]
        self.assertEqual(final['runs'],2)
        self.assertFalse(final['enabled'])
        self.assertEqual(self.store.events(first)[0]['data']['schedule_id'],schedule['id'])

    def test_deadline_disable_and_persistence(self):
        schedule = self.schedule()
        self.scheduler.disable(schedule['id'])
        self.store.mode('away')
        self.assertIsNone(Scheduler(Store(self.store.path),lambda:self.now).tick())
        self.schedule()
        self.now += 601
        self.assertIsNone(self.scheduler.tick())
        self.assertTrue(all(not row['enabled'] for row in self.scheduler.list()))

    def test_notice_cooldown_and_hourly_budget(self):
        self.assertTrue(self.scheduler.notify('return','Pausado'))
        self.assertFalse(self.scheduler.notify('return','Pausado'))
        self.assertTrue(self.scheduler.notify('memory','Memória'))
        self.assertTrue(self.scheduler.notify('game','Jogo'))
        self.assertFalse(self.scheduler.notify('other','Outra'))
        self.now += 3601
        self.assertTrue(self.scheduler.notify('return','Pausado'))

    def test_invalid_unbounded_schedule_rejected(self):
        with self.assertRaises(ValueError):
            self.schedule(max_runs=0)
        with self.assertRaises(ValueError):
            self.schedule(interval_seconds=1)
        with self.assertRaises(ValueError):
            self.schedule(expires_at=datetime.fromtimestamp(self.now-1,timezone.utc))

    def test_v3_migration_backs_up_and_preserves_memory(self):
        memory = Knowledge(self.store).put_memory(MemoryInput(key='porta',content='Porta 9321'))
        with self.store.connect() as conn:
            conn.executescript('DROP TABLE schedules; DROP TABLE notices; PRAGMA user_version=3;')
        migrated = Store(self.store.path)
        self.assertEqual(Knowledge(migrated).search('porta')[0]['item_id'],memory['id'])
        with migrated.connect() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],4)
        backup = next((self.store.path.parent/'migration-backups').glob('v3-*.db'))
        with Store.readonly(backup.resolve()) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],3)
            self.assertEqual(conn.execute('SELECT content FROM memories').fetchone()[0],'Porta 9321')
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='schedules'").fetchone())


class BlockingGateway:
    model = 'fixture'
    def __init__(self):
        self.started = asyncio.Event()
        self.unloaded = False
    async def stream(self,messages,max_tokens):
        self.started.set()
        yield {'text':'Início'}
        await asyncio.Event().wait()
    async def unload(self):
        self.unloaded = True


class CoexistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root/'nexo.db')
        self.gateway = BlockingGateway()
        self.worker = Worker(self.store,ScopedFiles(self.root),self.gateway)
        self.sample = {'last_input':1,'idle_seconds':200,'game_processes':[],'available_mb':4096}
        self.monitor = Coexistence(self.store,self.worker,Scheduler(self.store),lambda games:dict(self.sample))
        self.monitor.configure(CoexistenceInput(enabled=True,resume_when_idle=True))

    async def test_return_pauses_and_idle_resumes_checkpoint(self):
        await self.worker.set_mode('away')
        await self.monitor.tick()
        task = self.store.create(prompt='Trabalho autorizado',files=[])
        await self.worker.start()
        try:
            await asyncio.wait_for(self.gateway.started.wait(),2)
            self.sample.update(last_input=2,idle_seconds=0)
            started = time.monotonic()
            await self.monitor.tick()
            self.assertLess(time.monotonic()-started,2)
            self.assertEqual(self.store.mode(),'paused')
            self.assertEqual(self.store.get(task['id'])['state'],'paused')
            self.assertTrue(self.gateway.unloaded)
            self.sample['idle_seconds']=200
            await self.monitor.tick()
            self.assertEqual(self.store.mode(),'away')
            self.assertIn(self.store.get(task['id'])['state'],{'ready','running'})
        finally:
            await self.worker.close()

    async def test_manual_mode_overrides_auto_resume(self):
        self.monitor.auto_paused = ''
        await self.worker.set_mode('personal')
        await self.monitor.tick()
        self.assertEqual(self.store.mode(),'personal')
        self.assertIsNone(self.monitor.auto_paused)

    async def test_game_and_memory_pressure_pause(self):
        self.store.mode('development')
        self.sample['game_processes']=['fixture-game.exe']
        await self.monitor.tick()
        self.assertEqual(self.store.mode(),'personal')
        self.assertTrue(self.gateway.unloaded)
        self.sample.update(game_processes=[],available_mb=1000)
        await self.worker.set_mode('away')
        await self.monitor.tick()
        self.assertEqual(self.store.mode(),'paused')
        self.assertFalse(self.worker.allow_claim)

    async def test_missing_sensor_fails_closed(self):
        def unavailable(games):
            raise OSError('Sem sessão')
        self.monitor.sampler = unavailable
        self.store.mode('away')
        await self.monitor.tick()
        self.assertEqual(self.store.mode(),'paused')
        self.assertFalse(self.worker.allow_claim)
