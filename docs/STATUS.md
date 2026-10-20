# Execução do plano — 17/10/2026

## Atualização — Fase 4 em validação

Agenda finita, sensor opcional de atividade/processos/RAM, pausa no retorno, retomada opcional e prioridade manual implementados. Preparo/Git roda em Job cancelável: descendente lento encerrado em 0,033 s na última execução. **63 testes e 23 verificações reais aprovados**. Com sensor ligado, núcleo ocioso por 301,35 s: **80,5 MiB RSS e 0,0804% CPU média da máquina**, modelo descarregado. Usuário sem benchmark instalado; ensaio WebGL local concluído, mediana de 3,4 ms com e sem núcleo, sem substituir jogo real. Restam operações síncronas e avaliações antes do aceite integral. `reports/PHASE-4.md`.

## Atualização — Fase 3 demonstrada no escopo inicial

Memória por projeto e perfil compartilhado, FTS5, fontes por URL, diário de exclusões e painel Memória implementados. **53 testes aprovados e 21 verificações reais aprovadas**: reinício, correção, patch orientado pela decisão salva, testes/aplicação/restauração, exclusão e pesquisa com evidência/inferência. Catálogo de metadados e indexação incremental; conhecimentos de fonte alterada exigem revisão. Uso real pequeno do MVP na leitura do plano, com checklist revisado e limitações registradas. Evidências em `reports/PHASE-3.md`. Próximos trabalhos: avaliações completas, Fase 4 e pausa durante preparo/Git síncronos. O plano integral não está concluído.

## Atualização — 18/10/2026, desenvolvimento assistido

Fase 2 implementada e demonstrada no escopo inicial: dois projetos de avaliação com modelo real (bug e funcionalidade), testes independentes, cópia isolada, diff, aplicação e restauração. Interface de revisão passou em dez verificações reais, incluindo rejeição e preservação do original. **39 testes aprovados**, TypeScript/Vite e dependências aprovados. SQLite v2 com backup pré-migração; bancos vinculados ao escopo.

Novo perfil Instruct selecionado após falha de truncamento do anterior; duas variantes locais preservadas, uma carregada por vez. Limitações semânticas do modelo bruto registradas, sem alegação de aprovação geral do conjunto de 20 tarefas. Regresso do núcleo passou novamente nas 13 verificações reais, com pausa em cerca de 0,120 s.

Evidências em `reports/PHASE-2.md`. Próximo marco: Fase 3, memória por projeto e pesquisa com fontes. O objetivo completo permanece ativo. Seções seguintes são históricas.

## Atualização atual — núcleo funcional

Contexto 4096/saída 2560 concluiu 4/4 sondas, incluindo fonte adversarial antes truncada. Selecionado para texto/leitura; histórico rejeitado preservado.

Implementados FastAPI, gateway Ollama com streaming/cancelamento, SQLite com migração/eventos/fila/recuperação, leitura com verificação de handle no Windows e interface React responsiva. **18 testes aprovados**, build e dependências aprovados. **13 verificações reais aprovadas** com modelo local/Edge headless: fontes, SSE, reinício, fila, celular emulado, pausa em 0,132 s e descarga confirmada.

**Fase 1 aceita no escopo inicial de leitura.** Núcleo ocioso medido por 300,5 s: pico 78,4 MiB de RSS e média aproximada 0,042% CPU da máquina. Backup/restauração do banco real comparados com igualdade de tarefas/eventos/modo. Núcleo e backend encerrados sem processos remanescentes encontrados.

Instruções no README; evidências em `reports/PHASE-1.md`. O objetivo completo continua ativo; fases posteriores em `ROADMAP.md`. As seções abaixo preservam o checkpoint anterior, não a situação atual.

## Histórico — checkpoint de viabilidade inicial

- Repositório Git independente em `nexo/`, sem remoto ou publicação. Plano original preservado e copiado integralmente para `docs/`.
- Inventário reproduzível de versões, discos, memória e GPU, sem varredura de arquivos pessoais.
- Ollama portátil 0.40.6 instalado no D:, pacote conferido por SHA-256 e servidor restrito a `127.0.0.1:11434`, sem autostart. Qwen3 4B Q4_K_M baixado com autorização explícita. Nuvem desabilitada no backend.
- Prova da stack Python 3.15 + FastAPI/Pydantic/SQLite; compilação TypeScript/React/Vite. Versões e lockfiles registrados. Sete testes aprovados, incluindo limite de resposta, transporte local, rejeição de falso sucesso e persistência SQLite entre conexões.
- Vinte cenários de aceite especificados com resultado esperado, distribuição e conjunto reservado. São cenários de produto, ainda `not_run`; fixtures executáveis acompanharão cada capacidade.
- Benchmark local com quatro sondas em dois contextos, controle de tamanho de saída, timeout, checkpoint de resultados e descarga. Registro de respostas, métricas e amostras de recursos. Histórico de configurações rejeitadas preservado em `reports/local-*`.
- Contrato do primeiro incremento, decisões, backlog e instruções de reprodução.
- Janela de 319 s sem modelo carregado: pico de RAM do backend ~109,4 MiB. Servidor encerrado ao terminar, sem processos remanescentes desse runtime. Medição completa e limitações em `reports/BASELINE.md`.

## Limites deste checkpoint

O roadmap completo não está concluído. A Fase 0 tem infraestrutura e evidências iniciais; a aprovação de qualidade depende da revisão do benchmark e dos critérios documentados no relatório. As Fases 1–9 permanecem pendentes. Não existe ainda chat persistente de produto, agente executor, memória pessoal ou controle do Windows.

O benchmark textual não aprova o conjunto de 20 tarefas nem demonstra segurança de ferramentas. Nenhum código do modelo foi executado e nenhuma credencial foi lida. A integração do plano ChatGPT permanece desabilitada por elegibilidade não comprovada para esta aplicação privada. Sem API paga.

O orçamento inicial experimental limita-se a uma geração, contextos de 2048/4096 e descarga após uso. Não há promessa de impacto zero. A meta de RAM/CPU do núcleo NEXO e a comparação com jogos só poderão ser aceitas quando esse núcleo existir e houver benchmark de convivência.

## Próximo gate

O resultado está em `reports/BASELINE.md`: configuração ainda não aprovada, com 6/8 respostas finais completas (75%) e falha por truncamento nas duas sondas de fonte maliciosa. O escopo fica reduzido a experimentos sintéticos sem ferramentas executáveis. Resolver essa limitação por experimento limitado antes de aprovar o modelo e implementar a demonstração descrita em `CONTRACT.md`. Não liberar ferramentas de sistema com base apenas em uma resposta JSON correta.
