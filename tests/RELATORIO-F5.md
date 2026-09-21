# F5 - Relatorio de testes, casos adversariais e evidencia

- Frente: **F5 (qualidade)** - dono: **ira** (QA / pentester / code review)
- Worktree: `<worktree>`
- Escopo escrito: somente `tests/**` (contrato secao 3). Nenhum arquivo de outro dono foi editado.
- Data da rodada de evidencia: 2026-09-19 13:05-13:06 (horario de Brasilia)
- Nenhum comando `git` foi executado (o PO versiona).

## 1. Evidencia (saida real, sem retoque)

Comando (o mesmo da secao 8 do contrato):

```
.venv/Scripts/python.exe -m pytest -v
```

Resultado real:

```
rootdir: <worktree>
collected 284 items
======================= 4 failed, 280 passed in 12.75s ========================
```

Saida completa e crua: `tests/evidencia/pytest-f5.txt` (386 linhas).

| Arquivo | Casos | Falhas |
|---|---|---|
| `tests/test_extracao.py` | 198 | 4 |
| `tests/test_normalizacao.py` | 57 | 0 |
| `tests/test_adversarial.py` | 15 | 0 |
| `tests/test_idempotencia.py` | 8 | 0 |
| `tests/test_ponta_a_ponta.py` | 6 | 0 |
| **Total** | **284** | **4** |

As 4 falhas nao sao ruido nem teste mal escrito: sao **3 defeitos reais** (um deles
aparece em duas assercoes porque contamina nome do emitente e descricao de item).
Nenhuma assercao foi afrouxada, nenhum caso foi removido, nada foi marcado `xfail`.

## 2. Defeitos encontrados (reportados, nao consertados)

Regra do contrato: quem encontra nao conserta codigo alheio. Os tres itens abaixo
permanecem **abertos** e pendem de decisao dos donos.

### D1 - `manifest.json` da copia B4 tem chave de acesso inventada

- **Dono do arquivo:** F3 - dados sinteticos (`preguica`), `data/mocks/manifest.json`
  (a copia em si esta correta; o `esperado` dela e que esta errado).
- **Onde falha:** `tests/test_extracao.py::test_cnpj_e_chave_contra_manifest[pdf/FORN-ALFA_nf_1001_copia.pdf]`
- **Evidencia:**
  - `sha256(FORN-ALFA_nf_1001.pdf) == sha256(FORN-ALFA_nf_1001_copia.pdf)` =
    `2a84297a0a9a7a2a891a08a352c22c235bc9d37369893fc18773d3c283389ad9`;
    bytes identicos (comparacao direta) e texto extraido identico.
  - O proprio manifest diz: "Copia IDENTICA em bytes de FORN-ALFA_nf_1001.pdf (mesmo
    sha256)".
  - Mas o `esperado.chave_acesso_nf` da copia e `...10000010011748910120` enquanto o do
    original (e o que esta impresso no PDF, unico possivel) e `...10000010011968201250`.
  - `pytest`: `assert '...0011968201250' == '...0011748910120'`.
- **Impacto:** o teste de referencia compara a extracao contra um valor que o documento
  nao contem. Um PDF identico em bytes nao pode ter duas chaves de acesso. Qualquer
  consumidor do manifest (QA, relatorio, validacao do cliente) le numero falso.
- **Acao pedida a F3:** corrigir `esperado.chave_acesso_nf` da entrada da copia para
  `35260372973380000232550010000010011968201250` (ou remover o campo, ja que a copia e o
  mesmo documento). A chave atual tem DV valido - e justamente por isso que passa
  despercebida.
- **Teste que prova o lado certo:** `test_b4_copia_identica_tem_o_mesmo_conteudo_do_original`
  (passa) exige `chave(copia) == chave(original)`.

### D2 - OCR simulado do B1 degrada com F/E, fora do conjunto documentado

