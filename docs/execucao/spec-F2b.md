# TASK F2b - Correcao: motivo errado quando a soma dos itens nao pode ser calculada

## Target
`app/persistencia.py`, funcao `decidir()` (seu arquivo).

## Origem
Defeito D3 do relatorio de QA `tests/RELATORIO-F5.md` (ira), reproduzido pelo PO:
`test_status_e_motivos_contra_manifest[pdf/FORN-ALFA_nf_1003.pdf]` falha com
`motivos divergem: real=['divergencia_soma_itens'] manifest=['total_sem_detalhamento']`.

## O defeito
O caso de borda B6 e uma NF com **item sem valor unitario** - logo a soma dos itens **nao
pode ser calculada**. Hoje `decidir()` devolve `MOTIVO_DIVERGENCIA_ITENS`, que afirma ter
medido uma diferenca que nao existe. O manifesto (correto) espera
`MOTIVO_TOTAL_SEM_DETALHAMENTO`.

O status ja esta certo nos dois lados (`revisao_humana`) e nos dois casos **nao ha linha na
planilha** - o desacordo e so o codigo do motivo. Mas o codigo do motivo e contrato
(`contratos.MOTIVO_*`), e a fila de revisao, o painel e o relatorio fazem triagem por ele.
Dois codigos para o mesmo fato quebram a triagem.

## Decisao do PO (registrada no contrato, secao 5)
`MOTIVO_DIVERGENCIA_ITENS` exige diferenca **calculada**. Quando a soma nao pode ser
calculada (item sem quantidade, item sem valor unitario, itens ausentes ou parciais), o
motivo correto e `MOTIVO_TOTAL_SEM_DETALHAMENTO`. Nao se chama "divergencia" aquilo que
nao foi medido.

## Change
1. Ajuste o ramo "itens parciais/ausentes" de `decidir()`:
   - soma calculavel e `|total_calc - valor_total| <= 0,02` -> casa;
   - soma calculavel e diferenca dentro da tolerancia de suspeita -> `MOTIVO_SUSPEITA_ITENS`;
   - soma calculavel e diferenca acima -> `MOTIVO_DIVERGENCIA_ITENS`;
   - soma **nao** calculavel -> `MOTIVO_TOTAL_SEM_DETALHAMENTO`.
2. Confira que a mudanca nao afeta nenhuma outra decisao: os casos que hoje ficam
   `auto_aprovado` tem de continuar `auto_aprovado` e a planilha tem de continuar com
   **7 linhas estaveis** em rodadas repetidas.
3. Nada mais do seu codigo muda - nao "melhore" outras coisas pelo caminho.

## Constraints
- Nao edite `app/contratos.py` (CONGELADO), `tests/**` (ira), `data/mocks/**` (preguica)
  nem `app/pipeline.py`/`app/extracao.py` (avareza).
- **Nao rode nenhum comando `git`** - o PO versiona.
- Nao afrouxe tolerancia para o teste passar. A correcao e de classificacao, nao de limiar.

## Ownership
Somente `app/persistencia.py`.

## Observable acceptance
- Cole no `worker_done` a saida real de
  `.venv/Scripts/python.exe -m pytest -q tests/test_extracao.py` (esperado: D3 verde).
- Cole tambem a prova de idempotencia preservada: contagem de linhas da planilha em duas
  rodadas seguidas do comando unico (tem de ser 7 e 7).
- Se sobrar falha que nao seja sua, diga qual e de quem - nao conserte por conta propria.
