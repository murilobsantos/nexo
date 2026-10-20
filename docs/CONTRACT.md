# Contrato do primeiro incremento

## Resultado demonstrável

Pedido: “NEXO, leia este projeto de teste e explique como executá-lo, citando os arquivos usados”. O incremento recupera README e manifesto de um diretório de demonstração autorizado, responde em português, mostra procedência e registra tarefa/eventos em SQLite. Um reinício preserva o histórico. Demonstração implementada e executada; evidências em `../reports/PHASE-1.md`.

## Limite inicial

Texto e ferramentas de leitura. Um modelo local carregado por vez. Sem terminal de propósito geral, patches, Git operacional, indexação do disco, escrita em arquivos do usuário, rede privada ou controle de aplicativos na primeira demonstração. Essas capacidades têm marcos próprios no plano mestre.

## Tarefa

Identificador estável; objetivo; projeto; diretório canônico autorizado; ferramentas permitidas; estado; prazo; orçamento de geração/tentativas/bytes; cancelamento solicitado; checkpoint; versão de política. A autorização é aplicada pelo executor, nunca inferida do texto gerado pelo modelo ou de conteúdo recuperado.

Estados: proposta → pronta → executando → concluída/falhou/cancelada. Executando pode ir para pausada ou aguardando usuário/recurso. Retomada revalida escopo e efeitos observados. Em reinício, tarefas que estavam executando vão para revisão de checkpoint antes de outra ação; não voltam automaticamente a executar ações não idempotentes.

## Ferramenta de leitura

Entrada: caminho relativo e limite de bytes. Validar caminho resolvido, rejeitar escape de escopo inclusive por links, bloquear arquivos sensíveis/excluídos, limitar leitura antes de alocar saída e registrar caminho relativo, hash, tamanho, truncamento e erro estruturado. Escopo não equivale a proteção contra troca concorrente de arquivos; avaliar abertura segura no Windows antes de expor ferramentas a árvores que terceiros possam alterar.

Conteúdo de arquivo é dado não confiável. Uma fonte que pede novas permissões, comandos ou envio de segredos não pode modificar a política de execução. A ferramenta devolve dados ao coordenador, não executa instruções encontradas no documento.

## Gateway

Interface de geração com mensagens, limites, eventos de delta/uso/fim/erro e sinal de cancelamento. Adaptador Ollama inicial. Mensagens de raciocínio e resposta final permanecem separadas quando fornecidas pelo backend. Um término por limite de tokens é resultado incompleto. Parser JSON não concede autorização nem valida semântica da ferramenta.

Local é padrão. Chamadas externas exigem provedor habilitado, finalidade e destino dos dados registrados. API paga desabilitada. Ausência de provedor, recursos ou saldo leva a espera/falha clara, sem compra nem fallback externo silencioso.

## Persistência e auditoria

SQLite com migrações versionadas para tarefas, mensagens e eventos, com conexões explicitamente fechadas no Windows. Transações atômicas por mudança de estado e evento correspondente. Artefatos grandes fora do banco. Eventos registram início, ação proposta/autorizada, evidência, fim e erro, sem credenciais ou conteúdo indiscriminado.

Migração precisa de backup e teste de restauração. Dados não são memória confirmada automaticamente. Recuperação após falha verifica efeitos antes de repetir uma ação.

## Interrupção e recursos

Pausa impede novas ações em até dois segundos; geração e subprocessos têm cancelamento real medido. O timeout do cliente de benchmark não satisfaz esse requisito. Modo pessoal solicita descarga, confirma ausência de modelo residente e impede trabalhos pesados. Nenhuma execução toma foco, mouse ou teclado.

RAM/VRAM e duração serão medidas com o núcleo em execução; o processo Ollama sozinho não demonstra a meta do núcleo ocioso. O modo de desenvolvimento usa limites conservadores até haver comparação com uso pessoal/jogos.

## Aceite da Fase 1

1. Conversa local e leitura com arquivos citados.
2. Fluxo persistido após parar e iniciar o núcleo.
3. Escape por caminho/links e leitura excluída rejeitados por testes objetivos.
4. Interrupção medida, sem novas ações após pausa e sem processos órfãos.
5. Migrações, restauração e falhas de backend exercitadas.

Build da interface, testes de transporte e velocidade do modelo são evidências auxiliares; não substituem esses cinco resultados.
