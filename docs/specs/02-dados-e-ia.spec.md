# TASK: Extracao de dados e estrategia de IA

## Contexto do projeto
Cliente (projeto pequeno) quer agentes de IA que: (a) leiam PDFs de notas fiscais e pedidos e mensagens recebidas via WhatsApp e Telegram; (b) extraiam numero do pedido, valores, datas e itens; (c) insiram automaticamente numa planilha de controle financeiro da empresa. Precisa ser preciso na extracao e robusto a variacao de formatos de documento e de mensagem.

## Target
Escrever UM arquivo: <worktree>/docs/02-dados-e-ia.md

## Change (conteudo obrigatorio, nesta ordem)
1. Estrategia de extracao: comparar (a) regex/parser determinístico por template, (b) OCR + LLM com saida estruturada (JSON schema), (c) hibrido. Recomendar UM caminho para o MVP e explicar por que, incluindo tratamento de PDF digital vs PDF escaneado.
2. Campos alvo e tipos: numero do pedido, emitente/CNPJ, data de emissao, data de vencimento, valor total, itens (descricao, quantidade, valor unitario), forma de pagamento, chave de acesso da NF. Para cada campo: tipo, obrigatorio ou nao, tolerancia a erro, regra de normalizacao (data, moeda BR com virgula, CNPJ).
3. Modelo de dados: tabelas/colunas minimas (documentos, mensagens, pedidos, itens, fornecedores, log de extracao, fila de excecoes), chaves e como garantir idempotencia e deduplicacao (mesmo documento reenviado, mesma NF em PDF e em mensagem).
4. Regras de validacao e score de confianca: o que rejeita automaticamente, o que vai para revisao humana, soma dos itens vs total, CNPJ valido, data plausivel.
5. Conjunto de avaliacao e metrica: como montar a amostra, quais metricas usar por campo e no documento inteiro, e qual meta de acuracia propor para aceitar o MVP (com premissa).
6. Custo por documento: estimar tokens/custo por PDF e por mensagem, com a premissa de modelo e de tamanho de documento explicita. Se nao houver base para o numero, diga que e estimativa e mostre a conta.
7. Riscos de dados/IA (alucinacao de valor, campo inventado, layout novo) e mitigacao.
8. Perguntas ao cliente (maximo 8, objetivas).

## Constraints
- NAO invente preco de fornecedor, prazo nem escopo; toda estimativa com premissa explicita.
- Priorize o que reduz erro de valor monetario: dados financeiros errados sao o pior modo de falha.
- NAO commite no git, nao crie branches, nao altere o worktree alem do arquivo acima.
- NAO edite config, memoria ou arquivos de outros perfis.
- Pt-BR, tecnico e direto, maximo ~400 linhas.

## Ownership
Somente o arquivo docs/02-dados-e-ia.md.

## Observable acceptance
- O arquivo existe no caminho exato e contem as 8 secoes numeradas.
- O item 1 termina com UMA recomendacao explicita para o MVP.
- Ao terminar, envie worker_done conforme o preambulo, com --outcome succeeded e --files-modified com o caminho absoluto do arquivo.
