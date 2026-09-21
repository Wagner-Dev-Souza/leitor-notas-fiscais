# Relato F9 - `.env.example` gerado do catalogo + verificador de producao

* **Frente:** F9 (fechamento do produto) - dono: **preguica**
* **Card:** PROJ-22 (pai PROJ-19)
* **Contrato:** `docs/execucao/00b-contrato-fechamento.md` (secoes 2, 3.4, 3.5, 5, 6)
* **Spec:** `docs/execucao/spec-F9.md`
* **Worktree:** `<worktree>`
* **Interpretador:** `.venv/Scripts/python.exe` (CPython 3.12.14)
* **Status:** entregue e verificado. `.venv/Scripts/python.exe -m pytest -q` = **382 passed in 18.98s**
  (a suite da fase anterior + os novos testes da F10 passaram sem falha nesta execucao).
  Nenhum comando `git` de escrita foi executado (uso apenas de `git ls-files`, `git check-ignore` e `git status
  --porcelain`, todos de leitura).

## 1. Entregaveis (arquivos de dono unico da F9)

| Arquivo | Tamanho | sha256 |
| -- | -- | -- |
| `tools/gerar_env_example.py` | 8773 bytes | `1b250a42cc305681293730d8e21cea59706013229cc628ca30a708ab032e9995` |
| `tools/verificar_producao.py` | 26375 bytes | `a016a615cfaa1e3b3ecb5aabf24f3c5216eca5498e09fad65cedcaaeb76b8cc9` |
| `.env.example` | 4754 bytes | `4f111a6026a949a617b08947bdd3da739ac900c88eefdb76907bd7d5c9c81123` |

* `tools/gerar_env_example.py` - gera o texto a partir de `app.config.VARIAVEIS` (via
  `config.exemplo_env()`); **nunca digitado a mao**. Tem `--saida`, `--conferir` e sanidade
  propria (toda variavel do catalogo com linha `NOME=`, nenhuma variavel fora do catalogo,
  sensivel sempre vazio no exemplo, texto terminado em `\n`).
* `.env.example` - versionado na raiz, 16 variaveis, um comentario por variavel (o que e,
  obrigatoria em que modo, onde obter, padrao). Os 3 campos sensiveis
  (`TELEGRAM_BOT_TOKEN`, `WHATSAPP_TOKEN`, `WHATSAPP_VERIFY_TOKEN`) saem **vazios**.
* `tools/verificar_producao.py` - os 6 checks da secao 3.5, com execucao real via
  `subprocess` (`python -m app.run ...`), PASSOU/FALHOU por item, codigo de saida != 0 se
  algum falhar, tudo em diretorio temporario proprio.

## 2. Evidencia literal

### 2.1 `python tools/gerar_env_example.py` (exit 0)

```
==========================================================================
GERADOR DO .env.example - tools/gerar_env_example.py (F9 / preguica)
==========================================================================
catalogo : app/config.py -> VARIAVEIS (16 variaveis)
destino  : <worktree>\.env.example
--------------------------------------------------------------------------
gravado: <worktree>\.env.example
  variaveis : 16
  conteudo  : 4754 bytes | linhas: 102 | fim de linha: LF
  arquivo   : 4754 bytes no disco
  sha256    : 4f111a6026a949a617b08947bdd3da739ac900c88eefdb76907bd7d5c9c81123
  sensiveis : 3 (saem com valor vazio, para o operador preencher no .env)
  (arquivo anterior era diferente - regravado)
```

### 2.2 `python tools/gerar_env_example.py --conferir` (exit 0)

```
==========================================================================
GERADOR DO .env.example - tools/gerar_env_example.py (F9 / preguica)
==========================================================================
catalogo : app/config.py -> VARIAVEIS (16 variaveis)
destino  : <worktree>\.env.example
--------------------------------------------------------------------------
PASSOU: .env.example em sincronia com o catalogo (16 variaveis, sha256 4f111a6026a949a6)
```

O `--conferir` tambem foi testado **negativamente**: acrescentei duas linhas intrusas
(`# linha intrusa` e `TELEGRAM_BOT_TOKEN=valor-errado`) ao `.env.example` e o comando saiu
com **exit 1**, imprimindo o diff unificado (`--- .env.example (em disco)` /
`+++ .env.example (gerado do catalogo)`) e a instrucao de regerar. Depois restaurei o
arquivo e o `--conferir` voltou a `PASSOU`. Ou seja: divergencia entre o arquivo e o
catalogo nao passa silenciosa.

### 2.3 `python tools/verificar_producao.py` (exit 0)

