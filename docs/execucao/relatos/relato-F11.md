# Relato F11 - README de produção, AGENTS.md e relatório de fechamento (dono: luxuria, card PROJ-24)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (seções 1, 2, 3, 5, 6) e `docs/execucao/spec-F11.md`.
Data da execução: 2026-09-19. Worktree: `squad-pecados` (branch `squad-pecados`).
Interpretador: `.venv/Scripts/python.exe` (CPython 3.12.14). **Nenhum comando `git` foi rodado.**

## 0. Situação do worktree - e a virada no meio da minha janela

Quando comecei, o contrato dizia que F7, F8 **e F9** já estavam no worktree. **Não estavam:**

| Frente | Arquivo esperado | No início da minha janela | No fim |
| -- | -- | -- | -- |
| F7 | `app/config.py` | presente (13:47:57) | igual |
| F7 | `app/run.py` (ajustado) | presente (13:48:32) | igual |
| F8 | `app/canais.py` | presente (13:50:05) | igual |
| F8 | `tools/receber_webhook_whatsapp.py` | presente (13:49:03) | igual |
| **F9** | `.env.example` | **AUSENTE** | **presente (14:10:39, 4.754 B)** |
| **F9** | `tools/gerar_env_example.py` | **AUSENTE** | **presente (14:10:33, 8.773 B)** |
| **F9** | `tools/verificar_producao.py` | **AUSENTE** | **presente (14:08:55, 26.375 B)** |
| **F10** | `tests/test_config.py` | **AUSENTE** | **presente (14:08:44)** |
| **F10** | `tests/test_canais.py` | **AUSENTE** | **presente (14:10:11)** |
| **F10** | `tests/test_producao.py` | **AUSENTE** | **presente (14:12:56)** |
| F7/F8 | `relato-F7.md`, `relato-F8.md` | presentes | iguais |
| F9/F10 | `relato-F9.md`, `relato-F10.md` | **AUSENTES** | **presentes (14:11:23 / 14:15:13)** |

**F9 e F10 entregaram durante a minha janela de trabalho.** Consequência prática: a primeira versão
do README que escrevi dizia, com honestidade, que o `.env.example` não existia. Isso **deixou de ser
verdade** enquanto eu escrevia. Eu:

1. detectei a mudança ao reconferir o worktree antes de fechar;
2. **reexecutei todas as verificações** com o código final (seção 3, itens 10 a 12);
3. **reescrevi** o aviso da §7.2 do README, a tabela da §11, a contagem de testes da §6 e a
   limitação §10.7;
4. atualizei o `relatorios/RELATORIO-FECHAMENTO.md`.

Nada que eu tenha medido antes da virada sobrou como afirmação: as duas conferências que fiz antes
(`--check-config`, `--mock`) seguem válidas porque não dependem de F9/F10, e a contagem de testes
foi **refeita** (284 → **401**).

## 1. Arquivos entregues (somente os meus)

| Arquivo | Situação | Tamanho |
| -- | -- | -- |
| `README.md` | **nova seção 7** (Implementação em produção, 7.1 a 7.8) + renumeração de 7→8, 8→9, 9→10, 10→11 + seção 10 (limitações) atualizada + intro e §6 e §11 ajustadas | 60.012 bytes / 1.019 linhas |
| `relatorios/RELATORIO-FECHAMENTO.md` | **novo** | 16.030 bytes / 275 linhas |
| `AGENTS.md` | **BLOQUEADO - não escrevi** (ver seção 6.1) | inalterado |
| `docs/execucao/_ids/relato-F11.md` | este arquivo | - |

Não toquei em `app/**`, `tools/**`, `tests/**`, `.env.example`, `.gitignore` nem nas docs das
fases anteriores.

## 2. O que li antes de escrever (não documentei nada que não exista)

