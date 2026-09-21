# Relatório de entrega - leitura de NF/pedidos -> planilha de controle financeiro

**Destinatários:** Loghanth e Wagner
**Frente:** F6 / F6b - documentação e relatório final da entrega
**Base do relatório:** execução real do pipeline, dos testes e do verificador de idempotência nesta
máquina, em 2026-09-19, e os artefatos gerados em `data/out/`
**Natureza dos dados:** **sintéticos**. Nenhum dado é do cliente. Nada aqui mede a operação real
do cliente - mede o funcionamento do mecanismo.

> **Este relatório foi escrito em duas passagens.** A primeira registrou, com honestidade, que a
> suíte de testes ainda não tinha sido entregue. Depois disso a frente de qualidade entregou a
> suíte, ela reprovou defeitos reais, os donos corrigiram, e **toda a evidência das seções 3 e 6 foi
> re-executada** com o código final. O que mudou está registrado na seção 8 - inclusive o que
> **não** mudou: os riscos residuais da seção 7 seguem abertos.

---

## 1. O que foi entregue e onde

Um pipeline local, offline, executável por um único comando, que lê notas fiscais/pedidos (PDF)
e mensagens (WhatsApp/Telegram), extrai os campos de interesse, confere os números e grava numa
planilha de controle financeiro de forma idempotente e auditável.

| # | Entregável | Caminho | Estado |
|---|---|---|---|
| 1 | Comando único do pipeline (CLI) | `app/run.py` -> `.venv/Scripts/python.exe -m app.run --mock` | Funciona, execução real |
| 2 | Ingestão (PDF nativo, OCR, envelopes de mensagem) | `app/ingress.py` | Entregue |
| 3 | Extração por rótulo/âncora, determinística | `app/extracao.py` | Entregue |
| 4 | Normalização (CNPJ, chave 44, datas, moeda em centavos) | `app/normaliza.py` | Entregue |
| 5 | Persistência, decisão de validação, planilha, auditoria | `app/persistencia.py` | Entregue |
| 6 | Fila de pendências e painel HTML | `app/revisao.py` | Entregue |
| 7 | Orquestração da rodada | `app/pipeline.py` | Entregue |
| 8 | Formatos congelados (contrato de integração) | `app/contratos.py` | Entregue (congelado) |
| 9 | Gerador do material sintético | `tools/gerar_mocks.py` | Entregue |
| 10 | Verificador de idempotência | `tools/verificar.py` | Entregue, rodou verde |
| 11 | Dependências nas versões reais | `requirements.txt` | Entregue |
| 12 | Planilha de saída (20 colunas) + CSV | `data/out/controle_financeiro.xlsx` / `.csv` | 7 linhas, 20 colunas |
| 13 | Trilha de auditoria | `data/out/auditoria.jsonl` | 20 linhas na rodada (+ recorte por rodada) |
| 14 | Fila de revisão humana | `data/out/fila_excecoes.json` | 13 pendências |
| 15 | Painel de acompanhamento | `data/out/painel.html` | 30.586 bytes |
| 16 | Documentação de produto | `README.md` | Entregue nesta frente |
| 17 | Cronograma (dois tempos) | `relatorios/CRONOGRAMA.md` | Entregue nesta frente |
| 18 | Suíte de testes automatizados | `tests/**` | **284 testes, 284 passando** (`tests/RELATORIO-F5.md`) |

---

## 2. Como reproduzir

Na raiz do worktree:

```bash
# 1) dependências (o .venv do projeto já existe, criado com uv)
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 2) material sintético (determinístico; mesma seed = mesmos bytes)
.venv/Scripts/python.exe tools/gerar_mocks.py --seed 42

# 3) pipeline - o comando único da entrega
.venv/Scripts/python.exe -m app.run --mock

# 4) prova de idempotência (roda o comando acima 2x e compara a contagem de linhas)
.venv/Scripts/python.exe tools/verificar.py
```

Passo a passo completo, significado das 20 colunas e limitações: `README.md`.