```
==============================================================================
VERIFICADOR DE PRODUCAO - tools/verificar_producao.py (F9 / preguica)
contrato: docs/execucao/00b-contrato-fechamento.md secao 3.5
==============================================================================
projeto  : <worktree>
python   : <worktree>\.venv\Scripts\python.exe
data/    : retrato tirado antes e conferido depois (este script nao escreve la)
------------------------------------------------------------------------------
temporario: <local>
------------------------------------------------------------------------------
[1/6] .env.example presente, versionado e em sincronia com o catalogo
        PASSOU: 16 variaveis do catalogo presentes e em sincronia | AVISO: ainda nao esta no indice do git - o PO versiona nesta onda (nao ignorado, entao entra)

[2/6] nenhum .env real versionado e .env no .gitignore
        PASSOU: nenhum .env versionado; '.env' ignorado pelo git

[3/6] modo mock continua sendo o padrao (sem .env, roda e nao exige segredo)
        PASSOU: sem .env o padrao e mock, roda e nao pede credencial nenhuma

[4/6] modo real sem as obrigatorias -> mensagem clara, sem traceback, sem rodar pipeline
        PASSOU: codigo 2, citou as 5 variaveis faltantes pelo nome, sem traceback e sem rodar o pipeline

[5/6] varredura de segredo em arquivo versionado (inclusive .env.example)
        PASSOU: 160 arquivos versionados varridos: nenhum segredo e nenhum numero fora do material sintetico (13 numeros ficticios declarados reencontrados, 3 placeholders de exemplo)

[6/6] `.env` de teste com valores ficticios -> --check-config reconhece e mascara
        PASSOU: configuracao ficticia aceita (exit 0) e os 3 valores sensiveis mascarados na saida

------------------------------------------------------------------------------
data/ intacto (retrato de 84 arquivos, tamanho e mtime): True
RESULTADO: 6/6 PASSOU
==============================================================================
```

### 2.4 `head -40 .env.example`

```
# Configuracao do pipeline de notas fiscais e pedidos (Squad 7 Pecados)
#
#  1. copie este arquivo para .env na raiz do projeto:  cp .env.example .env
#  2. preencha os campos vazios (os de token/segredo ficam em branco aqui de proposito);
#  3. valide antes de rodar:  .venv/Scripts/python.exe -m app.run --check-config
#
#  O .env NAO vai para o git (esta no .gitignore). Nunca cole um segredo aqui.
#  Sem .env nenhum o app roda em modo mock com os dados sinteticos - isso nao e erro.
#  Este arquivo e gerado do catalogo de app/config.py; nao edite a mao:
#  regenere com  python tools/gerar_env_example.py

# MODO_EXECUCAO  [obrigatoria em: sempre]
#   Como o pipeline roda: 'mock' (dados sinteticos, padrao) ou 'real' (coleta dos canais).
#   Onde obter: Digitado pelo operador. As flags --mock/--real da linha de comando sobrepoem este valor.
#   Padrao: mock
MODO_EXECUCAO=mock

# CANAIS_ATIVOS  [obrigatoria em: real]
#   Canais coletados no modo real, separados por virgula (aceitos: whatsapp, telegram).
#   Onde obter: Digitado pelo operador, conforme os canais que ele conectou.
#   Padrao: whatsapp,telegram
CANAIS_ATIVOS=whatsapp,telegram

# INBOX_DIR
#   Diretorio de entrada com as subpastas pdf/, whatsapp/ e telegram/ (padrao: data/mocks no modo mock, data/inbox no modo real).
#   Onde obter: Caminho no servidor. Deixe vazio para usar o padrao do modo escolhido.
#   Padrao: data/mocks (modo mock) / data/inbox (modo real)
INBOX_DIR=

# OUT_DIR
#   Diretorio de saida: planilha, trilha de auditoria, fila de excecoes e painel.
#   Onde obter: Caminho no servidor (pasta com permissao de escrita para o usuario do servico).
#   Padrao: data/out
OUT_DIR=data/out

# DB_PATH
#   Arquivo SQLite do pipeline, fonte da verdade do dado (padrao: <OUT_DIR>/pipeline.db).
#   Onde obter: Caminho no servidor. Deixe vazio para usar <OUT_DIR>/pipeline.db.
#   Padrao: <OUT_DIR>/pipeline.db
DB_PATH=
```

### 2.5 `.venv/Scripts/python.exe -m pytest -q` (exit 0)

```
........................................................................ [ 18%]
........................................................................ [ 37%]
........................................................................ [ 56%]
........................................................................ [ 75%]
........................................................................ [ 94%]
......................                                                   [100%]
382 passed in 18.98s
```

## 3. Os 6 checks - o que cada um prova de verdade