- `docs/execucao/00b-contrato-fechamento.md` e `docs/execucao/spec-F11.md`, inteiros.
- `app/config.py` - catálogo `VARIAVEIS` **lido por comando**, não por leitura de olho.
- `app/run.py` - `_parser()` (todas as flags), `_coletar()`, `main()`, `_abrir_log()`.
- `app/canais.py` - assinaturas (`coletar`, `coletar_telegram`, `ler_webhook_whatsapp`,
  `envelopes_telegram`, `transporte_urllib`, `ErroCanal`, `ResultadoColeta`) e os `mkdir`.
- `tools/receber_webhook_whatsapp.py` - `--help`, `ROTA_PADRAO`, `do_GET`, `do_POST`.
- `app/revisao.py` - dicionário `MOTIVO_INFO` (os 15 motivos, com risco, descrição e dica).
- `docs/execucao/_ids/relato-F7.md` e `relato-F8.md` (evidência de quem rodou a coleta).

### Conferência programática README x código

Para não escrever tabela errada, comparei o README com o código por script:

```
$ .venv/Scripts/python.exe -c "<compara README.md com revisao.MOTIVO_INFO e config.VARIAVEIS>"
motivos no README: 15 de 15 | faltando: []
variaveis no README: 16 de 16 | faltando: []
menciona .env.example: True
menciona X-Hub-Signature: True
menciona Tesseract: True
```

Nenhum motivo e nenhuma variável do código ficaram fora do README.

## 3. Evidência - os comandos que rodei e a saída real

### (1) Modo mock (o padrão) - `exit=0`

```
$ .venv/Scripts/python.exe -m app.run --mock
==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Modo     : mock | config: nenhum .env (padrao)
Inbox    : data\mocks
Saida    : data\out
Banco    : data\out\pipeline.db
Rodada   : 20260919-140703
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
Auditoria           : 20 linha(s) nesta rodada | trilha cumulativa: 940 linha(s)
--------------------------------------------------------------
Arquivos gerados:
   xlsx              data\out\controle_financeiro.xlsx
   csv               data\out\controle_financeiro.csv
   auditoria         data\out\auditoria.jsonl
   auditoria_rodada  data\out\auditoria_rodada_20260919-140703.jsonl
   fila_excecoes     data\out\fila_excecoes.json
   painel            data\out\painel.html
   resumo            data\out\resumo.json
   db                data\out\pipeline.db
==============================================================
Rodada concluida em 0.824s
exit=0
```

`Deduplicados: 20`/`Auto-aprovados: 0` porque a inbox já havia sido processada antes (idempotência,
não defeito); `Linhas na planilha` seguiu **7**.

### (2) `--check-config` sem `.env` - o mock não exige credencial - `exit=0`

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

### (3) Modo real sem `.env` - mensagem clara, sem traceback - `exit=2`

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

### (4) `--check-config` com `.env` de teste - o mascaramento - `exit=0`

`.env` de teste gravado **fora do repositório**
(`%LOCALAPPDATA%/Temp/f11_teste.env`, valores fictícios, nunca no git):

```
MODO_EXECUCAO=real
CANAIS_ATIVOS=whatsapp,telegram
TELEGRAM_BOT_TOKEN=123456789:AAHfakeTokenDeTesteSomenteParaProvaABC
TELEGRAM_CHAT_ID=-1001234567890
WHATSAPP_TOKEN=EAAGfakeTokenDeTesteSomenteParaProvaXYZ
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=palavra-de-teste-nao-e-segredo-real
LOG_LEVEL=DEBUG
LOG_DIR=<worktree>/AppData/Local/Temp/f11_logs
```

```
$ .venv/Scripts/python.exe -m app.run --check-config --env "%LOCALAPPDATA%/Temp/f11_teste.env"
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
exit=0
```

Varredura da própria saída para confirmar que segredo não vazou:

```
$ grep -n "AAHfake\|EAAGfake\|palavra-de-teste\|1234567890\|123456789012345" <saida>
14:  chat_id         : -1001234567890
20:  phone_number_id : 123456789012345
```