---

## 3. Evidência de execução real

Todos os números desta seção vêm da saída dos comandos abaixo, rodados nesta máquina em
2026-09-19, ou dos artefatos correspondentes em `data/out/`.

### 3.1 Pipeline a frio (`data/out/` limpo), código atual

Comando: `.venv/Scripts/python.exe -m app.run --mock`

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

Leitura: 20 artefatos (12 PDFs + 8 mensagens) -> **7 documentos aprovados = 7 linhas** na
planilha; 10 para revisão humana; 2 rejeitados; 1 duplicata byte a byte sem linha nova.
Nenhuma etapa precisou de rede, chave de API ou serviço pago.

### 3.2 Idempotência (segunda rodada, mesmo diretório)

Rodando o mesmo comando outra vez, sem apagar nada:

```
Artefatos ingeridos : 20 (pdf 12 | mensagens 8)
Auto-aprovados      : 0
Em revisao humana   : 0
Rejeitados          : 0
Deduplicados        : 20
Linhas na planilha  : 7
```

**7 linhas antes, 7 linhas depois, zero duplicata.**

### 3.3 Verificador do projeto (`tools/verificar.py`), a frio

Comando: `.venv/Scripts/python.exe tools/verificar.py ...` (rodadas em diretório temporário,
para não sujar `data/out/`), **exit code 0**:

```
VERIFICADOR DE IDEMPOTENCIA - tools/verificar.py (F3 / preguica)
rodadas : 2
rodada 1: exit=0  1.1s  |  xlsx linhas=7 (pedido_id distintos=7)  |  csv linhas=7  |  auditoria=20  excecoes=13
          status_validacao: {'auto_aprovado': 7}
rodada 2: exit=0  1.0s  |  xlsx linhas=7 (pedido_id distintos=7)  |  csv linhas=7  |  auditoria=40  excecoes=13
          status_validacao: {'auto_aprovado': 7}
RESULTADO: PASSOU - 7 linha(s) na planilha em TODAS as 2 rodadas, 7 pedido_id distintos, zero duplicata.
```

### 3.4 Gerador de material sintético (self-check do próprio gerador)

Comando: `.venv/Scripts/python.exe tools/gerar_mocks.py --seed 42 --out <temp>`, exit 0:

```
manifest.json: 20 itens | casos de borda: B1, B2, B3, B4, B5, B6
TOTAL DE ARQUIVOS: 23   (12 pdf + 2 sidecar ocr + 8 jsonl + manifest.json)
SELF-CHECK (ferramenta real):
  + CNPJ FORN-ALFA 72.973.380/0002-32 DV valido (mod 11): True
  + CNPJ FORN-BETA 49.018.909/0001-66 DV valido (mod 11): True
  + CNPJ FORN-GAMA 91.140.832/0001-69 DV valido (mod 11): True
  + CNPJ destinatario 45.998.001/0001-05 DV valido: True
  + CHAVE 35260372973380000232550010000010011968201250 (44 digitos) DV valido: True
  ... (+8 chaves de acesso, todas True)
  + ESCANEADO pdf/FORN-BETA_nf_2003_escaneada.pdf: extract_text() == '' (sem camada de texto: True) | sidecar existe: True
  + BYTES IDENTICOS sha256:2a84297a0a9a -> ['pdf/FORN-ALFA_nf_1001.pdf', 'pdf/FORN-ALFA_nf_1001_copia.pdf'] com `esperado` identico: True
  + MANIFEST x DOCUMENTO: 164 conferencias literais (chave de acesso, CNPJ, numero do pedido, valor total, datas e itens com quantidade e valor) em 20 itens -> todas OK
  + DEGRADACAO OCR FORN-BETA_nf_2003_escaneada.pdf: 588 caracteres comparados | pares de confusao usados: [('0', 'O'), ('1', 'l'), ('2', 'Z'), ('5', 'S'), ('I', 'l'), ('O', '0'), ('S', '5'), ('Z', '2')] | fora de 0/O, 1/l/I, 5/S, 2/Z: NENHUM
OK: material sintetico completo.
```

