"""Demonstração da Fase 3 com modelo real e Edge em perfil separado."""
import json
import subprocess
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8766'
REPORT = ROOT / 'reports/local-memory-e2e.json'
result = {'checks': {}, 'tasks': []}


def check(name, condition):
    result['checks'][name] = bool(condition)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(name, bool(condition), flush=True)
    assert condition, name


def api(path, body=None):
    with httpx.Client(trust_env=False, timeout=30) as client:
        response = client.get(BASE+'/api'+path) if body is None else client.post(BASE+'/api'+path, json=body)
        response.raise_for_status()
        return response.json()


def ask(prompt):
    api('/mode', {'mode':'development'})
    task = api('/tasks', {'prompt':prompt, 'files':[]})
    deadline = time.monotonic()+180
    while time.monotonic()<deadline:
        task = api('/tasks/'+task['id'])
        if task['state'] in {'completed','failed','waiting_user','waiting_resource'}:
            result['tasks'].append(task)
            check('completed_'+str(len(result['tasks'])), task['state']=='completed')
            return task
        time.sleep(.3)
    raise TimeoutError('Modelo não concluiu')


def main():
    home = ROOT/'.runtime'/('memory-e2e-'+str(time.time_ns()))
    project = home/'project'
    project.mkdir(parents=True)
    (project/'README.md').write_text('Projeto de avaliação de memória. Nenhuma porta definida neste arquivo.', encoding='utf-8')
    (project/'app.py').write_text('def development_port():\n    return 8000\n',encoding='utf-8')
    (project/'tests').mkdir()
    (project/'tests/test_app.py').write_text('import unittest\nfrom app import development_port\nclass PortTest(unittest.TestCase):\n    def test_port(self):\n        self.assertEqual(development_port(), 9321)\n',encoding='utf-8')
    log = (ROOT/'.runtime/logs/memory-e2e.log').open('ab')
    process = None

    def start(scope=project, data=None):
        nonlocal process
        process = subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'), '-m','nexo','--port','8766',
            '--project',str(scope),'--data-dir',str(data or home/'data')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Servidor encerrou: consulte memory-e2e.log')
            try:
                api('/state')
                return
            except httpx.HTTPError:
                time.sleep(.1)
        raise TimeoutError('API não iniciou')

    def stop():
        nonlocal process
        if process and process.poll() is None:
            api('/mode',{'mode':'paused'})
            process.terminate()
            process.wait(timeout=15)
        process = None

    try:
        start()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True,
                args=['--disable-gpu','--disable-background-networking','--no-first-run'])
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(BASE,wait_until='networkidle')
                page.get_by_role('button',name='Memória',exact=True).click()
                page.get_by_label('Chave',exact=True).fill('porta de desenvolvimento')
                page.get_by_label('Conteúdo',exact=True).fill('Decisão explícita deste projeto: usar porta 9187 no servidor de desenvolvimento.')
                page.get_by_role('button',name='Guardar memória',exact=True).click()
                page.get_by_text('porta de desenvolvimento · v1',exact=True).wait_for()
                check('ui_memory_saved',len(api('/memories'))==1)
                check('ui_no_errors',not errors)
                check('ui_no_overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                page.screenshot(path=str(ROOT/'reports/local-memory-ui.png'),full_page=True)
            finally:
                browser.close()
        memory=api('/memories')[0]
        stop()
        start()
        first=ask('Qual porta de desenvolvimento foi decidida para este projeto? Responda em uma frase, usando a memória fornecida.')
        check('remember_after_restart','9187' in first['answer'])
        api('/memories/'+memory['id']+'/correct',{'key':memory['key'],'content':'Decisão explícita corrigida: usar porta 9321 no servidor de desenvolvimento.'})
        second=ask('Qual porta de desenvolvimento foi decidida para este projeto? Responda em uma frase, usando a memória fornecida.')
        check('corrected_value','9321' in second['answer'] and '9187' not in second['answer'])
        development=api('/tasks',{'kind':'development','prompt':'Ajuste development_port para respeitar a decisão registrada sobre porta de desenvolvimento deste projeto.','files':['app.py']})
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            development=api('/tasks/'+development['id'])
            if development['state'] in {'waiting_user','failed','waiting_resource'}:
                break
            time.sleep(.3)
        check('memory_guided_patch_ready',development['state']=='waiting_user')
        proposal=api('/tasks/'+development['id']+'/development')
        check('memory_guided_tests_pass',all(item['passed'] for item in proposal['checks']))
        check('memory_guided_patch_uses_decision','9321' in proposal['diff'])
        api('/tasks/'+development['id']+'/development/publish',{})
        check('decision_applied_to_project','9321' in (project/'app.py').read_text())
        api('/tasks/'+development['id']+'/development/restore',{})
        check('decision_patch_restored',(project/'app.py').read_text()=='def development_port():\n    return 8000\n')
        api('/memories/'+memory['id']+'/delete',{})
        check('all_versions_deleted',api('/memories')==[])
        check('index_deleted',api('/context/search?q=porta')==[])
        check('derived_answer_removed','9321' not in api('/tasks/'+second['id'])['answer'])
        third=ask('Qual porta de desenvolvimento foi decidida para este projeto? Se não houver evidência diga que não sabe.')
        check('forgotten_value_absent',all(value not in third['answer'] for value in ['9187','9321']))
        api('/sources',{'url':'https://www.python.org/'})
        research=ask('Segundo a fonte Python.org, o que é Python? Separe Evidência de Inferência e cite a URL. Até 100 palavras.')
        check('research_has_real_source','https://www.python.org/' in research['answer'])
        check('research_distinguishes_inference','infer' in research['answer'].casefold())
        stop()
        other=home/'other-project'
        other.mkdir()
        start(other,home/'other-data')
        check('other_project_isolated',api('/memories')==[] and api('/sources')==[])
        result['result']='passed'
        REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        stop()
        log.close()


if __name__=='__main__':
    main()
