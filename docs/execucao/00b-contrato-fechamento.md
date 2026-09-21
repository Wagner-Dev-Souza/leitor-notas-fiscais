# Contrato de execucao - FECHAMENTO DO PRODUTO (fase 3)

Dono deste documento: **PO (soberba)**. Interface congelada. Worker nao altera este arquivo
nem `app/contratos.py`; pedido de mudanca de interface volta para o PO.

Base: PROJ-12 (fase 2, entregue e verificada pelo cliente). Esta fase NAO refaz o pipeline:
o pipeline ja passa em 284 testes e continua sendo o mesmo. O que entra aqui e a camada de
operacao: **configuracao por `.env`, modo real, evidencia e documentacao de producao**.

## 1. Pedido do cliente (literal, para nao se perder)

1. A aplicacao precisa ser simples de rodar em producao, por quem nao conhece o projeto.
2. Arquivo de configuracao `.env`: `.env.example` versionado com TODAS as variaveis usadas,
   valores placeholder (vazios) e comentario explicando cada uma (o que e, onde obter);
   o app le esse arquivo e, quando faltar variavel obrigatoria, avisa com mensagem clara e
   especifica ("falta TELEGRAM_BOT_TOKEN") - nunca stack trace obscuro, nunca seguir em
   silencio; nenhum segredo no codigo nem versionado; `.env` real ignorado pelo git.
   Se existir `.env` no repositorio, denunciar.
3. README com secao de implementacao em producao: instalar dependencias, configurar
   (variavel por variavel, incluindo numero/token real de WhatsApp e Telegram), rodar,
   onde saem a planilha e a trilha de auditoria, acompanhar logs, agendar a execucao
   periodica, e o que fazer quando uma extracao falha (fila de excecoes / revisao humana).
4. Modo mock continua sendo o PADRAO; o modo real liga pela configuracao do `.env`.
5. Manter declarado no README o que ainda e simulado (os canais, hoje arquivos de
   mock com o envelope real das APIs).

## 2. Decisoes do PO (fechadas - nao reabrir sem pedido do cliente)

* **D1 - Modo**: `MODO_EXECUCAO` no `.env`, valores `mock` (padrao) ou `real`. Flags de CLI
  `--mock` / `--real` sobrepoem o arquivo. Sem `.env`, o app roda em mock e isso nao e erro.
* **D2 - Parser do `.env`**: implementacao propria em `app/config.py`, **somente biblioteca
  padrao**. Nao entra `python-dotenv` nem qualquer dependencia nova em `requirements.txt`.
* **D3 - Modo real = coleta, nao magia**: os canais reais (Telegram `getUpdates`; WhatsApp
  por receptor de webhook local) **gravam envelopes no inbox** no MESMO formato dos mocks.
  O pipeline (`ingerir -> ... -> planilha`) nao e alterado e a idempotencia continua valendo.
* **D4 - Rede**: a chamada credenciada real a `api.telegram.org` / `graph.facebook.com`
  **nao foi executada nesta entrega** - nao existe token nem numero real autorizado. O que
  se prova e: montagem da requisicao, gravacao do envelope e ciclo completo contra um
  **stub HTTP local (127.0.0.1)**. Nada disso sera apresentado como chamada real.
* **D5 - Segredo**: valor sensivel nunca aparece em log, resumo, painel ou mensagem de erro.
  `config.mascarar()` e a unica forma de citar um segredo (ultimos 4 caracteres).
* **D6 - `.env.example` e gerado do catalogo** (`app/config.py: VARIAVEIS`) por
  `tools/gerar_env_example.py`. Fonte unica: se a variavel existe no codigo, ela esta no
  exemplo; se esta no exemplo, existe no codigo. Divergencia = defeito.
* **D7 - Versionamento**: **somente o PO roda git** (add/commit/push). Worker nao roda git em
  hipotese alguma. Ha remoto (`origin`, privado) e o PO faz push da branch `squad-pecados`.
  A linha do `AGENTS.md` que diz "sem push, nao existe remoto" esta desatualizada e sera
  corrigida nesta fase.

## 3. Interface congelada

### 3.1 `app/config.py` (novo) - dono: avareza