Os **dois únicos** valores completos que aparecem são `chat_id` e `phone_number_id`, que são
`sensivel=False` no catálogo. Os **três** sensíveis (`TELEGRAM_BOT_TOKEN`, `WHATSAPP_TOKEN`,
`WHATSAPP_VERIFY_TOKEN`) saíram como `****aABC`, `****aXYZ`, `****real`. **Nenhum segredo vazou.**

### (5) Suíte de testes - `exit=0`

Primeira medição, antes de F10 entregar:

```
$ .venv/Scripts/python.exe -m pytest -q
284 passed in 13.35s
```

Medição **final**, depois de F10 entregar (é esta que está no README):

```
$ .venv/Scripts/python.exe -m pytest -q
........................................................................ [ 89%]
.........................................                                [100%]
401 passed in 28.05s
exit=0
```

**401 testes.** Contagem por arquivo (`pytest --collect-only -q`, contada por mim):

```
tests/test_extracao.py             198
tests/test_config.py                70
tests/test_normalizacao.py          57
tests/test_canais.py                28
tests/test_producao.py              19
tests/test_adversarial.py           15
tests/test_idempotencia.py           8
tests/test_ponta_a_ponta.py          6
TOTAL                              401
```

### (6) Os caminhos citados no README existem (conferidos um por um)

```
$ ls -l data/out/
auditoria.jsonl                                    560035 B
auditoria_rodada_20260919-140703.jsonl              11896 B   (um por rodada)
controle_financeiro.csv                              3067 B
controle_financeiro.xlsx                             6538 B
fila_excecoes.json                                  19343 B
painel.html                                         30586 B
pipeline.db                                        143360 B
resumo.json                                          2211 B

$ ls -l logs/
pipeline-20260919.log                              159311 B

$ tail -6 logs/pipeline-20260919.log
2026-09-19 14:07:04 INFO    painel            data\out\painel.html
2026-09-19 14:07:04 INFO    resumo            data\out\resumo.json
2026-09-19 14:07:04 INFO    db                data\out\pipeline.db
2026-09-19 14:07:04 INFO    ==============================================================
2026-09-19 14:07:04 INFO    Rodada concluida em 0.824s
2026-09-19 14:07:04 INFO    rodada concluida; log em C:\...\logs\pipeline-20260919.log

$ .venv/Scripts/python.exe tools/receber_webhook_whatsapp.py --help
usage: receber_webhook_whatsapp.py [-h] [--host HOST] [--porta PORTA] [--env ENV] [--uma-vez]
  --host HOST    endereco de escuta (padrao 127.0.0.1)
  --porta PORTA  porta de escuta (padrao 8787)
  --env ENV      arquivo .env alternativo (padrao: .env da raiz)
  --uma-vez      encerra depois do primeiro POST (usado na prova de aceite)

$ .venv/Scripts/python.exe -m app.run --help
usage: app.run [-h] [--mock] [--real] [--env ENV] [--check-config]
               [--inbox INBOX] [--out OUT] [--db DB] [--verbose]
```

Rota do receptor confirmada no código: `ROTA_PADRAO = "/webhook/whatsapp"`
(`tools/receber_webhook_whatsapp.py`, linha 42).

### (7) As pastas são criadas automaticamente (não inventei que o operador precisa criar)

```
$ grep -n "mkdir" tools/receber_webhook_whatsapp.py
223:    destino.mkdir(parents=True, exist_ok=True)

$ grep -n "mkdir" app/canais.py
195:    pasta.mkdir(parents=True, exist_ok=True)
433:    processados.mkdir(parents=True, exist_ok=True)

$ grep -n "mkdir" app/run.py
69:        caminho.parent.mkdir(parents=True, exist_ok=True)
```

