"""Higiene de producao: segredo, `.env.example`, `--check-config` e modo real pela CLI.

Contrato: `docs/execucao/00b-contrato-fechamento.md` secoes 1 (pedido do cliente), 3.6
(ajuste do `app/run.py`) e 5 (criterios de aceite 2, 3, 4 e 6).

Tudo que invoca a CLI roda em `cwd` temporario, com `--env` explicito e caminhos
absolutos dentro de `tmp_path`: **nenhum teste deste arquivo escreve em `data/` do
projeto**. `git ls-files` e `git check-ignore` sao usados apenas como consulta (leitura),
como o contrato autoriza.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app import config as CFG
from conftest import MOCKS, RAIZ_PROJETO

# Total de itens do corpus sintetico (manifest = verdade de referencia). Derivado, para
# nao haver numero magico a cada caso novo do gerador (a foto da nota, caso B7, entrou
# como o 21o item).
TOTAL_DO_CORPUS = len(
    json.loads((RAIZ_PROJETO / "data" / "mocks" / "manifest.json").read_text(encoding="utf-8"))["itens"]
)

PYTHON_PROJETO = RAIZ_PROJETO / ".venv" / "Scripts" / "python.exe"
PYTHON = str(PYTHON_PROJETO if PYTHON_PROJETO.is_file() else Path(sys.executable))

TOKEN_TELEGRAM = "2222222222:TOKEN_FICTICIO_PRODUCAO_TG"
TOKEN_WHATSAPP = "EAAGTOKEN_FICTICIO_PRODUCAO_WA"
VERIFY_WHATSAPP = "VERIFY_FICTICIO_PRODUCAO_VT"


# --------------------------------------------------------------------- padroes de segredo

PADROES_SEGREDO = {
    "token_bot_telegram": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b"),
    "token_meta": re.compile(r"\bEAA[A-Za-z0-9]{20,}"),
    "chave_aws": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "chave_google": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "chave_privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "atribuicao_suspeita": re.compile(
        r"(?i)\b(token|secret|senha|password|passwd|api[_-]?key|apikey|access[_-]?key)\b"
        r"\s*[=:]\s*[\"']?([A-Za-z0-9_\-]{24,})[\"']?"
    ),
    "telefone_formatado": re.compile(r"\+?55[\s.\-]?\d{2}[\s.\-]?\d{4,5}[\s.\-]?\d{4}\b"),
}

# Numeros ficticios DECLARADOS pelo projeto (material sintetico de `tools/gerar_mocks.py`,
# numero de exibicao do WABA nos mocks e um placeholder de documento de arquitetura em que
# todos os digitos sao 9). A comparacao e feita sobre os DIGITOS do trecho encontrado:
# qualquer outro telefone com cara de real reprova a varredura.
TELEFONES_FICTICIOS = (
    re.compile(r"^551140028922$"),          # numero de exibicao do WABA sintetico
    re.compile(r"^5511999999999$"),         # placeholder de exemplo nos docs (tudo 9)
    re.compile(r"^5511998887\d{3}$"),       # sequencia gerada pelo gerador de mocks
)

# Credencial FICTICIA declarada: o valor encontrado E, ele mesmo, um exemplo -
# mascara (`***`, `xxxx`), marca de material sintetico (FICTICIO, EXEMPLO, FAKE, ...)
# ou caractere repetido. Sem este filtro o scanner reprova os proprios testes,
# evidencias e relatos, que citam exemplos DE PROPOSITO. Credencial de entropia real
# continua reprovando: o filtro olha o valor encontrado, nao o arquivo.
MARCAS_DE_PLACEHOLDER = (
    "FICTICIO", "FICTITIOUS", "FAKE", "EXEMPLO", "EXAMPLE", "PLACEHOLDER",
    "REDACTED", "REDIGIDO", "SAMPLE", "DUMMY", "MOCK", "TESTE", "TEST",
)


def credencial_placebo(valor: str) -> bool:
    """True quando o trecho encontrado e exemplo declarado, nao credencial real."""
    if not valor:
        return False
    if any(marca in valor.upper() for marca in MARCAS_DE_PLACEHOLDER):
        return True
    for separador in (":", "="):
        if separador in valor:
            segredo = valor.split(separador, 1)[1]
            if segredo and set(segredo) <= {"*"}:
                return True
            if segredo and set(segredo.upper()) <= {"X"}:
                return True
    return re.search(r"(.)\1{5,}", valor) is not None


ARQUIVOS_RAIZ_VARRIDOS = ("README.md", "AGENTS.md", ".env.example")
PASTAS_VARRIDAS = ("app/", "tools/", "tests/", "docs/")
NOMES_DE_SEGREDO = ("secrets", "credentials", "id_rsa", ".env")


# --------------------------------------------------------------------- utilidades


def git(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *argumentos],
        cwd=str(RAIZ_PROJETO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def versionados() -> list[str]:
    resultado = git("ls-files")
    assert resultado.returncode == 0, f"git ls-files falhou: {resultado.stderr}"
    return [linha.strip() for linha in resultado.stdout.splitlines() if linha.strip()]


def arquivos_varridos() -> list[str]:
    alvos = []
    for relativo in versionados():
        if relativo.startswith(PASTAS_VARRIDAS) or relativo in ARQUIVOS_RAIZ_VARRIDOS:
            alvos.append(relativo)
    exemplo = ".env.example"
    if Path(RAIZ_PROJETO, exemplo).is_file() and exemplo not in alvos:
        alvos.append(exemplo)  # presente no disco; o PO versiona nesta onda
    return alvos


def varrer_segredos(texto: str) -> list[tuple[str, str, int]]:
    """Devolve [(padrao, valor, linha)] de tudo que parece segredo de verdade."""
    achados: list[tuple[str, str, int]] = []
    for nome, padrao in PADROES_SEGREDO.items():
        for encontro in padrao.finditer(texto):
            valor = encontro.group(0)
            if nome == "telefone_formatado":
                digitos = re.sub(r"\D", "", valor)
                if any(filtro.match(digitos) for filtro in TELEFONES_FICTICIOS):
                    continue
                if re.search(r"(\d)\1{3,}", digitos):
                    continue
            elif credencial_placebo(valor):
                continue
            linha = texto[: encontro.start()].count("\n") + 1
            achados.append((nome, valor, linha))
    return achados


def env_temporario(tmp_path: Path, **campos) -> Path:
    """`.env` de teste com caminhos ABSOLUTOS em `tmp_path` (nada toca o repositorio)."""
    valores = {
        "MODO_EXECUCAO": "mock",
        "INBOX_DIR": str(tmp_path / "inbox"),
        "OUT_DIR": str(tmp_path / "out"),
        "DB_PATH": str(tmp_path / "out" / "pipeline.db"),
        "LOG_DIR": str(tmp_path / "logs"),
    }
    valores.update({k: v for k, v in campos.items() if v is not None})
    caminho = tmp_path / "env.producao"
    caminho.write_text("".join(f"{k}={v}\n" for k, v in valores.items()), encoding="utf-8")
    return caminho


def rodar_cli(argumentos, tmp_path: Path):
    return subprocess.run(
        [PYTHON, "-m", "app.run", *argumentos],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(RAIZ_PROJETO)},
        timeout=300,
    )


def copiar_mocks_para(tmp_path: Path) -> Path:
    destino = tmp_path / "inbox"
    shutil.copytree(MOCKS, destino)
    return destino


def retrato_data() -> dict:
    retrato = {}
    raiz_data = RAIZ_PROJETO / "data"
    for caminho in raiz_data.rglob("*"):
        if caminho.is_file():
            info = caminho.stat()
            retrato[caminho.relative_to(RAIZ_PROJETO).as_posix()] = (info.st_size, info.st_mtime_ns)
    return retrato


# --------------------------------------------------------------------- higiene do git


def test_env_real_nao_esta_versionado_e_esta_no_gitignore():
    rastreados = versionados()
    env_rastreado = [caminho for caminho in rastreados if Path(caminho).name == ".env"]
    assert not env_rastreado, f".env REAL versionado no repositorio: {env_rastreado}"

    ignorado = git("check-ignore", "-v", ".env")
    assert ignorado.returncode == 0, ".env nao esta no .gitignore"
    assert ".gitignore" in ignorado.stdout and ".env" in ignorado.stdout

    gitignore = (RAIZ_PROJETO / ".gitignore").read_text(encoding="utf-8")
    linhas = [linha.strip() for linha in gitignore.splitlines()]
    assert ".env" in linhas, "a linha '.env' tem de estar no .gitignore"


def test_nao_existe_env_na_raiz_do_projeto():
    """Item 2 do cliente: existindo `.env` no repositorio, o QA denuncia."""
    assert not (RAIZ_PROJETO / ".env").exists(), (
        "existe um .env na raiz do projeto: ele nao pode ser versionado e nao pode ficar "
        "no worktree da entrega (contrato secao 1, item 2)"
    )


def test_nenhum_arquivo_versionado_com_nome_de_segredo():
    suspeitos = []
    for caminho in versionados():
        nome = Path(caminho).name.lower()
        if nome == ".env" or nome.endswith(".pem") or nome.endswith(".key"):
            suspeitos.append(caminho)
            continue
        if any(nome.startswith(prefixo) for prefixo in ("secrets", "credentials", "id_rsa")):
            suspeitos.append(caminho)
    assert not suspeitos, f"arquivo com nome de segredo versionado: {suspeitos}"


def test_env_example_existe_nao_e_ignorado_e_o_git_enxerga():
    exemplo = RAIZ_PROJETO / ".env.example"
    assert exemplo.is_file(), ".env.example nao existe (criterio 4 do aceite)"

    ignorado = git("check-ignore", ".env.example")
    assert ignorado.returncode != 0, ".env.example esta sendo ignorado pelo git"

    # O criterio e "o git ve o arquivo": versionado OU pendente de commit. Consultar
    # so `status --porcelain` dava falso negativo quando o arquivo ja estava
    # versionado e limpo - que e o estado normal do repositorio.
    versionado = git("ls-files", "--error-unmatch", "--", ".env.example")
    pendente = git("status", "--porcelain", "--", ".env.example")
    assert versionado.returncode == 0 or pendente.stdout.strip(), (
        "o git nao ve o .env.example (nem versionado, nem pendente)"
    )
    assert exemplo.read_text(encoding="utf-8").strip(), ".env.example esta vazio"


# --------------------------------------------------------------------- varredura de segredo


def test_varredura_de_segredo_nos_arquivos_versionados():
    achados = []
    for relativo in arquivos_varridos():
        caminho = RAIZ_PROJETO / relativo
        if not caminho.is_file():
            continue
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        for nome_padrao, valor, linha in varrer_segredos(texto):
            achados.append(f"{relativo}:{linha} [{nome_padrao}] {valor[:60]!r}")
    assert not achados, "possivel segredo em arquivo versionado:\n" + "\n".join(achados)
    assert len(arquivos_varridos()) >= 50, "varredura com poucos arquivos: o filtro esta errado?"


def test_scanner_de_segredo_tem_controle_positivo():
    """Sem isto, uma varredura que nunca encontra nada passaria como verde.

    Os exemplos sao montados por concatenacao de proposito: se o literal aparece
    inteiro neste arquivo, a varredura acusa o proprio scanner.
    """
    exemplo_token = "TELEGRAM_BOT_TOKEN=" + "8431172940" + ":" + "AAFdq3xK9Lm2Pz7Rw5Tn8"
    chave_aws = "AKIA" + "J7QK" + "2LMN" + "4PQR" + "STUV"
    assert varrer_segredos(exemplo_token), "o scanner nao pegaria um token de bot de verdade"
    assert varrer_segredos(chave_aws), "o scanner nao pegaria uma chave AWS"
    assert varrer_segredos("-" * 5 + "BEGIN RSA PRIVATE KEY" + "-" * 5), (
        "o scanner nao pegaria chave privada"
    )
    telefone = varrer_segredos("contato +55 11 " + "97431" + "-" + "6028")
    assert achados_telefone(telefone), "o scanner nao pegaria um telefone brasileiro"


def achados_telefone(achados) -> list:
    return [item for item in achados if item[0] == "telefone_formatado"]


def test_env_example_nao_tem_valor_em_variavel_sensivel():
    texto = (RAIZ_PROJETO / ".env.example").read_text(encoding="utf-8")
    for var in CFG.VARIAVEIS:
        if not var.sensivel:
            continue
        assert re.search(rf"^{var.nome}=\s*$", texto, re.MULTILINE), (
            f"{var.nome} aparece com valor no .env.example"
        )
    assert not varrer_segredos(texto), "o .env.example tem algo com cara de segredo"


# --------------------------------------------------------------------- .env.example x catalogo


def test_env_example_bate_com_catalogo_e_com_o_gerador():
    exemplo = RAIZ_PROJETO / ".env.example"
    assert exemplo.is_file(), ".env.example ausente"
    texto = exemplo.read_text(encoding="utf-8")

    atribuicoes = [linha for linha in texto.splitlines() if "=" in linha and not linha.lstrip().startswith("#")]
    assert len(atribuicoes) == len(CFG.VARIAVEIS), (
        f".env.example com {len(atribuicoes)} variaveis e o catalogo com {len(CFG.VARIAVEIS)}"
    )
    for var in CFG.VARIAVEIS:
        assert any(linha.startswith(f"{var.nome}=") for linha in atribuicoes), (
            f"{var.nome} esta no catalogo e nao esta no .env.example"
        )

    assert texto == CFG.exemplo_env(), (
        "o .env.example do disco difere do texto gerado do catalogo (fonte unica, contrato D6)"
    )

    gerador = RAIZ_PROJETO / "tools" / "gerar_env_example.py"
    if gerador.is_file():
        conferencia = subprocess.run(
            [PYTHON, str(gerador), "--conferir"],
            cwd=str(RAIZ_PROJETO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        assert conferencia.returncode == 0, (
            f"tools/gerar_env_example.py --conferir reprovou:\n{conferencia.stdout}\n{conferencia.stderr}"
        )


# --------------------------------------------------------------------- CLI: --check-config


def test_check_config_com_env_ficticio_sai_0_e_mascara_os_segredos(tmp_path):
    caminho = env_temporario(
        tmp_path,
        MODO_EXECUCAO="real",
        CANAIS_ATIVOS="whatsapp,telegram",
        TELEGRAM_BOT_TOKEN=TOKEN_TELEGRAM,
        TELEGRAM_CHAT_ID="-1001234567890",
        WHATSAPP_TOKEN=TOKEN_WHATSAPP,
        WHATSAPP_PHONE_NUMBER_ID="1234567890",
        WHATSAPP_VERIFY_TOKEN=VERIFY_WHATSAPP,
        WHATSAPP_WEBHOOK_DIR=str(tmp_path / "webhook"),
    )
    resultado = rodar_cli(["--check-config", "--env", str(caminho)], tmp_path)

    assert resultado.returncode == 0, resultado.stderr
    saida = resultado.stdout + resultado.stderr
    assert "Modo de execucao : real" in resultado.stdout
    for segredo in (TOKEN_TELEGRAM, TOKEN_WHATSAPP, VERIFY_WHATSAPP):
        assert segredo not in saida, "segredo em texto puro na saida do --check-config"
        assert CFG.mascarar(segredo) in resultado.stdout, "o mascaramento nao apareceu no relatorio"
    assert f"bot{TOKEN_TELEGRAM}" not in saida
    assert "whatsapp, telegram" in resultado.stdout


def test_check_config_nao_roda_o_pipeline(tmp_path):
    caminho = env_temporario(tmp_path)
    resultado = rodar_cli(["--check-config", "--env", str(caminho)], tmp_path)
    assert resultado.returncode == 0, resultado.stderr
    assert "Rodada concluida" not in resultado.stdout
    assert not (tmp_path / "out").exists(), "o --check-config nao pode escrever saida de pipeline"


def test_check_config_com_env_inexistente_e_erro_claro(tmp_path):
    ausente = tmp_path / "nao_existe.env"
    resultado = rodar_cli(["--check-config", "--env", str(ausente)], tmp_path)
    assert resultado.returncode == 2
    assert "nao encontrado" in resultado.stderr
    assert "Traceback" not in resultado.stderr


# --------------------------------------------------------------------- CLI: modo mock (padrao)


def test_mock_e_o_padrao_sem_env_e_nao_exige_credencial_nenhuma(tmp_path):
    """Criterios 3 e 4 do cliente: mock e o padrao e nao pede segredo."""
    vazio = env_temporario(tmp_path)
    conferencia = rodar_cli(["--check-config", "--env", str(vazio)], tmp_path)
    assert conferencia.returncode == 0, conferencia.stderr
    assert "Modo de execucao : mock" in conferencia.stdout
    assert "Arquivo .env" in conferencia.stdout

    inbox = copiar_mocks_para(tmp_path)
    resultado = rodar_cli(
        [
            "--mock",
            "--env",
            str(vazio),
            "--inbox",
            str(inbox),
            "--out",
            str(tmp_path / "out"),
            "--db",
            str(tmp_path / "out" / "pipeline.db"),
        ],
        tmp_path,
    )
    assert resultado.returncode == 0, f"STDOUT:\n{resultado.stdout}\nSTDERR:\n{resultado.stderr}"
    assert "Modo     : mock" in resultado.stdout
    assert f"Artefatos ingeridos : {TOTAL_DO_CORPUS}" in resultado.stdout
    assert "Rodada concluida" in resultado.stdout
    for nome in ("controle_financeiro.xlsx", "controle_financeiro.csv", "auditoria.jsonl", "fila_excecoes.json"):
        assert (tmp_path / "out" / nome).is_file(), f"{nome} nao foi gerado na rodada mock"


def test_rodada_com_caminhos_temporarios_nao_toca_no_data_do_projeto(tmp_path):
    antes = retrato_data()
    inbox = copiar_mocks_para(tmp_path)
    caminho = env_temporario(tmp_path)
    resultado = rodar_cli(
        [
            "--mock",
            "--env",
            str(caminho),
            "--inbox",
            str(inbox),
            "--out",
            str(tmp_path / "out"),
            "--db",
            str(tmp_path / "out" / "pipeline.db"),
        ],
        tmp_path,
    )
    assert resultado.returncode == 0, resultado.stderr
    depois = retrato_data()
    alterados = sorted(
        chave for chave in set(antes) | set(depois) if antes.get(chave) != depois.get(chave)
    )
    assert not alterados, f"a rodada configurada escreveu no data/ do projeto: {alterados}"


def test_log_em_arquivo_e_append_no_log_dir(tmp_path):
    inbox = copiar_mocks_para(tmp_path)
    caminho = env_temporario(tmp_path)
    argumentos = [
        "--mock",
        "--env",
        str(caminho),
        "--inbox",
        str(inbox),
        "--out",
        str(tmp_path / "out"),
        "--db",
        str(tmp_path / "out" / "pipeline.db"),
    ]
    primeiro = rodar_cli(argumentos, tmp_path)
    assert primeiro.returncode == 0, primeiro.stderr
    logs = sorted((tmp_path / "logs").glob("pipeline-*.log"))
    assert len(logs) == 1, f"log de execucao nao gerado: {logs}"
    linhas_primeiro = len(logs[0].read_text(encoding="utf-8").splitlines())

    segundo = rodar_cli(argumentos, tmp_path)
    assert segundo.returncode == 0, segundo.stderr
    conteudo = logs[0].read_text(encoding="utf-8")
    linhas_segundo = len(conteudo.splitlines())

    assert linhas_segundo > linhas_primeiro, "o log em arquivo tem de ser append entre rodadas"
    assert "resumo da rodada" in conteudo
    assert "Rodada concluida em" in conteudo
    assert logs[0].name.endswith(".log")


def test_aviso_de_log_impossivel_nao_derruba_a_rodada(tmp_path):
    """Contrato 3.6: falha ao abrir o log avisa e a rodada segue."""
    from datetime import datetime

    bloqueio = tmp_path / "logs" / f"pipeline-{datetime.now():%Y%m%d}.log"
    bloqueio.mkdir(parents=True)  # diretorio no lugar do arquivo de log: abrir vai falhar
    caminho = env_temporario(tmp_path, LOG_DIR=str(tmp_path / "logs"))
    inbox = copiar_mocks_para(tmp_path)
    resultado = rodar_cli(
        [
            "--mock",
            "--env",
            str(caminho),
            "--inbox",
            str(inbox),
            "--out",
            str(tmp_path / "out"),
            "--db",
            str(tmp_path / "out" / "pipeline.db"),
        ],
        tmp_path,
    )
    assert resultado.returncode == 0, f"a rodada devia seguir sem log: {resultado.stderr}"
    assert "AVISO" in resultado.stderr
    assert "Rodada concluida" in resultado.stdout


# --------------------------------------------------------------------- CLI: modo real sem credencial


def test_real_sem_credencial_sai_nao_zero_citando_todas_as_variaveis(tmp_path):
    """Criterio 2 do aceite: mensagem clara por nome, sem traceback, sem rodar o pipeline."""
    caminho = env_temporario(
        tmp_path,
        MODO_EXECUCAO="real",
        CANAIS_ATIVOS="whatsapp,telegram",
        INBOX_DIR=str(tmp_path / "inbox_vazio"),
        OUT_DIR=str(tmp_path / "out"),
    )
    (tmp_path / "inbox_vazio").mkdir()
    resultado = rodar_cli(["--real", "--env", str(caminho)], tmp_path)

    assert resultado.returncode != 0, f"modo real incompleto devia falhar:\n{resultado.stdout}"
    assert resultado.returncode == 2
    assert "Traceback" not in resultado.stderr
    assert "Traceback" not in resultado.stdout
    for nome in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "WHATSAPP_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_VERIFY_TOKEN",
    ):
        assert f"falta {nome}" in resultado.stderr, f"a mensagem nao cita {nome}"
    assert "onde obter" in resultado.stderr
    assert not (tmp_path / "out").exists(), "configuracao incompleta nao pode rodar o pipeline"


def test_real_sem_credencial_nao_vaza_valor_ja_configurado(tmp_path):
    caminho = env_temporario(
        tmp_path,
        MODO_EXECUCAO="real",
        CANAIS_ATIVOS="whatsapp,telegram",
        TELEGRAM_BOT_TOKEN=TOKEN_TELEGRAM,
    )
    resultado = rodar_cli(["--real", "--env", str(caminho)], tmp_path)
    assert resultado.returncode == 2
    assert TOKEN_TELEGRAM not in (resultado.stdout + resultado.stderr), (
        "token configurado vazou na mensagem de configuracao incompleta"
    )
    assert "TELEGRAM_CHAT_ID" in resultado.stderr


def test_modo_real_com_um_canal_incompleto_nao_cobra_o_outro(tmp_path):
    caminho = env_temporario(
        tmp_path,
        MODO_EXECUCAO="real",
        CANAIS_ATIVOS="telegram",
        WHATSAPP_TOKEN=TOKEN_WHATSAPP,
    )
    resultado = rodar_cli(["--real", "--env", str(caminho)], tmp_path)
    assert resultado.returncode == 2
    assert "TELEGRAM_BOT_TOKEN" in resultado.stderr
    assert "WHATSAPP_TOKEN" not in resultado.stderr, "canal desligado nao pode ser cobrado"


# --------------------------------------------------------------------- resumo do comando unico


def test_resumo_do_comando_unico_mostra_modo_e_trilha(tmp_path):
    inbox = copiar_mocks_para(tmp_path)
    caminho = env_temporario(tmp_path)
    resultado = rodar_cli(
        [
            "--mock",
            "--env",
            str(caminho),
            "--inbox",
            str(inbox),
            "--out",
            str(tmp_path / "out"),
            "--db",
            str(tmp_path / "out" / "pipeline.db"),
        ],
        tmp_path,
    )
    assert resultado.returncode == 0, resultado.stderr
    for trecho in (
        "Pipeline de leitura de NF/pedidos - resumo da rodada",
        "Modo     : mock",
        "Arquivos gerados:",
        "Rodada concluida em",
    ):
        assert trecho in resultado.stdout, f"o resumo perdeu a linha {trecho!r}"

    resumo = json.loads((tmp_path / "out" / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["artefatos"] == TOTAL_DO_CORPUS
    assert (
        resumo["auto_aprovados"]
        + resumo["revisao"]
        + resumo["rejeitados"]
        + resumo["deduplicados"]
        == TOTAL_DO_CORPUS
    )
    assert not any("TOKEN" in str(valor) for valor in resumo.values() if isinstance(valor, str))
