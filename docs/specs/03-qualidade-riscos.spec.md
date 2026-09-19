# TASK: Qualidade, criterios de aceite e riscos

## Contexto do projeto
Cliente (projeto pequeno) quer agentes de IA que: (a) leiam PDFs de notas fiscais e pedidos e mensagens recebidas via WhatsApp e Telegram; (b) extraiam numero do pedido, valores, datas e itens; (c) insiram automaticamente numa planilha de controle financeiro da empresa. Precisa ser preciso na extracao e robusto a variacao de formatos de documento e de mensagem.

## Target
Escrever UM arquivo: <local>

## Change (conteudo obrigatorio, nesta ordem)
1. Criterios de aceite testaveis por etapa (definicao de pronto): o que precisa ser verdade para o cliente aceitar cada entrega.
2. Plano de testes: unitarios, integracao, ponta a ponta com PDFs reais variados, testes de mensagem (WhatsApp/Telegram) e teste de escrita na planilha sem duplicar linha.
3. Casos adversariais obrigatorios: PDF escaneado de baixa qualidade, PDF com tabela e quebra de pagina, layout de fornecedor diferente, nota com desconto/frete/imposto, mensagem de pedido sem valor, mensagem ambigua, mesmo pedido enviado duas vezes, documento com texto malicioso (instrucao escondida no PDF ou na mensagem) tentando desviar o agente.
4. Seguranca e LGPD: dados financeiros e pessoais, autenticacao de webhook, quem pode ver a planilha, retencao do PDF original, o que nao pode ir para API de terceiro.
5. Performance e limites: volume esperado por dia como premissa, tempo aceitavel por documento, o que acontece se a API externa cair.
6. Evidencias exigidas para aceitar cada etapa (o que voce vai querer ver antes de dizer que funciona).
7. Lista priorizada de riscos do projeto (probabilidade x impacto), incluindo risco de extracao errada silenciosa.
8. Perguntas ao cliente (maximo 8, objetivas).

## Constraints
- NAO invente numero de volume, preco nem prazo; se precisar de volume para dimensionar, trate como pergunta ao cliente.
- Seja concreto: cada caso adversarial deve dizer entrada, resultado esperado e como verificar.
- NAO commite no git, nao crie branches, nao altere o worktree alem do arquivo acima.
- NAO edite config, memoria ou arquivos de outros perfis.
- Pt-BR, tecnico e direto, maximo ~400 linhas.

## Ownership
Somente o arquivo docs/03-qualidade-riscos.md.

## Observable acceptance
- O arquivo existe no caminho exato e contem as 8 secoes numeradas.
- A secao 1 tem criterios verificaveis (nao frases genericas como funciona bem).
- Ao terminar, envie worker_done conforme o preambulo, com --outcome succeeded e --files-modified com o caminho absoluto do arquivo.
