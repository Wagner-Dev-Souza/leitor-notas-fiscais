# Relatório de fechamento - configuração e operação em produção

**Destinatários:** Loghanth e Wagner
**Fase:** 3 - fechamento do produto (card PROJ-24, pai PROJ-19)
**Frente:** F11 - documentação de produção (dono: luxuria)
**Base:** execução real nesta máquina, em 2026-09-19, e o código presente no worktree
**Natureza dos dados:** sintéticos. Nenhuma mensagem real de WhatsApp ou Telegram passou por aqui.

---

## 1. O que foi pedido (literal, do contrato de fechamento)

1. A aplicação precisa ser **simples de rodar em produção**, por quem não conhece o projeto.
2. **Arquivo `.env`**: `.env.example` versionado com todas as variáveis, valores placeholder e
   comentário explicando cada uma; o app lê o arquivo e, quando falta variável obrigatória, avisa
   com mensagem clara citando o nome — nunca stack trace, nunca silêncio; nenhum segredo no código
   nem versionado; `.env` real ignorado pelo git.
3. **README com seção de implementação em produção**: instalar, configurar (incluindo token/número
   real de WhatsApp e Telegram), rodar, onde saem planilha e trilha de auditoria, acompanhar logs,
   agendar execução periódica, e o que fazer quando uma extração falha.
4. **Modo mock continua sendo o padrão**; o modo real liga pela configuração do `.env`.
5. **Manter declarado o que ainda é simulado** (OCR e os canais).

---

## 2. O que foi entregue e onde

| # | Pedido | Onde está | Situação |
|---|---|---|---|
| 1 | Rodar simples em produção | `README.md`, **seção 7** - Implementação em produção | **Entregue** - 8 subseções (7.1 a 7.8) |
| 2 | Arquivo `.env` + aviso de variável faltante | `.env.example` + `app/config.py` (catálogo de 16 variáveis) + `README.md` §7.2 | **Entregue** - 16/16 variáveis em sincronia com o código, nenhum segredo preenchido |
| 3 | README de produção com os 7 itens | `README.md`, seção 7 | **Entregue** - item por item na tabela da seção 3 |
| 4 | Modo mock é o padrão; real liga pelo `.env` | `app/config.py`, `app/run.py` + README §§7.2 e 7.3 | **Entregue e verificado** |
| 5 | Declarar o que é simulado | `README.md`, **seção 10** (10 limitações declaradas) | **Entregue** |
| — | Verificador de prontidão da produção | `tools/verificar_producao.py` | **Entregue** - rodou **6/6 PASSOU** |
| — | Testes desta fase | `tests/test_config.py`, `test_canais.py`, `test_producao.py` | **Entregue** - suíte em **401 testes**, todos passando |
| — | Correção do `AGENTS.md` ("sem push / sem remoto") | `AGENTS.md` | **Já estava corrigido**; faltou acrescentar 1 regra e a escrita foi **bloqueada** - ver seção 4 |
| — | Relatório desta fase | este arquivo | **Entregue** |

**Escopo desta fase, em uma frase:** o pipeline da fase 2 não foi refeito — ele continua passando
em 284 testes. O que entrou foi a **camada de operação**: configuração por `.env`, modo real, e a
documentação para colocar isso para rodar.

---

## 3. Os 7 itens do pedido, um por um

