# TASK F4 - Revisao humana: fila de excecoes e painel de acompanhamento

## Target
Worktree `<local>`.
Arquivo: `app/revisao.py`.

## Contexto obrigatorio (leia ANTES de escrever codigo)
1. `docs/execucao/00-contrato-execucao.md` secoes 4.1, 4.6 e 5. Integra.
2. `app/contratos.py` - CONGELADO pelo PO. Importe `STATUS_REVISAO_HUMANA`,
   `STATUS_REJEITADO`, motivos e a tabela `fila_excecoes`.
3. `docs/05-ux-revisao-humana.md` - seu proprio planejamento de UX. Aplique o principio:
   valor duvidoso **nunca** entra na planilha em silencio.

## Change
`app/revisao.py`, com as assinaturas congeladas da secao 5 do contrato:
- `enfileirar_excecoes(conn, itens) -> int`: grava as pendencias na tabela `fila_excecoes`
  (motivo codigo, detalhe, valor suspeito, status `aberta`, aberta_em). Idempotente:
  reenfileirar a mesma pendencia nao cria duplicata.
- `listar_pendencias(conn) -> list[dict]`: pendencias abertas com o contexto util para
  decisao humana (documento, campo suspeito, valor lido, valor calculado quando houver).
- `exportar_fila(conn, caminho_json) -> int`: materializa a fila em
  `data/out/fila_excecoes.json`.
- `gerar_painel(conn, caminho_html) -> str`: painel HTML autocontido (sem CDN, sem rede -
  CSS embutido), com:
  * cartoes de resumo: artefatos lidos, auto-aprovados, deduplicados, em revisao, rejeitados;
  * valor total conciliado (soma em centavos formatada em BRL via `contratos.formatar_brl`);
  * tabela do que entrou (documento, origem, numero do pedido, emitente/CNPJ, data,
     valor, confianca, status) e linhas de excecao em destaque;
  * rodape com data/hora da geracao e o aviso de que leituras por OCR simulado estao
     marcadas como simuladas.
  Padrao visual sobrio de produto financeiro (fundo claro, tipografia de sistema, sem
  enfeite). Devolve o caminho.

## Constraints
- Python 3.12 do venv. `openpyxl`/`pytest` ja instalados; nada de framework web, nada de CDN,
  nada de rede: o painel e um arquivo HTML estatico gerado localmente.
- NAO escreva em `data/out/` por conta propria fora das funcoes acima - quem orquestra e o
  `app/pipeline.py` (avareza).
- NAO edite arquivos de outro dono (tabela da secao 3 do contrato).
- **NAO rode nenhum comando `git`.** O PO commita.
- Sem dado pessoal real: o material e sintetico, mantenha assim.

## Ownership
Somente `app/revisao.py`. Leitura livre do repositorio.

## Observable acceptance
- Prove com um teste local seu (script curto ou pytest avulso) que: enfileirar duas vezes a
  mesma pendencia nao duplica, `exportar_fila` grava o json e `gerar_painel` escreve um HTML
  com o resumo. Cole a saida real no `worker_done`.
- Declare o caminho do `app/revisao.py` e do HTML gerado no seu teste.