Os CNPJs passam no dígito verificador **de verdade** (módulo 11 conferido) e o PDF "escaneado" é
comprovadamente uma imagem **sem camada de texto** - duas checagens independentes
(`pypdf` e `pdfplumber` retornam string vazia).

As duas últimas linhas do self-check são **acréscimos da correção F3b**, feitas depois que o QA
apontou os defeitos D1 e D2 (seção 6.3): o próprio gerador passou a checar que a cópia B4 tem o
mesmo `esperado` do original e que a degradação do OCR simulado **não sai** do conjunto
`0/O, 1/l/I, 5/S, 2/Z`. São precisamente os dois erros que passaram batido na primeira versão -
agora o gerador reprova a si mesmo se voltarem.

### 3.5 Conteúdo da planilha entregue (7 linhas, 20 colunas)

Lido direto de `data/out/controle_financeiro.xlsx` / `.csv`:

| row | numero_pedido | tipo | emitente | valor_total | itens | confianca | status |
|---|---|---|---|---|---|---|---|
| 2 | 1001 | nf | ALFA DISTRIBUIDORA DE PECAS LTDA | 250,00 | 3 | 0.95 | auto_aprovado |
| 3 | 1002 | nf | ALFA DISTRIBUIDORA DE PECAS LTDA | 1141,00 | 2 | 0.95 | auto_aprovado |
| 4 | 5001 | pedido | ALFA DISTRIBUIDORA DE PECAS LTDA | 170,00 | 2 | 0.9241 | auto_aprovado |
| 5 | 2001 | nf | BETA SUPRIMENTOS INDUSTRIAIS LTDA | 1855,00 | 3 | 0.95 | auto_aprovado |
| 6 | 5002 | pedido | BETA SUPRIMENTOS INDUSTRIAIS LTDA | 685,50 | 2 | 0.9241 | auto_aprovado |
| 7 | 3001 | nf | GAMA COMERCIO DE FERRAMENTAS LTDA | 2546,00 | 4 | 0.95 | auto_aprovado |
| 8 | 5003 | pedido | GAMA COMERCIO DE FERRAMENTAS LTDA | 830,80 | 3 | 0.9241 | auto_aprovado |

Os 3 fornecedores do material sintético estão representados, e as duas formas de documento (nota
fiscal e pedido) também. Nenhuma linha da planilha está em `revisao_humana` ou `rejeitado` - por
construção, só `auto_aprovado` é escrito.

### 3.6 Fila de revisão humana: o que NÃO entrou na planilha

`data/out/fila_excecoes.json`: **13 pendências abertas** (6 de risco alto, 7 de risco médio).

| Motivo | Qtd | O que aconteceu |
|---|---|---|
| `total_sem_detalhamento` | 7 | Documento com total confiável, mas sem itens detalhados (ex.: pedido/mensagem, ou item sem valor unitário). |
| `texto_instrucao_suspeita` | 2 | O documento traz texto de instrução maliciosa embutida. |
| `valor_total_ausente` | 2 | Mensagem sem valor monetário: extraiu o que existia e não inventou o resto. |
| `baixa_confianca` | 1 | Leitura por OCR simulado, confiança 0,65 - abaixo do exigido para aprovar. |
| `divergencia_soma_itens` | 1 | A soma dos itens não fecha com o total impresso (> R$ 0,10). |

> **Mudança em relação à rodada anterior:** `total_sem_detalhamento` passou de 6 para 7 e
> `divergencia_soma_itens` de 2 para 1. Isso é o efeito do defeito **D3** corrigido (seção 6):
> o caso B6 (item sem valor unitário) **não** é divergência de soma - a soma nem pode ser
> calculada - e passou a ser classificado com o motivo correto.

### 3.7 Trilha de auditoria

