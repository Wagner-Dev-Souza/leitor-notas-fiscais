# TASK F2 - Normalizacao, modelo de dados, idempotencia e planilha

## Target
Worktree `<worktree>`.
Arquivos: `app/normaliza.py`, `app/persistencia.py`.

## Contexto obrigatorio (leia ANTES de escrever codigo)
1. `docs/execucao/00-contrato-execucao.md` - a lei da fase. Integra.
2. `app/contratos.py` - CONGELADO pelo PO. Nao edite. Importe daqui dataclasses,
   limiares, motivos e `COLUNAS_PLANILHA`.
3. `docs/02-dados-e-ia.md` secoes 2, 3 e 4 - seu proprio planejamento. Siga-o.

## Change
1. `app/normaliza.py` - funcoes puras, com teste facil:
   - `normalizar_cnpj(bruto) -> (cnpj14|None, dv_valido)` e `validar_cnpj_dv(cnpj14)`:
     digito verificador **mod 11 de verdade**. DV invalido nunca e "consertado".
   - `validar_chave_nf_dv(chave44)`: mod 11 da chave de acesso.
   - `normalizar_data(bruto) -> (iso|None, ambigua)`: aceita `dd/mm/aaaa`, `dd/mm/aa`,
     `aaaa-mm-dd` e `dd de <mes> de aaaa`. Assume **dd/mm**; marca `ambigua=True` quando
     o dia e <= 12. Devolve `YYYY-MM-DD`.
   - `normalizar_moeda_centavos(bruto) -> int|None`: `R$ 1.234,56` -> `123456`.
     Se `.` for milhar e `,` decimal, a virgula e o decimal. Nunca float.
   - `normalizar_quantidade(bruto) -> Decimal|None`: aceita `3`, `3,000`, `3 UN`, `3.000,00`.
2. `app/persistencia.py`:
   - `abrir_db(caminho)`: schema SQLite exatamente com as tabelas/chaves do doc 02 secao 3.1
     (`documentos`, `mensagens`, `pedidos`, `itens_pedido`, `fornecedores`, `templates`,
     `log_extracao`, `fila_excecoes`) e os indices UNIQUE de idempotencia. Idempotente:
     rodar de novo nao quebra.
   - `registrar_documento(conn, artefato) -> (documento_id, dedupe)`: `INSERT ... ON CONFLICT
     DO NOTHING` sobre `sha256_conteudo`; devolve o id existente e `dedupe=True` quando repetido.
   - `decidir(extracao) -> (status_validacao, motivos)`: implementa a secao 4 do doc 02
     (rejeicao automatica, reconciliacao aritmetica de itens com as tolerancias congeladas,
     juizo de qualidade de campo e os limiares de confianca 0.90 / 0.80 / 0.60).
   - `gravar_extracao(conn, extracao) -> pedido_id`: dedupe pela `Extracao.chave_dedupe()`
     na ordem de precedencia. Fingerprint igual com valor diferente -> excecao
     `MOTIVO_CONFLITO_VALOR`, sem sobrescrever.
   - `escrever_ledger(conn, caminho_xlsx, caminho_csv) -> int`: grava `openpyxl` + csv com
     as 20 colunas de `COLUNAS_PLANILHA` na ordem exata, **uma linha por pedido_id**.
     Se `row_id_planilha` existe, atualiza a linha; senao faz append e grava o row_id.
     `valor_total` e a string BR via `contratos.formatar_brl`; `valor_total_centavos` e o int.
   - `registrar_auditoria(caminho_jsonl, registro)` e `registrar_excecao(conn, extracao, motivo, detalhe)`.
3. Nao escreva na planilha nada que nao esteja `validado` por `decidir()`.

## Constraints
- Python 3.12 do venv (`uv pip install --python .venv/Scripts/python.exe <pacote>` se faltar;
  se instalar pacote novo, ele tambem entra em `requirements.txt` - mas esse arquivo e do
  preguica: avise-o, nao edite voce mesmo).
- Dinheiro **nunca** em float. Data sempre ISO. Campo ausente sempre `None`.
- NAO edite arquivos de outro dono (tabela da secao 3 do contrato).
- **NAO rode nenhum comando `git`.** O PO commita.
- Nada de rede, chave, servico pago.
- A planilha e destino, nunca fonte da verdade: a fonte e `pedidos`/`itens_pedido`.

## Ownership
Somente `app/normaliza.py` e `app/persistencia.py`. Leitura livre do repositorio.

## Observable acceptance
- Um script curto de verificacao que voce mesmo roda provando: (a) CNPJ valido passa e
  CNPJ com DV torto e rejeitado; (b) `1.234,56` -> 123456; (c) registrar o mesmo artefato
  duas vezes devolve `dedupe=True` na segunda; (d) `escrever_ledger` chamado duas vezes
  nao duplica linha. Cole a saida real no `worker_done`.
- Declare no `worker_done` os caminhos dos seus dois arquivos.
