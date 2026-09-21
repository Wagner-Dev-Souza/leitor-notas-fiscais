# TASK F6 - README e relatorio final da entrega

## Target
Worktree `<worktree>`.
Arquivos: `README.md`, `relatorios/`.

## Pre-requisito
As frentes F1 a F5 ja entregaram. Leia o codigo e **rode** o pipeline antes de escrever:
nao descreva o que voce nao viu funcionar.

## Contexto obrigatorio
1. `docs/execucao/00-contrato-execucao.md` - contrato e secao 9 (definicao de pronto).
2. `docs/06-plano-e-requisitos-cliente.md` - seu proprio cronograma, base do cronograma humano.
3. `data/out/` - artefatos reais da rodada (planilha, auditoria, fila, painel).

## Change
1. `README.md` - substitua o conteudo atual (que e o scratch do teste de orquestracao) por
   documentacao de produto, nesta ordem:
   - o que a solucao faz, em linguagem de negocio e curta;
   - arquitetura em uma tela (fluxo documento/mensagem -> extracao -> planilha);
   - **como instalar as dependencias** (`uv` + `.venv` do projeto, ou `pip install -r requirements.txt`);
   - **como gerar os mocks** (`tools/gerar_mocks.py --seed 42`);
   - **como rodar o pipeline** (`.venv/Scripts/python.exe -m app.run --mock`), com a saida esperada;
   - como rodar os testes (`-m pytest -v`);
   - a planilha de saida: as 20 colunas e o significado de cada uma;
   - idempotencia e trilha de auditoria explicadas para quem nao e programador;
   - **limitacoes honestas**: OCR por motor simulado rotulado como simulado (nao ha Tesseract
     nesta maquina), sem WhatsApp real, sem rede em tempo de execucao, dados sinteticos.
     Nao apresente dado sintetico como se fosse do cliente.
2. `relatorios/RELATORIO-ENTREGA.md` - relatorio final destinado ao cliente (Loghanth/Wagner):
   o que foi entregue e onde, como reproduzir, evidencia de execucao real (o comando e o
   resultado observado), decisoes tomadas, o que ficou de fora e por que, e riscos residuais.
   Sem enfeite, sem numero inventado: **todo numero tem de vir de `data/out/` ou da saida real
   de comando que voce mesmo rodou**.
3. `relatorios/CRONOGRAMA.md` - os dois tempos, explicitamente separados e rotulados:
   - **cronograma humano** (o que se promete ao cliente, do doc 06, com premissas); e
   - **sprint real no tempo de execucao de IA**: quanto o squad de fato levou rodando como IA
     nesta fase. Meça pelo intervalo entre o primeiro e o ultimo commit/artefato que voce
     conseguir comprovar (`git log --date=iso` se o PO ja tiver commitado, ou mtime dos
     arquivos). Se nao conseguir medir com rigor, diga que e estimativa e mostre a base.

## Constraints
- Nada de preco, proposta comercial ou prazo que o cliente nao tenha aprovado.
- Nao invente numero. Cada numero do relatorio precisa de origem rastreavel.
- NAO edite arquivos de outro dono (tabela da secao 3 do contrato). O `README.md` e seu.
- **NAO rode nenhum comando `git`.** O PO commita.
- Se o pipeline nao rodar ate o fim na sua vez, escreva o README com o que existe e
  **relate o bloqueio** - nao escreva instrucao de algo que nao funciona.

## Ownership
Somente `README.md` e `relatorios/**`.

## Observable acceptance
- `README.md` contem as secoes de instalar, gerar mocks, rodar e testar.
- `relatorios/RELATORIO-ENTREGA.md` e `relatorios/CRONOGRAMA.md` existem com os dois tempos
  separados.
- Cole no `worker_done` o trecho da saida real do pipeline que voce rodou.
