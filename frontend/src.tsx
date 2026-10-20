/// <reference types="vite/client" />
import * as React from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Task = {id:string; prompt:string; answer:string; state:string; error:string|null; files:string[]; created:string; attempts:number;kind:'chat'|'development'};
type State = {mode:string; scope:string; project_name:string; model:string; active_task:string|null; backend:{available:boolean; model_installed:boolean;model_changed?:boolean}};
type Entry = {seq:number; kind:string; created:string; data:unknown};
type Candidate = {id:string;status:string;summary:string;diff:string;files:{path:string}[];checks:{check:string;passed:boolean;output:string;elapsed_seconds:number}[]};
const labels:Record<string,string> = {ready:'Na fila', running:'Em execução', completed:'Concluída', failed:'Falhou', paused:'Pausada', cancelled:'Cancelada', waiting_resource:'Aguardando recurso', waiting_user:'Aguardando você'};
const modes:Record<string,string> = {development:'Desenvolvimento', paused:'Pausado', personal:'Pessoal / jogo', away:'Ausente'};
const terminal = new Set(['completed','failed','paused','cancelled','waiting_resource','waiting_user']);

async function api<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch('/api'+path, body === undefined ? undefined : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Confira os dados da solicitação.');
  return data;
}

function FormattedAnswer({text}:{text:string}) {
  const blocks=text.split(/```[^\n]*\n([\s\S]*?)```/g);
  return <>{blocks.map((block,index)=>index%2
    ?<pre key={index}><code>{block}</code></pre>
    :<React.Fragment key={index}>{block.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g).map((part,i)=>part.startsWith('`')?<code key={i}>{part.slice(1,-1)}</code>:part.startsWith('**')?<strong key={i}>{part.slice(2,-2)}</strong>:<React.Fragment key={i}>{part}</React.Fragment>)}</React.Fragment>)}</>;
}

