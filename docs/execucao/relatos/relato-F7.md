# Relato F7 - configuracao `.env` e CLI de producao (dono: avareza, card PROJ-20)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (secoes 2, 3.1, 3.6, 5, 6) e `docs/execucao/spec-F7.md`.
Data da execucao: 2026-09-19. Worktree: `squad-pecados` (branch `squad-pecados`).
Interpretador: `.venv/Scripts/python.exe` (CPython 3.12.14). Nenhum comando `git` foi rodado.

## 1. Arquivos entregues (somente os meus)

| Arquivo | Situacao | Tamanho |
| -- | -- | -- |
| `app/config.py` | **novo** - secao 3.1 do contrato | 24.254 bytes |
| `app/run.py` | **ajustado** - secao 3.6 do contrato | 13.496 bytes |

Nao toquei em `app/canais.py`, `app/contratos.py`, `app/pipeline.py`, `app/ingress.py`,
`app/persistencia.py`, `app/normaliza.py`, `app/revisao.py`, `app/extracao.py`, `tools/*`,
`tests/*`, `.env.example`, `README.md`, `AGENTS.md` nem `docs/execucao/00b-*.md`.

## 2. Evidencia obrigatoria

### (1) Comando unico no modo padrao

```
$ .venv/Scripts/python.exe -m app.run --mock

==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Modo     : mock | config: nenhum .env (padrao)
Inbox    : data\mocks
Saida    : data\out
Banco    : data\out\pipeline.db
Rodada   : 20260919-134836
--------------------------------------------------------------
Artefatos ingeridos : 20 (pdf 12 | mensagens 8)
Auto-aprovados      : 0
Em revisao humana   : 0
Rejeitados          : 0
Deduplicados        : 20
Linhas na planilha  : 7
--------------------------------------------------------------
Leitura por motor   : ocr_simulado 1 | parser 8 | pdfplumber 11
OCR                 : 1 artefato(s) lido(s) por OCR SIMULADO (sidecar .ocr.txt): a leitura nao vem de motor de OCR real e esta marcada como simulada.
Auditoria           : 20 linha(s) nesta rodada | trilha cumulativa: 420 linha(s)
--------------------------------------------------------------
Arquivos gerados:
   xlsx              data\out\controle_financeiro.xlsx
   csv               data\out\controle_financeiro.csv
   auditoria         data\out\auditoria.jsonl
   auditoria_rodada  data\out\auditoria_rodada_20260919-134836.jsonl
   fila_excecoes     data\out\fila_excecoes.json
   painel            data\out\painel.html
   resumo            data\out\resumo.json
   db                data\out\pipeline.db
==============================================================
Rodada concluida em 0.772s
exit=0
```

O resumo da fase 2 esta preservado (mesmas linhas de antes); o modo mock continua sendo o
padrao e nao exige credencial nenhuma. (`Auto-aprovados 0 / Deduplicados 20` porque a inbox
ja havia sido processada nas rodadas anteriores - idempotencia, nao defeito.)

### (2) Modo real sem `.env` - mensagem clara, sem traceback, codigo 2

```
$ .venv/Scripts/python.exe -m app.run --real

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
exit=2
```

Cinco variaveis citadas pelo nome, com onde obter; **nenhum** valor de segredo, nenhum
traceback, pipeline **nao** executado (nao ha arquivo de saida novo em `data/out`).

### (3) `--check-config`

Sem `.env` nenhum (configuracao padrao, mock):

```
$ .venv/Scripts/python.exe -m app.run --check-config

Configuracao do pipeline
----------------------------------------
Modo de execucao : mock  (padrao, dados sinteticos)
Arquivo .env     : (nao configurado)
Canais ativos    : (nao configurado) (modo mock nao coleta)
Inbox            : data\mocks
Saida            : data\out
Banco            : data\out\pipeline.db
Log              : logs/pipeline-AAAAMMDD.log (nivel INFO)

Telegram
  api_base        : https://api.telegram.org
  bot token       : (nao configurado)
  chat_id         : (nao configurado)
  timeout_s       : 30

WhatsApp
  api_base        : https://graph.facebook.com/v21.0
  token           : (nao configurado)
  phone_number_id : (nao configurado)
  verify_token    : (nao configurado)
  webhook_dir     : data\inbox_webhook\whatsapp

Valores sensiveis aparecem mascarados (ultimos 4 caracteres). Nenhum segredo vai para log, resumo ou mensagem de erro.
exit=0
```

Com `.env` FICTICIO em diretorio temporario (`--env`, nunca na raiz do projeto). O arquivo
usa de proposito as sintaxes toleradas pela secao 3.1: comentario `#`, espacos em volta do
`=`, prefixo `export ` e aspas:

