#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verificador de producao - frente F9 (preguica).

Contrato: `docs/execucao/00b-contrato-fechamento.md`, secao 3.5. Roda os 6 checks de
operacao com **execucao real** (`subprocess` chamando `python -m app.run ...`) e imprime
PASSOU/FALHOU por item. Sai != 0 se qualquer item falhar.

    1. `.env.example` presente, versionado e em sincronia com o catalogo.
    2. Nenhum `.env` real versionado e `.env` presente no `.gitignore`.
    3. Modo mock continua sendo o padrao (sem `.env`, roda e nao exige segredo).
    4. Modo real sem as variaveis obrigatorias -> mensagem clara citando cada variavel
       faltante, sem traceback e sem rodar o pipeline.
    5. Varredura de segredo em arquivo versionado (inclusive `.env.example`).
    6. `.env` de teste com valores ficticios -> `--check-config` reconhece tudo e **mascara**
       os valores sensiveis.

Regras de trabalho respeitadas:

* **Nada de `git` de escrita.** So consulta: `git ls-files`, `git check-ignore`,
  `git status --porcelain` (leitura).
* Tudo roda em **diretorio temporario proprio**; este script **nao escreve em `data/`** -
  e prova isso comparando o retrato de `data/` antes e depois (a prova sai no resumo).
  O unico ponto fora do retrato e `data/out/`: isso e **saida de rodada**, e o check 1 roda
  o comando congelado `app.run --mock`, cujo trabalho e justamente regrava-la.
* Nao reimplementa a logica de configuracao: quem valida e o `app/run.py` de verdade.
  Comportamento ausente no codigo = check FALHANDO (e a informacao que o cliente quer).
* Nenhum valor de segredo aparece na saida: os valores ficticios usados nos checks moram em
  arquivo temporario e a unica forma de cita-los aqui e por nome de variavel.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import config as configuracao  # noqa: E402

NOMES_CATALOGO = tuple(var.nome for var in configuracao.VARIAVEIS)
SENSIVEIS = tuple(var.nome for var in configuracao.VARIAVEIS if var.sensivel)

LINHA_VARIAVEL = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")

