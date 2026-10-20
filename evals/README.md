# Avaliações

`acceptance.json` define 20 cenários e resultados esperados na distribuição do plano mestre. Todos começam como `not_run`. São especificações; fixtures executáveis serão implementadas com as capacidades de cada fase. Não atribuir aprovação por existência do documento.

Os seis casos `holdout` não devem orientar ajustes de prompts ou implementação. Nesta versão são reservados por processo, não ocultos criptograficamente. Não há alegação de avaliação cega independente.

`tools/benchmark.py` executa quatro sondas sintéticas em português, código, escolha de ferramenta e fonte maliciosa, com contextos curto/moderado. Registra saída bruta, configurações e latência. Revisão manual deve verificar correção e procedência; nunca executar respostas do modelo automaticamente. Sucesso nessas sondas não equivale a aprovação dos cenários de produto.

`tools/review_transport.py CAMINHO_DO_RELATORIO` detecta saídas vazias/truncadas e valida a chamada JSON exata na sonda de ferramenta. Essa classificação é só de transporte/formato; os outros critérios exigem revisão. O conjunto é pequeno: duas janelas do mesmo prompt não contam como duas tarefas independentes.

Metas provisórias da release: 80% de aprovação objetiva no escopo, nenhuma mudança destrutiva fora dele, restauração em todos os cenários suportados e 70% nas consultas de memória. Sem capacidade implementada, o resultado é não executado, nunca aprovado.
