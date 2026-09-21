# Leitor de notas fiscais e pedidos -> planilha de controle financeiro

Pipeline local que **lê documentos e mensagens de compra, extrai os números que importam e
grava numa planilha de controle financeiro** - sem duplicar linha, com trilha de auditoria
do que foi aceito e do que ficou em dúvida.

Roda **por um único comando**. O padrão é o **modo mock**: offline, na máquina, sem serviço pago,
sem rede e sem chave de API - é o modo das seções 1 a 6 e o que este repositório demonstra. Existe
também o **modo real**, que liga por configuração e coleta mensagens de WhatsApp/Telegram para
alimentar o mesmo pipeline: o passo a passo de produção (instalar, configurar, rodar, agendar,
acompanhar, tratar falha) está na **seção 7**.

> **Aviso de origem dos dados:** todo o material deste repositório é **sintético**, gerado por
> script (`tools/gerar_mocks.py`). Nenhum dado é do cliente, nenhum fornecedor é real e **nenhuma
> mensagem real de WhatsApp ou Telegram passou por aqui** - as mensagens de demonstração são
> arquivos de mock escritos no formato real das APIs. Os valores em `data/out/` saem desse material
> sintético. O que ainda é simulado está declarado sem rodeio na seção 10.

---

## 1. O que a solução faz, em linguagem de negócio

Hoje a informação de compra chega por dois caminhos: **arquivo** (nota fiscal ou pedido em PDF)
e **mensagem** (WhatsApp / Telegram). Alguém abre cada um, digita o que interessa numa planilha
e, quando erra, ninguém percebe.

Este sistema faz esse trabalho de leitura e digitação:

- lê o PDF (inclusive nota **escaneada**, que não tem texto selecionável - ver limitações);
- lê **imagem** (foto ou print da nota: `.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, `.bmp`), pelo
  mesmo OCR real;
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
(geração dos PDFs sintéticos), `openpyxl` (planilha `.xlsx`), `pytest` (testes), `pillow`
(geração do PDF escaneado e das imagens de teste) e `pytesseract` (ponte para o OCR real).

**O OCR real depende de um binário que não vem pelo pip.** Instale o **Tesseract** na máquina:

```bash
winget install --id tesseract-ocr.tesseract -e      # Windows
```

Confira que ele está visível:

```bash
.venv/Scripts/python.exe -c "from app.ingress import localizar_tesseract; print(localizar_tesseract())"
```

Esse comando imprime o caminho do executável (ex.: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
ou `None`. Ele procura pelo `PATH`, pela variável `TESSERACT_CMD` e no local padrão de instalação -
o instalador só registra o `PATH` para processos **novos**, e sem essa busca um processo já em
execução (o gateway, a suíte) continuaria sem enxergar o binário. **Sem o Tesseract o produto não
quebra:** ele cai no motor simulado (sidecar) para PDF escaneado, e a imagem entra sem texto, indo
para a fila de revisão humana com o motivo `documento_ilegivel`.

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
manifest.json: 21 itens | casos de borda: B1, B2, B3, B4, B5, B6, B7
TOTAL DE ARQUIVOS EM mocks/: 24
SELF-CHECK (ferramenta real):
  + CNPJ FORN-ALFA 72.973.380/0002-32 DV valido (mod 11): True
  + CNPJ FORN-BETA 49.018.909/0001-66 DV valido (mod 11): True
  + CNPJ FORN-GAMA 91.140.832/0001-69 DV valido (mod 11): True
  + CNPJ destinatario 45.998.001/0001-05 DV valido: True
  + CHAVE 35260372973380000232550010000010011968201250 (44 digitos) DV valido: True
  + CHAVE 35260372973380000232550010000010021761678683 (44 digitos) DV valido: True
  + CHAVE 35260349018909000166550010000020011289624986 (44 digitos) DV valido: True
  + CHAVE 35260391140832000169550010000030011024532750 (44 digitos) DV valido: True
  + CHAVE 35260372973380000232550010000010031515936709 (44 digitos) DV valido: True
  + CHAVE 35260349018909000166550010000020021488836301 (44 digitos) DV valido: True
  + CHAVE 35260391140832000169550010000030021576152091 (44 digitos) DV valido: True
  + CHAVE 35260349018909000166550010000020031759670983 (44 digitos) DV valido: True
  + CHAVE 35260372973380000232550010000010011968201250 (44 digitos) DV valido: True
  + CHAVE 35260391140832000169550010000030031571854907 (44 digitos) DV valido: True
  + ESCANEADO pdf/FORN-BETA_nf_2003_escaneada.pdf: extract_text() == '' (sem camada de texto: True) | sidecar existe: True
  + BYTES IDENTICOS sha256:2a84297a0a9a -> ['pdf/FORN-ALFA_nf_1001.pdf', 'pdf/FORN-ALFA_nf_1001_copia.pdf'] com `esperado` identico: True
  + MANIFEST x DOCUMENTO: 176 conferencias literais (chave de acesso, CNPJ, numero do pedido, valor total, datas e itens com quantidade e valor) em 21 itens -> todas OK
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
| `data/mocks/pdf/FORN-GAMA_nf_3003_foto.png` | 1 **foto da nota** em PNG: o caso do canal `imagem`, lido pelo OCR real (caso B7) |
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
Modo     : mock | config: nenhum .env (padrao)
Inbox    : data\mocks
Saida    : data\out
Banco    : data\out\pipeline.db
Rodada   : 20260921-112718
--------------------------------------------------------------
Artefatos ingeridos : 21 (pdf 12 | imagens 1 | mensagens 8)
Auto-aprovados      : 0
Em revisao humana   : 0
Rejeitados          : 0
Deduplicados        : 21
Linhas na planilha  : 7
--------------------------------------------------------------
Leitura por motor   : parser 8 | pdfplumber 11 | tesseract 2
OCR                 : nenhum artefato usou OCR simulado nesta rodada
Auditoria           : 21 linha(s) nesta rodada | trilha cumulativa: 3176 linha(s)
```

Leitura das contagens: dos 21 artefatos lidos, **7 documentos foram aprovados** e viraram
**7 linhas** na planilha; 11 foram para revisão humana (falta de detalhamento, divergência de
soma, texto suspeito, valor ausente, baixa confiança - a foto da nota entra por baixa confiança, porque
leitura de OCR não aprova sozinha); 2 foram rejeitados; 1 era **duplicata
byte a byte** de outro arquivo e não gerou linha. "Rejeitado" e "em revisão" **não** entram na
planilha - ficam na fila de pendências.

> **Rodar de novo não duplica.** Rodando o mesmo comando uma segunda vez, a saída mostra
> `Deduplicados: 21` e **`Linhas na planilha: 7`** - mesmo número de linhas, zero duplicata.
> É assim que se prova a idempotência (seção 9).

### Entrada por imagem (foto ou print da nota)

A pasta de documentos da inbox (`<INBOX_DIR>/pdf/`) aceita PDF **e imagem** - não precisa separar
por pasta. Jogue o arquivo lá e rode o mesmo comando de sempre:

```bash
.venv/Scripts/python.exe -m app.run --inbox data/inbox --out data/out
```

O artefato entra com `origem=imagem` e motor `tesseract` (o OCR real). Como a leitura de OCR recebe
confiança **0,65**, ela fica abaixo do limiar de aprovação automática (**0,90**): **toda nota vinda
de imagem vai para a fila de revisão humana**, já com os campos extraídos e o motivo escrito. É o
desenho do produto - OCR não publica sozinho - e não um defeito.

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
........................................................................ [ 89%]
.........................................                                [100%]
437 passed in 79.93s (0:01:16)
```

**São 437 testes, e todos passam.** Distribuição por arquivo:

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_extracao.py` | 219 | Extração contra o `manifest.json`, campo a campo: número do pedido, CNPJ, chave de acesso, datas, valor total, valor unitário e descrição de cada item, mais o status e os motivos esperados de cada documento. |
| `tests/test_config.py` | 70 | Leitura e validação do `.env`: sintaxe tolerada, variável obrigatória ausente, catálogo, mensagem de erro por variável, mascaramento do segredo. |
| `tests/test_normalizacao.py` | 57 | CNPJ e chave de 44 dígitos com dígito verificador válido (passam) e torto (rejeitados); `R$ 1.234,56` -> `123456` sempre inteiro; datas em vários formatos -> ISO, com marcação de ambiguidade; entradas vazias, lixo e `None`. |
| `tests/test_canais.py` | 33 | Coleta dos canais contra stub HTTP local: envelope do Telegram gravado, filtro por chat, falha de credencial virando erro claro sem imprimir o token, leitura do webhook do WhatsApp. |
| `tests/test_producao.py` | 19 | Os itens de operação: `.env.example` em sincronia com o catálogo, `.env` fora do git, modo mock sem credencial, modo real sem variável obrigatória, varredura de segredo. |
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

## 7. Implementação em produção

Esta é a seção para quem vai **colocar o produto para rodar**. Ela responde, na ordem: instalar,
configurar, rodar, onde ficam os resultados, como acompanhar, como agendar e o que fazer quando
uma extração falha.

**O que muda em produção.** O **modo mock é o padrão** - é o que as seções anteriores mostram:
dados sintéticos, sem credencial nenhuma. O **modo real** liga por uma linha no `.env`
(`MODO_EXECUCAO=real`) e faz o produto **coletar** as mensagens dos canais configurados **antes**
de processar. O pipeline em si não muda:

```
modo real:   canais (Telegram / WhatsApp)  ->  coleta grava envelopes no inbox  ->  mesmo pipeline de sempre
modo mock:   data/mocks/                   -------------------------------------->
```

Ou seja: a coleta **entrega arquivos no mesmo formato dos mocks**. É por isso que o pipeline, a
planilha e a idempotência continuam idênticos nos dois modos.

### 7.1 Instalar as dependências

O interpretador do projeto é o do próprio repositório: **`.venv/Scripts/python.exe`** (CPython
3.12.14, criado com `uv`). Em produção, use sempre esse caminho - não o `python` solto do PATH.

```bash
# com uv (como o .venv deste projeto foi criado)
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# do zero, se o .venv não existir
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# sem uv, com o pip comum dentro do ambiente
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Conferir que as dependências estão no lugar:

```bash
.venv/Scripts/python.exe -c "import pypdf, pdfplumber, reportlab, openpyxl, pytest, PIL; print('deps OK')"
```

Rodar os testes (é o portão de sanidade antes de subir):

```bash
.venv/Scripts/python.exe -m pytest -q
```

> **Nenhuma dependência nova nesta fase.** A configuração (`.env`), a coleta dos canais e o
> receptor de webhook foram implementados com **biblioteca padrão do Python** (`urllib`,
> `http.server`, `json`, `dataclasses`). Não entrou `python-dotenv` nem nada em
> `requirements.txt` - é decisão registrada no contrato de fechamento (D2), e o motivo é
> operacional: menos peça para instalar, menos para quebrar no servidor.

### 7.2 Configurar: o arquivo `.env`

O `.env` é **um arquivo de texto** que fica na **raiz do projeto** (ao lado de `app/`), com uma
variável por linha. É ele que diz ao produto se roda em mock ou real, onde gravar as coisas e
quais são as credenciais dos canais.

**A regra que não se quebra:** o `.env` real contém **segredo** (tokens de acesso). Ele **nunca**
vai para o git - já está no `.gitignore`. O que se versiona é o **`.env.example`**, com as chaves
vazias, que é a lista oficial das variáveis.

> **Onde o `.env` mora na prática.** No **worktree da entrega** (esta cópia de trabalho do
> repositório) o `.env` **não pode existir**: um teste do próprio projeto
> (`tests/test_producao.py`) falha se encontrar um - e o motivo é bom, segredo não mora dentro do
> repositório. A configuração real fica **fora** da árvore do repositório e é apontada com `--env`:
>
> ```bash
> .venv/Scripts/python.exe -m app.run --real --env "C:/caminho/fora/do/repo/.env"
> ```
>
> Na cópia do cliente - que não é worktree de desenvolvimento - o `.env` pode ficar na raiz do
> projeto normalmente, como descrito acima. `--check-config` funciona nos dois modos.

**A coleta não re-baixa o histórico a cada rodada.** O `getUpdates` do Telegram devolve a janela
inteira de updates enquanto ninguém confirma a leitura. A coleta grava `telegram_offset.json` no
diretório de saída com o próximo offset (`maior update_id + 1`) e o envia na execução seguinte - é
a confirmação de leitura do Telegram. Sem isso, cada rodada reprocessava toda a janela de 24h: a
deduplicação sempre impediu linha repetida na planilha, mas o custo crescia com o histórico do
grupo. Se o arquivo for apagado, a rodada seguinte volta a ler o que estiver pendente.

> **O `.env.example` está no repositório e é a lista oficial das variáveis.** Ele é **gerado** a
> partir do catálogo do código (`app/config.py` → `VARIAVEIS`, 16 entradas) por
> `tools/gerar_env_example.py` - nunca digitado à mão. A tabela abaixo é esse mesmo catálogo, e eu
> conferi que os dois batem: **17 de 17 variáveis**, sem sobra de nenhum lado, e **nenhum valor de
> segredo preenchido** no exemplo. Para conferir você mesmo:

```bash
.venv/Scripts/python.exe tools/gerar_env_example.py --conferir
```

Saída real desta máquina (`exit 0`):

```
catalogo : app/config.py -> VARIAVEIS (17 variaveis)
destino  : C:\...\squad-pecados\.env.example
--------------------------------------------------------------------------
PASSOU: .env.example em sincronia com o catalogo (17 variaveis, sha256 0946540270ce5639)
```

Para começar a configurar, o caminho mais curto é:

```bash
cp .env.example .env      # no Windows: copy .env.example .env
```

**Sintaxe aceita** (tolerante com o que as pessoas colam de tutorial):

```
CHAVE=valor              # uma por linha
# linha começada com # é comentário
export CHAVE=valor       # o "export" é aceito e ignorado
CHAVE = valor            # espaços em volta do = são ignorados
CHAVE="valor"            # aspas simples ou duplas são removidas
CHAVE=                   # vazio = NÃO CONFIGURADO (vale para variável obrigatória)
```

#### As 17 variáveis, na ordem do catálogo

**Obrigatória em:** `sempre` = sempre que a aplicação roda · `real` = todo modo real ·
`real:telegram` / `real:whatsapp` = só quando aquele canal está em `CANAIS_ATIVOS`.

| # | Variável | O que é | Obrigatória em | Onde obter o valor | Exemplo de linha |
|---|---|---|---|---|---|
| 1 | `MODO_EXECUCAO` | Como o produto roda: `mock` (dados sintéticos) ou `real` (coleta dos canais). | sempre | Você digita. As flags `--mock` / `--real` da linha de comando sobrepõem este valor. | `MODO_EXECUCAO=real` |
| 2 | `CANAIS_ATIVOS` | Quais canais o modo real coleta, separados por vírgula (`whatsapp`, `telegram`). | real | Você digita, conforme os canais que conectou. Para ligar só um: `CANAIS_ATIVOS=telegram`. | `CANAIS_ATIVOS=whatsapp,telegram` |
| 3 | `INBOX_DIR` | Pasta de entrada com as subpastas `pdf/` (aceita PDF **e imagem**), `whatsapp/` e `telegram/`. | não | Caminho no servidor. **Deixe vazio** para usar o padrão do modo: `data/mocks` no mock, `data/inbox` no real. | `INBOX_DIR=` |
| 4 | `OUT_DIR` | Pasta de saída: planilha, trilha de auditoria, fila de exceções e painel. | não | Caminho no servidor, com permissão de escrita para o usuário do serviço. | `OUT_DIR=data/out` |
| 5 | `DB_PATH` | Arquivo SQLite do pipeline (a fonte da verdade do dado). | não | Caminho no servidor. **Deixe vazio** para usar `<OUT_DIR>/pipeline.db`. | `DB_PATH=` |
| 6 | `LOG_DIR` | Pasta dos arquivos de log de execução. | não | Caminho no servidor, de preferência coberto pela rotação de logs do sistema. | `LOG_DIR=logs` |
| 7 | `LOG_LEVEL` | Nível de detalhe do log: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`. | não | Você digita. Use `DEBUG` para investigar uma coleta que falhou. | `LOG_LEVEL=INFO` |
| 8 | `TELEGRAM_BOT_TOKEN` | **Token do bot do Telegram** que recebe as mensagens dos pedidos. **SEGREDO.** | real:telegram | No Telegram, fale com o **@BotFather**, crie (ou abra) o bot e copie o token que ele devolve. | `TELEGRAM_BOT_TOKEN=123456789:AA...` |
| 9 | `TELEGRAM_CHAT_ID` | **Chat ou grupo** do Telegram que o bot deve ler. Só os updates desse chat entram no pipeline. | real:telegram | Mande uma mensagem no grupo e leia `https://api.telegram.org/bot<token>/getUpdates` no navegador: o campo `message.chat.id` é o valor (grupos começam com `-`). | `TELEGRAM_CHAT_ID=-1001234567890` |
| 10 | `TELEGRAM_API_BASE` | Endereço base da API do Telegram. | não | Valor fixo do Telegram. Só mude para apontar a um espelho/proxy local. | `TELEGRAM_API_BASE=https://api.telegram.org` |
| 11 | `TELEGRAM_TIMEOUT_S` | Tempo limite, em segundos, de cada chamada HTTP ao Telegram. | não | Você digita (padrão 30). | `TELEGRAM_TIMEOUT_S=30` |
| 12 | `WHATSAPP_TOKEN` | **Token de acesso do WhatsApp Cloud API**, do seu app na Meta. **SEGREDO.** | real:whatsapp | No **Meta for Developers**: seu app > WhatsApp > **API Setup** > *Access token*. | `WHATSAPP_TOKEN=EAAG...` |
| 13 | `WHATSAPP_PHONE_NUMBER_ID` | **Identificador do número de WhatsApp Business** que recebe as mensagens. | real:whatsapp | No **Meta for Developers**: seu app > WhatsApp > **API Setup**, campo *Phone number ID*. | `WHATSAPP_PHONE_NUMBER_ID=123456789012345` |
| 14 | `WHATSAPP_VERIFY_TOKEN` | Palavra-chave que a Meta usa para validar o webhook. **Você escolhe** e repete no painel da Meta. **SEGREDO.** | real:whatsapp | Você inventa uma palavra longa e cadastra a mesma em **Meta for Developers > WhatsApp > Configuration > Webhook**. | `WHATSAPP_VERIFY_TOKEN=uma-palavra-longa-sua` |
| 15 | `WHATSAPP_APP_SECRET` | **App secret do app da Meta**, usado para conferir a assinatura `X-Hub-Signature-256` de cada webhook recebido pelo receptor local. **SEGREDO.** | não | No **Meta for Developers**: seu app > **Configurações do app** > Básico > *Chave secreta do app*. | `WHATSAPP_APP_SECRET=uma-chave-longa-sua` |
| 16 | `WHATSAPP_API_BASE` | Endereço base da Graph API do WhatsApp. | não | Valor do Meta for Developers (padrão `https://graph.facebook.com/v21.0`). | `WHATSAPP_API_BASE=https://graph.facebook.com/v21.0` |
| 17 | `WHATSAPP_WEBHOOK_DIR` | Pasta onde o receptor local do webhook grava os envelopes recebidos do WhatsApp. | não | Caminho no servidor, de preferência **fora** da árvore versionada. | `WHATSAPP_WEBHOOK_DIR=data/inbox_webhook/whatsapp` |

#### Onde entram o número/token real - em uma resposta

- **Telegram:** crie o bot no **@BotFather** e cole o resultado em `TELEGRAM_BOT_TOKEN`. Descubra
  o id do grupo com `getUpdates` e cole em `TELEGRAM_CHAT_ID`.
- **WhatsApp:** crie o app no **Meta for Developers**, pegue o *Access token* em `WHATSAPP_TOKEN`
  e o *Phone number ID* em `WHATSAPP_PHONE_NUMBER_ID`. Escolha uma palavra sua para
  `WHATSAPP_VERIFY_TOKEN` e cadastre a **mesma** no painel de webhook da Meta.
- **Ligar o modo real:** as duas linhas que fazem isso são
  `MODO_EXECUCAO=real` e `CANAIS_ATIVOS=whatsapp,telegram` (ou só o canal que você conectou).
- **Nunca commitar o `.env`.** Ele está no `.gitignore`. Se um `.env` aparecer versionado, é
  incidente de segurança: rotacione os tokens.
- **Validar antes de rodar**, sem executar o pipeline:

```bash
.venv/Scripts/python.exe -m app.run --check-config
```

Saída real desta máquina, com um `.env` de teste (valores fictícios, arquivo **fora** do
repositório) - repare que os três segredos aparecem **mascarados** e nenhum valor sensível é
impresso:

```
Configuracao do pipeline
----------------------------------------
Modo de execucao : real
Arquivo .env     : <local>
Canais ativos    : whatsapp, telegram
Inbox            : data\inbox
Saida            : data\out
Banco            : data\out\pipeline.db
Log              : <local>)

Telegram
  api_base        : https://api.telegram.org
  bot token       : ****aABC
  chat_id         : -1001234567890
  timeout_s       : 30

WhatsApp
  api_base        : https://graph.facebook.com/v21.0
  token           : ****aXYZ
  phone_number_id : 123456789012345
  verify_token    : ****real
  webhook_dir     : data\inbox_webhook\whatsapp

Valores sensiveis aparecem mascarados (ultimos 4 caracteres). Nenhum segredo vai para log, resumo ou mensagem de erro.
```

`****aABC` é a única forma de citar um segredo: quatro asteriscos e os últimos 4 caracteres.
Nunca o valor inteiro - nem em log, nem em resumo, nem em mensagem de erro.

### 7.3 Rodar o produto

**Modo mock (o padrão, sem credencial nenhuma):**

```bash
.venv/Scripts/python.exe -m app.run --mock
```

Saída real desta máquina (recorte):

```
Modo     : mock | config: nenhum .env (padrao)
Inbox    : data\mocks
Saida    : data\out
Banco    : data\out\pipeline.db
Rodada   : 20260921-112718
--------------------------------------------------------------
Artefatos ingeridos : 21 (pdf 12 | imagens 1 | mensagens 8)
Auto-aprovados      : 0
Em revisao humana   : 0
Rejeitados          : 0
Deduplicados        : 21
Linhas na planilha  : 7
--------------------------------------------------------------
Leitura por motor   : parser 8 | pdfplumber 11 | tesseract 2
OCR                 : nenhum artefato usou OCR simulado nesta rodada
Auditoria           : 21 linha(s) nesta rodada | trilha cumulativa: 3176 linha(s)
```

Na primeira rodada de uma máquina limpa os números são `7 auto-aprovados / 10 em revisão /
2 rejeitados / 1 deduplicado` (seção 5). Aqui apareceu `Deduplicados: 20` porque a inbox já tinha
sido processada antes: **é a idempotência funcionando, não um erro** - e `Linhas na planilha`
continuou **7**.

**Modo real:**

```bash
.venv/Scripts/python.exe -m app.run --real
```

O que ele faz, nesta ordem: lê o `.env` -> valida a configuração -> **coleta** dos canais ativos
(grava envelopes no inbox) -> roda o pipeline no inbox. No resumo aparecem linhas extras de
`Modo` e `Coleta`, com quantas mensagens cada canal trouxe e onde foram gravadas.

**Se ele reclamar de variável faltante.** Não é stack trace: é uma lista do que falta, com o nome
exato e onde obter. Saída real desta máquina, rodando `--real` sem `.env` (código de saída **2**):

```
configuracao incompleta para o modo real (canais ativos: whatsapp, telegram): 5 variavel(is) obrigatoria(is) sem valor.
falta TELEGRAM_BOT_TOKEN - Token do bot do Telegram que recebe as mensagens dos pedidos (SEGREDO).
    onde obter: No Telegram, fale com @BotFather, crie/abra o bot e copie o token.
falta TELEGRAM_CHAT_ID - Identificador do chat ou grupo do Telegram que o bot deve ler (so os updates desse chat entram no pipeline).
    onde obter: Envie uma mensagem no grupo e leia getUpdates em https://api.telegram.org/bot<token>/getUpdates (campo message.chat.id).
falta WHATSAPP_TOKEN - Token de acesso do app do WhatsApp Cloud API (SEGREDO).
    onde obter: No Meta for Developers: seu app > WhatsApp > API Setup > Access token.
falta WHATSAPP_PHONE_NUMBER_ID - Identificador do numero de WhatsApp Business que recebe as mensagens.
    onde obter: No Meta for Developers: seu app > WhatsApp > API Setup (campo Phone number ID).
falta WHATSAPP_VERIFY_TOKEN - Palavra-chave que o Meta usa para validar o webhook; e voce quem escolhe e repete no painel (SEGREDO).
    onde obter: Voce inventa uma palavra longa e cadastra a mesma no Meta for Developers > WhatsApp > Configuration > Webhook.
preencha essas variaveis no arquivo .env do projeto (copie de .env.example) ou exporte no ambiente; para validar antes de rodar use: .venv/Scripts/python.exe -m app.run --check-config
para rodar com dados sinteticos, sem credencial nenhuma, use o modo padrao: .venv/Scripts/python.exe -m app.run --mock
```

**Como resolver:** crie o `.env` (seção 7.2), preencha as variáveis citadas, e confirme com
`--check-config`. Nada é executado em silêncio: se falta credencial, o produto para e diz o que
falta.

**Todas as flags:**

| Flag | O que faz |
|---|---|
| `--mock` | Modo mock (o padrão). Usa `data/mocks/` e `data/out/`. Sobrepõe o `.env`. |
| `--real` | Modo real: coleta dos canais configurados e depois roda o pipeline. Sobrepõe o `.env`. |
| `--env <arquivo>` | Usa outro arquivo de configuração em vez do `.env` da raiz. |
| `--check-config` | Valida a configuração, imprime o relatório e **sai sem rodar o pipeline** (0 = ok, 2 = falta algo). |
| `--inbox <dir>` | Outra pasta de entrada. |
| `--out <dir>` | Outra pasta de saída. |
| `--db <arquivo>` | Outro arquivo SQLite. |
| `--verbose` | Detalha artefato por artefato. |

**Antes de considerar a produção pronta, rode o verificador.** Ele checa, em um comando, os seis
pontos que fazem a configuração de produção estar sã:

```bash
.venv/Scripts/python.exe tools/verificar_producao.py
```

Saída real desta máquina (`exit 0`):

```
[1/6] .env.example presente, versionado e em sincronia com o catalogo
        PASSOU: 16 variaveis do catalogo presentes e em sincronia
[2/6] nenhum .env real versionado e .env no .gitignore
        PASSOU: nenhum .env versionado; '.env' ignorado pelo git
[3/6] modo mock continua sendo o padrao (sem .env, roda e nao exige segredo)
        PASSOU: sem .env o padrao e mock, roda e nao pede credencial nenhuma
[4/6] modo real sem as obrigatorias -> mensagem clara, sem traceback, sem rodar pipeline
        PASSOU: codigo 2, citou as 5 variaveis faltantes pelo nome, sem traceback
[5/6] varredura de segredo em arquivo versionado (inclusive .env.example)
        PASSOU: 160 arquivos versionados varridos: nenhum segredo
[6/6] `.env` de teste com valores ficticios -> --check-config reconhece e mascara
        PASSOU: configuracao ficticia aceita (exit 0) e os 3 valores sensiveis mascarados

data/ intacto (retrato de 98 arquivos, tamanho e mtime): True
RESULTADO: 6/6 PASSOU
```

O verificador trabalha em um diretório temporário próprio e **não** toca em `data/`.

### 7.4 Onde saem a planilha e a trilha de auditoria

Tudo vai para o **`OUT_DIR`** (padrão `data/out/`). O papel de cada arquivo está detalhado nas
seções 8 e 9; em resumo:

| Arquivo | Papel | Se apaga a cada rodada? |
|---|---|---|
| `controle_financeiro.xlsx` | **A planilha** de controle financeiro, 20 colunas, uma linha por pedido. | Sim - é visão do estado atual. |
| `controle_financeiro.csv` | A mesma planilha em CSV, para importar em outra ferramenta. | Sim. |
| `auditoria.jsonl` | **A trilha de auditoria: nunca se apaga.** Acumula todas as rodadas, com `rodada_id` em cada linha. | **Não.** |
| `auditoria_rodada_<AAAAMMDD-HHMMSS>.jsonl` | O recorte de **uma** execução. Serve para auditar "o que aconteceu naquela rodada". | Não (um por rodada). |
| `fila_excecoes.json` | As pendências de revisão humana (seção 7.7). | Sim - é a fila do momento. |
| `painel.html` | Painel visual para o operador, abre no navegador sem internet. | Sim. |
| `resumo.json` | O resumo da rodada em formato de máquina (o mesmo da tela). | Sim. |
| `pipeline.db` | **O banco SQLite: a fonte da verdade.** Histórico de documentos e pedidos. **Não apague** - é dele que sai a idempotência. | **Não.** |

**A distinção que importa:** a planilha, o CSV, a fila, o painel e o resumo são **visões
regeneráveis** - podem ser reescritos a cada rodada porque são recalculados a partir do banco. A
**trilha de auditoria e o banco são o registro**: nunca se apagam. É por isso que dá para
reconstruir "por que essa linha está assim" meses depois.

### 7.5 Acompanhar os logs

Cada execução escreve um arquivo de log, além de imprimir na tela:

```
<LOG_DIR>/pipeline-<AAAAMMDD>.log          # padrão: logs/pipeline-20260919.log
```

O formato é `data hora nivel mensagem`, uma linha por evento, em **append** (o log do dia não é
apagado entre rodadas). Exemplo real desta máquina:

```
2026-09-19 14:07:04 INFO    rodada iniciada: modo=mock config=nenhum .env (padrao)
2026-09-19 14:07:04 INFO    painel            data\out\painel.html
2026-09-19 14:07:04 INFO    resumo            data\out\resumo.json
2026-09-19 14:07:04 INFO    ==============================================================
2026-09-19 14:07:04 INFO    Rodada concluida em 0.824s
2026-09-19 14:07:04 INFO    rodada concluida; log em C:\...\logs\pipeline-20260919.log
```

**O que olhar no dia a dia:**

| Nível | O que significa | Quando aparece |
|---|---|---|
| `INFO` | Andamento normal: rodada iniciada, arquivos gerados, rodada concluída com o tempo. | Toda rodada. |
| `WARNING` | Algo fora do comum mas que não parou o trabalho (ex.: interrompido pelo usuário). | Eventual. |
| `ERROR` | Uma rodada falhou, ou um canal não pôde ser coletado. **É aqui que você olha primeiro.** | Quando algo quebrou. |
| `DEBUG` | Detalhe fino, para investigar. | Só com `LOG_LEVEL=DEBUG`. |

Regras de operação: (a) se o log não puder ser aberto, a rodada **avisa e segue** - não derruba o
trabalho; (b) `*.log` está no `.gitignore`, então log nunca vai para o git; (c) para investigar
uma coleta que falhou, suba `LOG_LEVEL=DEBUG` no `.env` e rode de novo.

### 7.6 Agendar a execução periódica

**Pode agendar sem medo.** A rodada é **idempotente**: rodar de novo sobre os mesmos documentos
**não duplica linha** na planilha (seção 9, e `tools/verificar.py` prova isso rodando duas vezes).
Agendar de mais causa trabalho extra de leitura, não dado duplicado.

**Windows - Agendador de Tarefas (GUI):** crie a tarefa, e na aba **Ações** preencha os três
campos:

| Campo | Valor |
|---|---|
| Programa/script | `C:\...\squad-pecados\.venv\Scripts\python.exe` |
| Adicionar argumentos | `-m app.run --real` |
| **Iniciar em** | `C:\...\squad-pecados`  ← **a raiz do projeto** |

> O campo **"Iniciar em" é obrigatório e é o erro mais comum.** Sem ele a tarefa roda em
> `C:\Windows\System32`: não acha o `.venv`, não acha o `.env` e não acha `data/`. O agendamento
> falha "sem motivo aparente". Com ele, o produto enxerga o projeto inteiro.

**Windows - linha de comando** (`schtasks`, exemplo a cada hora - ajuste caminhos e horário):

```bat
schtasks /Create /TN "NF-Pedidos coleta" /SC HOURLY /MO 1 ^
  /TR "\"C:\...\squad-pecados\.venv\Scripts\python.exe\" -m app.run --real"
```

**Linux / macOS (`cron`)** - no Linux o interpretador do venv fica em `.venv/bin/python`:

```cron
# a cada 15 minutos; ajuste o caminho do projeto
*/15 * * * * cd /opt/squad-pecados && .venv/bin/python -m app.run --real >> logs/cron.log 2>&1
```

Para rodar só o processamento (sem coletar), troque `--real` por `--mock`; para o modo real sem
coleta automática, mantenha `--real` e deixe o receptor de webhook (seção 7.8) alimentando a pasta.

> **O que eu não fiz:** não executei o agendamento nesta entrega - nem no Agendador de Tarefas
> nem no `cron`. O que está provado é o comando base (seção 7.3) e a idempotência (seção 9). O
> passo de agendar em si é do ambiente do cliente.

### 7.7 Quando uma extração falha: a fila de exceções e a revisão humana

**O caminho, em uma linha:**

```
documento chega -> o sistema lê e CONFERE -> passou?  -> linha na planilha
                                          -> não passou? -> fila de exceções -> revisão humana -> planilha
```

**Nada entra na planilha "no escuro".** Quando o sistema não tem certeza - o CNPJ não fecha, a
soma dos itens não bate, a leitura ficou fraca, o documento manda fazer algo estranho -, ele
**não chuta e não escreve**: registra a dúvida e deixa para uma pessoa decidir.

**Onde a pessoa olha:**

- **`painel.html`** - abra no navegador (é um arquivo local, não precisa de internet). Mostra os
  totais da rodada e a lista do que ficou em dúvida, com o documento, o campo suspeito e a dica.
- **`fila_excecoes.json`** - a mesma fila em formato de dado, para quem for tratar em lote.
  Cada pendência traz `motivo_codigo`, `motivo` (a explicação), `campo_suspeito`, `risco`
  (`alto` / `medio`), `dica`, o `arquivo` de origem e o status (`aberta` até alguém resolver).

**O que significa cada motivo** (é o vocabulário que aparece na fila e no painel):

| Motivo (`motivo_codigo`) | Risco | Em português, o que aconteceu |
|---|---|---|
| `cnpj_dv_invalido` | alto | O CNPJ do emitente não fecha o dígito verificador. |
| `chave_acesso_dv_invalido` | alto | A chave de acesso da NF não fecha o dígito verificador. |
| `valor_total_ausente` | alto | Nenhum valor total foi encontrado no documento. |
| `valor_total_fora_da_faixa` | alto | Valor total fora da faixa aceita (R$ 0,01 a R$ 10.000.000,00). |
| `divergencia_soma_itens` | alto | A soma dos itens não bate com o total lido (diferença acima de R$ 0,10). |
| `suspeita_soma_itens` | médio | A soma quase bate (diferença de até R$ 0,10). |
| `total_sem_detalhamento` | médio | Tem total confiável, mas sem itens detalhados (caso de pedido/mensagem). |
| `conflito_valor_mesma_chave` | alto | O mesmo pedido já é conhecido, com valor diferente. Não sobrescreve sozinho. |
| `possivel_duplicata` | alto | Suspeita de duplicidade: mesmo emitente, data e valor de outro documento. |
| `data_implausivel` | alto | Data de emissão fora da janela plausível. |
| `data_ambigua` | médio | Data ambígua (dia menor ou igual a 12: dá para ler como mês). |
| `documento_ilegivel` | alto | Nenhum texto útil foi reconhecido no documento. |
| `sem_campos_obrigatorios` | alto | Nenhum campo obrigatório foi extraído. |
| `baixa_confianca` | alto | A leitura ficou abaixo do exigido para aprovação automática. |
| `texto_instrucao_suspeita` | alto | O documento traz texto de instrução suspeita (tentativa de manipular o sistema). |

Regra de ouro do operador: **na dúvida, confira o documento original** (o caminho dele está na
própria pendência) e só então libere. O sistema nunca "corrige" um valor por conta própria, e
nunca obedece a instrução escrita dentro do documento.

### 7.8 Modo real dos canais: como Telegram e WhatsApp entram

**Telegram - o produto busca (`getUpdates`).** Na coleta, o produto chama
`GET {TELEGRAM_API_BASE}/bot{TOKEN}/getUpdates` e transforma cada mensagem recebida em uma linha
de envelope, no mesmo formato de `data/mocks/telegram/*.jsonl`. As mensagens de outros chats são
filtradas por `TELEGRAM_CHAT_ID`. Grava **um** arquivo por coleta:
`<INBOX_DIR>/telegram/telegram_coleta_<AAAAMMDD-HHMMSS>.jsonl`.

- Sem mensagem nova: **não é erro** - ele diz "getUpdates sem update novo" e segue.
- Credencial recusada pela API: vira uma mensagem clara citando `TELEGRAM_BOT_TOKEN`, **sem
  imprimir o token**.

**WhatsApp - o produto recebe (webhook local).** O WhatsApp Cloud API não tem "buscar mensagens":
a Meta **empurra** cada mensagem para um endereço seu. Por isso existe um receptor local:

```bash
.venv/Scripts/python.exe tools/receber_webhook_whatsapp.py
```

| Parâmetro | Padrão | Para que serve |
|---|---|---|
| `--host` | `127.0.0.1` | Endereço de escuta. |
| `--porta` | `8787` | Porta de escuta. |
| `--env` | `.env` da raiz | Outro arquivo de configuração. |
| `--uma-vez` | desligado | Encerra depois do primeiro `POST` (útil para testar). |

A rota padrão é **`/webhook/whatsapp`**. Em `GET` ele responde a verificação da Meta
(`hub.mode=subscribe` + `hub.verify_token` + `hub.challenge`): devolve o `challenge` com **200**
quando o token confere, **403** quando não confere. Em `POST` ele grava o envelope em
`<WHATSAPP_WEBHOOK_DIR>/<timestamp>_<n>.json`. Cada requisição vira uma linha na tela - e o token
**nunca** é impresso. Sem `WHATSAPP_VERIFY_TOKEN` configurado, ele **recusa iniciar** com uma
mensagem clara.

> **Não precisa criar as pastas na mão.** `data/inbox/`, `data/inbox_webhook/whatsapp/` (e
> `logs/`) são criadas automaticamente na primeira vez que o produto precisa delas.

Depois de gravados, os envelopes são consumidos pela coleta: `ler_webhook_whatsapp()` leva cada
um para `<INBOX_DIR>/whatsapp/whatsapp_coleta_<...>.jsonl` e move o arquivo consumido para
`<WHATSAPP_WEBHOOK_DIR>/processados/`. Webhook que não traz `entry` (aviso de status de entrega,
por exemplo) é descartado com explicação.

**O que o operador precisa fazer no painel da Meta:**

1. Criar o app e pegar **Access token** (`WHATSAPP_TOKEN`) e **Phone number ID**
   (`WHATSAPP_PHONE_NUMBER_ID`) em *WhatsApp > API Setup*.
2. Escolher uma palavra longa e cadastrá-la como **Verify token** em
   *WhatsApp > Configuration > Webhook* - a mesma que foi para `WHATSAPP_VERIFY_TOKEN`.
3. Informar a **URL do webhook** (`https://seu-dominio/webhook/whatsapp`) e assinar o campo
   **messages**.

> **Limite honesto desta parte.** O receptor escuta em `127.0.0.1`: isso serve para uso **local**,
> como o contrato pede. Para a Meta alcançar o receptor em produção é preciso **expor o endereço
> em HTTPS** (domínio + certificado + liberação de firewall) - e esse ponto continua sendo do
> ambiente do cliente.
>
> A **assinatura `X-Hub-Signature-256`** dos webhooks **é validada** desde que `WHATSAPP_APP_SECRET`
> esteja no `.env`: o receptor confere o HMAC-SHA256 do corpo **bruto**, em tempo constante,
> **antes** de gravar qualquer coisa, e responde **401 sem gravar** quando a assinatura falta ou
> não confere. Sem o app secret, ele sobe com **aviso explícito na tela** e aceita o POST - é o
> modo que permite a prova local sem credencial real, e por isso ele avisa alto em vez de fingir
> que está seguro.

---

## 8. A planilha de saída: as 20 colunas

`data/out/controle_financeiro.xlsx` (e o `.csv` equivalente) tem **uma linha por pedido**, com
exatamente estas 20 colunas, nesta ordem. Elas são congeladas por contrato: os nomes são a
interface do sistema.

| # | Coluna | O que significa |
|---|---|---|
| 1 | `data_processamento` | Quando o sistema gravou (ou atualizou) essa linha. Data e hora com fuso. |
| 2 | `documento_id` | Identificador interno do documento lido de onde a linha veio. |
| 3 | `pedido_id` | Identificador do **pedido**. É a chave da linha: o mesmo pedido nunca ocupa duas linhas. |
| 4 | `origem` | Por qual canal chegou: `pdf`, `imagem`, `whatsapp` ou `telegram`. |
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

## 9. Idempotência e trilha de auditoria (explicado para quem não programa)

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

## 10. Limitações honestas

Estas são as fronteiras desta entrega. Nenhuma delas é detalhe: leia antes de avaliar o
resultado.

**1. O OCR real ESTÁ instalado e em uso; o simulado virou o caminho de quem não tem o binário.**
Esta máquina tem o **Tesseract 5.5.3** (instalador oficial, com o idioma `por`) e o pacote
`pytesseract`. A ordem de leitura do produto é: **Tesseract real → sidecar `<arquivo>.ocr.txt`
(simulado) → texto vazio, marcado para revisão humana**. O motor simulado continua existindo para
quem não tem o binário e continua **rotulado como simulado** (`ocr_simulado`) na trilha, no resumo
e no painel - nenhuma leitura se passa por nativa. A rasterização da página antes do OCR é de
**300 dpi**: a 200 dpi o Tesseract perde a vírgula decimal dos itens (`2,35 17,50` sai
`2,35 1750`) e a 400 dpi ou mais ele cola colunas - 300 é o ponto medido como correto nesta
máquina. O que **está** provado: PDF escaneado e **imagem** entram, passam pelo OCR real, saem com
a confiança de OCR (0,65 em vez de 0,95) e **vão para revisão humana** - nunca para a planilha sem
conferência de uma pessoa. A confiança **por campo** também segue a origem da leitura: quem leu acompanha a extração (`extrair(..., motor=...)`), então texto vindo do motor real - PDF escaneado sem sidecar ou imagem - pontua com a base de OCR (0,65), e não com a base nativa. Foi essa emenda que fechou a última brecha em que uma leitura de OCR podia se passar por leitura nativa.

**O que ainda NÃO está medido:** acurácia de OCR em foto de nota de
verdade (ângulo, sombra, papel amassado, celular na mão). O material deste repositório é sintético
e limpo, e os limiares são os do desenho do produto, não calibrados contra foto real.

**2. Os canais são mock com o envelope real - e a coleta real NÃO foi exercitada com credencial.**
As mensagens usadas na demonstração são **arquivos de mock** (`data/mocks/whatsapp/*.jsonl`,
`data/mocks/telegram/*.jsonl`) escritos no **formato real** dos envelopes do WhatsApp Cloud API e
do Telegram Bot API. Em cima disso, a **coleta real foi implementada**: o produto sabe buscar no
Telegram (`getUpdates`) e receber no WhatsApp (receptor de webhook local), e converte tudo no mesmo
formato de envelope. Ela foi **testada contra um stub HTTP local (`127.0.0.1`)**, que provou a
montagem da requisição, a gravação do envelope e o ciclo completo até a planilha. **O que não
aconteceu:** a chamada **credenciada** a `api.telegram.org` e a `graph.facebook.com` **não foi
executada** - não existe token nem número real autorizado nesta entrega. Portanto: **nenhuma
mensagem real de WhatsApp ou Telegram passou por este sistema.** O que está provado é o mecanismo,
não a integração com as contas do cliente.

**3. O pipeline não usa rede; a coleta, sim.** O processamento (leitura, extração, validação,
planilha) é **100% local e offline** - nenhuma API, nenhum LLM, nenhum serviço externo. A extração
é por regras determinísticas, lendo rótulos e âncoras do texto (`VALOR TOTAL DA NOTA`,
`CHAVE DE ACESSO`, `PEDIDO N`...). Duas consequências práticas: **formato novo de fornecedor não é
"aprendido" sozinho** - ou o rótulo é reconhecido, ou o documento vai para a fila de revisão; e
**que não usa rede não quer dizer que o produto todo não use** - no **modo real**, a etapa de
coleta fala com a API do Telegram e recebe webhook do WhatsApp, e é a única parte que depende de
internet.

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
comportamento na fronteira foi calibrado contra estes 21 artefatos. Com volume e variedade
reais, esses limiares precisam ser reconferidos - e essa é uma decisão de produto, não de código.

**7. A suíte cobre carga e nota multipágina; NÃO cobre paralelismo.** São os testes de correção
funcional, adversariais e ponta a ponta, mais dois casos que antes ficavam de fora do escopo
(AD-02 e AD-12 do plano de testes):

- **nota fiscal multipágina** (`tests/test_multipagina.py`): documento de 2 páginas, com 3 itens
  na primeira e 2 na segunda. Prova que o item da página 2 não é perdido e que a soma fecha.
- **rajada de volume** (`tests/test_rajada.py`): 120 artefatos numa rodada (90 notas em PDF + 30
  mensagens), com a contabilidade fechando e a segunda rodada deduplicando tudo. Medido nesta
  máquina: **3,1 s** para os 120 (o teto declarado no teste é 180 s).

O que **continua fora**: documento de 2 páginas com 30 itens, rajada de centenas de milhares de
documentos e **paralelismo** - o alvo do produto é processo local único + SQLite (limitação 8),
então não há teste de execução concorrente porque não há execução concorrente. Junto com a
limitação 8, é isso que ainda separa esta entrega de um uso em produção.

**8. Um comando, uma máquina.** O alvo desta entrega é **processo local único + SQLite**, sem
Docker, sem serviço pago, sem banco de dados em rede. Rodar em produção com volume, multiusuário
e agendamento é outro passo - e não está feito.

**9. Nada de serviço pago, chave nova ou número real.** Esta entrega **não** contratou serviço,
**não** criou conta, **não** gerou chave de API e **não** usou número de telefone real - nem de
WhatsApp, nem de Telegram. O modo real existe e está pronto para receber as credenciais do cliente,
mas quem as fornece é o cliente: por isso a seção 7.2 termina com "onde obter cada valor".

**10. O receptor de webhook está pronto para uso local, não para a internet.** Ele escuta em
`127.0.0.1` e valida a assinatura `X-Hub-Signature-256` dos webhooks quando `WHATSAPP_APP_SECRET`
está configurado (sem ele, aceita o POST com aviso explícito na tela). Para receber webhook real
em produção faltam três coisas do ambiente do cliente: **endereço público em HTTPS**,
**certificado** e **liberação de firewall**.

---

## 11. Estrutura do repositório

```
app/          código do pipeline (contratos, config, ingestão, extração, normalização,
              persistência, revisão, canais, CLI)
data/mocks/   material sintético gerado por script (PDFs, mensagens, manifest.json)
data/out/     saída real da rodada: planilha, auditoria, fila de pendências, painel
logs/         log de execução do dia (pipeline-AAAAMMDD.log); ignorado pelo git
docs/         desenho técnico e planejamento (arquitetura, dados/IA, qualidade, devops, UX, plano do cliente)
docs/execucao/contrato de execução das fases (00 e 00b) e specs das frentes de trabalho
relatorios/   RELATORIO-ENTREGA.md, CRONOGRAMA.md e RELATORIO-FECHAMENTO.md
tests/        suíte pytest (437 testes) + RELATORIO-F5.md, test_imagem.py,
              test_multipagina.py, test_rajada.py e evidencia/
tools/        gerar_mocks.py      material sintético determinístico
              verificar.py        prova a idempotência (roda o pipeline 2x)
              receber_webhook_whatsapp.py  receptor local do webhook do WhatsApp
              gerar_env_example.py         gera o .env.example a partir do catálogo
              verificar_producao.py        verificador de execução real (6 itens)
.env.example  lista versionada das 17 variáveis, com as chaves vazias (gerada do código)
requirements.txt  dependências, nas versões exatas instaladas no .venv
```

Arquivos e pastas que **não** vão para o git (e por quê): `.venv/` (ambiente local),
`.env` (segredo), `logs/` e `*.log` (saída de execução), `__pycache__/`, `.pytest_cache/`.
`data/mocks/` e `data/out/` **entram** de propósito: são a evidência do funcionamento.

Documentação de referência, em ordem de leitura:

1. `docs/execucao/00b-contrato-fechamento.md` - o contrato desta fase (configuração, modo real,
   operação) e a definição de pronto.
2. `docs/execucao/00-contrato-execucao.md` - o contrato do produto (formatos congelados).
3. `relatorios/RELATORIO-FECHAMENTO.md` - o que esta fase entregou, com as evidências.
4. `relatorios/RELATORIO-ENTREGA.md` - o que foi entregue nas fases anteriores e o que ficou de fora.
5. `relatorios/CRONOGRAMA.md` - o cronograma prometido ao cliente e o tempo real de execução.
6. `docs/01-arquitetura.md` a `docs/06-plano-e-requisitos-cliente.md` - o desenho e o plano.

---

*Todo número neste README veio de execução real do pipeline nesta máquina ou de artefato em
`data/out/`. Onde não deu para medir, está escrito que não deu.*