function DevelopmentPanel({task,mode,onChange}:{task:Task;mode:string;onChange:()=>Promise<void>}) {
  const [candidate,setCandidate]=React.useState<Candidate|null>(null);
  const [error,setError]=React.useState('');
  const [busy,setBusy]=React.useState(false);
  React.useEffect(()=>{
    let active=true;
    if(terminal.has(task.state)) api<Candidate>(`/tasks/${task.id}/development`).then(value=>{if(active)setCandidate(value);}).catch(()=>{});
    return ()=>{active=false;};
  },[task.id,task.state]);
  async function apply(action:'publish'|'reject'|'restore') {
    setBusy(true);setError('');
    try {await api(`/tasks/${task.id}/development/${action}`,{});setCandidate(await api<Candidate>(`/tasks/${task.id}/development`));await onChange();}
    catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  if(!candidate)return <p className="development-note">{task.state==='running'?'Preparando cópia, patch e verificações…':'As evidências da alteração aparecerão aqui.'}</p>;
  const statuses:Record<string,string>={review:'Pronta para revisão',applied:'Aplicada ao projeto',restored:'Original restaurado',rejected:'Proposta rejeitada',failed:'Verificação falhou',interrupted:'Execução interrompida',needs_recovery:'Restauração necessária'};
  const canWrite=['development','away'].includes(mode);
  return <section className="development-panel"><div className="development-title"><strong>Alteração isolada</strong><span>{statuses[candidate.status]||candidate.status}</span></div>
    <div className="attachments">{candidate.files.map(file=><span key={file.path}>▧ {file.path}</span>)}</div>
    <div className="diff" aria-label="Diff da alteração"><pre>{candidate.diff.split('\n').map((line,index)=><span key={index} className={line.startsWith('+')?'added':line.startsWith('-')?'removed':line.startsWith('@@')?'hunk':''}>{line}{'\n'}</span>)}</pre></div>
    <div className="check-results">{candidate.checks.map((check,index)=><details key={index}><summary>{check.passed?'✓':'×'} {check.check} · {check.passed?'aprovado':'falhou'} · {check.elapsed_seconds?.toFixed(1)} s</summary><pre>{check.output||'Sem saída adicional.'}</pre></details>)}</div>
    {error&&<p className="task-error" role="alert">{error}</p>}
    <div className="review-actions">{candidate.status==='review'&&task.state==='waiting_user'&&<><button disabled={busy||!canWrite} onClick={()=>apply('publish')}>Aplicar ao projeto</button><button disabled={busy} onClick={()=>apply('reject')}>Rejeitar proposta</button></>}{['applied','applying','needs_recovery'].includes(candidate.status)&&<button disabled={busy||!canWrite} onClick={()=>apply('restore')}>Restaurar original</button>}</div>
    {!canWrite&&['review','applied','needs_recovery'].includes(candidate.status)&&<small>Retome o modo de desenvolvimento para aplicar ou restaurar.</small>}
  </section>;
}

function KnowledgePanel({onChange}:{onChange:()=>Promise<void>}) {
  type Memory={id:string;key:string;content:string;version:number;validation:string;category:string;scope:string};
  const [memories,setMemories]=React.useState<Memory[]>([]);
  const [sources,setSources]=React.useState<{id:string;title:string;source:string}[]>([]);
  const [key,setKey]=React.useState('');const [content,setContent]=React.useState('');
  const [url,setUrl]=React.useState('');const [editing,setEditing]=React.useState<Memory|null>(null);
  const [memoryKind,setMemoryKind]=React.useState('project');
  const [error,setError]=React.useState('');const [busy,setBusy]=React.useState(false);
  const [exclusions,setExclusions]=React.useState<{path:string;reason:string}[]>([]);
  async function load(){setMemories(await api<Memory[]>('/memories'));setSources(await api<typeof sources>('/sources'));setExclusions((await api<{excluded:typeof exclusions}>('/project/catalog')).excluded);}
  React.useEffect(()=>{load().catch(e=>setError(e.message));},[]);
  async function run(operation:()=>Promise<unknown>){setBusy(true);setError('');try{await operation();await load();await onChange();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  return <div className="event-list knowledge-panel"><p>Memórias deste projeto. Alterações pausam a execução; retome quando terminar.</p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{await api(editing?`/memories/${editing.id}/correct`:'/memories',{key,content,category:editing?.category||(memoryKind==='project'?'project':'profile'),scope:editing?.scope||(memoryKind==='global'?'global':'project')});setKey('');setContent('');setEditing(null);});}}>
      {!editing&&<label>Escopo<select value={memoryKind} onChange={e=>setMemoryKind(e.target.value)}><option value="project">Decisão deste projeto</option><option value="preference">Preferência deste projeto</option><option value="global">Perfil compartilhado entre projetos</option></select></label>}
      <label>Chave<input required maxLength={120} value={key} disabled={Boolean(editing)} onChange={e=>setKey(e.target.value)}/></label>
      <label>Conteúdo<textarea required maxLength={4000} value={content} onChange={e=>setContent(e.target.value)}/></label>
      <button disabled={busy}>{editing?'Salvar correção':'Guardar memória'}</button>{editing&&<button type="button" onClick={()=>{setEditing(null);setKey('');setContent('');}}>Cancelar edição</button>}
    </form>
    {memories.map(m=><article key={m.id}><strong>{m.key} · v{m.version}</strong><small>{m.scope==='global'?'Perfil compartilhado':'Projeto atual'} · {m.validation}</small><p>{m.content}</p>
      {['validated','conflict','candidate'].includes(m.validation)&&<><button disabled={busy} onClick={()=>{setEditing(m);setKey(m.key);setContent(m.content);}}>Corrigir</button>{m.validation==='conflict'&&<button disabled={busy} onClick={()=>run(()=>api(`/memories/${m.id}/resolve`,{}))}>Usar esta versão</button>}<button disabled={busy} onClick={()=>run(()=>api(`/memories/${m.id}/delete`,{}))}>Apagar histórico desta memória</button></>}
    </article>)}
    <form onSubmit={e=>{e.preventDefault();run(async()=>{await api('/sources',{url});setUrl('');});}}><label>Fonte pública por URL<input type="url" required value={url} onChange={e=>setUrl(e.target.value)}/></label><button disabled={busy}>Importar fonte</button></form>
    {sources.map(s=><article key={s.id}><strong>{s.title}</strong><p>{s.source}</p><button disabled={busy} onClick={()=>run(()=>api(`/sources/${s.id}/delete`,{}))}>Apagar fonte</button></article>)}
    <button disabled={busy} onClick={()=>run(()=>api('/project/index',{}))}>Indexar arquivos do projeto</button>
    <details><summary>Exclusões do catálogo ({exclusions.length})</summary>{exclusions.map((entry,index)=><p key={index}>{entry.path} · {entry.reason}</p>)}</details>
    {error&&<p role="alert">{error}</p>}
  </div>;
}