```python
MODO_MOCK = "mock"
MODO_REAL = "real"
MODOS = (MODO_MOCK, MODO_REAL)
ARQUIVO_ENV_PADRAO = ".env"          # na raiz do projeto

@dataclass(frozen=True)
class Variavel:
    nome: str                # ex.: "TELEGRAM_BOT_TOKEN"
    descricao: str           # o que e (1 linha, pt-BR, sem acento quebrado)
    onde_obter: str          # onde o operador consegue o valor
    obrigatoria_em: tuple[str, ...]  # subconjunto de: "sempre", "real", "real:telegram", "real:whatsapp"
    padrao: str = ""         # valor usado quando ausente (nunca para segredo)
    sensivel: bool = False   # True -> nunca imprimir valor
    exemplo: str = ""        # placeholder mostrado no .env.example ("" = vazio)

VARIAVEIS: tuple[Variavel, ...]      # catalogo completo (fonte do .env.example, do erro e do README)

class ConfigError(Exception):
    faltando: list[str]              # ex.: ["TELEGRAM_BOT_TOKEN", "WHATSAPP_TOKEN"]
    mensagens: list[str]             # linhas pt-BR prontas para o operador
    # str(erro) devolve as linhas unidas por "\n"; NUNCA inclui traceback nem valor de segredo

@dataclass(frozen=True)
class TelegramConfig:  token: str; chat_id: str; api_base: str; timeout_s: float
@dataclass(frozen=True)
class WhatsAppConfig:  token: str; phone_number_id: str; verify_token: str; api_base: str
                       webhook_dir: Path
@dataclass(frozen=True)
class Config:
    modo: str                        # MODO_MOCK | MODO_REAL
    arquivo_env: Path | None         # qual arquivo foi lido (None = nenhum)
    canais: tuple[str, ...]          # ex.: ("whatsapp", "telegram")
    inbox_dir: Path
    out_dir: Path
    db_path: Path
    log_dir: Path
    log_level: str
    telegram: TelegramConfig
    whatsapp: WhatsAppConfig
    @property
    def modo_real(self) -> bool

def carregar(env_path=None, ambiente=None) -> Config
    # Le o .env (se existir), aplica o ambiente do processo por cima, valida e devolve Config.
    # Levanta ConfigError apontando EXATAMENTE as variaveis faltantes. Nunca imprime segredo.

def mascarar(valor: str) -> str       # "" -> ""; curto -> "****"; longo -> "****" + ultimos 4
def imprimir_configuracao(cfg) -> str # relatorio legivel do que foi configurado (sem segredo)
def exemplo_env() -> str              # texto do .env.example, terminado em "\n"
```

Variaveis do catalogo (todas, com o modo em que importam):

| Nome | Obrigatoria em | Sensivel | Padrao |
| -- | -- | -- | -- |
| `MODO_EXECUCAO` | sempre | nao | `mock` |
| `CANAIS_ATIVOS` | `real` | nao | `whatsapp,telegram` |
| `INBOX_DIR` | nao | nao | `data/mocks` (mock) / `data/inbox` (real) |
| `OUT_DIR` | nao | nao | `data/out` |
| `DB_PATH` | nao | nao | `<OUT_DIR>/pipeline.db` |
| `LOG_DIR` | nao | nao | `logs` |
| `LOG_LEVEL` | nao | nao | `INFO` |
| `TELEGRAM_BOT_TOKEN` | `real:telegram` | sim | - |
| `TELEGRAM_CHAT_ID` | `real:telegram` | nao | - |
| `TELEGRAM_API_BASE` | nao | nao | `https://api.telegram.org` |
| `TELEGRAM_TIMEOUT_S` | nao | nao | `30` |
| `WHATSAPP_TOKEN` | `real:whatsapp` | sim | - |
| `WHATSAPP_PHONE_NUMBER_ID` | `real:whatsapp` | nao | - |
| `WHATSAPP_VERIFY_TOKEN` | `real:whatsapp` | sim | - |
| `WHATSAPP_APP_SECRET` | nao | sim | - |
| `WHATSAPP_API_BASE` | nao | nao | `https://graph.facebook.com/v21.0` |
| `WHATSAPP_WEBHOOK_DIR` | nao | nao | `data/inbox_webhook/whatsapp` |

Formato do `.env`: `CHAVE=valor`, uma por linha, `#` comenta. Linhas em branco ignoradas.
Sintaxe tolerada: espacos em volta do `=` e `export CHAVE=valor` (quem cola de tutorial).
Aspas simples ou duplas em volta do valor sao removidas. Valor ausente (`CHAVE=`) conta como
**nao configurado** para variavel obrigatoria.

### 3.2 `app/canais.py` (novo) - dono: gula

