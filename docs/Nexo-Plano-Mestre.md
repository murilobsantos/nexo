NEXO — Plano mestre de desenvolvimento
Versão 0.1 • 17 de outubro de 2026 • Uso pessoal de Murilo
1. Visão e compromisso do produto
NEXO é um assistente pessoal persistente, extensível e orientado a tarefas. Conhece projetos e objetivos, pesquisa, trabalha com código, opera ferramentas e desenvolve habilidades verificáveis ao longo do tempo. Texto primeiro; voz, múltiplos dispositivos e operação ampla do Windows depois.
Prioridades: utilidade diária; aprendizado de engenharia de IA; independência progressiva de fornecedores; portfólio como consequência futura. Sem mensalidade adicional como requisito inicial. Não há objetivo de comercialização nesta versão.
A identidade, as memórias e as habilidades pertencem ao NEXO; o modelo de linguagem é substituível. Não se promete inteligência geral, melhoria infinita, equivalência com modelos de fronteira nem autonomia sem falhas. Independência será medida pela proporção de tarefas reais resolvidas localmente com qualidade aceitável.
Configuração de referência: Windows 11, Ryzen 5 5500, RAM de 16 GB e GTX 1660 Ti de 6 GB. O computador continua destinado também a jogos, desenvolvimento e uso pessoal.
2. Requisitos e decisões iniciais
- Assistência a programação, pesquisa, organização, objetivos e operação do computador.
- Autonomia ampla dentro de um objetivo e de um escopo de trabalho previamente definido; evitar confirmações repetitivas em operações reversíveis já autorizadas.
- Iniciativa por fila de oportunidades e objetivos ativos, com orçamento de execução e possibilidade de interrupção.
- Acesso amplo pode ser concedido; coleta indiscriminada não é requisito. Descobrir diretórios e aplicativos por metadados, incorporar conteúdo conforme necessidade e manter exclusões consultáveis.
- Nenhuma atividade de fundo deve disputar deliberadamente mouse, teclado ou foco com Murilo.
- Memória exportável, corrigível e apagável. Procedência e versão para conhecimentos e habilidades.
- Sem captura contínua de tela, áudio ou teclas por padrão. Contexto da rotina por eventos úteis e fontes configuradas.
- Gastos novos desativados por padrão. Falta de saldo ou limites de provedor coloca a tarefa em espera ou permite alternativa local; não autoriza compra automática.
3. Relação com o Argus
Repositório independente para o NEXO. O Argus continua sendo um sistema especializado em pesquisa de segurança explicitamente autorizada, conforme seu README consultado em 17/10/2026.
Reaproveitar conceitos de contexto de execução, evidências, eventos, especialistas substituíveis e limites de escopo. Reutilização de código somente após revisão de compatibilidade, dependências e testes; não copiar a arquitetura inteira antecipadamente.
Integração futura por adaptador: enviar tarefa e contexto autorizados, receber evidências e estado. O NEXO não amplia escopo nem substitui aprovações do Argus. Uma falha ou atualização em um projeto não pode impedir a inicialização do outro.
4. Arquitetura proposta
Um monólito modular local, com executores separados para tarefas pesadas ou com acesso ao sistema. Sem microsserviços, Kubernetes ou múltiplos bancos no início.
Módulo	Responsabilidade
Interface	Conversas, projetos, tarefas, memórias, permissões e consumo
Coordenador	Planejar, selecionar ferramentas, acompanhar e concluir tarefas
Registro de tarefas	Estados, dependências, tentativas, orçamentos e checkpoints
Gateway de modelos	Adaptar provedores e modelos, cancelar e registrar uso
Contexto e memória	Recuperar conteúdo, controlar validade, conflitos e procedência
Ferramentas	Arquivos, terminal, Git, pesquisa, navegador e Windows
Avaliador	Conferir resultados, regressões e candidatos a aprendizado
Agendador de recursos	Disponibilidade, prioridade, pausa e liberação de memória
Registro de habilidades	Manifestos, versões, testes e acessos necessários
Auditoria e recuperação	Eventos, alterações, restauração e diagnóstico