`data/inbox/` e `data/inbox_webhook/whatsapp/` **não existem** hoje no worktree (confirmado por
`ls -la data/`) e são criadas na primeira necessidade - foi o que escrevi no README (§7.8).

### (8) O receptor recusa iniciar sem `WHATSAPP_VERIFY_TOKEN`

```
$ .venv/Scripts/python.exe tools/receber_webhook_whatsapp.py --env <env sem token> --uma-vez
ERRO de configuracao: configuracao incompleta para o modo real (canais ativos: whatsapp): 3 variavel(is) obrigatoria(is) sem valor.
falta WHATSAPP_TOKEN - ...
falta WHATSAPP_PHONE_NUMBER_ID - ...
```

Mensagem clara e sem traceback, como o contrato exige.

### (9) Evidência de terceiros que usei (e que não é minha)

O ciclo de coleta real contra stub local **não foi rodado por mim**: é do relato do dono da F8,
`docs/execucao/_ids/relato-F8.md`, e está citado no README sem ser apresentado como execução minha.
Trechos do relato de F8 (saída literal dele):

```
[stub 127.0.0.1:64163] GET /bot<TOKEN>/getUpdates
 ErroCanal: telegram: getUpdates recusado em http://127.0.0.1:64163 (HTTP 401 Unauthorized). Confira TELEGRAM_BOT_TOKEN (credencial recusada) no .env - nenhuma credencial e impressa aqui.
13:52:15 GET /webhook/whatsapp 403 hub.verify_token nao confere
13:52:15 GET /webhook/whatsapp 200 verificacao aceita (challenge com 17 caractere(s))
13:52:15 POST /webhook/whatsapp 200 gravado 20260919-135215_1.json (602 bytes, com entry) - encerrando (--uma-vez)
```

No README isso aparece declarado como teste **contra stub local**, e declaro também que a chamada
credenciada a `api.telegram.org`/`graph.facebook.com` **não foi executada**.

### (10) `.env.example` conferido contra o catálogo - `exit=0`

```
$ .venv/Scripts/python.exe tools/gerar_env_example.py --conferir
==========================================================================
GERADOR DO .env.example - tools/gerar_env_example.py (F9 / preguica)
==========================================================================
catalogo : app/config.py -> VARIAVEIS (16 variaveis)
destino  : C:\...\squad-pecados\.env.example
--------------------------------------------------------------------------
PASSOU: .env.example em sincronia com o catalogo (16 variaveis, sha256 4f111a6026a949a6)
```

Conferência independente (script meu, comparando o arquivo com `config.VARIAVEIS`):

```
variaveis no .env.example: 16
variaveis no catalogo    : 16
so no .env.example: nenhuma
so no catalogo    : nenhuma
segredos com valor preenchido? []
```

Os três segredos (`sensivel=True`) estão **vazios** no exemplo: `[]` = nenhum preenchido.

### (11) `tools/verificar_producao.py` - 6/6 PASSOU - `exit=0`

```
$ .venv/Scripts/python.exe tools/verificar_producao.py
==============================================================================
VERIFICADOR DE PRODUCAO - tools/verificar_producao.py (F9 / preguica)
contrato: docs/execucao/00b-contrato-fechamento.md secao 3.5
==============================================================================
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
data/ intacto (retrato de 98 arquivos, tamanho e mtime): True
RESULTADO: 6/6 PASSOU
==============================================================================
```

Um ponto para o PO: o item [1/6] traz o aviso de que o `.env.example` **ainda não está no índice
do git** - o arquivo existe e está correto, falta o commit (que é do PO).

### (12) A suíte confere sozinha o que eu documentei

Para não deixar a conferência só na minha palavra, rodei um script que compara o README com o
código:

```
$ .venv/Scripts/python.exe -c "<compara README.md com revisao.MOTIVO_INFO e config.VARIAVEIS>"
motivos: 15 / 15
variaveis: 16 / 16
401 no README: True
6/6 no README: True
284 residual: False
```

