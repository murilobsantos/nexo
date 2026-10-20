# Fase 4 — iniciativa e convivência em validação

Implementados agenda finita por projeto, detecção opcional de atividade Windows, processos configurados e RAM disponível; pausa no retorno, retomada opcional quando ocioso e precedência do modo manual. Não há captura de tela, áudio, conteúdo de teclas ou títulos de janelas. Detecção vem desligada. Usa metadados da sessão que executa o núcleo; outras sessões e eventos sintéticos podem limitar a precisão ([GetLastInputInfo](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo)).

## Agenda e limites

Cada agendamento guarda objetivo explícito, tarefa tipada, arquivos do projeto ativo, início/prazo, intervalo, máximo de execuções e modo permitido. Padrão: uma execução, somente Ausente. Intervalo mínimo 60 s, máximo 100 execuções, prazo até 90 dias. Não acumula atrasos nem cria trabalho enquanto outra tarefa aguarda execução, recurso, retomada ou revisão. Falha não autoriza tentativas ilimitadas. Desativação impede próximas execuções; tarefa já criada conserva seu próprio botão Interromper.

SQLite v4, com backup antes de migrar v3. Enfileirar e consumir orçamento é uma transação única; tarefas continuam no registro normal após reinício. Avisos só no painel: cooldown de 15 minutos por tipo, máximo três/hora, retenção de 100. Não há notificação externa ou janela que tome foco.

## Interrupção e recursos

Preparo da cópia e captura inicial Git passaram a processo confiável separado, associado a Job Windows antes do sinal de início. Limites: 512 MiB, CPU 25%, 16 processos; fechamento encerra descendentes. Checkpoint identifica interrupção durante preparo e preserva o original. Um Git sintético realmente bloqueado por 30 s foi encerrado pela pausa em menos de dois segundos; teste verifica também descendente morto, manifesto interrompido e bytes originais preservados.

Geração, executores de testes e preparo têm demonstrações de pausa. Ainda existem operações síncronas de leitura/SQLite/patch/diff na API e no coordenador: não está demonstrado o limite global de dois segundos sob qualquer falha de I/O. Resolver isso antes de declarar aceite integral de convivência.

## Evidência atual

- **63 testes aprovados** em `phase4-tests.txt`, incluindo nove de agenda/política/migração e um de cancelamento de Git lento real (0,033 s na última execução).
- **23 verificações reais aprovadas**, com UI Edge headless, agendamento finito, modelo local e sensor nativo. Tarefa consultou porta 4821 no README, citou a fonte e encerrou o orçamento. Modo pessoal descarregou o modelo.
- Janela de **301,35 s**, sensor ligado, núcleo ocioso em modo pessoal: pico da árvore do núcleo **80,5 MiB RSS**, CPU média aproximada **0,0804% da máquina**. Modelo continuou descarregado nas dez verificações periódicas. Não inclui memória do backend ou navegador, nem equivale a benchmark de jogo. Sumário em `coexistence-summary.json`.
- Retorno/retomada e processo configurado usam sensor determinístico nos testes; disponibilidade do sensor Windows e ausência de mudança de foco durante leitura de metadados foram verificadas na demonstração. Não foi sintetizada entrada na sessão pessoal para fabricar um retorno.

O usuário informou não possuir benchmark instalado. Ensaio gráfico local sem download foi medido: Edge headless, ANGLE/D3D11 na GTX 1660 Ti, shader 1280×720 e leitura síncrona de um pixel, seis rodadas de 15 segundos em ordem sem/com/com/sem/sem/com núcleo. Medianas de desenho+leitura: **3,4 ms nos dois grupos**, sem diferença observada na resolução medida. Não prova impacto zero nem substitui jogo real/limiar de variação acordado. `graphics-summary.json`; reprodução `python tools/graphics_compare.py` com runtimes parados. Uma tentativa anterior baseada apenas em `finish()` retornou tempos zerados e foi rejeitada; um problema de controle de processos do próprio ensaio também foi corrigido, com o processo remanescente identificado e encerrado antes das rodadas válidas. A versão atual verifica o estado do núcleo entre condições.

Metodologia de sincronização: [readPixels](https://developer.mozilla.org/en-US/docs/Web/API/WebGLRenderingContext/readPixels); identificação: [WEBGL_debug_renderer_info](https://developer.mozilla.org/en-US/docs/Web/API/WEBGL_debug_renderer_info). O ensaio mede também custo de leitura/sincronização, sem representar uma carga de jogo.

GPU ainda não é sinal automático de pausa; processos configurados, RAM e modo manual são os sinais atuais. A Fase 4 e o plano completo permanecem em execução.
