# Relato F8 - coleta real dos canais (Telegram getUpdates + receptor de webhook WhatsApp)

Frente: **F8** - dono: **gula**. Card: PROJ-21 (pai PROJ-19). Contrato: `docs/execucao/00b-contrato-fechamento.md`
(secoes 3.2 e 3.3). Spec: `docs/execucao/spec-F8.md`.

## Arquivos entregues

| Arquivo | O que e |
| -- | -- |
| `app/canais.py` (novo) | coleta dos canais: `TransporteHTTP` injetavel, `transporte_urllib()`, `envelopes_telegram()`, `coletar_telegram()`, `ler_webhook_whatsapp()`, `coletar()`, `ErroCanal`, `ResultadoColeta`. Somente biblioteca padrao. |
| `tools/receber_webhook_whatsapp.py` (novo) | receptor local do webhook do WhatsApp Cloud API (`http.server`): `GET` de verificacao (200 com o challenge / 403), `POST` grava o envelope, `--uma-vez`. |
| `docs/execucao/_ids/relato-F8.md` (este) | evidencia de execucao real. |
| `docs/execucao/_ids/f8_prova.py` (novo) | harness da prova - copiado do temp para a pasta de evidencia, para a prova ser reproduzivel depois desta sessao. Usa so valores FICTICIOS e aponta tudo para `127.0.0.1`. |

Nenhum arquivo de outro dono foi tocado. **Nenhum comando `git` foi executado.** Nenhuma
dependencia nova (`urllib`, `http.server`, `json`, `pathlib`, `datetime` - tudo stdlib), entao
`requirements.txt` nao muda.

Alem de `ErroCanal` (o unico erro publico da secao 3.2), `app/canais.py` tem dois erros
internos usados pelo transporte real: `ErroHTTP` (carrega `status`, nunca a URL) e
`ErroRede`. Eles nunca chegam ao chamador - `coletar_telegram`/`coletar` os convertem em
`ErroCanal` com mensagem pt-BR. O QA pode testa-los se quiser, mas o contrato so promete
`ErroCanal`.

## O que foi provado com execucao real

1. **Telegram**: `coletar_telegram()` monta `GET {api_base}/bot<token>/getUpdates` e grava
   `<inbox>/telegram/telegram_coleta_<AAAAMMDD-HHMMSS>.jsonl`, um update por linha, no formato
   de `data/mocks/telegram/*.jsonl`. A prova usa o **transporte real (`urllib`)** apontado para
   um **stub HTTP em `127.0.0.1`**; o envelope gravado e comparado byte a byte com o update da
   API. O filtro por `chat_id` (local, porque `getUpdates` nao aceita `chat_id`) descartou o
   update de outro chat. Sem update novo -> `arquivos=()` com detalhe, sem erro. Stub devolvendo
   `HTTP 401` -> `ErroCanal` citando `TELEGRAM_BOT_TOKEN` e o status, **sem o token**.
2. **WhatsApp**: o receptor sobe de verdade em subprocesso (`--uma-vez`), responde `403` para
   `hub.verify_token` errado, `200` com o `hub.challenge` para o token certo, grava o `POST` em
   `<WHATSAPP_WEBHOOK_DIR>/<AAAAMMDD-HHMMSS>_<n>.json` e encerra. Cada requisicao vira uma linha
   de log; o teste confere que nem o verify token nem os tokens de API aparecem no stdout.
   `ler_webhook_whatsapp()` leva o envelope para `<inbox>/whatsapp/whatsapp_coleta_<...>.jsonl` e
   move o arquivo consumido para `processados/`.
3. **Pipeline sem alteracao**: `python -m app.run --inbox <temp> --out <temp> --db <temp>` digeriu
   a inbox coletada e contou **2 mensagens** (`mensagens=2`, motor `parser`), sem tocar em
   `app/ingress.py`/`app/pipeline.py`.
4. **Suite da fase 2 segue verde**: `pytest -q` = **284 passed**.

## O que NAO foi provado (e por que) - observacao honesta

* **Chamada credenciada real** a `api.telegram.org` ou `graph.facebook.com` **nao foi executada**
  (decisao D4 do contrato: nao existe token nem numero autorizado nesta entrega; nada de chave
  nova ou servico pago). O que esta provado e a montagem da requisicao, a gravacao do envelope e
  o ciclo completo contra stub local. Nada aqui e apresentado como chamada real.
* **Assinatura `X-Hub-Signature-256` do webhook nao e validada**: o catalogo congelado de
  variaveis (`app/config.py: VARIAVEIS`) nao tem o *app secret* da Meta. Em producao, com o app
  secret configurado, o `POST` precisa ser validado antes de gravar o arquivo - recomendo tratar
  isso como item da proxima fase (nao inventei variavel nova para nao quebrar a fonte unica D6).
