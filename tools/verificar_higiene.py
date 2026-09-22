#!/usr/bin/env python
"""Reprova material que nao pode entrar em um repositorio publico de vitrine.

Por que existe
--------------
O repositorio e publico. Caminho da maquina de quem executa e dump bruto de execucao
nao sao segredo: sao sujeira. Revelam o ambiente e o processo interno de trabalho e
fazem um projeto serio parecer roda de laboratorio. Este verificador roda no CI e
falha o push de quem trouxer qualquer coisa disso.

O que ele cobre
---------------
- caminho da maquina de quem executa
- dump de execucao versionado (fechamento, ids, fotografia por rodada)
- arquivo com nome de segredo (.env, .pem, .key, secrets*, credentials*)

Credencial com valor ja e coberta por `tests/test_producao.py` (`varrer_segredos`), que
continua valendo e nao e duplicada aqui.

Uso
---
    python tools/verificar_higiene.py         # sai com codigo 1 quando encontra problema
"""

import re
import subprocess
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
ESTE_ARQUIVO = Path(__file__).resolve()

# Padroes montados por concatenacao de proposito: assim este arquivo nao casa consigo
# mesmo ao ser varrido, e continua podendo ser versionado sem excecao escondida.
PADROES_TEXTO = [
    ("caminho da maquina", re.compile(r"(?i)[A-ZAa-z]:[\\/]{1,2}" + "Users" + r"[\\/]")),
    ("caminho de sistema unix", re.compile(r"(?<![\w.])/(home|Users)/[A-Za-z0-9._-]+/")),
    ("nome de pasta pessoal", re.compile("Meu" + " Computador")),
]

PADROES_CAMINHO_VERSIONADO = [
    ("dump de fechamento", re.compile(r"^docs/execucao/" + "_fech/")),
    ("dump de ids", re.compile(r"^docs/execucao/" + "_ids/")),
    ("fotografia por rodada", re.compile(r"auditoria_rodada_\d{8}-\d{6}\.jsonl$")),
]

NOMES_DE_SEGREDO = ("secrets", "credentials", "id_rsa")
SUFIXOS_DE_SEGREDO = (".pem", ".key")


def versionados() -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ_PROJETO, capture_output=True, text=True, check=True
    )
    return [linha for linha in saida.stdout.splitlines() if linha.strip()]


def eh_binario(caminho: Path) -> bool:
    try:
        return b"\x00" in caminho.read_bytes()[:2048]
    except OSError:
        return True


def texto_de(caminho: Path) -> str | None:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def main() -> int:
    problemas: list[str] = []

    for relativo in versionados():
        caminho = RAIZ_PROJETO / relativo

        nome = Path(relativo).name.lower()
        if nome == ".env" or nome.endswith(SUFIXOS_DE_SEGREDO) or nome.startswith(NOMES_DE_SEGREDO):
            problemas.append(f"{relativo}: arquivo com nome de segredo versionado")

        for descricao, padrao in PADROES_CAMINHO_VERSIONADO:
            if padrao.search(relativo):
                problemas.append(f"{relativo}: {descricao} versionado")

        if caminho.resolve() == ESTE_ARQUIVO or eh_binario(caminho):
            continue

        conteudo = texto_de(caminho)
        if conteudo is None:
            continue
        for descricao, padrao in PADROES_TEXTO:
            achado = padrao.search(conteudo)
            if achado:
                problemas.append(f"{relativo}: {descricao} ({achado.group(0)!r})")

    if problemas:
        print("material que nao pode ser versionado neste repositorio:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        print(
            "\ncorrija: troque o caminho por um marcador (<local>) e remova o dump. "
            "O objetivo e o repositorio mostrar o produto e o processo, nao o ambiente "
            "de quem executou.",
            file=sys.stderr,
        )
        return 1

    print(f"higiene ok: {len(versionados())} arquivo(s) versionado(s) conferido(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
