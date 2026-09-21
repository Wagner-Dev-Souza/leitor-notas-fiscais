#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gera o `.env.example` a partir do catalogo de `app/config.py` - frente F9 (preguica).

Contrato: `docs/execucao/00b-contrato-fechamento.md`, secao 3.4 (e decisao D6 do PO).

Regra do arquivo: **nunca digitado a mao**. O texto sai de `config.exemplo_env()`, que por
sua vez sai de `config.VARIAVEIS`. Se a variavel existe no codigo, ela esta no exemplo; se
esta no exemplo, existe no codigo. Divergencia = defeito.

Uso:

    .venv/Scripts/python.exe tools/gerar_env_example.py              # escreve .env.example
    .venv/Scripts/python.exe tools/gerar_env_example.py --conferir    # so compara (exit != 0 se divergir)
    .venv/Scripts/python.exe tools/gerar_env_example.py --saida outro.env.example

Antes de escrever, o script confere o proprio texto (sanidade):

* toda variavel do catalogo aparece como `NOME=` em uma linha propria;
* nenhuma linha `NOME=` cita uma variavel que nao existe no catalogo;
* variavel sensivel nunca sai com valor preenchido (nem placeholder de segredo);
* o texto termina em quebra de linha.

O arquivo nao contem segredo nenhum: os campos sensiveis ficam vazios de proposito, para o
operador preencher no `.env` (que o git ignora).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import re
import sys
import time
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import config as configuracao  # noqa: E402

SAIDA_PADRAO = RAIZ / ".env.example"
LINHA_VARIAVEL = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


# ------------------------------------------------------------------ utilidades


def com_retry(acao, descricao: str, tentativas: int = 8, espera: float = 0.35):
    """Tolera lock de arquivo do Windows (varios agentes no mesmo worktree)."""
    for tentativa in range(tentativas):
        try:
            return acao()
        except PermissionError:
            if tentativa == tentativas - 1:
                raise SystemExit(
                    f"ERRO: {descricao} esta em uso por outro processo (lock do Windows)"
                )
            time.sleep(espera)


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def problemas_de_sanidade(texto: str) -> list[str]:
    """Confere o texto gerado contra o catalogo. Lista vazia = tudo certo."""
    problemas: list[str] = []
    nomes_catalogo = [var.nome for var in configuracao.VARIAVEIS]

    no_arquivo: dict[str, str] = {}
    for linha in texto.splitlines():
        casado = LINHA_VARIAVEL.match(linha)
        if casado:
            no_arquivo[casado.group(1)] = casado.group(2)

    faltando = [nome for nome in nomes_catalogo if nome not in no_arquivo]
    if faltando:
        problemas.append(f"variavel do catalogo sem linha no exemplo: {', '.join(faltando)}")

    sobrando = [nome for nome in no_arquivo if nome not in nomes_catalogo]
    if sobrando:
        problemas.append(f"linha no exemplo para variavel fora do catalogo: {', '.join(sobrando)}")

    for var in configuracao.VARIAVEIS:
        valor = no_arquivo.get(var.nome)
        if valor is None:
            continue
        if var.sensivel and valor.strip():
            problemas.append(
                f"{var.nome} e sensivel e saiu com valor preenchido no exemplo (tem de ser vazio)"
            )
        if var.nome in ("MODO_EXECUCAO", "CANAIS_ATIVOS") and not valor.strip():
            problemas.append(f"{var.nome} e obrigatoria sempre e nao pode sair vazia no exemplo")

    if not texto.endswith("\n"):
        problemas.append('o texto nao termina em "\\n"')
    return problemas


def ler_texto(caminho: Path) -> Optional[str]:
    """Le normalizando fim de linha (aceita LF ou CRLF, de qualquer checkout)."""
    if not caminho.is_file():
        return None
    texto = caminho.read_text(encoding="utf-8")
    return texto.replace("\r\n", "\n")


def escrever_texto(caminho: Path, texto: str) -> None:
    """Grava com fim de linha LF explicito.

    O modo texto do Windows traduziria `\\n` para `\\r\\n`, o arquivo versionado ficaria com
    CRLF e o tamanho no disco nao bateria com o conteudo gerado.
    """
    with caminho.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)