# --- padroes obvios de segredo (check 5) -------------------------------------
PADROES_SEGREDO = (
    ("chave-privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("token-telegram", re.compile(r"\b\d{8,13}:[A-Za-z0-9_-]{30,}\b")),
    ("token-meta", re.compile(r"\bEAA[A-Za-z0-9_-]{20,}\b")),
    ("token-google", re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")),
    ("token-openai", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("token-github", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
)
# Numero de telefone (brasileiro, com DDI). Os mocks sinteticos declarados usam numeros
# ficticios; fora deles, numero em arquivo versionado e sinal de alerta.
PADRAO_TELEFONE = re.compile(r"\b55\d{10,11}\b")
# Numero de exemplo obvio: 7+ digitos iguais seguidos (ex.: 5511999999999).
NUMERO_PLACEHOLDER = re.compile(r"(\d)\1{6,}")
PASTAS_SINTETICAS = ("data/mocks/",)

# Marcadores que dizem "isto e exemplo, nao e segredo de verdade".
MARCADORES_PLACEHOLDER = re.compile(
    r"(fake|fictic|dummy|placeholder|exemplo|exemplo-|teste|test-|nao-e-segredo|troque|"
    r"seu-|minha-|xxx|aaaa|1111|1234567890|"
    r"nao[-_ ]?pode[-_ ]?aparecer|nao[-_ ]?vaza|apenas|somente|so[-_ ]?para|mascar|"
    r"prova|redacted|redigid)",
    re.IGNORECASE,
)

# Valor que e nome de variavel (Python) e REFERENCIA, nao segredo: `TELEGRAM_BOT_TOKEN=
# TOKEN_TELEGRAM` nos testes aponta para a constante; o literal esta em outro lugar.
VALOR_E_REFERENCIA = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Mesmo criterio da suite: caractere repetido 6+ vezes e numero/valor de exemplo, nao
# credencial de verdade (credencial real tem entropia).
VALOR_REPETIDO = re.compile(r"(.)\1{5,}")
LINHA_ATRIBUICAO_SENSIVEL = re.compile(
    r"^\s*(?:export\s+)?(" + "|".join(SENSIVEIS) + r")\s*=\s*(\S.*)$"
)

EXTENSOES_TEXTO = {
    ".py", ".md", ".txt", ".json", ".jsonl", ".cfg", ".toml", ".ini", ".yaml", ".yml",
    ".env", ".example", ".sh", ".ps1", ".csv", ".html", ".js", ".ts", ".gitignore",
}
LIMITE_BYTES = 1_500_000


# ------------------------------------------------------------------ utilidades


def resolver_python(preferido: Optional[str]) -> str:
    if preferido:
        return preferido
    if Path(sys.executable).name.lower().startswith("python") and (
        ".venv" in sys.executable.replace("\\", "/")
    ):
        return sys.executable
    for rel in ("Scripts/python.exe", "bin/python"):
        candidato = RAIZ / ".venv" / rel
        if candidato.exists():
            return str(candidato)
    return sys.executable


def ambiente_limpo() -> dict:
    """Ambiente sem nenhuma variavel do catalogo: prova que o padrao nao exige config."""
    limpo = {chave: valor for chave, valor in os.environ.items() if chave not in NOMES_CATALOGO}
    limpo["PYTHONIOENCODING"] = "utf-8"
    limpo["PYTHONUTF8"] = "1"
    return limpo


def rodar_app(python: str, argumentos: list[str], extra_env: Optional[dict] = None,
              timeout: int = 180) -> subprocess.CompletedProcess:
    """Roda o comando unico de verdade. Nunca uso shell: lista de argumentos."""
    ambiente = ambiente_limpo()
    if extra_env:
        ambiente.update(extra_env)
    return subprocess.run(
        [python, "-m", "app.run", *argumentos],
        cwd=str(RAIZ), env=ambiente, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def git(*argumentos: str) -> subprocess.CompletedProcess:
    """Somente consulta (ls-files/check-ignore/status). Nunca escreve no repositorio."""
    return subprocess.run(
        ["git", *argumentos], cwd=str(RAIZ), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def retrato_data() -> dict:
    """Retrato de cheap de data/: (tamanho, mtime_ns) por arquivo.

    `data/out/` fica **fora** do retrato de proposito: e a saida da rodada, e o check 1 roda
    o comando congelado `app.run --mock`, que regrava planilha, trilha, fila, painel e banco
    ali - e o trabalho dele. Cobrar do script que ele nao reescreva a propria saida dava
    `data/ intacto: False` com os 6 checks passando, e o verificador saia com codigo 1
    (defeito relatado na fase anterior e corrigido aqui).

    O que o retrato protege e o material que **nao** pode mudar sozinho: `data/mocks/`
    (corpus sintetico) e todo o resto de `data/`.
    """
    raiz = RAIZ / "data"
    saida_de_rodada = (raiz / "out").resolve()
    retrato: dict[str, tuple[int, int]] = {}
    if not raiz.is_dir():
        return retrato
    for caminho in sorted(raiz.rglob("*")):
        if not caminho.is_file():
            continue
        try:
            resolvido = caminho.resolve()
            if resolvido == saida_de_rodada or saida_de_rodada in resolvido.parents:
                continue
            info = caminho.stat()
        except OSError:
            continue
        retrato[caminho.relative_to(RAIZ).as_posix()] = (info.st_size, info.st_mtime_ns)
    return retrato


def escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")


def nomes_do_texto(texto: str) -> set[str]:
    return {
        casado.group(1)
        for linha in texto.splitlines()
        if (casado := LINHA_VARIAVEL.match(linha))
    }


# ---------------------------------------------------------------------- checks


def check_1_env_example(tmp: Path, python: str) -> tuple[bool, str, list[str]]:
    """.env.example presente, versionado e em sincronia com o catalogo."""
    arquivo = RAIZ / ".env.example"
    evidencia: list[str] = []
    if not arquivo.is_file():
        return False, ".env.example nao existe na raiz do projeto", evidencia

    esperado = configuracao.exemplo_env()
    atual = arquivo.read_text(encoding="utf-8")
    nomes_arquivo = nomes_do_texto(atual)
    nomes_catalogo = set(NOMES_CATALOGO)

    rastreado = git("ls-files", "--error-unmatch", "--", ".env.example").returncode == 0
    ignorado = git("check-ignore", "-q", "--", ".env.example").returncode == 0
    status = git("status", "--porcelain", "--", ".env.example").stdout.strip()

    evidencia.append(f"variaveis no catalogo: {len(nomes_catalogo)}")
    evidencia.append(f"variaveis com linha no exemplo: {len(nomes_arquivo)}")
    evidencia.append(f"em sincronia com config.exemplo_env(): {atual == esperado}")
    evidencia.append(f"ignorado pelo .gitignore: {ignorado} (tem de ser False)")
    evidencia.append(f"rastreado pelo git (git ls-files): {rastreado}")
    evidencia.append(f"git status --porcelain: {status or '(limpo)'}")

    problemas: list[str] = []
    if atual != esperado:
        problemas.append("conteudo fora de sincronia com o catalogo "
                         "(rode tools/gerar_env_example.py)")
    if nomes_arquivo != nomes_catalogo:
        problemas.append(
            f"conjunto de variaveis difere do catalogo: "
            f"so no arquivo={sorted(nomes_arquivo - nomes_catalogo)} | "
            f"so no catalogo={sorted(nomes_catalogo - nomes_arquivo)}"
        )
    if ignorado:
        problemas.append(".env.example esta no .gitignore (nao seria versionado)")

    if problemas:
        return False, "; ".join(problemas), evidencia

    detalhe = (f"{len(nomes_catalogo)} variaveis do catalogo presentes e em sincronia"
               + ("" if rastreado else " | AVISO: ainda nao esta no indice do git - o PO "
                                       "versiona nesta onda (nao ignorado, entao entra)"))
    return True, detalhe, evidencia


def check_2_env_fora_do_git(tmp: Path, python: str) -> tuple[bool, str, list[str]]:
    """Nenhum .env real versionado e .env presente no .gitignore."""
    evidencia: list[str] = []
    resultado = git("ls-files")
    if resultado.returncode != 0:
        return False, f"git ls-files falhou: {resultado.stderr.strip()}", evidencia
    rastreados = [linha.strip() for linha in resultado.stdout.splitlines() if linha.strip()]
    sospeitos = [
        caminho for caminho in rastreados
        if Path(caminho).name == ".env" or caminho.endswith("/.env")
    ]
    env_example_versionado = ".env.example" in rastreados
    ignorado = git("check-ignore", "-q", "--", ".env").returncode == 0

    evidencia.append(f"arquivos rastreados: {len(rastreados)}")
    evidencia.append(f"'.env' versionado: {sospeitos or 'nenhum'}")
    evidencia.append(f"'.env' no .gitignore: {ignorado}")
    evidencia.append(f"'.env.example' versionado: {env_example_versionado}")

    problemas = []
    if sospeitos:
        problemas.append(f".env versionado no repositorio: {sospeitos}")
    if not ignorado:
        problemas.append("'.env' nao esta no .gitignore (um segredo local poderia ser commitado)")
    if problemas:
        return False, "; ".join(problemas), evidencia
    return True, "nenhum .env versionado; '.env' ignorado pelo git", evidencia


def check_3_modo_mock_padrao(tmp: Path, python: str) -> tuple[bool, str, list[str]]:
    """Modo mock continua sendo o padrao (sem .env, roda e nao exige segredo)."""
    evidencia: list[str] = []
    out_dir = tmp / "check3" / "out"
    db = tmp / "check3" / "out" / "pipeline.db"
    log_dir = tmp / "check3" / "logs"
    env_local = RAIZ / ".env"

    # Sem --mock de proposito: o padrao tem de ser mock sozinho.
    resultado = rodar_app(
        python,
        ["--inbox", str(RAIZ / "data" / "mocks"), "--out", str(out_dir), "--db", str(db)],
        extra_env={"LOG_DIR": str(log_dir)},
    )
    evidencia.append(f"comando: python -m app.run --inbox data/mocks --out <tmp> --db <tmp> "
                     f"(sem --mock, sem .env)")
    evidencia.append(f"modo no ambiente do processo: nada de MODO_EXECUCAO/segredos "
                     f"(ambiente limpo com {len(NOMES_CATALOGO)} variaveis removidas)")
    evidencia.append(f"'.env' presente na raiz do projeto: {env_local.is_file()}")
    evidencia.append(f"exit code: {resultado.returncode}")
    linhas_modo = [l for l in resultado.stdout.splitlines() if l.startswith("Modo ")]
    for linha in linhas_modo:
        evidencia.append(f"  stdout: {linha}")
    if resultado.stderr.strip():
        evidencia.append(f"stderr: {resultado.stderr.strip().splitlines()[-1]}")

    if resultado.returncode != 0:
        return False, f"o comando padrao saiu com codigo {resultado.returncode}", evidencia
    if "Traceback" in resultado.stdout + resultado.stderr:
        return False, "o comando padrao imprimiu traceback", evidencia
    if not any(re.search(r"Modo\s*:\s*mock\b", linha) for linha in linhas_modo):
        return False, ("sem .env e sem --mock o comando NAO rodou em modo mock "
                       f"(linhas de modo: {linhas_modo or 'nenhuma'})"), evidencia
    if not (out_dir / "controle_financeiro.xlsx").is_file():
        return False, "rodou mas nao gerou a planilha de saida no diretorio temporario", evidencia
    if not any(p.stat().st_size > 0 for p in out_dir.glob("*")):
        return False, "saida do pipeline esta vazia", evidencia
    return True, "sem .env o padrao e mock, roda e nao pede credencial nenhuma", evidencia


def check_4_modo_real_sem_credencial(tmp: Path, python: str) -> tuple[bool, str, list[str]]:
    """Modo real sem as obrigatorias: mensagem clara, sem traceback, sem rodar pipeline."""
    evidencia: list[str] = []
    pasta = tmp / "check4"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo_env = pasta / "real-sem-credencial.env"
    out_dir = pasta / "out"
    escrever(
        arquivo_env,
        "# cenario do check 4: modo real pedido, nenhuma credencial preenchida\n"
        "MODO_EXECUCAO=real\n"
        "CANAIS_ATIVOS=whatsapp,telegram\n"
        f"LOG_DIR={pasta.as_posix()}/logs\n"
        f"OUT_DIR={out_dir.as_posix()}\n",
    )
    resultado = rodar_app(python, ["--real", "--env", str(arquivo_env)])
    saida = resultado.stdout + resultado.stderr
    evidencia.append(f"comando: python -m app.run --real --env <tmp>/real-sem-credencial.env")
    evidencia.append(f"exit code: {resultado.returncode}")
    for linha in resultado.stderr.strip().splitlines():
        evidencia.append(f"  stderr: {linha}")

    esperadas = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "WHATSAPP_TOKEN",
                 "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN"]
    faltando_no_texto = [nome for nome in esperadas if nome not in saida]
    rodou_pipeline = out_dir.exists() and any(out_dir.iterdir())

    problemas = []
    if resultado.returncode == 0:
        problemas.append("o comando saiu com codigo 0 no modo real sem credencial")
    if "Traceback" in saida:
        problemas.append("imprimiu traceback")
    if faltando_no_texto:
        problemas.append(f"nao citou pelo nome: {faltando_no_texto}")
    if rodou_pipeline:
        problemas.append("o pipeline rodou mesmo sem configuracao valida")

    evidencia.append(f"saida do pipeline criada em <tmp>: {rodou_pipeline}")
    evidencia.append(f"variaveis citadas pelo nome: "
                     f"{[n for n in esperadas if n in saida]}")
    if problemas:
        return False, "; ".join(problemas), evidencia
    return True, (f"codigo {resultado.returncode}, citou as {len(esperadas)} variaveis "
                  f"faltantes pelo nome, sem traceback e sem rodar o pipeline"), evidencia


def _classificar_ocorrencia(caminho: str, linha: str, achado: str) -> str:
    """'placeholder' e exemplo declarado; 'suspeito' e ocorrencia com cara de real.

    Nao ha filtro por arquivo: o criterio olha o VALOR e a linha. Credencial de verdade
    (entropia real, sem marcador, sem repeticao) continua reprovando.
    """
    if MARCADORES_PLACEHOLDER.search(linha) or MARCADORES_PLACEHOLDER.search(achado):
        return "placeholder"
    if VALOR_REPETIDO.search(achado):
        return "placeholder"
    return "suspeito"


def _numeros_sinteticos_declarados() -> set[str]:
    """Numeros que o proprio material sintetico (`data/mocks/`) declara como ficticios.

    A comparacao e contra o material versionado, nao contra uma lista escrita a mao: numero
    novo, que nao vem do mock, continua sendo tratado como suspeito.
    """
    numeros: set[str] = set()
    raiz = RAIZ / "data" / "mocks"
    if not raiz.is_dir():
        return numeros
    for caminho in raiz.rglob("*"):
        if not caminho.is_file() or caminho.suffix.lower() not in (".jsonl", ".json", ".txt"):
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        numeros.update(PADRAO_TELEFONE.findall(texto))
    return numeros


def check_5_varredura_segredo(tmp: Path, python: str) -> tuple[bool, str, list[str]]:
    """Varredura de segredo nos arquivos versionados (git ls-files)."""
    evidencia: list[str] = []
    resultado = git("ls-files")
    if resultado.returncode != 0:
        return False, f"git ls-files falhou: {resultado.stderr.strip()}", evidencia
    arquivos = [linha.strip() for linha in resultado.stdout.splitlines() if linha.strip()]

    sinteticos = _numeros_sinteticos_declarados()
    lidos = pulados = 0
    suspeitos: list[str] = []
    placeholders: list[str] = []
    ficticios: list[str] = []

    for relativo in arquivos:
        caminho = RAIZ / relativo
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() not in EXTENSOES_TEXTO and caminho.name != ".gitignore":
            pulados += 1
            continue
        try:
            if caminho.stat().st_size > LIMITE_BYTES:
                pulados += 1
                continue
            texto = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pulados += 1
            continue
        lidos += 1
        sintetico = relativo.replace("\\", "/").startswith(PASTAS_SINTETICAS)

        for numero_linha, linha in enumerate(texto.splitlines(), start=1):
            for rotulo, padrao in PADROES_SEGREDO:
                achado = padrao.search(linha)
                if not achado:
                    continue
                registro = f"{relativo}:{numero_linha} [{rotulo}]"
                if _classificar_ocorrencia(relativo, linha, achado.group(0)) == "placeholder":
                    placeholders.append(registro)
                else:
                    suspeitos.append(registro)

            atribuicao = LINHA_ATRIBUICAO_SENSIVEL.match(linha)
            if atribuicao:
                # tira o que e sintaxe de chamada (`VAR=VALOR,`) para olhar o VALOR
                valor = atribuicao.group(2).strip().strip("'\"").rstrip(",").strip()
                # `VAR=SENSIVEL` onde SENSIVEL e o nome de uma constante do codigo nao e
                # valor preenchido: e referencia. O literal, se existir, e avaliado na
                # propria linha em que aparece.
                if VALOR_E_REFERENCIA.match(valor):
                    valor = ""
                if valor:
                    registro = (f"{relativo}:{numero_linha} "
                                f"[{atribuicao.group(1)} com valor preenchido em arquivo "
                                f"versionado]")
                    if MARCADORES_PLACEHOLDER.search(valor):
                        placeholders.append(registro)
                    else:
                        suspeitos.append(registro)

            if not sintetico:
                telefone = PADRAO_TELEFONE.search(linha)
                if telefone:
                    numero = telefone.group(0)
                    if numero in sinteticos:
                        ficticios.append(
                            f"{relativo}:{numero_linha} [{numero} - numero ficticio do "
                            f"material sintetico de data/mocks]"
                        )
                    elif NUMERO_PLACEHOLDER.search(numero) or MARCADORES_PLACEHOLDER.search(linha):
                        placeholders.append(
                            f"{relativo}:{numero_linha} [{numero} - numero de exemplo]"
                        )
                    else:
                        suspeitos.append(
                            f"{relativo}:{numero_linha} [{numero} - numero com DDI 55 fora de "
                            f"data/mocks e fora do material sintetico]"
                        )

    evidencia.append(f"arquivos versionados: {len(arquivos)} | lidos como texto: {lidos} | "
                     f"pulados (binario/grande): {pulados}")
    evidencia.append(f"padroes procurados: "
                     f"{', '.join(rotulo for rotulo, _ in PADROES_SEGREDO)}, "
                     f"variavel sensivel com valor atribuido, telefone DDI 55 (fora do material "
                     f"sintetico, que tem {len(sinteticos)} numeros ficticios declarados em "
                     f"data/mocks)")
    evidencia.append(f"IGNORADO por ser o proprio material sintetico: data/mocks/**")
    evidencia.append(f"numeros ficticios declarados reencontrados em outros arquivos: "
                     f"{len(ficticios)}")
    for registro in ficticios[:25]:
        evidencia.append(f"  - {registro}")
    evidencia.append(f"placeholders de exemplo: {len(placeholders)}")
    for registro in placeholders[:25]:
        evidencia.append(f"  - {registro}")
    evidencia.append(f"SUSPEITOS (segredo ou numero real): {len(suspeitos)}")
    for registro in suspeitos[:25]:
        evidencia.append(f"  - {registro}")

    if suspeitos:
        return False, f"{len(suspeitos)} ocorrencia(s) suspeita(s) em arquivo versionado", evidencia
    return True, (f"{len(arquivos)} arquivos versionados varridos: nenhum segredo e nenhum "
                  f"numero fora do material sintetico ({len(ficticios)} numeros ficticios "
                  f"declarados reencontrados, {len(placeholders)} placeholders de exemplo)"), \
        evidencia


def _env_ficticio(pasta: Path) -> Path:
    """`.env` de teste, com valores obviamente ficticios (moram no diretorio temporario)."""
    arquivo = pasta / "env-ficticio.env"
    escrever(
        arquivo,
        "# check 6: configuracao completa com valores FICTICIOS (nao e credencial de verdade)\n"
        "MODO_EXECUCAO=real\n"
        "CANAIS_ATIVOS=whatsapp,telegram\n"
        f"OUT_DIR={pasta.as_posix()}/out\n"
        f"LOG_DIR={pasta.as_posix()}/logs\n"
        "LOG_LEVEL=DEBUG\n"
        "TELEGRAM_BOT_TOKEN=1111111111:FAKE-teste-nao-e-segredo-de-verdade\n"
        "TELEGRAM_CHAT_ID=-1001234567890\n"
        "TELEGRAM_TIMEOUT_S=15\n"
        "WHATSAPP_TOKEN=FAKE-teste-nao-e-segredo-de-verdade-0002\n"
        "WHATSAPP_PHONE_NUMBER_ID=123456789012345\n"
        "WHATSAPP_VERIFY_TOKEN=FAKE-teste-nao-e-segredo-de-verdade-0003\n",
    )
    return arquivo


def check_6_check_config_mascara(tmp: Path, python: str) -> tuple[bool, str, list[str]]:
    """`.env` ficticio -> --check-config reconhece tudo e mascara os sensiveis."""
    evidencia: list[str] = []
    pasta = tmp / "check6"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo_env = _env_ficticio(pasta)
    resultado = rodar_app(python, ["--check-config", "--env", str(arquivo_env)])
    saida = resultado.stdout + resultado.stderr

    valores_ficticios = {}
    for linha in arquivo_env.read_text(encoding="utf-8").splitlines():
        casado = LINHA_VARIAVEL.match(linha)
        if casado and casado.group(1) in SENSIVEIS:
            valores_ficticios[casado.group(1)] = casado.group(2).strip()

    evidencia.append(f"comando: python -m app.run --check-config --env <tmp>/env-ficticio.env")
    evidencia.append(f"exit code: {resultado.returncode}")
    for linha in resultado.stdout.strip().splitlines():
        evidencia.append(f"  stdout: {linha}")

    problemas = []
    if resultado.returncode != 0:
        problemas.append(f"saida {resultado.returncode}: a configuracao ficticia nao foi aceita")
    if "Traceback" in saida:
        problemas.append("imprimiu traceback")
    if re.search(r"Modo de execucao\s*:\s*real", saida) is None:
        problemas.append("nao reconheceu o modo real do .env de teste")

    for nome, valor in valores_ficticios.items():
        mascara = configuracao.mascarar(valor)
        evidencia.append(f"  {nome}: mascarado na saida = {mascara in saida}")
        if valor in saida:
            problemas.append(f"o valor de {nome} apareceu inteiro na saida")
        if mascara not in saida:
            problemas.append(f"{nome} nao saiu mascarado ({mascara})")

    if problemas:
        return False, "; ".join(problemas), evidencia
    return True, (f"configuracao ficticia aceita (exit 0) e os {len(valores_ficticios)} valores "
                  f"sensiveis mascarados na saida"), evidencia


CHECKS: tuple[tuple[str, Callable[[Path, str], tuple[bool, str, list[str]]]], ...] = (
    (".env.example presente, versionado e em sincronia com o catalogo",
     check_1_env_example),
    ("nenhum .env real versionado e .env no .gitignore", check_2_env_fora_do_git),
    ("modo mock continua sendo o padrao (sem .env, roda e nao exige segredo)",
     check_3_modo_mock_padrao),
    ("modo real sem as obrigatorias -> mensagem clara, sem traceback, sem rodar pipeline",
     check_4_modo_real_sem_credencial),
    ("varredura de segredo em arquivo versionado (inclusive .env.example)",
     check_5_varredura_segredo),
    ("`.env` de teste com valores ficticios -> --check-config reconhece e mascara",
     check_6_check_config_mascara),
)


# ----------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verificador de producao (6 checks, execucao real).")
    ap.add_argument("--python", default=None, help="interpretador do projeto")
    ap.add_argument("--manter-temp", action="store_true", help="nao apaga o diretorio temporario")
    ap.add_argument("--detalhe", action="store_true", help="mostra a evidencia completa")
    args = ap.parse_args(argv)

    python = resolver_python(args.python)
    print("=" * 78)
    print("VERIFICADOR DE PRODUCAO - tools/verificar_producao.py (F9 / preguica)")
    print("contrato: docs/execucao/00b-contrato-fechamento.md secao 3.5")
    print("=" * 78)
    print(f"projeto  : {RAIZ}")
    print(f"python   : {python}")
    print("data/    : retrato tirado antes e conferido depois (este script nao escreve la; "
          "data/out e saida de rodada e fica fora do retrato)")
    print("-" * 78)

    antes = retrato_data()
    tmp = Path(tempfile.mkdtemp(prefix="verificar_producao_"))
    print(f"temporario: {tmp}")
    print("-" * 78)

    resultados: list[tuple[str, bool, str, list[str]]] = []
    try:
        for indice, (titulo, funcao) in enumerate(CHECKS, start=1):
            try:
                ok, detalhe, evidencia = funcao(tmp, python)
            except subprocess.TimeoutExpired:
                ok, detalhe, evidencia = False, "o comando de execucao real estourou o tempo", []
            except Exception as erro:  # defeito real: falha declarada, nunca silenciosa
                ok, detalhe, evidencia = False, f"{type(erro).__name__}: {erro}", []
            resultados.append((titulo, ok, detalhe, evidencia))
            marca = "PASSOU" if ok else "FALHOU"
            print(f"[{indice}/6] {titulo}")
            print(f"        {marca}: {detalhe}")
            if args.detalhe or not ok:
                for linha in evidencia:
                    print(f"          {linha}")
            print()
    finally:
        if not args.manter_temp:
            shutil.rmtree(tmp, ignore_errors=True)

    depois = retrato_data()
    data_intacta = antes == depois
    print("-" * 78)
    print(f"data/ intacto (retrato de {len(antes)} arquivos, tamanho e mtime): {data_intacta}")
    if not data_intacta:
        alterados = sorted(set(antes) ^ set(depois)) or [
            chave for chave in antes if antes.get(chave) != depois.get(chave)
        ]
        print(f"  ATENCAO: mudou {alterados[:10]}")

    falhas = [titulo for titulo, ok, _, _ in resultados if not ok]
    total_ok = len(resultados) - len(falhas)
    print(f"RESULTADO: {total_ok}/6 PASSOU")
    for titulo in falhas:
        print(f"  FALHOU: {titulo}")
    print("=" * 78)
    return 0 if not falhas and data_intacta else 1


if __name__ == "__main__":
    raise SystemExit(main())
