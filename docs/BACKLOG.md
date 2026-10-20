# Backlog priorizado

## Prioridade durante validação da Fase 4 — 18/10/2026

1. Completar interrupção durante demais I/O síncronos; preparo/Git já roda em Job separado e pausou em 0,062 s com descendente lento real.
2. Exercitar retorno/retomada nativos de forma controlada, sinal de GPU e cenário de jogo com critério de variação. Usuário sem benchmark instalado; ensaio WebGL local não substitui jogo.
3. Ampliar avaliações de recuperação/pesquisa e executar os cenários aplicáveis; preservar conjunto reservado.
4. Prosseguir fases 5–9, incluindo celular real e duas semanas reais de uso. Não declarar 1.0 com base apenas nos testes atuais.

As seções seguintes são históricas.

## Prioridade após demonstração da Fase 3 — 18/10/2026

1. Resolver pausa durante preparo de cópia/Git e demais I/O síncronos antes de afirmar o limite global de dois segundos.
2. Fase 4: atividade, agendamento finito ligado a objetivos, recorrência, cooldown, limites e comparação de convivência/jogo.
3. Ampliar avaliações pessoais de recuperação e pesquisa; executar cenários aplicáveis do conjunto de 20 e preservar o teste reservado.
4. Fases 5–9 conforme roadmap, incluindo celular real e duas semanas reais de uso. O MVP já foi usado para ler o plano e produzir checklist revisado; não dispensar avaliações posteriores.

As próximas seções são históricas.

## Prioridade após demonstração da Fase 2 — 18/10/2026

1. Fase 3: memória com origem/versão/validade/sensibilidade, correção/exclusão/conflitos por projeto, indexação incremental e pesquisa verificável.
2. Usar recuperação de trechos para arquivos maiores que o orçamento de contexto, compartilhando a seleção com desenvolvimento.
3. Executar o conjunto de 20 aceites com fixtures reproduzíveis e usar o MVP numa tarefa real pequena, antes de Windows amplo.
4. Fases 4–9 conforme `ROADMAP.md`; não substituir avaliações de jogo, celular real ou duas semanas de uso por testes menores.

As listas seguintes preservam prioridades anteriores.

## Prioridade atual após aceite do núcleo

1. Fase 2: cópia/worktree isolada, mapa/busca, patches tipados, comandos delimitados com timeout/cancelamento e rastreamento de subprocessos.
2. Exercitar bug preparado e funcionalidade pequena com modelo real, testes e diff; rejeitar/restaurar sem perder alterações prévias ou não rastreados.
3. Fase 3: memória por projeto com fontes, correção/exclusão/conflitos e pesquisa verificável.
4. Reexecutar aceites e usar MVP numa tarefa pequena real antes de Windows amplo.

O escopo completo está em `ROADMAP.md`. A lista abaixo é o histórico do backlog inicial, agora parcialmente concluído.

1. P0 — Resolver a falha de finalização em fonte maliciosa por experimento limitado. A última configuração obteve 6/8 respostas completas (75%); permanece experimental. Hash/versão, digest, latências e histórico estão em `reports/BASELINE.md`.
2. P0 — Expandir avaliação reproduzível e aprovar orçamento operacional após medições. Benchmark textual não aprova sozinho os 20 testes de produto. Não repetir ajustes indefinidamente.
3. Concluído — Prova de instalação FastAPI/servidor e Vite/React em ambiente isolado; versões testadas fixadas. Python 3.15 funcionou nessa prova. O teste HTTPX emitiu aviso de depreciação do TestClient/Starlette, sem falha; revisar a integração de testes ao iniciar o núcleo.
4. P1 — Contratos tipados, gateway local, streaming/cancelamento; SQLite com migrações, eventos e estados da fila.
5. P1 — Demonstração de leitura de pasta: escopo canônico, rejeição de escapes/symlinks, limites de bytes, procedência. Conteúdo nunca altera permissões.
6. P1 — Chat e painel de estado; reinício/retomada; pausa em até dois segundos; teste de ausência de processos órfãos.
7. P2 — Desenvolvimento isolado com patches, diff e testes; preservar mudanças prévias e arquivos não rastreados; restauração exercitada.
8. P3 — Memória por projeto, fontes, conflitos, correção/exclusão e política explícita de backup.

Fases 4–9 permanecem no plano mestre. Nenhuma é declarada concluída por existir um esqueleto. Duas semanas de uso cotidiano da Fase 9 exigem tempo real e registro de problemas.
