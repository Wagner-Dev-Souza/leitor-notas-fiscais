"""Extracao real (PDF nativo, PDF escaneado via OCR e mensagens) contra o manifest.

`data/mocks/manifest.json` e a verdade de referencia (contrato secao 7/8). Cada dimensao
do `esperado` tem um teste proprio para que a falha aponte o campo exato, sem barulho.

DEFEITOS ENCONTRADOS NA PRIMEIRA EXECUCAO (relatados, nao mascarados):

1. `pdf/FORN-ALFA_nf_1003.pdf` (caso B6) - `decidir()` devolve
   `divergencia_soma_itens` onde o manifest espera `total_sem_detalhamento`.
   Divergencia entre F2 (`app/persistencia.py`, dono gula - ramo "itens parciais") e
   F3 (`data/mocks/manifest.json`, dono preguica). O desfecho de negocio e o mesmo
   (`revisao_humana`, sem linha na planilha); o **codigo do motivo** difere.
   Teste que pina: `test_status_e_motivos_contra_manifest[pdf/FORN-ALFA_nf_1003.pdf]`.

2. `pdf/FORN-BETA_nf_2003_escaneada.pdf` (caso B1) - o sidecar
   `FORN-BETA_nf_2003_escaneada.pdf.ocr.txt` traz `BFTA`/`CANFTA` (letra F no lugar de E),
   confusao que o contrato 4.3 NAO documenta (o conjunto declarado e 0/O, 1/l/I, 5/S, 2/Z e
   espacos espurios) e que `recuperar_texto_ocr()` nao desfaz. O manifest espera os nomes
   limpos (`BETA`, `CANETA`). Divergencia entre F3 (gerador do sidecar/manifest) e F1
   (extrator). Testes que pinam: `test_nome_do_emitente_contra_manifest[...]` e
   `test_itens_contra_manifest[...]` para esse arquivo. O resto do documento (chave, CNPJ,
   valor, datas) sai correto e o motor sai rotulado como `ocr_simulado`.

3. `pdf/FORN-ALFA_nf_1001_copia.pdf` (caso B4) - o manifest declara essa copia como
   IDENTICA em bytes ao `FORN-ALFA_nf_1001.pdf` (mesmo `sha256`) mas registra no
   `esperado.chave_acesso_nf` uma chave diferente da do original
   (`...1748910120` x `...1968201250`). Conferido: bytes iguais, texto igual, e o
   `esperado` do original e a chave realmente impressa. Defeito de F3 no manifest.
   Teste que pina: `test_cnpj_e_chave_contra_manifest[pdf/FORN-ALFA_nf_1001_copia.pdf]`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.contratos import TIPO_NF, TIPO_PEDIDO

RAIZ = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((RAIZ / "data" / "mocks" / "manifest.json").read_text(encoding="utf-8"))
ITENS: list[dict] = list(MANIFEST["itens"])


def casos(**filtro) -> list:
    selecionados = [i for i in ITENS if all(i.get(k) == v for k, v in filtro.items())]
    return pytest.mark.parametrize("item", selecionados, ids=[i["arquivo"] for i in selecionados])


CASOS = pytest.mark.parametrize("item", ITENS, ids=[i["arquivo"] for i in ITENS])


# --------------------------------------------------------------------- identificacao


@CASOS
def test_tipo_documento_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    assert extracao.tipo_documento == item["esperado"]["tipo_documento"]
    assert extracao.tipo_documento in (TIPO_NF, TIPO_PEDIDO)


@CASOS
def test_numero_pedido_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    assert extracao.numero_pedido == item["esperado"]["numero_pedido"]


@CASOS
def test_cnpj_e_chave_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    assert extracao.emitente_cnpj == item["esperado"]["emitente_cnpj"]
    assert extracao.chave_acesso_nf == item["esperado"]["chave_acesso_nf"]


@CASOS
def test_nome_do_emitente_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    assert extracao.emitente_nome == item["esperado"]["emitente_nome"]


@CASOS
def test_datas_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    assert extracao.data_emissao == item["esperado"]["data_emissao"]
    assert extracao.data_vencimento == item["esperado"]["data_vencimento"]


@CASOS
def test_valor_total_e_soma_dos_itens_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    esperado = item["esperado"]
    assert extracao.valor_total_centavos == esperado["valor_total_centavos"]
    assert extracao.soma_itens_centavos() == esperado["soma_itens_centavos"]


def _canonico_ocr(texto: str) -> str:
    """Forma canonica da tabela de confusoes do contrato 4.3, sem espacos.

    Descricao de item e texto livre lido por OCR: exigir caractere exato cobraria do motor
    uma perfeicao que o proprio contrato nao promete. A comparacao usa a confusao
    DECLARADA (0/O, 1/l/I, 5/S, 2/Z) e ignora espaco - que e justamente o que o OCR erra
    (medido: o Tesseract le "HP 26A" como "HPZ6A"). Item trocado, faltando ou de outro
    documento continua reprovando.
    """
    from app.ingress import TABELA_OCR

    return re.sub(r"\s+", "", (texto or "").upper().translate(TABELA_OCR))


@CASOS
def test_itens_contra_manifest(item, decisoes):
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    esperados = item["esperado"]["itens"]
    reais = extracao.itens
    assert len(reais) == len(esperados), (
        f"quantidade de itens diverge: real={len(reais)} manifest={len(esperados)}"
    )
    for indice, (real, esperado) in enumerate(zip(reais, esperados)):
        assert _canonico_ocr(real.descricao) == _canonico_ocr(esperado["descricao"]), (
            f"item {indice} descricao: real={real.descricao!r} "
            f"manifest={esperado['descricao']!r}"
        )
        quantidade = None if real.quantidade is None else str(real.quantidade)
        assert quantidade == esperado["quantidade"], f"item {indice} quantidade"
        assert real.unidade == esperado["unidade"], f"item {indice} unidade"
        assert real.valor_unitario_centavos == esperado["valor_unitario_centavos"], (
            f"item {indice} valor unitario"
        )
        assert real.valor_total_centavos == esperado["valor_total_centavos"], (
            f"item {indice} valor total"
        )


@pytest.mark.parametrize(
    "item",
    [i for i in ITENS if "status_esperado" in i["esperado"]],
    ids=[i["arquivo"] for i in ITENS if "status_esperado" in i["esperado"]],
)
def test_status_e_motivos_contra_manifest(item, decisoes):
    _extracao, status, motivos = decisoes[item["arquivo"]]
    esperado = item["esperado"]
    assert status == esperado["status_esperado"]
    assert sorted(motivos) == sorted(esperado["motivos_esperados"]), (
        f"motivos divergem: real={motivos} manifest={esperado['motivos_esperados']}"
    )


# --------------------------------------------------------------------- regras de honestidade


@CASOS
def test_campo_ausente_e_none_nunca_zero_ou_string_vazia(item, decisoes):
    """Contrato secao 5: campo ausente e `None`. Nunca 0, nunca string vazia."""
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    for campo, valor in (
        ("emitente_cnpj", extracao.emitente_cnpj),
        ("data_emissao", extracao.data_emissao),
        ("data_vencimento", extracao.data_vencimento),
        ("valor_total_centavos", extracao.valor_total_centavos),
        ("numero_pedido", extracao.numero_pedido),
        ("emitente_nome", extracao.emitente_nome),
    ):
        esperado = item["esperado"].get(campo)
        if esperado is None:
            assert valor is None, f"{campo} devia ser None, veio {valor!r}"
        assert valor != "" and valor != 0 or valor is None, (
            f"{campo} nao pode ser string vazia nem zero: {valor!r}"
        )


@CASOS
def test_confianca_por_campo_existe_e_esta_na_faixa(item, decisoes):
    """CA-E2-02: todo campo extraido carrega confianca entre 0 e 1."""
    extracao, _status, _motivos = decisoes[item["arquivo"]]
    assert 0.0 <= extracao.confianca_geral <= 1.0
    assert isinstance(extracao.confianca_por_campo, dict) and extracao.confianca_por_campo
    for campo, valor in extracao.confianca_por_campo.items():
        assert 0.0 <= valor <= 1.0, f"confianca fora da faixa em {campo}: {valor}"


@casos(caso_borda="B3")
def test_b3_mensagem_sem_valor_nao_inventa_nada(item, decisoes):
    extracao, status, _motivos = decisoes[item["arquivo"]]
    assert extracao.valor_total_centavos is None
    assert extracao.numero_pedido == item["esperado"]["numero_pedido"]
    assert extracao.confianca_geral < 0.6, "mensagem sem valor tem de sair com confianca baixa"
    assert status != "auto_aprovado", "mensagem sem valor nao pode ser publicada sozinha"
    assert extracao.soma_itens_centavos() is None


def test_b1_escaneada_usa_ocr_rotulado_e_confianca_menor(artefatos_ingeridos, decisoes):
    """Contrato 4.3: o caminho do escaneado e OCR, ROTULADO com o motor que leu.

    A ordem do contrato e motor real primeiro, simulado depois. Com o Tesseract instalado
    na maquina quem le e ele; sem o binario, o sidecar. Nos dois casos a leitura tem de
    sair rotulada - nenhuma pode se passar por leitura nativa. O caminho simulado tem
    teste proprio logo abaixo.
    """
    artefato = next(
        a for a in artefatos_ingeridos if a.caminho.endswith("FORN-BETA_nf_2003_escaneada.pdf")
    )
    assert artefato.motor in ("ocr_simulado", "tesseract")
    assert artefato.texto.strip(), "a leitura do escaneado nao chegou ao artefato"
    if artefato.motor == "ocr_simulado":
        assert 0.55 <= artefato.confianca_leitura <= 0.75
    extracao, status, _motivos = decisoes["pdf/FORN-BETA_nf_2003_escaneada.pdf"]
    assert extracao.ocr_usado is True
    assert status == "revisao_humana"
    # o que o OCR simulado entrega de forma recuperavel sai correto:
    assert extracao.valor_total_centavos == 64865
    assert extracao.chave_acesso_nf == "35260349018909000166550010000020031759670983"
    assert extracao.emitente_cnpj == "49018909000166"


def test_b1_sem_tesseract_cai_no_sidecar_rotulado_como_simulado(monkeypatch, raiz):
    """Sem motor real na maquina, o sidecar e usado - e vem marcado `ocr_simulado`.

    O fallback nao pode sumir so porque a maquina passou a ter Tesseract: ele e o
    caminho de quem nao tem o binario, e continua tendo de ser honesto no rotulo.
    """
    from app import ingress as ING

    monkeypatch.setattr(ING, "localizar_tesseract", lambda: None)
    leitura = ING.ocr_pdf(raiz / "data" / "mocks" / "pdf" / "FORN-BETA_nf_2003_escaneada.pdf")
    assert leitura.motor == "ocr_simulado"
    assert 0.55 <= leitura.confianca_leitura <= 0.75
    assert leitura.texto.strip(), "o sidecar de OCR simulado nao foi lido"


def test_b1_escaneada_recupera_o_zero_confundido_com_letra(decisoes):
    """Degradacao documentada (0/O, 1/l/I, 5/S, 2/Z) tem de ser desfeita pelo extrator."""
    extracao, _status, _motivos = decisoes["pdf/FORN-BETA_nf_2003_escaneada.pdf"]
    assert extracao.emitente_cnpj == "49018909000166", "CNPJ do OCR saiu com letra no lugar de digito"
    assert extracao.chave_acesso_nf.isdigit()


def test_b4_copia_identica_tem_o_mesmo_conteudo_do_original(decisoes):
    """Prova de que a chave do esperado da copia no manifest esta errada.

    Os dois arquivos sao o MESMO binario (sha256 identico no manifest), logo a extracao
    tem de devolver exatamente o mesmo conteudo.
    """
    original, _s1, _m1 = decisoes["pdf/FORN-ALFA_nf_1001.pdf"]
    copia, _s2, _m2 = decisoes["pdf/FORN-ALFA_nf_1001_copia.pdf"]
    assert copia.chave_acesso_nf == original.chave_acesso_nf
    assert copia.valor_total_centavos == original.valor_total_centavos
    assert copia.numero_pedido == original.numero_pedido


def test_b6_item_sem_valor_unitario_nao_inventa_preco(decisoes):
    """B6: item sem valor unitario nao recebe preco chutado e o documento vai para humano."""
    extracao, status, _motivos = decisoes["pdf/FORN-ALFA_nf_1003.pdf"]
    servico = [i for i in extracao.itens if "SERVICO" in i.descricao.upper()]
    assert servico, "o item sem valor unitario desapareceu da extracao"
    assert servico[0].valor_unitario_centavos is None
    assert servico[0].valor_total_centavos is None
    assert extracao.soma_itens_centavos() is None
    assert status == "revisao_humana"


# --------------------------------------------------------------------- OCR real


def _texto_da_nf_nativa() -> str:
    """Texto real de uma NF do corpus (leitura nativa), para isolar o efeito do motor."""
    import pdfplumber

    with pdfplumber.open(str(RAIZ / "data" / "mocks" / "pdf" / "FORN-ALFA_nf_1001.pdf")) as pdf:
        return "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)


def test_pdf_escaneado_com_motor_de_ocr_usa_confianca_de_ocr(tmp_path):
    """PDF SEM sidecar lido por OCR real: a confianca por campo tem de ser de OCR.

    Antes o motor nao chegava a extracao. Sem sidecar (`<arquivo>.ocr.txt`), ela concluia
    "leitura nativa" e pontuava os campos com a base nativa (0,95) - otimista para um texto
    que veio de OCR. Agora quem leu acompanha a extracao, e o pipeline repassa o motor do
    artefato. Mesmo arquivo e mesmo texto: so o motor muda.
    """
    from app import extracao as EX
    from app import persistencia as PE
    from app.contratos import CANAL_PDF, LIMIAR_AUTO_APROVACAO, MOTOR_TESSERACT
    from conftest import pdf_de_imagem_sem_texto

    texto = _texto_da_nf_nativa()
    alvo = pdf_de_imagem_sem_texto(tmp_path / "escaneada_sem_sidecar.pdf")

    nativo = EX.extrair(texto, CANAL_PDF, str(alvo))
    real = EX.extrair(texto, CANAL_PDF, str(alvo), motor=MOTOR_TESSERACT)

    assert nativo.ocr_usado is False, "sem motor de OCR e sem sidecar, a leitura e nativa"
    assert real.ocr_usado is True, "motor de OCR tem de marcar a leitura como OCR"
    assert real.motor == MOTOR_TESSERACT
    assert real.confianca_geral < nativo.confianca_geral, (
        "leitura de OCR nao pode confiar o mesmo que leitura nativa"
    )
    assert real.confianca_geral < LIMIAR_AUTO_APROVACAO, (
        "confianca de OCR nao pode alcancar o limiar de aprovacao automatica"
    )
    status, _motivos = PE.decidir(real)
    assert status == "revisao_humana", "leitura de OCR nao pode aprovar sozinha"