```python
CANAL_TELEGRAM = "telegram"
CANAL_WHATSAPP = "whatsapp"

class ErroCanal(Exception): ...      # falha de coleta; mensagem pt-BR com o canal e a causa

@dataclass(frozen=True)
class ResultadoColeta:
    canal: str
    destino: Path                    # diretorio onde os envelopes foram gravados
    arquivos: tuple[Path, ...]       # arquivos .jsonl criados (vazio = nada novo)
    mensagens: int
    detalhe: str                     # texto pt-BR para o log/resumo

class TransporteHTTP(Protocol):      # seam para teste: os testes injetam stub local
    def get_json(self, url: str, params: dict | None = None,
                 cabecalhos: dict | None = None, timeout: float = 30) -> dict: ...
    def post_json(self, url: str, corpo: dict, cabecalhos: dict | None = None,
                  timeout: float = 30) -> dict: ...

def transporte_urllib() -> TransporteHTTP         # implementacao real (urllib, stdlib)
def envelopes_telegram(updates: list[dict], chat_id: str | None = None) -> list[dict]
def coletar_telegram(cfg, transporte=None, destino=None, offset=None) -> ResultadoColeta
def ler_webhook_whatsapp(cfg, destino=None, mover=True) -> ResultadoColeta
def coletar(cfg, canais=None, transporte=None) -> list[ResultadoColeta]
```

Regras da coleta (congeladas):

* Destino padrao: `<cfg.inbox_dir>/<canal>/`. Cada coleta grava **um** arquivo
  `<canal>_coleta_<AAAAMMDD-HHMMSS>.jsonl`, uma linha por envelope, `ensure_ascii=False`.
* **Telegram**: `GET {api_base}/bot{token}/getUpdates`, com `chat_id` em
  `allowed_updates`/filtro local por `message.chat.id`; cada item de `result` vira uma linha
  (mesmo formato de `data/mocks/telegram/*.jsonl`). Sem update novo -> `arquivos=()` e
  `detalhe` explicando; isso **nao** e erro.
* **WhatsApp**: cada arquivo `.json` ou `.jsonl` em `cfg.whatsapp.webhook_dir` e um envelope
  (`{"object":"whatsapp_business_account","entry":[...]}`, mesmo formato do mock). Com
  `mover=True`, o arquivo consumido vai para `<webhook_dir>/processados/`. Envelope sem
  `entry` (webhook de status) e descartado com `detalhe` explicando.
* Nenhum segredo em `detalhe`, nome de arquivo ou log. Falha de rede -> `ErroCanal` com
  mensagem clara (o comando devolve codigo != 0 e diz o que fazer).

### 3.3 `tools/receber_webhook_whatsapp.py` (novo) - dono: gula

Receptor local do webhook do WhatsApp Cloud API, biblioteca padrao (`http.server`).
- `GET <rota>?hub.mode=subscribe&hub.verify_token=<WHATSAPP_VERIFY_TOKEN>&hub.challenge=X`
  -> responde `X` (200) quando o token confere, 403 quando nao confere.
- `POST <rota>` com o envelope -> grava `<WHATSAPP_WEBHOOK_DIR>/<timestamp>_<n>.json` (200).
- Imprime cada requisicao em uma linha; nunca imprime o token.
- Parametros: `--host` (padrao `127.0.0.1`), `--porta` (padrao `8787`), `--env`,
  `--uma-vez` (derruba depois de um POST - usado na prova do PO).
- Sem `WHATSAPP_VERIFY_TOKEN` configurado -> recusa iniciar com mensagem clara.
- Com `WHATSAPP_APP_SECRET` configurado, o `POST` tem a assinatura `X-Hub-Signature-256`
  conferida (HMAC-SHA256 do corpo bruto, comparacao em tempo constante) **antes** de gravar;
  assinatura ausente ou que nao confere -> **401 e nada e gravado**. Sem o app secret o receptor
  sobe com aviso explicito e aceita o POST (uso local, sem credencial real).

### 3.4 `tools/gerar_env_example.py` (novo) - dono: preguica

`python tools/gerar_env_example.py [--saida .env.example] [--conferir]`
- Gera o texto a partir de `config.VARIAVEIS` (nunca digitado a mao).
- `--conferir` compara com o arquivo em disco e sai != 0 se divergir, imprimindo o diff.

### 3.5 `tools/verificar_producao.py` (novo) - dono: preguica

Verificador de execucao real (comando unico), imprime PASSOU/FALHOU por item:
1. `.env.example` presente, versionado e em sincronia com o catalogo.
2. Nenhum `.env` real versionado (`git ls-files`) e `.env` presente no `.gitignore`.
3. Modo mock continua sendo o padrao (sem `.env`, roda e nao exige segredo).
4. Modo real sem as variaveis obrigatorias -> mensagem clara citando cada variavel faltante,
   sem traceback e sem rodar o pipeline.
