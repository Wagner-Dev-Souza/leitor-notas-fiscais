"""CLI do pipeline - o comando unico congelado da fase (contrato, secao 2).

    .venv/Scripts/python.exe -m app.run --mock

Flags: `--mock` (usa `data/mocks/` e `data/out/`), `--inbox <dir>`, `--out <dir>`,
`--db <arquivo>`, `--verbose`. Sem argumento, o comportamento e o de `--mock`, que e o
documentado no README.

O resumo impresso aqui e o mesmo que vai para `<out>/resumo.json`: contagens da rodada,
caminhos gerados e a marcacao explicita de quando a leitura veio de OCR **simulado**.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
MOCKS_PADRAO = RAIZ_PROJETO / "data" / "mocks"
OUT_PADRAO = RAIZ_PROJETO / "data" / "out"
DB_PADRAO = OUT_PADRAO / "pipeline.db"


def _legivel(caminho) -> str:
    """Caminho curto para o terminal (relativo quando der)."""
    try:
        return str(Path(caminho).resolve().relative_to(RAIZ_PROJETO))
    except (ValueError, OSError):
        return str(caminho)


def _linha(caractere: str = "-", largura: int = 62) -> str:
    return caractere * largura


def _imprimir_resumo(resumo: dict, verbose: bool) -> None:
    imprimir = print
    imprimir(_linha("="))
    imprimir("Pipeline de leitura de NF/pedidos - resumo da rodada")
    imprimir(_linha("="))
    imprimir(f"Inbox    : {_legivel(resumo['inbox'])}")
    imprimir(f"Saida    : {_legivel(resumo['out_dir'])}")
    imprimir(f"Banco    : {_legivel(resumo['db'])}")
    imprimir(_linha())
    imprimir(
        f"Artefatos ingeridos : {resumo['artefatos']} "
        f"(pdf {resumo['pdfs']} | mensagens {resumo['mensagens']})"
    )
    imprimir(f"Auto-aprovados      : {resumo['auto_aprovados']}")
    imprimir(f"Em revisao humana   : {resumo['revisao']}")
    imprimir(f"Rejeitados          : {resumo['rejeitados']}")
    imprimir(f"Deduplicados        : {resumo['deduplicados']}")
    imprimir(f"Linhas na planilha  : {resumo['linhas_planilha']}")
    imprimir(_linha())
    motores = " | ".join(f"{motor} {qtd}" for motor, qtd in sorted(resumo["por_motor"].items()))
    imprimir(f"Leitura por motor   : {motores or '-'}")
    imprimir(f"OCR                 : {resumo['aviso_ocr']}")
    if resumo["motivos"]:
        imprimir(_linha())
        imprimir("Motivos na fila de excecoes:")
        for motivo, qtd in resumo["motivos"].items():
            imprimir(f"   {motivo:34s} {qtd}")
    imprimir(_linha())
    imprimir("Arquivos gerados:")
    for chave in ("xlsx", "csv", "auditoria", "fila_excecoes", "painel", "resumo", "db"):
        caminho = resumo["arquivos"].get(chave)
        if caminho:
            imprimir(f"   {chave:14s} {_legivel(caminho)}")
    if resumo.get("avisos"):
        imprimir(_linha())
        for aviso in resumo["avisos"]:
            imprimir(f"AVISO: {aviso}")
    if verbose and resumo.get("detalhes"):
        imprimir(_linha())
        imprimir("Detalhe por artefato:")
        for item in resumo["detalhes"]:
            marca_ocr = " [ocr_simulado]" if item.get("ocr_simulado") else ""
            imprimir(
                f"   {Path(item['artefato']).name:34s} {item['acao']:12s} "
                f"conf={item.get('confianca')} valor={item.get('valor_total_centavos')}"
                f" motivos={item.get('motivos')}{marca_ocr}"
            )
    imprimir(_linha("="))
    imprimir(f"Rodada concluida em {resumo['duracao_s']}s")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.run",
        description="Pipeline local de leitura de notas fiscais e pedidos (dados sinteticos).",
    )
    parser.add_argument("--mock", action="store_true", help="usa data/mocks/ e data/out/ (padrao)")
    parser.add_argument("--inbox", default=None, help="diretorio da inbox (pdf/, whatsapp/, telegram/)")
    parser.add_argument("--out", dest="out", default=None, help="diretorio de saida")
    parser.add_argument("--db", dest="db", default=None, help="arquivo sqlite do pipeline")
    parser.add_argument("--verbose", action="store_true", help="imprime o detalhe por artefato")
    return parser


def main(argv=None) -> int:
    argumentos = _parser().parse_args(argv)

    inbox = Path(argumentos.inbox) if argumentos.inbox else MOCKS_PADRAO
    out_dir = Path(argumentos.out) if argumentos.out else OUT_PADRAO
    db_path = Path(argumentos.db) if argumentos.db else (out_dir / "pipeline.db")

    if not Path(inbox).is_dir():
        print(f"inbox nao encontrada: {inbox}", file=sys.stderr)
        print(
            "gere o material sintetico com: .venv/Scripts/python.exe tools/gerar_mocks.py --seed 42",
            file=sys.stderr,
        )
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
        return 130
    except Exception as erro:  # falha real: mostra e devolve codigo de erro
        if argumentos.verbose:
            raise
        print(f"falha na rodada: {type(erro).__name__}: {erro}", file=sys.stderr)
        return 1

    _imprimir_resumo(resumo, argumentos.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