Especialistas iniciais: pesquisador, implementador e revisor. São papéis sequenciais do mesmo modelo, não três modelos residentes. A revisão pelo mesmo modelo não é evidência independente suficiente: testes e critérios objetivos têm precedência. Limite inicial de uma geração pesada por vez.
Fluxo: pedido → escopo e orçamento → recuperação de contexto → plano → ferramenta → evidência → avaliação → conclusão ou nova tentativa limitada → memória candidata.
Estados de tarefa: proposta, pronta, executando, pausada, aguardando usuário/recurso, concluída, falhou e cancelada. Após falha, verificar efeitos já produzidos antes de tentar novamente. Ações externas não idempotentes nunca são repetidas às cegas.
5. Stack de implementação
Decisão de projeto, sujeita a uma prova curta de compatibilidade antes de fixar versões:
- Python para núcleo, ferramentas, avaliação e integração com Windows; API HTTP local com FastAPI.
- TypeScript, React e Vite para uma interface web única e responsiva.
- SQLite para tarefas, eventos, memórias, configurações e busca textual inicial; arquivos para artefatos grandes.
- Um executor de modelos local compatível com modelos quantizados, escolhido por benchmark no próprio PC. Ollama e llama.cpp são candidatos de avaliação, não dependências definitivamente aprovadas.
- Git para código, habilidades e mudanças em projetos; worktrees ou cópias isoladas quando aplicável.
- Automação de navegador por integração própria; Windows por adaptadores estruturados, PowerShell e acessibilidade antes de cliques por coordenadas.
- Desktop/tray depois da validação web; avaliar wrapper leve apenas nessa etapa. Celular começa com interface responsiva na rede privada.
Contratos de ferramentas tipados e validados, com timeout, cancelamento, permissões e saída estruturada. Versões fixadas após teste de instalação. Não presumir que JSON válido significa que a ação solicitada é correta.
6. Estratégia de modelos e custo
Primeiro comparar modelos pequenos quantizados em português, código e seleção de ferramentas. Faixas de 3–4B e, se couber, 7–8B são hipóteses de benchmark; VRAM, contexto e backend determinam a viabilidade. Nenhuma taxa de tokens ou qualidade está garantida antecipadamente.
Pipeline de seleção: instalar um backend → medir RAM/VRAM em repouso e geração → executar conjunto fixo de tarefas → avaliar contexto curto e moderado → escolher configuração utilizável → registrar baseline. Só baixar outro modelo para responder a uma limitação observada. Limitar cache de modelos e avisar antes de downloads grandes.
O provedor local é obrigatório para a trajetória de independência. ChatGPT/Codex pode auxiliar o desenvolvimento pelo acesso já contratado. A documentação oficial distingue autenticação de assinatura e de API, com cobrança por uso para API keys. Também descreve uso do plano em clientes elegíveis via integração oficial; disponibilidade, registro do cliente, limites e adequação ao projeto pessoal precisam ser verificados na fase 0. Não assumir API ilimitada incluída no Plus nem usar cookies/tokens copiados ou automação da interface do ChatGPT como backend.
Se a integração oficial não estiver disponível: desenvolvimento assistido manualmente pelo Codex e execução do NEXO por modelo local. API paga permanece opcional e desativada. Registrar destino dos dados antes de chamadas externas; autorização para leitura local não equivale automaticamente a enviar conteúdo privado a terceiros.
7. Modos de convivência com o PC
Modo	Comportamento
Pausado	Sem novas execuções; painel e histórico disponíveis
Pessoal/jogo	Modelo descarregado; sem indexação pesada nem automação da sessão
Desenvolvimento assistido	Atua no projeto ativo; tarefas limitadas; sem tomar foco
Ausente	Executa fila autorizada, com orçamento de recursos e checkpoints
Controle do computador	Sessão explícita para operar aplicativos, com parada imediata


