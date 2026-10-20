# Fase 2 — desenvolvimento assistido, 18/10/2026

## Demonstrações reais

`tools/live_development.py` criou dois repositórios sintéticos independentes, com alterações prévias rastreadas e um arquivo não rastreado. O modelo local recebeu o objetivo e o código; produziu patches JSON, aplicados somente à cópia. Testes do projeto permaneceram protegidos contra edição pelo modelo.

| Cenário | Resultado | Tempo observado |
|---|---|---:|
| Bug: média de lista vazia causava divisão por zero | Patch em `app.py`, testes e compilação aprovados | 8,8 s |
| Funcionalidade: mediana vazia/par/ímpar, sem alterar entrada | Função adicionada, seis testes e compilação aprovados | 12,4 s |

Nos dois casos, o original ficou intacto até a aplicação. A aplicação local passou novamente nos testes; a restauração devolveu os bytes do checkpoint, preservando comentário e anotação não rastreada. Estado da tarefa: `waiting_user` enquanto a proposta aguarda revisão, `completed` após aplicar e `cancelled` após rejeitar/desfazer. Não confundir preparar um patch com concluir a alteração no original.

Relatório bruto local: `local-development-e2e.json`. As alterações aplicadas nos projetos de avaliação foram restauradas.

## Interface e regressão

`tools/live_development_ui.py`: **10 verificações aprovadas** no Edge headless. Criou proposta real pela interface, mostrou diff, aplicou, passou nos testes, restaurou e rejeitou uma segunda proposta. Arquivos não rastreados preservados, sem erro JavaScript e sem transbordamento horizontal em 1440/390 px. Screenshots em `local-development-ui-desktop.png` e `local-development-ui-mobile.png`.

`tools/live_e2e.py`: as **13 verificações do núcleo** passaram com o novo perfil, incluindo resposta após reinício e pausa real em **0,120 s**, com modelo descarregado. A primeira tentativa encontrou omissão de citação pelo modelo; o núcleo passou a anexar a proveniência dos arquivos efetivamente lidos. A evidência é do acesso verificado, não uma alegação de que o modelo citou espontaneamente cada fonte.

## Infraestrutura e testes

**39 testes aprovados**, dependências consistentes (`pip check`) e build TypeScript/Vite aprovado. Saída reproduzível em `phase2-tests.txt`.

- Cópia com manifesto, hashes e backup dos arquivos anteriores, incluindo não rastreados. Diffs mostram somente mudanças da cópia em relação ao checkpoint.
- Mapa recursivo e busca literal com caminhos/linhas; limites de 200 arquivos, 500 entradas, 2 MiB por cópia, profundidade oito, 32 KiB por arquivo. Dependências/builds/segredos conhecidos e links são excluídos ou rejeitados.
- Patches tipados, campos desconhecidos rejeitados, correspondência exata/única do trecho original, até duas tentativas automáticas. Novos arquivos são limitados; testes existentes não podem ser editados pelo modelo.
- Git status/diff restritos aos arquivos autorizados, sem pager, fsmonitor, textconv ou diff externo, sem refresh opcional do índice. Teste preserva exatamente os bytes do índice com conteúdo já staged e modificações não staged.
- Comandos cadastrados: `python-tests`, `python-check`, `node-tests`, `npm-build`, todos exercitados com fixtures. Sem terminal arbitrário ou instalação automática de dependências.
- Descoberta vazia não é aprovação: unittest exige casos e Node usa relatório TAP com contagem positiva. Build npm é exigido quando já constava do manifesto original, evitando que a proposta o elimine para pular a verificação.
- Windows Job Object: até 512 MiB de memória comprometida, 25% da CPU, 16 processos; fechamento encerra processos associados. Bootstrap confiável aguarda a atribuição ao Job antes de carregar código do projeto. Usa intérprete real, evitando a corrida do redirecionador do venv.
- Timeout, cancelamento e limite de 128 KiB de saída; testes reais criam descendente e confirmam encerramento. Cache de bytecode separado e escrita de `.pyc` desabilitada para não testar código antigo após patch de mesmo tamanho/segundo.
- Comandos são iniciados sem janela; os streams são passados explicitamente aos filhos. A validação encontrou e corrigiu perda de stdout do Node em `CREATE_NO_WINDOW`; ausência de contagem de testes nunca passou como sucesso.
- Escrita verifica hash e handle, impede substituição concorrente, bloqueia reparse points e usa exclusão pelo handle. Mutex por projeto serializa aplicação/restauração. Conflitos preservam alterações posteriores do usuário.
- Journal antes da aplicação e verificação de efeitos para recuperação após interrupção; restauração não repete operações às cegas. Pastas criadas são removidas somente se mantiverem identidade e estiverem vazias; conteúdo novo do usuário é preservado.
- Migração SQLite v1→v2 com backup anterior à mudança; restauração de backup antigo exercitada. Banco é vinculado ao projeto para impedir mistura de históricos entre escopos.

## Modelo e limites

O modelo anterior falhou por truncamento no primeiro patch real; registro em `local-development-original-model-failure.json`. Após essa evidência, foi avisado e realizado download de um segundo candidato de ~2,5 GB no D:, preservando o anterior. Nenhuma API paga ou envio externo de código.

Selecionado `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`. Perfil versionado em `model-profile.json`, contexto 4096, sem raciocínio solicitado, temperatura 0,7/top_p 0,8. O gateway confere o digest antes de enviar prompts. Backend mantém uma geração/modelo residente por vez.

Benchmark sintético `local-benchmark-1792292669080667700.json`: **8/8 respostas completas**, o que não equivale a aprovação semântica. A revisão estrita encontrou ao menos duas violações de instrução no contexto moderado: exemplo `python main.py` apesar da restrição e explicação de código mais longa que a frase pedida. Portanto, não se usa este benchmark bruto para alegar qualidade geral de 80%. A escolha para desenvolvimento se apoia nos dois fluxos reais com testes independentes; leitura com fontes foi revalidada pelo núcleo. Os 20 aceites completos continuam pendentes, sem aprovação fictícia.

Sonda de recursos do perfil: `tools/measure_model.py`, 15 amostras em 14,9 s incluindo carregamento/geração/descarga. Pico de RSS agregado do backend/runner **799,3 MiB** e GPU total do sistema **4224 MiB**, com geração concluída. Resumo `model-resource-summary.json`. A média de CPU dessa janela não representa somente geração; não é baseline ociosa nem benchmark de jogo.

O incremento atende aos dois cenários iniciais de desenvolvimento do plano. Cópias e Jobs controlam alterações/recursos/processos; não são uma VM nem sandbox de credenciais/rede. Execução de testes se destina a projetos autorizados e confiáveis. Dependências externas, árvores maiores e comandos não cadastrados exigem evolução explícita. Não há publicação remota, commit automático no projeto do usuário, operação de desktop ou autoalteração do NEXO habilitada por este marco.

Ponto aberto para o agendador da Fase 4: preparo da cópia e coleta de metadados Git ainda são síncronos. As medidas de pausa abaixo de dois segundos cobrem geração e os executores verificados, não garantem esse prazo durante toda chamada lenta de arquivo/Git. Converter esses estágios para execução cancelável antes de aprovar o aceite de convivência em todos os estágios.

Fontes técnicas: [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [exclusão por handle](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info), [modelo avaliado](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M).
