# NEXO

Assistente pessoal local de Murilo. Plano integral em `docs/Nexo-Plano-Mestre.md`; original na pasta superior preservado.

## Estado

Versão 0.2 de desenvolvimento: chat React, modelo local, streaming, SQLite, histórico, evidências, leitura, busca e alterações em cópia isolada com testes, diff, aplicação/rejeição/restauração. As fases seguintes continuam em execução. Nenhum serviço pago, envio externo de código, autostart ou publicação.

Perfil selecionado em `model-profile.json`: Qwen3 4B Instruct quantizado, com digest conferido antes dos prompts. Desenvolvimento isolado, memória versionada, fontes por URL, índice incremental e agenda finita disponíveis. **63 testes aprovados**; demonstrações reais documentadas em `reports/PHASE-2.md`, `reports/PHASE-3.md` e `reports/PHASE-4.md`. Os 20 aceites completos ainda não foram aprovados. Controle amplo de aplicativos pertence às fases posteriores.

## Abrir no Windows

Com dependências e backend já instalados nesta máquina:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-nexo.ps1
```

Abra **http://127.0.0.1:8765**. Se estiver pausado, use **Retomar**. O pedido inicial sugerido lê README e manifesto de `demo/`. Escolher arquivos não amplia o diretório autorizado. Para parar núcleo e backend e liberar recursos:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/stop-nexo.ps1
```

A parada solicita pausa e descarga antes de encerrar somente a árvore do PID verificado. A interface escuta exclusivamente em loopback; acesso do celular em rede privada autenticada pertence a uma fase posterior.

No compositor, escolha **Conversa** ou **Desenvolvimento**. Desenvolvimento executa verificações cadastradas em uma cópia, com até duas tentativas. A proposta fica **aguardando você**, com diff e resultados, até aplicar ou rejeitar. Depois de aplicar, **Restaurar original** desfaz apenas alterações que ainda correspondam aos hashes publicados; mudanças posteriores do usuário geram conflito.

Para um projeto autorizado diferente, com o núcleo padrão parado e o backend iniciado:

```powershell
.venv/Scripts/python.exe -m nexo --project "D:/caminho/do/projeto"
```

Cada projeto usa banco separado por padrão. Não reutilize o banco de outro escopo. O executor se destina a projetos e testes confiáveis: cópias e Job Objects não são uma VM ou sandbox de rede/credenciais. Dependências não são instaladas automaticamente.

Na aba **Memória**, guarde decisões do projeto ou preferências explícitas. Perfil compartilhado usa `.runtime/profile/nexo.db`; `--data-dir` personalizado isola também esse perfil. Correções preservam versões e conflitos exigem escolha. Mutações pausam a execução: use Retomar depois. Fontes públicas são importadas por URL explícita; arquivos locais não são enviados. Indexação exige modo desenvolvimento/ausente, com limites e exclusões consultáveis. Política de exclusão/restauração em `reports/PHASE-3.md`; preserve o diário de exclusões mais recente junto aos backups.

Na aba **Agenda**, crie um pedido recorrente associado a um objetivo, com prazo e número máximo de execuções. A interface agenda consultas aos arquivos selecionados, somente no modo Ausente. Não acumula execuções atrasadas nem trabalho pendente. Detecção de atividade/processos/RAM é opcional e começa desligada; habilite explicitamente e configure nomes exatos dos jogos. Retomada automática por ociosidade também exige habilitação. O modo manual prevalece. Avisos ficam no painel e não tomam foco. Desativar agenda preserva tarefas já criadas, que podem ser interrompidas individualmente.

## Instalação reproduzível (na raiz deste repositório)

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
.venv/Scripts/python.exe -m pip install --no-build-isolation -e .
npm.cmd ci --prefix frontend
npm.cmd exec --prefix frontend tsc -- --project frontend/tsconfig.json
npm.cmd exec --prefix frontend vite -- build frontend
```

Python 3.15 e Node 24 foram as versões efetivamente testadas. Reinstalação do Ollama/modelo em `docs/LOCAL-RUNTIME.md`; scripts de início não baixam modelos.

## Verificação

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pip check
```

Com NEXO iniciado, a demonstração usa Edge headless já instalado, perfil temporário, cria tarefas sintéticas, reinicia o núcleo e verifica pausa durante geração real:

```powershell
.venv/Scripts/python.exe tools/live_e2e.py
```

Benchmark sintético do modelo:

```powershell
python tools/benchmark.py --model qwen3:4b-instruct-2507-q4_K_M --contexts 2048 4096 --max-tokens 1536 --temperature 0.7 --top-p 0.8
```

Aceite de desenvolvimento em projetos sintéticos próprios (com backend iniciado, sem outra geração em andamento):

```powershell
.venv/Scripts/python.exe tools/live_development.py --model qwen3:4b-instruct-2507-q4_K_M --no-thinking
.venv/Scripts/python.exe tools/live_development_ui.py
```

O benchmark usa apenas prompts sintéticos, grava respostas e métricas em `reports/`, não executa código gerado e descarrega o modelo após cada amostra. Ele mede capacidade textual; não comprova autonomia, memória persistente ou segurança de ferramentas. Os 20 cenários de produto estão em `evals/acceptance.json`.

Consulte `docs/STATUS.md`, `docs/DECISIONS.md` e `docs/BACKLOG.md` para evidências, limites e próximos marcos. Dados, downloads e executáveis locais ficam em `.runtime/`, excluídos do Git. O plano original é preservado.

`-ExecutionPolicy Bypass` aplica-se somente ao processo invocado e permite executar os scripts revisáveis deste repositório sem alterar a política global do Windows. O servidor recusa iniciar se a porta estiver ocupada e só escuta em loopback. Encerramento confere o executável do PID registrado antes de finalizar sua árvore.

## Repetir prova isolada da stack

```powershell
Set-Location tools/stack-probe
npm.cmd ci
npm.cmd exec tsc -- --project tsconfig.json
npm.cmd exec vite -- build
```

Essa página mínima é apenas prova de compilação, não a interface de produto. O runtime não instala modelos automaticamente. A reinstalação dos binários/modelos está descrita em `docs/LOCAL-RUNTIME.md`.
