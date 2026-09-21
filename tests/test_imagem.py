"""Leitura de IMAGEM: foto/print de nota entra pela inbox e vira dado no pipeline.

Requisito do cliente: o leitor nasceu lendo so PDF e tem de aceitar imagem tambem.

A imagem e desenhada pelo proprio teste a partir do **texto real** da NF do corpus
sintetico (`FORN-ALFA_nf_1001.pdf`), entao os rotulos de ancora sao exatamente os que o
extrator conhece: o que se mede aqui e o caminho `imagem -> OCR -> campos`, nao a
tolerancia a foto torta (essa so se mede com material do cliente).

Sem Tesseract instalado o arquivo inteiro e pulado: o requisito e OCR **real**, e pular
e mais honesto do que fingir que passou.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from app import ingress  # noqa: E402

NF_REFERENCIA = RAIZ_PROJETO / "data" / "mocks" / "pdf" / "FORN-ALFA_nf_1001.pdf"
CNPJ_ALFA = "72973380000232"
CHAVE_ALFA = "35260372973380000232550010000010011968201250"
VALOR_ALFA = 25000

pytestmark = pytest.mark.skipif(
    ingress.localizar_tesseract() is None,
    reason="Tesseract nao instalado nesta maquina: o requisito e OCR real",
)


def _python_do_projeto() -> str:
    return str(RAIZ_PROJETO / ".venv" / "Scripts" / "python.exe")


def _linhas_da_nf() -> list[str]:
    """Texto real da NF de referencia - a imagem usa os mesmos rotulos."""
    import pdfplumber

    with pdfplumber.open(str(NF_REFERENCIA)) as pdf:
        texto = "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)
    return [linha.strip() for linha in texto.splitlines() if linha.strip()]


def test_idioma_do_ocr_cai_para_ingles_quando_falta_portugues(monkeypatch):
    """Tesseract sem o pacote de portugues nao pode virar leitura vazia.

    O instalador oficial do Windows vem so com `eng` + `osd`. Pedir `por` sem ter o pacote
    faz o motor recusar e a leitura sair VAZIA - medido no runner do CI. O produto tem de
    ler em ingles nesse caso, e nao ficar mudo.
    """

    class _FalsoTesseract:
        @staticmethod
        def get_languages(config=""):
            return ["eng", "osd"]

    assert ingress.idioma_ocr(_FalsoTesseract) == "eng"

    class _ComPortugues:
        @staticmethod
        def get_languages(config=""):
            return ["eng", "osd", "por"]

    assert ingress.idioma_ocr(_ComPortugues) == "por"


def desenhar_nota(destino: Path) -> Path:
    """Desenha as linhas da NF num PNG limpo, preto no branco, fonte grande."""
    from PIL import Image, ImageDraw, ImageFont

    fonte = None
    for nome in ("arial.ttf", "calibri.ttf", "DejaVuSans.ttf"):
        try:
            fonte = ImageFont.truetype(nome, 30)
            break
        except OSError:
            continue
    if fonte is None:  # pragma: no cover - ambiente sem fonte escalavel
        pytest.fail("nenhuma fonte escalavel encontrada para desenhar a imagem de teste")

    linhas = _linhas_da_nf()
    largura, altura_linha, margem = 1500, 48, 30
    imagem = Image.new("RGB", (largura, altura_linha * len(linhas) + margem * 2), "white")
    pincel = ImageDraw.Draw(imagem)
    for indice, linha in enumerate(linhas):
        pincel.text((margem, margem + indice * altura_linha), linha, fill="black", font=fonte)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino)
    return destino


def test_imagem_vira_artefato_do_canal_imagem_lido_por_ocr(tmp_path):
    """A imagem entra na pasta de documentos e sai como artefato `imagem`/`tesseract`."""
    imagem = desenhar_nota(tmp_path / "inbox" / "pdf" / "nota_alfa.png")

    artefatos = ingress.ingerir(tmp_path / "inbox")

    assert len(artefatos) == 1, f"esperado 1 artefato de imagem, veio {len(artefatos)}"
    (artefato,) = artefatos
    assert artefato.tipo_artefato == "imagem"
    assert artefato.canal == "imagem"
    assert artefato.motor == "tesseract", "imagem so pode ser lida pelo OCR real"
    assert artefato.tem_camada_texto is False, "imagem nao tem camada de texto"
    assert artefato.paginas == 1
    assert artefato.hash_conteudo == hashlib.sha256(imagem.read_bytes()).hexdigest()

    digitos = "".join(caractere for caractere in artefato.texto if caractere.isdigit())
    assert CHAVE_ALFA in digitos, f"o OCR nao trouxe a chave de acesso: {artefato.texto[:200]!r}"
    assert "250,00" in artefato.texto, "o OCR nao trouxe o valor total"


def test_imagem_atravessa_o_pipeline_e_chega_a_fila_com_os_campos(tmp_path):
    """Ponta a ponta: imagem -> OCR -> extracao -> fila de revisao, com trilha."""
    desenhar_nota(tmp_path / "inbox" / "pdf" / "nota_alfa.png")
    out = tmp_path / "out"

    resultado = subprocess.run(
        [
            _python_do_projeto(),
            "-m",
            "app.run",
            "--mock",
            "--inbox",
            str(tmp_path / "inbox"),
            "--out",
            str(out),
            "--db",
            str(out / "pipeline.db"),
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(RAIZ_PROJETO)},
        timeout=300,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["artefatos"] == 1
    assert resumo["imagens"] == 1, "a imagem tem contador proprio no resumo"
    assert resumo["pdfs"] == 0 and resumo["mensagens"] == 0
    assert resumo["por_motor"] == {"tesseract": 1}
    assert resumo["ocr_real_artefatos"] == 1

    # Leitura de OCR entra com confianca 0.65 (base do contrato para OCR): fica ABAIXO do
    # limiar de aprovacao automatica (0.90) e por isso vai para revisao humana - nunca
    # para a planilha sem conferencia. Isso e o desenho do produto, nao um defeito.
    assert resumo["auto_aprovados"] == 0
    assert resumo["revisao"] == 1
    assert resumo["linhas_planilha"] == 0

    trilha = [
        json.loads(linha)
        for linha in (out / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    assert len(trilha) == 1
    registro = trilha[0]
    assert registro["canal"] == "imagem"
    assert registro["motor"] == "tesseract"
    assert registro["ocr_usado"] is True
    assert registro["ocr_simulado"] is False
    assert registro["tipo_documento"] == "nf"
    assert registro["numero_pedido"] == "1001"
    assert registro["valor_total_centavos"] == VALOR_ALFA
    assert registro["status_validacao"] == "revisao_humana"
    assert registro["motivos"] == ["baixa_confianca"]

    fila = json.loads((out / "fila_excecoes.json").read_text(encoding="utf-8"))
    assert fila["total"] == 1
    (pendencia,) = fila["pendencias"]
    assert pendencia["origem"] == "imagem"
    assert pendencia["motivo_codigo"] == "baixa_confianca"
    assert pendencia["emitente_nome"] == "ALFA DISTRIBUIDORA DE PECAS LTDA"
    assert pendencia["emitente_cnpj"] == CNPJ_ALFA
    assert pendencia["numero_pedido"] == "1001"
    assert pendencia["valor_suspeito"] == "250,00"
