"""Configuracao (`app/config.py`, F7): catalogo, leitura do `.env`, validacao e mascara.

Fonte de verdade: `docs/execucao/00b-contrato-fechamento.md` secoes 2 (decisoes D1-D6) e
3.1 (interface congelada + tabela de variaveis). O catalogo e a tabela do contrato estao
transcritos lado a lado aqui de proposito: se os dois se separarem, o teste acusa.

Nada aqui usa rede. Os arquivos `.env` sao criados em diretorio temporario; o `.env` da
raiz do projeto **nao** pode existir (ha teste proprio para isso em `test_producao.py`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import config as CFG
from conftest import RAIZ_PROJETO

# --------------------------------------------------------------------- contrato (tabela 3.1)

# nome -> (obrigatoria_em, sensivel, padrao)  -- literal do contrato, secao 3.1
CONTRATO: dict[str, tuple[tuple[str, ...], bool, str]] = {
    "MODO_EXECUCAO": (("sempre",), False, "mock"),
    "CANAIS_ATIVOS": (("real",), False, "whatsapp,telegram"),
    "INBOX_DIR": ((), False, ""),
    "OUT_DIR": ((), False, "data/out"),
    "DB_PATH": ((), False, ""),
    "LOG_DIR": ((), False, "logs"),
    "LOG_LEVEL": ((), False, "INFO"),
    "TELEGRAM_BOT_TOKEN": (("real:telegram",), True, ""),
    "TELEGRAM_CHAT_ID": (("real:telegram",), False, ""),
    "TELEGRAM_API_BASE": ((), False, "https://api.telegram.org"),
    "TELEGRAM_TIMEOUT_S": ((), False, "30"),
    "WHATSAPP_TOKEN": (("real:whatsapp",), True, ""),
    "WHATSAPP_PHONE_NUMBER_ID": (("real:whatsapp",), False, ""),
    "WHATSAPP_VERIFY_TOKEN": (("real:whatsapp",), True, ""),
    "WHATSAPP_API_BASE": ((), False, "https://graph.facebook.com/v21.0"),
    "WHATSAPP_WEBHOOK_DIR": ((), False, "data/inbox_webhook/whatsapp"),
}

VARIAVEIS_REAL_SEMPRE = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                         "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN")

PYTHON = str(Path(sys.executable))


# --------------------------------------------------------------------- utilidades


def escrever_env(destino: Path, conteudo: str) -> Path:
    destino.write_text(conteudo, encoding="utf-8")
    return destino


def env_basico(**extras) -> str:
    """`.env` de teste com valores ficticios (nunca sao segredo de verdade)."""
    valores = {
        "MODO_EXECUCAO": "real",
        "CANAIS_ATIVOS": "telegram",
        "TELEGRAM_BOT_TOKEN": "1111111111:TOKENFICTICIO_DE_TESTE_NAO_E_REAL",
        "TELEGRAM_CHAT_ID": "-1001234567890",
    }
    valores.update(extras)
    return "".join(f"{chave}={valor}\n" for chave, valor in valores.items() if valor is not None)


# --------------------------------------------------------------------- catalogo


def test_catalogo_tem_exatamente_as_variaveis_do_contrato():
    nomes = [var.nome for var in CFG.VARIAVEIS]
    assert len(nomes) == len(set(nomes)), f"variavel repetida no catalogo: {nomes}"
    assert set(nomes) == set(CONTRATO), (
        f"catalogo fora do contrato. so no codigo: {sorted(set(nomes) - set(CONTRATO))}; "
        f"so no contrato: {sorted(set(CONTRATO) - set(nomes))}"
    )
    assert nomes == [nome for nome in CONTRATO], "ordem do catalogo mudou (o .env.example segue esta ordem)"


@pytest.mark.parametrize("nome", sorted(CONTRATO))
def test_variavel_tem_descricao_e_onde_obter_uteis(nome):
    var = CFG.VARIAVEIS_POR_NOME[nome]
    assert var.descricao and var.descricao == var.descricao.strip()
    assert var.onde_obter and var.onde_obter == var.onde_obter.strip()
    assert len(var.descricao) >= 15, f"{nome}: descricao curta demais para ajudar o operador"
    assert len(var.onde_obter) >= 10, f"{nome}: 'onde obter' curto demais"
    proibido = ("TODO", "FIXME", "XXX", "??")
    assert not any(marca in var.descricao for marca in proibido), f"{nome}: descricao com pendencia"
    assert not any(marca in var.onde_obter for marca in proibido), f"{nome}: 'onde obter' com pendencia"


@pytest.mark.parametrize("nome", sorted(CONTRATO))
def test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato(nome):
    var = CFG.VARIAVEIS_POR_NOME[nome]
    obrigatoria_em, sensivel, padrao = CONTRATO[nome]
    assert var.obrigatoria_em == obrigatoria_em, f"{nome}: obrigatoria_em fora do contrato"
    assert var.sensivel is sensivel, f"{nome}: marca de sensivel fora do contrato"
    assert var.padrao == padrao, f"{nome}: padrao fora do contrato"
    for marca in var.obrigatoria_em:
        assert marca in CFG.OBRIGATORIEDADES, f"{nome}: obrigatoriedade desconhecida {marca!r}"


def test_variavel_sensivel_nunca_tem_padrao_nem_exemplo():
    for var in CFG.VARIAVEIS:
        if not var.sensivel:
            continue
        assert var.padrao == "", f"{var.nome} e sensivel e tem valor padrao no codigo"
        assert var.exemplo == "", f"{var.nome} e sensivel e tem exemplo preenchido no catalogo"


def test_sensiveis_do_catalogo_sao_exatamente_os_tres_segredos_do_contrato():
    sensiveis = {var.nome for var in CFG.VARIAVEIS if var.sensivel}
    assert sensiveis == {"TELEGRAM_BOT_TOKEN", "WHATSAPP_TOKEN", "WHATSAPP_VERIFY_TOKEN"}


# --------------------------------------------------------------------- leitura do .env


def test_env_aceita_comentario_linha_vazia_export_aspas_e_espacos(tmp_path):
    caminho = escrever_env(
        tmp_path / ".env",
        "\n".join(
            [
                "# comentario no topo",
                "",
                "MODO_EXECUCAO = real ",
                "  CANAIS_ATIVOS=telegram  ",
                "export TELEGRAM_BOT_TOKEN='1111111111:TOKEN_ENTRE_ASPAS_SIMPLES'",
                'export TELEGRAM_CHAT_ID = "-1001234567890"',
                "TELEGRAM_TIMEOUT_S=45",
                "   # comentario indentado",
                "LINHA SEM IGUAL (lixo de edicao)",
                "",
            ]
        )
        + "\n",
    )
    lidos = CFG.ler_env(caminho)
    assert lidos["MODO_EXECUCAO"] == "real"
    assert lidos["CANAIS_ATIVOS"] == "telegram"
    assert lidos["TELEGRAM_BOT_TOKEN"] == "1111111111:TOKEN_ENTRE_ASPAS_SIMPLES"
    assert lidos["TELEGRAM_CHAT_ID"] == "-1001234567890"
    assert lidos["TELEGRAM_TIMEOUT_S"] == "45"
    assert "LINHA SEM IGUAL (lixo de edicao)" not in lidos

    cfg = CFG.carregar(env_path=caminho, ambiente={})
    assert cfg.modo == CFG.MODO_REAL
    assert cfg.telegram.token == "1111111111:TOKEN_ENTRE_ASPAS_SIMPLES"
    assert cfg.telegram.timeout_s == 45.0


def test_env_com_bom_na_primeira_chave_e_lido(tmp_path):
    caminho = tmp_path / ".env"
    caminho.write_bytes(b"\xef\xbb\xbfMODO_EXECUCAO=real\nTELEGRAM_BOT_TOKEN=x\n")
    lidos = CFG.ler_env(caminho)
    assert lidos.get("MODO_EXECUCAO") == "real", "BOM no inicio do arquivo quebrou a primeira chave"


def test_ambiente_do_processo_vence_o_arquivo(tmp_path):
    caminho = escrever_env(
        tmp_path / ".env",
        "MODO_EXECUCAO=mock\nOUT_DIR=data/out\n"
        "CANAIS_ATIVOS=telegram\nTELEGRAM_BOT_TOKEN=1111111111:TOKENFICTICIO\n"
        "TELEGRAM_CHAT_ID=-1001234567890\n",
    )
    cfg = CFG.carregar(env_path=caminho, ambiente={"MODO_EXECUCAO": "real", "CANAL_EXTRA": "x"})
    assert cfg.modo == CFG.MODO_REAL, "o ambiente do processo tem de vencer o .env"
    assert cfg.canais == ("telegram",)
    assert "CANAL_EXTRA" not in {v.nome for v in CFG.VARIAVEIS}

    cfg_mock = CFG.carregar(env_path=caminho, ambiente={"MODO_EXECUCAO": "mock"})
    assert cfg_mock.modo == CFG.MODO_MOCK

    # e o padrao do catalogo so vale quando nem arquivo nem ambiente dizem nada
    so_padrao = escrever_env(tmp_path / "vazio.env", "# sem nada\n")
    assert CFG.carregar(env_path=so_padrao, ambiente={}).modo == CFG.MODO_MOCK


def test_env_arquivo_inexistente_e_erro_explicito(tmp_path):
    ausente = tmp_path / "nao_existe.env"
    with pytest.raises(CFG.ConfigError) as capturado:
        CFG.carregar(env_path=ausente, ambiente={})
    mensagem = str(capturado.value)
    assert "nao encontrado" in mensagem
    assert str(ausente) in mensagem
    assert "Traceback" not in mensagem


# --------------------------------------------------------------------- modo padrao e validacao


def test_sem_env_nenhum_o_modo_padrao_e_mock_e_isso_nao_e_erro(tmp_path):
    """Requisito 4 do cliente: mock e o PADRAO; ausencia de .env nao pode ser erro."""
    vazio = escrever_env(tmp_path / ".env", "# nada configurado aqui\n\n")
    cfg = CFG.carregar(env_path=vazio, ambiente={})
    assert cfg.modo == CFG.MODO_MOCK
    assert cfg.modo_real is False
    assert cfg.canais == ()
    assert cfg.telegram.token == ""
    assert cfg.whatsapp.token == ""
    assert cfg.inbox_dir == RAIZ_PROJETO / "data" / "mocks"
    assert cfg.log_level == "INFO"
    assert cfg.telegram.timeout_s == 30.0


def test_modo_real_com_credencial_do_canal_ativo_nao_acusa_falta(tmp_path):
    caminho = escrever_env(tmp_path / ".env", env_basico())
    cfg = CFG.carregar(env_path=caminho, ambiente={})
    assert cfg.modo_real is True
    assert cfg.canais == ("telegram",)
    assert cfg.telegram.token.startswith("1111111111:")


def test_modo_real_exige_so_as_variaveis_do_canal_ativo(tmp_path):
    caminho_vazio = escrever_env(
        tmp_path / "sem_credencial.env", "MODO_EXECUCAO=real\nCANAIS_ATIVOS=telegram\n"
    )
    with pytest.raises(CFG.ConfigError) as erro_telegram:
        CFG.carregar(env_path=caminho_vazio, ambiente={})
    assert erro_telegram.value.faltando == ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"], (
        "so as variaveis do canal ativo podem faltar"
    )
    assert "WHATSAPP" not in str(erro_telegram.value), "canal desligado nao pode ser cobrado"


def test_modo_real_com_os_dois_canais_exige_as_cinco_variaveis(tmp_path):
    caminho = escrever_env(tmp_path / ".env", "MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp,telegram\n")
    with pytest.raises(CFG.ConfigError) as capturado:
        CFG.carregar(env_path=caminho, ambiente={})
    assert capturado.value.faltando == list(VARIAVEIS_REAL_SEMPRE)


def test_chave_com_valor_vazio_conta_como_nao_configurada(tmp_path):
    """Contrato 3.1: `CHAVE=` e ausente, nao "valor vazio valido"."""
    caminho = escrever_env(
        tmp_path / ".env",
        "MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp\n"
        "WHATSAPP_TOKEN=\nWHATSAPP_PHONE_NUMBER_ID=   \nWHATSAPP_VERIFY_TOKEN=''\n",
    )
    with pytest.raises(CFG.ConfigError) as capturado:
        CFG.carregar(env_path=caminho, ambiente={})
    assert capturado.value.faltando == [
        "WHATSAPP_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_VERIFY_TOKEN",
    ]


@pytest.mark.parametrize(
    "linha, trecho_esperado",
    [
        ("MODO_EXECUCAO=producao\n", "MODO_EXECUCAO"),
        ("MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp,email\n", "email"),
        ("MODO_EXECUCAO=real\nCANAIS_ATIVOS=,\n", "CANAIS_ATIVOS"),
        ("LOG_LEVEL=VERBOSE\n", "LOG_LEVEL"),
    ],
)
def test_configuracao_invalida_aponta_o_campo_e_sai_com_mensagem_clara(tmp_path, linha, trecho_esperado):
    caminho = escrever_env(tmp_path / ".env", linha)
    with pytest.raises(CFG.ConfigError) as capturado:
        CFG.carregar(env_path=caminho, ambiente={})
    mensagem = str(capturado.value)
    assert trecho_esperado in mensagem
    assert "Traceback" not in mensagem


def test_timeout_invalido_e_recusado(tmp_path):
    for valor in ("abc", "0", "-5"):
        caminho = escrever_env(tmp_path / "t.env", env_basico(TELEGRAM_TIMEOUT_S=valor))
        with pytest.raises(CFG.ConfigError) as capturado:
            CFG.carregar(env_path=caminho, ambiente={})
        assert "TELEGRAM_TIMEOUT_S" in str(capturado.value)


def test_caminhos_padrao_do_modo_real_e_do_mock(tmp_path):
    real = escrever_env(tmp_path / "real.env", env_basico())
    cfg_real = CFG.carregar(env_path=real, ambiente={})
    assert cfg_real.inbox_dir == RAIZ_PROJETO / "data" / "inbox"
    assert cfg_real.out_dir == RAIZ_PROJETO / "data" / "out"
    assert cfg_real.db_path == cfg_real.out_dir / "pipeline.db"
    assert cfg_real.log_dir == RAIZ_PROJETO / "logs"
    assert cfg_real.canais == ("telegram",)

    db_custom = escrever_env(
        tmp_path / "db.env", env_basico(OUT_DIR="data/saida_x", DB_PATH="data/db_x.sqlite")
    )
    cfg_db = CFG.carregar(env_path=db_custom, ambiente={})
    assert cfg_db.db_path == RAIZ_PROJETO / "data" / "db_x.sqlite"
    assert cfg_db.out_dir == RAIZ_PROJETO / "data" / "saida_x"


def test_caminho_absoluto_no_env_nao_e_rebaseado(tmp_path):
    alvo = tmp_path / "saida_absoluta"
    caminho = escrever_env(tmp_path / "abs.env", f"MODO_EXECUCAO=mock\nOUT_DIR={alvo}\n")
    cfg = CFG.carregar(env_path=caminho, ambiente={})
    assert cfg.out_dir == alvo
    assert cfg.db_path == alvo / "pipeline.db"


# --------------------------------------------------------------------- ConfigError


def test_erro_cita_cada_variavel_faltante_pelo_nome(tmp_path):
    caminho = escrever_env(tmp_path / ".env", "MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp,telegram\n")
    with pytest.raises(CFG.ConfigError) as capturado:
        CFG.carregar(env_path=caminho, ambiente={})
    mensagem = str(capturado.value)
    for nome in VARIAVEIS_REAL_SEMPRE:
        assert f"falta {nome}" in mensagem, f"a mensagem nao cita {nome} pelo nome"
    assert "onde obter" in mensagem
    assert "--check-config" in mensagem and "--mock" in mensagem
    assert "Traceback" not in mensagem


def test_mensagem_de_erro_nunca_vaza_valor_de_variavel_configurada(tmp_path):
    """D5: erro cita o NOME do que falta; o valor do que esta configurado nao aparece."""
    token_telegram = "9999999999:SEGREDO_QUE_NAO_PODE_APARECER_NO_ERRO"
    token_whatsapp = "EAAGSEGREDO_WHATSAPP_NAO_PODE_APARECER"
    caminho = escrever_env(
        tmp_path / ".env",
        "MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp,telegram\n"
        f"TELEGRAM_BOT_TOKEN={token_telegram}\n"
        f"WHATSAPP_TOKEN={token_whatsapp}\n",
    )
    with pytest.raises(CFG.ConfigError) as capturado:
        CFG.carregar(env_path=caminho, ambiente={})
    mensagem = str(capturado.value)
    assert token_telegram not in mensagem, "segredo do Telegram vazou na mensagem de erro"
    assert token_whatsapp not in mensagem, "segredo do WhatsApp vazou na mensagem de erro"
    assert capturado.value.faltando == ["TELEGRAM_CHAT_ID", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN"]
    assert len(capturado.value.mensagens) == len(str(capturado.value).split("\n"))


# --------------------------------------------------------------------- mascarar


def test_mascarar_valor_longo_mostra_so_os_ultimos_quatro():
    token = "1111111111:AAF_abcdefghijklmnopqrstuvwxyz1234"
    mascarado = CFG.mascarar(token)
    assert mascarado == CFG.MASCARA + token[-4:]
    assert mascarado != token
    assert token[:-4] not in mascarado
    assert mascarado.endswith(token[-4:])
    assert mascarado.count(token[-4:]) == 1


@pytest.mark.parametrize("valor", ["", None])
def test_mascarar_vazio_devolve_vazio(valor):
    assert CFG.mascarar(valor) == ""


@pytest.mark.parametrize("valor", ["a", "abc", "1234567"])
def test_mascarar_valor_curto_nao_revela_nada(valor):
    assert CFG.mascarar(valor) == CFG.MASCARA


@pytest.mark.parametrize(
    "valor",
    ["segredo", "senha12345678", "EAAG" + "x" * 40, "1111111111:" + "y" * 35],
)
def test_mascarar_nunca_devolve_o_valor_completo(valor):
    assert CFG.mascarar(valor) != valor


def test_relatorio_de_configuracao_mostra_segredo_apenas_mascarado(tmp_path):
    token = "1111111111:TOKEN_DO_RELATORIO_NAO_PODE_APARECER_INTEIRO"
    verify = "VERIFY_TOKEN_DO_RELATORIO_NAO_PODE_APARECER"
    caminho = escrever_env(
        tmp_path / ".env",
        "MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp,telegram\n"
        f"TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID=-1001234567890\n"
        f"WHATSAPP_TOKEN={token}\nWHATSAPP_PHONE_NUMBER_ID=123456789\n"
        f"WHATSAPP_VERIFY_TOKEN={verify}\n",
    )
    cfg = CFG.carregar(env_path=caminho, ambiente={})
    relatorio = CFG.imprimir_configuracao(cfg)

    assert token not in relatorio, "token inteiro apareceu no relatorio de configuracao"
    assert verify not in relatorio, "verify token inteiro apareceu no relatorio"
    assert CFG.mascarar(token) in relatorio
    assert CFG.mascarar(verify) in relatorio
    assert "Modo de execucao : real" in relatorio
    assert "whatsapp, telegram" in relatorio


# --------------------------------------------------------------------- .env.example


def test_exemplo_env_cita_todas_as_variaveis_do_catalogo():
    texto = CFG.exemplo_env()
    assert texto.endswith("\n")
    atribuicoes = [linha for linha in texto.splitlines() if "=" in linha and not linha.startswith("#")]
    assert len(atribuicoes) == len(CFG.VARIAVEIS)
    for var in CFG.VARIAVEIS:
        assert any(linha.startswith(f"{var.nome}=") for linha in atribuicoes), (
            f"{var.nome} nao aparece no .env.example gerado"
        )
        assert f"# {var.nome}" in texto, f"{var.nome} sem o bloco de comentario explicando"
    for linha in texto.splitlines():
        if linha.startswith("#") or not linha.strip():
            continue
        nome = linha.split("=", 1)[0]
        assert nome in CFG.VARIAVEIS_POR_NOME, f"linha do exemplo com variavel fora do catalogo: {nome}"


def test_exemplo_env_nao_traz_valor_nas_variaveis_sensiveis():
    texto = CFG.exemplo_env()
    for var in CFG.VARIAVEIS:
        if not var.sensivel:
            continue
        assert f"{var.nome}=\n" in texto, f"{var.nome} aparece com valor no exemplo"
        bloco = texto.split(f"# {var.nome}")[1].splitlines()[0]
        assert "SEGREDO" in bloco, f"{var.nome} sem o aviso de segredo no exemplo"


def test_exemplo_env_usa_os_placeholders_do_catalogo():
    texto = CFG.exemplo_env()
    for var in CFG.VARIAVEIS:
        if var.sensivel:
            continue
        assert f"{var.nome}={var.exemplo}\n" in texto, (
            f"{var.nome}: o exemplo do catalogo e {var.exemplo!r} e nao chegou ao texto"
        )


# --------------------------------------------------------------------- flags de CLI


def _python_do_projeto() -> str:
    candidato = RAIZ_PROJETO / ".venv" / "Scripts" / "python.exe"
    return str(candidato) if candidato.is_file() else PYTHON


def test_flag_mock_da_cli_sobrepoe_env_em_modo_real(tmp_path):
    """D1: `--mock`/`--real` vencem o arquivo; provado pelo `--check-config` de verdade."""
    caminho = escrever_env(
        tmp_path / ".env",
        env_basico(OUT_DIR=str(tmp_path / "out"), LOG_DIR=str(tmp_path / "logs")),
    )
    resultado = subprocess.run(
        [_python_do_projeto(), "-m", "app.run", "--mock", "--check-config", "--env", str(caminho)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(RAIZ_PROJETO)},
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Modo de execucao : mock" in resultado.stdout, resultado.stdout
    assert "Modo de execucao : real" not in resultado.stdout


def test_flag_real_da_cli_sobrepoe_env_em_modo_mock(tmp_path):
    caminho = escrever_env(
        tmp_path / ".env",
        "MODO_EXECUCAO=mock\nCANAIS_ATIVOS=telegram\n"
        "TELEGRAM_BOT_TOKEN=1111111111:TOKENFICTICIO\nTELEGRAM_CHAT_ID=-1001234567890\n",
    )
    resultado = subprocess.run(
        [_python_do_projeto(), "-m", "app.run", "--real", "--check-config", "--env", str(caminho)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(RAIZ_PROJETO)},
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Modo de execucao : real" in resultado.stdout


def test_check_config_sai_2_e_cita_as_variaveis_quando_a_configuracao_esta_incompleta(tmp_path):
    caminho = escrever_env(tmp_path / ".env", "MODO_EXECUCAO=real\nCANAIS_ATIVOS=telegram\n")
    resultado = subprocess.run(
        [_python_do_projeto(), "-m", "app.run", "--check-config", "--env", str(caminho)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(RAIZ_PROJETO)},
        timeout=120,
    )
    assert resultado.returncode == 2
    assert "TELEGRAM_BOT_TOKEN" in resultado.stderr
    assert "TELEGRAM_CHAT_ID" in resultado.stderr
    assert "Traceback" not in resultado.stderr