Regra inicial conservadora: uso pessoal prevalece. A detecção de atividade, processos e GPU ajuda a sugerir ou aplicar pausa, mas um botão manual tem precedência e a detecção não é infalível.
Controles: fila com prioridades, um trabalho pesado por vez, timeout de subprocessos, limites de CPU/memória quando suportados, limite de saída e tamanho de arquivos, frequência adaptativa e descarregamento do modelo. Comparar métricas com e sem NEXO; não prometer impacto zero.
Meta experimental: núcleo ocioso sem modelo residente abaixo de 400 MB de RAM e média inferior a 1% de CPU numa janela de 5 minutos; validar, não assumir. O restante do orçamento será definido por medição na fase 0. Solicitação de pausa deve impedir novas ações em até 2 segundos; geração e subprocessos devem ter cancelamento com escalonamento de encerramento. Não fingir que uma chamada externa ou ação já enviada pode ser desfeita.
Automação visual não roda na mesma sessão interativa enquanto Murilo usa mouse e teclado. Fora de foco, apenas APIs ou mecanismos que comprovadamente não mudem o foco. Uma VM pode permitir isolamento no futuro, mas compete por RAM e não é requisito desta máquina.
8. Memória e aprendizado
Cinco categorias: perfil do usuário; contexto por projeto; episódios de execução; conhecimentos com fontes; habilidades executáveis. Conversa bruta não é automaticamente conhecimento confirmado.
Cada registro contém origem, data, projeto, estado de validação, sensibilidade, validade/revisão e referências de evidência. Fatos conflitantes são preservados e sinalizados; uma preferência explícita recente pode substituir uma antiga, mantendo histórico. Conteúdo obsoleto deve ser invalidado após mudanças relevantes.
Recuperação começa com SQLite e busca textual. Só acrescentar embeddings locais quando uma avaliação mostrar vantagem real. Indexação incremental, exclusão de dependências, builds, binários e segredos. Conteúdo recuperado de arquivos ou internet é dado não confiável, não instrução com poder de alterar permissões.
Ciclo: lacuna → pesquisa → hipótese → experimento isolado → avaliação → habilidade candidata → promoção → monitoramento → revisão ou rollback. A IA não é a única juíza da própria solução.
Promoção exige critérios específicos e evidências reproduzíveis; habilidades de maior alcance exigem revisão humana. Um script útil pode ser salvo sem se tornar imediatamente uma ferramenta com acesso amplo. Habilidades têm manifesto, entradas/saídas, acessos, versão, testes e comando de desativação.
Autoalteração: ramo separado, ambiente de teste, diff, avaliações e possibilidade de restauração. Inicialmente requer revisão para ativação. O assistente não muda sozinho seu mecanismo de permissões, avaliação ou parada.
Treinamento futuro: reunir exemplos realmente corrigidos e validados; retirar segredos; separar treino, validação e teste; comparar com recuperação de contexto e modelos alternativos; só adotar se houver ganho nas tarefas pessoais. Treinar de forma contínua no PC compartilhado não faz parte do caminho inicial. Recursos externos de treinamento exigem decisão específica de custo e dados.
9. Escopo de autonomia
A autorização ampla do usuário será representada por sessões e políticas persistentes, sem pedir confirmação a cada comando dentro do escopo concedido. Cada tarefa recebe objetivo, diretórios, ferramentas, prazo e orçamento.
Mudanças locais reversíveis podem prosseguir conforme a política escolhida. Ações de grande impacto — apagar dados definitivamente, mexer em boot/discos, gastar dinheiro, publicar, enviar mensagens ou alterar credenciais — precisam de autorização específica antecipada ou confirmação concreta. Isso evita interpretar “resolva este projeto” como autorização para qualquer consequência fora dele.
Credenciais no cofre do sistema; não em prompts, banco de memória ou logs. Conteúdo pessoal fora da tarefa não é incorporado sem necessidade. Capturas temporárias devem ter retenção curta. Backups e checkpoints antes de mudanças relevantes; Git não protege arquivos não rastreados e não substitui backup.
10. Roadmap por marcos
Estimativa de esforço, não prazo contratado. Uma pessoa aprendendo e desenvolvendo, com assistência de IA. As horas não incluem downloads demorados, compras de hardware nem treinamento de modelos. Passar de fase exige demonstração, não apenas interface pronta.
Fase 0 — Viabilidade e contrato do projeto (8–16 h)
Inventariar ambiente Python/Node/Git, espaço livre e drivers. Criar repositório independente e decisões de arquitetura. Medir modelos e uso de recursos. Verificar integração oficial do plano OpenAI. Criar 20 tarefas representativas com resultado esperado, sem enviar segredos para serviços externos.
Saída: backend e modelo inicial escolhidos por evidência, orçamento de recursos, caminho de autenticação e backlog priorizado. Se os modelos locais falharem nas tarefas mínimas, reduzir escopo e documentar limites antes de expandir.
Fase 1 — Núcleo persistente (20–35 h)
Chat textual, gateway de modelos, streaming, cancelamento, SQLite com migrações, fila, eventos, retomada após reinício e painel de estado. Inicialmente ferramentas de leitura e acesso a uma pasta de demonstração.
Aceite: conversar, consultar arquivos e reiniciar sem perder a tarefa; cancelamento funciona; sem acesso fora do escopo e sem processos órfãos.
Fase 2 — Assistente de desenvolvimento (30–50 h)
Mapa do repositório, busca, edição por patches, Git, comandos delimitados, testes e build. Criar isolamento e mostrar diff. Limitar tentativas de correção; registrar diagnóstico quando falhar.
Aceite: resolver um bug preparado e implementar uma funcionalidade pequena num projeto de teste; passar critérios definidos e permitir rejeitar/restaurar a alteração. Verificar também arquivos não rastreados e mudanças pré-existentes do usuário.
Fase 3 — Memória útil e pesquisa (25–45 h)
Preferências, decisões por projeto, pesquisa com fontes, indexação incremental, correção e exclusão de memórias. Revisão de conflitos e tratamento de instruções maliciosas em conteúdo consultado.
Aceite: recordar uma decisão após reinício e aplicá-la no projeto certo; corrigir memória errada; pesquisa diferencia evidência de inferência; exclusão retira também índice e derivados conforme política de backup documentada.
As fases 0–3 formam o MVP. Ele já deve ser usado numa tarefa real e pequena antes de adicionar desktop amplo.
Fase 4 — Iniciativa e convivência (25–45 h)
Modos pessoal, desenvolvimento e ausente; detecção de atividade; agendamento; tarefas recorrentes; cooldown de sugestões; limites de notificações e recursos. Iniciativa vinculada a objetivos, sem criar trabalho infinito.
Aceite: tarefa autorizada continua quando ausente, pausa no retorno e retoma com estado consistente; cenário de jogo não mantém modelo na GPU. Perfil pessoal não deve apresentar degradação mensurável relevante frente à variação normal do benchmark acordado.
Fase 5 — Operação do Windows (35–65 h)
Adaptadores para arquivos, processos e aplicativos; navegador separado; seleção explícita de sessão; inspeção por acessibilidade; fallback visual quando necessário. Tecla global de parada e checkpoints. Elevação administrativa somente por ação e não como privilégio permanente.
Aceite: abrir projeto no editor, executar o ambiente, coletar logs e organizar uma pasta de teste com restauração. Testar interrupção durante automação e ausência de disputa por foco. Operações de aplicações reais variam e serão adicionadas individualmente.
Fase 6 — Especialistas e habilidades (30–55 h)
Contratos de papéis, delegação sequencial, registro de módulos, criador de habilidades candidatas, avaliações e versionamento. Comparar com fluxo de um único agente; remover delegações que só aumentam custo.
Aceite: pesquisador, implementador e revisor concluem uma tarefa com evidências; uma habilidade validada é reutilizada em outra sessão e pode ser desativada sem quebrar o núcleo.
Fase 7 — Desktop, celular e voz (35–65 h)
Tray, atalho global, interface responsiva, acesso autenticado em rede privada e depois transcrição/fala. Começar com push-to-talk; escuta contínua é opcional e posterior. Microfone visivelmente ativo e processamento de voz liberado após uso.
Aceite: enviar tarefa do celular na rede privada e consultar o resultado; acesso não autenticado bloqueado; voz permite revisar uma intenção ambígua antes de ação de grande impacto. Sem expor porta diretamente à internet como atalho.
Fase 8 — Evolução controlada e integração Argus (35–70 h)
Conjunto histórico de avaliações, comparação entre versões, experimentos de ferramentas e recuperação, atualizações reversíveis, adaptador do Argus e análise de viabilidade de treinamento. Avaliar modelos novos apenas mediante ganho esperado.
Aceite: melhoria demonstrada no conjunto de validação sem regressão crítica no teste reservado; versão anterior restaurável; integração Argus preserva escopo e aprovações dele. Treinamento não é obrigatório para concluir esta fase.
Fase 9 — Versão pessoal 1.0 (20–35 h)
Instalação reproduzível, atualização, backup/restore exercitados, exportação de dados, documentação, diagnóstico e duas semanas de uso cotidiano com registro de problemas.
Aceite: instalar em ambiente limpo, restaurar memória e tarefas, recuperar de falha simulada e usar rotineiramente sem incidentes de perda de trabalho ou interferência não tratada. Novas capacidades passam a ser versões incrementais.
Total estimado: 263–481 horas. A 10 h/semana, cerca de 6–11 meses antes de folgas e imprevistos. MVP de 83–146 h: aproximadamente 2–3,5 meses nessa dedicação. Entregar utilidade antes de completar o roadmap; recalcular as estimativas ao final de cada fase. A visão de evolução contínua não tem um “fim” definitivo; a versão 1.0 tem critérios finitos.
11. Avaliação e definição de sucesso
Conjunto inicial de 20 tarefas: cinco correções de código; quatro funcionalidades pequenas; quatro pesquisas com fontes; três tarefas de organização; duas de memória; duas de convivência/interrupção. Acrescentar suítes próprias antes de liberar Windows e integrações.
Separar tarefas usadas no desenvolvimento de um conjunto reservado. Registrar sucesso objetivo, intervenção humana, duração, RAM/VRAM, chamadas externas e regressões. Pesquisa é avaliada também por procedência e sustentação das conclusões.
Metas provisórias: pelo menos 80% das tarefas do escopo de cada release aprovadas; nenhuma alteração destrutiva fora do escopo; restauração aprovada em todos os cenários suportados; pelo menos 70% de recuperação correta nas consultas de memória preparadas. Ajustar escopo, não maquiar resultados, se um modelo pequeno não atingir as metas.
Medir independência: fração de tarefas resolvidas com modelo local, sem provedor externo e com critérios satisfeitos. Começar com uma baseline real; não fixar promessa de substituir Codex/Claude em qualquer tarefa.
12. Riscos e respostas de projeto
- Capacidade limitada de modelos locais: tarefas menores, contexto selecionado e validação objetiva; não compensar com loops infinitos.
- Disputa de recursos: modos de uso, descarga de modelo e uma execução pesada por vez.
- Complexidade excessiva: monólito modular, interfaces simples e integração após uso real.
- Memória contaminada: procedência, estados de validação, revisão e exclusão.
- Autoalteração degradante: ramo isolado, conjunto reservado e rollback.
- Pesquisa sem custo adicional: acesso direto a fontes e caminhos permitidos; serviços de busca podem impor limites, autenticação ou custo. Nenhuma disponibilidade ilimitada presumida.
- Rotina invasiva: coleta por finalidade e transparência, mesmo com autorização ampla.
- Dependência de fornecedor: adaptadores e exportação; desempenho equivalente local não é garantido.
13. Backlog das primeiras duas semanas
Semana 1, se houver aproximadamente 10 horas: repositório, especificação mínima, benchmark inicial, 20 casos de avaliação e definição de recursos. Semana 2: esqueleto núcleo/interface, primeiro chat local, leitura de pasta e persistência básica. Se a fase 0 consumir mais tempo, deslocar a segunda semana; não pular a validação.
Primeira demonstração: “NEXO, leia este projeto de teste e explique como executá-lo, citando os arquivos usados”. Segunda: “corrija este bug preparado, execute a verificação e mostre o diff”. Terceira, após memória: “retome a tarefa de ontem respeitando a decisão que registrei”.
Não priorizar avatar, animações, múltiplos agentes simultâneos, treino de modelo, ingestão de todo o disco ou controle amplo de desktop antes da primeira demonstração.
14. Manutenção após a versão 1.0
Semanal: examinar falhas, revisar candidatos a memória e priorizar uma melhoria útil. Mensal: testar restauração e verificar dependências/modelos com benefício concreto. Antes de cada release: executar conjunto reservado, medir recursos e comparar com a versão anterior. Atualizações de esquema exigem backup e migração testada.
O assistente deve manter uma lista curta de limitações conhecidas e sugerir evolução com evidências: frequência do problema, impacto e custo estimado. Crescimento eficiente significa acrescentar capacidade útil por recurso consumido, não maximizar quantidade de módulos.
15. Referências e limites de verificação
Fontes consultadas em 17/10/2026:
- Projeto Argus: https://github.com/murilobsantos/Project-Argus — README e documentação introdutória examinados nesta conversa; não foi feita auditoria completa do repositório.
- Autenticação OpenAI/Codex: https://developers.openai.com/codex/auth — distingue acesso por assinatura e API key; fluxo programático deve seguir documentação vigente.
- Sign in with ChatGPT: https://developers.openai.com/siwc/quickstart — descreve caminhos elegíveis para uso do plano; não confirma elegibilidade desta aplicação pessoal.
A stack, os limites de consumo e as metas numéricas são propostas de engenharia, não resultados medidos. Compatibilidade exata, versões de bibliotecas, modelo local e integração do plano são decisões de prova de conceito na fase 0.