"""Nota fiscal MULTIPAGINA: os itens das paginas 2+ tem de entrar.

O ingress concatena o texto de todas as paginas (`ingress._texto_pdfplumber`), mas isso nunca
teve teste - o corpus sintetico so tem documento de 1 pagina. Sem cobertura, uma regressao que
parasse na primeira pagina passaria despercebida, e nota fiscal grande (30 itens) e exatamente
esse caso.

A NF e montada pelo teste, com os rotulos de ancora que o extrator conhece, valores cuja soma
fecha e CNPJ/chave com digito verificador valido (os do corpus, para nao inventar dado fiscal).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from conftest import rodar_pipeline  # noqa: E402

from app import extracao as EX  # noqa: E402
from app import ingress  # noqa: E402

CNPJ_ALFA = "72.973.380/0002-32"
CHAVE_ALFA = "35260372973380000232550010000010011968201250"
NUMERO_PEDIDO = "9010"
TOTAL_CENTAVOS = 64875  # 125,00 + 80,00 + 45,00 (pagina 1) + 117,50 + 281,25 (pagina 2)

PAGINA_1 = [
    "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRONICA",
    "MODELO 55 - NF-e | MOCK SINTETICO, SEM VALOR FISCAL",
    "EMITENTE",
    "ALFA DISTRIBUIDORA DE PECAS LTDA",
    f"CNPJ: {CNPJ_ALFA}",
    "END AV. DAS INDUSTRIAS, 1200 - SAO PAULO/SP",
    "DESTINATARIO",
    "SQUAD 7 PECADOS LTDA",
    "CNPJ/CPF: 45.998.001/0001-05",
    f"NUMERO DA NF: {NUMERO_PEDIDO}",
    f"N DO PEDIDO: {NUMERO_PEDIDO}",
    "SERIE: 1",
    "DATA DE EMISSAO: 13/03/2026",
    "VENCIMENTO: 12/04/2026",
    f"CHAVE DE ACESSO: {CHAVE_ALFA}",
    "ITENS",
    "ITEM DESCRICAO QTD UN V.UNITARIO V.TOTAL",
    "1 PARAFUSO SEXTAVADO 5/16 X 2 100,0000 PC 1,25 125,00",
    "2 ARRUELA LISA 5/16 250,0000 PC 0,32 80,00",
    "3 PORCA SEXTAVADA 5/16 100,0000 PC 0,45 45,00",
]

PAGINA_2 = [
    "ITENS (CONTINUACAO)",
    "4 CANETA ESFEROGRAFICA AZUL 50,0000 UN 2,35 117,50",
    "5 CAIXA ARQUIVO MORTO 15,0000 UN 18,75 281,25",
    f"VALOR TOTAL DA NOTA: R$ {TOTAL_CENTAVOS / 100:.2f}".replace(".", ","),
]


def pdf_multipagina(destino: Path, paginas: list[list[str]]) -> Path:
    """PDF nativo com varias paginas, uma lista de linhas por pagina."""
    from reportlab.pdfgen import canvas

    destino.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(destino))
    for indice, linhas in enumerate(paginas):
        if indice:
            pdf.showPage()
        altura = 760
        for linha in linhas:
            pdf.drawString(40, altura, linha)
            altura -= 18
    pdf.save()
    return destino


@pytest.fixture
def inbox_multipagina(tmp_path: Path) -> Path:
    inbox = tmp_path / "inbox"
    pdf_multipagina(inbox / "pdf" / "multipagina_9010.pdf", [PAGINA_1, PAGINA_2])
    return inbox


def test_artefato_multipagina_conta_e_concatena_as_paginas(inbox_multipagina):
    artefatos = ingress.ingerir(inbox_multipagina)

    assert len(artefatos) == 1
    (artefato,) = artefatos
    assert artefato.paginas == 2, f"o PDF tem 2 paginas, o artefato viu {artefato.paginas}"
    assert artefato.motor == "pdfplumber"
    assert artefato.tem_camada_texto is True
    # texto das duas paginas no mesmo artefato
    assert "PARAFUSO SEXTAVADO" in artefato.texto, "texto da pagina 1 ausente"
    assert "CAIXA ARQUIVO MORTO" in artefato.texto, "texto da pagina 2 ausente"


def test_extracao_multipagina_traz_itens_das_duas_paginas(inbox_multipagina):
    """O caso que o corpus nao cobria: item da pagina 2 nao pode ser perdido."""
    (artefato,) = ingress.ingerir(inbox_multipagina)
    extracao = EX.extrair(artefato.texto, artefato.canal, artefato.caminho)

    assert extracao.numero_pedido == NUMERO_PEDIDO
    assert extracao.valor_total_centavos == TOTAL_CENTAVOS
    assert extracao.chave_acesso_nf == CHAVE_ALFA
    assert extracao.emitente_cnpj == "72973380000232"

    descricoes = [item.descricao for item in extracao.itens]
    assert len(descricoes) == 5, f"esperado 5 itens (3 na pagina 1, 2 na pagina 2): {descricoes}"
    assert "CANETA ESFEROGRAFICA AZUL" in descricoes, "item da pagina 2 nao foi lido"
    assert "CAIXA ARQUIVO MORTO" in descricoes, "item da pagina 2 nao foi lido"

    # a soma dos itens tem de fechar com o total impresso na ultima pagina
    assert extracao.soma_itens_centavos() == TOTAL_CENTAVOS


def test_pipeline_multipagina_aprova_o_documento(inbox_multipagina, tmp_path):
    """Documento nativo, somas fechando: caminho feliz ponta a ponta."""
    resumo = rodar_pipeline(inbox_multipagina, tmp_path / "out")

    assert resumo["artefatos"] == 1
    assert resumo["pdfs"] == 1
    assert resumo["auto_aprovados"] == 1, "nota nativa com somas fechando deve ser aprovada"
    assert resumo["revisao"] == 0
    assert resumo["linhas_planilha"] == 1

    import json

    registros = [
        json.loads(texto)
        for texto in (tmp_path / "out" / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
        if texto.strip()
    ]
    assert len(registros) == 1
    registro = registros[0]
    assert registro["numero_pedido"] == NUMERO_PEDIDO
    assert registro["valor_total_centavos"] == TOTAL_CENTAVOS
    assert registro["status_validacao"] == "auto_aprovado"
    assert registro["motivos"] == []

    with open(tmp_path / "out" / "controle_financeiro.csv", encoding="utf-8") as arquivo:
        planilha = arquivo.read()
    assert NUMERO_PEDIDO in planilha
    assert "648,75" in planilha