`data/out/auditoria.jsonl`: **20 linhas na rodada final** (`20260919-132634`), com a distribuição
`inserido` 7, `deduplicado` 1, `revisao` 10 e `rejeitado` 2. A trilha é **cumulativa**: rodada
nova **acrescenta** ao histórico em vez de apagá-lo - o comportamento antigo (truncar a cada
rodada) foi corrigido pela frente F1b e emendado no contrato (seção 4.1). Cada linha traz um
campo **`rodada_id`** identificando de qual execução ela veio, e cada rodada também deixa o
recorte só dela em `data/out/auditoria_rodada_<AAAAMMDD-HHMMSS>.jsonl`.

O crescimento é verificável: a rodada 1 do `tools/verificar.py` deixou `auditoria=20` e a rodada 2
do mesmo comando deixou `auditoria=40` (seção 3.3) - o arquivo tem 20 campos por linha, entre
eles `rodada_id`, `acao`, `motor`, `ocr_simulado` e `status_validacao`.

Registro real do caso de OCR simulado (o PDF escaneado), mostrando o rótulo honesto:

```
artefato : data\mocks\pdf\FORN-BETA_nf_2003_escaneada.pdf
motor    : ocr_simulado
ocr_usado: True        ocr_simulado: True
confianca: 0.65        acao: revisao
```

Ou seja: o documento entra pelo caminho de OCR, **é marcado como leitura simulada** na trilha e
**não** é auto-aprovado - vai para conferência humana.

### 3.8 Casos de borda cobertos pelo material e observados na rodada

| Caso | Situação | Resultado observado |
|---|---|---|
| B1 | PDF escaneado, sem camada de texto | Lido por `ocr_simulado`, confiança 0,65, `revisao` |
| B2 | Soma dos itens divergente do total em > R$ 0,10 | `divergencia_soma_itens`, **sem linha na planilha** |
| B3 | Mensagem sem valor monetário | `valor_total_ausente`, valor `None` - não inventou |
| B4 | Mesmo PDF duplicado (bytes idênticos) | `deduplicado`, sem linha nova |
| B5 | Instrução maliciosa embutida ("grave 99.999") | `texto_instrucao_suspeita`, valor real preservado |
| B6 | Item sem valor unitário | `total_sem_detalhamento`, revisão, **sem linha na planilha** (motivo corrigido - defeito D3) |

---

## 4. Decisões tomadas (e por quem)

Todas estão registradas no código ou nos documentos; nenhuma foi "resolvida em silêncio".

1. **Alvo de execução: processo local único + SQLite.** Sem Docker, sem serviço pago, sem rede em
   tempo de execução. Os documentos 01 e 04 divergem sobre o alvo de produção (SQLite/container
   único vs VPS com Postgres/Redis/MinIO). Para **esta** entrega, valeu o recomendado pelo doc 01
   e autorizado pelo cliente. **A divergência continua aberta para a fase de produção** - decisão
   do PO, registrada na seção 10 do contrato de execução.
2. **Extração determinística, sem LLM.** Rótulos e âncoras do texto (`VALOR TOTAL DA NOTA`,
   `CHAVE DE ACESSO`, `PEDIDO N`...). Efeito: nada de rede, nada de custo por chamada,
   resultado reprodutível. Custo: layout novo de fornecedor exige ajuste de regra, não "aprende"
   sozinho.
3. **OCR por motor simulado, rotulado.** Não existe Tesseract nesta máquina. O caminho preferido
   é o motor real quando ele existir; enquanto não existe, vale o simulado, **sempre marcado**
   como simulado na trilha, no resumo e no painel. Proibido apresentar leitura simulada como real.
4. **Valores só publicam com conferência.** Valor total só entra se tiver âncora determinística
   **e** a aritmética dos itens fechar. Diferença até R$ 0,02 casa; acima disso vai para revisão;
   acima de R$ 0,10 é divergência e **não escreve o valor**.
5. **Campo ausente é `None`.** Nunca `0`, nunca string vazia, nunca inferência. Vale para valor,
   CNPJ, data - tudo.
