# Plano completo e evidências

O objetivo permanece executar todo o plano mestre. Um incremento funcional não conclui a versão 1.0. Esta tabela acompanha o escopo original, sem substituir seus aceites.

| Fase | Situação | Evidência ou trabalho restante |
|---|---|---|
| 0 — Viabilidade | Validada no escopo inicial de leitura | Inventário, runtime, quatro sondas completas, contrato e 20 cenários; caminho local comprovado; OpenAI opcional desabilitada. `reports/BASELINE.md` |
| 1 — Núcleo persistente | Aceita no escopo inicial de leitura | Chat/SSE/SQLite/fila/recuperação/UI, pausa real 0,132 s, 300,5 s ocioso abaixo de 400 MB/1%, backup/restore e encerramento sem processos remanescentes. `reports/PHASE-1.md` |
| 2 — Desenvolvimento | Aceite inicial demonstrado | Bug e funcionalidade resolvidos com modelo real, testes/build, cópia/diff, aplicação/rejeição/restauração, índice Git e não rastreados preservados; comandos limitados e Jobs Windows. `reports/PHASE-2.md` |
| 3 — Memória/pesquisa | Aceite inicial demonstrado | 53 testes e 21 verificações reais: decisão após reinício, correção, código orientado por memória, exclusão de derivados e pesquisa; perfil isolado e índice incremental. `reports/PHASE-3.md`; ampliar recuperação/pesquisa pessoais |
| 4 — Iniciativa/convivência | Em validação | Agenda finita, sensor opcional, pausa/retomada e limites; 63 testes e 23 verificações reais. Preparo/Git cancelável em Job; núcleo 80,5 MiB/0,0804% CPU por 301 s. Ensaio WebGL sem diferença de mediana observada. Restam limite global sob I/O lento, sinal GPU e jogo real. `reports/PHASE-4.md` |
| 5 — Windows | Pendente | Adaptadores, sessão explícita, acessibilidade, navegador separado, parada global, checkpoints, restauração, ausência de disputa de foco |
| 6 — Habilidades/especialistas | Pendente | Papéis sequenciais, manifestos/versões, candidatos/testes/promoção, reuso e desativação |
| 7 — Desktop/celular/voz | Pendente; UI responsiva local disponível | Tray/atalho, autenticação em rede privada, celular real, push-to-talk, indicadores de microfone e revisão de intenção |
| 8 — Evolução/Argus | Pendente | Avaliações históricas/reservadas, rollback, adaptador Argus preservando escopo/aprovações; viabilidade de treinamento |
| 9 — Pessoal 1.0 | Pendente | Instalação limpa, update, backup/restore/export completos, falha simulada, documentação e **duas semanas reais de uso cotidiano registrado** |

## Requisitos transversais

- Identidade, memória e habilidades exportáveis, independentes do modelo; coleta por finalidade.
- Projeto independente do Argus; sem ampliação do escopo ou aprovações dele.
- Monólito/SQLite, contratos tipados, timeout/cancelamento, estados, tentativas, checkpoints e evidências.
- Modelo local obrigatório; externo opcional com destino dos dados registrado, sem compra automática ou credenciais copiadas.
- Uso pessoal prevalece; uma geração; sem disputa por foco/mouse/teclado, sem captura contínua padrão.
- Categorias/validade de memória, conflitos, fontes não confiáveis e exclusões consultáveis.
- Aprendizado com avaliação objetiva/promoção/rollback; autoalteração isolada com revisão; não alterar sozinho permissões/parada/avaliação.
- Políticas persistentes com objetivo, diretórios, ferramentas, orçamento e prazo; impacto externo/destrutivo exige autorização específica conforme plano.
- Qualidade, recuperação e independência medidas por tarefas reais; testes de transporte não equivalem a aceites.
- Rotina semanal/mensal e avaliação antes de release. Documentar rotinas não prova que sua execução futura já ocorreu.

Não concluir o objetivo enquanto houver requisito obrigatório pendente ou sem evidência suficiente.
