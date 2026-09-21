"""Ponta a ponta pelo comando unico congelado (contrato secao 2 e secao 9).

`test_comando_unico_mock_gera_os_quatro_artefatos` executa exatamente

    .venv/Scripts/python.exe -m app.run --mock

em um processo separado, com o cwd na raiz do projeto, e confere a existencia **e o
conteudo** de `data/out/controle_financeiro.xlsx`, `.csv`, `auditoria.jsonl` e
`fila_excecoes.json`. Esse e o critério 1/4 da definicao de pronto da fase; o pipeline
regenera a propria saida, nenhum arquivo de outro dono e editado.

Os outros dois testes rodam o mesmo comando apontando `--inbox/--out/--db` para
diretorios temporarios, para conferir o conteudo publicado sem depender do historico
de rodadas do repositorio.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.contratos import COLUNAS_PLANILHA
from conftest import MOCKS, OUT_PADRAO, ler_auditoria, ler_fila, linhas_planilha, rodar_comando_unico

CHAVES_AUDITORIA = (
    "ts",
    "artefato",
    "hash_conteudo",
    "documento_id",
    "pedido_id",
    "acao",
    "motivos",
    "motor",
    "ocr_usado",
    "valor_total_centavos",
)


def _inbox_isolada(tmp_path) -> Path:
    destino = tmp_path / "mocks"
    shutil.copytree(MOCKS, destino)
    return destino


def _contar_linhas(caminho: Path) -> int:
    """Linhas nao vazias do arquivo (0 se ainda nao existe)."""
    if not Path(caminho).exists():
        return 0
    return sum(1 for linha in Path(caminho).read_text(encoding="utf-8").splitlines() if linha.strip())


def test_comando_unico_mock_gera_os_quatro_artefatos(python_venv, raiz):
    """O comando unico do contrato roda de ponta a ponta e deixa a saida completa."""
    resultado = rodar_comando_unico(python_venv, raiz, "--mock")

    assert resultado.returncode == 0, (
        f"comando unico falhou (rc={resultado.returncode})\n"
        f"STDOUT:\n{resultado.stdout}\nSTDERR:\n{resultado.stderr}"
    )
    assert "Rodada concluida" in resultado.stdout

    esperados = {
        "xlsx": OUT_PADRAO / "controle_financeiro.xlsx",
        "csv": OUT_PADRAO / "controle_financeiro.csv",
        "auditoria": OUT_PADRAO / "auditoria.jsonl",
        "fila_excecoes": OUT_PADRAO / "fila_excecoes.json",
    }
    for nome, caminho in esperados.items():
        assert caminho.is_file(), f"{nome} nao foi gerado em {caminho}"
        assert caminho.stat().st_size > 0, f"{nome} foi gerado vazio"


def test_conteudo_da_planilha_do_comando_unico(python_venv, raiz):
    resultado = rodar_comando_unico(python_venv, raiz, "--mock")
    assert resultado.returncode == 0, resultado.stderr

    linhas = linhas_planilha(OUT_PADRAO / "controle_financeiro.xlsx")
    csv_bruto = (OUT_PADRAO / "controle_financeiro.csv").read_text(encoding="utf-8").splitlines()
    resumo = json.loads((OUT_PADRAO / "resumo.json").read_text(encoding="utf-8"))

    assert list(COLUNAS_PLANILHA) == csv_bruto[0].split(","), "cabecalho do CSV fora do contrato"
    assert len(linhas) == len(csv_bruto) - 1 == resumo["linhas_planilha"]
    assert linhas, "a planilha saiu sem nenhuma linha de dado"
    for linha in linhas:
        assert linha["pedido_id"], "linha sem pedido_id (sem rastro de origem)"
        assert linha["documento_id"], "linha sem documento_id de origem"
        assert linha["valor_total_centavos"] is not None
        assert linha["valor_total"] == _brl(linha["valor_total_centavos"])
        assert linha["status_validacao"] in ("auto_aprovado", "validado")


def test_conteudo_da_trilha_e_da_fila_do_comando_unico(python_venv, raiz):
    auditoria = OUT_PADRAO / "auditoria.jsonl"
    antes = _contar_linhas(auditoria)
    resultado = rodar_comando_unico(python_venv, raiz, "--mock")
    assert resultado.returncode == 0, resultado.stderr

    registros = ler_auditoria(auditoria)
    resumo = json.loads((OUT_PADRAO / "resumo.json").read_text(encoding="utf-8"))
    novas = registros[antes:] if len(registros) > antes else registros
    assert len(novas) == resumo["artefatos"], (
        "contrato 4.6: uma linha de auditoria por artefato processado na rodada"
    )
    assert resumo["auditoria_linhas_rodada"] == resumo["artefatos"]
    for registro in novas:
        faltando = [chave for chave in CHAVES_AUDITORIA if chave not in registro]
        assert not faltando, f"registro de auditoria sem {faltando}"

    fila = ler_fila(OUT_PADRAO / "fila_excecoes.json")
    assert fila["versao"]
    assert fila["gerado_em"]
    assert fila["total"] == len(fila["pendencias"])
    assert fila["total"] > 0, "nenhuma pendencia de revisao humana na rodada dos mocks"
    for pendencia in fila["pendencias"]:
        assert pendencia["motivo_codigo"], "pendencia sem motivo codigo"
        assert pendencia["detalhe"], "pendencia sem detalhe legivel"


def test_ocr_simulado_esta_rotulado_na_trilha_do_comando_unico(python_venv, raiz):
    auditoria = OUT_PADRAO / "auditoria.jsonl"
    antes = _contar_linhas(auditoria)
    resultado = rodar_comando_unico(python_venv, raiz, "--mock")
    assert resultado.returncode == 0, resultado.stderr

    registros = ler_auditoria(auditoria)
    novas = registros[antes:] if len(registros) > antes else registros
    escaneado = [
        r for r in novas if str(r["artefato"]).endswith("FORN-BETA_nf_2003_escaneada.pdf")
    ]
    assert escaneado, "o PDF escaneado (caso B1) nao aparece na trilha"
    assert escaneado[0]["motor"] == "ocr_simulado"
    assert escaneado[0]["ocr_usado"] is True
    assert escaneado[0]["ocr_simulado"] is True, "OCR simulado apresentado sem rotulo"

    resumo = json.loads((OUT_PADRAO / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["por_motor"].get("ocr_simulado", 0) >= 1
    assert "OCR SIMULADO" in resumo["aviso_ocr"]


def test_comando_unico_com_diretorios_isolados_publica_so_os_validados(python_venv, raiz, tmp_path):
    inbox = _inbox_isolada(tmp_path)
    out = tmp_path / "out"
    db = tmp_path / "pipeline.db"

    resultado = rodar_comando_unico(
        python_venv, raiz, "--inbox", str(inbox), "--out", str(out), "--db", str(db)
    )
    assert resultado.returncode == 0, f"STDOUT:\n{resultado.stdout}\nSTDERR:\n{resultado.stderr}"

    linhas = linhas_planilha(out / "controle_financeiro.xlsx")
    publicados = {linha["numero_pedido"] for linha in linhas}
    assert len(linhas) == 7, f"a rodada dos mocks devia publicar 7 pedidos, publicou {len(linhas)}"
    assert publicados == {"1001", "1002", "2001", "3001", "5001", "5002", "5003"}
    assert "3002" not in publicados, "caso B2 (divergencia) entrou na planilha"
    assert "2002" not in publicados, "caso B5 (injecao) entrou na planilha"
    assert "2003" not in publicados, "caso B1 (OCR com baixa confianca) entrou na planilha"

    registros = ler_auditoria(out / "auditoria.jsonl")
    assert len(registros) == 20, f"esperado um registro por artefato (20), veio {len(registros)}"
    assert all(r["documento_id"] for r in registros)


def test_duas_rodadas_do_comando_unico_sao_idempotentes(python_venv, raiz, tmp_path):
    inbox = _inbox_isolada(tmp_path)
    out = tmp_path / "out"
    db = tmp_path / "pipeline.db"
    argumentos = ("--inbox", str(inbox), "--out", str(out), "--db", str(db))

    primeira = rodar_comando_unico(python_venv, raiz, *argumentos)
    assert primeira.returncode == 0, primeira.stderr
    linhas_primeira = linhas_planilha(out / "controle_financeiro.xlsx")

    segunda = rodar_comando_unico(python_venv, raiz, *argumentos)
    assert segunda.returncode == 0, segunda.stderr
    linhas_segunda = linhas_planilha(out / "controle_financeiro.xlsx")

    assert len(linhas_primeira) == len(linhas_segunda) == 7
    assert [l["pedido_id"] for l in linhas_primeira] == [l["pedido_id"] for l in linhas_segunda]

    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["deduplicados"] == resumo["artefatos"], "a segunda rodada devia deduplicar tudo"
    assert resumo["auto_aprovados"] == 0


def _brl(centavos) -> str:
    from app.contratos import formatar_brl

    return formatar_brl(int(centavos))