* O WhatsApp real tambem exige *webhook publico* (HTTPS/tunel) para o Meta alcancar o receptor;
  nesta entrega ele escuta em `127.0.0.1` (uso local), como o contrato pede.

## Observacoes para o PO (fora do meu escopo - nao toquei em nada disso)

1. `logs/` na raiz do repo: o `app/run.py` (F7) grava `<LOG_DIR>/pipeline-<AAAAMMDD>.log` com
   `LOG_DIR` padrao `logs`, e o `.gitignore` atual cobre `.env` mas **nao** cobre `logs/`.
   Hoje existe `logs/pipeline-20260919.log` no worktree. Se o PO commitar assim, entra log de
   execucao no repositorio - sugestao: linha `logs/` no `.gitignore` (arquivo do F9/preguica).
   Meu harness passou a apontar `LOG_DIR` para o temporario justamente para nao aumentar isso.
2. Assinatura do webhook da Meta (`X-Hub-Signature-256`) nao validada - falta o *app secret* no
   catalogo congelado. Recomendo tratar como item da proxima fase (nao inventei variavel).
3. `app/run.py` no modo real ja importa `app/canais.py` e usa `canais.coletar(cfg)`; a prova 5
   mostra esse caminho rodando ponta a ponta (com a `api_base` no stub local).

## Evidencia 1 - prova dos canais (harness com stub local; saida literal, exit=0)

Comando: `.venv/Scripts/python.exe %LOCALAPPDATA%/Temp/f8_prova.py`
(arquivo do harness: `%LOCALAPPDATA%/Temp/f8_prova.py`; todo trafego vai para 127.0.0.1.
O texto abaixo e a saida real, colada sem edicao.)

