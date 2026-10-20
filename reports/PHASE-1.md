# Núcleo persistente — evidências de 17/10/2026

## Fluxo real

Teste reproduzível: `tools/live_e2e.py`, interface FastAPI/React, Edge instalado em modo headless com perfil temporário, inferência Ollama/Qwen3 4B local. Última execução: **13 verificações aprovadas**. Relatório bruto: `local-live-e2e.json`; screenshots: `local-ui-desktop.png`, `local-ui-conversation.png` e `local-ui-mobile.png`.

Pedido: “Leia este projeto de teste e explique como executá-lo. Cite README.md e pyproject.toml e apenas os comandos presentes nas fontes. Responda em até 120 palavras.”

Resposta: “Segundo README.md, execute `python app.py` e verifique com `python -m unittest discover -s tests -v`. O projeto requer Python >=3.12 (pyproject.toml).”

Verificações: modelo real; fontes corretas; deltas/hashes registrados; resposta preservada após parar/iniciar servidor; tarefa pronta preservada na fila com modo pausado; interface de 390 px sem transbordamento horizontal; ausência de erros JavaScript; modelo efetivamente carregado antes da interrupção; pausa em **0,132 s**; tarefa pausada; `/api/ps` vazio depois da pausa.

A primeira tentativa do utilitário ficou presa em pipes herdados por processos de fundo no Windows, após a resposta já gerada. Corrigido para usar arquivo de log nos scripts de ciclo de vida; fluxo completo repetido com sucesso. Artefato parcial preservado como `local-live-e2e-attempt1.json`.

## Testes objetivos

**18 testes aprovados**; `pip check` sem incompatibilidades; TypeScript e Vite build aprovados. Aviso de depreciação HTTPX/Starlette do TestClient sem falha; revisar ao atualizar a stack.

- UTF-8 com hash/limite; bloqueio de caminhos externos, drive relativo, UNC, ADS, junctions, hard links, segredos conhecidos e arquivos excessivos.
- Handle aberto verificado antes de ler; teste substitui a validação anterior por caminho externo para simular troca entre validação e abertura.
- Migração inicial transacional (`user_version=1`), reinício preserva resposta parcial, tarefa executando passa a pausada com evento de recuperação.
- Backup SQLite, integridade, restauração em destino novo e recusa de sobrescrita.
- Pausa cancela stream bloqueado, descarrega backend e impede próxima tarefa; uma geração ativa.
- HTTP rejeita Origin/Host externos, registra fontes, entrega SSE e preserva dados entre instâncias.
- Resposta vazia/truncada nunca é concluída.
- Timeout de geração fecha o stream e solicita descarga antes de despachar outra tarefa.

## Escopo do aceite

Um projeto (`demo/`), somente leitura, sem subprocessos de usuário, sem inferência externa e sem concessão de ferramentas por texto gerado. React escapa conteúdo; respostas não viram HTML executável. Conversas recuperam até dois pares anteriores dentro de orçamento, no projeto único.

O cancelamento é medido nesta máquina/backend, não significa desfazer ação externa. Não há aprovação para comandos amplos nem resistência geral a toda injeção. Convivência automática com jogos, os 20 aceites, memória e Windows permanecem nos respectivos marcos.

## Recursos, restauração e encerramento

Janela **300,5 s**, 121 amostras, modo pausado, modelo descarregado, processo pai e intérprete filho do núcleo verificados em todas as amostras. Pico de RSS agregado **78,4 MiB** (~82,2 MB); média aproximada de CPU normalizada pela máquina **0,042%**. A meta experimental de 400 MB/1% foi satisfeita nesta janela específica. `core-idle-summary.json` preserva o resumo; bruto local `local-resources-core-idle-1792291362067304000.json`.

Não é garantia para todos os modos/cargas. GPU na amostra é consumo total da máquina; páginas compartilhadas podem ser contadas duas vezes; picos entre amostras podem ser perdidos. Não é benchmark de interferência em jogo.

Backup do banco real do incremento restaurado em destino novo em `.runtime/restore-proof/`. Tarefas, eventos e modo comparados iguais; evidência `restore-proof.json`. Não substitui o aceite de backup/restore/export da versão completa na Fase 9.

Ao encerrar, `stop-nexo.ps1` pausou o núcleo, encerrou sua árvore e o backend pertencente ao projeto. Consulta de processos não encontrou executáveis remanescentes do runtime nem `python -m nexo`.

**Fase 1 aceita no escopo inicial de um projeto de demonstração, com leitura.** O objetivo completo continua ativo; Fases 2–9 permanecem pendentes conforme `docs/ROADMAP.md`.
