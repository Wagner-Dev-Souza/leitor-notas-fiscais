"""Configuracao da operacao: catalogo de variaveis, leitura do `.env` e validacao.

Dono: avareza (F7 - fechamento do produto). Interface congelada na secao 3.1 do
`docs/execucao/00b-contrato-fechamento.md`. **Somente biblioteca padrao**: nao entra
`python-dotenv` nem qualquer dependencia nova em `requirements.txt` (decisao D2 do PO).

O que este modulo garante:

* `.env` e OPCIONAL. Sem arquivo nenhum o app roda em `mock` e isso **nao** e erro.
* Variavel obrigatoria faltando -> `ConfigError` citando **pelo nome** cada variavel,
  com o que ela e e onde obter; nunca traceback obscuro, nunca seguir em silencio.
* Valor sensivel nunca sai inteiro: `mascarar()` e a unica forma de citar um segredo
  (contrato D5). Nem mensagem de erro, nem relatorio, nem log imprimem o valor.
* Precedencia: ambiente do processo > arquivo `.env` > padrao do catalogo. As flags de
  CLI (`--mock`/`--real`) vencem tudo, porque o `app/run.py` as injeta no `ambiente`.
* `VARIAVEIS` e a fonte unica: o `.env.example` (gerado por
  `tools/gerar_env_example.py`), a mensagem de erro e o README saem todos daqui.
  Variavel que existe no codigo esta no exemplo; o que esta no exemplo existe no codigo.

Formato do `.env` aceito (secao 3.1 do contrato): `CHAVE=valor`, uma por linha, `#`
comenta, linhas em branco ignoradas, espacos em volta do `=`, prefixo `export ` (quem
cola de tutorial) e aspas simples ou duplas em volta do valor. `CHAVE=` (valor vazio)
conta como **nao configurado**.

Caminhos relativos sao resolvidos a partir da raiz do projeto (onde vive o `.env`), e
nao do diretorio de onde o comando foi chamado: o operador pode rodar de qualquer lugar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

MODO_MOCK = "mock"
MODO_REAL = "real"
MODOS = (MODO_MOCK, MODO_REAL)
ARQUIVO_ENV_PADRAO = ".env"  # na raiz do projeto

# Raiz do projeto: `app/config.py` -> `app/` -> raiz.
RAIZ_PROJETO = Path(__file__).resolve().parent.parent

# Canais que o catalogo conhece. A implementacao da coleta vive em `app/canais.py`
# (dono: gula/F8); aqui e so a lista de nomes aceitos em `CANAIS_ATIVOS`.
CANAIS_CONHECIDOS = ("whatsapp", "telegram")

NIVEIS_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Texto unico para "nao mostro o valor" (contrato D5).
MASCARA = "****"
NAO_CONFIGURADO = "(nao configurado)"

# Valores obrigatorios (o que conta como "obrigatoria" em cada situacao).
OBRIGATORIA_SEMPRE = "sempre"
OBRIGATORIA_REAL = "real"
OBRIGATORIA_REAL_TELEGRAM = "real:telegram"
OBRIGATORIA_REAL_WHATSAPP = "real:whatsapp"
OBRIGATORIEDADES = (
    OBRIGATORIA_SEMPRE,
    OBRIGATORIA_REAL,
    OBRIGATORIA_REAL_TELEGRAM,
    OBRIGATORIA_REAL_WHATSAPP,
)


# --------------------------------------------------------------------- catalogo


@dataclass(frozen=True)
class Variavel:
    """Uma variavel de configuracao do produto."""

    nome: str
    descricao: str
    onde_obter: str
    obrigatoria_em: tuple[str, ...]
    padrao: str = ""
    sensivel: bool = False
    exemplo: str = ""


VARIAVEIS: tuple[Variavel, ...] = (
    Variavel(
        nome="MODO_EXECUCAO",
        descricao="Como o pipeline roda: 'mock' (dados sinteticos, padrao) ou 'real' (coleta dos canais).",
        onde_obter="Digitado pelo operador. As flags --mock/--real da linha de comando sobrepoem este valor.",
        obrigatoria_em=(OBRIGATORIA_SEMPRE,),
        padrao=MODO_MOCK,
        exemplo=MODO_MOCK,
    ),
    Variavel(
        nome="CANAIS_ATIVOS",
        descricao="Canais coletados no modo real, separados por virgula (aceitos: whatsapp, telegram).",
        onde_obter="Digitado pelo operador, conforme os canais que ele conectou.",
        obrigatoria_em=(OBRIGATORIA_REAL,),
        padrao="whatsapp,telegram",
        exemplo="whatsapp,telegram",
    ),
    Variavel(
        nome="INBOX_DIR",
        descricao="Diretorio de entrada com as subpastas pdf/, whatsapp/ e telegram/ (padrao: data/mocks no modo mock, data/inbox no modo real).",
        onde_obter="Caminho no servidor. Deixe vazio para usar o padrao do modo escolhido.",
        obrigatoria_em=(),
    ),
    Variavel(
        nome="OUT_DIR",
        descricao="Diretorio de saida: planilha, trilha de auditoria, fila de excecoes e painel.",
        onde_obter="Caminho no servidor (pasta com permissao de escrita para o usuario do servico).",
        obrigatoria_em=(),
        padrao="data/out",
        exemplo="data/out",
    ),
    Variavel(
        nome="DB_PATH",
        descricao="Arquivo SQLite do pipeline, fonte da verdade do dado (padrao: <OUT_DIR>/pipeline.db).",
        onde_obter="Caminho no servidor. Deixe vazio para usar <OUT_DIR>/pipeline.db.",
        obrigatoria_em=(),
    ),
    Variavel(
        nome="LOG_DIR",
        descricao="Diretorio dos arquivos de log de execucao (pipeline-AAAAMMDD.log).",
        onde_obter="Caminho no servidor, de preferencia coberto pela rotacao de logs.",
        obrigatoria_em=(),
        padrao="logs",
        exemplo="logs",
    ),
    Variavel(
        nome="LOG_LEVEL",
        descricao="Nivel de detalhe do log: DEBUG, INFO, WARNING, ERROR ou CRITICAL.",
        onde_obter="Digitado pelo operador. Use DEBUG para investigar uma coleta que falhou.",
        obrigatoria_em=(),
        padrao="INFO",
        exemplo="INFO",
    ),
    Variavel(
        nome="TELEGRAM_BOT_TOKEN",
        descricao="Token do bot do Telegram que recebe as mensagens dos pedidos (SEGREDO).",
        onde_obter="No Telegram, fale com @BotFather, crie/abra o bot e copie o token.",
        obrigatoria_em=(OBRIGATORIA_REAL_TELEGRAM,),
        sensivel=True,
    ),
    Variavel(
        nome="TELEGRAM_CHAT_ID",
        descricao="Identificador do chat ou grupo do Telegram que o bot deve ler (so os updates desse chat entram no pipeline).",
        onde_obter="Envie uma mensagem no grupo e leia getUpdates em https://api.telegram.org/bot<token>/getUpdates (campo message.chat.id).",
        obrigatoria_em=(OBRIGATORIA_REAL_TELEGRAM,),
    ),
    Variavel(
        nome="TELEGRAM_API_BASE",
        descricao="Endereco base da API do Telegram. Só mude para apontar a um espelho/proxy local.",
        onde_obter="Valor fixo do Telegram: https://api.telegram.org",
        obrigatoria_em=(),
        padrao="https://api.telegram.org",
        exemplo="https://api.telegram.org",
    ),
    Variavel(
        nome="TELEGRAM_TIMEOUT_S",
        descricao="Tempo limite em segundos de cada chamada HTTP ao Telegram.",
        onde_obter="Digitado pelo operador (padrao 30).",
        obrigatoria_em=(),
        padrao="30",
        exemplo="30",
    ),
    Variavel(
        nome="WHATSAPP_TOKEN",
        descricao="Token de acesso do app do WhatsApp Cloud API (SEGREDO).",
        onde_obter="No Meta for Developers: seu app > WhatsApp > API Setup > Access token.",
        obrigatoria_em=(OBRIGATORIA_REAL_WHATSAPP,),
        sensivel=True,
    ),
    Variavel(
        nome="WHATSAPP_PHONE_NUMBER_ID",
        descricao="Identificador do numero de WhatsApp Business que recebe as mensagens.",
        onde_obter="No Meta for Developers: seu app > WhatsApp > API Setup (campo Phone number ID).",
        obrigatoria_em=(OBRIGATORIA_REAL_WHATSAPP,),
    ),
    Variavel(
        nome="WHATSAPP_VERIFY_TOKEN",
        descricao="Palavra-chave que o Meta usa para validar o webhook; e voce quem escolhe e repete no painel (SEGREDO).",
        onde_obter="Voce inventa uma palavra longa e cadastra a mesma no Meta for Developers > WhatsApp > Configuration > Webhook.",
        obrigatoria_em=(OBRIGATORIA_REAL_WHATSAPP,),
        sensivel=True,
    ),
    Variavel(
        nome="WHATSAPP_APP_SECRET",
        descricao=(
            "App secret do app da Meta, usado para conferir a assinatura X-Hub-Signature-256 "
            "de cada webhook recebido pelo receptor local (SEGREDO)."
        ),
        onde_obter=(
            "No Meta for Developers: seu app > Configuracoes do app > Basico > Chave secreta do app."
        ),
        obrigatoria_em=(),
        sensivel=True,
    ),
    Variavel(
        nome="WHATSAPP_API_BASE",
        descricao="Endereco base da Graph API do WhatsApp. Só mude para apontar a um espelho/proxy local.",
        onde_obter="Valor do Meta for Developers (padrao https://graph.facebook.com/v21.0).",
        obrigatoria_em=(),
        padrao="https://graph.facebook.com/v21.0",
        exemplo="https://graph.facebook.com/v21.0",
    ),
    Variavel(
        nome="WHATSAPP_WEBHOOK_DIR",
        descricao="Diretorio onde o receptor local do webhook grava os envelopes recebidos do WhatsApp.",
        onde_obter="Caminho no servidor, de preferencia fora da arvore versionada.",
        obrigatoria_em=(),
        padrao="data/inbox_webhook/whatsapp",
        exemplo="data/inbox_webhook/whatsapp",
    ),
)

VARIAVEIS_POR_NOME: dict[str, Variavel] = {var.nome: var for var in VARIAVEIS}


# --------------------------------------------------------------------- erro


class ConfigError(Exception):
    """Configuracao incompleta ou invalida, com a mensagem pronta para o operador.

    `str(erro)` devolve as linhas unidas por "\\n". Nunca inclui traceback e nunca
    inclui valor de variavel sensivel (so o nome dela).
    """

    def __init__(self, mensagens, faltando=None) -> None:
        self.mensagens: list[str] = [str(linha) for linha in mensagens]
        self.faltando: list[str] = list(faltando or [])
        super().__init__("\n".join(self.mensagens))

    def __str__(self) -> str:  # pragma: no cover - trivial, coberto por teste
        return "\n".join(self.mensagens)

    def __repr__(self) -> str:
        return f"ConfigError(faltando={self.faltando!r}, mensagens={self.mensagens!r})"


# --------------------------------------------------------------------- mascara


def mascarar(valor: str) -> str:
    """Unica forma de citar um valor sensivel (contrato D5).

    ``""`` -> ``""``; valor curto -> ``****``; valor longo -> ``****`` + ultimos 4
    caracteres. Com menos de 8 caracteres nao vale a pena revelar: os 4 ultimos seriam
    quase o segredo inteiro.
    """
    texto = "" if valor is None else str(valor)
    if not texto:
        return ""
    if len(texto) < 8:
        return MASCARA
    return MASCARA + texto[-4:]


# --------------------------------------------------------------------- .env


def ler_env(caminho) -> dict[str, str]:
    """Le um arquivo `.env` no formato `CHAVE=valor` (secao 3.1 do contrato).

    Aceita `#` comentando, linhas em branco, espacos em volta do `=`, prefixo
    `export ` e aspas simples/duplas em volta do valor. Nao expande variaveis, nao
    executa nada do arquivo e nao imprime nada. Linha sem `=` e ignorada em silencio
    (comentario solto, lixo de edicao) - o que importa e o valor das variaveis do
    catalogo, e quem valida isso e `carregar()`.
    """
    valores: dict[str, str] = {}
    caminho_env = Path(caminho)
    if not caminho_env.is_file():
        return valores

    with caminho_env.open("r", encoding="utf-8-sig", errors="replace") as fh:
        for linha in fh:
            texto = linha.strip()
            if not texto or texto.startswith("#"):
                continue
            if texto.lower().startswith("export "):
                texto = texto[len("export ") :].lstrip()
            if "=" not in texto:
                continue
            chave, _, valor = texto.partition("=")
            chave = chave.strip()
            if not chave:
                continue
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
                valor = valor[1:-1]
            valores[chave] = valor.strip()
    return valores


# --------------------------------------------------------------------- config


@dataclass(frozen=True)
class TelegramConfig:
    token: str
    chat_id: str
    api_base: str
    timeout_s: float


@dataclass(frozen=True)
class WhatsAppConfig:
    token: str
    phone_number_id: str
    verify_token: str
    app_secret: str
    api_base: str
    webhook_dir: Path


@dataclass(frozen=True)
class Config:
    modo: str
    arquivo_env: Optional[Path]
    canais: tuple[str, ...]
    inbox_dir: Path
    out_dir: Path
    db_path: Path
    log_dir: Path
    log_level: str
    telegram: TelegramConfig
    whatsapp: WhatsAppConfig

    @property
    def modo_real(self) -> bool:
        return self.modo == MODO_REAL


# ------------------------------------------------------------------ validacao


def _caminho(bruto: str, padrao: str = "") -> Path:
    """Resolve um caminho do catalogo contra a raiz do projeto (aceita absoluto)."""
    texto = (bruto or padrao or "").strip()
    caminho = Path(texto).expanduser()
    if not caminho.is_absolute():
        caminho = RAIZ_PROJETO / caminho
    return caminho


def _valor_efetivo(nome: str, ambiente: Mapping, arquivo: Mapping, padroes: Mapping) -> str:
    """Ambiente do processo > arquivo `.env` > padrao do catalogo. Vazio = ausente."""
    for fonte in (ambiente, arquivo, padroes):
        bruto = fonte.get(nome)
        if bruto is None:
            continue
        texto = str(bruto).strip()
        if texto:
            return texto
    return ""


def _obrigatoria(var: Variavel, modo: str, canais: tuple[str, ...]) -> bool:
    if OBRIGATORIA_SEMPRE in var.obrigatoria_em:
        return True
    if modo != MODO_REAL:
        return False
    if OBRIGATORIA_REAL in var.obrigatoria_em:
        return True
    if "telegram" in canais and OBRIGATORIA_REAL_TELEGRAM in var.obrigatoria_em:
        return True
    if "whatsapp" in canais and OBRIGATORIA_REAL_WHATSAPP in var.obrigatoria_em:
        return True
    return False


def _erro_faltando(faltando: list[Variavel], modo: str, canais: tuple[str, ...]) -> ConfigError:
    """Mensagem de falta: cita cada variavel pelo nome e diz o que e e onde obter."""
    contexto = "modo real"
    if canais:
        contexto += f" (canais ativos: {', '.join(canais)})"
    linhas = [
        f"configuracao incompleta para o {contexto}: "
        f"{len(faltando)} variavel(is) obrigatoria(is) sem valor.",
    ]
    for var in faltando:
        linhas.append(f"falta {var.nome} - {var.descricao}")
        linhas.append(f"    onde obter: {var.onde_obter}")
    linhas.append(
        "preencha essas variaveis no arquivo .env do projeto (copie de .env.example) ou "
        "exporte no ambiente; para validar antes de rodar use: "
        ".venv/Scripts/python.exe -m app.run --check-config"
    )
    linhas.append(
        "para rodar com dados sinteticos, sem credencial nenhuma, use o modo padrao: "
        ".venv/Scripts/python.exe -m app.run --mock"
    )
    return ConfigError(linhas, [var.nome for var in faltando])


def carregar(env_path=None, ambiente=None) -> Config:
    """Le o `.env` (se existir), aplica o ambiente por cima, valida e devolve `Config`.

    `env_path=None` procura `.env` na raiz do projeto; caminho explicito que nao existe
    e erro (o operador pediu um arquivo e ele nao esta la). `ambiente=None` usa
    `os.environ`; um dicionario pode ser injetado (testes e as flags de CLI).

    Levanta `ConfigError` apontando EXATAMENTE as variaveis faltantes do modo pedido.
    Nunca imprime segredo: as mensagens citam apenas nomes de variavel.
    """
    if env_path is None:
        candidato = RAIZ_PROJETO / ARQUIVO_ENV_PADRAO
        caminho_env: Optional[Path] = candidato if candidato.is_file() else None
    else:
        caminho_env = Path(env_path)
        if not caminho_env.is_file():
            raise ConfigError(
                [
                    f"arquivo de configuracao nao encontrado: {caminho_env}",
                    "confira o caminho passado em --env ou deixe o arquivo .env na raiz do projeto",
                ]
            )

    arquivo = ler_env(caminho_env) if caminho_env is not None else {}
    ambiente_real: Mapping = os.environ if ambiente is None else ambiente
    padroes = {var.nome: var.padrao for var in VARIAVEIS if var.padrao}

    valores = {var.nome: _valor_efetivo(var.nome, ambiente_real, arquivo, padroes) for var in VARIAVEIS}

    # ---------------------------------------------------------------- modo
    modo_bruto = valores["MODO_EXECUCAO"].strip().lower()
    if modo_bruto not in MODOS:
        raise ConfigError(
            [
                f"valor invalido em MODO_EXECUCAO: {modo_bruto!r}",
                f"use um destes: {', '.join(MODOS)} (padrao: {MODO_MOCK})",
                "no modo mock o pipeline roda com os dados sinteticos de data/mocks; no modo real "
                "ele coleta dos canais antes de processar",
            ]
        )
    modo = modo_bruto

    # --------------------------------------------------------------- canais
    canais: tuple[str, ...] = ()
    if modo == MODO_REAL:
        pedidos = [parte.strip().lower() for parte in valores["CANAIS_ATIVOS"].split(",")]
        canais = tuple(dict.fromkeys(parte for parte in pedidos if parte))
        desconhecidos = [canal for canal in canais if canal not in CANAIS_CONHECIDOS]
        if desconhecidos:
            raise ConfigError(
                [
                    f"canal desconhecido em CANAIS_ATIVOS: {', '.join(desconhecidos)}",
                    f"canais aceitos: {', '.join(CANAIS_CONHECIDOS)}",
                ]
            )
        if not canais:
            raise ConfigError(
                [
                    "modo real sem canal ativo: CANAIS_ATIVOS esta vazio",
                    f"informe pelo menos um canal ({', '.join(CANAIS_CONHECIDOS)}) ou rode o modo padrao --mock",
                ]
            )

    # ------------------------------------------------------- obrigatorias
    faltando = [
        var for var in VARIAVEIS if _obrigatoria(var, modo, canais) and not valores[var.nome]
    ]
    if faltando:
        raise _erro_faltando(faltando, modo, canais)

    # ------------------------------------------------------------- nivel de log
    nivel = valores["LOG_LEVEL"].strip().upper()
    if nivel not in NIVEIS_LOG:
        raise ConfigError(
            [
                f"valor invalido em LOG_LEVEL: {valores['LOG_LEVEL']!r}",
                f"use um destes: {', '.join(NIVEIS_LOG)}",
            ]
        )

    # -------------------------------------------------------------- timeout
    timeout_bruto = valores["TELEGRAM_TIMEOUT_S"].strip()
    try:
        timeout = float(timeout_bruto)
    except ValueError:
        timeout = 0.0
    if timeout <= 0:
        raise ConfigError(
            [
                f"valor invalido em TELEGRAM_TIMEOUT_S: {timeout_bruto!r}",
                "informe um numero de segundos maior que zero (exemplo: 30)",
            ]
        )

    # ------------------------------------------------------------- caminhos
    padrao_inbox = "data/inbox" if modo == MODO_REAL else "data/mocks"
    out_dir = _caminho(valores["OUT_DIR"], "data/out")
    db_path = _caminho(valores["DB_PATH"]) if valores["DB_PATH"] else out_dir / "pipeline.db"

    return Config(
        modo=modo,
        arquivo_env=caminho_env,
        canais=canais,
        inbox_dir=_caminho(valores["INBOX_DIR"], padrao_inbox),
        out_dir=out_dir,
        db_path=db_path,
        log_dir=_caminho(valores["LOG_DIR"], "logs"),
        log_level=nivel,
        telegram=TelegramConfig(
            token=valores["TELEGRAM_BOT_TOKEN"],
            chat_id=valores["TELEGRAM_CHAT_ID"],
            api_base=valores["TELEGRAM_API_BASE"].rstrip("/"),
            timeout_s=timeout,
        ),
        whatsapp=WhatsAppConfig(
            token=valores["WHATSAPP_TOKEN"],
            phone_number_id=valores["WHATSAPP_PHONE_NUMBER_ID"],
            verify_token=valores["WHATSAPP_VERIFY_TOKEN"],
            app_secret=valores["WHATSAPP_APP_SECRET"],
            api_base=valores["WHATSAPP_API_BASE"].rstrip("/"),
            webhook_dir=_caminho(valores["WHATSAPP_WEBHOOK_DIR"], "data/inbox_webhook/whatsapp"),
        ),
    )


# ------------------------------------------------------------------ relatorio


def _caminho_legivel(caminho: Optional[Path]) -> str:
    if caminho is None:
        return NAO_CONFIGURADO
    try:
        return str(Path(caminho).resolve().relative_to(RAIZ_PROJETO))
    except (ValueError, OSError):
        return str(caminho)


def _valor_exibivel(valor: str, sensivel: bool) -> str:
    if not valor:
        return NAO_CONFIGURADO
    return mascarar(valor) if sensivel else valor


def imprimir_configuracao(cfg: Config) -> str:
    """Relatorio legivel do que foi configurado. **Nunca** imprime valor sensivel."""
    linhas = [
        "Configuracao do pipeline",
        "-" * 40,
        f"Modo de execucao : {cfg.modo}" + ("" if cfg.modo_real else "  (padrao, dados sinteticos)"),
        f"Arquivo .env     : {_caminho_legivel(cfg.arquivo_env)}",
        f"Canais ativos    : {', '.join(cfg.canais) if cfg.canais else NAO_CONFIGURADO + ' (modo mock nao coleta)'}",
        f"Inbox            : {_caminho_legivel(cfg.inbox_dir)}",
        f"Saida            : {_caminho_legivel(cfg.out_dir)}",
        f"Banco            : {_caminho_legivel(cfg.db_path)}",
        f"Log              : {_caminho_legivel(cfg.log_dir)}/pipeline-AAAAMMDD.log (nivel {cfg.log_level})",
        "",
        "Telegram",
        f"  api_base        : {cfg.telegram.api_base}",
        f"  bot token       : {_valor_exibivel(cfg.telegram.token, True)}",
        f"  chat_id         : {_valor_exibivel(cfg.telegram.chat_id, False)}",
        f"  timeout_s       : {cfg.telegram.timeout_s:g}",
        "",
        "WhatsApp",
        f"  api_base        : {cfg.whatsapp.api_base}",
        f"  token           : {_valor_exibivel(cfg.whatsapp.token, True)}",
        f"  phone_number_id : {_valor_exibivel(cfg.whatsapp.phone_number_id, False)}",
        f"  verify_token    : {_valor_exibivel(cfg.whatsapp.verify_token, True)}",
        f"  webhook_dir     : {_caminho_legivel(cfg.whatsapp.webhook_dir)}",
        "",
        "Valores sensiveis aparecem mascarados (ultimos 4 caracteres). "
        "Nenhum segredo vai para log, resumo ou mensagem de erro.",
    ]
    return "\n".join(linhas)


# ------------------------------------------------------------------ .env.example


def exemplo_env() -> str:
    """Texto do `.env.example`, gerado do catalogo e terminado em "\\n".

    Fonte unica (contrato D6): `tools/gerar_env_example.py` (dono: preguica/F9) escreve
    exatamente este texto. Nenhum valor aqui e segredo de verdade - os campos de token
    ficam vazios de proposito.
    """
    linhas = [
        "# Configuracao do pipeline de notas fiscais e pedidos (Squad 7 Pecados)",
        "#",
        "#  1. copie este arquivo para .env na raiz do projeto:  cp .env.example .env",
        "#  2. preencha os campos vazios (os de token/segredo ficam em branco aqui de proposito);",
        "#  3. valide antes de rodar:  .venv/Scripts/python.exe -m app.run --check-config",
        "#",
        "#  O .env NAO vai para o git (esta no .gitignore). Nunca cole um segredo aqui.",
        "#  Sem .env nenhum o app roda em modo mock com os dados sinteticos - isso nao e erro.",
        "#  Este arquivo e gerado do catalogo de app/config.py; nao edite a mao:",
        "#  regenere com  python tools/gerar_env_example.py",
        "",
    ]
    for var in VARIAVEIS:
        marcas = []
        if var.obrigatoria_em:
            marcas.append("obrigatoria em: " + ", ".join(var.obrigatoria_em))
        if var.sensivel:
            marcas.append("SEGREDO - nunca versione o valor")
        titulo = f"# {var.nome}"
        if marcas:
            titulo += "  [" + "; ".join(marcas) + "]"
        linhas.append(titulo)
        linhas.append(f"#   {var.descricao}")
        linhas.append(f"#   Onde obter: {var.onde_obter}")
        if var.padrao:
            linhas.append(f"#   Padrao: {var.padrao}")
        elif var.nome in ("INBOX_DIR", "DB_PATH"):
            padrao_dinamico = {
                "INBOX_DIR": "data/mocks (modo mock) / data/inbox (modo real)",
                "DB_PATH": "<OUT_DIR>/pipeline.db",
            }[var.nome]
            linhas.append(f"#   Padrao: {padrao_dinamico}")
        linhas.append(f"{var.nome}={var.exemplo}")
        linhas.append("")
    return "\n".join(linhas) + "\n"


__all__ = [
    "MODO_MOCK",
    "MODO_REAL",
    "MODOS",
    "ARQUIVO_ENV_PADRAO",
    "RAIZ_PROJETO",
    "CANAIS_CONHECIDOS",
    "NIVEIS_LOG",
    "MASCARA",
    "OBRIGATORIEDADES",
    "Variavel",
    "VARIAVEIS",
    "VARIAVEIS_POR_NOME",
    "ConfigError",
    "TelegramConfig",
    "WhatsAppConfig",
    "Config",
    "carregar",
    "ler_env",
    "mascarar",
    "imprimir_configuracao",
    "exemplo_env",
]