```text
== 0. configuracao carregada do modulo real de F7 (app/config.py) ==
   modo            : real (modo_real=True)
   canais          : ('whatsapp', 'telegram')
   inbox / out     : inbox / out
   telegram api    : http://127.0.0.1:64163
   token telegram  : ****ESTE
   token whatsapp  : ****ESTE
   verify token    : ****ESTE
   webhook dir     : <local>
  [OK ] config real carregada em modo real
  [OK ] canais ativos = whatsapp,telegram

== 1. coleta Telegram: transporte REAL (urllib) contra stub em 127.0.0.1 ==
  [stub 127.0.0.1:64163] GET /bot<TOKEN>/getUpdates
   canal=telegram mensagens=1 destino=telegram
   arquivos=['telegram_coleta_20260919-135215.jsonl']
   detalhe : telegram: 1 update(s) gravado(s) em telegram_coleta_20260919-135215.jsonl
--- cat do envelope gravado (um update por linha) ---
{"update_id": 500001, "message": {"message_id": 9001, "from": {"id": 424242, "is_bot": false, "first_name": "Jose", "username": "jose_compras"}, "chat": {"id": -1001234567890, "title": "Compras Fornecedores", "type": "group"}, "date": 1773835200, "text": "PEDIDO N: 6201 confirmado com a Alfa Pecas, emitido em 18/03/2026, valor total R$ 1.234,56. Pagamento por PIX."}}
  [OK ] gravou 1 arquivo de coleta
  [OK ] gravou 1 update (filtro por chat_id descartou o outro chat)
  [OK ] envelope identico ao update da API
  [OK ] update de outro chat nao foi gravado
  [OK ] nome do arquivo no padrao telegram_coleta_<AAAAMMDD-HHMMSS>.jsonl

== 1b. sem update novo: nao e erro ==
  [stub 127.0.0.1:64163] GET /bot<TOKEN>/getUpdates
   arquivos=() mensagens=0 detalhe=telegram: getUpdates sem update novo (fila vazia ou nenhum update do chat configurado) - nada a gravar, e nao e erro
  [OK ] sem update -> arquivos=() e detalhe explicativo

== 1c. falha HTTP do canal: ErroCanal claro, sem token ==
  [stub 127.0.0.1:64163] GET /bot<TOKEN>/getUpdates
   ErroCanal: telegram: getUpdates recusado em http://127.0.0.1:64163 (HTTP 401 Unauthorized). Confira TELEGRAM_BOT_TOKEN (credencial recusada) no .env - nenhuma credencial e impressa aqui.
  [OK ] falha 401 vira ErroCanal
  [OK ] mensagem cita o nome da variavel (TELEGRAM_BOT_TOKEN)
  [OK ] mensagem traz o status HTTP
  [OK ] mensagem NAO contem o token

== 2. receptor de webhook WhatsApp (subprocesso real, --uma-vez) ==
   GET com token ERRADO -> HTTP 403 corpo='403'
   GET com token CERTO  -> HTTP 200 corpo='CHALLENGE-F8-2026'
   POST do envelope     -> HTTP 200 corpo={"status": "recebido", "arquivo": "20260919-135215_1.json"}
--- stdout do receptor (uma linha por requisicao; token nunca impresso) ---
escutando em http://127.0.0.1:64164 | rota /webhook/whatsapp | destino de envelopes: <local>| verify_token: configurado (valor nunca e impresso)
pronto para receber o webhook (GET de verificacao + POST de envelope). Ctrl+C encerra.
13:52:15 GET /webhook/whatsapp 403 hub.verify_token nao confere
13:52:15 GET /webhook/whatsapp 200 verificacao aceita (challenge com 17 caractere(s))
13:52:15 POST /webhook/whatsapp 200 gravado 20260919-135215_1.json (602 bytes, com entry) - encerrando (--uma-vez)
receptor encerrado (1 POST(s) gravado(s) nesta execucao).
  [OK ] GET token errado -> 403
  [OK ] GET token certo -> 200 com o hub.challenge ecoado
  [OK ] POST do envelope -> 200
  [OK ] receptor encerrou depois do POST (--uma-vez)
  [OK ] stdout do receptor nao contem o verify token
  [OK ] stdout do receptor nao contem o token errado nem o token da API

--- cat do arquivo gravado pelo receptor no diretorio de webhook ---
{"object": "whatsapp_business_account", "entry": [{"id": "WABA-001", "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp", "metadata": {"display_phone_number": "551140028922", "phone_number_id": "PH-001"}, "contacts": [{"profile": {"name": "Jose da Silva"}, "wa_id": "5511998887777"}], "messages": [{"from": "5511998887777", "id": "wamid.HBgLNTUxMTk5ODg4Nzc3Nw==", "timestamp": "1773835200", "type": "text", "text": {"body": "Bom dia! Segue o PEDIDO N: 5201 da Alfa Pecas, emitido em 18/03/2026. Total de R$ 250,00, pagamento por PIX. Conseguem confirmar o recebimento?"}}]}}]}]}
  [OK ] receptor gravou 1 arquivo .json no diretorio de webhook
  [OK ] envelope gravado e o mesmo do mock

== 2b. coleta do webhook para o inbox (app.canais.ler_webhook_whatsapp) ==
   canal=whatsapp mensagens=1 arquivos=['whatsapp_coleta_20260919-135216.jsonl']
   detalhe : whatsapp: 1 envelope(s) de 1 arquivo(s) gravado(s) em whatsapp_coleta_20260919-135216.jsonl; 1 arquivo(s) movido(s) para processados/
--- cat do envelope no inbox ---
{"object": "whatsapp_business_account", "entry": [{"id": "WABA-001", "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp", "metadata": {"display_phone_number": "551140028922", "phone_number_id": "PH-001"}, "contacts": [{"profile": {"name": "Jose da Silva"}, "wa_id": "5511998887777"}], "messages": [{"from": "5511998887777", "id": "wamid.HBgLNTUxMTk5ODg4Nzc3Nw==", "timestamp": "1773835200", "type": "text", "text": {"body": "Bom dia! Segue o PEDIDO N: 5201 da Alfa Pecas, emitido em 18/03/2026. Total de R$ 250,00, pagamento por PIX. Conseguem confirmar o recebimento?"}}]}}]}]}
  [OK ] webhook -> inbox gravado como whatsapp_coleta_<...>.jsonl
  [OK ] arquivo consumido movido para processados/
  [OK ] nada mais na raiz do diretorio de webhook

== 3. o pipeline digere a coleta sem alteracao ==
   $ <worktree>\.venv\Scripts\python.exe -m app.run --inbox <local>
==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Modo     : mock | config: nenhum .env (padrao)
Inbox    : <local>
Saida    : <local>
Banco    : <local>
Rodada   : 20260919-135216
--------------------------------------------------------------
Artefatos ingeridos : 2 (pdf 0 | mensagens 2)
Auto-aprovados      : 0
Em revisao humana   : 2
Rejeitados          : 0
Deduplicados        : 0
Linhas na planilha  : 0
--------------------------------------------------------------
Leitura por motor   : parser 2
OCR                 : nenhum artefato usou OCR simulado nesta rodada
Auditoria           : 2 linha(s) nesta rodada | trilha cumulativa: 2 linha(s)
--------------------------------------------------------------
Motivos na fila de excecoes:
   total_sem_detalhamento             2
--------------------------------------------------------------
Arquivos gerados:
   xlsx              <local>
   csv               <local>
   auditoria         <local>
   auditoria_rodada  <local>
   fila_excecoes     <local>
   painel            <local>
   resumo            <local>
   db                <local>
==============================================================
Rodada concluida em 0.252s
   exit code: 0
   resumo: artefatos=2 mensagens=2 revisao=2 rejeitados=0 linhas_planilha=0
  [OK ] pipeline rodou sem erro
  [OK ] pipeline contou as 2 mensagens coletadas - mensagens=2
  [OK ] nenhum arquivo de coleta ficou de fora

== 5. modo real ponta a ponta: app.run --real --env <teste> (api_base no stub local) ==
   $ <worktree>\.venv\Scripts\python.exe -m app.run --real --env --out <temp> --db <temp>
  [stub 127.0.0.1:64163] GET /bot<TOKEN>/getUpdates
==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Modo     : real | canais: whatsapp, telegram | config: <local>
Coleta   : whatsapp: whatsapp: diretorio de webhook webhook_real ainda nao existe - suba o receptor (tools/receber_webhook_whatsapp.py) ou aponte WHATSAPP_WEBHOOK_DIR
Coleta   : telegram: 1 mensagem(ns) em <local>
Inbox    : <local>
Saida    : <local>
Banco    : <local>
Rodada   : 20260919-135216
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
   xlsx              <local>
   csv               <local>
   auditoria         <local>
   auditoria_rodada  <local>
   fila_excecoes     <local>
   painel            <local>
   resumo            <local>
   db                <local>
==============================================================
Rodada concluida em 0.256s
   exit code: 0
   envelopes coletados no modo real: ['telegram_coleta_20260919-135216.jsonl']
--- cat do envelope coletado pelo app.run --real ---
{"update_id": 500001, "message": {"message_id": 9001, "from": {"id": 424242, "is_bot": false, "first_name": "Jose", "username": "jose_compras"}, "chat": {"id": -1001234567890, "title": "Compras Fornecedores", "type": "group"}, "date": 1773835200, "text": "PEDIDO N: 6201 confirmado com a Alfa Pecas, emitido em 18/03/2026, valor total R$ 1.234,56. Pagamento por PIX."}}
   resumo: artefatos=1 mensagens=1 revisao=1 rejeitados=0
  [OK ] app.run --real coletou do canal e rodou o pipeline
  [OK ] modo real gravou o envelope no inbox do canal
  [OK ] pipeline contou a mensagem coletada no modo real
  [OK ] modo real nao vazou token no stdout

== 6. nenhum destino externo foi usado ==
  [OK ] api_base do Telegram aponta para o stub local (nada saiu para api.telegram.org) - api_base telegram=http://127.0.0.1:64163
  [OK ] coleta do WhatsApp e inbound (le arquivo; nao existe cliente HTTP nesse caminho) - ler_webhook_whatsapp nao recebe transporte e nao faz requisicao
  [OK ] nenhuma requisicao foi feita fora de 127.0.0.1 nesta prova - todo trafego registrado veio do stub em 127.0.0.1 (ver linhas [stub] acima)

RESULTADO: 33/33 provas OK
diretorio da prova: <local>
```

