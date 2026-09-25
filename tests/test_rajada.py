"""Rajada: volume de uma vez, sem perder e sem duplicar.

O que este teste **prova**: 120 artefatos numa rodada (90 notas em PDF + 30 mensagens de
WhatsApp), todos contabilizados, com planilha e fila fechando a conta - e a segunda rodada
sobre a mesma inbox deduplicando tudo.

O que ele **nao prova**: paralelismo. O alvo do produto e processo local unico + SQLite
(limitacao 8 do README): o teste mede o desenho que existe, nao outro desenho. O tempo real
sai no relatorio do pytest.

Os documentos sao montados pelo teste (nao usam o corpus), com pedido e valor distintos por
nota, para que nenhum deles seja confundido com outro na deduplicacao.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from conftest import linha_whatsapp, pdf_texto, rodar_pipeline  # noqa: E402

CNPJ_ALFA = "72.973.380/0002-32"
CNPJ14_ALFA = "72973380000232"


def _gerador_do_projeto():
    """O gerador de mocks do projeto, para montar chave de acesso com DV valido.

    Cada nota precisa da SUA chave: a identidade do pedido no produto e a chave de acesso
    (44 digitos). Reusar a mesma chave em 90 notas faria - corretamente - um unico pedido.
    """
    caminho = RAIZ_PROJETO / "tools" / "gerar_mocks.py"
    spec = importlib.util.spec_from_file_location("gerar_mocks_do_projeto", caminho)
    modulo = importlib.util.module_from_spec(spec)
    # `dataclasses` consulta `sys.modules` pelo nome do modulo: sem registrar antes, o
    # `@dataclass` do gerador quebra na importacao.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo

TOTAL_NFS = 90
TOTAL_MENSAGENS = 30
TOTAL = TOTAL_NFS + TOTAL_MENSAGENS
LIMITE_SEGUNDOS = 180.0  # teto generoso; o tempo real medido vai para o relatorio


def _brl(centavos: int) -> str:
    return f"{centavos // 100},{centavos % 100:02d}"


def _linhas_nf(numero: int, chave: str) -> list[str]:
    valor = 100 + numero % 900  # centavos, distinto por documento
    return [
        "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRONICA",
        "MODELO 55 - NF-e | MOCK SINTETICO, SEM VALOR FISCAL",
        "EMITENTE",
        "ALFA DISTRIBUIDORA DE PECAS LTDA",
        f"CNPJ: {CNPJ_ALFA}",
        "DESTINATARIO",
        "SQUAD 7 PECADOS LTDA",
        "CNPJ/CPF: 45.998.001/0001-05",
        f"NUMERO DA NF: {numero}",
        f"N DO PEDIDO: {numero}",
        "SERIE: 1",
        "DATA DE EMISSAO: 13/03/2026",
        "VENCIMENTO: 12/04/2026",
        f"CHAVE DE ACESSO: {chave}",
        "ITENS",
        "ITEM DESCRICAO QTD UN V.UNITARIO V.TOTAL",
        f"1 ITEM DE CARGA {numero} 1,0000 UN {_brl(valor)} {_brl(valor)}",
        f"VALOR TOTAL DA NOTA: R$ {_brl(valor)}",
    ]


@pytest.fixture(scope="module")
def inbox_rajada(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("rajada")
    inbox = base / "inbox"
    for subpasta in ("pdf", "whatsapp", "telegram"):
        (inbox / subpasta).mkdir(parents=True, exist_ok=True)

    gerador = _gerador_do_projeto()
    for indice in range(TOTAL_NFS):
        numero = 10000 + indice
        chave = gerador.montar_chave(
            CNPJ14_ALFA, numero, datetime(2026, 3, 13), random.Random(numero)
        )
        assert len(chave) == 44, f"chave invalida gerada para a nota {numero}"
        pdf_texto(inbox / "pdf" / f"carga_nf_{numero}.pdf", _linhas_nf(numero, chave))

    linhas = [
        linha_whatsapp(
            f"Pedido {20000 + indice} confirmado, total R$ 10,00",
            id_externo=f"wamid.CARGA{indice:03d}",
        )
        for indice in range(TOTAL_MENSAGENS)
    ]
    (inbox / "whatsapp" / "whatsapp_carga.jsonl").write_text(
        "\n".join(linhas) + "\n", encoding="utf-8"
    )
    return inbox


def test_rajada_processa_tudo_e_a_contabilidade_fecha(inbox_rajada, tmp_path):
    out = tmp_path / "out"
    inicio = time.monotonic()
    resumo = rodar_pipeline(inbox_rajada, out)
    duracao = time.monotonic() - inicio

    assert resumo["artefatos"] == TOTAL
    assert resumo["pdfs"] == TOTAL_NFS
    assert resumo["mensagens"] == TOTAL_MENSAGENS
    assert resumo["imagens"] == 0

    baldes = (
        resumo["auto_aprovados"]
        + resumo["revisao"]
        + resumo["rejeitados"]
        + resumo["deduplicados"]
    )
    assert baldes == TOTAL, f"a contabilidade nao fecha: {baldes} de {TOTAL}"
    assert resumo["deduplicados"] == 0, "documentos distintos nao podem deduplicar entre si"
    assert resumo["linhas_planilha"] == TOTAL, (
        "lancamento direto: todo artefato processado vira linha na planilha"
    )

    registros = [
        json.loads(linha)
        for linha in (out / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    assert len(registros) == TOTAL, "uma linha de trilha por artefato"
    assert len({registro["documento_id"] for registro in registros}) == TOTAL, (
        "cada documento tem de ter identidade propria - sem colisao"
    )
    assert len({registro["pedido_id"] for registro in registros}) == TOTAL

    assert duracao < LIMITE_SEGUNDOS, (
        f"rajada de {TOTAL} artefatos levou {duracao:.1f}s (teto {LIMITE_SEGUNDOS:.0f}s)"
    )
    print(f"\nrajada: {TOTAL} artefatos ({TOTAL_NFS} PDF + {TOTAL_MENSAGENS} mensagens) "
          f"em {duracao:.2f}s")


def test_rajada_repetida_deduplica_tudo(inbox_rajada, tmp_path):
    """Mesma inbox de novo: nenhuma linha nova, nenhum documento novo."""
    out = tmp_path / "out"
    primeira = rodar_pipeline(inbox_rajada, out)

    resumo = rodar_pipeline(inbox_rajada, out)

    assert resumo["artefatos"] == TOTAL
    assert resumo["deduplicados"] == TOTAL
    assert resumo["auto_aprovados"] == 0
    assert resumo["revisao"] == 0
    assert resumo["rejeitados"] == 0
    # O ledger e regravado a partir do banco a cada rodada: o que nao pode acontecer e a
    # planilha CRESCER ou mudar. Nenhum pedido novo entra.
    assert resumo["linhas_planilha"] == primeira["linhas_planilha"], (
        "a segunda rodada mexeu na planilha"
    )
