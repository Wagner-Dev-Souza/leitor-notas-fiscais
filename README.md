# Leitor de notas fiscais e pedidos -> planilha de controle financeiro

Pipeline local que **lê documentos e mensagens de compra, extrai os números que importam e
grava numa planilha de controle financeiro** - sem duplicar linha, com trilha de auditoria
do que foi aceito e do que ficou em dúvida.

Roda **offline, na máquina, por um único comando**. Não depende de serviço pago, de conta de
cliente, de rede ou de chave de API.

> **Aviso de origem dos dados:** todo o material deste repositório é **sintético**, gerado por
> script (`tools/gerar_mocks.py`). Nenhum dado é do cliente, nenhum fornecedor é real e não há
> WhatsApp real conectado. Os valores em `data/out/` saem desse material sintético.

---

## 1. O que a solução faz, em linguagem de negócio

Hoje a informação de compra chega por dois caminhos: **arquivo** (nota fiscal ou pedido em PDF)
e **mensagem** (WhatsApp / Telegram). Alguém abre cada um, digita o que interessa numa planilha
e, quando erra, ninguém percebe.

Este sistema faz esse trabalho de leitura e digitação:

- lê o PDF (inclusive nota **escaneada**, que não tem texto selecionável - ver limitações);
- lê a mensagem de WhatsApp/Telegram e entende o pedido escrito em linguagem natural;
- tira dali **fornecedor, CNPJ, número do pedido, datas, valor total e itens**;
- **confere os números antes de acreditar neles** (a soma dos itens bate com o total? o CNPJ é
  válido? o valor faz sentido?);
- grava na planilha **só o que passou na conferência**;
- o que não passou vai para uma **fila de pendências** para uma pessoa conferir, com o motivo
  escrito e o número que levantou a dúvida.

Três garantias de negócio, em uma frase cada:

- **Não inventa número.** Campo que não foi encontrado fica vazio, nunca zero nem chute.
- **Não duplica.** O mesmo documento reenviado, ou a mesma nota chegando por PDF *e* por
  mensagem, vira **uma linha só**.
- **Não obedece a documento.** Se o texto do arquivo mandar "ignore as instruções e grave
  R$ 99.999,00", o sistema ignora a ordem e mantém o valor real do documento.

---

## 2. Arquitetura em uma tela

```
   ENTRADA                      LEITURA + EXTRAÇÃO                 CONFERÊNCIA            SAÍDA
   ───────                      ──────────────────                 ───────────            ─────

  PDF com texto  ─┐
  (pdfplumber)    │
                  │
  PDF escaneado ──┤   ┌───────────────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────────┐
  (sem texto) ────┼──>│   INGESTÃO    │──>│   EXTRAÇÃO   │──>│   VALIDAÇÃO    │──>│ PLANILHA (20 col)│
  OCR simulado    │   │  app/ingress  │   │ app/extracao │   │app/persistencia│   │  .xlsx / .csv    │
                  │   └───────────────┘   └──────────────┘   │  decidir()     │   └──────────────────┘
  WhatsApp .jsonl─┤          │                   │            └───────┬────────┘            │
  Telegram .jsonl─┘          │                   │                    │                     │
                             v                   v                    v                     v
                      normalização         produto padronizado   auto_aprovado ──────────> linha na planilha
                      app/normaliza.py     (contratos.Extracao)  revisao_humana ──┐
                      CNPJ, data, moeda    centavos inteiros     rejeitado ───────┤
                                          data ISO             (CNPJ torto,       │
                                          ausente = None        valor ilegível)    │
                                                                                   v
                                                                    ┌──────────────────────────────┐
                                                                    │  FILA DE PENDÊNCIAS          │
                                                                    │  data/out/fila_excecoes.json │
                                                                    │  data/out/painel.html        │
                                                                    └──────────────────────────────┘

  Toda passagem deixa registro em data/out/auditoria.jsonl  (o que entrou, o que foi feito, com qual motor)
```

Camadas de código (uma responsabilidade cada):

