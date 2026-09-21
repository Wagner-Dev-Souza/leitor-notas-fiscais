# TASK: Experiencia de revisao humana e interface do MVP

## Contexto do projeto
Cliente (projeto pequeno) quer agentes de IA que: (a) leiam PDFs de notas fiscais e pedidos e mensagens recebidas via WhatsApp e Telegram; (b) extraiam numero do pedido, valores, datas e itens; (c) insiram automaticamente numa planilha de controle financeiro da empresa. Precisao e robustez sao requisitos explicitos.

## Target
Escrever UM arquivo: <worktree>/docs/05-ux-revisao-humana.md

## Change (conteudo obrigatorio, nesta ordem)
1. Principio de desenho: por que revisao humana e obrigatoria quando a extracao tem baixa confianca, e o que NUNCA deve ser escrito na planilha sem aprovacao.
2. Fluxo de revisao humana ponta a ponta: como o usuario ve o que foi extraido, corrige, aprova ou rejeita, e o que acontece depois.
3. Wireframe textual das telas do MVP: painel de pendencias, detalhe do documento com campos extraidos lado a lado com o original, edicao do campo, aprovacao em lote, historico de aprovacoes. Descreva elemento por elemento (o que aparece, onde, e para que serve).
4. Notificacoes: quando e como avisar o usuario (ex.: resumo diario por e-mail ou Telegram), com foco em nao virar spam.
5. Padrao visual minimo da entrega: paleta, tipografia e componentes basicos, coerente com um produto financeiro serio; se for usar Bootstrap ou similar, diga o que reaproveitar.
6. O que fica para fase 2 (mobile, app proprio, dashboards avancados, multiusuario com perfis).
7. Riscos de usabilidade e de adocao (o operador voltar a digitar tudo a mao) e mitigacao.
8. Perguntas ao cliente (maximo 6, objetivas).

## Constraints
- Projeto pequeno: a interface do MVP deve caber em poucas telas; diga o que cortar.
- Sem codigo de producao nesta etapa: descreva, nao implemente. Wireframe em texto e suficiente.
- NAO invente preco, prazo nem escopo; toda estimativa com premissa explicita.
- NAO commite no git, nao crie branches, nao altere o worktree alem do arquivo acima.
- NAO edite config, memoria ou arquivos de outros perfis.
- Pt-BR, direto, maximo ~400 linhas.

## Ownership
Somente o arquivo docs/05-ux-revisao-humana.md.

## Observable acceptance
- O arquivo existe no caminho exato e contem as 8 secoes numeradas.
- A secao 3 descreve pelo menos 4 telas, elemento por elemento.
- Ao terminar, envie worker_done conforme o preambulo, com --outcome succeeded e --files-modified com o caminho absoluto do arquivo.