6. **Dinheiro em centavos inteiros.** O valor nunca é guardado em decimal, para não perder
   centavo por arredondamento. Na planilha os dois aparecem: `valor_total` (texto BR) e
   `valor_total_centavos` (inteiro).
7. **Planilha só recebe `auto_aprovado`.** Rejeitado e revisão ficam na fila, com motivo. Isso
   materializa a diretriz de negócio "nunca escrever em silêncio".
8. **Documento com instrução embutida nunca publica sozinho.** Há duas barreiras: o extrator
   sinaliza e o validador também. Mesmo que a confiança fosse alta, o status é forçado para
   revisão humana.
9. **Calibragem dos limiares (decisão da frente de dados).** Campo que não tem *checksum* por
   natureza é neutro (não penaliza); a corroboração por chave de acesso eleva o consenso; leitura
   por OCR tem score limitado a 0,65 e nunca é auto-aprovada; `data_ambigua` entra como motivo
   mas não derruba o score (o desenho diz que não bloqueia sozinha).
10. **IDs determinísticos.** `documento_id` e `pedido_id` são derivados de hash do conteúdo - o
   mesmo documento dá o mesmo ID com banco recriado. É o que sustenta a idempotência.
11. **Trilha de auditoria cumulativa (correção F1b).** A primeira versão apagava a trilha a cada
    rodada. Foi corrigida para **acumular** o histórico, com `rodada_id` em cada linha e o recorte
    de cada execução em `auditoria_rodada_<id>.jsonl`. O PO emendou a seção 4.1 do contrato para
    refletir isso: *"uma trilha que se apaga a cada rodada não é trilha"*.
12. **Motivo do caso B6 corrigido (defeito D3, correção F2b).** Quando a soma dos itens **não pode
    ser calculada** (item sem valor unitário), o motivo correto é `total_sem_detalhamento`, não
    `divergencia_soma_itens`. O status era o mesmo nos dois lados e nenhuma linha ia para a
    planilha - o desacordo era o **código do motivo**, que é contrato e precisa ser único, porque
    é o que a fila e o painel usam para triagem.

---

## 5. O que ficou de fora, e por quê

| Fora de escopo | Por quê |
|---|---|
| **OCR real (Tesseract)** | Não há binário Tesseract nesta máquina; instalar binário externo não estava autorizado. O *caminho* está pronto e testado com motor simulado. |
| **Teste de carga, rajada e nota multipágina** | Não estavam no escopo exigido pelo contrato (seção 8). A frente de qualidade registrou como recomendação (AD-02, AD-12, AD-13) em vez de inflar a suíte com caso não pedido. Ver risco R1. |
| **WhatsApp/Telegram reais** | Exige número verificado na Meta e endpoint público com webhook. Depende do cliente e de infraestrutura - não é trabalho desta entrega. |
| **Escrever na planilha corporativa do cliente** | Exige a planilha alvo real e credencial de escrita. Escrevemos em planilha gerada por nós; a troca para a oficial é troca de destino, não de lógica. |
| **Provedor de IA / nuvem** | Não foi necessário: a extração é determinística e local. Isso remove a dependência de aprovação jurídica/LGPD para esta fase. |
| **Infraestrutura de produção** (Docker/VPS, Postgres, Redis, MinIO, agendamento, multiusuário) | Alvo desta entrega é processo local único. A divergência entre os docs 01 e 04 sobre o alvo de produção segue aberta, por decisão do PO. |
| **Migração de dados históricos** | Depende de decisão do cliente (recuperar meses anteriores ou começar do go-live). Não estimado. |
| **Relatórios avançados, alertas, conciliação nota x pedido, app próprio** | Fase 2, por definição do escopo priorizado. |
| **Preço, proposta comercial, prazo não aprovado** | Não foram pedidos nesta fase e não existem neste relatório. |

---

## 6. Rodada de qualidade: 284 testes verdes e 4 defeitos fechados

A frente de qualidade (F5) entregou a suíte de testes automatizados depois da primeira versão
deste relatório. Ela **não nasceu verde de propósito** - e é isso que a torna útil.

