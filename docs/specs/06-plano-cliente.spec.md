# TASK: Plano por etapas e requisitos do cliente

## Contexto do projeto
Cliente (projeto pequeno) quer agentes de IA que: (a) leiam PDFs de notas fiscais e pedidos e mensagens recebidas via WhatsApp e Telegram; (b) extraiam numero do pedido, valores, datas e itens; (c) insiram automaticamente numa planilha de controle financeiro da empresa. Precisa ser preciso na extracao e robusto a variacao de formatos.

O cliente declarou o que espera receber: escopo priorizado, solucao desenhada o suficiente para confiar no prazo, prazo por etapas, o que precisamos dele para comecar, e riscos/pontos em aberto.

## Target
Escrever UM arquivo: <local>

## Change (conteudo obrigatorio, nesta ordem)
1. Cronograma por etapas: 4 a 5 etapas, cada uma com objetivo, entregavel visivel para o cliente e duracao em dias uteis. Marque explicitamente quais premissas sustentam o prazo (ex.: acesso a amostras de PDFs, aprovacao em ate X dias uteis, numero de WhatsApp ja verificado).
2. Marcos de aceite: o que o cliente consegue verificar no fim de cada etapa.
3. Checklist do que precisamos do cliente para comecar: acessos, amostras reais de PDFs e de mensagens, planilha alvo, contato decisor, e qualquer credencial necessaria. Diga o que trava o inicio se nao vier.
4. Ritual de comunicacao: cadencia de atualizacao, formato, quem aprova cada marco.
5. Dependencias externas que podem atrasar o projeto (verificacao de conta WhatsApp Business junto a Meta, limites de API, acesso ao provedor de IA, acesso a planilha corporativa).
6. Riscos de prazo com impacto estimado e o que fazer se ocorrerem.
7. Pontos em aberto para o cliente decidir (maximo 10, em forma de pergunta com opcoes quando fizer sentido).

## Constraints
- NAO invente preco, valor de hora, nem proposta comercial: orcamento nao foi pedido. Foco em prazo e escopo.
- Todo prazo precisa de premissa explicita; se uma etapa depende do cliente, diga isso na propria linha.
- NAO defina escopo final: proponha e marque o que precisa de aprovacao do PO e do cliente.
- NAO commite no git, nao crie branches, nao altere o worktree alem do arquivo acima.
- NAO edite config, memoria ou arquivos de outros perfis.
- Pt-BR, direto, maximo ~400 linhas.

## Ownership
Somente o arquivo docs/06-plano-e-requisitos-cliente.md.

## Observable acceptance
- O arquivo existe no caminho exato e contem as 7 secoes numeradas.
- A secao 1 traz a duracao total somada em dias uteis e as premissas que a sustentam.
- Ao terminar, envie worker_done conforme o preambulo, com --outcome succeeded e --files-modified com o caminho absoluto do arquivo.
