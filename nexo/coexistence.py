"""Metadados de atividade da sessão Windows; sem captura de teclas ou tela."""
import asyncio
import ctypes
import json
import os
from ctypes import wintypes

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoexistenceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    idle_seconds: int = Field(default=120,ge=10,le=3600)
    resume_when_idle: bool = False
    game_processes: list[str] = Field(default_factory=list,max_length=20)
    min_available_mb: int = Field(default=2048,ge=512,le=8192)

    @field_validator('game_processes')
    @classmethod
    def names_only(cls,values):
        if any(not value.lower().endswith('.exe') or len(value)>100 or any(char in value for char in '/\\:*?') for value in values):
            raise ValueError('Informe nomes exatos de executáveis .exe, sem caminhos')
        return list(dict.fromkeys(value.casefold() for value in values))


def sample_activity(game_processes=()):
    if os.name != 'nt':
        raise OSError('Detecção disponível somente no Windows')
    class LastInput(ctypes.Structure):
        _fields_ = [('cbSize',wintypes.UINT),('dwTime',wintypes.DWORD)]
    user = ctypes.WinDLL('user32',use_last_error=True)
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    user.GetLastInputInfo.argtypes = [ctypes.POINTER(LastInput)]
    user.GetLastInputInfo.restype = wintypes.BOOL
    kernel.GetTickCount64.restype = ctypes.c_ulonglong
    value = LastInput()
    value.cbSize = ctypes.sizeof(value)
    if not user.GetLastInputInfo(ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    idle = ((kernel.GetTickCount64()-value.dwTime)&0xffffffff)/1000
    games = set(game_processes)
    matched = []
    if games:
        for process in psutil.process_iter(['name']):
            try:
                name = (process.info['name'] or '').casefold()
                if name in games:
                    matched.append(name)
            except (psutil.NoSuchProcess,psutil.AccessDenied):
                pass
    return {'last_input':value.dwTime,'idle_seconds':idle,'game_processes':sorted(set(matched)),
            'available_mb':psutil.virtual_memory().available/1024**2}


class Coexistence:
    def __init__(self,store,worker,scheduler,sampler=sample_activity):
        self.store,self.worker,self.scheduler = store,worker,scheduler
        self.sampler = sampler
        self.task = None
        self.last_input = None
        self.auto_paused = None
        self.snapshot = {'enabled':False,'status':'disabled'}
        worker.on_manual_mode = self.manual

    def config(self):
        with self.store.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='coexistence'").fetchone()
        return CoexistenceInput.model_validate_json(row[0]) if row else CoexistenceInput()

    def configure(self,value):
        with self.store.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('coexistence',?)",(value.model_dump_json(),))
        self.manual()
        return value.model_dump()

    def manual(self):
        self.auto_paused = None
        self.last_input = None

    async def tick(self):
        config = self.config()
        if not config.enabled:
            self.snapshot = {'enabled':False,'status':'disabled'}
            self.worker.allow_claim = True
            self.scheduler.tick()
            return
        try:
            sample = await asyncio.to_thread(self.sampler,config.game_processes)
        except (OSError,psutil.Error):
            self.worker.allow_claim = False
            self.snapshot = {'enabled':True,'status':'unavailable'}
            if self.store.mode() in {'away','development'}:
                await self.worker.set_mode('paused',automatic=True)
            self.scheduler.notify('activity_unavailable','Detecção indisponível. Execução pausada; revise o modo manualmente.')
            return
        self.snapshot = {'enabled':True,'status':'observing',**sample}
        mode = self.store.mode()
        self.worker.allow_claim = sample['available_mb'] >= config.min_available_mb
        if sample['game_processes'] and mode in {'development','away'}:
            self.auto_paused = None
            await self.worker.set_mode('personal',automatic=True)
            self.scheduler.notify('game_detected','Processo configurado detectado. Modo pessoal ativado e descarga solicitada.')
        elif not self.worker.allow_claim and mode in {'development','away'}:
            self.auto_paused = None
            await self.worker.set_mode('paused',automatic=True)
            self.scheduler.notify('memory_pressure','Memória disponível abaixo do limite. Execução pausada.')
        elif mode == 'away' and self.last_input is not None and sample['last_input'] != self.last_input and sample['idle_seconds'] < config.idle_seconds:
            task_id = self.worker.active_id
            await self.worker.set_mode('paused',automatic=True)
            self.auto_paused = task_id or ''
            self.scheduler.notify('user_returned','Atividade detectada. Trabalho ausente pausado, com checkpoint preservado.')
        elif mode == 'paused' and self.auto_paused is not None and config.resume_when_idle and sample['idle_seconds'] >= config.idle_seconds:
            task_id = self.auto_paused
            self.auto_paused = None
            if task_id and self.store.get(task_id)['state']=='paused':
                self.store.resume(task_id)
            await self.worker.set_mode('away',automatic=True)
        self.last_input = sample['last_input']
        if self.worker.allow_claim:
            self.scheduler.tick()

    async def loop(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.worker.allow_claim = False
                self.snapshot = {'enabled':self.config().enabled,'status':'error'}
                self.scheduler.notify('scheduler_error','Agenda interrompida por erro; consulte o diagnóstico antes de retomar.')
            await asyncio.sleep(.5 if self.config().enabled else 2)

    async def start(self):
        await self.tick()
        self.task = asyncio.create_task(self.loop())

    async def close(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