### 6.1 Evidência atual (rodada real desta frente)

Comando: `.venv/Scripts/python.exe -m pytest -q`, **exit code 0**:

```
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 76%]
....................................................................     [100%]
284 passed in 12.64s
```

Suite real, versionada em `tests/`, sem rede e sem `sleep`. Distribuição por arquivo:

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_extracao.py` | 198 | Extração contra o `manifest.json`: número do pedido, CNPJ, chave, datas, valor total, itens, status e motivos de cada artefato. |
| `tests/test_normalizacao.py` | 57 | CNPJ/chave com DV válido e torto; moeda em centavos inteiros; datas em vários formatos; vazio, lixo e `None`. |
| `tests/test_adversarial.py` | 15 | Injeção de prompt, divergência de soma, documento ilegível, DV inválido. |
| `tests/test_idempotencia.py` | 8 | Mesmo documento 2x, cópia byte a byte (B4), contagem estável em 2 rodadas. |
| `tests/test_ponta_a_ponta.py` | 6 | O comando único e o conteúdo de `.xlsx`, `.csv`, `auditoria.jsonl` e `fila_excecoes.json`. |

Relatório da frente: `tests/RELATORIO-F5.md`. Saída crua: `tests/evidencia/pytest-f5.txt`.

### 6.2 Quantos critérios de aceite os testes cobrem

`tests/test_normalizacao.py` (57) + `tests/test_extracao.py` (198) = **255 dos 284 testes** são
conferência de conteúdo contra a verdade de referência, não teste de fumaça. Os 15 adversariais
cobrem, um por um, os casos que o contrato exige na seção 8: injeção de prompt (B5), divergência de
valor (B2), documento ilegível, CNPJ e chave com DV inválido.

### 6.3 Os 4 defeitos que o QA encontrou - e como cada um foi fechado

A primeira execução da suíte deu **280 passed, 4 failed**. As 4 falhas não eram ruído nem teste mal
escrito: eram defeitos reais, em três frentes diferentes. A regra do contrato é que **quem encontra
não conserta código alheio** - a frente de qualidade reportou, o PO roteou ao dono, o dono corrigiu,
e o PO verificou a correção. O registro abaixo é prova de processo, não é vergonha.

| # | Defeito | Dono do arquivo | Como foi diagnosticado | Correção |
|---|---|---|---|---|
| **D1** | O `manifest.json` da cópia B4 tinha uma **chave de acesso inventada** (`...0011748910120`), diferente da do PDF original (`...0011968201250`) - e o manifest afirma, na própria nota, que a cópia é idêntica em bytes. Um PDF byte a byte idêntico não pode ter duas chaves. | dados sintéticos (F3) | `sha256` dos dois arquivos iguais; texto extraído igual; o teste de referência comparava a extração contra um valor que o documento não contém. A chave errada tinha DV válido - por isso passaria despercebida. | corrigido pelo dono na frente **F3b**: o `esperado` da cópia passou a ser o do original. |
| **D2** | O OCR simulado do caso B1 degradava **`F` no lugar de `E`** (`BFTA`, `CANFTA`), fora do conjunto documentado no contrato (4.3) e no manifest - que listam `0/O`, `1/l/I`, `5/S`, `2/Z`. O manifest exigia do extrator uma recuperação que o contrato não define. | dados sintéticos (F3) / extrator (F1) | as confusões **documentadas** funcionavam (`SUPRIMENT05` -> `SUPRIMENTOS`, CNPJ `49.0l8.909/0OOl-66` -> `49018909000166`); só o `F` não era recuperado. | decidido pelo PO restringir o gerador ao conjunto congelado; corrigido na frente **F3b** (`tools/gerar_mocks.py`), com os mocks regenerados. |
| **D3** | O caso B6 (item sem valor unitário) retornava o motivo **`divergencia_soma_itens`**, quando a soma nem podia ser calculada. O manifest esperava `total_sem_detalhamento`. | persistência (F2) | `decidir()` devolvia `['divergencia_soma_itens']`; o status (`revisao_humana`) e a ausência de linha na planilha já estavam certos. O desacordo era o **código do motivo**, que é contrato. | corrigido pelo dono na frente **F2b**: B6 passou a `total_sem_detalhamento`. Efeito visível na fila: `total_sem_detalhamento` 6 -> 7 e `divergencia_soma_itens` 2 -> 1 (seção 3.6). |
| **extra** | `Artefato.tem_camada_texto` voltava **`True`** no PDF escaneado lido pelo caminho de OCR simulado - o nome do campo sugere "tem camada de texto no PDF", e esse arquivo comprovadamente não tem. | núcleo/ingestão (F1) | registrado pela frente de qualidade nas observações do relatório dela (não reprovava a suíte, mas o rótulo estava enganoso). | corrigido pelo dono na frente **F1c**: `tem_camada_texto=False` no caminho de OCR. |

**Ordem real dos fatos** (carimbos do `monitor.log`, convertidos para -03):
F5 reporta os 3 defeitos às **13:08:17** -> F2b corrige D3 às **13:17:13** -> F3b corrige D1 e D2
às **13:19:46** -> F1c corrige o extra às **13:20:50**.

**Verificação independente desta frente:** a suíte inteira roda verde (284/284, 12,64 s) e o
pipeline, rodado a frio depois de todas as correções, continua estável em **7 linhas em 2 rodadas
sem duplicar** (seções 3.1, 3.2 e 3.3). Nenhuma asserção foi afrouxada, nenhum caso foi removido e
nada foi marcado `xfail` - as três falhas `.py` foram fechadas corrigindo o código, não o teste.

---

## 7. Riscos residuais

| # | Risco | Gravidade | Por que |
|---|---|---|---|
| R1 | **A suíte não cobre carga, rajada nem nota multipágina** | Média | Os 284 testes provam correção funcional (extração, normalização, adversariais, idempotência, ponta a ponta) em 12,6 s. **Nenhum** mede comportamento sob volume, concorrência ou documento multipágina - casos declarados fora do escopo exigido (AD-02, AD-12, AD-13). Passar na suíte não autoriza afirmar que o sistema aguenta a operação real. |
| R2 | **Acurácia do OCR real não medida** | Alta | O caminho foi validado com motor **simulado**. O desempenho com OCR de verdade (scan ruim, baixa resolução, papel torto) é **desconhecido**. Nada aqui autoriza prometer acurácia de OCR real. |
| R3 | **Layout novo de fornecedor** | Alta (esperada) | Extração por rótulo: fornecedor com rótulo diferente cai em revisão. O fluxo de exceção protege o dado, mas gera trabalho manual até a regra ser calibrada. |
| R4 | **Limiares calibrados em 20 artefatos sintéticos** | Média | Os portões de 0,90 / 0,60 foram ajustados neste conjunto. Com volume e variedade reais, precisam ser reconferidos - e isso é decisão de produto. |
| R5 | **Volume real desconhecido** | Média | O dimensionamento do MVP assumiu "até 200 documentos/dia e até 500 mensagens/dia" como **premissa não medida**. SQLite + processo único **não foi validado** nesse volume. |
| R6 | **Dados de fornecedores reais divergem do sintético** | Média | O material cobre 3 fornecedores com formatos parecidos. A variedade real (ver R3) é a variável não testada. |
| R7 | **Acesso à planilha corporativa** | Média | Escrevemos em planilha nossa. A liberação de conta de serviço costuma passar por TI terceirizada e é caminho típico de atraso. |
| R8 | **Verificação da conta WhatsApp na Meta** | Média | Se o cliente partir para WhatsApp real, o processo da Meta é externo e leva de dias a semanas. O Telegram não depende disso. |
| R9 | **Divergência de alvo de infraestrutura (docs 01 vs 04)** | Média | SQLite/processo único vs VPS com Postgres/Redis/MinIO. Adiada por decisão do PO, mas **a decisão de produção continua pendente** e pode mudar o desenho. |
| R10 | **Worktree ativo durante a documentação** | Baixa (de processo) | Este relatório foi escrito em duas passagens: a primeira antes de F5/F1b/F2b/F3b/F1c fecharem, a segunda depois. Todas as evidências das seções 3 e 6 foram **re-executadas** por esta frente com o código já corrigido (rodada fria `20260919-132634`, `pytest -q` e `tools/verificar.py`, todos depois de 13:20:50). O único processo que ainda escreve no worktree é esta documentação. Não sobra artefato medido antes da última correção. |

---

## 8. Definição de pronto da fase - conferência item a item

| # | Critério (contrato, seção 9) | Situação |
|---|---|---|
| 1 | Comando único roda de ponta a ponta sem erro | **Atendido** - exit 0, 0,872s, rodada `20260919-132634` (seção 3.1) |
| 2 | `.xlsx` existe com as 20 colunas e dados reais extraídos; `.csv` equivalente | **Atendido** - 20 colunas, 7 linhas em xlsx **e** csv (seções 3.1 e 3.5) |
| 3 | Rodar de novo: zero linha duplicada (evidência de contagem) | **Atendido** - 7 -> 7 linhas; `tools/verificar.py` PASSOU com 7 `pedido_id` distintos, zero duplicata (seções 3.2 e 3.3) |
| 4 | `auditoria.jsonl` e `fila_excecoes.json` populados | **Atendido** - 20 linhas de auditoria na rodada (cresce para 40 na 2ª rodada, com `rodada_id` por linha); 13 pendências na fila (seções 3.6 e 3.7) |
| 5 | `python -m pytest -v` verde, com saída colada | **Atendido** - `.venv/Scripts/python.exe -m pytest -q` -> **284 passed in 12.64s**, exit 0 (seção 6.1). Na primeira execução da suíte foram 280 passed / 4 failed, com 3 defeitos reais reportados e corrigidos pelos donos (seção 6.3) |
| 6 | PDF escaneado entra pelo OCR; B2 **não** entra na planilha | **Atendido** - motor `ocr_simulado` rotulado, confiança 0,65, resultado `revisao`, sem auto-aprovação; B2 na fila com `divergencia_soma_itens` e **sem linha** na planilha (seções 3.7 e 3.8) |
| 7 | README com o que faz, como instalar, gerar mocks, rodar e testar | **Atendido** - `README.md`: seções 1 (o que faz), 2 (arquitetura), 3 (instalar), 4 (gerar mocks), 5 (rodar), 6 (testar) |
| 8 | Relatório final em `relatorios/` | **Atendido** - este arquivo e `relatorios/CRONOGRAMA.md` |
| 9 | Zero segredo em texto no repositório | **Atendido** - nenhuma chave, token ou senha foi usada ou gravada; não há `.env` no repositório (varredura por padrões de chave/token/senha em `.py/.md/.txt/.json/.jsonl/.sh`, fora de `.venv`: nenhuma ocorrência) |

**Resultado: 9 de 9 critérios atendidos.**

O item 5 é o que mudou em relação à primeira versão deste relatório: naquele momento a frente de
qualidade ainda não havia entregado e o critério estava marcado como **não atendido**, com o
registro honesto do bloqueio. O quadro mudou, a suíte chegou, quatro defeitos foram encontrados e
fechados, e este relatório foi reescrito com a evidência nova - não com a intenção de fechar a
tabela.

**Ressalva que a tabela não deve esconder:** "9 de 9" vale para a definição de pronto **desta
fase**, com **dados sintéticos**. Ela não diz nada sobre a operação real do cliente. Os riscos
residuais da seção 7 (acurácia de OCR real, volume, layout de fornecedor novo, planilha
corporativa, infraestrutura de produção) continuam abertos e são o que separa esta entrega de um
go-live.

---

*Nenhum número deste relatório foi estimado ou arredondado "para ficar melhor". Onde um número
não pôde ser medido, está escrito que não pôde.*
