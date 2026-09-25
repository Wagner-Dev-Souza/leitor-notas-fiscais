"""Aprovacao humana NA PLANILHA: a saida que faltava para a fila de excecoes.

Requisito do cliente: "a parte de aprovacao humana e feita na planilha... e depois disso deve
seguir pra resolvido automaticamente pra sair da fila".

O que se prova aqui, em ciclo completo com a rodada mock de verdade:

1. a rodada gera a aba `Revisao` na planilha, com a leitura proposta e as colunas de decisao;
2. a decisao digitada na aba (`APROVAR`/`REJEITAR`, com correcao opcional) e lida na rodada
   seguinte;
3. aprovado -> linha na aba oficial `controle_financeiro` + pendencia `resolvida`;
4. rejeitado -> nenhuma linha, pendencia `resolvida` com a decisao registrada;
5. aprovacao sem valor total nao vira linha: o valor errado e o pior modo de falha do projeto.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

from conftest import MOCKS, RAIZ_PROJETO

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import aprovacao  # noqa: E402

PYTHON = str(RAIZ / ".venv" / "Scripts" / "python.exe")


def rodar_mock(out: Path) -> subprocess.CompletedProcess:
    """Rodada mock de verdade (o mesmo comando unico da entrega) numa saida isolada."""
    return subprocess.run(
        [
            PYTHON,
            "-m",
            "app.run",
            "--mock",
            "--inbox",
            str(MOCKS),
            "--out",
            str(out),
            "--db",
            str(out / "pipeline.db"),
        ],
        cwd=str(RAIZ_PROJETO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(RAIZ_PROJETO)},
        timeout=300,
    )


def ler_aba(caminho: Path, aba: str) -> list[dict]:
    ws = load_workbook(caminho)[aba]
    cabecalho = [celula.value for celula in ws[1]]
    return [
        dict(zip(cabecalho, [celula.value for celula in linha]))
        for linha in ws.iter_rows(min_row=3)
    ]


def decidir_linha(caminho: Path, pedido_id: str | None, decisao: str, **campos) -> dict:
    """Marca a decisao numa linha da aba `Revisao`, como o humano faria."""
    wb = load_workbook(caminho)
    ws = wb[aprovacao.ABA_REVISAO]
    cabecalho = [celula.value for celula in ws[1]]
    alvo = None
    for linha in ws.iter_rows(min_row=3):
        if pedido_id is None or linha[cabecalho.index("pedido_id")].value == pedido_id:
            alvo = linha
            break
    assert alvo is not None, f"linha do pedido {pedido_id} nao esta na aba Revisao"
    alvo[cabecalho.index("DECISAO")].value = decisao
    for nome, valor in campos.items():
        alvo[cabecalho.index(nome)].value = valor
    wb.save(caminho)
    return {
        "pedido_id": alvo[cabecalho.index("pedido_id")].value,
        "valor_lido": alvo[cabecalho.index("valor_lido")].value,
        "arquivo": alvo[cabecalho.index("arquivo_origem")].value,
    }


@pytest.fixture()
def rodada(tmp_path):
    """Uma rodada mock completa numa saida limpa (planilha + fila + banco)."""
    out = tmp_path / "out"
    out.mkdir()
    resultado = rodar_mock(out)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    return out


# ------------------------------------------------------------------ rotulos aceitos


def test_rotulo_de_decisao_aceita_o_que_o_humano_digita():
    for bruto in ("APROVAR", "aprovar", "Aprovado", "ok", "SIM", "s", "X"):
        assert aprovacao.rotulo_decisao(bruto) == aprovacao.DECISAO_APROVAR, bruto
    for bruto in ("REJEITAR", "rejeitado", "nao", "NÃO", "N"):
        assert aprovacao.rotulo_decisao(bruto) == aprovacao.DECISAO_REJEITAR, bruto


def test_sem_decisao_o_sistema_nao_adivinha():
    for bruto in (None, "", "   ", "talvez", "conferir", 42):
        assert aprovacao.rotulo_decisao(bruto) is None, bruto


# ------------------------------------------------------------------ a aba de revisao


def test_rodada_gera_a_aba_de_revisao_com_a_leitura_e_as_colunas_de_decisao(rodada):
    caminho = rodada / "controle_financeiro.xlsx"
    wb = load_workbook(caminho)

    assert wb.sheetnames == [aprovacao.ABA_OFICIAL, aprovacao.ABA_REVISAO]
    assert wb.active.title == aprovacao.ABA_OFICIAL, (
        "a aba ativa tem de continuar sendo a oficial: o ledger escreve na ativa"
    )

    fila = json.loads((rodada / "fila_excecoes.json").read_text(encoding="utf-8"))
    linhas = ler_aba(caminho, aprovacao.ABA_REVISAO)
    assert len(linhas) == fila["total"], "uma linha de revisao por pendencia aberta"

    cabecalho = set(linhas[0])
    assert set(aprovacao.COLUNAS_DECISAO) <= cabecalho, "faltam as colunas de decisao"
    assert {"valor_lido", "numero_pedido", "emitente_cnpj", "motivo_codigo", "dica"} <= cabecalho

    for linha in linhas:
        assert linha["pendencia_id"], "sem o id da pendencia a decisao nao volta para a fila"
        assert linha["pedido_id"]
        assert linha["DECISAO"] is None, "a rodada nao pode decidir pelo humano"


def test_planilha_oficial_mantem_as_20_colunas_de_contrato(rodada):
    from app import contratos

    ws = load_workbook(rodada / "controle_financeiro.xlsx")[aprovacao.ABA_OFICIAL]
    assert [celula.value for celula in ws[1]] == list(contratos.COLUNAS_PLANILHA)


# ------------------------------------------------------------------ ciclo completo


def test_aprovar_leva_a_linha_para_a_planilha_e_fecha_a_pendencia(rodada):
    caminho = rodada / "controle_financeiro.xlsx"
    antes = len(ler_aba(caminho, aprovacao.ABA_OFICIAL))
    alvo = decidir_linha(caminho, None, "APROVAR", VALOR_TOTAL_CORRIGIDO="1.234,56", REVISOR="Wagner")

    resultado = rodar_mock(rodada)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    linhas = ler_aba(caminho, aprovacao.ABA_OFICIAL)
    aprovada = [linha for linha in linhas if linha["pedido_id"] == alvo["pedido_id"]]
    assert len(linhas) == antes + 1, "a aprovacao tem de virar UMA linha nova no livro-caixa"
    assert len(aprovada) == 1, "a linha aprovada nao apareceu na aba oficial"
    assert aprovada[0]["valor_total_centavos"] == 123456, "o valor corrigido a mao nao foi usado"
    assert aprovada[0]["status_validacao"] == "validado"
    assert aprovada[0]["valor_total"] == "1234,56"

    resumo = json.loads((rodada / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["aprovacao_planilha"]["lidas"] == 1
    assert resumo["aprovacao_planilha"]["aprovadas"] == 1
    assert resumo["aprovacao_planilha"]["pendencias_fechadas"] == 1
    assert "Aprovacao na planilha (aba Revisao)" in resultado.stdout

    conn = sqlite3.connect(rodada / "pipeline.db")
    conn.row_factory = sqlite3.Row
    pendencia = conn.execute(
        "SELECT * FROM fila_excecoes WHERE pedido_id = ?", (alvo["pedido_id"],)
    ).fetchall()
    assert pendencia, "a pendencia sumiu do banco em vez de ser fechada"
    for linha in pendencia:
        assert linha["status"] == "resolvida"
        assert linha["resolvida_por"] == "Wagner"
        assert linha["decisao"] == "aprovado"
        assert linha["resolvida_em"]
    conn.close()

    restantes = [linha for linha in ler_aba(caminho, aprovacao.ABA_REVISAO)
                 if linha["pedido_id"] == alvo["pedido_id"]]
    assert restantes == [], "pendencia resolvida nao pode continuar na aba de revisao"


def test_rejeitar_fecha_a_pendencia_sem_linha_na_planilha(rodada):
    caminho = rodada / "controle_financeiro.xlsx"
    antes = len(ler_aba(caminho, aprovacao.ABA_OFICIAL))
    alvo = decidir_linha(caminho, None, "REJEITAR", REVISOR="Wagner", OBSERVACAO="nota do fornecedor errado")

    assert rodar_mock(rodada).returncode == 0

    linhas = ler_aba(caminho, aprovacao.ABA_OFICIAL)
    assert len(linhas) == antes, "documento rejeitado nao pode virar linha"
    assert not [linha for linha in linhas if linha["pedido_id"] == alvo["pedido_id"]]

    conn = sqlite3.connect(rodada / "pipeline.db")
    conn.row_factory = sqlite3.Row
    linha = conn.execute("SELECT * FROM fila_excecoes WHERE pedido_id = ?", (alvo["pedido_id"],)).fetchone()
    assert linha["status"] == "resolvida"
    assert linha["decisao"] == "rejeitado"
    pedido = conn.execute("SELECT status FROM pedidos WHERE id = ?", (alvo["pedido_id"],)).fetchone()
    assert pedido["status"] == "rejeitado"
    conn.close()


def test_aprovacao_sem_valor_nao_vira_linha_e_a_pendencia_continua_aberta(rodada):
    """Nenhum valor (nem lido, nem digitado): aprovar nao pode inventar numero."""
    caminho = rodada / "controle_financeiro.xlsx"
    ws = load_workbook(caminho)[aprovacao.ABA_REVISAO]
    cabecalho = [celula.value for celula in ws[1]]
    alvo = None
    for linha in ws.iter_rows(min_row=3):
        if not linha[cabecalho.index("valor_lido")].value:
            alvo = linha
            break
    assert alvo is not None, "o corpus mock tem de ter pendencia sem valor lido"
    alvo[cabecalho.index("DECISAO")].value = "APROVAR"
    pedido_id = alvo[cabecalho.index("pedido_id")].value
    ws.parent.save(caminho)

    antes = len(ler_aba(caminho, aprovacao.ABA_OFICIAL))
    resultado = rodar_mock(rodada)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    linhas = ler_aba(caminho, aprovacao.ABA_OFICIAL)
    assert len(linhas) == antes, "aprovacao sem valor nao pode entrar no livro-caixa"
    assert not [linha for linha in linhas if linha["pedido_id"] == pedido_id]

    resumo = json.loads((rodada / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["aprovacao_planilha"]["aprovadas"] == 0
    assert any("sem valor total" in aviso for aviso in resumo["avisos"]), resumo["avisos"]

    conn = sqlite3.connect(rodada / "pipeline.db")
    pendencia = conn.execute(
        "SELECT status FROM fila_excecoes WHERE pedido_id = ?", (pedido_id,)
    ).fetchone()
    assert pendencia[0] == "aberta", "sem aprovacao valida a pendencia tem de continuar na fila"
    conn.close()


def test_aprovar_duas_vezes_nao_duplica_linha_nem_pendencia(rodada):
    caminho = rodada / "controle_financeiro.xlsx"
    decidir_linha(caminho, None, "APROVAR", REVISOR="Wagner")
    assert rodar_mock(rodada).returncode == 0
    depois_da_primeira = len(ler_aba(caminho, aprovacao.ABA_OFICIAL))

    # A decisao continua escrita na planilha (o humano nao apagou a linha); a rodada seguinte
    # nao pode aplicar de novo: o pedido ja esta `validado`.
    assert rodar_mock(rodada).returncode == 0
    assert len(ler_aba(caminho, aprovacao.ABA_OFICIAL)) == depois_da_primeira


def test_decisao_de_pedido_que_nao_existe_vira_aviso_sem_quebrar_a_rodada(rodada):
    caminho = rodada / "controle_financeiro.xlsx"
    wb = load_workbook(caminho)
    ws = wb[aprovacao.ABA_REVISAO]
    cabecalho = [celula.value for celula in ws[1]]
    linha = ws[3]
    linha[cabecalho.index("pedido_id")].value = "ped_inventado"
    linha[cabecalho.index("DECISAO")].value = "APROVAR"
    linha[cabecalho.index("REVISOR")].value = "Wagner"
    wb.save(caminho)

    resultado = rodar_mock(rodada)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    resumo = json.loads((rodada / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["aprovacao_planilha"]["ignoradas"] == 1
    assert any("nao existe no banco" in aviso for aviso in resumo["avisos"])
