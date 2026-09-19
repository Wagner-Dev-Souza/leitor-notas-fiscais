# TASK F1c - Correcao: campo `tem_camada_texto` mente no caminho de OCR

## Target
`app/ingress.py`, funcao `ocr_pdf()` (seu arquivo).

## Origem
Observacao 3 do relatorio de QA `tests/RELATORIO-F5.md` (ira), confirmada pelo PO na
trilha de auditoria.

## O defeito
No ramo 2 do `ocr_pdf()` (sidecar de OCR simulado), o `TextoExtraido` volta com
`tem_camada_texto=True`. O PDF escaneado **nao tem camada de texto** - e um PDF de imagem;
o texto veio do sidecar. O campo descreve o **PDF**, e hoje ele afirma o contrario da
verdade.

Isso nao quebra o fluxo, mas vai para a trilha de auditoria e para o resumo do produto
financeiro. Um campo que mente sobre a origem do dado e exatamente o tipo de coisa que nao
pode existir num sistema cujo pior modo de falha e a extracao silenciosamente errada.

## Change
1. No ramo do sidecar de OCR simulado, `tem_camada_texto=False`. O rotulo de OCR
   (`motor=ocr_simulado`, `ocr_usado=True`) continua exatamente como esta - e ele que
   identifica a origem do texto.
2. Contrato emendado no mesmo sentido (secao 4.3): o campo descreve o PDF, nao a origem do
   texto. Leia antes de mexer.
3. Verifique se `tem_camada_texto` e usado em algum outro ponto do seu codigo (decisao,
   confianca, log) e ajuste o que dependia do valor errado.
4. Nao mude mais nada: a extracao do escaneado esta correta (o PO conferiu que o CNPJ
   `49018909000166` e a chave de 44 digitos saem certos do sidecar degradado).

## Constraints
- Nao edite `app/contratos.py` (CONGELADO), `tests/**` (ira), `data/mocks/**` (preguica),
  `app/persistencia.py`/`app/normaliza.py` (gula).
- **Nao rode nenhum comando `git`** - o PO versiona.
- Nada de rede, nada de servico pago.

## Ownership
Somente `app/ingress.py`.

## Observable acceptance
- Cole no `worker_done` a saida real de um trecho que mostre o `TextoExtraido` do arquivo
  `data/mocks/pdf/FORN-BETA_nf_2003_escaneada.pdf` com `tem_camada_texto=False`,
  `motor='ocr_simulado'` e `tem(texto) > 0`.
- Cole tambem `.venv/Scripts/python.exe -m pytest -q tests/test_ponta_a_ponta.py` (tem de
  seguir verde) e a contagem de linhas da planilha (tem de seguir 7).
