# Runtime local experimental

Instalação de binários/modelos no D:. Ollama portátil 0.40.6; perfil atual em `model-profile.json`: **Qwen3 4B Instruct 2507 Q4_K_M**, selecionado em 18/10/2026 após falha observada do candidato anterior. Nenhum serviço do Windows, autostart, mudança global de PATH ou elevação administrativa.

O primeiro modelo `qwen3:4b` permanece somente para comparação. São dois modelos locais (~5 GB de pesos), mas o backend carrega um por vez. Não há download automático na aplicação. A justificativa e o aviso do segundo download constam da execução da Fase 2.

Para repetir a instalação manualmente, a partir da raiz do repositório:

1. Baixe `ollama-windows-amd64.zip` e `sha256sum.txt` da release oficial https://github.com/ollama/ollama/releases/tag/v0.40.6 para `.runtime/downloads/`. O ZIP tem 1.471.164.488 bytes. Confira SHA-256 antes de extrair: `e359637575302f288d76c0007c408a4be9c7376d59c4f28684d63b232a44b427` (também registrado em `reports/ollama-sha256.txt`). A comparação detecta corrupção; não substitui assinatura independente da origem.
2. Extraia para `.runtime/ollama/`, crie `.runtime/models/` e `.runtime/logs/`.
3. Execute `powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-local.ps1`.
4. No terminal, configure `$env:OLLAMA_HOST='127.0.0.1:11434'` e execute `& '.runtime/ollama/ollama.exe' pull qwen3:4b-instruct-2507-q4_K_M`. Isso baixa aproximadamente 2,5 GB. O servidor já foi iniciado com `OLLAMA_MODELS` no D:. O digest esperado é `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; o gateway recusa prompts se o artefato selecionado mudar. Reavaliar antes de trocar o perfil.
5. Execute o benchmark do README. Não compartilhe o serviço na rede. Ao terminar, execute `tools/stop-local.ps1` pelo PowerShell conforme README.

Prompts são sintéticos e a inferência permanece local. O download acessa GitHub e o registro do Ollama. `OLLAMA_NO_CLOUD=1` desabilita funcionalidades de nuvem do backend; não é sandbox de rede do sistema operacional.

`keep_alive=0` solicita descarga após as gerações. Confirme `/api/ps` vazio e o uso de GPU quando o modelo terminar; finalizar o servidor é o passo final para liberar também o processo ocioso. `taskkill /T` limita-se à árvore do servidor identificado.

## Limites

A API e a interface estão implementadas; use início/parada conforme README. O perfil atual passou na regressão real do núcleo, com pausa em ~0,120 s e descarga confirmada. Desenvolvimento tem executor de verificações cadastradas em cópias, com Jobs Windows; não há terminal arbitrário, memória pessoal ou controle de aplicativos.

Relatórios `local-*` ficam fora do Git. Resumos versionáveis distinguem medições de hipóteses. `.venv/`, binários e modelos são reconstruíveis. **Dados de tarefas e cópias em `.runtime/data/` e `.runtime/projects/` não são descartáveis**: preserve bancos, backups e manifestos. Migração v1→v2 guarda backup antes de mudar o esquema. Memória pessoal ainda pertence ao próximo marco.