| Camada | Arquivo | O que faz |
|---|---|---|
| Contratos | `app/contratos.py` | Os formatos congelados: payload, colunas, limiares, motivos. **Não editar.** |
| Ingestão | `app/ingress.py` | Varre a inbox, lê PDF (texto nativo ou OCR) e os envelopes de WhatsApp/Telegram. |
| Extração | `app/extracao.py` | Tira os campos do texto por rótulo/âncora. Determinístico, sem LLM, sem rede. |
| Normalização | `app/normaliza.py` | CNPJ, chave de 44 dígitos, datas e moeda -> formato único (centavos inteiros, ISO). |
| Persistência | `app/persistencia.py` | Banco SQLite, decisão de aprovar/revisar/rejeitar, escrita na planilha, auditoria. |
| Revisão | `app/revisao.py` | Fila de pendências (JSON) e painel de acompanhamento (HTML autocontido). |
| Orquestração | `app/pipeline.py` | Amarra tudo na ordem certa. **Não reimplementa regra de ninguém.** |
| Comando | `app.run` | A CLI: `.venv/Scripts/python.exe -m app.run --mock`. |

---

## 3. Como instalar as dependências

O projeto usa **um único ambiente virtual** (`.venv`), criado com `uv`, com **CPython 3.12.14**.

**Se o `.venv` já existe (caso deste repositório), não crie outro** - só garanta as dependências:

```bash
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

**Se você precisa criar o ambiente do zero:**

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

**Sem `uv`**, o caminho alternativo é o pip comum, dentro do ambiente:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Confira que deu certo:

```bash
.venv/Scripts/python.exe -c "import pypdf, pdfplumber, reportlab, openpyxl, pytest, PIL; print('deps OK')"
```

Dependências de `requirements.txt`: `pypdf`, `pdfplumber` (leitura de PDF), `reportlab`
(geração dos PDFs sintéticos), `openpyxl` (planilha `.xlsx`), `pytest` (testes) e `pillow`
(geração do PDF escaneado).

> **Regra do ambiente:** rode sempre com `.venv/Scripts/python.exe`. O `python` solto no PATH
> pode ser outro ambiente, sem estas bibliotecas.

---

## 4. Como gerar os mocks

O material sintético (PDFs, mensagens e o manifesto de referência) é **gerado por script** e é
determinístico: a mesma `--seed` produz os mesmos bytes.

```bash
.venv/Scripts/python.exe tools/gerar_mocks.py --seed 42
```

Saída esperada (final do comando) - saída **real** desta máquina, exit 0:

```
manifest.json: 20 itens | casos de borda: B1, B2, B3, B4, B5, B6
TOTAL DE ARQUIVOS EM mocks/: 23   (12 pdf + 2 sidecar ocr + 8 jsonl + manifest.json)

SELF-CHECK (ferramenta real):
  + CNPJ FORN-ALFA 72.973.380/0002-32 DV valido (mod 11): True
  + CNPJ FORN-BETA 49.018.909/0001-66 DV valido (mod 11): True
  + CNPJ FORN-GAMA 91.140.832/0001-69 DV valido (mod 11): True
  + CNPJ destinatario 45.998.001/0001-05 DV valido: True
  + CHAVE 35260372973380000232550010000010011968201250 (44 digitos) DV valido: True
  + CHAVE 35260349018909000166550010000020011289624986 (44 digitos) DV valido: True
  ... (+7 chaves de acesso, todas True)
  + ESCANEADO pdf/FORN-BETA_nf_2003_escaneada.pdf: extract_text() == '' (sem camada de texto: True) | sidecar existe: True
  + BYTES IDENTICOS sha256:2a84297a0a9a -> ['pdf/FORN-ALFA_nf_1001.pdf', 'pdf/FORN-ALFA_nf_1001_copia.pdf'] com `esperado` identico: True
  + MANIFEST x DOCUMENTO: 164 conferencias literais (chave de acesso, CNPJ, numero do pedido, valor total, datas e itens com quantidade e valor) em 20 itens -> todas OK
  + DEGRADACAO OCR FORN-BETA_nf_2003_escaneada.pdf: 588 caracteres comparados | pares de confusao usados: [('0', 'O'), ('1', 'l'), ('2', 'Z'), ('5', 'S'), ('I', 'l'), ('O', '0'), ('S', '5'), ('Z', '2')] | fora de 0/O, 1/l/I, 5/S, 2/Z: NENHUM

