"""Extracao deterministica por rotulo/ancora. Sem LLM, sem rede, sem inferencia.

Dono: avareza (F1 - nucleo). Fronteira congelada na secao 5 do contrato:

    classificar(texto) -> 'nf' | 'pedido' | 'desconhecido'
    extrair(texto, origem_canal, arquivo=None) -> Extracao
    extrair_mensagem(msg: MensagemBruta) -> Extracao

Regras que este modulo respeita sem excecao:
  * Campo ausente e `None`. Nunca `0`, nunca string vazia, nunca chute.
  * Todo valor sai com `evidencia` = trecho **literal** do texto.
  * Instrucao maliciosa embutida no documento (injecao de prompt) **nunca** e obedecida:
    o texto e dado, nao ordem. O caso vira motivo `texto_instrucao_suspeita`.
  * Dinheiro em centavos (int), data em ISO — a normalizacao e da frente F2
    (`app.normaliza`, dono: gula), chamada aqui pelas assinaturas do contrato.

Normalizacao de rotulos para OCR
--------------------------------
Os PDFs escaneados passam por OCR (real ou simulado) e chegam com confusoes tipicas
(`0/O`, `1/l/I`, `5/S`, `2/Z`). `app.ingress.busca_ocr()` aplica uma tabela canonica
**que preserva o comprimento da string**, entao rotulos e valores casam tanto no texto
nativo quanto no degradado, e o recorte de posicao continua apontando para o trecho
literal original (que e o que vai para `evidencia`).

Formula de confianca (doc 02 secao 4.4) e a leitura adotada
-----------------------------------------------------------
`score = base_motor x fator_checksum x fator_coerencia x fator_consenso`

- `base_motor`: 0.95 ancora forte / 0.80 texto sem ancora; quando a leitura vem de OCR:
  0.65 / 0.55 (o doc da 0.65 para "imagem/OCR" — aqui o texto e nativo-via-OCR).
- `fator_checksum`: 1.00 passou a validacao deterministica do campo (DV de CNPJ/chave,
  faixa de valor, janela de plausibilidade da data, formato da quantidade) ou nao ha
  validacao a aplicar; 0.50 quando a validacao e **aplicavel mas inconclusiva**
  (ex.: itens ausentes, entao a aritmetica nao fecha nem reprova); 0.00 quando falhou.
  NOTA DE ENGENHARIA: o texto do doc 02 lista "0.50 sem checksum aplicavel". Lido ao pe
  da letra, todo campo sem checksum (nome, numero do pedido, forma de pagamento) cairia
  para ~0.40 e a **media ponderada nunca chegaria a 0.90** — ou seja, a propria regra de
  auto-aprovacao (>= 0.90 com nenhum obrigatorio abaixo de 0.80) ficaria inalcancavel e a
  planilha sairia vazia, violando a definicao de pronto da secao 9. Optou-se por: 0.50 =
  "aplicavel e inconclusivo". Os valores de 0.85/0.60 de `fator_consenso` continuam
  punindo leitura fraca, e o OCR derruba o score do documento para a faixa de revisao.
- `fator_coerencia`: 1.00 dentro da faixa esperada | 0.70 outlier (aqui: data fora da
  janela plausivel ou, no caso de data ambigua `dd/mm` com dia <= 12, 0.70).
- `fator_consenso`: 1.00 com corroboracao deterministica independente (aritmetica dos
  itens casa, DV valida, janela de data ok); 0.85 fonte unica com evidencia literal;
  0.60 fonte unica sem evidencia literal.

`confianca_geral` = media ponderada (peso 3 para `valor_total` e `emitente_cnpj`,
peso 2 para as datas, peso 1 para o resto) **somente sobre os campos presentes**:
campo ausente nao vira zero, senao "ausente" e "ruim" ficariam indistinguiveis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

from .contratos import (
    CANAL_TELEGRAM,
    CANAL_WHATSAPP,
    MOTIVO_INJECAO_SUSPEITA,
    TIPO_DESCONHECIDO,
    TIPO_NF,
    TIPO_PEDIDO,
    Item,
    Extracao,
    MensagemBruta,
    sha256_arquivo,
    sha256_bytes,
)
from .ingress import (
    TABELA_OCR,
    busca_ocr,
    caminho_sidecar_ocr,
    hash_mensagem,
    confianca_ocr_simulado,
)
from .normaliza import (
    normalizar_cnpj,
    normalizar_data,
    normalizar_moeda_centavos,
    normalizar_quantidade,
    validar_chave_nf_dv,
)

TEMPLATE_VERSAO = "extrator-v1"

# --------------------------------------------------------------- fatores (4.4)

BASE_ANCORA_NATIVO = 0.95
BASE_SEM_ANCORA_NATIVO = 0.80
BASE_ANCORA_OCR = 0.65
BASE_SEM_ANCORA_OCR = 0.55

CK_OK = 1.00
CK_INCONCLUSIVO = 0.50
CK_FALHOU = 0.00

CONSENSO_CORROBORADO = 1.00
CONSENSO_EVIDENCIA = 0.85
CONSENSO_SEM_EVIDENCIA = 0.60

COERENCIA_OK = 1.00
COERENCIA_OUTLIER = 0.70

PESO_CAMPO = {
    "valor_total": 3,
    "emitente_cnpj": 3,
    "data_emissao": 2,
    "data_vencimento": 2,
}
PESO_PADRAO = 1


# ------------------------------------------------------------------ utilidades


def _c(padrao: str) -> str:
    """Canoniza um padrao regex para casar texto nativo e texto degradado por OCR.

    Aplica maiuscula + `TABELA_OCR` apenas nas sequencias alfabeticas, preservando
    escapes de regex (`\\s`, `\\d`, `\\b`, ...) intactos. Escape = barra invertida
    seguida de UMA letra; por isso `\\bTOTAL\\b` ainda tem o corpo "TOTAL" canonicalizado.
    """
    partes = re.split(r"(\\[A-Za-z])", padrao)
    for i, parte in enumerate(partes):
        if len(parte) == 2 and parte.startswith("\\"):
            continue
        partes[i] = parte.upper().translate(TABELA_OCR)
    return "".join(partes)


def _trecho(linha_orig: str, ini: int, fim: int) -> str:
    """Recorta a evidencia no texto ORIGINAL (posicoes vem da forma canonica)."""
    if len(linha_orig) < fim:
        return linha_orig.strip()
    return linha_orig[ini:fim].strip()


RE_MOEDA_BR = re.compile(r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}")
RE_MOEDA_US = re.compile(r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*\.\d{2}")
RE_DATA = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{1,2}\s+DE\s+[A-Z]{3,12}\s+DE\s+\d{4}"
)
RE_QTD_UN = re.compile(r"(?P<qtd>\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(?P<un>[A-Z0-9]{1,6})?$")
RE_PEDIDO_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9._/-]{1,29}")
RE_SEQUENCIA = re.compile(r"^\s*\d{1,4}[\s.)-]")

# --------------------------------------------------------------- ancoras (4.2)

ANCORAS_TOTAL = tuple(
    _c(p)
    for p in (
        r"VALOR\s+TOTAL\s+DA\s+NOTA",
        r"VALOR\s+TOTAL\s+DO\s+DOCUMENTO",
        r"TOTAL\s+A\s+PAGAR",
        r"VALOR\s+TOTAL\s+GERAL",
        r"VALOR\s+TOTAL",
        r"TOTAL\s+GERAL",
        r"\bTOTAL\b",
        # Ultimo recurso (texto livre de mensagem): "valor de R$ ...", "valor R$ ...".
        # So e alcancado quando nenhuma ancora de total casou — nunca antes dela.
        r"\bVALOR\b",
    )
)

ANCORAS_CHAVE = tuple(_c(p) for p in (r"CHAVE\s+DE\s+ACESSO", r"CHAVE\s+DE\s+ACESS0"))

ANCORAS_CNPJ = (_c(r"CNPJ"),)

ANCORAS_EMISSAO = tuple(
    _c(p)
    for p in (
        r"DATA\s+D[AE]\s+EMISS[AÃ]O",
        r"DATA\s+DE\s+EMISS[AÃ]O",
        r"EMISS[AÃ]O\s+EM",
        r"EMITID[OA]\s+EM",
        r"EMITIDA?\s+EM",
        r"EMISS[AÃ]O",
    )
)

ANCORAS_VENCIMENTO = tuple(
    _c(p) for p in (r"DATA\s+DE\s+VENCIMENTO", r"VENCIMENTO", r"VENCE\s+EM")
)

ANCORAS_PEDIDO = tuple(
    _c(p)
    for p in (
        r"N[º°o]?\s*D[OE]\s*PEDIDO",
        r"PEDIDO\s*N[º°o]?",
        r"N[ÚU]MER[O0]\s*D[OE]\s*PEDIDO",
        r"N[ÚU]MER[O0]\s*DA\s*NF",
        r"N[ÚU]MER[O0]\s*DA\s*NOTA",
        r"N[ÚU]MER[O0]\s*D[OA]\s*N[O0]TA",
        r"NOTA\s+FISCAL\s*N[º°o]?",
        r"NF\s*N[º°o]?",
        r"PEDIDO",
    )
)

ANCORAS_NOME = tuple(
    _c(p)
    for p in (
        r"RAZ[AÃ]O\s+SOCIAL",
        r"NOME\s+EMPRESARIAL",
        r"NOME\s*/?\s*RAZ[AÃ]O",
        r"EMITENTE",
        r"FORNECEDOR",
        r"PRESTADOR",
        r"VENDEDOR",
    )
)

ANCORAS_DESCONTO = tuple(_c(p) for p in (r"VALOR\s+DO\s+DESCONTO", r"DESCONTO"))
ANCORAS_FRETE = tuple(_c(p) for p in (r"VALOR\s+DO\s+FRETE", r"FRETE"))
ANCORAS_PAGAMENTO = tuple(
    _c(p)
    for p in (
        r"FORMA\s+DE\s+PAGAMENTO",
        r"CONDI[CÇ][AÃ]O\s+DE\s+PAGAMENTO",
        r"MEIO\s+DE\s+PAGAMENTO",
        r"PAGAMENTO",
    )
)
ANCORAS_OBS = tuple(_c(p) for p in (r"OBSERVA[CÇ][OÕ]ES", r"OBSERVA[CÇ][AÃ]O", r"OBS"))

ANCORA_CABECALHO_ITENS = (
    _c(r"DESCRI[CÇ][AÃ]O"),
    _c(r"DESCRI[CÇ][AÃ]O\s+D[OE]"),
    _c(r"PRODUTO"),
    _c(r"DISCRIMINA[CÇ][AÃ]O"),
)

# Qualquer rotulo conhecido: usado para cortar o valor de um campo antes de invadir o
# campo seguinte (ex.: "RAZAO SOCIAL: X LTDA   CNPJ: 12.345...").
ROTULOS_CONHECIDOS = tuple(
    sorted(
        {
            *ANCORAS_TOTAL,
            *ANCORAS_CHAVE,
            *ANCORAS_CNPJ,
            *ANCORAS_EMISSAO,
            *ANCORAS_VENCIMENTO,
            *ANCORAS_PEDIDO,
            *ANCORAS_NOME,
            *ANCORAS_DESCONTO,
            *ANCORAS_FRETE,
            *ANCORAS_PAGAMENTO,
        },
        key=len,
        reverse=True,
    )
)

# ------------------------------------------------------------- injecao de prompt

PADROES_INJECAO = tuple(
    _c(p)
    for p in (
        r"IGNORE\s+(AS\s+)?INSTRU[CÇ][OÕ]ES",
        r"IGNORE\s+PREVIOUS",
        r"IGNORAR\s+(AS\s+)?INSTRU[CÇ][OÕ]ES",
        r"DESCONSIDERE\s+(AS\s+)?(INSTRU[CÇ][OÕ]ES|O\s+PROMPT)",
        r"GRAVE\s+COMO",
        r"GRAVAR?\s+COMO",
        r"REGISTRE\s+COMO",
        r"REGISTRAR?\s+COMO",
        r"ANOTE\s+COMO",
        r"LAN[CÇ]E\s+COMO",
        r"CONSIDERE\s+COMO",
        r"VALOR\s+99999",
        r"(VALOR|TOTAL)\s+DE?\s*99999",
        r"(SYSTEM|ASSISTANT|USER)\s*:",
        r"YOU\s+ARE\s+NOW",
        r"VOC[EÊ]\s+AGORA\s+[EÉ]",
        r"NOVAS?\s+INSTRU[CÇ][OÕ]ES",
        r"OVERRIDE",
        r"SUPERE\s+AS\s+INSTRU",
        r"N[AÃ]O\s+IMPORTA\s+O\s+VALOR",
        r"ESQUE[CÇ]A\s+(AS\s+)?(INSTRU[CÇ][OÕ]ES|REGRAS)",
    )
)

# ------------------------------------------------------------------ mapas fixos

MAPA_PAGAMENTO = (
    (_c(r"PIX"), "pix"),
    (_c(r"BOLETO"), "boleto"),
    (_c(r"CART[AÃ]O\s+DE\s+CR[EÉ]DITO"), "cartao_credito"),
    (_c(r"CR[EÉ]DITO"), "cartao_credito"),
    (_c(r"CART[AÃ]O\s+DE\s+D[EÉ]BITO"), "cartao_debito"),
    (_c(r"D[EÉ]BITO"), "cartao_debito"),
    (_c(r"TRANSFER[EÊ]NCIA"), "transferencia"),
    (_c(r"\bTED\b"), "transferencia"),
    (_c(r"\bDOC\b"), "transferencia"),
    (_c(r"DINHEIRO"), "dinheiro"),
    (_c(r"ESP[EÉ]CIE"), "dinheiro"),
    (_c(r"A\s+PRAZO"), "prazo"),
    (_c(r"PRAZO"), "prazo"),
    (_c(r"PARCELADO"), "prazo"),
    (_c(r"FATURADO"), "prazo"),
    (_c(r"30\s+DIAS"), "prazo"),
    (_c(r"28\s+DIAS"), "prazo"),
    (_c(r"15\s+DIAS"), "prazo"),
    (_c(r"CART[AÃ]O"), "outro"),
)

PALAVRAS_IGNORADAS_PEDIDO = {
    _c(p)
    for p in (
        "N", "NO", "NR", "NUM", "NUMERO", "DE", "DA", "DO", "DAS", "DOS", "EMITENTE",
        "FISCAL", "NOTA", "NF", "NFE", "INTERNO", "PEDIDO", "REF", "REFERENCIA",
        "ORDEM", "COMPRA", "COTACAO", "PROPOSTA",
    )
}
PALAVRAS_IGNORADAS_PEDIDO |= {"º", "°", "Nº", "N°"}


# --------------------------------------------------------------- resultado de busca


@dataclass
class _Achado:
    valor: Any
    trecho: str
    linha: int = -1
    ancora: str = ""
    ancora_forte: bool = True
    ambigua: bool = False


class _Leitura:
    """Texto preparado para extracao: linhas originais + linhas canonicas."""

    def __init__(self, texto: str, ocr: bool = False) -> None:
        self.texto = texto or ""
        self.orig = self.texto.splitlines()
        self.busca = [busca_ocr(l) for l in self.orig]
        self.ocr = ocr
        # Formato de moeda: se o documento usa a virgula decimal (BR), o ponto
        # decimal nao e aceito como dinheiro (evita ler "3.000" como valor).
        self.regex_moeda = RE_MOEDA_BR if RE_MOEDA_BR.search(busca_ocr(self.texto)) else RE_MOEDA_US

    # ---------------------------------------------------------------- helpers

    def base(self, ancora_forte: bool) -> float:
        if self.ocr:
            return BASE_ANCORA_OCR if ancora_forte else BASE_SEM_ANCORA_OCR
        return BASE_ANCORA_NATIVO if ancora_forte else BASE_SEM_ANCORA_NATIVO

    def proximo_rotulo(self, linha_busca: str, pos: int) -> int:
        fim = len(linha_busca)
        for rotulo in ROTULOS_CONHECIDOS:
            m = re.search(rotulo, linha_busca[pos:])
            if m:
                fim = min(fim, pos + m.start())
        return fim

    def segmento(self, linha_busca: str, linha_orig: str, pos: int) -> str:
        """Texto entre o rotulo e o proximo rotulo conhecido (evita invadir o vizinho)."""
        fim = self.proximo_rotulo(linha_busca, pos)
        return _trecho(linha_orig, pos, fim).strip(" :\t-|")


def _moedas(leitura: _Leitura, linha_busca: str) -> list[re.Match]:
    """Tokens de dinheiro da linha.

    Um match seguido de digito nao e dinheiro: "50,0000" e quantidade (o regex casou
    apenas "50,00"). Sem esse corte, quantidade viraria valor unitario.
    """
    tokens = []
    for m in leitura.regex_moeda.finditer(linha_busca):
        if m.end() < len(linha_busca) and linha_busca[m.end()].isdigit():
            continue
        tokens.append(m)
    return tokens


def _normalizar_moeda(canonico: str, literal: str) -> Optional[int]:
    """Tenta o literal (texto real) e, se falhar, a forma canonica (OCR recuperado)."""
    for candidato in (literal, canonico):
        if not candidato:
            continue
        valor = normalizar_moeda_centavos(candidato)
        if valor is not None:
            return valor
    return None


def _normalizar_data_segura(canonico: str, literal: str) -> tuple[Optional[str], bool]:
    for candidato in (literal, canonico):
        if not candidato:
            continue
        iso, ambigua = normalizar_data(candidato)
        if iso:
            return iso, bool(ambigua)
    return None, False


def _normalizar_quantidade_segura(canonico: str, literal: str) -> Optional[Decimal]:
    for candidato in (literal, canonico):
        if not candidato:
            continue
        valor = normalizar_quantidade(candidato)
        if valor is not None:
            return valor
    return None


# Recuperacao do texto alfabetico degradado por OCR (mesmas confusoes declaradas:
# 0/O, 1/l/I, 5/S, 2/Z). Vale so onde o valor e texto descritivo (nome, descricao de
# item); a evidencia guarda o trecho LITERAL, sem recuperacao.
_TABELA_OCR_INVERSA = str.maketrans({"0": "O", "1": "I", "5": "S", "2": "Z"})
RE_PALAVRA = re.compile(r"[A-Za-z0-9][A-Za-z0-9./-]*")


def recuperar_texto_ocr(trecho: str) -> str:
    """Recupera palavras com troca de caracteres declarada no contrato 4.3.

    - palavra com letras e digitos misturados e 3+ letras: 0->O, 1->I, 5->S, 2->Z;
    - `l` minusculo em palavra de 3+ letras: -> I.
    Palavra predominantemente numerica ("26A", "5/16", "A4") fica intacta - recuperar
    ai seria inventar conteudo.
    """
    if not trecho:
        return trecho

    def _palavra(m: re.Match) -> str:
        palavra = m.group(0)
        letras = sum(1 for c in palavra if c.isalpha())
        digitos = sum(1 for c in palavra if c.isdigit())
        if digitos and letras >= 3:
            palavra = palavra.translate(_TABELA_OCR_INVERSA)
        if letras >= 3 and "l" in palavra:
            palavra = palavra.replace("l", "I")
        return palavra

    return RE_PALAVRA.sub(_palavra, trecho)


# ------------------------------------------------------------------- extratores


def _extrator_moeda(leitura: _Leitura, linha_busca: str, linha_orig: str, pos: int) -> Optional[tuple[int, str]]:
    achados = _moedas(leitura, linha_busca)
    if not achados:
        return None
    escolhido = None
    for achado in achados:
        if achado.start() >= pos:
            escolhido = achado
            break
    if escolhido is None:
        escolhido = achados[-1]
    canonico = linha_busca[escolhido.start():escolhido.end()]
    literal = _trecho(linha_orig, escolhido.start(), escolhido.end())
    valor = _normalizar_moeda(canonico, literal)
    if valor is None:
        return None
    return valor, literal


def _extrator_data(leitura: _Leitura, linha_busca: str, linha_orig: str, pos: int) -> Optional[tuple[str, bool, str]]:
    achados = list(RE_DATA.finditer(linha_busca))
    if not achados:
        return None
    escolhido = None
    for achado in achados:
        if achado.start() >= pos:
            escolhido = achado
            break
    if escolhido is None:
        escolhido = achados[-1]
    canonico = linha_busca[escolhido.start():escolhido.end()]
    literal = _trecho(linha_orig, escolhido.start(), escolhido.end())
    iso, ambigua = _normalizar_data_segura(canonico, literal)
    if not iso:
        return None
    return iso, ambigua, literal


def _extrator_texto_livre(leitura: _Leitura, linha_busca: str, linha_orig: str, pos: int) -> Optional[tuple[str, str]]:
    texto = leitura.segmento(linha_busca, linha_orig, pos)
    if len(texto) < 2 or not any(ch.isalnum() for ch in texto):
        return None
    return texto[:200], texto


def _extrator_pedido(leitura: _Leitura, linha_busca: str, linha_orig: str, pos: int) -> Optional[tuple[str, str]]:
    for achado in RE_PEDIDO_TOKEN.finditer(linha_busca, pos):
        bruto = achado.group(0)
        puro = bruto.strip("._/-")
        if not puro or not any(ch.isdigit() for ch in puro):
            continue
        if puro in PALAVRAS_IGNORADAS_PEDIDO or puro.strip(".") in PALAVRAS_IGNORADAS_PEDIDO:
            continue
        if puro.upper() in {r.upper() for r in ROTULOS_CONHECIDOS}:
            continue
        return puro, _trecho(linha_orig, achado.start(), achado.end())
    return None


def _eh_rotulo(linha_busca: str, m: re.Match) -> bool:
    """Rotulo de verdade: inicio da linha ou seguido de dois-pontos.

    Evita que a palavra "fornecedor" no meio de uma frase ("pedimos a segunda via ao
    fornecedor.") seja lida como rotulo de razao social.
    """
    antes = linha_busca[: m.start()].strip(" \t|-")
    depois = linha_busca[m.end():].lstrip(" \t")
    return not antes or depois.startswith(":")


def _buscar(
    leitura: _Leitura,
    ancoras: tuple[str, ...],
    extrator: Callable[..., Optional[Any]],
    linhas_frente: int = 2,
    ancoras_fortes: int = 1,
    exigir_rotulo: bool = False,
) -> Optional[_Achado]:
    """Procura o valor ancorado: mesma linha (depois do rotulo), senao linha seguinte.

    Duas passadas: primeiro o valor na MESMA linha do rotulo (todas as ancoras, todas as
    linhas); so depois a linha de baixo de um rotulo que termina a linha. Assim um
    cabecalho de tabela ("... V.TOTAL") nao rouba o valor da linha do total nem define
    o fim da regiao de itens.
    """
    for passada in (0, 1):
        for pos_ancora, ancora in enumerate(ancoras):
            for idx, linha_busca in enumerate(leitura.busca):
                for m in re.finditer(ancora, linha_busca):
                    if exigir_rotulo and not _eh_rotulo(linha_busca, m):
                        continue
                    forte = pos_ancora < ancoras_fortes
                    if passada == 0:
                        resultado = extrator(leitura, linha_busca, leitura.orig[idx], m.end())
                        if resultado is None:
                            continue
                        linha = idx
                    else:
                        # Rotulo no fim da linha ("VALOR TOTAL DA NOTA" na linha de cima).
                        if linha_busca[m.end():].strip(" :\t-|"):
                            continue
                        resultado = None
                        linha = idx
                        for j in range(idx + 1, min(idx + 1 + linhas_frente, len(leitura.busca))):
                            if not leitura.busca[j].strip():
                                continue
                            resultado = extrator(leitura, leitura.busca[j], leitura.orig[j], 0)
                            linha = j
                            if resultado is not None:
                                break
                            # Primeira linha util ja tentada e sem valor: nao insiste.
                            break
                        if resultado is None:
                            continue
                    return _Achado(
                        valor=resultado[0],
                        trecho=resultado[-1],
                        linha=linha,
                        ancora=ancora,
                        ancora_forte=forte,
                        ambigua=bool(len(resultado) == 3 and isinstance(resultado[1], bool) and resultado[1]),
                    )
    return None


def _extrair_chave(leitura: _Leitura) -> Optional[_Achado]:
    for ancora in ANCORAS_CHAVE:
        for idx, linha_busca in enumerate(leitura.busca):
            m = re.search(ancora, linha_busca)
            if not m:
                continue
            fim = leitura.proximo_rotulo(linha_busca, m.end())
            segmento = linha_busca[m.end():fim]
            digitos = re.sub(r"\D", "", segmento)
            j = idx
            while len(digitos) < 44 and j + 1 < len(leitura.busca):
                j += 1
                proxima = leitura.busca[j]
                if not proxima.strip():
                    continue
                corte = leitura.proximo_rotulo(proxima, 0)
                digitos += re.sub(r"\D", "", proxima[:corte])
                if corte < len(proxima):
                    break
            if len(digitos) >= 44:
                chave = digitos[:44]
                return _Achado(
                    valor=chave,
                    trecho=leitura.orig[idx].strip(),
                    linha=idx,
                    ancora=ancora,
                    ancora_forte=True,
                )
    return None


def _extrair_cnpj(leitura: _Leitura) -> Optional[_Achado]:
    """Primeiro CNPJ do documento, com o bloco de emitente tendo prioridade.

    Em DANFE o emitente vem antes do destinatario/remetente; quando existe a marcacao
    `DESTINATARIO`, os CNPJ que aparecem depois dela sao descartados.
    """
    candidatos: list[tuple[int, int, str, str]] = []  # (indice_linha, pos, cnpj, trecho)
    indice_destinatario = None
    for idx, linha_busca in enumerate(leitura.busca):
        if _c(r"DESTINAT[AÁ]RIO") in linha_busca or _c(r"REMETENTE") in linha_busca:
            if indice_destinatario is None:
                indice_destinatario = idx
        for ancora in ANCORAS_CNPJ:
            for m in re.finditer(ancora, linha_busca):
                fim = leitura.proximo_rotulo(linha_busca, m.end())
                segmento_busca = linha_busca[m.end():fim]
                segmento_orig = leitura.orig[idx][m.end():fim]
                for token in re.finditer(r"\d[\d./-]{12,19}\d", segmento_busca):
                    bruto_orig = segmento_orig[token.start():token.end()].strip()
                    # Em leitura por OCR a forma canonica tem os digitos recuperados
                    # (l->1, O->0); o literal degradado pode perder digitos. Vale o
                    # candidato de DV valido; sem nenhum, o primeiro legivel.
                    opcoes = (token.group(0), bruto_orig) if leitura.ocr else (bruto_orig, token.group(0))
                    escolhido = None
                    primeiro = None
                    for opcao in opcoes:
                        if not opcao:
                            continue
                        cnpj14, dv_ok = normalizar_cnpj(opcao)
                        if cnpj14 is None:
                            continue
                        if primeiro is None:
                            primeiro = (cnpj14, opcao)
                        if dv_ok:
                            escolhido = (cnpj14, opcao)
                            break
                    if escolhido is None:
                        escolhido = primeiro
                    if escolhido is None:
                        continue
                    cnpj14, bruto = escolhido
                    candidatos.append((idx, m.start(), cnpj14, bruto))

    if not candidatos:
        return None

    if indice_destinatario is not None:
        antes = [c for c in candidatos if c[0] <= indice_destinatario]
        if antes:
            candidatos = antes

    # Preferencia explicita: linha que fala do emitente.
    marcadores = (_c(r"EMITENTE"), _c(r"PRESTADOR"), _c(r"FORNECEDOR"), _c(r"VENDEDOR"))
    for idx, pos, cnpj14, bruto in candidatos:
        linha = leitura.busca[idx]
        if any(marca in linha for marca in marcadores):
            return _Achado(valor=cnpj14, trecho=bruto, linha=idx, ancora="CNPJ", ancora_forte=True)

    idx, pos, cnpj14, bruto = candidatos[0]
    return _Achado(valor=cnpj14, trecho=bruto, linha=idx, ancora="CNPJ", ancora_forte=True)


def _extrair_nome(leitura: _Leitura, achado_cnpj: Optional[_Achado]) -> Optional[_Achado]:
    achado = _buscar(
        leitura,
        ANCORAS_NOME,
        _extrator_texto_livre,
        linhas_frente=1,
        ancoras_fortes=len(ANCORAS_NOME),
        exigir_rotulo=True,
    )
    if achado is not None:
        nome = str(achado.valor).strip().rstrip(".,;")
        if len(nome) >= 3 and any(ch.isalpha() for ch in nome):
            achado.valor = nome
            return achado

    # Sem rotulo de razao social: no DANFE o nome fica na linha imediatamente acima do
    # CNPJ do emitente. E leitura de posicao, nao inferencia de conteudo.
    if achado_cnpj is not None and achado_cnpj.linha > 0:
        for j in range(achado_cnpj.linha - 1, max(-1, achado_cnpj.linha - 3), -1):
            candidato = leitura.orig[j].strip()
            if not candidato:
                continue
            if any(re.search(rot, leitura.busca[j]) for rot in ROTULOS_CONHECIDOS):
                continue
            if len(candidato) < 3 or not any(ch.isalpha() for ch in candidato):
                continue
            return _Achado(
                valor=candidato[:200],
                trecho=candidato,
                linha=j,
                ancora="linha acima do CNPJ",
                ancora_forte=False,
            )
    return None


def _data_unica_sem_ancora(leitura: _Leitura) -> Optional[_Achado]:
    """Data sem rotulo, so em texto livre de mensagem, e so quando ela e inequivoca.

    Mensagem real escreve "fechado com a Gama em 20/03/2026" sem rotulo nenhum. Se
    existir **uma unica** data distinta no texto, ela e o fato lido (evidencia literal,
    ancora fraca); havendo duas ou mais, nao se escolhe nenhuma - escolher seria chute.
    """
    achados: dict[str, tuple[str, str]] = {}
    for idx, linha_busca in enumerate(leitura.busca):
        for m in RE_DATA.finditer(linha_busca):
            canonico = linha_busca[m.start():m.end()]
            literal = _trecho(leitura.orig[idx], m.start(), m.end())
            iso, _ambigua = _normalizar_data_segura(canonico, literal)
            if iso and iso not in achados:
                achados[iso] = (literal, str(idx))
    if len(achados) != 1:
        return None
    iso, (literal, idx_linha) = next(iter(achados.items()))
    return _Achado(
        valor=iso,
        trecho=literal,
        linha=int(idx_linha),
        ancora="data unica do texto",
        ancora_forte=False,
    )


def _extrair_forma_pagamento(leitura: _Leitura) -> Optional[_Achado]:
    achado = _buscar(leitura, ANCORAS_PAGAMENTO, _extrator_texto_livre, linhas_frente=1, ancoras_fortes=len(ANCORAS_PAGAMENTO))
    if achado is None:
        return None
    bruto = str(achado.valor)
    canonico = busca_ocr(bruto)
    for padrao, forma in MAPA_PAGAMENTO:
        if re.search(padrao, canonico):
            achado.valor = forma
            return achado
    achado.valor = "outro"
    return achado


# ------------------------------------------------------------------ itens


def _localizar_cabecalho_itens(leitura: _Leitura, limite: int) -> Optional[int]:
    """Ultima linha de cabecalho de tabela de itens antes do total."""
    encontrado = None
    fim = limite if limite >= 0 else len(leitura.busca)
    colunas = (_c("QTD"), _c("QUANT"), _c("UNIT"), _c("VLR"), _c("VALOR"), _c("UN"))
    for idx in range(min(fim, len(leitura.busca))):
        linha = leitura.busca[idx]
        tem_descricao = any(chave in linha for chave in ANCORA_CABECALHO_ITENS)
        tem_coluna = any(termo in linha for termo in colunas)
        if tem_descricao and tem_coluna:
            encontrado = idx
    return encontrado


def _linha_encerra_itens(linha_busca: str) -> bool:
    if any(re.search(ancora, linha_busca) for ancora in ANCORAS_TOTAL[:4]):
        return True
    return any(
        re.search(_c(p), linha_busca)
        for p in (r"OBSERVA[CÇ]", r"INFORMA[CÇ][OÕ]ES\s+COMPLEMENTARES", r"TRANSPORTE", r"ICMS", r"FRETE")
    )


def _partir_descricao(
    leitura: _Leitura, linha_busca: str, linha_orig: str, corte: int
) -> tuple[str, Optional[Decimal], Optional[str]]:
    """Separa descricao / quantidade / unidade do prefixo da linha do item.

    Quantidade so e aceita quando vem com unidade explicita ou separada por 2+ espacos
    do texto: sem isso, um digito que faz parte da descricao ("PARAFUSO 3/8") viraria
    quantidade por engano.
    """
    prefixo_busca = linha_busca[:corte].rstrip()
    prefixo_orig = linha_orig[:corte].rstrip()

    quantidade: Optional[Decimal] = None
    unidade: Optional[str] = None
    descricao = prefixo_orig

    m_qtd = RE_QTD_UN.search(prefixo_busca)
    if m_qtd is not None:
        antes = prefixo_busca[: m_qtd.start()]
        separado = m_qtd.start() == 0 or antes.endswith("  ") or antes.endswith("\t")
        if m_qtd.group("un") or separado:
            quantidade = _normalizar_quantidade_segura(
                m_qtd.group("qtd"),
                _trecho(prefixo_orig, m_qtd.start("qtd"), m_qtd.end("qtd")) or m_qtd.group("qtd"),
            )
            if m_qtd.group("un"):
                # A unidade e lida do texto ORIGINAL: na forma canonica "RS" fica "R5".
                unidade = (
                    _trecho(prefixo_orig, m_qtd.start("un"), m_qtd.end("un")) or m_qtd.group("un")
                ).upper()
            descricao = prefixo_orig[: m_qtd.start()].rstrip()

    descricao = RE_SEQUENCIA.sub("", descricao, count=1).strip(" |\t")
    return descricao, quantidade, unidade


def _parse_item_linha(leitura: _Leitura, idx: int) -> Optional[Item]:
    linha_busca = leitura.busca[idx]
    linha_orig = leitura.orig[idx]
    if not linha_busca.strip():
        return None

    achados = _moedas(leitura, linha_busca)
    tem_sequencia = bool(RE_SEQUENCIA.match(linha_busca))

    if len(achados) == 1:
        # "3 SERVICO X 1,00 UN": numero seguido so de unidade no fim da linha e
        # quantidade, nao dinheiro.
        sobra = linha_busca[achados[0].end():].strip(" \t|")
        if sobra and re.fullmatch(r"[A-Z0-9]{1,6}", sobra):
            achados = []

    if not achados:
        # Caso B6: item listado sem valor nenhum. Nao inventa valor: le o que existe.
        if not tem_sequencia:
            return None
        descricao, quantidade, unidade = _partir_descricao(leitura, linha_busca, linha_orig, len(linha_busca))
        if len(descricao) < 3:
            return None
        if leitura.ocr:
            descricao = recuperar_texto_ocr(descricao)
        return Item(
            descricao=descricao[:200],
            quantidade=quantidade,
            unidade=unidade,
            valor_unitario_centavos=None,
            valor_total_centavos=None,
            confianca=round(
                leitura.base(True) * CK_INCONCLUSIVO * COERENCIA_OK * CONSENSO_EVIDENCIA, 4
            ),
        )

    if len(achados) >= 2:
        token_unit, token_total = achados[-2], achados[-1]
    else:
        token_unit, token_total = None, achados[-1]

    valor_total = _normalizar_moeda(
        linha_busca[token_total.start():token_total.end()],
        _trecho(linha_orig, token_total.start(), token_total.end()),
    )
    valor_unit = None
    if token_unit is not None:
        valor_unit = _normalizar_moeda(
            linha_busca[token_unit.start():token_unit.end()],
            _trecho(linha_orig, token_unit.start(), token_unit.end()),
        )

    corte = token_unit.start() if token_unit is not None else token_total.start()
    descricao, quantidade, unidade = _partir_descricao(leitura, linha_busca, linha_orig, corte)
    if len(descricao) < 2:
        return None
    if leitura.ocr:
        descricao = recuperar_texto_ocr(descricao)

    linha_completa = quantidade is not None and valor_unit is not None
    checksum = CK_OK if linha_completa else CK_INCONCLUSIVO
    confianca = leitura.base(True) * checksum * COERENCIA_OK * CONSENSO_EVIDENCIA

    return Item(
        descricao=descricao[:200],
        quantidade=quantidade,
        unidade=unidade,
        valor_unitario_centavos=valor_unit,
        valor_total_centavos=valor_total,
        confianca=round(confianca, 4),
    )


def _extrair_itens(leitura: _Leitura, indice_total: int) -> list[Item]:
    indice_cabecalho = _localizar_cabecalho_itens(leitura, indice_total)
    inicio = 0 if indice_cabecalho is None else indice_cabecalho + 1
    fim = indice_total if indice_total >= 0 else len(leitura.busca)

    itens: list[Item] = []
    for idx in range(inicio, min(fim, len(leitura.busca))):
        if _linha_encerra_itens(leitura.busca[idx]):
            break
        item = _parse_item_linha(leitura, idx)
        if item is not None:
            itens.append(item)
    return itens


# ------------------------------------------------------------------ injecao


def detectar_injecao(texto: str) -> list[tuple[str, str]]:
    """Trechos com instrucao suspeita. O texto e DADO: nunca e obedecido."""
    achados: list[tuple[str, str]] = []
    for linha in (texto or "").splitlines():
        canonica = busca_ocr(linha)
        for padrao in PADROES_INJECAO:
            if re.search(padrao, canonica):
                achados.append((linha.strip()[:300], padrao))
                break
    return achados


# --------------------------------------------------------------- classificar


def classificar(texto: str) -> str:
    """'nf' (DANFE/NF-e) | 'pedido' | 'desconhecido'. Sem LLM, sem adivinhacao."""
    canonica = busca_ocr(texto or "")
    if not canonica.strip():
        return TIPO_DESCONHECIDO

    fortes_nf = (
        _c(r"DANFE"),
        _c(r"NOTA\s+FISCAL"),
        _c(r"N[O0]TA\s+FISCAL\s+ELETR[OÔ]NICA"),
        _c(r"CHAVE\s+DE\s+ACESSO"),
        _c(r"VALOR\s+TOTAL\s+DA\s+NOTA"),
        _c(r"NF-?E\b"),
    )
    if any(re.search(p, canonica) for p in fortes_nf):
        return TIPO_NF

    fracos_nf = (
        _c(r"CNPJ"),
        _c(r"INSCRI[CÇ][AÃ]O\s+ESTADUAL"),
        _c(r"DESTINAT[AÁ]RIO"),
        _c(r"ICMS"),
        _c(r"BASE\s+DE\s+C[AÁ]LCULO"),
        _c(r"NATUREZA\s+DA\s+OPERA[CÇ][AÃ]O"),
    )
    marcadores_pedido = (
        _c(r"PEDIDO"),
        _c(r"ORDEM\s+DE\s+COMPRA"),
        _c(r"OR[CÇ]AMENTO"),
        _c(r"COTA[CÇ][AÃ]O"),
        _c(r"PR[O0]POSTA"),
    )
    pontos_nf = sum(1 for p in fracos_nf if re.search(p, canonica))
    if pontos_nf >= 2:
        return TIPO_NF
    if any(re.search(p, canonica) for p in marcadores_pedido):
        return TIPO_PEDIDO
    return TIPO_DESCONHECIDO


# --------------------------------------------------------------- score


def _score(leitura: _Leitura, ancora_forte: bool, checksum: float, coerencia: float, consenso: float) -> float:
    valor = leitura.base(ancora_forte) * checksum * coerencia * consenso
    return round(min(1.0, max(0.0, valor)), 4)


def _confianca_geral(confianca_por_campo: dict, presentes: set[str]) -> float:
    soma = 0.0
    peso_total = 0
    for campo, conf in confianca_por_campo.items():
        if campo not in presentes:
            continue
        peso = PESO_CAMPO.get(campo, PESO_PADRAO)
        soma += conf * peso
        peso_total += peso
    if peso_total == 0:
        return 0.0
    return round(soma / peso_total, 4)


def _modo_ocr(arquivo: Optional[str]) -> tuple[bool, float]:
    if not arquivo:
        return False, 1.0
    sidecar = caminho_sidecar_ocr(arquivo)
    if sidecar.is_file():
        texto = sidecar.read_text(encoding="utf-8", errors="replace")
        return True, confianca_ocr_simulado(texto)
    return False, 1.0


def _documento_id_provisorio(texto: str, arquivo: Optional[str]) -> str:
    """Id local deterministico; o pipeline troca pelo id do banco (`registrar_documento`)."""
    if arquivo:
        caminho = Path(arquivo)
        if caminho.is_file():
            return "doc_" + sha256_arquivo(caminho)[:16]
    return "doc_" + sha256_bytes((texto or "").encode("utf-8"))[:16]


# --------------------------------------------------------------- extracao


def extrair(texto: str, origem_canal: str, arquivo: Optional[str] = None) -> Extracao:
    """Extrator deterministico por rotulo/ancora (DANFE/NF e pedido, PDF ou mensagem)."""
    texto = texto or ""
    ocr, _conf_leitura = _modo_ocr(arquivo)
    leitura = _Leitura(texto, ocr=ocr)

    extracao = Extracao(
        documento_id=_documento_id_provisorio(texto, arquivo),
        origem_canal=origem_canal,
        tipo_documento=classificar(texto),
        arquivo_origem=arquivo,
        motor="parser",
        ocr_usado=ocr,
        template_versao=TEMPLATE_VERSAO,
    )

    evidencia: dict[str, str] = {}
    confianca: dict[str, float] = {}
    presentes: set[str] = set()

    total = _buscar(leitura, ANCORAS_TOTAL, _extrator_moeda, ancoras_fortes=len(ANCORAS_TOTAL))
    indice_total = total.linha if total is not None else -1

    # --- valor total
    if total is not None:
        extracao.valor_total_centavos = int(total.valor)
        evidencia["valor_total"] = total.trecho
        presentes.add("valor_total")

    # --- itens (precisam do total para a reconciliacao de confianca)
    itens = _extrair_itens(leitura, indice_total)
    if itens:
        extracao.itens = itens
        presentes.add("itens")

    if total is not None:
        from .contratos import TOLERANCIA_ITENS_CASA_CENTAVOS

        diferenca = extracao.diferenca_itens_centavos()
        if diferenca is not None and diferenca <= TOLERANCIA_ITENS_CASA_CENTAVOS:
            checksum_total = CK_OK
            consenso_total = CONSENSO_CORROBORADO  # aritmetica dos itens confirma
        elif diferenca is None:
            checksum_total = CK_INCONCLUSIVO  # sem itens: nao confirma nem reprova
            consenso_total = CONSENSO_EVIDENCIA
        else:
            # Divergencia aritmetica e decidida por `persistencia.decidir()` (contrato 5):
            # aqui o valor lido continua sendo o lido, com confianca de leitura menor.
            checksum_total = CK_INCONCLUSIVO
            consenso_total = CONSENSO_EVIDENCIA
        confianca["valor_total"] = _score(leitura, total.ancora_forte, checksum_total, COERENCIA_OK, consenso_total)

    # --- chave de acesso
    chave = _extrair_chave(leitura)
    if chave is not None:
        extracao.chave_acesso_nf = chave.valor
        evidencia["chave_acesso_nf"] = chave.trecho
        presentes.add("chave_acesso_nf")
        dv_ok = validar_chave_nf_dv(chave.valor)
        confianca["chave_acesso_nf"] = _score(
            leitura, True, CK_OK if dv_ok else CK_FALHOU, COERENCIA_OK,
            CONSENSO_CORROBORADO if dv_ok else CONSENSO_EVIDENCIA,
        )

    # --- CNPJ do emitente
    cnpj = _extrair_cnpj(leitura)
    if cnpj is not None:
        extracao.emitente_cnpj = cnpj.valor
        evidencia["emitente_cnpj"] = cnpj.trecho
        presentes.add("emitente_cnpj")
        _cnpj14, dv_valido = normalizar_cnpj(cnpj.valor)
        confianca["emitente_cnpj"] = _score(
            leitura, True, CK_OK if dv_valido else CK_FALHOU, COERENCIA_OK,
            CONSENSO_CORROBORADO if dv_valido else CONSENSO_EVIDENCIA,
        )

    # --- nome do emitente
    nome = _extrair_nome(leitura, cnpj)
    if nome is not None:
        texto_nome = str(nome.valor)
        if leitura.ocr:
            texto_nome = recuperar_texto_ocr(texto_nome)
        extracao.emitente_nome = texto_nome
        evidencia["emitente_nome"] = nome.trecho
        presentes.add("emitente_nome")
        confianca["emitente_nome"] = _score(leitura, nome.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_EVIDENCIA)

    # --- numero do pedido
    pedido = _buscar(leitura, ANCORAS_PEDIDO, _extrator_pedido, linhas_frente=1, ancoras_fortes=len(ANCORAS_PEDIDO) - 1)
    if pedido is not None:
        extracao.numero_pedido = str(pedido.valor)
        evidencia["numero_pedido"] = pedido.trecho
        presentes.add("numero_pedido")
        confianca["numero_pedido"] = _score(leitura, pedido.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_EVIDENCIA)

    # --- data de emissao
    emissao = _buscar(leitura, ANCORAS_EMISSAO, _extrator_data, linhas_frente=1, ancoras_fortes=len(ANCORAS_EMISSAO))
    if emissao is None and origem_canal in (CANAL_WHATSAPP, CANAL_TELEGRAM):
        emissao = _data_unica_sem_ancora(leitura)
    if emissao is not None:
        extracao.data_emissao = emissao.valor
        evidencia["data_emissao"] = emissao.trecho
        if emissao.ambigua:
            # Doc 02 4.3: dia <= 12 e sem outro indicador -> pode ser mm/dd. Nao bloqueia
            # sozinho: reduz a confianca da data e fica registrado na evidencia.
            evidencia["data_emissao_ambigua"] = emissao.trecho
        presentes.add("data_emissao")
        confianca["data_emissao"] = _score(
            leitura,
            emissao.ancora_forte,
            CK_OK,
            COERENCIA_OUTLIER if emissao.ambigua else COERENCIA_OK,
            CONSENSO_CORROBORADO,
        )

    # --- vencimento
    vencimento = _buscar(leitura, ANCORAS_VENCIMENTO, _extrator_data, linhas_frente=1, ancoras_fortes=2)
    if vencimento is not None:
        extracao.data_vencimento = vencimento.valor
        evidencia["data_vencimento"] = vencimento.trecho
        presentes.add("data_vencimento")
        confianca["data_vencimento"] = _score(
            leitura, vencimento.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_CORROBORADO
        )

    # --- desconto / frete
    desconto = _buscar(leitura, ANCORAS_DESCONTO, _extrator_moeda, linhas_frente=1, ancoras_fortes=2)
    if desconto is not None:
        extracao.desconto_centavos = int(desconto.valor)
        evidencia["desconto_centavos"] = desconto.trecho
        presentes.add("desconto_centavos")
        confianca["desconto_centavos"] = _score(
            leitura, desconto.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_EVIDENCIA
        )

    frete = _buscar(leitura, ANCORAS_FRETE, _extrator_moeda, linhas_frente=1, ancoras_fortes=2)
    if frete is not None:
        extracao.frete_centavos = int(frete.valor)
        evidencia["frete_centavos"] = frete.trecho
        presentes.add("frete_centavos")
        confianca["frete_centavos"] = _score(
            leitura, frete.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_EVIDENCIA
        )

    # --- forma de pagamento
    pagamento = _extrair_forma_pagamento(leitura)
    if pagamento is not None:
        extracao.forma_pagamento = str(pagamento.valor)
        extracao.forma_pagamento_raw = pagamento.trecho
        evidencia["forma_pagamento"] = pagamento.trecho
        presentes.add("forma_pagamento")
        confianca["forma_pagamento"] = _score(
            leitura, pagamento.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_EVIDENCIA
        )

    # --- observacoes
    obs = _buscar(
        leitura, ANCORAS_OBS, _extrator_texto_livre, linhas_frente=1, ancoras_fortes=4
    )
    if obs is not None and len(str(obs.valor)) >= 4:
        extracao.observacoes = str(obs.valor)
        evidencia["observacoes"] = obs.trecho
        presentes.add("observacoes")
        confianca["observacoes"] = _score(
            leitura, obs.ancora_forte, CK_OK, COERENCIA_OK, CONSENSO_EVIDENCIA
        )

    # --- itens: confianca media entra como campo de peso 1
    if itens:
        confianca["itens"] = round(sum(it.confianca for it in itens) / len(itens), 4)

    # --- injecao de prompt (registra, nunca obedece)
    suspeitas = detectar_injecao(texto)
    if suspeitas:
        if MOTIVO_INJECAO_SUSPEITA not in extracao.motivos:
            extracao.motivos.append(MOTIVO_INJECAO_SUSPEITA)
        evidencia["injecao_suspeita"] = suspeitas[0][0]

    extracao.evidencia = evidencia
    extracao.confianca_por_campo = confianca
    extracao.confianca_geral = _confianca_geral(confianca, presentes)
    return extracao


def extrair_mensagem(msg: MensagemBruta) -> Extracao:
    """Mesmos campos, agora a partir do texto livre da mensagem (WhatsApp/Telegram)."""
    extracao = extrair(msg.texto or "", msg.canal, msg.arquivo_origem)
    extracao.documento_id = "doc_" + hash_mensagem(msg)[:16]
    extracao.hash_conteudo = hash_mensagem(msg)
    extracao.origem_remetente = msg.remetente_nome or msg.remetente_id or None
    extracao.recebido_em = msg.enviada_em
    extracao.arquivo_origem = msg.arquivo_origem
    return extracao


__all__ = [
    "classificar",
    "extrair",
    "extrair_mensagem",
    "detectar_injecao",
    "PESO_CAMPO",
]
