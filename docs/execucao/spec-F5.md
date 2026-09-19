# TASK F5 - Testes automatizados, casos adversariais e evidencia

## Target
Worktree `<local>`. Diretorio `tests/`.

## Pre-requisito
As frentes F1 (ingestao/extracao/pipeline/CLI), F2 (normalizacao/persistencia),
F3 (dados sinteticos) e F4 (revisao) ja entregaram seus arquivos. Leia o codigo que
existe antes de escrever teste. Se um modulo faltar, **diga isso** e teste o que existe;
nao invente sucesso.

## Contexto obrigatorio
1. `docs/execucao/00-contrato-execucao.md` - contrato, formatos e secao 8 (suite minima).
2. `app/contratos.py` - CONGELADO. Nao edite.
3. `data/mocks/manifest.json` - verdade de referencia para as assercoes.
4. `docs/03-qualidade-riscos.md` - seu proprio plano de testes e casos adversariais.

## Change
Suite `pytest` real (sem mock de framework), com `tests/conftest.py` e no minimo:
- `tests/test_normalizacao.py`: CNPJ e chave com DV valido passam; DV torto e rejeitado;
  `1.234,56` -> `123456`; datas `dd/mm/aaaa`, `dd/mm/aa`, ISO e por extenso -> ISO;
  dia <= 12 marca `ambigua`. Casos limite: vazio, lixo, `None`.
- `tests/test_extracao.py`: extrai numero do pedido, CNPJ, datas, valor total e itens de
  PDF nativo e de mensagem, e **compara contra o `manifest.json`**.
- `tests/test_idempotencia.py`: registrar o mesmo documento duas vezes devolve `dedupe=True`
  e **nao** cria segunda linha; rodar o pipeline 2x mantem a contagem de linhas da planilha;
  duplicata B4 deduplicada.
- `tests/test_adversarial.py`: **injecao de prompt** (B5 - texto do documento manda ignorar
  instrucoes e gravar valor 99999; exija que o valor real seja preservado e que a injecao
  seja sinalizada) e **divergencia de valor** (B2 - soma dos itens != total em mais de
  R$ 0,10; exija `revisao_humana` e **ausencia** de linha na planilha). Inclua documento
  ilegivel e CNPJ com DV invalido.
- `tests/test_ponta_a_ponta.py`: roda o comando unico e verifica a existencia e o conteudo
  de `data/out/controle_financeiro.xlsx`, `.csv`, `auditoria.jsonl` e `fila_excecoes.json`.

## Constraints
- Python 3.12 do venv. `pytest` ja instalado.
- Teste que falha e resultado valido: **reporte a falha**, nao afrouxe a assercao para
  ficar verde, nao marque `xfail` em cima de bug real e nao remova caso. Se o defeito
  for de outro dono, registre no `worker_done` e mande mensagem ao dono.
- Nada de rede nos testes. Nada de `sleep` longo.
- NAO edite arquivos de outro dono (tabela da secao 3 do contrato). Corrigir codigo de
  outro dono e do dono; voce reporta.
- **NAO rode nenhum comando `git`.** O PO commita.

## Ownership
Somente `tests/**`. Leitura livre do repositorio.

## Observable acceptance
- `.venv/Scripts/python.exe -m pytest -v` roda e a saida **real e completa** e colada no
  seu `worker_done`, com a contagem de aprovados/falhados.
- Declare a contagem de testes e quais casos adversariais cobriu.
- Se algum teste falhar por defeito de outra frente, relate o defeito, o teste e a
  evidencia - nao conserte por conta propria e nao esconda.
