"""Comparação sintética local; não substitui benchmark de jogo real."""
import json
import statistics
import socket
import subprocess
import time
from pathlib import Path

import httpx
import psutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/local-graphics-comparison.json'


def api(path,body=None):
    with httpx.Client(trust_env=False,timeout=8) as client:
        response=client.get('http://127.0.0.1:8766/api'+path) if body is None else client.post('http://127.0.0.1:8766/api'+path,json=body)
        response.raise_for_status()
        return response.json()


def main():
    for port in (8765,8766,11434):
        try:
            connection=socket.create_connection(('127.0.0.1',port),timeout=.3)
        except OSError:
            continue
        connection.close()
        raise RuntimeError(f'Porta {port} ocupada; pare o runtime antes da comparação')
    home=ROOT/'.runtime'/('graphics-'+str(time.time_ns()))
    home.mkdir(parents=True)
    result={'kind':'synthetic_webgl','game_benchmark':False,'resolution':[1280,720],
            'shader_iterations':64,'measurement':'draw plus synchronous one-pixel readback',
            'order':[False,True,True,False,False,True],'runs':[]}
    process=None
    log=(ROOT/'.runtime/logs/graphics-server.log').open('ab')

    def stop():
        nonlocal process
        if process and process.poll() is None:
            try:
                api('/mode',{'mode':'paused'})
            finally:
                children=psutil.Process(process.pid).children(recursive=True)
                for child in children:
                    child.terminate()
                process.terminate()
                _,alive=psutil.wait_procs(children,timeout=5)
                for child in alive:
                    child.kill()
                psutil.wait_procs(alive,timeout=2)
                process.wait(timeout=5)
        process=None

    def start():
        nonlocal process
        if process is not None:
            if process.poll() is not None:
                raise RuntimeError('Servidor anterior encerrou inesperadamente')
            return
        process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-m','nexo','--project',str(ROOT/'demo'),
            '--data-dir',str(home),'--port','8766'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Servidor não iniciou')
            try:
                api('/automation')
                time.sleep(.1)
                if process.poll() is not None:
                    raise RuntimeError('Servidor não permaneceu ativo')
                break
            except httpx.HTTPError:
                time.sleep(.1)
        api('/mode',{'mode':'personal'})
        api('/automation/config',{'enabled':True,'game_processes':[],'min_available_mb':512})

    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True,args=['--disable-background-networking','--no-first-run','--use-angle=d3d11'])
            try:
                page=browser.new_page(viewport={'width':1280,'height':720})
                page.route('**/*',lambda route:route.abort())
                page.set_content((ROOT/'tools/graphics_probe.html').read_text(encoding='utf-8'))
                result['renderer']=page.evaluate('window.renderer')
                if not any(name in result['renderer'].casefold() for name in ['nvidia','amd','intel']) or any(name in result['renderer'].casefold() for name in ['swiftshader','software','basic render']):
                    raise RuntimeError('Renderizador de hardware não comprovado: '+result['renderer'])
                print('renderer',result['renderer'],flush=True)
                warmup=page.evaluate('window.probe(5)')
                if statistics.median(warmup['draw_readback_ms'])<=0 or not warmup['pixel_checksum']:
                    raise RuntimeError('Medição sem tempo ou imagem verificável; comparação inconclusiva')
                for index,enabled in enumerate(result['order']):
                    start() if enabled else stop()
                    if enabled:
                        if api('/state')['mode']!='personal' or not api('/automation')['config']['enabled']:
                            raise RuntimeError('Perfil pessoal/sensor não confirmado')
                    else:
                        try:
                            unexpected=socket.create_connection(('127.0.0.1',8766),timeout=.3)
                        except OSError:
                            pass
                        else:
                            unexpected.close()
                            raise RuntimeError('Núcleo ainda disponível durante controle sem NEXO')
                    page.evaluate('window.probe(2)')
                    sample=page.evaluate('window.probe(15)')
                    if sample['error']:
                        raise RuntimeError('Erro WebGL '+str(sample['error']))
                    sample.update(core_enabled=enabled,index=index,median_draw_readback_ms=statistics.median(sample['draw_readback_ms']),
                        median_frame_interval_ms=statistics.median(sample['frame_intervals_ms']))
                    result['runs'].append(sample)
                    REPORT.write_text(json.dumps(result,indent=2),encoding='utf-8')
                    print('run',index,'core',enabled,'median_ms',round(sample['median_draw_readback_ms'],3),flush=True)
                baseline=[row['median_draw_readback_ms'] for row in result['runs'] if not row['core_enabled']]
                active=[row['median_draw_readback_ms'] for row in result['runs'] if row['core_enabled']]
                if min(baseline+active)<=0:
                    raise RuntimeError('Precisão temporal insuficiente; comparação inconclusiva')
                result['summary']={'baseline_median_ms':statistics.median(baseline),'personal_median_ms':statistics.median(active),
                    'difference_percent':100*(statistics.median(active)/statistics.median(baseline)-1),
                    'baseline_run_range_ms':[min(baseline),max(baseline)],'personal_run_range_ms':[min(active),max(active)],
                    'acceptance':'observational_only; no agreed game threshold'}
                result['result']='measured'
                REPORT.write_text(json.dumps(result,indent=2),encoding='utf-8')
                print(json.dumps(result['summary']),flush=True)
            finally:
                browser.close()
    finally:
        stop()
        log.close()


if __name__=='__main__':
    main()