```
# conteudo do .env FICTICIO usado (valores inventados, marcados como ficticios)
MODO_EXECUCAO=real
  CANAIS_ATIVOS = whatsapp, telegram
export LOG_LEVEL="DEBUG"
TELEGRAM_BOT_TOKEN=<FICTICIO-NAO-E-SEGREDO-...-1234>
TELEGRAM_CHAT_ID=-1000000000000
WHATSAPP_TOKEN=<FICTICIO-NAO-E-SEGREDO-...-5678>
WHATSAPP_PHONE_NUMBER_ID=000000000000000
WHATSAPP_VERIFY_TOKEN=<FICTICIO-NAO-E-SEGREDO-...-oken>
```

```
$ .venv/Scripts/python.exe -m app.run --check-config --env <tmp>/.env

Configuracao do pipeline
----------------------------------------
Modo de execucao : real
Arquivo .env     : <local>\AppData\Local\Temp\f7_env\.env
Canais ativos    : whatsapp, telegram
Inbox            : data\inbox
Saida            : data\out
Banco            : data\out\pipeline.db
Log              : logs/pipeline-AAAAMMDD.log (nivel DEBUG)

Telegram
  api_base        : https://api.telegram.org
  bot token       : ****1234
  chat_id         : -1000000000000
  timeout_s       : 30

WhatsApp
  api_base        : https://graph.facebook.com/v21.0
  token           : ****5678
  phone_number_id : 000000000000000
  verify_token    : ****oken
  webhook_dir     : data\inbox_webhook\whatsapp

Valores sensiveis aparecem mascarados (ultimos 4 caracteres). Nenhum segredo vai para log, resumo ou mensagem de erro.
exit=0
```

Sensiveis mascarados (`****` + ultimos 4); `INBOX_DIR` assumiu o padrao do modo real
(`data/inbox`); sintaxe tolerada confirmada (`export`, aspas, espacos, comentario).

### (3b) Precedencia e caminho de erro (F7 spec)

```
$ MODO_EXECUCAO=mock .venv/Scripts/python.exe -m app.run --check-config --env <tmp>/.env
Modo de execucao : mock  (padrao, dados sinteticos)      <- ambiente do processo venceu o .env (que dizia real)

$ .venv/Scripts/python.exe -m app.run --mock --check-config --env <tmp>/.env
Modo de execucao : mock  (padrao, dados sinteticos)      <- flag --mock venceu o .env

$ .venv/Scripts/python.exe -m app.run --check-config --env <tmp>/nao_existe.env
arquivo de configuracao nao encontrado: C:\...\f7_env\nao_existe.env
confira o caminho passado em --env ou deixe o arquivo .env na raiz do projeto
exit=2
```

### (3c) Modo real com coleta - ciclo completo contra stub HTTP local (sem rede externa)

Stub `http.server` em `127.0.0.1:8799` (arquivo temporario, fora do repo) respondendo
`getUpdates` com um update FICTICIO; `.env` de teste com `TELEGRAM_API_BASE=http://127.0.0.1:8799`,
`CANAIS_ATIVOS=telegram`, `INBOX_DIR/OUT_DIR/DB_PATH/LOG_DIR` em diretorio temporario:

```
$ .venv/Scripts/python.exe -m app.run --real --env <tmp>/.env.real

==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Modo     : real | canais: telegram | config: <local>\AppData\Local\Temp\f7_env\.env.real
Coleta   : telegram: 1 mensagem(ns) em <local>\AppData\Local\Temp\f7_env\inbox\telegram\telegram_coleta_20260919-135010.jsonl
Inbox    : <local>\AppData\Local\Temp\f7_env\inbox
Saida    : <local>\AppData\Local\Temp\f7_env\out
Banco    : <local>\AppData\Local\Temp\f7_env\out\pipeline.db
Rodada   : 20260919-135010
--------------------------------------------------------------
Artefatos ingeridos : 1 (pdf 0 | mensagens 1)
Auto-aprovados      : 0
Em revisao humana   : 1
Rejeitados          : 0
Deduplicados        : 0
Linhas na planilha  : 0
--------------------------------------------------------------
Leitura por motor   : parser 1
OCR                 : nenhum artefato usou OCR simulado nesta rodada
Auditoria           : 1 linha(s) nesta rodada | trilha cumulativa: 1 linha(s)
--------------------------------------------------------------
Motivos na fila de excecoes:
   total_sem_detalhamento             1
--------------------------------------------------------------
Arquivos gerados:
   xlsx              C:\...\f7_env\out\controle_financeiro.xlsx
   csv               C:\...\f7_env\out\controle_financeiro.csv
   auditoria         C:\...\f7_env\out\auditoria.jsonl
   auditoria_rodada  C:\...\f7_env\out\auditoria_rodada_20260919-135010.jsonl
   fila_excecoes     C:\...\f7_env\out\fila_excecoes.json
   painel            C:\...\f7_env\out\painel.html
   resumo            C:\...\f7_env\out\resumo.json
   db                C:\...\f7_env\out\pipeline.db
==============================================================
Rodada concluida em 0.243s
exit=0
```

