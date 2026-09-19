"""Normalizacao deterministica de campos - frente F2 (dono: gula).

Funcoes **puras** (sem banco, sem rede, sem relogio, exceto quando o relogio vem
por parametro). Toda regra aqui deriva de `docs/02-dados-e-ia.md` secao 2 (campos,
tipos e normalizacao) e da secao 5 do `docs/execucao/00-contrato-execucao.md`
(assinaturas congeladas).

Regras de ouro (nao negociaveis):

1. **Dinheiro nunca em float.** Entrada bruta -> inteiro em centavos.
2. **Data sempre ISO** `YYYY-MM-DD` (str) ou `None`.
3. **Campo ausente e `None`.** Nunca `0`, nunca string vazia, nunca chute.
4. **DV invalido nunca e "consertado"** - CNPJ e chave de acesso retornam os
   digitos lidos junto com `dv_valido=False`, para que a excecao carregue o valor
   que estava no documento.

Convencoes numericas (documentadas porque geram duvida na revisao):

- Quando o token tem `.` **e** `,`, o separador **mais a direita** e o decimal
  (`1.234,56` -> virgula decimal = 1234,56; `1,234.56` -> ponto decimal = 1234,56).
  O segundo caso e o padrao americano, que a secao 2 do doc 02 manda **sinalizar**;
  use `classificar_formato_moeda()` para levantar a suspeita.
- Com **um unico** `.` e exatamente 3 digitos depois (`1.234`) ele e separador de
  milhar (convencao BR): 1234 reais. Com um unico `,` a virgula e o decimal
  (convencao BR): `1,234` = 1,234.
- `normalizar_quantidade("3,000")` = `Decimal("3")` e `normalizar_quantidade("3.000")`
  = `Decimal("3000")` - cada separador segue a convencao BR acima.

Ambiguidade de data (doc 02 secao 4.3): `ambigua=True` so e devolvido para formato
**numerico dia-primeiro** (`dd/mm/aaaa`, `dd/mm/aa`, `dd-mm-aaaa`) com dia `<= 12`,
porque so nesse caso a leitura `mm/dd` e plausivel. `aaaa-mm-dd` e `dd de <mes> de
aaaa` sao inequivocos (o mes esta escrito ou o ano vem primeiro) e devolvem
`ambigua=False` - doc 02 4.3: "dia <= 12 **e sem outro indicador**".
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

__all__ = [
    "limpar_espacos",
    "so_digitos",
    "validar_cnpj_dv",
    "normalizar_cnpj",
    "validar_chave_nf_dv",
    "normalizar_chave_nf",
    "normalizar_data",
    "normalizar_moeda_centavos",
    "classificar_formato_moeda",
    "normalizar_quantidade",
    "separar_quantidade_unidade",
    "normalizar_numero_pedido",
    "mapear_forma_pagamento",
    "data_plausivel",
    "detectar_injecao",
    "MESES_ABREVIADOS",
    "FORMATOS_MOEDA",
]

# --------------------------------------------------------------- utilidades de texto

_ESPACOS_ESPECIAIS = ("\u00a0", "\u202f", "\u2009", "\u2007", "\u200b", "\ufeff")


def limpar_espacos(bruto: Any) -> str:
    """Colapsa espacos (inclusive nao-quebravel/fino) e faz trim."""
    if bruto is None:
        return ""
    if isinstance(bruto, bool):
        return ""
    s = str(bruto)
    for ch in _ESPACOS_ESPECIAIS:
        s = s.replace(ch, " ")
    return re.sub(r"\s+", " ", s).strip()


def so_digitos(bruto: Any) -> str:
    """So os digitos do valor. `None`/lixo sem digito devolve string vazia."""
    if bruto is None or isinstance(bruto, bool):
        return ""
    if isinstance(bruto, (datetime, date)):
        return ""
    return "".join(c for c in str(bruto) if c.isdigit())


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


# --------------------------------------------------------------- CNPJ (mod 11 de verdade)

_PESOS_CNPJ_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_CNPJ_DV2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_RE_CNPJ_FORMATADO = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")


def _dv_mod11(digitos: str, pesos: tuple) -> int:
    """DV modulo 11: resto < 2 -> 0, senao 11 - resto."""
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj_dv(cnpj14: Any) -> bool:
    """True se os 14 digitos tem os dois DVs validos (mod 11).

    Aceita com ou sem pontuacao. Sequencia repetida (`00000000000000`) e invalida:
    ela passa no mod 11 mas nao existe como CNPJ.
    """
    digitos = so_digitos(cnpj14)
    if len(digitos) != 14:
        return False
    if len(set(digitos)) == 1:
        return False
    if _dv_mod11(digitos[:12], _PESOS_CNPJ_DV1) != int(digitos[12]):
        return False
    return _dv_mod11(digitos[:13], _PESOS_CNPJ_DV2) == int(digitos[13])


def normalizar_cnpj(bruto: Any) -> tuple[Optional[str], bool]:
    """`(cnpj14 | None, dv_valido)`.

    - Sem 14 digitos identificaveis -> `(None, False)` (nao inventa, nao completa).
    - Com 14 digitos -> devolve os digitos **como lidos** e o resultado do DV.
      DV invalido **nao** e corrigido: quem chama registra a excecao com o valor real.
    """
    if bruto is None or isinstance(bruto, bool):
        return (None, False)
    texto = limpar_espacos(bruto)
    if not texto:
        return (None, False)

    nucleo = re.sub(r"[.\-/\s]+", "", texto)
    if len(nucleo) == 14 and nucleo.isdigit():
        return (nucleo, validar_cnpj_dv(nucleo))

    # veio com rotulo/ruido em volta ("CNPJ: 12.345.678/0001-95"): aceita so quando
    # existe UM unico candidato no formato de CNPJ - dois candidatos e ambiguidade.
    candidatos = {re.sub(r"\D", "", m.group(0)) for m in _RE_CNPJ_FORMATADO.finditer(texto)}
    if len(candidatos) == 1:
        candidato = candidatos.pop()
        if len(candidato) == 14:
            return (candidato, validar_cnpj_dv(candidato))
    return (None, False)


# --------------------------------------------------------------- chave de acesso NF-e (44)

def validar_chave_nf_dv(chave44: Any) -> bool:
    """DV da chave de acesso da NF-e (44 digitos): pesos 2..9 da direita para a
    esquerda sobre os 43 primeiros; DV = 11 - resto, e 0 quando o resto e 0 ou 1.
    """
    digitos = so_digitos(chave44)
    if len(digitos) != 44:
        return False
    if len(set(digitos)) == 1:
        return False
    soma, peso = 0, 2
    for d in reversed(digitos[:43]):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    dv = 0 if resto in (0, 1) else 11 - resto
    return dv == int(digitos[43])


def normalizar_chave_nf(bruto: Any) -> tuple[Optional[str], bool]:
    """`(chave44 | None, dv_valido)` - analogo ao CNPJ, com o mesmo rigor."""
    digitos = so_digitos(bruto)
    if len(digitos) != 44:
        return (None, False)
    return (digitos, validar_chave_nf_dv(digitos))


# --------------------------------------------------------------- data -> ISO

MESES_ABREVIADOS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
    "dezembro": 12,
}
_RE_DATA_NUM = re.compile(r"^(\d{1,4})([/\-.])(\d{1,2})\2(\d{1,4})$")
_RE_DATA_EXTENSO = re.compile(r"^(\d{1,2})\s*(?:de|do|d)?\s*([^\W\d_]+)\s*(?:de|do|d)?\s*(\d{2,4})$")


def _ano(txt: str) -> Optional[int]:
    """Ano de 2 digitos segue a regra deterministica: < 70 -> 20xx, senao 19xx."""
    if not txt or not txt.isdigit():
        return None
    valor = int(txt)
    if len(txt) == 2:
        return 2000 + valor if valor < 70 else 1900 + valor
    if len(txt) == 4:
        return valor
    return None


def _numero_mes(nome: str) -> Optional[int]:
    chave = _sem_acento(nome).lower().strip(".")
    if chave in _MESES:
        return _MESES[chave]
    return MESES_ABREVIADOS.get(chave[:3])


def normalizar_data(bruto: Any) -> tuple[Optional[str], bool]:
    """`(YYYY-MM-DD | None, ambigua)`.

    Formatos aceitos: `dd/mm/aaaa`, `dd/mm/aa`, `aaaa-mm-dd` (e `aaaa/mm/dd`),
    `dd de <mes> de aaaa`, `dd-<mes>-aaaa`. Assume **dd/mm** no formato numerico
    dia-primeiro. Data inexistente (`31/02/2026`) -> `(None, False)`.
    """
    if bruto is None or isinstance(bruto, bool):
        return (None, False)
    if isinstance(bruto, datetime):
        return (bruto.date().isoformat(), False)
    if isinstance(bruto, date):
        return (bruto.isoformat(), False)

    texto = limpar_espacos(bruto)
    if not texto:
        return (None, False)

    ambigua = False
    ano: Optional[int]
    mes: Optional[int]
    dia: int

    m = _RE_DATA_NUM.match(texto)
    if m:
        g1, g2, g3 = m.group(1), m.group(3), m.group(4)
        if len(g1) == 4:                      # ano primeiro: inequivoco
            ano, mes, dia = int(g1), int(g2), int(g3)
        else:                                 # dd/mm[/aa|aaaa] (assume dia primeiro)
            ano = _ano(g3)
            if ano is None:
                return (None, False)
            dia, mes = int(g1), int(g2)
            ambigua = dia <= 12
    else:
        m = _RE_DATA_EXTENSO.match(texto)
        if not m:
            return (None, False)
        ano = _ano(m.group(3))
        mes = _numero_mes(m.group(2))
        dia = int(m.group(1))
        if ano is None or mes is None:
            return (None, False)

    if not 1900 <= ano <= 2199:
        return (None, False)
    try:
        return (date(ano, mes, dia).isoformat(), bool(ambigua))
    except ValueError:
        return (None, False)


def _parse_iso(iso: Any) -> Optional[date]:
    if isinstance(iso, datetime):
        return iso.date()
    if isinstance(iso, date):
        return iso
    if not iso:
        return None
    texto = str(iso).strip()[:10]
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _menos_meses(hoje: date, meses: int) -> date:
    indice = hoje.month - 1 - meses
    ano = hoje.year + indice // 12
    mes = indice % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(hoje.day, ultimo_dia))


def data_plausivel(iso: Any, referencia: Any = None) -> bool:
    """Janela plausivel do doc 02 4.1: ate 24 meses no passado, 30 dias no futuro.

    `referencia` (date/datetime/ISO) existe para teste deterministico; sem ela usa
    a data de hoje. Data invalida/ausente -> False.
    """
    alvo = _parse_iso(iso)
    if alvo is None:
        return False
    if referencia is None:
        hoje = date.today()
    else:
        hoje = _parse_iso(referencia) or date.today()
    return _menos_meses(hoje, 24) <= alvo <= hoje + timedelta(days=30)


# --------------------------------------------------------------- moeda BR -> centavos

FORMATOS_MOEDA = (
    "br_milhar",          # 1.234,56 / 1.234.567,89
    "us_milhar",          # 1,234.56 (levanta suspeita - doc 02 secao 2)
    "ambiguo_milhar",     # 1,234 (lido como BR decimal; pode ser milhar US)
    "br_decimal_virgula",  # 1,56
    "br_inteiro",         # 1234
    "invalido",
)

_CUR_SIMBOLO = re.compile(r"(?:R\$|BRL|REAIS|REAL|\$)", re.IGNORECASE)
_RE_TOKEN_NUMERICO = re.compile(r"([-+(]*)(\d[\d.,]*)([)\-]*)")


def _token_numerico(bruto: Any) -> Optional[str]:
    """Token numerico limpo (com sinal), ou None quando sobra letra/lixo.

    Lixo alfabetico adjacente e recusado de proposito: em dinheiro ler `None`
    e melhor do que inventar um valor (doc 02 secao 5.2, taxa_campo_inventado).
    """
    if bruto is None or isinstance(bruto, bool):
        return None
    if isinstance(bruto, (int, Decimal)):
        return str(bruto)
    if isinstance(bruto, float):        # entrada float e aceita e virara Decimal exato
        return repr(bruto)

    texto = limpar_espacos(bruto)
    if not texto:
        return None
    texto = _CUR_SIMBOLO.sub("", texto).replace(" ", "")
    if not texto:
        return None
    m = _RE_TOKEN_NUMERICO.fullmatch(texto)
    if not m:
        return None
    negativo = "-" in m.group(1) or "(" in m.group(1)
    return ("-" if negativo else "") + m.group(2)


def _decimal_de_token(token: str) -> Optional[Decimal]:
    """Convencao BR: aplica a regra do separador decimal descrita no topo do modulo."""
    s = token
    negativo = s.startswith("-")
    if negativo:
        s = s[1:]
    if not s or not any(ch.isdigit() for ch in s):
        return None

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            dec_sep, grp_sep = ",", "."
        else:
            dec_sep, grp_sep = ".", ","
    elif "," in s:
        dec_sep, grp_sep = (",", None) if s.count(",") == 1 else (None, ",")
    elif "." in s:
        partes = s.split(".")
        if len(partes) >= 3 or (len(partes) == 2 and len(partes[1]) == 3 and partes[0].isdigit()):
            dec_sep, grp_sep = None, "."
        else:
            dec_sep, grp_sep = ".", None
    else:
        dec_sep, grp_sep = None, None

    if dec_sep:
        corpo, _, fracao = s.rpartition(dec_sep)
        if dec_sep in corpo or dec_sep in fracao:
            return None
        if grp_sep:
            corpo = corpo.replace(grp_sep, "")
        texto = f"{corpo or '0'}.{fracao or '0'}"
    else:
        corpo = s.replace(grp_sep, "") if grp_sep else s
        texto = corpo or "0"

    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    if not valor.is_finite():
        return None
    return -valor if negativo else valor


def classificar_formato_moeda(bruto: Any) -> str:
    """Rotula o formato do token monetario. `us_milhar`/`ambiguo_milhar` merecem
    excecao de suspeita (doc 02 secao 2: padrao `1,234.56` -> flag de excecao)."""
    token = _token_numerico(bruto)
    if not token:
        return "invalido"
    s = token.lstrip("-")
    if not s or not s[0].isdigit():
        return "invalido"
    if re.fullmatch(r"\d{1,3}(,\d{3})+\.\d+", s):
        return "us_milhar"                      # 1,234.56
    if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        # 1,234.567 e milhar US sem duvida; 1,234 pode ser decimal BR
        return "us_milhar" if s.count(",") >= 2 else "ambiguo_milhar"
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):
        return "br_milhar"
    if re.fullmatch(r"\d+,\d+", s):
        return "br_decimal_virgula"
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return "br_inteiro"
    return "invalido"


def normalizar_moeda_centavos(bruto: Any) -> Optional[int]:
    """`R$ 1.234,56` -> `123456`. Nunca float: sempre `int` de centavos.

    Arredondamento ao centavo e ROUND_HALF_UP (o resto do sistema tambem usa
    HALF_UP, ver `contratos.Extracao.soma_itens_centavos`).
    """
    token = _token_numerico(bruto)
    if not token:
        return None
    valor = _decimal_de_token(token)
    if valor is None:
        return None
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _sem_zeros_inuteis(valor: Decimal) -> Decimal:
    """`Decimal("3.000")` -> `Decimal("3")`, `Decimal("3000.00")` -> `Decimal("3000")`.

    Mantem o numero exato (nenhuma precisao e perdida) mas com a representacao
    minima, para que `str(quantidade)` nao carregue zeros decorativos.
    """
    sinal, digitos, expoente = valor.as_tuple()
    digitos = list(digitos)
    while len(digitos) > 1 and expoente < 0 and digitos[-1] == 0:
        digitos.pop()
        expoente += 1
    return Decimal((sinal, tuple(digitos), expoente))


_RE_QUANTIDADE = re.compile(r"\d[\d.,]*")


def separar_quantidade_unidade(bruto: Any) -> tuple[Optional[Decimal], Optional[str]]:
    """`(quantidade, unidade)` - a unidade vai em campo proprio (doc 02 secao 2).

    `3 UN` -> `(Decimal("3"), "UN")`; `3,000` -> `(Decimal("3"), None)`.
    """
    if bruto is None or isinstance(bruto, bool):
        return (None, None)
    if isinstance(bruto, (int, Decimal)):
        return (normalizar_quantidade(bruto), None)
    texto = limpar_espacos(bruto)
    if not texto:
        return (None, None)

    m = _RE_QUANTIDADE.search(texto)
    if not m:
        return (None, None)
    quantidade = normalizar_quantidade(m.group(0))

    resto = (texto[: m.start()] + " " + texto[m.end():]).strip(" .,;:-")
    resto = limpar_espacos(resto)
    unidade = resto.upper()[:12] if resto else None
    if unidade and not re.fullmatch(r"[A-Z0-9º./]{1,12}", unidade):
        unidade = None
    return (quantidade, unidade)


def normalizar_quantidade(bruto: Any) -> Optional[Decimal]:
    """`3` | `3,000` | `3 UN` | `3.000,00` -> `Decimal`.

    Nunca float. Unidade e ignorada aqui (use `separar_quantidade_unidade`).
    """
    if bruto is None or isinstance(bruto, bool):
        return None
    if isinstance(bruto, Decimal):
        return _sem_zeros_inuteis(bruto)
    if isinstance(bruto, int):
        return _sem_zeros_inuteis(Decimal(bruto))
    if isinstance(bruto, float):
        return _sem_zeros_inuteis(Decimal(repr(bruto)))

    texto = limpar_espacos(bruto)
    if not texto:
        return None
    m = _RE_QUANTIDADE.search(texto)
    if not m:
        return None
    token = m.group(0).rstrip(".,")
    if not token:
        return None
    valor = _decimal_de_token(token.replace("+", ""))
    if valor is None:
        return None
    return _sem_zeros_inuteis(valor)


# --------------------------------------------------------------- campos textuais

_RE_PREFIXO_PEDIDO = re.compile(
    r"^\s*(?:n[ºo°]?\.?\s*|n[uú]mero\s+|pedido\s*(?:n[ºo°]?\.?\s*)?|nf-?e?\s*(?:n[ºo°]?\.?\s*)?|"
    r"ordem\s*(?:de\s*)?(?:compra\s*)?|oc\s*|pc\s*)?[:#\-]?\s*",
    re.IGNORECASE,
)


def normalizar_numero_pedido(bruto: Any) -> Optional[str]:
    """Trim + colapso de espacos + remocao de rotulo. Preserva zeros a esquerda,
    `/` e `-` (doc 02 secao 2: identificador sem fuzzy, tolerancia zero)."""
    if bruto is None or isinstance(bruto, bool):
        return None
    texto = limpar_espacos(bruto)
    if not texto:
        return None
    texto = _RE_PREFIXO_PEDIDO.sub("", texto).strip(" .,;:#-")
    texto = limpar_espacos(texto)
    if not texto:
        return None
    if not re.fullmatch(r"[A-Za-z0-9º°/.\- ]{1,40}", texto):
        return None
    return texto


_FORMA_PAGAMENTO_TOKENS = (
    ("cartao_credito", (r"cart[aã]o\s*de\s*cr[eé]dito", r"cr[eé]dito", r"\bcc\b")),
    ("cartao_debito", (r"cart[aã]o\s*de\s*d[eé]bito", r"d[eé]bito")),
    ("pix", (r"\bpix\b", r"pagamento\s+instant")),
    ("boleto", (r"boleto", r"bloqueto")),
    ("transferencia", (r"transfer[eê]ncia", r"\bted\b", r"\bdoc\b", r"dep[oó]sito")),
    ("dinheiro", (r"dinheiro", r"esp[eé]cie", r"em\s+esp[eé]cie")),
    ("prazo", (r"\bprazo\b", r"a\s+prazo", r"faturado", r"faturamento", r"\d+\s*dias")),
)


def mapear_forma_pagamento(bruto: Any) -> Optional[str]:
    """Mapeia o texto livre para o enum de `contratos.FORMAS_PAGAMENTO`.

    Texto sem correspondencia -> `"outro"`; ausente -> `None`. O texto original
    deve continuar indo para `forma_pagamento_raw`.
    """
    texto = limpar_espacos(bruto)
    if not texto:
        return None
    alvo = _sem_acento(texto).lower()
    for forma, padroes in _FORMA_PAGAMENTO_TOKENS:
        for padrao in padroes:
            if re.search(padrao, alvo):
                return forma
    return "outro"


# --------------------------------------------------------------- filtro de injecao de prompt

_TERMOS_INJECAO = (
    r"ignore\s+(as\s+|todas\s+as\s+)?(instru[cç][oõ]es|orienta[cç][oõ]es|regras|comandos)",
    r"ignore\s+(previous|all\s+previous|the\s+above)\s+instructions",
    r"disregard\s+(the\s+)?(previous\s+)?instructions",
    r"desconsidere\s+(as\s+|todas\s+as\s+)?(instru[cç][oõ]es|regras)",
    r"instru[cç][oõ]es\s+(anteriores|acima)",
    r"voc[eê]\s+(agora\s+)?[eé]\s+(um|uma|o|a)\s",
    r"you\s+are\s+now",
    r"(grave|gravar|registre|registrar|lance|lan[cç]ar|anote|anotar|salve|escreva|considere)\s+"
    r"(como\s+)?(o\s+|esse\s+|este\s+)?(valor|total|pre[cç]o)",
    r"(sobrescreva|substitua|altere|atualize|mude|modifique)\s+(o\s+|os\s+|esse\s+)?"
    r"(valor|total|pre[cç]o|dados|registro)",
    r"valor\s+(de\s+|final\s+de\s+)?(99999|999\.?999|9\.?999\.?999)",
    r"novo\s+total",
    r"total\s+(correto|real)\s+[eé]",
    r"system\s*prompt",
    r"prompt\s+do\s+sistema",
    r"como\s+(um\s+)?assistente",
    r"ignore\s+o\s+(valor|documento)",
    r"(nao|não)\s+confira",
)
_RE_INJECAO = re.compile("|".join(_TERMOS_INJECAO), re.IGNORECASE)


def detectar_injecao(texto: Any) -> bool:
    """True quando o texto contem instrucao dirigida ao leitor automatico.

    Conteudo de documento e **dado, nunca instrucao** (doc 02 risco R4). A funcao
    so sinaliza - quem chama decide (nunca obedecer, sempre mandar para humano).
    """
    alvo = limpar_espacos(texto)
    if not alvo:
        return False
    return bool(_RE_INJECAO.search(_sem_acento(alvo).lower()))