| Item pedido | Onde responde | O que diz |
|---|---|---|
| Instalar dependências | §7.1 (e §3) | Interpretador do projeto (`.venv/Scripts/python.exe`, CPython 3.12.14), instalação com `uv` e com `pip`, comando de conferência e comando dos testes. |
| Configurar variável por variável | §7.2 | Tabela com **as 16 variáveis na ordem do catálogo**: o que é, obrigatória em qual modo, **onde obter o valor** e exemplo de linha. Mais a sintaxe aceita e o `--check-config` com saída real. |
| Onde entram o token/número real de WhatsApp e Telegram | §7.2 | Bloco "Onde entram o número/token real": @BotFather → `TELEGRAM_BOT_TOKEN`; grupo via `getUpdates` → `TELEGRAM_CHAT_ID`; Meta for Developers → `WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID`; verify token escolhido por você. Como ligar o real: `MODO_EXECUCAO=real` + `CANAIS_ATIVOS`. |
| Rodar o produto | §7.3 | Comando único no mock (padrão) e no real, com saída real colada; o que fazer quando reclama de variável faltante; tabela completa de flags. |
| Onde saem a planilha e a trilha de auditoria | §7.4 (+ §8 e §9) | Tabela dos 8 artefatos com papel de cada um e, coluna a coluna, **o que se apaga a cada rodada e o que nunca se apaga**. |
| Acompanhar logs | §7.5 | `<LOG_DIR>/pipeline-<AAAAMMDD>.log`, formato da linha, exemplo real, tabela de níveis (o que olhar em cada um) e 3 regras de operação. |
| Agendar a execução periódica | §7.6 | Windows (Agendador de Tarefas com o campo "**Iniciar em**" destacado como o erro mais comum; e `schtasks`) + Linux/macOS (`cron`), com o comando real e o aviso de que agendar é seguro porque a rodada é idempotente. |
| O que fazer quando uma extração falha | §7.7 | O caminho `falhou → fila → revisão humana → planilha`, onde a pessoa olha (`painel.html` e `fila_excecoes.json`) e **tabela com os 15 motivos** possíveis, com risco e explicação em português. |
| Modo real dos canais | §7.8 | Telegram via `getUpdates` (filtro por chat), WhatsApp via receptor local (`/webhook/whatsapp`, porta 8787, verify token, `--uma-vez`), e o que o operador faz no painel da Meta. |

### Honestidade declarada (requisito 5 do cliente)

A seção 10 do README declara, sem rodeio, **10 limitações**. As três que o cliente pediu
explicitamente:

1. **OCR é simulado** (§10.1): o PDF escaneado é lido por um motor **simulado** (sidecar
   `.ocr.txt`), rotulado como `ocr_simulado` na trilha de auditoria. **Não há Tesseract nesta
   máquina.** A acurácia do OCR real **não foi medida**.
2. **Os canais de demonstração são mock com o envelope real das APIs** (§10.2): as mensagens são
   arquivos `.jsonl` escritos no payload oficial do WhatsApp Cloud API e do Telegram Bot API.
3. **A coleta real foi implementada e testada contra stub local, mas a chamada credenciada não foi
   executada** (§10.2): nada foi enviado a `api.telegram.org` nem a `graph.facebook.com` — não
   existe token nem número real autorizado. **Nenhuma mensagem real de WhatsApp ou Telegram passou
   por este sistema.** O que ficou provado foi a montagem da requisição, a gravação do envelope e o
   ciclo completo até a planilha, contra um stub em `127.0.0.1`.

Somado a isso: **nenhum serviço pago, nenhuma chave nova, nenhum número real** (§10.9).

---

## 4. O que ficou de fora, e por quê

| Fora | Por quê | O que falta |
|---|---|---|
| **Não consegui editar o `AGENTS.md`** | O arquivo é protegido contra escrita por agente nesta sessão: a tentativa de gravação foi **bloqueada** e eu **não** contornei por outro caminho. Não é falha de conteúdo — o ajuste é de uma linha. | acrescentar a regra "**só o PO roda git**" no bloco `## Modelo de branches`. O resto do arquivo **já estava correto**: a linha antiga ("sem push", "não existe remoto") já havia sido corrigida antes de eu começar. |
| **`.env.example` ainda não está no índice do git** | O versionamento é do PO (regra do contrato). O arquivo **existe** e está correto; o verificador de produção aponta o aviso: *"ainda nao esta no indice do git - o PO versiona nesta onda"*. | o PO adicionar `.env.example` ao commit. |
| **Chamada credenciada real aos canais** | Decisão D4 do contrato: não há token nem número autorizado. | colocar credencial real no `.env` (passo do cliente, §7.2). |
| **Agendamento executado** | Não executei o Agendador de Tarefas nem o `cron` — isso é do ambiente do cliente. O que está provado é o comando base e a idempotência. | criar a tarefa no servidor do cliente, com o campo "Iniciar em" (§7.6). |
| **Exposição pública do webhook** | O receptor escuta em `127.0.0.1`, como o contrato pede. | endereço em **HTTPS** + certificado + liberação de firewall, no ambiente do cliente. |
| **Validação da assinatura `X-Hub-Signature-256`** | Exige o *app secret* da Meta, que **não está no catálogo de variáveis** — é decisão de contrato, não desta frente. | ampliar o catálogo e implementar a validação (fase seguinte). |