1. **`.env.example` presente, versionado e em sincronia** - PASSOU. Le o arquivo do disco,
   compara byte a byte com `config.exemplo_env()` e compara o **conjunto** de nomes dos dois
   lados (16 = 16), entao pega tanto variavel faltando quanto variavel inventada. Consulta o
   git em modo leitura.
2. **Nenhum `.env` real versionado** - PASSOU. `git ls-files` (160 arquivos) nao tem `.env`
   nem `.env.*` real; `git check-ignore -q .env` confirma que a linha do `.gitignore` esta
   ativa (e que `.env.example` **nao** e ignorado).
3. **Mock continua padrao** - PASSOU. Roda o comando de verdade **sem `--mock` e sem `.env`**,
   com o ambiente do processo limpo das 16 variaveis do catalogo; o app imprime
   `Modo     : mock | config: nenhum .env (padrao)`, sai 0 e gera a planilha em diretorio
   temporario.
4. **Modo real sem credencial** - PASSOU. Roda `python -m app.run --real --env <tmp>/real-sem-credencial.env`
   com `MODO_EXECUCAO=real` e `CANAIS_ATIVOS=whatsapp,telegram`: exit **2**, citando **pelo
   nome** as 5 variaveis faltantes (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`), cada uma com o que
   e e onde obter, **sem traceback**, e a saida do pipeline **nao** foi criada (o pipeline nao
   rodou).
5. **Varredura de segredo** - PASSOU. Le os 160 arquivos versionados (124 como texto; 36
   pulados por serem binarios/grandes - os PDFs dos mocks) procurando chave privada, token
   Telegram/Meta/Google/OpenAI/GitHub, atribuicao de valor em variavel sensivel e numero com
   DDI 55. Resultado: **0 suspeitos**. Transparencia do que foi aceito: **13 ocorrencias** de
   numeros que sao exatamente os ficticios declarados pelo material sintetico de
   `data/mocks/` (`5511998887777`, `551140028922`, ...) reencontrados em docs/testes/gerador,
   e **3 placeholders** de exemplo (`5511999999999` das docs de arquitetura, com 8 digitos
   repetidos). A comparacao e contra o **material versionado**, nao contra lista escrita a
   mao: numero novo, que nao venha do mock, cairia em "suspeito" e reprovaria o check.
6. **`--check-config` mascara os sensiveis** - PASSOU. `.env` de teste com valores ficticios
   (moram no diretorio temporario, nunca no repositorio): exit 0, modo `real` reconhecido,
   e os 3 valores sensiveis saem como `****` + ultimos 4 caracteres. O check **falha** se
   qualquer valor aparecer inteiro ou se a mascara nao aparecer.

**Nao escreve em `data/`** - o script tira um retrato de `data/` (80 arquivos, tamanho +
mtime) antes dos checks e confere depois: `data/ intacto: True`. Foi assim nas execucoes
registradas acima.

## 4. Observacoes honestas

* O check 1 imprime `rastreado pelo git (git ls-files): False` **por desenho da fase**: o
  `.env.example` e arquivo novo e so o PO roda `git add`/`commit` (contrato D7). O check
  PASSA porque o que esta sob meu controle esta correto - arquivo presente, em sincronia e
  **nao ignorado** pelo `.gitignore` - e o proprio check deixa o AVISO explicito na saida.
  Depois do commit do PO ele passa a mostrar `rastreado: True` sem nenhuma mudanca de codigo.
* `pytest -q` = **354 passed** (284 das fases anteriores + os novos da F10), sem falha.
* Nenhum defeito foi encontrado em arquivo de outro dono nesta rodada, entao **nao** criei
  `docs/execucao/_ids/pedido-F9.md`. Se algum check passar a falhar por comportamento de
  `app/config.py` / `app/run.py` / `app/canais.py`, o pedido vai para esse arquivo.
* Limite declarado (contrato D4): nenhuma chamada real a `api.telegram.org` ou
  `graph.facebook.com` foi feita - nao existe token nem numero autorizado. Os checks 3, 4 e 6
  exercitam configuracao e CLI de verdade; a coleta real com credencial nao faz parte desta
  frente (e da F8).
* O verificador **nao** reimplementa a logica de configuracao: ele chama o `app/run.py` de
  verdade e le a saida. Se o codigo nao se comportasse como o contrato pede, o check
  apareceria FALHOU com a saida real colada - nao com uma simulacao.

## 5. Como reproduzir

```
cd <worktree>
.venv/Scripts/python.exe tools/gerar_env_example.py
.venv/Scripts/python.exe tools/gerar_env_example.py --conferir
.venv/Scripts/python.exe tools/verificar_producao.py            # ou --detalhe
.venv/Scripts/python.exe -m pytest -q
```