- **Donos:** F3 (`preguica` - `tools/gerar_mocks.py` e o sidecar
  `data/mocks/pdf/FORN-BETA_nf_2003_escaneada.pdf.ocr.txt`) e F1 (`avareza` -
  `app/extracao.py`, funcao `recuperar_texto_ocr`).
- **Onde falha:**
  - `tests/test_extracao.py::test_nome_do_emitente_contra_manifest[pdf/FORN-BETA_nf_2003_escaneada.pdf]`
  - `tests/test_extracao.py::test_itens_contra_manifest[pdf/FORN-BETA_nf_2003_escaneada.pdf]`
- **Evidencia (linhas 5 e 1 do sidecar):**
  - `BFTA SUPRIMENT05 INDU5TRIAI5 LTDA` -> extrator devolve `BFTA SUPRIMENTOS INDUSTRIAIS LTDA`;
    manifest espera `BETA SUPRIMENTOS INDUSTRIAIS LTDA`.
  - `1  CANFTA E5FEROGRAFICA AZUL ...` -> extrator devolve `CANFTA ESFEROGRAFICA AZUL`;
    manifest espera `CANETA ESFEROGRAFICA AZUL`.
  - `recuperar_texto_ocr("BFTA ...")` devolve `BFTA ...` (nao desfaz F/E);
    `recuperar_texto_ocr("CANFTA ...")` devolve `CANFTA ...`.
  - O contrato 4.3 e a nota do proprio manifest declaram a degradacao como
    **0/O, 1/l/I, 5/S, 2/Z e espacos espurios**. `F` no lugar de `E` nao esta nessa lista.
    Note que as confusoes documentadas **funcionam**: `SUPRIMENT05` -> `SUPRIMENTOS` e o
    CNPJ `49.0l8.909/0OOl-66` -> `49018909000166` saem corretos.
- **Impacto:** o manifest exige uma recuperacao (F->E) que o contrato nao define e que o
  extrator nao faz. B1 vai para `revisao_humana` de qualquer forma, mas a evidencia de
  aceite do caso B1 fica reprovada: nome do emitente e descricao de item entram na fila
  com caractere errado, sem `MOTIVO_*` que explique "OCR degradou e nao recuperei".
- **Acao pedida:** decidir de um dos dois lados - (a) F3 restringe o sidecar ao conjunto
  documentado (sem `F` por `E`), ou (b) o contrato amplia o conjunto de degradacao e F1
  passa a recupera-lo (com motivo explicito na fila). Enquanto isso os testes ficam
  vermelhos de proposito.

### D3 - codigo do motivo do caso B6 divergente entre F2 e F3

- **Donos:** F2 (`gula` - `app/persistencia.py::decidir`, ramo "itens parciais") x
  F3 (`preguica` - `manifest.json`, `esperado.motivos_esperados` do B6).
- **Onde falha:**
  `tests/test_extracao.py::test_status_e_motivos_contra_manifest[pdf/FORN-ALFA_nf_1003.pdf]`
- **Evidencia:** `decidir()` devolve `['divergencia_soma_itens']`; o manifest espera
  `['total_sem_detalhamento']`. O **status e o mesmo** nos dois lados
  (`revisao_humana`) e nos dois casos **nao ha linha na planilha** - o desacordo e o
  codigo do motivo, que e contrato (`contratos.MOTIVO_*`) e por isso precisa ser unico.
- **Impacto:** o cliente e a fila de revisao leem o codigo para triagem; dois codigos para
  o mesmo fato quebram relatorio, painel e assercao de aceite. B6 e "item sem valor
  unitario" (`MOTIVO_TOTAL_SEM_DETALHAMENTO`), nao "soma divergente" - a soma nem pode ser
  calculada.
- **Acao pedida:** o PO decide quem corrige (o texto do contrato define
  `total_sem_detalhamento` para total sem detalhamento de itens). Depois o teste fica verde
  sozinho.

## 3. Observacoes (nao contratuais - nao reprovam a suite)