## Evidencia 2 - suite completa

Comando: `.venv/Scripts/python.exe -m pytest -q`

```text
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 76%]
....................................................................     [100%]
284 passed in 13.11s
```

## Interface para o QA (F10) e para o run.py (F7)

* Injetar transporte: `canais.coletar_telegram(cfg, transporte=stub)` ou
  `canais.coletar(cfg, canais=("telegram",), transporte=stub)`. O stub precisa apenas de
  `get_json(url, params=None, cabecalhos=None, timeout=30)`.
* `TransporteHTTP` e um `Protocol` com `@runtime_checkable`: da para checar `isinstance`
  sem herdar.
* WhatsApp nao usa transporte nenhum: e inbound (arquivo em `WHATSAPP_WEBHOOK_DIR`).
* `ler_webhook_whatsapp(mover=False)` deixa o arquivo no lugar (util em teste);
  `mover=True` (padrao) manda para `processados/`.
* Erros: `ErroCanal` (mensagem pt-BR, cita o NOME da variavel, nunca o valor; traz o status
  HTTP quando houver).
* `ResultadoColeta.destino` e o diretorio de inbox do canal; `arquivos=()` quando nao ha
  nada novo - nao e erro.
* Sem update novo / sem arquivo no diretorio de webhook: nao levanta, devolve resultado
  explicativo (o run.py segue para o pipeline).