Ou seja: as 15 linhas da tabela de motivos e as 16 da tabela de variáveis batem com o código, e
**não sobrou** nenhuma afirmação antiga (284 testes / `.env.example` ausente) no README.

## 4. Linhas do README que eu criei

| Linha | Seção | O que é |
| -- | -- | -- |
| 7-19 | intro | Modo mock é o padrão; modo real aponta para a seção 7; aviso de origem dos dados atualizado |
| **313** | `## 7. Implementação em produção` | **nova seção** (o pedido 3 do cliente) |
| 332 | `### 7.1` | Instalar as dependências (uv, venv, pip, conferência, testes) |
| 368 | `### 7.2` | Configurar: o `.env` - sintaxe, **tabela das 16 variáveis**, onde entram os tokens reais, `--check-config` com saída real, sincronia do `.env.example` |
| 489 | `### 7.3` | Rodar o produto - mock, real, o que fazer quando falta variável, tabela de flags, verificador de produção (6/6) |
| 600 | `### 7.4` | Onde saem a planilha e a trilha de auditoria (o que se apaga x o que nunca se apaga) |
| 621 | `### 7.5` | Acompanhar os logs - caminho, formato, exemplo real, níveis |
| 654 | `### 7.6` | Agendar: Windows ("Iniciar em") + `schtasks` + `cron` + aviso de idempotência |
| 694 | `### 7.7` | Quando uma extração falha - o fluxo e a **tabela dos 15 motivos** |
| 739 | `### 7.8` | Modo real dos canais - `getUpdates`, receptor de webhook, painel da Meta |
| 798 | `## 8.` | renumerada (era 7) - a planilha de 20 colunas |
| 846 | `## 9.` | renumerada (era 8) - idempotência e trilha de auditoria |
| 904 | `## 10.` | renumerada (era 9) - limitações honestas, com itens 2 e 3 reescritos e itens 9 e 10 novos |
| 981 | `## 11.` | renumerada (era 10) - estrutura do repositório, com os arquivos desta fase |

Total: **1.019 linhas**. Referência interna corrigida: "É assim que se prova a idempotência
(seção 7)" → **(seção 9)**, por causa da renumeração.

### Honestidade obrigatória - onde está declarado

- **OCR simulado**: §10.1 (sidecar `.ocr.txt`, sem Tesseract nesta máquina, acurácia do OCR real
  não medida).
- **Canais mock com envelope real**: §10.2.
- **Coleta real implementada e testada contra stub local, chamada credenciada NÃO executada**:
  §10.2, com a frase explícita "nenhuma mensagem real de WhatsApp ou Telegram passou por este
  sistema".
- **Sem serviço pago, sem chave nova, sem número real**: §10.9.
- **Receptor de webhook só local + assinatura da Meta não validada**: §10.10 e §7.8.

## 5. Divergências entre README e código

Nenhuma encontrada. Conferi as duas tabelas grandes contra o código por script (seção 2) e a
contagem de variáveis (16) e de motivos (15) bate exatamente.

Duas observações de contexto, que **não** são divergência:

1. O contrato (§3.1) lista `INBOX_DIR` como "obrigatoria em: nao" e o código usa tupla vazia
   `obrigatoria_em=()`. Coerente.
2. O catálogo tem `WHATSAPP_API_BASE` com padrão `https://graph.facebook.com/v21.0`; o contrato
   diz "v21.0". Coerente.

## 6. O que NÃO consegui fazer

### 6.1 `AGENTS.md` - escrita bloqueada (não é falha de conteúdo)

A spec F11 me deu o `AGENTS.md` como arquivo meu, mas o ambiente **bloqueia escrita de agente em
arquivo de instrução de agente**. A tentativa foi recusada literalmente assim:

