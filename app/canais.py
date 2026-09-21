"""Coleta real dos canais - frente F8, fase 3 (dono: gula).

Implementa a secao 3.2 de `docs/execucao/00b-contrato-fechamento.md`: no modo real os
canais **coletam e gravam envelopes no inbox** no MESMO formato dos mocks de
`data/mocks/{whatsapp,telegram}/*.jsonl`, para o pipeline atual digerir sem alteracao e a
idempotencia continuar valendo.

Decisao de escopo declarada (D4 do contrato): **nao existe token nem numero real autorizado
nesta entrega**. Nada aqui chama `api.telegram.org` ou `graph.facebook.com` por conta
propria: a chamada credenciada real nao foi executada. O que esta provado e a montagem da
requisicao, a gravacao do envelope e o ciclo completo contra um **stub HTTP local**
(`127.0.0.1`), injetado pelo seam `TransporteHTTP`. Ver `docs/execucao/_ids/relato-F8.md`.

Somente biblioteca padrao. Nenhum segredo em `detalhe`, nome de arquivo ou mensagem de erro:
mensagem cita o **nome** da variavel (`TELEGRAM_BOT_TOKEN`), nunca o valor, e a URL da
Telegram (que embute o token no caminho) nunca aparece em texto - so o `api_base`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

__all__ = [
    "CANAL_TELEGRAM",
    "CANAL_WHATSAPP",
    "CANAIS_CONHECIDOS",
    "ErroCanal",
    "ErroHTTP",
    "ErroRede",
    "ResultadoColeta",
    "TransporteHTTP",
    "transporte_urllib",
    "envelopes_telegram",
    "coletar_telegram",
    "ler_webhook_whatsapp",
    "coletar",
]

CANAL_TELEGRAM = "telegram"
CANAL_WHATSAPP = "whatsapp"
CANAIS_CONHECIDOS = (CANAL_WHATSAPP, CANAL_TELEGRAM)

_SUFIXOS_WEBHOOK = (".json", ".jsonl")
_PASTA_PROCESSADOS = "processados"

# Nomes das variaveis citadas nas mensagens de erro (nunca o valor delas)
_VARIAVEIS_TELEGRAM = "TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_API_BASE"
_VARIAVEIS_WHATSAPP = "WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_API_BASE"


class ErroCanal(Exception):
    """Falha de coleta. Mensagem em pt-BR com o canal e a causa, sem segredo."""


class ErroHTTP(Exception):
    """Resposta HTTP de erro do transporte. Carrega `status` e `motivo` (sem URL)."""

    def __init__(self, status: int, motivo: str = "") -> None:
        self.status = int(status)
        self.motivo = motivo or ""
        super().__init__(f"HTTP {self.status}{': ' + self.motivo if self.motivo else ''}")


class ErroRede(Exception):
    """Falha de rede/DNS/timeout do transporte (sem URL, para nao vazar token)."""


@dataclass(frozen=True)
class ResultadoColeta:
    """Resultado de uma coleta de canal (contrato 3.2)."""

    canal: str
    destino: Path
    arquivos: tuple[Path, ...]
    mensagens: int
    detalhe: str

    @property
    def gravou(self) -> bool:
        return bool(self.arquivos)


@runtime_checkable
class TransporteHTTP(Protocol):
    """Seam de teste: o QA injeta um stub local; a producao usa `transporte_urllib()`."""

    def get_json(
        self,
        url: str,
        params: Optional[dict] = None,
        cabecalhos: Optional[dict] = None,
        timeout: float = 30,
    ) -> dict: ...

    def post_json(
        self,
        url: str,
        corpo: dict,
        cabecalhos: Optional[dict] = None,
        timeout: float = 30,
    ) -> dict: ...


class _TransporteUrllib:
    """Transporte real, `urllib` da biblioteca padrao.

    Levanta `ErroHTTP` (com o status) ou `ErroRede`, **sem URL na mensagem**: a URL do
    Telegram carrega o token no caminho e nao pode ir para log.
    """

    def _executar(self, requisicao: "urllib.request.Request", timeout: float) -> dict:
        try:
            with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
                bruto = resposta.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            motivo = ""
            try:
                corpo_erro = exc.read().decode("utf-8", errors="replace")
                dados = json.loads(corpo_erro)
                motivo = str(dados.get("description") or dados.get("error") or "")
            except Exception:  # corpo de erro nem sempre e JSON: nao importa
                motivo = str(exc.reason or "")
            raise ErroHTTP(int(exc.code), motivo) from None
        except urllib.error.URLError as exc:
            raise ErroRede(str(getattr(exc, "reason", exc) or "falha de rede")) from None
        except TimeoutError as exc:
            raise ErroRede(f"tempo esgotado: {exc}") from None

        if not bruto.strip():
            return {}
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError as exc:
            raise ErroRede(f"resposta nao e JSON valido ({exc.msg})") from None
        return dados if isinstance(dados, dict) else {"result": dados}

    def get_json(
        self,
        url: str,
        params: Optional[dict] = None,
        cabecalhos: Optional[dict] = None,
        timeout: float = 30,
    ) -> dict:
        alvo = url
        if params:
            alvo = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        requisicao = urllib.request.Request(
            alvo, headers={"Accept": "application/json", **(cabecalhos or {})}, method="GET"
        )
        return self._executar(requisicao, timeout)

    def post_json(
        self,
        url: str,
        corpo: dict,
        cabecalhos: Optional[dict] = None,
        timeout: float = 30,
    ) -> dict:
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        requisicao = urllib.request.Request(
            url,
            data=dados,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                **(cabecalhos or {}),
            },
            method="POST",
        )
        return self._executar(requisicao, timeout)


def transporte_urllib() -> TransporteHTTP:
    """Transporte real (producao). Os testes injetam o proprio stub."""
    return _TransporteUrllib()


# ------------------------------------------------------------------ utilitarios internos


def _agora_marca() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _gravar_envelopes(destino: Path, canal: str, envelopes: Sequence[dict]) -> Path:
    """Grava UM arquivo `<canal>_coleta_<AAAAMMDD-HHMMSS>.jsonl`, uma linha por envelope."""
    pasta = Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"{canal}_coleta_{_agora_marca()}"
    caminho = pasta / f"{base}.jsonl"
    sufixo = 2
    while caminho.exists():  # duas coletas no mesmo segundo nao se sobrescrevem
        caminho = pasta / f"{base}_{sufixo}.jsonl"
        sufixo += 1
    with open(caminho, "w", encoding="utf-8") as fh:
        for envelope in envelopes:
            fh.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    return caminho


def _erro_de_transporte(
    canal: str, operacao: str, api_base: str, exc: BaseException, variaveis: str
) -> ErroCanal:
    """Converte falha do transporte em `ErroCanal` sem vazar token/URL credenciada.

    Cita o **nome** das variaveis de configuracao envolvidas (nunca o valor): para 401/403
    o problema e credencial; para 404, o endereco base.
    """
    base = (api_base or "").rstrip("/")
    dica = variaveis
    if isinstance(exc, ErroHTTP):
        if exc.status in (401, 403):
            primeiro = variaveis.split(",")[0].strip()
            dica = f"{primeiro} (credencial recusada)"
        elif exc.status == 404:
            ultimo = variaveis.split(",")[-1].strip()
            dica = f"{ultimo} (endereco base nao encontrado)"
        return ErroCanal(
            f"{canal}: {operacao} recusado em {base} (HTTP {exc.status}"
            f"{' ' + exc.motivo if exc.motivo else ''}). Confira {dica} no .env - nenhuma "
            f"credencial e impressa aqui."
        )
    if isinstance(exc, ErroRede):
        return ErroCanal(
            f"{canal}: {operacao} nao alcancou {base} ({exc}). Verifique a rede/proxy e "
            f"{dica}; no modo mock nada disso e necessario."
        )
    return ErroCanal(f"{canal}: {operacao} falhou ({type(exc).__name__}: {exc}). Confira {dica}.")


def _config_presente(cfg: Any) -> bool:
    return cfg is not None and hasattr(cfg, "inbox_dir")


# ------------------------------------------------------------------ Telegram (getUpdates)


def envelopes_telegram(updates: Sequence[dict], chat_id: Optional[str] = None) -> list[dict]:
    """`result` do `getUpdates` -> envelopes no formato de `data/mocks/telegram/*.jsonl`.

    Cada update ja vem da API com a mesma forma do mock (`{"update_id": ..., "message": ...}`):
    aqui so se descarta lixo, o que nao tem mensagem e - quando `chat_id` e informado - o que
    nao e do chat configurado.
    """
    saida: list[dict] = []
    alvo = str(chat_id).strip() if chat_id is not None else ""
    for update in updates or []:
        if not isinstance(update, dict):
            continue
        mensagem = update.get("message") or update.get("edited_message") or update.get("channel_post")
        if not isinstance(mensagem, dict):
            continue
        if alvo:
            chat = mensagem.get("chat") or {}
            if str(chat.get("id", "")).strip() != alvo:
                continue
        saida.append(update)
    return saida


def coletar_telegram(
    cfg: Any,
    transporte: Optional[TransporteHTTP] = None,
    destino: Optional[Path] = None,
    offset: Optional[int] = None,
) -> ResultadoColeta:
    """`GET {api_base}/bot{token}/getUpdates` e grava os updates no inbox.

    O `chat_id` e filtrado **localmente** por `message.chat.id` (o `getUpdates` nao aceita
    `chat_id` como parametro; mandar isso quebraria a chamada).

    Sem update novo: `arquivos=()` com `detalhe` explicando - nao e erro.
    Falha de rede/HTTP: `ErroCanal` com o status, citando o **nome** da variavel.
    """
    if not _config_presente(cfg):
        raise ErroCanal("telegram: configuracao ausente - carregue o .env antes de coletar")
    telegram = cfg.telegram
    api_base = str(getattr(telegram, "api_base", "") or "").rstrip("/")
    token = str(getattr(telegram, "token", "") or "")
    if not api_base:
        raise ErroCanal("telegram: TELEGRAM_API_BASE nao configurado no .env")
    if not token:
        raise ErroCanal(
            "telegram: falta TELEGRAM_BOT_TOKEN no .env - sem token nao ha coleta "
            "(no modo mock a coleta nao e usada)"
        )

    pasta = Path(destino) if destino is not None else (Path(cfg.inbox_dir) / CANAL_TELEGRAM)
    transporte = transporte or transporte_urllib()
    url = f"{api_base}/bot{token}/getUpdates"

    # offset: o que veio por parametro manda; senao o estado da ultima coleta. Sem estado
    # nenhum (primeira rodada) fica None e o Telegram devolve o que estiver pendente.
    if offset is None:
        offset = ler_offset_telegram(cfg)
    params: dict[str, Any] = {}
    if offset is not None:
        params["offset"] = int(offset)
    timeout = float(getattr(telegram, "timeout_s", 30) or 30)

    try:
        resposta = transporte.get_json(url, params=params or None, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - vira ErroCanal com mensagem clara
        raise _erro_de_transporte(
            CANAL_TELEGRAM, "getUpdates", api_base, exc, _VARIAVEIS_TELEGRAM
        ) from exc

    if not isinstance(resposta, dict):
        raise ErroCanal(f"telegram: getUpdates devolveu resposta inesperada em {api_base}")
    if resposta.get("ok") is False:
        descricao = str(resposta.get("description") or "sem descricao")
        raise ErroCanal(
            f"telegram: getUpdates recusado ({descricao}). Confira TELEGRAM_BOT_TOKEN "
            f"e TELEGRAM_CHAT_ID no .env."
        )

    updates = resposta.get("result") or []
    # Confirma a leitura ANTES de filtrar: o update de outro chat tambem foi visto.
    if updates:
        gravar_offset_telegram(cfg, updates)

    envelopes = envelopes_telegram(
        updates, getattr(telegram, "chat_id", None) or None
    )
    if not envelopes:
        return ResultadoColeta(
            canal=CANAL_TELEGRAM,
            destino=pasta,
            arquivos=(),
            mensagens=0,
            detalhe=(
                "telegram: getUpdates sem update novo (fila vazia"
                f"{' ou nenhum update do chat configurado' if getattr(telegram, 'chat_id', '') else ''})"
                f" - nada a gravar, e nao e erro (offset atual: {offset})"
            ),
        )

    caminho = _gravar_envelopes(pasta, CANAL_TELEGRAM, envelopes)
    return ResultadoColeta(
        canal=CANAL_TELEGRAM,
        destino=pasta,
        arquivos=(caminho,),
        mensagens=len(envelopes),
        detalhe=(
            f"telegram: {len(envelopes)} update(s) gravado(s) em {caminho.name} "
            f"| offset confirmado ate {ler_offset_telegram(cfg)}"
        ),
    )


# --- estado da coleta: offset do Telegram -------------------------------------
#
# O `getUpdates` devolve TODA a janela de updates pendentes enquanto ninguem passa
# `offset`; passar `offset = ultimo_update_id + 1` e a confirmacao de leitura do Telegram.
# Sem guardar isso, cada rodada re-baixa o historico inteiro: a deduplicacao do pipeline
# segura a duplicata (por isso o dado nunca sai errado), mas o custo cresce com o tamanho
# do historico. O estado mora no OUT_DIR, junto da saida e do banco.

ARQUIVO_OFFSET_TELEGRAM = "telegram_offset.json"


def caminho_offset_telegram(cfg: Any) -> Path:
    return Path(cfg.out_dir) / ARQUIVO_OFFSET_TELEGRAM


def ler_offset_telegram(cfg: Any) -> Optional[int]:
    """Proximo offset a enviar, ou None se nunca houve coleta (primeira rodada)."""
    caminho = caminho_offset_telegram(cfg)
    if not caminho.is_file():
        return None
    try:
        return int(json.loads(caminho.read_text(encoding="utf-8"))["proximo_offset"])
    except (OSError, ValueError, KeyError, TypeError):
        # estado ilegivel nao pode derrubar a coleta: trata como primeira rodada
        return None


def gravar_offset_telegram(cfg: Any, updates: list[dict]) -> Optional[int]:
    """Confirma a leitura gravando `max(update_id) + 1`.

    Confirma TODOS os updates recebidos, inclusive os de outro chat (que o filtro local
    descarta): eles foram vistos pelo bot e nao podem voltar na proxima rodada.
    """
    # update malformado (o Telegram pode devolver qualquer coisa) nao pode derrubar
    # a coleta: so dict com update_id inteiro entra na conta.
    identificadores = [
        update.get("update_id") for update in updates
        if isinstance(update, dict) and isinstance(update.get("update_id"), int)
    ]
    if not identificadores:
        return ler_offset_telegram(cfg)
    proximo = max(identificadores) + 1
    caminho = caminho_offset_telegram(cfg)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps({"proximo_offset": proximo, "confirmado_em": _agora_marca()}, indent=2) + "\n",
        encoding="utf-8",
    )
    return proximo


# ------------------------------------------------------------------ WhatsApp (webhook local)


def ler_webhook_whatsapp(
    cfg: Any, destino: Optional[Path] = None, mover: bool = True
) -> ResultadoColeta:
    """Consome os envelopes deixados pelo receptor de webhook e grava no inbox.

    Cada `.json`/`.jsonl` em `cfg.whatsapp.webhook_dir` e um envelope do Cloud API
    (`{"object": "whatsapp_business_account", "entry": [...]}`). Com `mover=True` o arquivo
    consumido vai para `<webhook_dir>/processados/`. Envelope sem `entry` (webhook de status)
    e descartado com `detalhe` explicando - nao e erro.
    """
    if not _config_presente(cfg):
        raise ErroCanal("whatsapp: configuracao ausente - carregue o .env antes de coletar")

    origem = Path(getattr(cfg.whatsapp, "webhook_dir", "") or "")
    pasta = Path(destino) if destino is not None else (Path(cfg.inbox_dir) / CANAL_WHATSAPP)
    if not str(origem) or str(origem) in (".", ""):
        raise ErroCanal(
            f"whatsapp: coleta do webhook sem diretorio configurado. Confira "
            f"{_VARIAVEIS_WHATSAPP} no .env."
        )
    if not origem.exists():
        return ResultadoColeta(
            canal=CANAL_WHATSAPP,
            destino=pasta,
            arquivos=(),
            mensagens=0,
            detalhe=(
                f"whatsapp: diretorio de webhook {origem.name} ainda nao existe - suba o "
                "receptor (tools/receber_webhook_whatsapp.py) ou aponte WHATSAPP_WEBHOOK_DIR"
            ),
        )

    arquivos = sorted(
        item
        for item in origem.iterdir()
        if item.is_file()
        and item.suffix.lower() in _SUFIXOS_WEBHOOK
        and item.parent.name != _PASTA_PROCESSADOS
    )

    envelopes: list[dict] = []
    descartados = 0
    invalidos = 0
    consumidos: list[Path] = []
    for arquivo in arquivos:
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except OSError:
            invalidos += 1
            continue
        consumidos.append(arquivo)
        for linha in texto.splitlines():
            if not linha.strip():
                continue
            try:
                objeto = json.loads(linha)
            except json.JSONDecodeError:
                invalidos += 1
                continue
            if isinstance(objeto, dict) and objeto.get("entry"):
                envelopes.append(objeto)
            else:
                descartados += 1  # webhook de status/entrega: sem mensagem

    extras = []
    if descartados:
        extras.append(f"{descartados} sem 'entry' descartado(s) (status de entrega)")
    if invalidos:
        extras.append(f"{invalidos} linha(s)/arquivo(s) ilegiveis mantidos para inspecao")
    cauda = f"; {', '.join(extras)}" if extras else ""

    if not envelopes:
        return ResultadoColeta(
            canal=CANAL_WHATSAPP,
            destino=pasta,
            arquivos=(),
            mensagens=0,
            detalhe=f"whatsapp: nenhum envelope com mensagem em {origem.name}{cauda}",
        )

    caminho = _gravar_envelopes(pasta, CANAL_WHATSAPP, envelopes)

    movidos = 0
    if mover and consumidos:
        processados = origem / _PASTA_PROCESSADOS
        processados.mkdir(parents=True, exist_ok=True)
        for arquivo in consumidos:
            try:
                arquivo.replace(processados / arquivo.name)
                movidos += 1
            except OSError:
                pass  # arquivo travado: fica onde esta, sem derrubar a coleta

    return ResultadoColeta(
        canal=CANAL_WHATSAPP,
        destino=pasta,
        arquivos=(caminho,),
        mensagens=len(envelopes),
        detalhe=(
            f"whatsapp: {len(envelopes)} envelope(s) de {len(consumidos)} arquivo(s) gravado(s) "
            f"em {caminho.name}"
            + (f"; {movidos} arquivo(s) movido(s) para {_PASTA_PROCESSADOS}/" if movidos else "")
            + cauda
        ),
    )


# ------------------------------------------------------------------ orquestracao da coleta


def coletar(
    cfg: Any,
    canais: Optional[Sequence[str]] = None,
    transporte: Optional[TransporteHTTP] = None,
) -> list[ResultadoColeta]:
    """Coleta os canais pedidos (ou `cfg.canais`) e devolve um resultado por canal.

    Canal desabilitado/desconhecido nunca levanta: entra no resultado com `detalhe`
    explicando. Falha real de rede/HTTP de um canal levanta `ErroCanal` (o comando devolve
    codigo != 0 e diz o que fazer).
    """
    if canais is None:
        canais = tuple(getattr(cfg, "canais", ()) or ()) if cfg is not None else ()
    resultados: list[ResultadoColeta] = []

    for canal in canais:
        nome = str(canal).strip().lower()
        if nome == CANAL_TELEGRAM:
            resultados.append(coletar_telegram(cfg, transporte=transporte))
        elif nome == CANAL_WHATSAPP:
            resultados.append(ler_webhook_whatsapp(cfg))
        else:
            destino = Path(getattr(cfg, "inbox_dir", ".") or ".")
            resultados.append(
                ResultadoColeta(
                    canal=nome,
                    destino=destino,
                    arquivos=(),
                    mensagens=0,
                    detalhe=(
                        f"{nome}: canal desconhecido ignorado (conhecidos: "
                        f"{', '.join(CANAIS_CONHECIDOS)})"
                    ),
                )
            )
    return resultados
