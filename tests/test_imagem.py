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


# ------------------------------------------------- preparo da imagem antes do OCR (F8-fase 4)
#
# Medido nas fotos reais que chegaram pelo canal: em escala original, 2 das 4 nao entregavam
# o valor total. Preparo = cinza + escala normalizada + contraste, e DEPOIS duas passagens
# (preparada e crua) unidas sem repetir linha.


def reduzir_nota(origem: Path, destino: Path, fator: float) -> Path:
    """Simula foto de celular: a mesma nota em resolucao menor."""
    from PIL import Image

    with Image.open(origem) as imagem:
        reduzida = imagem.resize(
            (round(imagem.width * fator), round(imagem.height * fator)), Image.LANCZOS
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    reduzida.save(destino)
    return destino


def test_imagem_preparada_normaliza_escala_e_tons_de_cinza(tmp_path):
    imagem = desenhar_nota(tmp_path / "nota.png")
    reduzida = reduzir_nota(imagem, tmp_path / "nota_pequena.png", 0.25)

    preparada = ingress._imagem_preparada(reduzida)
    assert preparada is not None, "sem PIL o preparo nao existe e a passagem crua assume"
    assert preparada.mode == "L", "o OCR de foto trabalha em tons de cinza"
    assert max(preparada.size) == ingress.ESCALA_OCR_ALVO, (
        f"a escala nao foi normalizada: {preparada.size}"
    )


def test_imagem_acima_do_alvo_nao_e_reduzida(tmp_path):
    """A escala so SOBE ate o alvo: foto grande nao perde pixel (nao se reduz a imagem)."""
    from PIL import Image

    imagem = desenhar_nota(tmp_path / "nota.png")
    with Image.open(imagem) as base_img:
        grande = tmp_path / "nota_grande.png"
        base_img.resize((2000, round(base_img.height * 2000 / base_img.width)), Image.LANCZOS).save(grande)

    preparada = ingress._imagem_preparada(grande)
    assert max(preparada.size) == 2000, "imagem acima do alvo tem de passar intacta"


def test_linha_repetida_das_duas_passagens_entra_uma_vez():
    """A mesma linha lida nas duas passagens nao pode contar como duas.

    Sem isso, uma nota com uma data viraria nota com "duas datas" e o extrator descartaria
    a data por ambiguidade (regra de seguranca) - o preparo viraria piora.
    """
    passagem_1 = "NOTA FISCAL ELETRONICA\nDATA DE EMISSAO 17/03/2026\nVALOR TOTAL R$ 250,00"
    passagem_2 = "nota fiscal eletronica\ndata de emissao 17/03/2026\nvalor total r$ 250,00"

    unida = ingress.unir_leituras([passagem_1, passagem_2])
    assert unida.splitlines() == passagem_1.splitlines(), (
        "as linhas repetidas (mesmo com caixa diferente) tem de entrar uma vez so"
    )

    # A passagem 2 repete a linha do total (ja veio na 1) e acrescenta 2 linhas novas:
    # cada linha entra 1 vez, na ordem - 5 linhas no total.
    complementar = "VALOR TOTAL R$ 250,00\nCHAVE DE ACESSO\n3526037297338000023255001000001001196820125 0"
    com_extra = ingress.unir_leituras([passagem_1, complementar])
    assert com_extra.splitlines() == [
        "NOTA FISCAL ELETRONICA",
        "DATA DE EMISSAO 17/03/2026",
        "VALOR TOTAL R$ 250,00",
        "CHAVE DE ACESSO",
        "3526037297338000023255001000001001196820125 0",
    ], com_extra


def test_imagem_pequena_demais_para_a_passagem_crua_e_lida_apos_o_preparo(tmp_path):
    """A prova que interessa: foto pequena do celular nao vira "documento ilegivel"."""
    import pytesseract
    from PIL import Image

    imagem = desenhar_nota(tmp_path / "nota.png")
    reduzida = reduzir_nota(imagem, tmp_path / "nota_pequena.png", 0.25)

    with Image.open(reduzida) as pequena:
        cru = pytesseract.image_to_string(pequena, lang=ingress.idioma_ocr(pytesseract))
    assert cru.strip() == "", (
        "se a passagem crua ja lê, este teste perdeu o sentido: reavalie o preparo"
    )

    leitura = ingress.ocr_imagem(reduzida)
    digitos = "".join(c for c in leitura.texto if c.isdigit())
    assert "250,00" in leitura.texto, f"o preparo nao recuperou o valor: {leitura.texto[:200]!r}"
    assert CHAVE_ALFA in digitos, "o preparo nao recuperou a chave de acesso"


def test_imagem_real_do_celular_enche_o_maximo_de_campos_que_o_ocr_permite(tmp_path):
    """Ponta a ponta com foto: preto no branco reduzido -> ancora o comportamento medido.

    O que se fixa aqui e o PISO: tipo de documento, valor total e status de revisao. Campo
    que o OCR de foto nao entrega com seguranca (CNPJ/data de nota de cliente real) nao
    entra na assercao - prometer isso seria mentir sobre o motor.
    """
    from app import contratos, extracao as extracao_mod, persistencia

    imagem = desenhar_nota(tmp_path / "nota.png")
    reduzida = reduzir_nota(imagem, tmp_path / "nota_pequena.png", 0.4)

    leitura = ingress.ocr_imagem(reduzida)
    extracao = extracao_mod.extrair(
        leitura.texto, str(reduzida), str(reduzida), motor=contratos.MOTOR_TESSERACT
    )
    status, _motivos = persistencia.decidir(extracao)

    assert extracao.tipo_documento == "nf"
    assert extracao.valor_total_centavos == VALOR_ALFA
    assert status == contratos.STATUS_REVISAO_HUMANA, (
        "leitura de OCR nunca auto-aprova: confianca base 0.65 fica abaixo do limiar 0.90"
    )
