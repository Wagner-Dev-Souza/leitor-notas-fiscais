"""Idempotencia: o que o cliente vai testar (contrato secao 6).

Cobre: mesmo binario reenviado, mesmo conteudo em arquivo diferente, mensagem reentregue,
rodada dupla do pipeline com contagem estavel da planilha e a duplicata B4.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import persistencia as PE
from conftest import ler_auditoria, linhas_planilha, rodar_pipeline

CONSULTA_DOCUMENTOS_POR_SHA = "SELECT COUNT(*) AS n FROM documentos WHERE sha256_conteudo = ?"


@pytest.fixture
def conexao(tmp_path):
    conn = PE.abrir_db(str(tmp_path / "idempotencia.db"))
    yield conn
    conn.close()


def _artefato(artefatos_ingeridos, nome: str):
    return next(a for a in artefatos_ingeridos if Path(a.caminho).name == nome)


def test_registrar_mesmo_documento_duas_vezes_devolve_dedupe_e_nao_cria_segunda_linha(
    conexao, artefatos_ingeridos
):
    artefato = _artefato(artefatos_ingeridos, "FORN-ALFA_nf_1001.pdf")

    documento_id, dedupe = PE.registrar_documento(conexao, artefato)
    assert dedupe is False

    repetido_id, dedupe_repetido = PE.registrar_documento(conexao, artefato)
    assert dedupe_repetido is True, "o mesmo binario reenviado tem de ser deduplicado"
    assert repetido_id == documento_id

    total = conexao.execute(
        CONSULTA_DOCUMENTOS_POR_SHA, (artefato.hash_conteudo,)
    ).fetchone()["n"]
    assert total == 1, "a segunda passada criou uma linha nova em documentos"


def test_mesmo_conteudo_mas_objeto_novo_continua_deduplicado(conexao, artefatos_ingeridos):
    """Segunda barreira (contrato 6.1): reingestao do mesmo arquivo em outra passada."""
    from app import ingress

    primeiro = PE.registrar_documento(conexao, _artefato(artefatos_ingeridos, "FORN-BETA_nf_2001.pdf"))
    artefatos_novos = ingress.ingerir(
        Path(artefatos_ingeridos[0].caminho).parent.parent
    )
    segundo_artefato = _artefato(artefatos_novos, "FORN-BETA_nf_2001.pdf")

    documento_id, dedupe = PE.registrar_documento(conexao, segundo_artefato)
    assert dedupe is True
    assert documento_id == primeiro[0]


def test_duplicata_b4_e_deduplicada_e_nao_cria_linha_nova(conexao, artefatos_ingeridos, por_arquivo):
    """B4: copia identica na inbox -> deduplicada, sem documento novo."""
    original = _artefato(artefatos_ingeridos, "FORN-ALFA_nf_1001.pdf")
    copia = _artefato(artefatos_ingeridos, "FORN-ALFA_nf_1001_copia.pdf")

    assert copia.hash_conteudo == original.hash_conteudo, "o B4 deixou de ser copia identica"
    assert copia.hash_conteudo == por_arquivo["pdf/FORN-ALFA_nf_1001.pdf"]["sha256"]

    id_original, _ = PE.registrar_documento(conexao, original)
    id_copia, dedupe = PE.registrar_documento(conexao, copia)

    assert dedupe is True
    assert id_copia == id_original
    total = conexao.execute(
        CONSULTA_DOCUMENTOS_POR_SHA, (original.hash_conteudo,)
    ).fetchone()["n"]
    assert total == 1


def test_mensagem_reentregue_nao_cria_segundo_registro(conexao, artefatos_ingeridos):
    """Contrato 6.4: UNIQUE em (provedor, id_externo)."""
    mensagem = _artefato(artefatos_ingeridos, "whatsapp_1.jsonl")
    primeiro_id, dedupe = PE.registrar_documento(conexao, mensagem)
    assert dedupe is False

    segundo_id, dedupe_repetido = PE.registrar_documento(conexao, mensagem)
    assert dedupe_repetido is True
    assert segundo_id == primeiro_id

    total = conexao.execute(
        "SELECT COUNT(*) AS n FROM mensagens WHERE provedor = ? AND id_externo = ?",
        (mensagem.mensagem.canal, mensagem.mensagem.id_externo),
    ).fetchone()["n"]
    assert total == 1


def test_pipeline_duas_rodadas_mantem_contagem_da_planilha(inbox_tmp, out_tmp):
    """Contrato 6.5 e item 3 do aceite: rodar 2x -> contagem de linhas identica."""
    primeira = rodar_pipeline(inbox_tmp, out_tmp)
    xlsx = out_tmp / "controle_financeiro.xlsx"
    linhas_primeira = linhas_planilha(xlsx)

    segunda = rodar_pipeline(inbox_tmp, out_tmp)
    linhas_segunda = linhas_planilha(xlsx)

    assert primeira["linhas_planilha"] == segunda["linhas_planilha"]
    assert len(linhas_primeira) == len(linhas_segunda) == primeira["linhas_planilha"]
    assert primeira["linhas_planilha"] > 0, "nenhuma linha aprovada: a assercao seria vazia"


def test_pipeline_segunda_rodada_nao_gera_linha_duplicada_nem_novo_pedido(inbox_tmp, out_tmp):
    primeira = rodar_pipeline(inbox_tmp, out_tmp)
    segunda = rodar_pipeline(inbox_tmp, out_tmp)

    assert segunda["deduplicados"] == segunda["artefatos"], (
        "na segunda rodada todo artefato tinha de cair na deduplicacao"
    )
    assert segunda["auto_aprovados"] == 0
    assert segunda["revisao"] == 0
    assert segunda["rejeitados"] == 0

    linhas = linhas_planilha(out_tmp / "controle_financeiro.xlsx")
    pedidos = [linha["pedido_id"] for linha in linhas]
    assert len(pedidos) == len(set(pedidos)), "pedido repetido no ledger"
    assert len(pedidos) == primeira["linhas_planilha"]


def test_ledger_tem_uma_linha_por_pedido_validado_e_csv_casa_com_xlsx(inbox_tmp, out_tmp):
    resumo = rodar_pipeline(inbox_tmp, out_tmp)
    linhas = linhas_planilha(out_tmp / "controle_financeiro.xlsx")
    csv_bruto = (out_tmp / "controle_financeiro.csv").read_text(encoding="utf-8").splitlines()

    assert len(linhas) == resumo["auto_aprovados"] == resumo["linhas_planilha"]
    assert len(csv_bruto) == len(linhas) + 1, "CSV e XLSX com contagens diferentes"
    assert all(linha["status_validacao"] in ("auto_aprovado", "validado") for linha in linhas)


def test_documento_e_pedido_ficam_ligados_na_trilha_de_auditoria(inbox_tmp, out_tmp):
    """Contrato 4.6: uma linha de auditoria por artefato, com documento_id e pedido_id."""
    resumo = rodar_pipeline(inbox_tmp, out_tmp)
    registros = ler_auditoria(out_tmp / "auditoria.jsonl")

    assert len(registros) == resumo["artefatos"]
    for registro in registros:
        assert registro["documento_id"], "artefato processado sem documento_id"
        assert registro["hash_conteudo"]
        assert registro["acao"] in ("inserido", "atualizado", "deduplicado", "revisao", "rejeitado")
        if registro["acao"] != "deduplicado":
            assert registro["pedido_id"], "artefato gravado sem pedido_id"

    deduplicados = [r for r in registros if r["acao"] == "deduplicado"]
    assert len(deduplicados) >= 1, "o caso B4 (copia identica) nao apareceu como deduplicado"
    assert any("FORN-ALFA_nf_1001_copia.pdf" in str(r["artefato"]) for r in deduplicados)
