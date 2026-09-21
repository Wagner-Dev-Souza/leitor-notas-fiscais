# TASK: Arquitetura da solucao

## Contexto do projeto
Cliente (projeto pequeno) quer agentes de IA que: (a) leiam PDFs de notas fiscais e pedidos e mensagens recebidas via WhatsApp e Telegram; (b) extraiam numero do pedido, valores, datas e itens; (c) insiram automaticamente numa planilha de controle financeiro da empresa. Precisa ser preciso na extracao e robusto a variacao de formatos de documento e de mensagem. Objetivo: reduzir entrada manual de dados.

## Target
Escrever UM arquivo: <local>

## Change (conteudo obrigatorio, nesta ordem)
1. Visao de componentes (ingestao PDF, ingestao WhatsApp, ingestao Telegram, fila, extrator IA, validador, escritor da planilha, banco) com responsabilidade de cada um.
2. Fluxo ponta a ponta passo a passo (do documento/mensagem chegando ate a linha na planilha).
3. Contratos de interface: webhook/endpoint de entrada de documentos, endpoint de mensagens, payload de saida normalizado (JSON com os campos extraidos).
4. Stack recomendada (linguagem, libs de parsing/OCR, orquestracao do agente, banco, fila, escrita na planilha) com justificativa de UMA linha por escolha.
5. Opcoes de destino da planilha: Google Sheets API vs Excel/OneDrive (Graph API) vs CSV em pasta sincronizada - trade-offs.
6. O que e MVP e o que e fase 2 (separar claramente).
7. Riscos tecnicos da arquitetura (ordem decrescente de impacto) e mitigacao.
8. Perguntas ao cliente (maximo 8, objetivas).

## Constraints
- Projeto pequeno: prefira o desenho mais simples que atenda, sem over-engineering; se algo exigir mais complexidade, diga o custo.
- NAO invente preco, prazo final, numero de clientes nem escopo.
- Toda estimativa precisa vir com premissa explicita ao lado.
- NAO commite no git, nao crie branches, nao altere o worktree alem do arquivo acima.
- NAO edite config, memoria ou arquivos de outros perfis.
- Pt-BR, texto tecnico direto, maximo ~400 linhas. ASCII puro nos titulos de secao.

## Ownership
Somente o arquivo docs/01-arquitetura.md.

## Observable acceptance
- O arquivo existe no caminho exato e contem as 8 secoes numeradas.
- Cada componente citado no item 1 aparece no fluxo do item 2 (rastreabilidade).
- Ao terminar, envie worker_done conforme o preambulo, com --outcome succeeded e --files-modified com o caminho absoluto do arquivo.