> **Nota sobre o andamento:** quando comecei esta frente, o `.env.example`, os dois tools
> auxiliares e os testes deste ciclo **ainda não estavam** no worktree (frentes F9 e F10 em
> andamento). Eles foram entregues **durante** a minha janela de trabalho. Reexecutei todas as
> verificações depois disso: o que está neste relatório reflete o **estado final**, com F9 e F10
> entregues. Nenhum número deste relatório foi medido antes da última entrega.

---

## 5. Evidências reais (comandos e saída)

Todos os comandos abaixo foram rodados por mim, neste worktree, com o interpretador
`.venv/Scripts/python.exe`. A saída literal completa está em
`docs/execucao/_ids/relato-F11.md`.

### 5.1 O modo mock continua funcionando (é o padrão)

```
$ .venv/Scripts/python.exe -m app.run --mock
Modo     : mock | config: nenhum .env (padrao)
Inbox    : data\mocks
Rodada   : 20260919-140703
Artefatos ingeridos : 20 (pdf 12 | mensagens 8)
Auto-aprovados      : 0   Em revisao humana : 0   Rejeitados : 0
Deduplicados        : 20  Linhas na planilha : 7
Auditoria           : 20 linha(s) nesta rodada | trilha cumulativa: 940 linha(s)
Rodada concluida em 0.824s
exit=0
```

`Deduplicados: 20` porque a inbox já tinha sido processada em rodadas anteriores: é a
idempotência funcionando, e `Linhas na planilha` continuou **7**.

### 5.2 Sem `.env`, o modo mock roda e não pede credencial

```
$ .venv/Scripts/python.exe -m app.run --check-config
Modo de execucao : mock  (padrao, dados sinteticos)
Arquivo .env     : (nao configurado)
bot token        : (nao configurado)
token            : (nao configurado)
```
`exit=0` — o produto **não exige segredo** para rodar no modo padrão.

### 5.3 Modo real sem credencial: mensagem clara, sem traceback, código de saída 2

```
$ .venv/Scripts/python.exe -m app.run --real
configuracao incompleta para o modo real (canais ativos: whatsapp, telegram): 5 variavel(is) obrigatoria(is) sem valor.
falta TELEGRAM_BOT_TOKEN - Token do bot do Telegram ... (SEGREDO).
    onde obter: No Telegram, fale com @BotFather, ...
falta TELEGRAM_CHAT_ID - ...
falta WHATSAPP_TOKEN - ... (SEGREDO).
falta WHATSAPP_PHONE_NUMBER_ID - ...
falta WHATSAPP_VERIFY_TOKEN - ... (SEGREDO).
preencha essas variaveis no arquivo .env do projeto ... --check-config
para rodar com dados sinteticos, sem credencial nenhuma, use o modo padrao: ... --mock
exit=2
```

Cada variável faltante é citada **pelo nome**, com "onde obter". **Nenhum traceback.**

### 5.4 Segredo é mascarado

Com um `.env` de teste (valores fictícios, arquivo **fora** do repositório), o
`--check-config` reconheceu tudo e **mascarou os três segredos**:

```
bot token       : ****aABC
token           : ****aXYZ
verify_token    : ****real
```

Auditoria da própria saída: os únicos valores completos que aparecem são os **não sensíveis**
(`chat_id` e `phone_number_id`). Os três valores marcados como `sensivel=True` no catálogo
saíram mascarados.

### 5.5 A suíte está verde - e cresceu com os testes desta fase

```
$ .venv/Scripts/python.exe -m pytest -q
........................................................................ [ 89%]
.........................................                                [100%]
401 passed in 28.05s
exit=0
```

**401 testes** (eram 284 na fase 2; esta fase somou 117):

| Arquivo | Testes |
|---|---|
| `tests/test_extracao.py` | 198 |
| `tests/test_config.py` | 70 |
| `tests/test_normalizacao.py` | 57 |
| `tests/test_canais.py` | 28 |
| `tests/test_producao.py` | 19 |
| `tests/test_adversarial.py` | 15 |
| `tests/test_idempotencia.py` | 8 |
| `tests/test_ponta_a_ponta.py` | 6 |
| **Total** | **401** |

### 5.6 O `.env.example` está em sincronia com o código

```
$ .venv/Scripts/python.exe tools/gerar_env_example.py --conferir
catalogo : app/config.py -> VARIAVEIS (16 variaveis)
destino  : C:\...\squad-pecados\.env.example
--------------------------------------------------------------------------
PASSOU: .env.example em sincronia com o catalogo (16 variaveis, sha256 4f111a6026a949a6)
exit=0
```