def diff_legivel(atual: str, esperado: str, nome: str) -> str:
    linhas = difflib.unified_diff(
        atual.splitlines(keepends=True),
        esperado.splitlines(keepends=True),
        fromfile=f"{nome} (em disco)",
        tofile=f"{nome} (gerado do catalogo)",
        n=2,
    )
    return "".join(linhas) or "(sem diferenca de conteudo)"


# ----------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Gera o .env.example a partir do catalogo de app/config.py."
    )
    ap.add_argument("--saida", default=str(SAIDA_PADRAO),
                    help="arquivo a gerar (padrao: .env.example na raiz do projeto)")
    ap.add_argument("--conferir", action="store_true",
                    help="nao escreve: compara com o arquivo em disco e sai != 0 se divergir")
    ap.add_argument("--quiet", action="store_true", help="imprime so o resultado")
    args = ap.parse_args(argv)

    destino = Path(args.saida)
    if not destino.is_absolute():
        destino = (RAIZ / destino).resolve()

    def dizer(texto: str = "") -> None:
        if not args.quiet:
            print(texto)

    dizer("=" * 74)
    dizer("GERADOR DO .env.example - tools/gerar_env_example.py (F9 / preguica)")
    dizer("=" * 74)
    dizer(f"catalogo : app/config.py -> VARIAVEIS ({len(configuracao.VARIAVEIS)} variaveis)")
    dizer(f"destino  : {destino}")

    # ------------------------------------------------- fonte unica: o catalogo
    try:
        esperado = configuracao.exemplo_env()
    except Exception as erro:  # catalogo quebrado e defeito do dono, nao chute
        print(f"FALHOU: nao consegui gerar o texto a partir do catalogo: "
              f"{type(erro).__name__}: {erro}")
        return 2

    problemas = problemas_de_sanidade(esperado)
    if problemas:
        print("FALHOU: o texto gerado nao passou na sanidade:")
        for problema in problemas:
            print(f"  - {problema}")
        return 2

    atual = com_retry(lambda: ler_texto(destino), str(destino))
    atual_bytes = com_retry(
        lambda: destino.read_bytes() if destino.is_file() else None, str(destino)
    )
    esperado_bytes = esperado.encode("utf-8")

    # ------------------------------------------------------------- --conferir
    if args.conferir:
        dizer("-" * 74)
        if atual is None:
            print(f"FALHOU: {destino} nao existe. "
                  f"rode: .venv/Scripts/python.exe tools/gerar_env_example.py")
            return 1
        if atual != esperado:
            print(f"FALHOU: {destino} esta fora de sincronia com o catalogo.")
            print(diff_legivel(atual, esperado, destino.name))
            print("regenere com: .venv/Scripts/python.exe tools/gerar_env_example.py")
            return 1
        if atual_bytes != esperado_bytes:
            print(f"AVISO: conteudo igual, mas o arquivo em disco tem {len(atual_bytes)} bytes "
                  f"e o gerado tem {len(esperado_bytes)} (fim de linha do checkout). "
                  f"Rode o gerador sem --conferir para normalizar em LF.")
        print(f"PASSOU: {destino.name} em sincronia com o catalogo "
              f"({len(configuracao.VARIAVEIS)} variaveis, sha256 {sha256_texto(esperado)[:16]})")
        return 0

    # ---------------------------------------------------------------- escrever
    if atual_bytes == esperado_bytes:
        dizer("-" * 74)
        dizer(f"sem mudanca: {destino.name} ja estava igual ao catalogo "
              f"({len(esperado_bytes)} bytes, sha256 {sha256_texto(esperado)[:16]})")
        return 0

    com_retry(lambda: escrever_texto(destino, esperado), str(destino))
    dizer("-" * 74)
    dizer(f"gravado: {destino}")
    dizer(f"  variaveis : {len(configuracao.VARIAVEIS)}")
    dizer(f"  conteudo  : {len(esperado.encode('utf-8'))} bytes | linhas: "
          f"{len(esperado.splitlines())} | fim de linha: LF")
    dizer(f"  arquivo   : {destino.stat().st_size} bytes no disco")
    dizer(f"  sha256    : {sha256_texto(esperado)}")
    dizer(f"  sensiveis : {sum(1 for v in configuracao.VARIAVEIS if v.sensivel)} "
          f"(saem com valor vazio, para o operador preencher no .env)")
    if atual is not None:
        dizer("  (arquivo anterior era diferente - regravado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
