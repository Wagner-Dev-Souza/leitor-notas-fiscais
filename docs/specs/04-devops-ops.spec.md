# TASK: Operacao, deploy e automacao

## Contexto do projeto
Cliente (projeto pequeno) quer agentes de IA que: (a) leiam PDFs de notas fiscais e pedidos e mensagens recebidas via WhatsApp e Telegram; (b) extraiam numero do pedido, valores, datas e itens; (c) insiram automaticamente numa planilha de controle financeiro da empresa. Precisa ser preciso e robusto a variacao de formatos.

## Target
Escrever UM arquivo: <local>

## Change (conteudo obrigatorio, nesta ordem)
1. Onde o sistema roda: 2 ou 3 opcoes (ex.: VPS com Docker, container gerenciado, serverless) com trade-off de custo, esforco de setup e adequacao a um projeto pequeno. Terminar com UMA recomendacao para o MVP.
2. Necessidades de rede e integracao externa: endpoint publico para webhook do WhatsApp/Telegram, certificado, segredos e como guarda-los (nunca em texto no repositorio).
3. Pipeline minimo de entrega: repositorio, ambiente de teste, processo de deploy, rollback.
4. Observabilidade: logs estruturados, o que monitorar (documentos processados, falhas, linhas escritas na planilha), e alertas que importam.
5. Resiliencia: fila, retries com backoff, dead-letter, o que fazer quando a API do provedor de IA ou a planilha falhar.
6. Backup e retencao: banco, PDFs originais e planilha; frequencia e restauracao.
7. Runbook operacional curto: os 5 incidentes mais provaveis e o que fazer em cada um.
8. Esforco de setup por opcao (em dias uteis, com premissa explicita) - sem preco.
9. Riscos operacionais e perguntas ao cliente (maximo 6).

## Constraints
- NAO invente preco de hospedagem nem prazo final; use faixas com premissa ou marque como a confirmar.
- NAO execute nada de infraestrutura, nao instale, nao contrate: este trabalho e SO o documento.
- NAO commite no git, nao crie branches, nao altere o worktree alem do arquivo acima.
- NAO edite config, memoria ou arquivos de outros perfis.
- Pt-BR, tecnico e direto, maximo ~400 linhas.

## Ownership
Somente o arquivo docs/04-devops-ops.md.

## Observable acceptance
- O arquivo existe no caminho exato e contem as 9 secoes numeradas.
- A secao 1 termina com UMA recomendacao explicita para o MVP.
- Ao terminar, envie worker_done conforme o preambulo, com --outcome succeeded e --files-modified com o caminho absoluto do arquivo.