```
BLOCKED: write to protected agent-instruction file(s) (AGENTS.md) approval prompt timed out
without a user response. Silence is not consent. The user has NOT consented to this write.
Do NOT retry it or attempt the same edit via another path (terminal, execute_code, etc.).
```

**Não tentei contornar** por terminal nem por qualquer outro caminho - a própria mensagem proíbe,
e contornar proteção de arquivo seria o tipo de atalho que não se dá.

**O que o `AGENTS.md` já tem (conferido por `cat -n`, nada a corrigir):**

- `## O que entra` diz que os commits vão **com push** para o `origin`
  `Wagner-Dev-Souza/agentes-nf-pedidos` (**privado**) - a linha antiga ("sem push", "não existe
  remoto") **já não existe**. O PO corrigiu antes de eu começar (mtime 13:46:39).
- `## Modelo de branches (remoto origin)`: `squad-pecados` (trabalho) → `homolog` (homologação) →
  `main` (produção, **sem commit direto**).
- `Nunca faça push de segredo` e `## O que NUNCA entra no git` (com `.env` listado).

**O que falta, em uma linha:** a regra explícita "**só o PO roda git**". O restante da correção
pedida (remoto existe, `squad-pecados`/`homolog`/`main`, segredo nunca no git) **já está no
arquivo**.

**Ação para o PO (dono do versionamento e único que escreve no repo):** acrescentar, no bloco
`## Modelo de branches (remoto origin)`, a linha:

```
- **Só o PO roda git.** Os workers (os agentes) **não** executam `git add`, `git commit`,
  `git push` nem `git checkout` em hipótese alguma: quem versiona é o PO, nos limites de cada
  onda. O worker deixa o arquivo no diretório e segue.
```

### 6.2 `data/out/` ficou com trilha acumulada de 940 linhas

Efeito colateral de várias rodadas de várias frentes no mesmo `pipeline.db`. Não é defeito e não
mexi: o contrato (emenda do PO na seção 4.1 do `00-contrato-execucao.md`) diz que a trilha é
**cumulativa** e que a fonte da verdade é o banco. Registro porque o número aparece na saída colada
na seção 3.1 e pode assustar quem comparar com a fase 2.

### 6.3 Não agendei execução nem chamei API real

Fora do escopo (e, no caso da API, sem credencial autorizada - D4). Os comandos de agendamento no
README estão declarados como **não executados por mim**.

## 7. Resumo para o coordenador

- Entreguei **`README.md` §7 (Implementação em produção, 7.1-7.8)** cobrindo os 7 itens do pedido,
  com **16/16 variáveis** e **15/15 motivos** conferidos contra o código por script, e **sem
  nenhuma afirmação antiga sobrevivente** (284 testes / `.env.example` ausente: verificado).
- Entreguei **`relatorios/RELATORIO-FECHAMENTO.md`** com evidência real e a lista do que ficou de fora.
- **Não escrevi o `AGENTS.md`**: bloqueio de arquivo protegido (seção 6.1). O conteúdo já estava
  correto; falta só a linha "só o PO roda git" - o PO aplica.
- **F9 e F10 entregaram durante a minha janela.** O que eu havia registrado antes (`.env.example`
  ausente, 284 testes) **deixou de ser verdade** e foi corrigido: o README e o relatório passaram a
  dizer `.env.example` presente e **401 testes**. Reexecutei tudo com o código final.
- **Verificações finais:** `pytest -q` → **401 passed** · `gerar_env_example.py --conferir` →
  **PASSOU (16 variáveis em sincronia)** · `verificar_producao.py` → **6/6 PASSOU** ·
  `app.run --mock` → exit 0 · `app.run --check-config` → exit 0 · `app.run --real` sem `.env` →
  exit 2 com mensagem clara.
- **Pendências para o PO:** (a) aplicar a linha "só o PO roda git" no `AGENTS.md`; (b) incluir o
  `.env.example` no commit (o verificador de produção aponta que ele ainda não está no índice do
  git).