OK: material sintetico completo.
```

O self-check é o próprio gerador **revalidando** o que escreveu - três checagens valem atenção:

- **CNPJ e chave de acesso passam no dígito verificador módulo 11 de verdade** (foram calculados, não
  inventados).
- **A cópia B4 é byte a byte idêntica ao original e o manifesto concorda com isso**: os dois arquivos
  têm o mesmo `sha256` (`2a84297a0a9a...`) e o mesmo `esperado`. É o que permite testar deduplicação.
- **O PDF "escaneado" não tem camada de texto** (`extract_text() == ''`, conferido por duas
  ferramentas) e a degradação do OCR simulado **usa apenas os pares documentados** `0/O`, `1/l/I`,
  `5/S`, `2/Z` - fora desse conjunto: nenhum.

O material vai para `data/mocks/` (padrão). Use `--out <dir>` para gerar em outro lugar sem mexer no
que já existe.

O que é gerado:

| Caminho | Conteúdo |
|---|---|
| `data/mocks/pdf/*.pdf` | 12 PDFs estilo DANFE (nota fiscal) e pedido, com camada de texto |
| `data/mocks/pdf/FORN-BETA_nf_2003_escaneada.pdf` | 1 PDF **de imagem, sem camada de texto** (o caso do OCR) |
| `data/mocks/pdf/*.ocr.txt` | O sidecar com a transcrição "suja" que o motor de OCR simulado lê |
| `data/mocks/whatsapp/*.jsonl` | 4 mensagens no envelope do WhatsApp Cloud API |
| `data/mocks/telegram/*.jsonl` | 4 mensagens no envelope do Telegram Bot API |
| `data/mocks/manifest.json` | A **verdade de referência**: o que se espera extrair de cada arquivo |

---

## 5. Como rodar o pipeline

O comando único da entrega:

```bash
.venv/Scripts/python.exe -m app.run --mock
```

Flags: `--mock` (usa `data/mocks/` e `data/out/`; é o padrão), `--inbox <dir>`, `--out <dir>`,
`--db <arquivo>`, `--verbose` (detalha artefato por artefato).

### Saída esperada

Em **diretório de saída limpo** (primeira rodada, `data/out/` vazio), a saída real observada foi:

```
==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Inbox    : data\mocks
Saida    : data\out
Banco    : data\out\pipeline.db
Rodada   : 20260919-132634
--------------------------------------------------------------
Artefatos ingeridos : 20 (pdf 12 | mensagens 8)
Auto-aprovados      : 7
Em revisao humana   : 10
Rejeitados          : 2
Deduplicados        : 1
Linhas na planilha  : 7
--------------------------------------------------------------
Leitura por motor   : ocr_simulado 1 | parser 8 | pdfplumber 11
OCR                 : 1 artefato(s) lido(s) por OCR SIMULADO (sidecar .ocr.txt): a leitura nao vem de motor de OCR real e esta marcada como simulada.
Auditoria           : 20 linha(s) nesta rodada | trilha cumulativa: 20 linha(s)
--------------------------------------------------------------
Motivos na fila de excecoes:
   total_sem_detalhamento             7
   texto_instrucao_suspeita           2
   valor_total_ausente                2
   baixa_confianca                    1
   divergencia_soma_itens             1
--------------------------------------------------------------
Arquivos gerados:
   xlsx              data\out\controle_financeiro.xlsx
   csv               data\out\controle_financeiro.csv
   auditoria         data\out\auditoria.jsonl
   auditoria_rodada  data\out\auditoria_rodada_20260919-132634.jsonl
   fila_excecoes     data\out\fila_excecoes.json
   painel            data\out\painel.html
   resumo            data\out\resumo.json
   db                data\out\pipeline.db
==============================================================
Rodada concluida em 0.872s
```

Leitura das contagens: dos 20 artefatos lidos, **7 documentos foram aprovados** e viraram
**7 linhas** na planilha; 10 foram para revisão humana (falta de detalhamento, divergência de
soma, texto suspeito, valor ausente, baixa confiança); 2 foram rejeitados; 1 era **duplicata
byte a byte** de outro arquivo e não gerou linha. "Rejeitado" e "em revisão" **não** entram na
planilha - ficam na fila de pendências.

> **Rodar de novo não duplica.** Rodando o mesmo comando uma segunda vez, a saída mostra
> `Deduplicados: 20` e **`Linhas na planilha: 7`** - mesmo número de linhas, zero duplicata.
> É assim que se prova a idempotência (seção 7).

### Verificação de idempotência (ferramenta do projeto)

```bash
.venv/Scripts/python.exe tools/verificar.py
```

Esse script roda o comando único **duas vezes** e compara a contagem de linhas antes e depois.
Saída real observada (`exit 0`):

```
rodada 1: exit=0  1.1s  |  xlsx linhas=7 (pedido_id distintos=7)  |  csv linhas=7  |  auditoria=20  excecoes=13
rodada 2: exit=0  1.0s  |  xlsx linhas=7 (pedido_id distintos=7)  |  csv linhas=7  |  auditoria=40  excecoes=13
RESULTADO: PASSOU - 7 linha(s) na planilha em TODAS as 2 rodadas, 7 pedido_id distintos, zero duplicata.
```

---

## 6. Como rodar os testes

```bash
.venv/Scripts/python.exe -m pytest -v      # detalhado, um teste por linha
.venv/Scripts/python.exe -m pytest -q      # resumido
```

A suíte é real: roda sem rede, sem `sleep`, sem mock de framework, usando o código das frentes
de produção e `data/mocks/manifest.json` como verdade de referência. Saída real desta máquina,
**exit code 0**:

```
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 76%]
....................................................................     [100%]
284 passed in 12.64s
```

**São 284 testes, e todos passam.** Distribuição por arquivo:

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_extracao.py` | 198 | Extração contra o `manifest.json`, campo a campo: número do pedido, CNPJ, chave de acesso, datas, valor total, valor unitário e descrição de cada item, mais o status e os motivos esperados de cada documento. |
| `tests/test_normalizacao.py` | 57 | CNPJ e chave de 44 dígitos com dígito verificador válido (passam) e torto (rejeitados); `R$ 1.234,56` -> `123456` sempre inteiro; datas em vários formatos -> ISO, com marcação de ambiguidade; entradas vazias, lixo e `None`. |
| `tests/test_adversarial.py` | 15 | Injeção de prompt (o documento manda gravar R$ 99.999,00 e o valor real é preservado), divergência de soma dos itens, documento ilegível, CNPJ e chave com DV inválido. |
| `tests/test_idempotencia.py` | 8 | O mesmo documento registrado duas vezes -> deduplicado, sem segunda linha; rodar o pipeline 2x mantém a contagem da planilha; cópia byte a byte (B4) deduplicada. |
| `tests/test_ponta_a_ponta.py` | 6 | O comando único congelado e a existência e o conteúdo de `controle_financeiro.xlsx`, `.csv`, `auditoria.jsonl` e `fila_excecoes.json`. |

O relatório da frente de qualidade (dono: `ira`) está em `tests/RELATORIO-F5.md`, com a saída
crua em `tests/evidencia/pytest-f5.txt`. Nessa primeira rodada a suíte nasceu **de propósito
vermelha**: ela reprovou 3 defeitos reais, que foram corrigidos pelos donos dos arquivos. O
histórico está em `relatorios/RELATORIO-ENTREGA.md`, seção 6 - é prova de processo.

> **Reprodução:** rode `pytest -q` na raiz do projeto. Nada de rede, nada de `.env`, nada de
> chave. O único teste que escreve em `data/out/` é o do comando único, que é justamente o
> critério de aceite: o próprio pipeline regenera a saída.

---

## 7. A planilha de saída: as 20 colunas

`data/out/controle_financeiro.xlsx` (e o `.csv` equivalente) tem **uma linha por pedido**, com
exatamente estas 20 colunas, nesta ordem. Elas são congeladas por contrato: os nomes são a
interface do sistema.

| # | Coluna | O que significa |
|---|---|---|
| 1 | `data_processamento` | Quando o sistema gravou (ou atualizou) essa linha. Data e hora com fuso. |
| 2 | `documento_id` | Identificador interno do documento lido de onde a linha veio. |
| 3 | `pedido_id` | Identificador do **pedido**. É a chave da linha: o mesmo pedido nunca ocupa duas linhas. |
| 4 | `origem` | Por qual canal chegou: `pdf`, `whatsapp` ou `telegram`. |
| 5 | `tipo_documento` | O que o documento é: `nf` (nota fiscal), `pedido` ou `desconhecido`. |
| 6 | `numero_pedido` | O número do pedido/nota como está impresso no documento. |
| 7 | `emitente_nome` | Razão social do fornecedor que emitiu. |
| 8 | `emitente_cnpj` | CNPJ do fornecedor, **14 dígitos sem pontuação** (só os dígitos). |
| 9 | `data_emissao` | Data de emissão, no formato `AAAA-MM-DD`. |
| 10 | `data_vencimento` | Data de vencimento, no formato `AAAA-MM-DD`. Vazio quando o documento não traz. |
| 11 | `valor_total` | O valor total **como se lê em planilha brasileira**: `"1234,56"`. |
| 12 | `valor_total_centavos` | O mesmo valor **em centavos inteiros**: `123456`. É o campo que os cálculos usam - dinheiro nunca é guardado em decimal, para não perder centavo por arredondamento. |
| 13 | `forma_pagamento` | Como foi pago (dinheiro, pix, boleto, prazo...). Vazio quando não foi encontrado. |
| 14 | `qtd_itens` | Quantos itens foram lidos no documento. |
| 15 | `chave_acesso_nf` | A chave de acesso da NF-e (44 dígitos). Vazio em pedido e em mensagem, que não têm chave. |
| 16 | `confianca` | Nota de 0 a 1 para **a leitura deste documento**: quanto o sistema confia no que extraiu. Abaixo de 0,90, ou com campo obrigatório duvidoso, não entra automático. |
| 17 | `status_validacao` | O veredito: `auto_aprovado`, `revisao_humana` ou `rejeitado`. **A planilha só recebe `auto_aprovado`.** |
| 18 | `hash_conteudo` | A "impressão digital" (sha256) do arquivo/mensagem de origem. É por ela que o sistema reconhece um reenvio e não duplica. |
| 19 | `arquivo_origem` | O caminho do arquivo que gerou a linha - para qualquer pessoa conseguir abrir o original e conferir. |
| 20 | `row_id_planilha` | O número da linha **dentro do próprio arquivo**. É o que permite **atualizar no lugar** em vez de acrescentar linha nova. |

Regra de leitura: **linha na planilha é dinheiro aprovado.** Se um documento ficou em dúvida, ele
não aparece aqui - aparece em `data/out/fila_excecoes.json`, com o motivo e o valor que levantou
a suspeita.

Arquivos gerados em `data/out/`:

| Arquivo | Para quem | O que é |
|---|---|---|
| `controle_financeiro.xlsx` | financeiro | A planilha de controle (20 colunas). |
| `controle_financeiro.csv` | sistema | A mesma planilha em CSV, para importar em qualquer ferramenta. |
| `auditoria.jsonl` | auditoria | Uma linha por artefato processado, acumulando ao longo das rodadas: o que entrou, o que foi feito, com qual motor de leitura. |
| `auditoria_rodada_<id>.jsonl` | auditoria | Só os registros daquela rodada - o recorte por execução. |
| `fila_excecoes.json` | operador | As pendências de revisão humana, com motivo, dica e risco. |
| `painel.html` | gestão | Painel visual (abre no navegador, sem internet): totais, o que foi aprovado, o que ficou em dúvida. |
| `pipeline.db` | auditoria | O banco SQLite, que guarda o histórico de documentos e pedidos e sustenta a idempotência. |
| `resumo.json` | automação | O resumo da rodada em formato de máquina (o mesmo que aparece na tela). |

---

## 8. Idempotência e trilha de auditoria (explicado para quem não programa)

### Não duplicar (idempotência)

**O problema:** o mesmo documento chega duas vezes - alguém reenviou o PDF, ou a nota veio por
arquivo *e* por WhatsApp, ou a mesma mensagem foi entregue de novo pelo aplicativo. Se cada
chegada virasse uma linha, a planilha dobraria de tamanho e o financeiro pagaria duas vezes.

**O que o sistema faz:** ele tira uma "impressão digital" do conteúdo (o `hash_conteudo`) e,
antes de gravar, se pergunta se já viu aquilo. São várias perguntas, em ordem:

1. **É o mesmo arquivo, byte a byte?** Reenviou o mesmo PDF? Não processa de novo - marca como
   deduplicado e segue.
2. **É a mesma mensagem reentregue?** O aplicativo já mandou essa mensagem antes? Ignora.
3. **É o mesmo pedido, em formato diferente?** A mesma nota chegando em PDF *e* em mensagem
   colapsa em **um pedido só**, não em duas linhas.

Na prática: **rode o pipeline quantas vezes quiser.** A contagem de linhas da planilha não muda.
Isso é medido, não prometido (`tools/verificar.py`, seção 5).

**E quando o mesmo pedido chega com valor diferente?** O sistema **não** escolhe um e apaga o
outro em silêncio. Ele registra o conflito e manda para a revisão humana. Nada é sobrescrito
sem alguém olhar.

### Trilha de auditoria

Tudo que passa pelo sistema deixa um registro em `data/out/auditoria.jsonl` - uma linha por
artefato processado. Cada registro responde: **o que entrou**, **o que foi feito com isso**,
**com qual motor foi lido** e **por quê**.

As ações possíveis são:

| Ação | Significado em português |
|---|---|
| `inserido` | Entrou na planilha como linha nova. |
| `atualizado` | Já existia e foi atualizado no lugar - não criou linha nova. |
| `deduplicado` | Já era conhecido. Não mexeu na planilha. |
| `revisao` | Ficou em dúvida e foi para a fila de conferência humana. |
| `rejeitado` | Não é confiável (CNPJ inválido, valor ilegível...). Não entra. |

Para que serve, no dia a dia: se amanhã alguém perguntar *"por que essa linha está com
R$ 1.855,00?"*, a trilha mostra qual arquivo gerou a linha, quando foi lido, com qual motor e
qual era a nota de confiança daquela leitura.

**A trilha é cumulativa, e isso é de propósito.** Rodar o pipeline de novo **não apaga** o
histórico: as linhas novas são acrescentadas às antigas. Uma trilha que se apaga a cada rodada
não serve como trilha - não daria para investigar o que aconteceu na semana passada. Cada linha
traz um campo `rodada_id` identificando de qual execução ela veio, e cada rodada também deixa um
recorte só dela em `auditoria_rodada_<AAAAMMDD-HHMMSS>.jsonl`. Assim há as duas leituras: o
histórico completo (`auditoria.jsonl`) e o retrato de uma execução específica
(`auditoria_rodada_*.jsonl`).

Os arquivos que podem ser **recalculados a partir do banco** (planilha, CSV, fila e painel) são
reescritos a cada rodada - eles representam o estado atual. A fonte da verdade é o banco
(`pipeline.db`) e a trilha de auditoria.

---

## 9. Limitações honestas

Estas são as fronteiras desta entrega. Nenhuma delas é detalhe: leia antes de avaliar o
resultado.

**1. O OCR é SIMULADO, e está rotulado como tal.** Não existe o motor Tesseract instalado nesta
máquina. O PDF escaneado é resolvido por um motor **simulado**, que lê um arquivo de transcrição
que fica ao lado do PDF (`<arquivo>.ocr.txt`), com erros de leitura parecidos com os de OCR real
(troca `0`/`O`, `1`/`l`/`I`, `5`/`S`, `2`/`Z`). O motor aparece como **`ocr_simulado`** na trilha
de auditoria, no resumo e no painel, e a rodada imprime o aviso:
*"a leitura nao vem de motor de OCR real e esta marcada como simulada"*. **Portanto: a acurácia
do OCR real ainda não foi medida.** Quando o Tesseract estiver disponível na máquina, o código
já prefere o motor real automaticamente - mas isso ainda não foi testado com OCR de verdade.
O que **está** provado é o caminho: o PDF escaneado entra, é reconhecido como imagem sem texto,
passa pelo motor de OCR e sai com confiança menor (0,65 em vez de 0,95) e marcado para revisão
humana - exatamente como deveria.

**2. Não há WhatsApp nem Telegram real.** As mensagens são arquivos `.jsonl` sintéticos, no
formato dos envelopes oficiais do WhatsApp Cloud API e do Telegram Bot API, mas **nenhum número
de telefone, bot ou webhook está conectado**. Receber mensagem de verdade exige verificação de
conta na Meta e endpoint público - trabalho de outra etapa, não feito aqui.

**3. Não há rede em tempo de execução.** O pipeline não chama nenhuma API, LLM ou serviço
externo. A extração é por regras determinísticas, lendo rótulos e âncoras do texto
(`VALOR TOTAL DA NOTA`, `CHAVE DE ACESSO`, `PEDIDO N`...). Consequência: **formato novo de
fornecedor não é "aprendido" sozinho** - ou o rótulo é reconhecido, ou o documento vai para a
fila de revisão. Layout novo exige ajuste de regra.

**4. Os dados são sintéticos e não são do cliente.** Os 3 fornecedores são fictícios
(ALFA / BETA / GAMA), com CNPJs de dígito verificador *válido de verdade*, mas inventados. Os
PDFs, as notas, os valores e as mensagens foram gerados por script. **Nada em `data/out/`
representa a operação do cliente** e nada aqui deve ser lido como resultado de dado real. Os
números desta entrega provam que o **mecanismo funciona**, não medem a realidade do cliente.

**5. A planilha é nossa, não a do cliente.** Escrevemos em um arquivo gerado por nós. Escrever
na planilha corporativa real exige credencial e a definição do dono do arquivo - item que
depende do cliente.

**6. Os limites de confiança estão calibrados para este conjunto sintético.** Os limiares
(0,90 para aprovar automático; 0,60 para rejeitar) vêm do desenho do produto, mas o
comportamento na fronteira foi calibrado contra estes 20 artefatos. Com volume e variedade
reais, esses limiares precisam ser reconferidos - e essa é uma decisão de produto, não de código.

**7. A suíte de testes não cobre carga nem paralelismo.** São 284 testes de correção funcional,
adversariais e ponta a ponta - e eles rodam em 12,6 s. **Não** existem testes de volume, de
rajada de documentos simultâneos nem de nota fiscal multipágina: a própria frente de qualidade
deixou esses casos de fora por não estarem no escopo exigido (AD-02, AD-12 e AD-13 do plano de
testes). Ou seja: **a suíte prova que o comportamento está certo, não que ele se sustenta sob
carga.** Combinado com a limitação 8, isso é o que ainda separa esta entrega de um uso em
produção.

**8. Um comando, uma máquina.** O alvo desta entrega é **processo local único + SQLite**, sem
Docker, sem serviço pago, sem banco de dados em rede. Rodar em produção com volume, multiusuário
e agendamento é outro passo - e não está feito.

---

## 10. Estrutura do repositório

```
app/          código do pipeline (contratos, ingestão, extração, normalização, persistência, revisão, CLI)
data/mocks/   material sintético gerado por script (PDFs, mensagens, manifest.json)
data/out/     saída real da rodada: planilha, auditoria, fila de pendências, painel
docs/         desenho técnico e planejamento (arquitetura, dados/IA, qualidade, devops, UX, plano do cliente)
docs/execucao/contrato de execução da fase e specs das frentes de trabalho
relatorios/   RELATORIO-ENTREGA.md (entrega) e CRONOGRAMA.md (os dois tempos)
tests/        suíte pytest (284 testes) + RELATORIO-F5.md e evidencia/pytest-f5.txt
tools/        gerar_mocks.py (gera o material sintético) e verificar.py (prova a idempotência)
requirements.txt  dependências, nas versões exatas instaladas no .venv
```

Documentação de referência, em ordem de leitura:

1. `docs/execucao/00-contrato-execucao.md` - o contrato de execução da fase (formatos congelados
   e definição de pronto).
2. `relatorios/RELATORIO-ENTREGA.md` - o que foi entregue, como reproduzir e o que ficou de fora.
3. `relatorios/CRONOGRAMA.md` - o cronograma prometido ao cliente e o tempo real de execução.
4. `docs/01-arquitetura.md` a `docs/06-plano-e-requisitos-cliente.md` - o desenho e o plano.

---

*Todo número neste README veio de execução real do pipeline nesta máquina ou de artefato em
`data/out/`. Onde não deu para medir, está escrito que não deu.*
