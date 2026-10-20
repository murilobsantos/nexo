# Decisões iniciais — 17/10/2026

## Atualização de 18/10/2026

Perfil local selecionado para o incremento de desenvolvimento: Qwen3 4B Instruct 2507 Q4_K_M, digest fixado em `model-profile.json`, após truncamento do primeiro candidato em tarefa real. Aprovação limitada aos cenários efetivamente verificados, não à qualidade geral de um assistente de fronteira. Backend continua Ollama 0.40.6 local, sem API paga.

Isolamento inicial por cópias, não worktrees: inclui bytes rastreados/não rastreados e preserva o índice Git. Verificações limitadas a comandos cadastrados com Job Objects. A proposta exige ação de aplicar/rejeitar e fica `waiting_user` até a decisão; retomada não reaplica efeitos anteriores às cegas. Migração SQLite v2 e escopo associado ao banco. Evidências e limites em `reports/PHASE-2.md`.

Seções seguintes preservam as decisões iniciais.

- Repositório independente nesta pasta, sem dependência do Argus.
- Monólito modular Python/SQLite; FastAPI e React/Vite passaram pela prova de instalação/compilação em ambientes isolados. Python disponível e testado: 3.15. Versões instaladas estão em `requirements-phase0.lock` e `tools/stack-probe/package-lock.json`.
- Fase 0 usa biblioteca padrão do Python para não confundir compatibilidade de framework com viabilidade do modelo.
- Ollama portátil 0.40.6 como primeiro backend experimental. Qwen3 4B Q4_K_M como único candidato inicial (2,5 GB conforme catálogo), sem declarar vencedor antes das medições.
- Uma geração por vez, contextos de 2048 e 4096, saída limitada e descarga imediata. A primeira hipótese com temperatura zero falhou por truncamento. As configurações seguintes usam parâmetros recomendados pela Qwen e preservam os resultados anteriores. Sem autostart, alteração de PATH global ou controle da sessão interativa.
- Modelos e binários no disco D:, conforme autorização explícita do usuário nesta sessão. Sem novas compras ou API paga.
- Primeira interface apenas após o gate da Fase 0. Memória, execução de comandos e Windows amplo exigem os respectivos aceites; interface pronta não equivale a marco concluído.
- Prompts e respostas do benchmark são dados. Nenhum código produzido é executado.

## OpenAI

Consulta oficial em 17/10/2026: autenticação do Codex diferencia assinatura de API key. Sign in with ChatGPT documenta uso opcional do plano em clientes elegíveis, incluindo fluxo para projetos open-source, com registro e consentimento. A documentação não comprova elegibilidade desta aplicação pessoal privada nem desta conta. Não reutilizar credenciais do Codex nem copiar tokens. Integração permanece desabilitada; desenvolvimento assistido pelo Codex e runtime local são o caminho inicial.

Fontes verificadas:
- https://developers.openai.com/codex/auth (redireciona para https://learn.chatgpt.com/docs/auth)
- https://developers.openai.com/siwc/quickstart
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
- https://docs.ollama.com/windows
- https://docs.ollama.com/api/generate
- https://docs.ollama.com/api/tags
- https://ollama.com/library/qwen3:4b

## Recursos

Snapshot inicial: RAM total próxima de 15,9 GiB, livre próxima de 5,1 GiB; VRAM total 6144 MiB e 1125 MiB já em uso. Não assumir toda a RAM/VRAM disponível ao NEXO. C: com aproximadamente 14,5 GiB livres; D: com aproximadamente 190,7 GiB livres. São observações pontuais, não baseline de cinco minutos.

Meta ociosa <400 MB e <1% CPU em cinco minutos continua pendente. Orçamento operacional definitivo depende de medir pico de RAM/VRAM e interferência no uso pessoal. Tokens/s não substituem avaliação funcional.
