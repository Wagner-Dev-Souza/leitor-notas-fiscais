"""Receptor local do webhook do WhatsApp Cloud API - frente F8 (dono: gula).

Seçao 3.3 de `docs/execucao/00b-contrato-fechamento.md`. Somente biblioteca padrao
(`http.server`). Papel no produto: no modo real o WhatsApp nao tem *pull* de mensagens -
um receptor local recebe o webhook e **grava o envelope** em `WHATSAPP_WEBHOOK_DIR`; a
coleta (`app.canais.ler_webhook_whatsapp`) leva esse envelope para o inbox, no mesmo
formato dos mocks, e o pipeline segue sem alteracao.

Comportamento:
  * `GET <rota>?hub.mode=subscribe&hub.verify_token=<...>&hub.challenge=X`
    -> responde `X` (200) quando o token confere; 403 quando nao confere.
  * `POST <rota>` com o envelope JSON -> grava
    `<WHATSAPP_WEBHOOK_DIR>/<AAAAMMDD-HHMMSS>_<n>.json` e responde 200.
  * Cada requisicao vira UMA linha de log. O token **nunca** e impresso - nem o caminho
    com query crua, que o carrega; o log mostra a rota e o nome do parametro.

Assinatura do POST (`X-Hub-Signature-256`): com `WHATSAPP_APP_SECRET` configurado, todo POST
tem a assinatura conferida (HMAC-SHA256 do corpo BRUTO, comparado em tempo constante) **antes**
de qualquer gravacao - assinatura ausente ou que nao confere responde 401 e nada e gravado.
Sem o app secret o receptor sobe com aviso explicito na tela e segue aceitando o POST sem
conferir a origem: e o modo que permite a prova local sem credencial real, e por isso ele
avisa alto em vez de fingir que esta seguro.

Uso:
    .venv/Scripts/python.exe tools/receber_webhook_whatsapp.py [--host 127.0.0.1]
        [--porta 8787] [--env .env] [--uma-vez]
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

ROTA_PADRAO = "/webhook/whatsapp"
LIMITE_CORPO_BYTES = 5 * 1024 * 1024  # webhook de mensagem e pequeno; acima disso, recusa
CABECALHO_ASSINATURA = "X-Hub-Signature-256"


def _assinatura_confere(app_secret: str, corpo: bytes, cabecalho: str) -> bool:
    """Confere `X-Hub-Signature-256: sha256=<hex>` sobre o corpo BRUTO (HMAC-SHA256).

    Comparacao em tempo constante (`hmac.compare_digest`). Nao revela o valor esperado nem o
    recebido: quem le o log so sabe que nao conferiu.
    """
    if not cabecalho:
        return False
    partes = cabecalho.split("=", 1)
    if len(partes) != 2 or partes[0].strip().lower() != "sha256":
        return False
    esperado = hmac.new(app_secret.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, partes[1].strip().lower())


def _linha(mensagem: str) -> None:
    print(mensagem, flush=True)


def _carregar_config(caminho_env):
    """Le a configuracao pelo fonte unica (`app/config.py`, dono: F7).

    Devolve `(cfg, erro)`: em erro, `cfg` e None e `erro` ja e a mensagem pronta para o
    operador (sem traceback e sem valor de segredo).
    """
    try:
        from app import config as config_mod
    except ImportError as exc:
        return None, (
            "app/config.py nao esta disponivel "
            f"({exc}). Esta frente (F8) depende do modulo de configuracao (F7/avareza) "
            "para ler o .env: rode depois que ele existir."
        )
    try:
        cfg = config_mod.carregar(caminho_env) if caminho_env else config_mod.carregar()
    except Exception as exc:  # ConfigError: mensagens ja prontas para o operador
        return None, str(exc)
    return cfg, None


def _nome_arquivo(destino: Path, contador: int) -> Path:
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidato = destino / f"{marca}_{contador}.json"
    extra = contador
    while candidato.exists():
        extra += 1
        candidato = destino / f"{marca}_{extra}.json"
    return candidato


def _criar_handler(verify_token: str, destino: Path, uma_vez: bool, app_secret: str = ""):
    estado = {"posts": 0}

    class HandlerWebhook(BaseHTTPRequestHandler):
        server_version = "WebhookWhatsAppF8/1.0"

        def log_message(self, formato, *args):  # noqa: D401 - log proprio, em uma linha
            return  # silencia o log padrao (a linha e escrita por _log)

        def log_error(self, formato, *args):  # noqa: D401 - idem: ruido do http.server
            return

        # ---------------------------------------------------------------- helpers

        def _texto(self, status: int, corpo: str, tipo: str = "text/plain; charset=utf-8"):
            dados = corpo.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def _json(self, status: int, corpo: dict):
            self._texto(status, json.dumps(corpo, ensure_ascii=False), "application/json; charset=utf-8")

        def _log(self, metodo: str, detalhe: str) -> None:
            rota = urlparse(self.path).path
            _linha(f"{datetime.now().strftime('%H:%M:%S')} {metodo} {rota} {detalhe}")

        def _encerrar_se_uma_vez(self) -> None:
            if not uma_vez:
                return
            # shutdown() precisa sair da thread que atende a requisicao
            import threading

            threading.Thread(target=self.server.shutdown, daemon=True).start()

        # ---------------------------------------------------------------- verbos

        def do_GET(self):  # noqa: N802 - API do http.server
            partes = urlparse(self.path)
            consulta = parse_qs(partes.query)
            modo = (consulta.get("hub.mode") or [""])[0]
            token_recebido = (consulta.get("hub.verify_token") or [""])[0]
            desafio = (consulta.get("hub.challenge") or [""])[0]

            if modo != "subscribe":
                self._log("GET", f"403 modo invalido (hub.mode={modo or 'ausente'})")
                self._texto(403, "403")
                return
            if not token_recebido or token_recebido != verify_token:
                # NUNCA imprimir o valor recebido: so o fato de nao conferir
                self._log("GET", "403 hub.verify_token nao confere")
                self._texto(403, "403")
                return
            self._log("GET", f"200 verificacao aceita (challenge com {len(desafio)} caractere(s))")
            self._texto(200, desafio)

        def do_POST(self):  # noqa: N802 - API do http.server
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                tamanho = 0
            if tamanho <= 0:
                self._log("POST", "400 corpo vazio")
                self._json(400, {"erro": "corpo vazio"})
                return
            if tamanho > LIMITE_CORPO_BYTES:
                self._log("POST", f"413 corpo grande demais ({tamanho} bytes)")
                self._json(413, {"erro": "corpo grande demais"})
                return

            bruto = self.rfile.read(tamanho)

            if app_secret:
                cabecalho = self.headers.get(CABECALHO_ASSINATURA) or ""
                if not _assinatura_confere(app_secret, bruto, cabecalho):
                    self._log("POST", "401 assinatura X-Hub-Signature-256 ausente ou nao confere")
                    self._json(401, {"erro": "assinatura ausente ou invalida"})
                    return

            try:
                envelope = json.loads(bruto.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._log("POST", f"400 JSON invalido ({type(exc).__name__})")
                self._json(400, {"erro": "JSON invalido"})
                return

            if not isinstance(envelope, dict):
                self._log("POST", "400 JSON nao e objeto")
                self._json(400, {"erro": "envelope precisa ser objeto JSON"})
                return

            estado["posts"] += 1
            arquivo = _nome_arquivo(destino, estado["posts"])
            try:
                arquivo.write_text(json.dumps(envelope, ensure_ascii=False) + "\n", encoding="utf-8")
            except OSError as exc:
                self._log("POST", f"500 falha ao gravar envelope ({type(exc).__name__})")
                self._json(500, {"erro": "falha ao gravar envelope"})
                return

            tem_entry = bool(envelope.get("entry"))
            self._log(
                "POST",
                f"200 gravado {arquivo.name} ({len(bruto)} bytes, "
                f"{'com' if tem_entry else 'sem'} entry)"
                + (" - encerrando (--uma-vez)" if uma_vez else ""),
            )
            self._json(200, {"status": "recebido", "arquivo": arquivo.name})
            self._encerrar_se_uma_vez()

        def do_PUT(self):  # noqa: N802
            self._log("PUT", "405 metodo nao suportado")
            self._json(405, {"erro": "metodo nao suportado"})

    HandlerWebhook.estado = estado           # contador acessivel depois do serve_forever
    HandlerWebhook.destino = destino
    return HandlerWebhook


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Receptor local do webhook do WhatsApp Cloud API (grava envelopes para a coleta)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="endereco de escuta (padrao 127.0.0.1)")
    parser.add_argument("--porta", type=int, default=8787, help="porta de escuta (padrao 8787)")
    parser.add_argument("--env", default=None, help="arquivo .env alternativo (padrao: .env da raiz)")
    parser.add_argument(
        "--uma-vez",
        action="store_true",
        help="encerra depois do primeiro POST (usado na prova de aceite)",
    )
    args = parser.parse_args(argv)

    cfg, erro = _carregar_config(args.env)
    if erro is not None:
        _linha(f"ERRO de configuracao: {erro}")
        _linha("Nada foi iniciado. Corrija o .env (veja .env.example) e rode de novo.")
        return 2

    verify_token = str(getattr(cfg.whatsapp, "verify_token", "") or "")
    if not verify_token:
        _linha(
            "ERRO: falta WHATSAPP_VERIFY_TOKEN no .env - sem esse token o receptor nao consegue "
            "confirmar a verificacao do webhook (GET hub.verify_token). Nao vou iniciar."
        )
        return 2

    app_secret = str(getattr(cfg.whatsapp, "app_secret", "") or "")

    destino = Path(cfg.whatsapp.webhook_dir)
    destino.mkdir(parents=True, exist_ok=True)

    handler = _criar_handler(verify_token, destino, bool(args.uma_vez), app_secret)
    try:
        servidor = ThreadingHTTPServer((args.host, args.porta), handler)
    except OSError as exc:
        _linha(f"ERRO: nao consegui escutar em {args.host}:{args.porta} ({exc.strerror or exc}).")
        return 2

    _linha(
        f"escutando em http://{args.host}:{args.porta} | rota {ROTA_PADRAO} | "
        f"destino de envelopes: {destino} | verify_token: configurado (valor nunca e impresso)"
    )
    if app_secret:
        _linha(
            "assinatura do POST: VALIDADA (X-Hub-Signature-256 conferida com WHATSAPP_APP_SECRET; "
            "valor nunca e impresso)"
        )
    else:
        _linha(
            "AVISO: WHATSAPP_APP_SECRET nao configurado - o POST e aceito SEM conferir a "
            "assinatura X-Hub-Signature-256. Defina o app secret no .env antes de expor este "
            "receptor fora da maquina local."
        )
    _linha("pronto para receber o webhook (GET de verificacao + POST de envelope). Ctrl+C encerra.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        _linha("encerrando por Ctrl+C")
    finally:
        servidor.server_close()
    _linha(f"receptor encerrado ({handler.estado['posts']} POST(s) gravado(s) nesta execucao).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
