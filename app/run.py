"""CLI do pipeline - comando unico congelado + camada de operacao (contrato 3.6).

```
.venv/Scripts/python.exe -m app.run --mock          # padrao: dados sinteticos
.venv/Scripts/python.exe -m app.run --real          # coleta dos canais + pipeline
.venv/Scripts/python.exe -m app.run --check-config  # valida a configuracao e sai
```

Flags: `--mock` (padrao), `--real`, `--env <arquivo>`, `--check-config`, `--inbox <dir>`,
`--out <dir>`, `--db <arquivo>`, `--verbose`.

Regras de operacao (secao 3.6):

* `--check-config` valida, imprime `config.imprimir_configuracao(cfg)` e sai 0; com
  configuracao invalida sai 2 com a mensagem do `ConfigError`. **Nao** roda pipeline.
* Modo real: valida -> coleta (`app/canais.py`) -> roda o pipeline no inbox. A importacao
  de `canais` e defensiva (mensagem clara se o modulo nao estiver presente), como o
  `pipeline.py` faz com `revisao`.
* Modo real com configuracao incompleta: mensagem clara citando **cada** variavel
  faltante, codigo 2, nenhum traceback e nenhum segredo no texto.
* Log em arquivo: `<LOG_DIR>/pipeline-<AAAAMMDD>.log` (append), alem do stdout atual.
  Falha ao abrir o log **nao** derruba a rodada: avisa e segue.
* As flags `--mock`/`--real` sobrepoem o `.env`; sem `.env` o app roda em mock, que
  continua sendo o padrao e imprime o MESMO resumo das fases anteriores.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config as configuracao

RAIZ_PROJETO = configuracao.RAIZ_PROJETO
LOGGER = logging.getLogger("app.run")


def _legivel(caminho) -> str:
    """Caminho curto para o terminal (relativo quando der)."""
    try:
        return str(Path(caminho).resolve().relative_to(RAIZ_PROJETO))
    except (ValueError, OSError):
        return str(caminho)


def _linha(caractere: str = "-", largura: int = 62) -> str:
    return caractere * largura


# --------------------------------------------------------------------- log


def _abrir_log(cfg: configuracao.Config) -> tuple[Optional[Path], Optional[str]]:
    """Liga o log em arquivo do dia. Nunca levanta: falha vira aviso e a rodada segue."""
    for handler in list(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # handler ja fechado/invalido nao impede a rodada
            pass

    caminho = Path(cfg.log_dir) / f"pipeline-{datetime.now():%Y%m%d}.log"
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(caminho, mode="a", encoding="utf-8")
    except OSError as erro:
        LOGGER.setLevel(logging.CRITICAL)
        LOGGER.propagate = False
        return None, f"nao foi possivel abrir o log em {caminho} ({erro}); a rodada segue sem arquivo de log"

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    LOGGER.addHandler(handler)
    LOGGER.setLevel(getattr(logging, cfg.log_level, logging.INFO))
    LOGGER.propagate = False
    return caminho, None


def _registrar(linhas, nivel: int = logging.INFO) -> None:
    """Manda as linhas do resumo para o arquivo de log (uma por linha)."""
    for linha in linhas:
        LOGGER.log(nivel, "%s", linha)


# --------------------------------------------------------------------- resumo


def _linhas_resumo(resumo: dict, verbose: bool, contexto: dict) -> list[str]:
    """Linhas do resumo (as mesmas no stdout e no log)."""
    linhas = [
        _linha("="),
        "Pipeline de leitura de NF/pedidos - resumo da rodada",
        _linha("="),
        contexto["modo"],
    ]
    linhas.extend(contexto.get("coleta", []))
    linhas.extend(
        [
            f"Inbox    : {_legivel(resumo['inbox'])}",
            f"Saida    : {_legivel(resumo['out_dir'])}",
            f"Banco    : {_legivel(resumo['db'])}",
            f"Rodada   : {resumo['rodada_id']}",
            _linha(),
            f"Artefatos ingeridos : {resumo['artefatos']} "
            f"(pdf {resumo['pdfs']} | imagens {resumo['imagens']} | "
            f"mensagens {resumo['mensagens']})",
            f"Auto-aprovados      : {resumo['auto_aprovados']}",
            f"Em revisao humana   : {resumo['revisao']}",
            f"Rejeitados          : {resumo['rejeitados']}",
            f"Deduplicados        : {resumo['deduplicados']}",
            f"Linhas na planilha  : {resumo['linhas_planilha']}",
            _linha(),
        ]
    )
    motores = " | ".join(f"{motor} {qtd}" for motor, qtd in sorted(resumo["por_motor"].items()))
    linhas.append(f"Leitura por motor   : {motores or '-'}")
    linhas.append(f"OCR                 : {resumo['aviso_ocr']}")
    linhas.append(
        f"Auditoria           : {resumo['auditoria_linhas_rodada']} linha(s) nesta rodada"
        f" | trilha cumulativa: {resumo['auditoria_linhas_total']} linha(s)"
    )
    if resumo["motivos"]:
        linhas.append(_linha())
        linhas.append("Motivos na fila de excecoes:")
        for motivo, qtd in resumo["motivos"].items():
            linhas.append(f"   {motivo:34s} {qtd}")
    linhas.append(_linha())
    linhas.append("Arquivos gerados:")
    for chave in (
        "xlsx",
        "csv",
        "auditoria",
        "auditoria_rodada",
        "fila_excecoes",
        "painel",
        "resumo",
        "db",
    ):
        caminho = resumo["arquivos"].get(chave)
        if caminho:
            linhas.append(f"   {chave:17s} {_legivel(caminho)}")
    if resumo.get("avisos"):
        linhas.append(_linha())
        for aviso in resumo["avisos"]:
            linhas.append(f"AVISO: {aviso}")
    if verbose and resumo.get("detalhes"):
        linhas.append(_linha())
        linhas.append("Detalhe por artefato:")
        for item in resumo["detalhes"]:
            marca_ocr = " [ocr_simulado]" if item.get("ocr_simulado") else ""
            linhas.append(
                f"   {Path(item['artefato']).name:34s} {item['acao']:12s} "
                f"conf={item.get('confianca')} valor={item.get('valor_total_centavos')}"
                f" motivos={item.get('motivos')}{marca_ocr}"
            )
    linhas.append(_linha("="))
    linhas.append(f"Rodada concluida em {resumo['duracao_s']}s")
    return linhas


def _imprimir_resumo(resumo: dict, verbose: bool, contexto: dict) -> None:
    for linha in _linhas_resumo(resumo, verbose, contexto):
        print(linha)


# --------------------------------------------------------------------- parser


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.run",
        description="Pipeline local de leitura de notas fiscais e pedidos.",
    )
    parser.add_argument("--mock", action="store_true", help="usa data/mocks/ e data/out/ (padrao)")
    parser.add_argument(
        "--real",
        action="store_true",
        help="modo real: coleta dos canais configurados no .env e depois roda o pipeline",
    )
    parser.add_argument(
        "--env",
        dest="env",
        default=None,
        help="arquivo .env a usar (padrao: .env na raiz do projeto, se existir)",
    )
    parser.add_argument(
        "--check-config",
        dest="check_config",
        action="store_true",
        help="valida a configuracao, imprime o relatorio e sai sem rodar o pipeline",
    )
    parser.add_argument("--inbox", default=None, help="diretorio da inbox (pdf/, whatsapp/, telegram/)")
    parser.add_argument("--out", dest="out", default=None, help="diretorio de saida")
    parser.add_argument("--db", dest="db", default=None, help="arquivo sqlite do pipeline")
    parser.add_argument("--verbose", action="store_true", help="imprime o detalhe por artefato")
    return parser


# --------------------------------------------------------------------- coleta


def _coletar(cfg: configuracao.Config) -> tuple[list[str], int]:
    """Roda a coleta do modo real. Devolve (linhas de resumo, codigo de saida)."""
    try:
        from . import canais
    except ImportError:
        print(
            "modo real indisponivel: o modulo de coleta app/canais.py nao esta presente nesta copia.",
            file=sys.stderr,
        )
        print(
            "rode com dados sinteticos (--mock) ou peca a entrega de app/canais.py ao dono da frente F8.",
            file=sys.stderr,
        )
        return [], 2

    erro_canal = getattr(canais, "ErroCanal", None) or Exception
    try:
        resultados = canais.coletar(cfg)
    except erro_canal as erro:
        print(f"falha na coleta dos canais: {erro}", file=sys.stderr)
        print("confira a configuracao (.venv/Scripts/python.exe -m app.run --check-config) e a rede.", file=sys.stderr)
        _registrar([f"falha na coleta dos canais: {erro}"], logging.ERROR)
        return [], 2

    linhas: list[str] = []
    for resultado in resultados or []:
        canal = getattr(resultado, "canal", "?")
        arquivos = tuple(getattr(resultado, "arquivos", ()) or ())
        detalhe = str(getattr(resultado, "detalhe", "") or "")
        mensagens = getattr(resultado, "mensagens", 0)
        if arquivos:
            destino = _legivel(arquivos[0])
            linhas.append(f"Coleta   : {canal}: {mensagens} mensagem(ns) em {destino}")
        else:
            linhas.append(f"Coleta   : {canal}: {detalhe or 'nada novo'}")
    if not linhas:
        linhas.append("Coleta   : nenhum canal retornou (verifique CANAIS_ATIVOS)")
    return linhas, 0


# --------------------------------------------------------------------- main


def main(argv=None) -> int:
    argumentos = _parser().parse_args(argv)

    # As flags --mock/--real sobrepoem o arquivo .env (contrato D1).
    ambiente = None
    if argumentos.real:
        ambiente = {**os.environ, "MODO_EXECUCAO": configuracao.MODO_REAL}
    elif argumentos.mock:
        ambiente = {**os.environ, "MODO_EXECUCAO": configuracao.MODO_MOCK}

    try:
        cfg = configuracao.carregar(env_path=argumentos.env, ambiente=ambiente)
    except configuracao.ConfigError as erro:
        # Mensagem pronta para o operador: nomes de variavel, onde obter, sem traceback.
        print(str(erro), file=sys.stderr)
        return 2

    if argumentos.check_config:
        print(configuracao.imprimir_configuracao(cfg))
        return 0

    caminho_log, aviso_log = _abrir_log(cfg)
    if aviso_log:
        print(f"AVISO: {aviso_log}", file=sys.stderr)
    origem_config = _legivel(cfg.arquivo_env) if cfg.arquivo_env else "nenhum .env (padrao)"
    _registrar(
        [
            f"rodada iniciada: modo={cfg.modo} config={origem_config} "
            f"canais={','.join(cfg.canais) if cfg.canais else '-'}",
        ]
    )

    # ------------------------------------------------------------------ coleta
    linhas_coleta: list[str] = []
    if cfg.modo_real:
        linhas_coleta, codigo = _coletar(cfg)
        if codigo != 0:
            return codigo

    # -------------------------------------------------------- caminhos da rodada
    # Flags de CLI sobrepoem a configuracao (aceite da fase 2 preservado).
    inbox = Path(argumentos.inbox) if argumentos.inbox else Path(cfg.inbox_dir)
    out_dir = Path(argumentos.out) if argumentos.out else Path(cfg.out_dir)
    db_path = Path(argumentos.db) if argumentos.db else Path(cfg.db_path)

    if not Path(inbox).is_dir():
        print(f"inbox nao encontrada: {inbox}", file=sys.stderr)
        if cfg.modo_real:
            print(
                "no modo real a coleta precisa ter gravado ao menos um envelope; "
                "confira CANAIS_ATIVOS e a credencial no .env (--check-config mostra o que esta faltando).",
                file=sys.stderr,
            )
        else:
            print(
                "gere o material sintetico com: .venv/Scripts/python.exe tools/gerar_mocks.py --seed 42",
                file=sys.stderr,
            )
        _registrar([f"inbox nao encontrada: {inbox}"], logging.ERROR)
        return 2

    try:
        from .pipeline import processar
    except ImportError as erro:
        print(f"dependencia ausente para rodar o pipeline: {erro.name}", file=sys.stderr)
        print(
            "o modulo pertence a outra frente (tabela da secao 3 do contrato). "
            "Nada foi executado e nenhum resultado foi inventado.",
            file=sys.stderr,
        )
        return 2

    try:
        resumo = processar(inbox, out_dir, db_path, incluir_detalhes=argumentos.verbose)
    except KeyboardInterrupt:
        print("interrompido pelo usuario", file=sys.stderr)
        _registrar(["interrompido pelo usuario"], logging.WARNING)
        return 130
    except Exception as erro:  # falha real: mostra e devolve codigo de erro
        _registrar([f"falha na rodada: {type(erro).__name__}: {erro}"], logging.ERROR)
        if argumentos.verbose:
            raise
        print(f"falha na rodada: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 1

    contexto = {
        "modo": (
            f"Modo     : {cfg.modo}"
            + (f" | canais: {', '.join(cfg.canais)}" if cfg.canais else "")
            + f" | config: {origem_config}"
        ),
        "coleta": linhas_coleta,
    }
    linhas = _linhas_resumo(resumo, argumentos.verbose, contexto)
    for linha in linhas:
        print(linha)
    _registrar(linhas)
    if caminho_log:
        LOGGER.info("rodada concluida; log em %s", caminho_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