Envelope gravado pela coleta (mesmo formato do mock, `ensure_ascii=False`):

```
$ cat <tmp>/inbox/telegram/telegram_coleta_20260919-135010.jsonl
{"update_id": 555000111, "message": {"message_id": 9001, "from": {"id": 777000111, "is_bot": false, "first_name": "Operador", "username": "operador_ficticio"}, "chat": {"id": -1000000000000, "title": "Compras Ficticias", "type": "group"}, "date": 1774000000, "text": "PEDIDO N: 7001 fechado com a Alfa, emitido em 20/03/2026, valor total R$ 123,45"}}
```

Log em arquivo (`<LOG_DIR>/pipeline-20260919.log`, append):

```
2026-09-19 13:50:10 INFO    rodada iniciada: modo=real config=C:\...\f7_env\.env.real canais=telegram
2026-09-19 13:50:10 INFO    db                C:\...\f7_env\out\pipeline.db
2026-09-19 13:50:10 INFO ==============================================================
2026-09-19 13:50:10 INFO Rodada concluida em 0.243s
2026-09-19 13:50:10 INFO rodada concluida; log em C:\...\f7_env\logs\pipeline-20260919.log
```

### (4) Suite de testes

```
$ .venv/Scripts/python.exe -m pytest -q
........................................................................ [ 76%]
....................................................................     [100%]
284 passed in 13.33s
exit=0
```

284 testes (a suite da fase 2 segue verde). Os testes novos das frentes F10
(`tests/test_config.py`, `tests/test_canais.py`, `tests/test_producao.py`) ainda **nao**
existem no worktree; a contagem final do aceite 3 depende da entrega de F10.

## 3. Observacoes honestas

1. **Chamada de rede involuntaria (declarada).** Ao testar `--real` com um `.env` FICTICIO,
   o `app/canais.py` (F8, entregue durante esta execucao) fez a chamada real
   `GET https://api.telegram.org/bot<token-ficticio>/getUpdates` e recebeu `HTTP 404`.
   Nenhuma credencial real, nenhum servico pago, nenhum custo; o produto reagiu como manda
   a secao 3.2 (`ErroCanal` + mensagem clara + exit 2). Nao repeti o teste: a prova do modo
   real passou a usar o stub local `127.0.0.1` (item 3c), como o contrato D4 preve.
2. **`.env` na arvore de trabalho:** nenhum (`find . -name .env` fora de `.venv` volta
   vazio). Os `.env` de teste ficaram em diretorio temporario e foram usados via `--env`.
3. **Nenhum `git`:** nao rodei `git` em nenhum momento (nem `status`).
4. **`logs/`:** o diretorio de log padrao (`LOG_DIR=logs`) passou a existir na raiz quando
   o comando rodou; o conteudo e `pipeline-<AAAAMMDD>.log`, coberto por `*.log` no
   `.gitignore` (arquivo do F9).
5. **`mascarar()`:** valor com menos de 8 caracteres vira `****` (os 4 ultimos seriam quase
   o segredo inteiro). Com 8+ caracteres: `****` + ultimos 4.
6. **Import defensivo de `canais`:** o `run.py` continua funcionando se `app/canais.py`
   faltar (mensagem clara, exit 2, sem traceback). Como o F8 entregou o modulo durante esta
   execucao, o caminho exercitado foi o de integracao real (item 3c).

## 4. O que ficou de fora (e por que)

* **`.env.example` (dono F9)** - ainda nao existe no worktree, entao nao foi possivel
  conferir a sincronia catalogo x arquivo (contrato D6). O texto esta pronto e testado do
  meu lado: `config.exemplo_env()` devolve exatamente as **16** variaveis do catalogo, na
  ordem, terminando em `\n`, com os campos de segredo vazios e marcados como SEGREDO.
  Basta o F9 materializar com `tools/gerar_env_example.py`.
* **Testes novos do aceite 3** - pertencem ao F10; a contagem "284 + novos" sera fechada la.
* **Webhook do WhatsApp** (`ler_webhook_whatsapp`, `tools/receber_webhook_whatsapp.py`) -
  nao exercitei: e do F8/F9. A CLI ja entrega a coleta dos dois canais via `canais.coletar`.
* **README de producao** - F11.