5. Varredura de segredo em arquivo versionado (padroes obvios de token/número) - inclusive
   `.env.example` nao pode conter valor plausivel de segredo.
6. `.env` de teste com valores ficticios -> `--check-config` reconhece tudo e **mascara** os
   valores sensiveis na saida.
O script trabalha em diretorio temporario proprio e **nao** toca `data/`.

### 3.6 `app/run.py` (ajuste) - dono: avareza

Comando unico (nao muda):

```
.venv/Scripts/python.exe -m app.run --mock
```

Flags: `--mock` (padrao), `--real`, `--env <arquivo>`, `--check-config`, `--inbox`, `--out`,
`--db`, `--verbose`. Regras:
- `--check-config` valida a configuracao, imprime `config.imprimir_configuracao(cfg)` e sai 0
  (ou 2 com a mensagem de `ConfigError`). Nao roda pipeline.
- Modo real: valida a configuracao -> coleta (`canais.coletar`) -> roda o pipeline no inbox.
- Modo real com configuracao incompleta: mensagem clara + codigo 2, **nunca** traceback.
- Log em arquivo: `<LOG_DIR>/pipeline-<AAAAMMDD>.log` (append), alem do stdout atual.
  Falha ao abrir o log nao derruba a rodada (avisa e segue).
- A saida em terminal continua a mesma das fases anteriores (aceite da fase 2 preservado);
  pode ganhar as linhas de modo/configuracao/coleta.

## 4. Frentes, donos e arquivos (dono unico por arquivo - nao invadir)

| Frente | Dono | Arquivos (dono unico) | Card |
| -- | -- | -- | -- |
| F7 | avareza | `app/config.py` (novo), `app/run.py` (ajuste) | PROJ-20 |
| F8 | gula | `app/canais.py` (novo), `tools/receber_webhook_whatsapp.py` (novo) | PROJ-21 |
| F9 | preguica | `tools/gerar_env_example.py` (novo), `tools/verificar_producao.py` (novo), `.env.example` (novo) | PROJ-22 |
| F10 | ira | `tests/test_config.py`, `tests/test_canais.py`, `tests/test_producao.py` (novos), `tests/evidencia/*` | PROJ-23 |
| F11 | luxuria | `README.md` (secao de producao), `AGENTS.md` (correcao do "sem push"), `relatorios/RELATORIO-FECHAMENTO.md` | PROJ-24 |

`app/contratos.py`, `app/ingress.py`, `app/pipeline.py`, `app/persistencia.py`,
`app/revisao.py`, `app/extracao.py`, `tools/gerar_mocks.py`, `tools/verificar.py`,
`docs/execucao/00-contrato-execucao.md` e este arquivo: **nao se tocam** nesta fase.
Se um deles precisar mudar, e decisao do PO.

## 5. Critérios de aceite (o cliente cobra exatamente isto)

1. `.venv/Scripts/python.exe -m app.run --mock` roda e imprime o resumo real (evidencia colada).
2. Sem `.env` configurado e com `MODO_EXECUCAO=real`: a aplicacao avisa, citando pelo nome
   cada variavel faltante, e sai com codigo != 0. Sem traceback.
3. Suite de testes continua passando: **284 anteriores + os novos** (contagem total exata
   informada na evidencia, com `pytest -q` colado).
4. `.env.example` versionado existe e lista TODAS as variaveis do catalogo.
5. Secao de producao do README responde aos 7 itens do pedido (item 3 do cliente).
6. `git ls-files` nao mostra `.env` nem qualquer segredo; `.env` esta no `.gitignore`.
7. README declara o que e simulado: canais (mock com envelope real; coleta
   real implementada mas nao exercitada com credencial real).
8. Nada de servico pago, chave nova, numero real ou push de segredo.
9. Branch `squad-pecados` no `origin` com o trabalho (push feito pelo PO, apos a verificacao).

## 6. Regras de trabalho (valem para as 5 frentes)

* **Nao rodar git.** Nem `add`, nem `commit`, nem `push`, nem `checkout`. So o PO escreve no repo.
* Nao editar arquivo de outro dono. Precisou? Escreva o pedido em
  `docs/execucao/_ids/pedido-<frente>.md` e o PO decide.
* So vale o que voltou de execucao real. Comando que nao rodou nao aconteceu; falha se declara.
* Nao inventar saida, numero ou captura de tela.
* Nao apagar nem sobrescrever trabalho de outra frente ou das fases anteriores.
* Ao terminar: escreva `docs/execucao/_ids/relato-<frente>.md` com o que rodou, a saida real
  (colada, literal) e o que nao foi possivel fazer. Esse arquivo e a sua entrega de evidencia.