Conferência independente: o `.env.example` tem **16 variáveis**, o catálogo tem **16** - nenhuma
sobra de um lado nem do outro, e **nenhum dos 3 segredos (`sensivel=True`) veio com valor
preenchido**.

### 5.7 Verificador de prontidão da produção: 6 de 6

```
$ .venv/Scripts/python.exe tools/verificar_producao.py
[1/6] .env.example presente, versionado e em sincronia com o catalogo
        PASSOU: 16 variaveis do catalogo presentes e em sincronia
[2/6] nenhum .env real versionado e .env no .gitignore
        PASSOU: nenhum .env versionado; '.env' ignorado pelo git
[3/6] modo mock continua sendo o padrao (sem .env, roda e nao exige segredo)
        PASSOU: sem .env o padrao e mock, roda e nao pede credencial nenhuma
[4/6] modo real sem as obrigatorias -> mensagem clara, sem traceback, sem rodar pipeline
        PASSOU: codigo 2, citou as 5 variaveis faltantes pelo nome, sem traceback e sem rodar o pipeline
[5/6] varredura de segredo em arquivo versionado (inclusive .env.example)
        PASSOU: 160 arquivos versionados varridos: nenhum segredo e nenhum numero fora do material sintetico
[6/6] `.env` de teste com valores ficticios -> --check-config reconhece e mascara
        PASSOU: configuracao ficticia aceita (exit 0) e os 3 valores sensiveis mascarados na saida
--------------------------------------------------------------------------
data/ intacto (retrato de 98 arquivos, tamanho e mtime): True
RESULTADO: 6/6 PASSOU
exit=0
```

**Uma observação do próprio verificador, que vale registrar:** ele avisa que o `.env.example`
*"ainda nao esta no indice do git - o PO versiona nesta onda"*. O arquivo existe e está correto; o
que falta é o commit, que é do PO.

### 5.8 A infraestrutura citada no README existe

```
$ ls data/out/      -> controle_financeiro.xlsx/.csv, auditoria.jsonl,
                       auditoria_rodada_20260919-140703.jsonl, fila_excecoes.json,
                       painel.html, resumo.json, pipeline.db
$ ls logs/          -> pipeline-20260919.log  (159.311 bytes)
$ tail logs/pipeline-20260919.log
2026-09-19 14:07:04 INFO    Rodada concluida em 0.824s
2026-09-19 14:07:04 INFO    rodada concluida; log em ...\logs\pipeline-20260919.log
```

---

## 6. O que o cliente precisa fazer para rodar de verdade

Cinco passos, na ordem:

0. **Conferir que a configuração de produção está sã:**
   `.venv/Scripts/python.exe tools/verificar_producao.py` - tem de dar **6/6 PASSOU**.
1. **Criar o `.env`** a partir do exemplo versionado (`cp .env.example .env`). A lista das
   variáveis, com onde obter cada valor, é a tabela da **§7.2** do README.
2. **Preencher as credenciais reais:**
   - Telegram: criar o bot no **@BotFather** → `TELEGRAM_BOT_TOKEN`; descobrir o id do grupo por
     `getUpdates` → `TELEGRAM_CHAT_ID`.
   - WhatsApp: app no **Meta for Developers** → `WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID`;
     escolher uma palavra e cadastrá-la como *Verify token* → `WHATSAPP_VERIFY_TOKEN`.
3. **Validar sem rodar:** `.venv/Scripts/python.exe -m app.run --check-config`. Se faltar algo, ele
   diz exatamente o quê.
4. **Rodar:** `.venv/Scripts/python.exe -m app.run --real`.
5. **Agendar** a execução periódica (§7.6) — lembrando o campo "**Iniciar em**" no Windows.

E dois itens de ambiente, se o WhatsApp for usado a sério: **expor o webhook em HTTPS** e
**liberar a porta no firewall** (§10.10 do README).

**O que esperar no primeiro dia:** não espere 100% de acerto na primeira rodada de dados reais. O
que o produto garante é que **o que ele não souber, ele não escreve** — vai para a fila de revisão
com o motivo declarado. As linhas da planilha são só o que passou na conferência.

---

*Todo número deste relatório veio de saída de comando rodada nesta máquina ou de arquivo do
repositório. Onde não foi possível entregar ou verificar, está escrito na seção 4 — sem promessa
que não se cumpriu.*
