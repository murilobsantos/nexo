"""Agenda real, UI e cinco minutos de núcleo ocioso com sensor Windows ativo."""
import ctypes
import json
import subprocess
import time
from pathlib import Path

import httpx
import psutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8766'
REPORT = ROOT/'reports/local-coexistence-e2e.json'
result = {'checks':{},'samples':[]}


def save():
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


def check(name,condition):
    result['checks'][name]=bool(condition)
    save()
    print(name,bool(condition),flush=True)
    assert condition,name


def api(path,body=None):
    with httpx.Client(trust_env=False,timeout=15) as client:
        response=client.get(BASE+'/api'+path) if body is None else client.post(BASE+'/api'+path,json=body)
        response.raise_for_status()
        return response.json()


def models():
    with httpx.Client(trust_env=False,timeout=5) as client:
        response=client.get('http://127.0.0.1:11434/api/ps')
        response.raise_for_status()
        return response.json()['models']


def main():
    home=ROOT/'.runtime'/('coexistence-'+str(time.time_ns()))
    project=home/'project'
    project.mkdir(parents=True)
    (project/'README.md').write_text('Servidor de avaliação. A porta autorizada é 4821.',encoding='utf-8')
    log=(ROOT/'.runtime/logs/coexistence-e2e.log').open('ab')
    process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-m','nexo','--port','8766','--project',str(project),'--data-dir',str(home/'data')],
        cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    identity=psutil.Process(process.pid)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Servidor encerrou; consulte coexistence-e2e.log')
            try:
                api('/state')
                break
            except httpx.HTTPError:
                time.sleep(.1)
        api('/mode',{'mode':'paused'})
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu','--disable-background-networking','--no-first-run'])
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(BASE,wait_until='networkidle')
                page.get_by_role('button',name='Agenda',exact=True).click()
                page.get_by_label('Objetivo autorizado',exact=True).fill('Consultar configuração do servidor')
                page.get_by_label('Pedido recorrente',exact=True).fill('Qual porta está autorizada no README.md? Responda em uma frase e cite o arquivo.')
                page.get_by_role('button',name='Criar agendamento',exact=True).click()
                page.get_by_text('Consultar configuração do servidor',exact=True).wait_for()
                check('schedule_created_in_ui',len(api('/automation')['schedules'])==1)
                check('paused_schedule_does_not_run',api('/tasks')==[])
                check('desktop_no_overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check('ui_no_errors',not errors)
                page.screenshot(path=str(ROOT/'reports/local-coexistence-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                check('mobile_no_overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            finally:
                browser.close()
        api('/mode',{'mode':'away'})
        deadline=time.monotonic()+180
        task=None
        while time.monotonic()<deadline:
            tasks=api('/tasks')
            if tasks:
                task=tasks[0]
                if task['state'] in {'completed','failed','waiting_resource'}:
                    break
            time.sleep(.3)
        check('scheduled_real_model_completed',task and task['state']=='completed')
        check('scheduled_answer_has_evidence','4821' in task['answer'] and 'README.md' in task['answer'])
        schedule=api('/automation')['schedules'][0]
        check('finite_budget_exhausted',schedule['runs']==1 and not schedule['enabled'])
        api('/mode',{'mode':'personal'})
        check('personal_model_unloaded',not models())
        api('/automation/config',{'enabled':True,'idle_seconds':120,'resume_when_idle':False,'game_processes':[],'min_available_mb':512})
        check('native_activity_available',api('/automation')['activity']['status']=='observing')
        user=ctypes.WinDLL('user32')
        user.GetForegroundWindow.restype=ctypes.c_void_p
        foreground=user.GetForegroundWindow()
        api('/automation')
        check('metadata_read_kept_foreground',foreground==user.GetForegroundWindow())
        started=time.monotonic()
        next_progress=30
        while True:
            members=[identity,*identity.children(recursive=True)]
            sample={'elapsed':time.monotonic()-started,'processes':[]}
            for member in members:
                try:
                    cpu=member.cpu_times()
                    sample['processes'].append({'pid':member.pid,'rss':member.memory_info().rss,'cpu_seconds':cpu.user+cpu.system})
                except psutil.NoSuchProcess:
                    pass
            result['samples'].append(sample)
            save()
            if sample['elapsed']>=next_progress:
                check('model_still_unloaded_'+str(next_progress),not models())
                print('idle_seconds',round(sample['elapsed']),flush=True)
                next_progress+=30
            if sample['elapsed']>=300:
                break
            time.sleep(2)
        first,last=result['samples'][0],result['samples'][-1]
        baseline={row['pid']:row['cpu_seconds'] for row in first['processes']}
        cpu=sum(max(0,row['cpu_seconds']-baseline.get(row['pid'],0)) for row in last['processes'])
        peak=max(sum(row['rss'] for row in sample['processes']) for sample in result['samples'])/1024**2
        result['metrics']={'seconds':last['elapsed']-first['elapsed'],'peak_core_tree_rss_mib':peak,
            'machine_cpu_percent':100*cpu/(last['elapsed']-first['elapsed'])/psutil.cpu_count(),
            'sensor_enabled':True,'mode':'personal','game_benchmark':False}
        check('idle_memory_under_400_mib',peak<400)
        check('idle_cpu_under_one_percent',result['metrics']['machine_cpu_percent']<1)
        result['result']='passed'
        save()
    finally:
        try:
            api('/mode',{'mode':'paused'})
        finally:
            if process.poll() is None:
                children=identity.children(recursive=True)
                for child in children:
                    child.terminate()
                process.terminate()
                psutil.wait_procs(children,timeout=5)
                process.wait(timeout=10)
            log.close()


if __name__=='__main__':
    main()