1. **Artefato nao previsto no layout congelado:** `app/pipeline.py` passou a escrever
   tambem `data/out/auditoria_rodada_<AAAAMMDD-HHMMSS>.jsonl`. A secao 4.1 do contrato
   lista apenas `auditoria.jsonl`. O arquivo extra nao quebra nada e o `rodada_id` permite
   recortar a rodada na propria trilha cumulativa; fica registrado como desvio de layout
   para o PO decidir se incorpora ao contrato.
2. **`auditoria.jsonl` e append puro entre rodadas** (nunca truncada), alteracao feita por
   F1 durante esta frente. O teste do comando unico foi escrito para medir **a rodada**
   (delta de linhas) em vez de tamanho absoluto do arquivo, que cresce a cada execucao.
3. **`Artefato.tem_camada_texto` fica `True` no PDF escaneado** cujo texto veio do sidecar
   de OCR simulado (`app/ingress.py::ocr_pdf`, ramo 2). Nao e violacao: o contrato 4.3 so
   fixa `False` para o ramo 3 (sem sidecar) e o rotulo de OCR simulado
   (`motor`, `ocr_usado`, `ocr_simulado`) esta correto na trilha. Registrado porque o nome
   do campo sugere "tem camada de texto no PDF", o que nao e o caso desse arquivo.
4. **Sem segredos:** nao existe `.env` no repositorio e a varredura por padroes de
   chave/token/senha em `.py/.md/.txt/.json/.yaml` (fora de `.venv`) nao achou nada.
   Contrato 9.9 atendido nesta frente.

## 4. Casos adversariais cobertos

| Caso | Como | Resultado |
|---|---|---|
| B1 - PDF escaneado sem camada de texto | OCR simulado, rotulado | verde (com D2 aberto em nome/descricao) |
| B2 - soma dos itens diverge do total (> R$ 0,10) | `revisao_humana` + excecao com os numeros, **sem** linha na planilha | verde |
| B3 - mensagem sem valor monetario | nao inventa valor, confianca baixa, nao auto-aprova | verde |
| B4 - copia identica na inbox | deduplicada, sem linha nova, sem documento novo | verde (D1 no manifest) |
| B5 - injecao de prompt (PDF e mensagem) | valor real preservado, injecao sinalizada, nunca auto-aprovado, R$ 99.999,00 nao aparece em nenhuma saida | verde |
| B6 - item sem valor unitario | nao inventa preco, vai para revisao | verde em conteudo (D3 no codigo do motivo) |
| Documento ilegivel (PDF de imagem, sem sidecar) | `documento_ilegivel` na fila, rejeitado, planilha vazia | verde |
| CNPJ com DV invalido | `cnpj_dv_invalido`, rejeitado, sem publicacao | verde |
| Chave de acesso com DV invalido | `chave_acesso_dv_invalido`, rejeitado, sem publicacao | verde |
| Injecao construida no proprio teste (mensagem) | valor real (R$ 250,00) preservado, injecao sinalizada | verde |

Fora do escopo desta frente (nao pedidos no contrato secao 8): AD-02 (NF multipagina),
AD-12 (carga/rajada) e AD-13 (10 disparos paralelos). Ficam como recomendacao para uma
proxima rodada de performance; nao foram escritos para nao inflar a suite com teste que o
contrato nao exige.

## 5. Como reproduzir

```
cd <worktree>
.venv/Scripts/python.exe -m pytest -v
```

Os testes usam o codigo real das frentes F1/F2/F4, `data/mocks/manifest.json` como verdade
de referencia e diretorios temporarios (`tmp_path`) para o pipeline. Os artefatos
adversariais (PDF de imagem sem texto, NF com DV torto) sao criados em tempo de teste com
`pillow` e `reportlab`. Nada de rede, nada de `sleep`, nada de mock de framework.

O unico teste que toca `data/out/` e o do comando unico congelado (`--mock`), que e
exatamente o critério de aceite: o pipeline regenera a propria saida, nenhum codigo de
outro dono e editado.
