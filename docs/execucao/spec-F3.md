# TASK F3 - Dados sinteticos: gerador de PDFs e mensagens mock + verificador

## Target
Worktree `<worktree>`.
Arquivos: `tools/gerar_mocks.py`, `tools/verificar.py`, `requirements.txt`, `.gitignore`.

## Contexto obrigatorio (leia ANTES de escrever codigo)
1. `docs/execucao/00-contrato-execucao.md` secoes 4.1 a 4.4 e secao 7 - formatos e casos
   de borda. Integra.
2. `app/contratos.py` - CONGELADO pelo PO. Nao edite.

## Change
1. `tools/gerar_mocks.py` - gera TODO o material sintetico. O cliente nao envia nada;
   este script e a fonte do material. Requisitos:
   - **3 fornecedores** distintos (`FORN-ALFA`, `FORN-BETA`, `FORN-GAMA`) com razao social,
     nome fantasia e **CNPJ com digito verificador valido de verdade** (calcule mod 11 -
     nao invente numero que nao passa na propria validacao).
   - PDFs com camada de texto (`reportlab`), estilo DANFE modelo 55 para nota fiscal:
     bloco de emitente (razao social + CNPJ), numero da NF/numero do pedido, `CHAVE DE ACESSO`
     de 44 digitos **com DV valido**, data de emissao, destinatario, tabela de itens
     (descricao, quantidade, unidade, valor unitario, valor total) e `VALOR TOTAL DA NOTA`.
     Pedidos em PDF com numero do pedido, fornecedor, data, itens e `TOTAL`.
     Use os rotulos de ancora exatos da secao 4.2 do contrato.
   - **1 PDF escaneado**: PDF de imagem **sem camada de texto** (via PIL), mais o sidecar
     `<arquivo>.ocr.txt` com a transcricao degradada (confusao `0/O`, `1/l/I`, `5/S`, `2/Z`
     e espacos espurios). Verifique com `PdfReader(...).extract_text() == ""`.
   - Mensagens `.jsonl` com envelope real do WhatsApp Cloud API e do Telegram Bot API,
     exatamente nos moldes da secao 4.4. Variar redacao entre as mensagens.
   - `data/mocks/manifest.json` - **verdade de referencia** no formato da secao 7:
     por arquivo, `canal`, `tipo_documento`, `caso_borda` e `esperado` (o que a extracao
     deve produzir: numero_pedido, cnps, datas ISO, valor_total_centavos, itens).
     Os testes do QA comparam a extracao real contra este manifesto: **ele tem de estar
     correto**, senao voce contamina a suite inteira.
   - Casos de borda obrigatorios B1..B6 da secao 7, cada um marcado em `caso_borda`.
   - `--seed` para reprodutibilidade (mesma semente -> mesmos arquivos).
2. `tools/verificar.py` - roda o comando unico **duas vezes** e prova idempotencia:
   conta linhas da planilha antes e depois e exige contagem identica. Sai com codigo
   diferente de zero se duplicar. Imprime o resultado de forma legivel.
3. `requirements.txt` - fixe as versoes realmente instaladas:
   `pypdf`, `pdfplumber`, `reportlab`, `openpyxl`, `pytest`, `pillow`. Comente a linha de
   OCR real como opcional.
4. `.gitignore` - acrescente `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
   **NAO** ignore `data/mocks/` nem `data/out/` (sao material e evidencia da entrega).

## Constraints
- Python 3.12 do venv. Nao crie outro venv.
- Nada de rede em tempo de execucao; nada de servico pago, numero real de WhatsApp ou chave.
  Pode consultar formato de DANFE/WhatsApp/Telegram na internet durante o desenvolvimento,
  se precisar, mas o gerador nao acessa rede ao rodar.
- NAO edite arquivos de outro dono (tabela da secao 3 do contrato).
- **NAO rode nenhum comando `git`.** O PO commita.
- Determinismo: com a mesma `--seed`, rodar duas vezes produz os mesmos bytes.

## Ownership
Somente `tools/gerar_mocks.py`, `tools/verificar.py`, `requirements.txt`, `.gitignore`.

## Observable acceptance
- `.venv/Scripts/python.exe tools/gerar_mocks.py --seed 42` cria os PDFs, as mensagens e o
  `manifest.json` em `data/mocks/`.
- Cole no `worker_done` a saida real do gerador (lista e contagem de arquivos) e a prova de
  que o PDF escaneado **nao** tem camada de texto.
- Declare a contagem de fornecedores e quais casos de borda B1..B6 foram gerados.
