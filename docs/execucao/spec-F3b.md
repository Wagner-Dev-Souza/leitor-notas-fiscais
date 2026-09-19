# TASK F3b - Correcao: manifesto B4 com chave inventada + degradacao de OCR fora do contrato

## Target
`tools/gerar_mocks.py` e o `data/mocks/manifest.json` que ele gera. Seus arquivos.

## Origem
Defeitos D1 e D2 do relatorio de QA `tests/RELATORIO-F5.md` (ira), reproduzidos pelo PO
com `.venv/Scripts/python.exe -m pytest -q` -> `4 failed, 280 passed`.

## D1 - `manifest.json` da copia B4 tem chave de acesso que o documento nao contem
- `data/mocks/pdf/FORN-ALFA_nf_1001_copia.pdf` e copia **identica em bytes** do original
  (`sha256` igual, confirmado pelo PO e pelo QA).
- Mesmo assim o `esperado.chave_acesso_nf` da entrada da copia e `...11748910120`,
  enquanto o original (e o unico valor impresso no PDF) tem `...11968201250`.
- A chave atual tem DV valido - por isso passou despercebida. Mas o manifesto e a **verdade
  de referencia** dos testes: um valor que o documento nao contem contamina a suite inteira
  e engana quem ler o manifesto como fonte.
- **Corrija:** a entrada da copia passa a ter a mesma chave do original
  (`35260372973380000232550010000010011968201250`), ou o campo e removido, ja que e o mesmo
  documento. Aproveite e faca uma varredura de sanidade: todo `esperado` de PDF identico em
  bytes tem de ser identico, e toda chave/CNPJ do manifesto tem de aparecer literalmente no
  documento correspondente.

## D2 - degradacao de OCR com `F` no lugar de `E`, fora do conjunto congelado
- O sidecar `FORN-BETA_nf_2003_escaneada.pdf.ocr.txt` traz `BFTA SUPRIMENT05 INDU5TRIAI5 LTDA`
  e `CANFTA E5FEROGRAFICA AZUL`.
- O contrato (secao 4.3, emendado pelo PO) fecha o conjunto de degradacao em
  **`0/O`, `1/l/I`, `5/S`, `2/Z` e espacos espurios**. `F` por `E` nao esta na lista.
- **Decisao do PO:** o gerador **restringe** a degradacao ao conjunto congelado. Nao se
  amplia o contrato para acomodar o gerador - o extrator (F1) ja recupera corretamente
  `SUPRIMENT05` -> `SUPRIMENTOS` e o CNPJ degradado, que e o que o caso B1 precisa provar.
- Alem de corrigir o sidecar, deixe a nota do manifesto explicita listando o conjunto de
  degradacao usado, para que o desvio nao volte a acontecer sem ser notado.

## Change
1. Corrija D1 no gerador (o defeito esta no codigo que produz o manifesto, nao no arquivo
   gerado a mao) e regenere `data/mocks/` com `--seed 42`.
2. Corrija D2 no gerador: sidecar apenas com as confusoes do conjunto congelado.
3. Garanta determinismo byte a byte de novo (mesma `--seed` -> mesmos bytes).
4. Mantenha a copia B4 com bytes identicos ao original (o caso B4 depende disso).

## Constraints
- Nao edite arquivos de outro dono. `tests/**` e do ira; `app/**` das frentes 1 e 2.
- **Nao rode nenhum comando `git`** - o PO versiona.
- Nada de rede, nada de servico pago.
- Consistencia acima de conveniencia: se voce descobrir que outra entrada do manifesto
  tambem nao bate com o documento, corrija e **relate**.

## Ownership
`tools/gerar_mocks.py`, `data/mocks/**` (o material gerado).

## Observable acceptance
- Cole no `worker_done` a saida real de `tools/gerar_mocks.py --seed 42` e a prova de que
  a chave da copia agora e igual a do original.
- Cole a confirmacao de que o sidecar nao tem mais nenhuma confusao fora de `0/O`, `1/l/I`,
  `5/S`, `2/Z`.
- Rode `.venv/Scripts/python.exe -m pytest -q tests/test_extracao.py` e cole a contagem
  resultante (esperado: D1 e D2 verdes; D3 continua vermelho e **nao** e seu).