function AutomationPanel({files,onChange}:{files:string[];onChange:()=>Promise<void>}) {
  type Config={enabled:boolean;idle_seconds:number;resume_when_idle:boolean;game_processes:string[];min_available_mb:number};
  type Automation={config:Config;activity:{status:string;idle_seconds?:number};schedules:{id:string;objective:string;runs:number;max_runs:number;enabled:boolean;next_run:number;last_reason:string|null}[];notices:{id:number;text:string;created:number}[]};
  const [data,setData]=React.useState<Automation|null>(null);const [draft,setDraft]=React.useState<Config|null>(null);
  const [objective,setObjective]=React.useState('');const [prompt,setPrompt]=React.useState('');
  const [interval,setIntervalMinutes]=React.useState(60);const [runs,setRuns]=React.useState(1);const [hours,setHours]=React.useState(24);
  const [busy,setBusy]=React.useState(false);const [error,setError]=React.useState('');
  const activityLabels:Record<string,string>={disabled:'Desligada',observing:'Observando atividade',unavailable:'Sensor indisponível',error:'Revisão necessária'};
  const scheduleLabels:Record<string,string>={enqueued:'Tarefa criada',expired:'Prazo encerrado',disabled_by_user:'Desativado por você'};
  async function load(){const value=await api<Automation>('/automation');setData(value);setDraft(previous=>previous||value.config);}
  React.useEffect(()=>{load().catch(e=>setError(e.message));const timer=window.setInterval(()=>load().catch(e=>setError(e.message)),4000);return()=>window.clearInterval(timer);},[]);
  async function run(operation:()=>Promise<unknown>){setBusy(true);setError('');try{await operation();await load();await onChange();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
  if(!draft)return <p>Carregando agenda…</p>;
  return <div className="event-list knowledge-panel"><p>Agenda limitada ao projeto atual. Detecção usa tempo desde a última atividade e nomes de processos configurados, sem registrar teclas ou imagens.</p>
    <form onSubmit={e=>{e.preventDefault();run(()=>api('/automation/config',draft));}}>
      <label><input type="checkbox" checked={draft.enabled} onChange={e=>setDraft({...draft,enabled:e.target.checked})}/> Detectar retorno e processos de jogo</label>
      <label>Ociosidade para retomar (segundos)<input type="number" min={10} max={3600} value={draft.idle_seconds} onChange={e=>setDraft({...draft,idle_seconds:Number(e.target.value)})}/></label>
      <label><input type="checkbox" checked={draft.resume_when_idle} onChange={e=>setDraft({...draft,resume_when_idle:e.target.checked})}/> Retomar por ociosidade após pausa automática</label>
      <label>Jogos (nomes .exe separados por vírgula)<input defaultValue={draft.game_processes.join(', ')} onChange={e=>setDraft({...draft,game_processes:e.target.value.split(',').map(value=>value.trim()).filter(Boolean)})}/></label>
      <label>RAM disponível mínima (MiB)<input type="number" min={512} max={8192} value={draft.min_available_mb} onChange={e=>setDraft({...draft,min_available_mb:Number(e.target.value)})}/></label>
      <button disabled={busy}>Salvar convivência</button><small>Estado: {activityLabels[data?.activity.status||'disabled']||'Revisão necessária'}{data?.activity.idle_seconds!==undefined?` · ${Math.floor(data.activity.idle_seconds)} s sem atividade`:''}. O modo manual tem precedência.</small>
    </form>
    <form onSubmit={e=>{e.preventDefault();const now=Date.now();run(async()=>{await api('/schedules',{objective,task:{prompt,files},start_at:new Date(now+5000).toISOString(),expires_at:new Date(now+hours*3600000).toISOString(),interval_seconds:interval*60,max_runs:runs,away_only:true});setObjective('');setPrompt('');});}}>
      <label>Objetivo autorizado<input required maxLength={1000} value={objective} onChange={e=>setObjective(e.target.value)}/></label>
      <label>Pedido recorrente<textarea required maxLength={4000} value={prompt} onChange={e=>setPrompt(e.target.value)}/></label>
      <small>Consulta {files.length} arquivos selecionados. Executa somente no modo Ausente.</small>
      <label>Intervalo (minutos)<input type="number" min={1} max={43200} value={interval} onChange={e=>setIntervalMinutes(Number(e.target.value))}/></label>
      <label>Máximo de execuções<input type="number" min={1} max={100} value={runs} onChange={e=>setRuns(Number(e.target.value))}/></label>
      <label>Expira em (horas)<input type="number" min={1} max={2160} value={hours} onChange={e=>setHours(Number(e.target.value))}/></label>
      <button disabled={busy}>Criar agendamento</button>
    </form>
    {data?.schedules.map(schedule=><article key={schedule.id}><strong>{schedule.objective}</strong><p>{schedule.runs}/{schedule.max_runs} execuções · {schedule.enabled?'Ativo':'Encerrado'}</p><small>{scheduleLabels[schedule.last_reason||'']||'Aguardando horário e modo Ausente'}</small>{Boolean(schedule.enabled)&&<button disabled={busy} onClick={()=>run(()=>api(`/schedules/${schedule.id}/disable`,{}))}>Desativar próximas execuções</button>}</article>)}
    <small>Desativar agenda preserva tarefas já criadas; use Interromper na tarefa para cancelá-la. Avisos aparecem aqui, sem tomar foco.</small>
    {data?.notices.map(notice=><article key={notice.id}><time>{new Date(notice.created*1000).toLocaleTimeString('pt-BR')}</time><p>{notice.text}</p></article>)}
    {error&&<p role="alert">{error}</p>}
  </div>;
}

function App() {
  const [state,setState] = React.useState<State|null>(null);
  const [tasks,setTasks] = React.useState<Task[]>([]);
  const [selected,setSelected] = React.useState<string|null>(null);
  const [prompt,setPrompt] = React.useState('');
  const [fileOptions,setFileOptions] = React.useState<{path:string;bytes:number}[]>([]);
  const [files,setFiles] = React.useState<string[]>(['README.md','pyproject.toml']);
  const [events,setEvents] = React.useState<Entry[]>([]);
  const [error,setError] = React.useState('');
  const [sending,setSending] = React.useState(false);
  const [kind,setKind] = React.useState<'chat'|'development'>('chat');
  const [inspector,setInspector] = React.useState(()=>window.innerWidth>1150);
  const [tab,setTab] = React.useState<'files'|'events'|'memory'|'automation'>('files');
  const active = tasks.find(task=>task.id===selected);
  const projectName=state?.project_name&&state.project_name!=='demo'?state.project_name:'Projeto de demonstração';
  const modelReady=Boolean(state?.backend.available&&state.backend.model_installed&&!state.backend.model_changed);
  const backendLabel=!state?.backend.available?'Backend desconectado':state.backend.model_changed?'Modelo requer validação':state.backend.model_installed?'Modelo local disponível':'Modelo não instalado';
  const answerEnd = React.useRef<HTMLDivElement>(null);

  async function refresh() {
    try {
      const [nextState,nextTasks] = await Promise.all([api<State>('/state'),api<Task[]>('/tasks')]);
      setState(nextState); setTasks(nextTasks);
    } catch (e) {setError(String(e instanceof Error ? e.message : e));}
  }
  React.useEffect(()=>{
    refresh(); api<{path:string;bytes:number}[]>('/project/map').then(options=>{setFileOptions(options);setFiles(old=>old.filter(path=>options.some(option=>option.path===path)));}).catch(e=>setError(e.message));
    const timer = window.setInterval(refresh,4000);
    return ()=>window.clearInterval(timer);
  },[]);

  React.useEffect(()=>{
    if(!selected) {setEvents([]); return;}
    let disposed = false;
    const source = new EventSource(`/api/tasks/${selected}/stream`);
    async function update() {
      try {
        const [task,rows] = await Promise.all([api<Task>(`/tasks/${selected}`),api<Entry[]>(`/tasks/${selected}/events`)]);
        if(disposed) return;
        setTasks(old=>old.map(item=>item.id===task.id?task:item)); setEvents(rows);
        if(terminal.has(task.state)) {source.close(); refresh();}
      } catch(e) {if(!disposed) setError(String(e instanceof Error?e.message:e));}
    }
    source.onmessage = update;
    source.onerror = ()=>{source.close(); update();};
    update();
    return ()=>{disposed=true; source.close();};
  },[selected,active?.attempts]);

  React.useEffect(()=>{answerEnd.current?.scrollIntoView({behavior:'smooth',block:'end'});},[active?.answer]);
  React.useEffect(()=>{
    const handler = (event:KeyboardEvent)=>{
      const target = event.target as HTMLElement;
      if(event.key.toLowerCase()==='n'&&!event.ctrlKey&&!event.metaKey&&!event.altKey&&!['INPUT','TEXTAREA','SELECT'].includes(target.tagName)) {
        event.preventDefault(); setSelected(null); document.getElementById('prompt')?.focus();
      }
    };
    window.addEventListener('keydown',handler);
    return ()=>window.removeEventListener('keydown',handler);
  },[]);

  async function submit(event:React.FormEvent) {
    event.preventDefault(); if(!prompt.trim() || sending) return;
    setSending(true); setError('');
    try {
      const task = await api<Task>('/tasks',{prompt:prompt.trim(),files,kind,timeout_seconds:kind==='development'?300:180});
      setTasks(old=>[task,...old]); setSelected(task.id); setPrompt('');
    } catch(e) {setError(String(e instanceof Error?e.message:e));}
    finally {setSending(false);}
  }
  async function action(path:string, body:unknown={}) {
    try {setError(''); await api(path,body); await refresh(); if(selected) setEvents(await api<Entry[]>(`/tasks/${selected}/events`));}
    catch(e){setError(String(e instanceof Error?e.message:e));}
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="mark">N</span><div>NEXO<small>SEU ASSISTENTE LOCAL</small></div></div>
      <button className="new-task" onClick={()=>{setSelected(null);setPrompt('');}}>＋ Nova tarefa <kbd>N</kbd></button>
      <div className="section-title">ESPAÇO DE TRABALHO</div>
      <div className="project"><span>▧</span><div>{projectName}<small>Cópias isoladas para alterações</small></div><span className="dot"/></div>
      <div className="history-title section-title">TAREFAS <span>{tasks.length}</span></div>
      <nav className="history" aria-label="Histórico de tarefas">
        {tasks.map(task=><button key={task.id} className={selected===task.id?'selected':''} onClick={()=>setSelected(task.id)}>
          <span className={'task-dot '+task.state}/><div><span>{task.prompt}</span><small>{labels[task.state]||task.state} · {new Date(task.created).toLocaleDateString('pt-BR')}</small></div>
        </button>)}
        {!tasks.length&&<p className="empty-history">Suas tarefas ficam salvas aqui, mesmo depois de reiniciar.</p>}
      </nav>
      <div className="sidebar-bottom"><span className="avatar">M</span><div>Murilo<small>Dados neste computador</small></div><span className="local-tag">LOCAL</span></div>
    </aside>
    <main>
      <header className="topbar"><div><span className="breadcrumb">NEXO</span><span className="slash">/</span><span className="desktop-title">Assistente</span><select className="mobile-tasks" aria-label="Histórico de tarefas" value={selected||''} onChange={e=>setSelected(e.target.value||null)}><option value="">Nova tarefa</option>{tasks.map(task=><option key={task.id} value={task.id}>{task.prompt.slice(0,36)}</option>)}</select></div><div className="top-actions">
        <span className={'connection '+(modelReady?'online':'offline')}><i/>{backendLabel}</span>
        <button className="icon-button" aria-label="Mostrar contexto" onClick={()=>setInspector(!inspector)}>☷</button>
      </div></header>
      <div className="workspace">
        <section className="conversation">
          <div className="mode-strip"><span className="status-pill"><i/>{modes[state?.mode||'paused']}</span><span>Uma tarefa por vez · Sem serviços pagos</span><button onClick={()=>action('/mode',{mode:state?.mode==='paused'?'development':'paused'})}>{state?.mode==='paused'?'▶ Retomar':'Ⅱ Pausar'}</button></div>
          <div className="conversation-scroll">
            {!active ? <div className="welcome"><span className="welcome-symbol">✳</span><p className="eyebrow">TEXTO PRIMEIRO. CONTEXTO SEMPRE.</p><h1>Vamos conectar<br/>as próximas ideias.</h1><p>Converse, explore o projeto e acompanhe cada tarefa.<br/>O contexto e o histórico ficam neste computador.</p>
              <div className="suggestions">{[
                ['▧','Conhecer o projeto','Leia este projeto de teste e explique como executá-lo, citando os arquivos usados.'],
                ['⌘','Entender o código','Explique o que faz a função media em app.py, sem executar comandos.'],
                ['↗','Planejar o próximo passo','Sugira uma melhoria pequena para o projeto, com critérios de verificação.']
              ].map(([icon,title,text])=><button key={title} onClick={()=>{setPrompt(text);if(title==='Entender o código')setFiles(['README.md','app.py']);}}><span>{icon}</span><strong>{title}</strong><small>{text}</small><b>↗</b></button>)}</div>
            </div> : <div className="messages"><div className="message user-message"><div className="message-meta"><span className="avatar small">M</span>VOCÊ <time>{new Date(active.created).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</time></div><p>{active.prompt}</p>{active.files.length>0&&<div className="attachments">{active.files.map(file=><span key={file}>▧ {file}</span>)}</div>}</div>
              <div className="message assistant-message"><div className="message-meta"><span className="assistant-avatar">✳</span>NEXO <span className={'state-label '+active.state}>{labels[active.state]||active.state}</span></div>
              {active.answer ? <div className="answer"><FormattedAnswer text={active.answer}/></div> : <p className="thinking">{active.state==='running'?'Analisando o pedido e preparando a resposta…':active.state==='ready'?'Aguardando vez na fila…':'Ainda não há resposta final.'}</p>}
              {active.error&&<div className="task-error">{active.error}</div>}
              {active.kind==='development'&&<DevelopmentPanel key={active.id} task={active} mode={state?.mode||'paused'} onChange={refresh}/>}
              <div className="message-actions">{!terminal.has(active.state)&&<button onClick={()=>action(`/tasks/${active.id}/cancel`)}>■ Interromper</button>}{(['paused','waiting_resource'].includes(active.state)||(active.state==='waiting_user'&&active.kind!=='development'))&&<button onClick={()=>action(`/tasks/${active.id}/resume`)}>↻ Retomar tarefa</button>}<button onClick={()=>{setInspector(true);setTab('events');}}>Ver evidências ↗</button></div></div><div ref={answerEnd}/></div>}
          </div>
          <div className="composer-wrap">{error&&<div className="error" role="alert">{error}<button onClick={()=>setError('')} aria-label="Fechar erro">×</button></div>}
            <form className="composer" onSubmit={submit}><label className="sr-only" htmlFor="prompt">Pedido para o NEXO</label><textarea id="prompt" value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder={kind==='development'?'Descreva a alteração e como verificar o resultado…':'O que vamos fazer agora?'} rows={2} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><div className="composer-footer"><div className="composer-context"><button type="button" className="context-button" onClick={()=>{setInspector(true);setTab('files');}}>＋ {files.length} arquivos</button><select aria-label="Tipo de tarefa" value={kind} onChange={e=>setKind(e.target.value as 'chat'|'development')}><option value="chat">Conversa</option><option value="development">Desenvolvimento</option></select></div><div><span>{state?.model||'Modelo local'}</span><button className="send" type="submit" disabled={sending||!prompt.trim()} aria-label="Enviar tarefa">↑</button></div></div></form>
            <p className="composer-note">NEXO pode cometer erros. Confira fontes e resultados. <span>Enter para enviar · Shift + Enter para nova linha</span></p>
          </div>
        </section>
        <aside className={'inspector '+(inspector?'visible':'')}><div className="inspector-heading">Contexto de trabalho<button aria-label="Fechar contexto" onClick={()=>setInspector(false)}>×</button></div><div className="tabs"><button className={tab==='files'?'active':''} onClick={()=>setTab('files')}>Arquivos</button><button className={tab==='events'?'active':''} onClick={()=>setTab('events')}>Evidências</button><button className={tab==='memory'?'active':''} onClick={()=>setTab('memory')}>Memória</button><button className={tab==='automation'?'active':''} onClick={()=>setTab('automation')}>Agenda</button></div>
          {tab==='memory'&&<KnowledgePanel onChange={refresh}/>}
          {tab==='automation'&&<AutomationPanel files={files} onChange={refresh}/>}
          {['memory','automation'].includes(tab)?null:tab==='files'?<><p className="inspector-description">Escolha até cinco arquivos para priorizar no próximo pedido.</p><div className="file-list">{fileOptions.map(file=><label key={file.path}><input type="checkbox" checked={files.includes(file.path)} disabled={!files.includes(file.path)&&files.length>=5} onChange={e=>setFiles(old=>e.target.checked?[...old,file.path]:old.filter(path=>path!==file.path))}/><span>▧</span><div>{file.path}<small>{file.bytes.toLocaleString('pt-BR')} bytes</small></div></label>)}</div><div className="scope-card"><span>ESCOPO ATIVO</span><strong>{projectName}</strong><p>Conversa consulta arquivos. Desenvolvimento prepara alterações em cópia e mostra o diff antes de aplicar.</p></div></>:<div className="event-list">{events.map(entry=><article key={entry.seq}><span>{entry.kind}</span><time>{new Date(entry.created).toLocaleTimeString('pt-BR')}</time><pre>{JSON.stringify(entry.data,null,2)}</pre></article>)}{!events.length&&<p>Selecione uma tarefa para ver as evidências.</p>}</div>}
          <div className="inspector-bottom"><label htmlFor="mode">Convivência com o PC</label><select id="mode" value={state?.mode||'paused'} onChange={e=>action('/mode',{mode:e.target.value})}>{Object.entries(modes).map(([value,title])=><option key={value} value={value}>{title}</option>)}</select><small>No modo pessoal, novas gerações ficam bloqueadas e o modelo é descarregado.</small></div>
        </aside>
      </div>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
