"""F4 - Revisao humana: fila de excecoes e painel de acompanhamento.

Dono: inveja. Contrato: `docs/execucao/00-contrato-execucao.md` secao 5
(assinaturas congeladas) e secao 4.6 (trilha de auditoria e
`data/out/fila_excecoes.json`). O schema da tabela `fila_excecoes` esta em
`docs/02-dados-e-ia.md` secao 3.1: quem cria a tabela e
`app/persistencia.abrir_db` (dono gula). Aqui existe apenas um
`CREATE TABLE IF NOT EXISTS` com **as mesmas colunas** do doc, para o modulo
poder rodar e ser verificado isolado; quando o banco ja veio do
`persistencia.abrir_db`, o comando e um no-op.

Principio de UX aplicado (`docs/05-ux-revisao-humana.md`, secao 1.2):
**valor duvidoso nunca entra na planilha em silencio**. A pendencia fica
visivel na fila com motivo em linguagem de negocio, campo suspeito, valor lido e
valor calculado, para o humano decidir olhando o documento - o sistema nao
decide, nao esconde e nao inventa.

Regras nao negociaveis herdadas do contrato:
  * dinheiro **sempre inteiro em centavos** (nunca float);
  * data em ISO `YYYY-MM-DD`;
  * campo ausente e `None` - nunca `0`, nunca string vazia;
  * o painel e um HTML **estatico e autocontido**: sem CDN, sem rede, sem
    framework web, sem JavaScript.

Funcoes publicas (assinaturas congeladas):
    enfileirar_excecoes(conn, itens) -> int
    listar_pendencias(conn) -> list[dict]
    exportar_fila(conn, caminho_json) -> int
    gerar_painel(conn, caminho_html) -> str
"""

from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

try:  # execucao normal: pacote `app`
    from app import contratos
except ImportError:  # execucao solta (script de verificacao dentro do repo)
    import contratos  # type: ignore[no-redef]

__all__ = [
    "enfileirar_excecoes",
    "listar_pendencias",
    "exportar_fila",
    "gerar_painel",
    "info_motivo",
    "TABELA_FILA",
]

# --------------------------------------------------------------------- constantes

TABELA_FILA = "fila_excecoes"

# status da pendencia (doc 02 secao 3.1: aberta|em_analise|resolvida)
PENDENCIA_ABERTA = "aberta"
PENDENCIA_EM_ANALISE = "em_analise"
PENDENCIA_RESOLVIDA = "resolvida"
PENDENCIA_STATUS = (PENDENCIA_ABERTA, PENDENCIA_EM_ANALISE, PENDENCIA_RESOLVIDA)
PENDENCIA_STATUS_ABERTOS = (PENDENCIA_ABERTA, PENDENCIA_EM_ANALISE)

# faixas do semaforo de confianca (doc 05 secao 1.1) - iguais aos limiares do contrato
CONFIANCA_VERDE = contratos.LIMIAR_AUTO_APROVACAO      # >= 0.90
CONFIANCA_AMBAR = contratos.LIMIAR_REJEICAO            # 0.60 a 0.90
CONFIANCA_VERMELHO = contratos.LIMIAR_CAMPO_OBRIGATORIO  # < 0.60 (vermelho duro)

RISCO_ALTO = "alto"
RISCO_MEDIO = "medio"
_ORDEM_RISCO = {RISCO_ALTO: 0, RISCO_MEDIO: 1}

# Status que significam "esta conciliado / foi para a planilha".
_STATUS_CONCILIADOS = (
    contratos.STATUS_AUTO_APROVADO,
    contratos.STATUS_DOC_VALIDADO,
    "escrito",
)

# ------------------------------------------------------------------ catalogo de motivos

# Para cada motivo congelado em `contratos`, o que o humano precisa saber:
#   descricao -> motivo em linguagem de negocio (o doc 05 proibe jargao de IA);
#   campo     -> campo suspeito, o que ele deve olhar no documento;
#   dica      -> acao pratica de verificacao;
#   risco     -> alto (vermelho, sem lote) | medio (ambar, revisao individual).
MOTIVO_INFO: dict[str, dict[str, str]] = {
    contratos.MOTIVO_DIVERGENCIA_ITENS: {
        "descricao": "A soma dos itens nao bate com o total lido (diferenca acima de R$ 0,10).",
        "campo": "valor_total",
        "dica": "Confira o total impresso contra a soma das linhas de item antes de liberar.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_SUSPEITA_ITENS: {
        "descricao": "A soma dos itens quase bate com o total (diferenca de ate R$ 0,10).",
        "campo": "valor_total",
        "dica": "Rateio de desconto por item costuma explicar; confirme o total impresso.",
        "risco": RISCO_MEDIO,
    },
    contratos.MOTIVO_CONFLITO_VALOR: {
        "descricao": "Mesmo pedido ja conhecido com valor diferente (conflito de valor).",
        "campo": "valor_total",
        "dica": "Compare com a linha ja gravada: o sistema nao sobrescreve sozinho.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_VALOR_AUSENTE: {
        "descricao": "Nenhum valor total foi encontrado no documento.",
        "campo": "valor_total",
        "dica": "Leia o documento e digite o total; o sistema nao inventa valor.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_VALOR_FORA_FAIXA: {
        "descricao": "Valor total fora da faixa aceita (R$ 0,01 a R$ 10.000.000,00).",
        "campo": "valor_total",
        "dica": "Pode ser erro de leitura (virgula/ponto); confira o total impresso.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_CNPJ_INVALIDO: {
        "descricao": "O CNPJ do emitente nao fecha o digito verificador.",
        "campo": "emitente_cnpj",
        "dica": "Confira os 14 digitos do CNPJ no cabecalho do emitente.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_CHAVE_INVALIDA: {
        "descricao": "A chave de acesso da NF nao fecha o digito verificador.",
        "campo": "chave_acesso_nf",
        "dica": "Confira a chave de 44 digitos; erro de OCR costuma confundir 0/O e 1/l.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_DATA_IMPLAUSIVEL: {
        "descricao": "Data de emissao fora da janela plausivel.",
        "campo": "data_emissao",
        "dica": "Leia a data de emissao no documento: pode ter havido troca de dia e mes.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_DATA_AMBIGUA: {
        "descricao": "Data ambigua (dia menor ou igual a 12: da para ler como mes).",
        "campo": "data_emissao",
        "dica": "Confirme se o primeiro numero e o dia ou o mes.",
        "risco": RISCO_MEDIO,
    },
    contratos.MOTIVO_DOC_ILEGIVEL: {
        "descricao": "Documento ilegivel: nenhum texto util foi reconhecido.",
        "campo": "documento",
        "dica": "Peca o arquivo original ao fornecedor; leitura simulada nao sustenta valor.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_SEM_CAMPOS_OBRIGATORIOS: {
        "descricao": "Nenhum campo obrigatorio foi extraido do documento.",
        "campo": "campos_obrigatorios",
        "dica": "Documento provavelmente nao e nota/pedido do cliente; confirme antes de rejeitar.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_BAIXA_CONFIANCA: {
        "descricao": "Confianca da leitura abaixo do exigido para aprovacao automatica.",
        "campo": "confianca",
        "dica": "Confira campo por campo no original antes de aprovar.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_POSSIVEL_DUPLICATA: {
        "descricao": "Suspeita de duplicidade: mesmo emitente, data e valor de outro documento.",
        "campo": "duplicidade",
        "dica": "Procure o pedido ja lancado; duplicar aqui contamina o caixa.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_INJECAO_SUSPEITA: {
        "descricao": "O documento traz texto de instrucao suspeita (tentativa de manipular o sistema).",
        "campo": "texto",
        "dica": "Ignore a instrucao do texto e valide apenas os numeros reais do documento.",
        "risco": RISCO_ALTO,
    },
    contratos.MOTIVO_TOTAL_SEM_DETALHAMENTO: {
        "descricao": "Documento com total ancorado, mas sem itens detalhados.",
        "campo": "itens",
        "dica": "O valor entra como total sem detalhamento; confirme se e o que o cliente aceita.",
        "risco": RISCO_MEDIO,
    },
}

MOTIVO_INFO_PADRAO: dict[str, str] = {
    "descricao": "Pendencia registrada sem descricao padronizada pelo contrato.",
    "campo": "documento",
    "dica": "Leia o detalhe tecnico e confira o documento original.",
    "risco": RISCO_MEDIO,
}


def info_motivo(motivo_codigo: Optional[str]) -> dict[str, str]:
    """Descreve um motivo codigo em linguagem de negocio (campo, dica e risco)."""
    codigo = str(motivo_codigo or "").strip()
    base = MOTIVO_INFO.get(codigo, MOTIVO_INFO_PADRAO)
    return {
        "codigo": codigo,
        "descricao": base["descricao"],
        "campo": base["campo"],
        "dica": base["dica"],
        "risco": base["risco"],
    }


# ------------------------------------------------------------------------ utilidades


def _agora_iso() -> str:
    """Agora, em ISO 8601 com fuso local (segundos)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_iso(valor) -> Optional[datetime]:
    if valor is None:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def _idade_dias(valor) -> Optional[int]:
    dt = _parse_iso(valor)
    if dt is None:
        return None
    delta = datetime.now().astimezone() - dt
    return max(0, int(delta.total_seconds() // 86400))


def _centavos(valor) -> Optional[int]:
    """Coage um valor monetario para centavos inteiros. Nunca devolve float.

    - `int` passa direto (o contrato ja trabalha em centavos);
    - `Decimal`/`float` viram centavos inteiros;
    - texto com virgula (`"1.234,56"`) e tratado como reais e convertido para
      centavos; texto sem separador decimal e lido como centavos, igual ao resto
      do pipeline.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, Decimal):
        try:
            return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError):
            return None
    if isinstance(valor, float):
        return int(round(valor))
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")
    try:
        if "," in texto:
            limpo = texto.replace(".", "").replace(",", ".")
            return int(
                (Decimal(limpo) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        return int(Decimal(texto))
    except (InvalidOperation, ValueError):
        return None


def _brl(centavos) -> str:
    """`123456 -> 'R$ 1234,56'`; `None -> '—'` (ausente, nunca zero)."""
    if centavos is None:
        return "—"
    return "R$ " + contratos.formatar_brl(int(centavos))


def _pct(valor) -> str:
    if valor is None:
        return "—"
    try:
        return f"{int(round(float(valor) * 100))}%"
    except (TypeError, ValueError):
        return "—"


def _pegar(dicionario: Mapping, *nomes: str, default=None):
    """Primeiro valor nao-None entre os nomes candidatos.

    Serve para ler bancos com nomes de coluna levemente diferentes sem quebrar.
    """
    for nome in nomes:
        if nome in dicionario and dicionario[nome] is not None:
            return dicionario[nome]
    return default


def _pegar_attr(objeto, *nomes: str, default=None):
    for nome in nomes:
        valor = getattr(objeto, nome, None)
        if valor is not None:
            return valor
    return default


def _tabelas(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(linha[0]) for linha in cur.fetchall()}


def _todos(conn: sqlite3.Connection, tabela: str) -> list[dict]:
    """Todas as linhas de uma tabela como `dict`, tolerante a schema diferente.

    Devolve `[]` se a tabela nao existir - o painel continua sendo gerado.
    """
    if tabela not in _tabelas(conn):
        return []
    cur = conn.execute(f'SELECT * FROM "{tabela}"')  # nome sempre de constante interna
    colunas = [descricao[0] for descricao in cur.description or []]
    return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def _colunas(conn: sqlite3.Connection, tabela: str) -> list[str]:
    if tabela not in _tabelas(conn):
        return []
    cur = conn.execute(f'PRAGMA table_info("{tabela}")')
    return [str(linha[1]) for linha in cur.fetchall()]


def _texto(valor) -> str:
    return "" if valor is None else str(valor)


# ------------------------------------------------------------- schema da fila (no-op)


_SCHEMA_FILA = """
CREATE TABLE IF NOT EXISTS fila_excecoes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id   TEXT,
    pedido_id      TEXT,
    motivo_codigo  TEXT NOT NULL,
    detalhe        TEXT,
    valor_suspeito INTEGER,
    status         TEXT NOT NULL DEFAULT 'aberta',
    aberta_em      TEXT NOT NULL,
    resolvida_em   TEXT,
    resolvida_por  TEXT,
    decisao        TEXT
)
"""

_INDICE_FILA = (
    "CREATE INDEX IF NOT EXISTS idx_fila_excecoes_status "
    "ON fila_excecoes (status, motivo_codigo)"
)


def _garantir_tabela_fila(conn: sqlite3.Connection) -> None:
    """`CREATE TABLE IF NOT EXISTS` com as colunas do doc 02 secao 3.1.

    Se a tabela ja veio de `persistencia.abrir_db` (dono gula), nada acontece.
    """
    conn.execute(_SCHEMA_FILA)
    try:
        conn.execute(_INDICE_FILA)
    except sqlite3.Error:
        # Indice e conveniencia, nao pre-requisito: nunca derruba o pipeline.
        pass
    conn.commit()


# --------------------------------------------------------------- normalizacao de itens

# chaves aceitas na entrada de `enfileirar_excecoes` (dict, Extracao ou similar)
_CHAVES_DOCUMENTO = ("documento_id", "doc_id", "documento")
_CHAVES_PEDIDO = ("pedido_id", "pedido", "id_pedido")
_CHAVES_MOTIVO = ("motivo_codigo", "motivo", "codigo_motivo")
_CHAVES_VALOR = ("valor_suspeito", "valor_suspeito_centavos", "valor_total_centavos")
_CHAVES_DETALHE = ("detalhe", "observacao", "descricao")
_CHAVES_CONFIANCA = ("confianca_geral", "confianca_doc", "confianca")
_CHAVES_ARQUIVO = ("arquivo_origem", "arquivo", "caminho", "arquivo_uri")


def _base_comum() -> dict[str, Any]:
    return {
        "documento_id": None,
        "pedido_id": None,
        "valor_total_centavos": None,
        "valor_calculado_centavos": None,
        "confianca": None,
        "arquivo": None,
        "origem": None,
        "numero_pedido": None,
        "emitente_cnpj": None,
        "data_emissao": None,
        "status_validacao": None,
        "detalhe_extra": None,
    }


def _codigos_motivo(explicitos, status_validacao) -> tuple[list[str], bool]:
    """Devolve (codigos, inferido). Sem motivo explicito, deriva do status.

    Derivar o codigo do status e um ultimo recurso - e o `detalhe` deixa escrito
    que o validador nao detalhou o motivo, para nada ficar implicito.
    """
    if explicitos:
        return [str(c) for c in explicitos if c], False
    status = _texto(status_validacao).strip().lower()
    if status == contratos.STATUS_REVISAO_HUMANA:
        return [contratos.MOTIVO_BAIXA_CONFIANCA], True
    if status == contratos.STATUS_REJEITADO:
        return [contratos.MOTIVO_SEM_CAMPOS_OBRIGATORIOS], True
    return [], False


def _base_de_mapping(bruto: Mapping) -> dict[str, Any]:
    base = _base_comum()
    base["documento_id"] = _pegar(bruto, *_CHAVES_DOCUMENTO)
    base["pedido_id"] = _pegar(bruto, *_CHAVES_PEDIDO)
    base["valor_total_centavos"] = _centavos(
        _pegar(bruto, "valor_total_centavos", "valor_total", default=None)
    )
    base["valor_calculado_centavos"] = _centavos(
        _pegar(bruto, "valor_calculado_centavos", "total_calculado_centavos", default=None)
    )
    base["confianca"] = _pegar(bruto, *_CHAVES_CONFIANCA)
    base["arquivo"] = _pegar(bruto, *_CHAVES_ARQUIVO)
    base["origem"] = _pegar(bruto, "origem_canal", "origem", "canal")
    base["numero_pedido"] = _pegar(bruto, "numero_pedido", "pedido_numero")
    base["emitente_cnpj"] = _pegar(bruto, "emitente_cnpj", "cnpj")
    base["data_emissao"] = _pegar(bruto, "data_emissao")
    base["status_validacao"] = _pegar(bruto, "status_validacao", "status")
    base["detalhe_extra"] = _pegar(bruto, *_CHAVES_DETALHE)
    return base


def _base_de_objeto(objeto) -> dict[str, Any]:
    """Base a partir de uma `contratos.Extracao` (ou objeto equivalente)."""
    base = _base_comum()
    base["documento_id"] = _pegar_attr(objeto, *_CHAVES_DOCUMENTO)
    base["pedido_id"] = _pegar_attr(objeto, *_CHAVES_PEDIDO)
    base["valor_total_centavos"] = _centavos(
        _pegar_attr(objeto, "valor_total_centavos")
    )
    calculado = None
    if hasattr(objeto, "total_calculado_centavos") and callable(
        objeto.total_calculado_centavos
    ):
        try:
            calculado = objeto.total_calculado_centavos()
        except Exception:
            calculado = None
    base["valor_calculado_centavos"] = _centavos(calculado)
    base["confianca"] = _pegar_attr(objeto, *_CHAVES_CONFIANCA)
    base["arquivo"] = _pegar_attr(objeto, *_CHAVES_ARQUIVO)
    base["origem"] = _pegar_attr(objeto, "origem_canal", "origem", "canal")
    base["numero_pedido"] = _pegar_attr(objeto, "numero_pedido")
    base["emitente_cnpj"] = _pegar_attr(objeto, "emitente_cnpj")
    base["data_emissao"] = _pegar_attr(objeto, "data_emissao")
    base["status_validacao"] = _pegar_attr(objeto, "status_validacao", "status")
    return base


def _detalhe_legivel(motivo: str, base: Mapping, inferido: bool) -> str:
    info = info_motivo(motivo)
    pedacos: list[str] = []
    if base.get("numero_pedido"):
        pedacos.append(f"pedido={base['numero_pedido']}")
    if base.get("arquivo"):
        pedacos.append(f"arquivo={base['arquivo']}")
    if base.get("emitente_cnpj"):
        pedacos.append(f"cnpj={contratos.formatar_cnpj(str(base['emitente_cnpj']))}")
    if base.get("data_emissao"):
        pedacos.append(f"data_emissao={base['data_emissao']}")
    if base.get("valor_total_centavos") is not None:
        pedacos.append(f"valor_lido={_brl(base['valor_total_centavos'])}")
    if base.get("valor_calculado_centavos") is not None:
        pedacos.append(f"valor_calculado={_brl(base['valor_calculado_centavos'])}")
    if (
        base.get("valor_total_centavos") is not None
        and base.get("valor_calculado_centavos") is not None
    ):
        diferenca = abs(
            int(base["valor_calculado_centavos"]) - int(base["valor_total_centavos"])
        )
        pedacos.append(f"diferenca={_brl(diferenca)}")
    if base.get("confianca") is not None:
        pedacos.append(f"confianca={float(base['confianca']):.2f}")
    if base.get("origem"):
        pedacos.append(f"origem={base['origem']}")
    if base.get("status_validacao"):
        pedacos.append(f"status={base['status_validacao']}")
    detalhe = info["descricao"]
    if pedacos:
        detalhe += " | " + " ; ".join(pedacos)
    if inferido:
        detalhe += (
            " | motivo nao detalhado pelo validador: codigo derivado do status "
            f"{base.get('status_validacao') or 'ausente'}"
        )
    return detalhe


def _montar_pendencia(motivo: str, base: Mapping, inferido: bool) -> dict[str, Any]:
    extra = base.get("detalhe_extra")
    detalhe = _detalhe_legivel(motivo, base, inferido)
    if extra and str(extra).strip() and str(extra).strip() != detalhe:
        detalhe = f"{str(extra).strip()} | {detalhe}"

    info = info_motivo(motivo)
    valor_suspeito = None
    if not inferido:
        for chave in ("valor_suspeito",):
            if isinstance(base, Mapping) and base.get(chave) is not None:
                valor_suspeito = _centavos(base[chave])
                break
    if valor_suspeito is None and info["campo"] in (
        "valor_total",
        "duplicidade",
    ):
        valor_suspeito = base.get("valor_total_centavos")
    if valor_suspeito is None:
        # valor suspeito explicito vindo do dict de entrada
        valor_suspeito = base.get("valor_suspeito_centavos")

    return {
        "documento_id": base.get("documento_id"),
        "pedido_id": base.get("pedido_id"),
        "motivo_codigo": motivo,
        "detalhe": detalhe,
        "valor_suspeito": valor_suspeito,
    }


def _normalizar_item(bruto) -> list[dict[str, Any]]:
    """Transforma um item de entrada em 0..N pendencias normalizadas.

    Entradas aceitas: `dict` (chaves do contrato), `contratos.Extracao` e
    qualquer objeto com `motivos`/`documento_id`. Cada motivo vira uma pendencia.
    """
    if bruto is None:
        return []

    if isinstance(bruto, Mapping):
        # formato {extracao: Extracao, pedido_id: ...} tambem e aceito
        interno = bruto.get("extracao") or bruto.get("ext")
        if interno is not None and not isinstance(interno, Mapping):
            base = _base_de_objeto(interno)
            for chave, valor in _base_de_mapping(bruto).items():
                if valor is not None or base.get(chave) is None:
                    base[chave] = valor
            explicitos = bruto.get("motivos")
            if isinstance(explicitos, (list, tuple, set)):
                explicitos = list(explicitos)
            elif explicitos:
                explicitos = [explicitos]
            else:
                explicitos = _pegar_attr(interno, "motivos") or []
            codigos, inferido = _codigos_motivo(explicitos, base.get("status_validacao"))
            return [_montar_pendencia(c, base, inferido) for c in codigos]

        base = _base_de_mapping(bruto)
        explicitos = bruto.get("motivos")
        if isinstance(explicitos, (list, tuple, set)):
            explicitos = list(explicitos)
        elif explicitos:
            explicitos = [explicitos]
        else:
            explicitos = [_pegar(bruto, *_CHAVES_MOTIVO)] if _pegar(bruto, *_CHAVES_MOTIVO) else []
        base["valor_suspeito"] = _centavos(_pegar(bruto, *_CHAVES_VALOR, default=None))
        base["valor_suspeito_centavos"] = base["valor_suspeito"]
        codigos, inferido = _codigos_motivo(explicitos, base.get("status_validacao"))
        return [_montar_pendencia(c, base, inferido) for c in codigos]

    # objeto com atributos (Extracao e equivalentes)
    base = _base_de_objeto(bruto)
    explicitos = _pegar_attr(bruto, "motivos") or []
    if isinstance(explicitos, str):
        explicitos = [explicitos]
    codigos, inferido = _codigos_motivo(list(explicitos), base.get("status_validacao"))
    return [_montar_pendencia(c, base, inferido) for c in codigos]


def _normalizar_itens(itens) -> list[dict[str, Any]]:
    if itens is None:
        return []
    if isinstance(itens, (str, bytes)):
        return []
    if isinstance(itens, Mapping) or not hasattr(itens, "__iter__"):
        return _normalizar_item(itens)
    saida: list[dict[str, Any]] = []
    for bruto in itens:
        saida.extend(_normalizar_item(bruto))
    return saida


def _chave_pendencia(item: Mapping) -> tuple:
    """Chave natural de idempotencia de uma pendencia."""
    valor = item.get("valor_suspeito")
    return (
        _texto(item.get("documento_id")),
        _texto(item.get("pedido_id")),
        _texto(item.get("motivo_codigo")),
        "" if valor is None else str(int(valor)),
    )


def _status_pendencia(linha: Mapping) -> str:
    return _texto(_pegar(linha, "status", default=PENDENCIA_ABERTA)).strip().lower()


def _chaves_abertas(conn: sqlite3.Connection) -> set[tuple]:
    return {
        _chave_pendencia(linha)
        for linha in _todos(conn, TABELA_FILA)
        if _status_pendencia(linha) in PENDENCIA_STATUS_ABERTOS
    }


# ---------------------------------------------------------------- API: fila de excecoes


def enfileirar_excecoes(conn: sqlite3.Connection, itens) -> int:
    """Grava pendencias de revisao humana na tabela `fila_excecoes`.

    `itens` aceita um item ou uma lista; cada item pode ser um `dict` com as
    chaves do contrato (`documento_id`, `pedido_id`, `motivo_codigo`/`motivos`,
    `detalhe`, `valor_suspeito`) ou um objeto `contratos.Extracao`. Cada motivo
    do item vira uma linha, sempre com `status='aberta'` e `aberta_em` do momento
    da gravacao.

    **Idempotente**: a chave natural
    `(documento_id, pedido_id, motivo_codigo, valor_suspeito)` e comparada com as
    pendencias ainda abertas/em analise; reenfileirar a mesma pendencia nao cria
    duplicata. Um valor suspeito diferente para o mesmo motivo **e** pendencia
    nova (e bom que seja: e outra suspeita).

    Devolve o numero de pendencias **novas** gravadas (duplicatas nao contam).
    Confirma a transacao (`commit`) ao final.
    """
    pendencias = _normalizar_itens(itens)
    if not pendencias:
        return 0

    _garantir_tabela_fila(conn)
    colunas = set(_colunas(conn, TABELA_FILA))
    if "motivo_codigo" not in colunas:
        raise RuntimeError(
            "tabela 'fila_excecoes' sem a coluna 'motivo_codigo' - "
            "schema fora do doc 02 secao 3.1"
        )

    existentes = _chaves_abertas(conn)
    agora = _agora_iso()
    gravadas = 0

    for pendencia in pendencias:
        chave = _chave_pendencia(pendencia)
        if chave in existentes:
            continue
        campos = {k: v for k, v in pendencia.items() if k in colunas}
        campos["status"] = PENDENCIA_ABERTA
        campos["aberta_em"] = agora
        nomes = list(campos.keys())
        sql = (
            f'INSERT INTO "{TABELA_FILA}" ({", ".join(nomes)}) '
            f'VALUES ({", ".join(["?"] * len(nomes))})'
        )
        conn.execute(sql, [campos[n] for n in nomes])
        existentes.add(chave)
        gravadas += 1

    conn.commit()
    return gravadas


# -------------------------------------------------------------------- leitura do banco


def _contexto(conn: sqlite3.Connection) -> dict[str, dict]:
    """Mapas auxiliares para enriquecer pendencia e painel sem quebrar schema."""
    contexto: dict[str, dict] = {
        "documentos": {},
        "pedidos": {},
        "fornecedores": {},
        "soma_itens": {},
        "motor": {},
    }

    for doc in _todos(conn, "documentos"):
        identificador = doc.get("id")
        contexto["documentos"][identificador] = {
            "id": identificador,
            "arquivo": _pegar(
                doc, "arquivo_uri", "arquivo", "caminho", "arquivo_origem", "arquivo_nome"
            ),
            "origem": _pegar(doc, "origem", "canal", "origem_canal"),
            "status": _pegar(doc, "status"),
            "motor": _pegar(doc, "motor"),
            "ocr_usado": _pegar(doc, "ocr_usado"),
            "tipo_documento": _pegar(doc, "tipo_doc", "tipo_documento"),
            "confianca": _pegar(doc, "confianca", "confianca_doc"),
            "hash_conteudo": _pegar(doc, "sha256_conteudo", "hash_conteudo"),
        }

    for fornecedor in _todos(conn, "fornecedores"):
        cnpj = _pegar(fornecedor, "cnpj", "emitente_cnpj")
        contexto["fornecedores"][cnpj] = _pegar(
            fornecedor, "razao", "razao_social", "nome", "nome_fantasia"
        )

    for pedido in _todos(conn, "pedidos"):
        identificador = pedido.get("id")
        cnpj = _pegar(pedido, "emitente_cnpj", "cnpj")
        contexto["pedidos"][identificador] = {
            "id": identificador,
            "documento_id": _pegar(pedido, "documento_id"),
            "numero_pedido": _pegar(pedido, "numero_pedido", "numero"),
            "emitente_cnpj": cnpj,
            "emitente_nome": _pegar(pedido, "emitente_nome", "fornecedor", "razao")
            or contexto["fornecedores"].get(cnpj),
            "data_emissao": _pegar(pedido, "data_emissao"),
            "data_vencimento": _pegar(pedido, "data_vencimento"),
            "valor_total_centavos": _centavos(
                _pegar(pedido, "valor_total_centavos", "valor_total")
            ),
            "desconto_centavos": _centavos(_pegar(pedido, "desconto_centavos", "desconto")),
            "frete_centavos": _centavos(_pegar(pedido, "frete_centavos", "frete")),
            "confianca": _pegar(pedido, "confianca_doc", "confianca"),
            "status": _pegar(pedido, "status", "status_validacao"),
            "row_id_planilha": _pegar(pedido, "row_id_planilha"),
            "chave_acesso": _pegar(pedido, "chave_acesso", "chave_acesso_nf"),
        }

    for item in _todos(conn, "itens_pedido"):
        pedido_id = item.get("pedido_id")
        linha = _centavos(
            _pegar(item, "valor_linha_centavos", "valor_total_centavos", "total_centavos")
        )
        if linha is None:
            quantidade = _pegar(item, "quantidade")
            unitario = _centavos(
                _pegar(item, "valor_unitario_centavos", "valor_unitario")
            )
            if quantidade is not None and unitario is not None:
                try:
                    numero = Decimal(str(quantidade).split()[0].replace(",", "."))
                    linha = int(
                        (numero * unitario).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    )
                except (InvalidOperation, ValueError):
                    linha = None
        if linha is not None:
            contexto["soma_itens"][pedido_id] = (
                contexto["soma_itens"].get(pedido_id, 0) + int(linha)
            )

    for log in _todos(conn, "log_extracao"):
        motor = _pegar(log, "motor", "etapa")
        if motor:
            contexto["motor"][_pegar(log, "documento_id")] = str(motor)

    return contexto


def _ocr_simulado(contexto: Mapping, documento_id, documento: Mapping) -> bool:
    motor = contexto["motor"].get(documento_id) or (documento or {}).get("motor")
    if str(motor or "").strip() == contratos.MOTOR_OCR_SIMULADO:
        return True
    return bool((documento or {}).get("ocr_usado"))


def _pendencia_publica(
    linha: Mapping, contexto: Mapping
) -> dict[str, Any]:
    motivo = _texto(_pegar(linha, "motivo_codigo", "motivo"))
    info = info_motivo(motivo)

    documento_id = _pegar(linha, "documento_id")
    pedido_id = _pegar(linha, "pedido_id")
    documento = contexto["documentos"].get(documento_id) or {}
    pedido = contexto["pedidos"].get(pedido_id) or {}

    if not pedido and documento.get("id") is not None:
        # pendencia amarrada so ao documento: procura o pedido correspondente
        for candidato in contexto["pedidos"].values():
            if candidato.get("documento_id") == documento_id:
                pedido = candidato
                break
    if not documento and pedido.get("documento_id") is not None:
        documento = contexto["documentos"].get(pedido.get("documento_id")) or {}

    suspeito = _centavos(_pegar(linha, "valor_suspeito"))
    valor_lido = pedido.get("valor_total_centavos")
    if valor_lido is None:
        valor_lido = suspeito

    valor_calculado = None
    if pedido_id is not None and pedido_id in contexto["soma_itens"]:
        valor_calculado = int(contexto["soma_itens"][pedido_id])
        valor_calculado -= int(pedido.get("desconto_centavos") or 0)
        valor_calculado += int(pedido.get("frete_centavos") or 0)

    diferenca = None
    if valor_lido is not None and valor_calculado is not None:
        diferenca = abs(int(valor_calculado) - int(valor_lido))

    confianca = pedido.get("confianca")
    if confianca is None:
        confianca = documento.get("confianca")

    return {
        "id": _pegar(linha, "id"),
        "documento_id": documento_id,
        "pedido_id": pedido_id,
        "motivo_codigo": motivo,
        "motivo": info["descricao"],
        "campo_suspeito": info["campo"],
        "dica": info["dica"],
        "risco": info["risco"],
        "status": _status_pendencia(linha),
        "aberta_em": _pegar(linha, "aberta_em"),
        "idade_dias": _idade_dias(_pegar(linha, "aberta_em")),
        "detalhe": _pegar(linha, "detalhe"),
        "valor_suspeito_centavos": suspeito,
        "valor_suspeito": None if suspeito is None else contratos.formatar_brl(suspeito),
        "valor_lido_centavos": valor_lido,
        "valor_lido": None if valor_lido is None else contratos.formatar_brl(valor_lido),
        "valor_calculado_centavos": valor_calculado,
        "valor_calculado": (
            None if valor_calculado is None else contratos.formatar_brl(valor_calculado)
        ),
        "diferenca_centavos": diferenca,
        "diferenca": None if diferenca is None else contratos.formatar_brl(diferenca),
        # contexto do documento/pedido para decidir sem abrir o banco
        "arquivo": documento.get("arquivo") or pedido.get("arquivo"),
        "origem": documento.get("origem"),
        "tipo_documento": documento.get("tipo_documento"),
        "status_documento": documento.get("status"),
        "numero_pedido": pedido.get("numero_pedido"),
        "emitente_nome": pedido.get("emitente_nome"),
        "emitente_cnpj": pedido.get("emitente_cnpj"),
        "data_emissao": pedido.get("data_emissao"),
        "data_vencimento": pedido.get("data_vencimento"),
        "confianca": confianca,
        "confianca_texto": _pct(confianca),
        "ocr_simulado": _ocr_simulado(contexto, documento_id, documento),
        "resolvida_em": _pegar(linha, "resolvida_em"),
        "resolvida_por": _pegar(linha, "resolvida_por"),
        "decisao": _pegar(linha, "decisao"),
    }


def _listar_pendencias(conn: sqlite3.Connection, contexto: Mapping) -> list[dict]:
    linhas = [
        linha
        for linha in _todos(conn, TABELA_FILA)
        if _status_pendencia(linha) in PENDENCIA_STATUS_ABERTOS
    ]
    pendencias = [_pendencia_publica(linha, contexto) for linha in linhas]
    # ordenacao do doc 05 (tela 1): risco alto primeiro, depois a mais antiga
    pendencias.sort(
        key=lambda p: (
            _ORDEM_RISCO.get(str(p.get("risco")), 9),
            _texto(p.get("aberta_em")),
            _texto(p.get("motivo_codigo")),
        )
    )
    return pendencias


def listar_pendencias(conn: sqlite3.Connection) -> list[dict]:
    """Pendencias **abertas** (ou em analise), prontas para decisao humana.

    Cada item traz motivo codigo e o motivo em linguagem de negocio, campo
    suspeito e dica de verificacao, valor lido, valor calculado quando os itens
    do pedido existem, a diferenca entre os dois, risco, antiguidade e o contexto
    do documento (arquivo, origem, numero do pedido, emitente/CNPJ, data,
    confianca, status, marca de OCR simulado).

    Ordem: risco alto primeiro, depois a mais antiga (doc 05, tela 1).
    Devolve `[]` quando nao ha pendencia aberta.
    """
    return _listar_pendencias(conn, _contexto(conn))


def exportar_fila(conn: sqlite3.Connection, caminho_json) -> int:
    """Materializa a fila de excecoes em JSON (`data/out/fila_excecoes.json`).

    Formato do arquivo:
        {"versao": "1.0", "gerado_em": <ISO>, "total": N, "pendencias": [...]}

    cada pendencia com `motivo_codigo` e `detalhe` (secao 4.6 do contrato).
    Devolve o numero de pendencias exportadas.
    """
    pendencias = listar_pendencias(conn)
    payload = {
        "versao": contratos.SCHEMA_VERSION,
        "gerado_em": _agora_iso(),
        "total": len(pendencias),
        "pendencias": pendencias,
    }
    destino = Path(caminho_json)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return len(pendencias)


# ----------------------------------------------------------------------- painel HTML

_CSS = """
:root{
  --fundo:#f4f6f8; --papel:#ffffff; --linha:#e2e6eb; --linha-forte:#ccd4dd;
  --texto:#1f2328; --fraco:#5b6472; --primaria:#1c4f8f; --primaria-bg:#eaf1f9;
  --verde:#146c2e; --verde-bg:#e9f6ee; --verde-borda:#bfe3c8;
  --ambar:#8a5b00; --ambar-bg:#fdf4e3; --ambar-borda:#f0d9a8;
  --erro:#a4262c; --erro-bg:#fdeceb; --erro-borda:#f3c6c4;
  --neutro-bg:#f1f3f5; --sombra:0 1px 2px rgba(16,24,40,.05);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fundo);color:var(--texto);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  font-size:14px;line-height:1.5}
.wrap{max-width:1180px;margin:0 auto;padding:24px 20px 40px}
header.topo{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;
  justify-content:space-between;border-bottom:1px solid var(--linha-forte);
  padding-bottom:12px;margin-bottom:20px}
h1{margin:0;font-size:20px;font-weight:600;letter-spacing:-.01em}
.topo .meta{font-size:12px;color:var(--fraco)}
.marca{font-size:12px;color:var(--fraco);text-transform:uppercase;letter-spacing:.08em}
h2{margin:0 0 4px;font-size:16px;font-weight:600}
h2 .contador{font-weight:400;color:var(--fraco);font-size:13px}
.secao{margin-top:28px}
.secao .ajuda{margin:0 0 10px;font-size:12px;color:var(--fraco)}
.cartoes{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.cartao{background:var(--papel);border:1px solid var(--linha);border-radius:8px;
  padding:12px 14px;box-shadow:var(--sombra)}
.cartao .rotulo{font-size:11px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--fraco)}
.cartao .numero{font-size:26px;font-weight:600;line-height:1.2;margin-top:4px;
  font-variant-numeric:tabular-nums}
.cartao .nota{font-size:11px;color:var(--fraco);margin-top:4px}
.cartao.destaque{grid-column:1 / -1;border-left:3px solid var(--primaria);
  display:flex;flex-wrap:wrap;gap:8px 24px;align-items:flex-end;
  justify-content:space-between;background:var(--papel)}
.cartao.destaque .numero{font-size:30px}
.cartao.destaque .detalhe{font-size:12px;color:var(--fraco);text-align:right}
.tabela-wrap{background:var(--papel);border:1px solid var(--linha);border-radius:8px;
  overflow-x:auto;box-shadow:var(--sombra)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
caption{text-align:left;padding:12px 14px 0;font-size:12px;color:var(--fraco)}
th,td{padding:8px 10px;border-bottom:1px solid var(--linha);text-align:left;
  vertical-align:top}
thead th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--fraco);border-bottom:2px solid var(--linha-forte);white-space:nowrap}
tbody tr:nth-child(even){background:#fafbfc}
tbody tr:hover{background:var(--primaria-bg)}
tbody tr:last-child td{border-bottom:none}
tr.excecao{background:#fffaf1 !important}
tr.excecao td:first-child{border-left:3px solid #c9772a;padding-left:7px}
tr.rejeitado{background:#fdf7f7 !important}
tr.rejeitado td:first-child{border-left:3px solid var(--erro);padding-left:7px}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
td.mono{font-variant-numeric:tabular-nums;color:var(--fraco);white-space:nowrap}
.badge{display:inline-block;padding:0 7px;border-radius:999px;font-size:11.5px;
  border:1px solid var(--linha-forte);background:var(--neutro-bg);color:var(--fraco);
  white-space:nowrap;font-variant-numeric:tabular-nums}
.badge.ok{background:var(--verde-bg);border-color:var(--verde-borda);color:var(--verde)}
.badge.aviso{background:var(--ambar-bg);border-color:var(--ambar-borda);color:var(--ambar)}
.badge.erro{background:var(--erro-bg);border-color:var(--erro-borda);color:var(--erro)}
.badge.info{background:var(--primaria-bg);border-color:#c9dcef;color:var(--primaria)}
.motivo{display:block;color:var(--texto);font-weight:600;margin-top:2px}
.tecnico{display:block;color:var(--fraco);font-size:12px;margin-top:2px}
.truncar{max-width:320px}
.vazio{background:var(--papel);border:1px dashed var(--linha-forte);border-radius:8px;
  padding:18px 16px;color:var(--fraco)}
footer{margin-top:32px;border-top:1px solid var(--linha-forte);padding-top:14px;
  font-size:12px;color:var(--fraco)}
footer p{margin:0 0 6px}
footer strong{color:var(--texto);font-weight:600}
@media (max-width:900px){
  .cartoes{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cartao.destaque{flex-direction:column;align-items:flex-start}
  .cartao.destaque .detalhe{text-align:left}
  .truncar{max-width:220px}
}
@media (max-width:560px){
  .wrap{padding:16px 12px 28px}
  .cartoes{grid-template-columns:1fr}
  h1{font-size:18px}
}
"""

_ROTULOS_STATUS = {
    contratos.STATUS_AUTO_APROVADO: ("Aprovado automatico", "ok", "✓"),
    contratos.STATUS_REVISAO_HUMANA: ("Em revisao", "aviso", "!"),
    contratos.STATUS_REJEITADO: ("Rejeitado", "erro", "✖"),
    contratos.STATUS_DOC_RECEBIDO: ("Recebido", "neutro", "•"),
    contratos.STATUS_DOC_EXTRAIDO: ("Extraido", "neutro", "•"),
    contratos.STATUS_DOC_VALIDADO: ("Escrito na planilha", "ok", "✓"),
    contratos.STATUS_DOC_EXCECAO: ("Excecao", "aviso", "!"),
    "escrito": ("Escrito na planilha", "ok", "✓"),
    PENDENCIA_ABERTA: ("Aberta", "aviso", "!"),
    PENDENCIA_EM_ANALISE: ("Em analise", "info", "•"),
    PENDENCIA_RESOLVIDA: ("Resolvida", "ok", "✓"),
}


def _badge_status(status) -> str:
    chave = _texto(status).strip().lower()
    if not chave:
        return '<span class="badge">—</span>'
    rotulo, classe, simbolo = _ROTULOS_STATUS.get(
        chave, (chave, "neutro", "•")
    )
    return (
        f'<span class="badge {classe}" title="status: {html.escape(chave, quote=True)}">'
        f"{simbolo} {html.escape(rotulo)}</span>"
    )


def _badge_confianca(confianca) -> str:
    if confianca is None:
        return '<span class="badge">—</span>'
    try:
        numero = float(confianca)
    except (TypeError, ValueError):
        return '<span class="badge">—</span>'
    if numero >= CONFIANCA_VERDE:
        classe, simbolo = "ok", "✓"
    elif numero >= CONFIANCA_AMBAR:
        classe, simbolo = "aviso", "!"
    else:
        classe, simbolo = "erro", "✖"
    return (
        f'<span class="badge {classe}" aria-label="confianca {int(round(numero * 100))} por cento">'
        f"{simbolo} {_pct(numero)}</span>"
    )


def _celula_documento(arquivo, documento_id) -> str:
    nome = Path(str(arquivo)).name if arquivo else ""
    curto = _texto(documento_id)
    if len(curto) > 12:
        curto = curto[:12] + "…"
    if nome:
        return f"{html.escape(nome)}<span class=\"tecnico\">{html.escape(curto)}</span>"
    return f"<span class=\"mono\">{html.escape(curto) or '—'}</span>"


def _cartao(rotulo: str, valor, nota: str = "") -> str:
    numero = "—" if valor is None else f"{int(valor)}"
    nota_html = f'<div class="nota">{html.escape(nota)}</div>' if nota else ""
    return (
        '<div class="cartao">'
        f'<div class="rotulo">{html.escape(rotulo)}</div>'
        f'<div class="numero">{numero}</div>{nota_html}'
        "</div>"
    )


def _auditoria_dedupe(caminho_html) -> Optional[int]:
    """Conta reenvios barrados na trilha de auditoria ao lado do painel.

    O banco nao guarda "documento reenviado": quem registra isso e
    `data/out/auditoria.jsonl` (secao 4.6 do contrato, `acao="deduplicado"`).
    Leitura opcional: sem o arquivo, a metrica fica indisponivel (o painel mostra
    `—` em vez de inventar numero).
    """
    try:
        auditoria = Path(caminho_html).resolve().parent / "auditoria.jsonl"
    except (OSError, ValueError):
        return None
    if not auditoria.is_file():
        return None
    contador = 0
    try:
        with auditoria.open("r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registro = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if not isinstance(registro, dict):
                    continue
                acao = _texto(registro.get("acao")).strip().lower()
                if acao in ("deduplicado", "dedupe", "duplicado"):
                    contador += 1
    except OSError:
        return None
    return contador


def _resumo(
    conn: sqlite3.Connection,
    contexto: Mapping,
    documentos: list[dict],
    pedidos: list[dict],
    pendencias: list[dict],
    caminho_html,
) -> dict[str, dict]:
    tabelas = _tabelas(conn)
    tem_documentos = "documentos" in tabelas
    tem_pedidos = "pedidos" in tabelas

    def contar_pedidos(*status) -> Optional[int]:
        if not tem_pedidos:
            return None
        alvos = {s.lower() for s in status}
        return sum(
            1
            for p in pedidos
            if _texto(_pegar(p, "status", "status_validacao")).strip().lower() in alvos
        )

    artefatos = len(documentos) if tem_documentos else None

    auto_aprovados = contar_pedidos(contratos.STATUS_AUTO_APROVADO)
    em_revisao = contar_pedidos(contratos.STATUS_REVISAO_HUMANA)
    rejeitados = contar_pedidos(contratos.STATUS_REJEITADO)

    if em_revisao is None:
        em_revisao = len({p["documento_id"] for p in pendencias if p.get("documento_id")})
    if rejeitados is None:
        rejeitados = sum(
            1
            for d in documentos
            if _texto(_pegar(d, "status")).strip().lower() == contratos.STATUS_DOC_REJEITADO
        )

    deduplicados = _auditoria_dedupe(caminho_html)

    # valor conciliado: linhas que aprovacao automatica libera para a planilha
    conciliados = [
        p
        for p in pedidos
        if _texto(_pegar(p, "status", "status_validacao")).strip().lower()
        in {s.lower() for s in _STATUS_CONCILIADOS}
        and _centavos(_pegar(p, "valor_total_centavos", "valor_total")) is not None
    ]
    valor_conciliado = (
        sum(int(_centavos(_pegar(p, "valor_total_centavos", "valor_total"))) for p in conciliados)
        if tem_pedidos
        else None
    )

    return {
        "artefatos_lidos": {
            "valor": artefatos,
            "nota": "documentos no banco de entrada",
            "falta": "tabela 'documentos' ausente",
        },
        "auto_aprovados": {
            "valor": auto_aprovados,
            "nota": "pedidos liberados sem revisao",
            "falta": "tabela 'pedidos' ausente",
        },
        "deduplicados": {
            "valor": deduplicados,
            "nota": "reenvio barrado (trilha de auditoria)",
            "falta": "auditoria.jsonl ao lado do painel",
        },
        "em_revisao": {
            "valor": em_revisao,
            "nota": "pedidos na fila de revisao",
            "falta": None,
        },
        "rejeitados": {
            "valor": rejeitados,
            "nota": "pedidos rejeitados na validacao",
            "falta": None,
        },
        "valor_conciliado": {
            "valor": valor_conciliado if tem_pedidos else None,
            "linhas": len(conciliados) if tem_pedidos else None,
            "falta": "tabela 'pedidos' ausente",
        },
    }


def _linhas_entrada(
    contexto: Mapping, pedidos: list[dict], pendencias: list[dict]
) -> list[dict]:
    """Uma linha por pedido, com o que o operador precisa conferir de relance."""
    por_pedido: dict[Any, list[dict]] = {}
    por_documento: dict[Any, list[dict]] = {}
    for pendencia in pendencias:
        por_pedido.setdefault(pendencia.get("pedido_id"), []).append(pendencia)
        por_documento.setdefault(pendencia.get("documento_id"), []).append(pendencia)

    linhas: list[dict] = []
    for pedido in pedidos:
        identificador = pedido.get("id")
        documento_id = _pegar(pedido, "documento_id")
        documento = contexto["documentos"].get(documento_id) or {}
        excecoes = list(por_pedido.get(identificador, [])) or list(
            por_documento.get(documento_id, [])
        )
        cnpj = _pegar(pedido, "emitente_cnpj", "cnpj")
        status = _pegar(pedido, "status", "status_validacao")
        confianca = _pegar(pedido, "confianca_doc", "confianca")
        if confianca is None:
            confianca = documento.get("confianca")
        linhas.append(
            {
                "arquivo": documento.get("arquivo"),
                "documento_id": documento_id,
                "origem": documento.get("origem"),
                "numero_pedido": _pegar(pedido, "numero_pedido", "numero"),
                "emitente_nome": _pegar(pedido, "emitente_nome", "fornecedor", "razao")
                or contexto["fornecedores"].get(cnpj),
                "emitente_cnpj": cnpj,
                "data_emissao": _pegar(pedido, "data_emissao"),
                "valor_centavos": _centavos(
                    _pegar(pedido, "valor_total_centavos", "valor_total")
                ),
                "confianca": confianca,
                "status": status,
                "ocr_simulado": _ocr_simulado(contexto, documento_id, documento),
                "excecoes": excecoes,
                "rejeitado": _texto(status).strip().lower() == contratos.STATUS_REJEITADO,
            }
        )

    # excecoes primeiro (o operador quer o que esta errado), depois por pedido
    linhas.sort(
        key=lambda linha: (
            0 if linha["excecoes"] or linha["rejeitado"] else 1,
            _texto(linha["numero_pedido"]).rjust(12, "0"),
            _texto(linha["arquivo"]),
        )
    )
    return linhas


def _tabela_entradas(linhas: list[dict]) -> str:
    if not linhas:
        return (
            '<div class="vazio">Nenhum pedido registrado nesta rodada. '
            "Estado vazio e sistema quebrado precisam ser distinguiveis: confira se o "
            "banco do pipeline tem a tabela <code>pedidos</code>.</div>"
        )
    partes = [
        '<div class="tabela-wrap"><table>',
        "<caption>Uma linha por pedido processado. Linhas em destaque tem pendencia "
        "aberta ou foram rejeitadas - nada disso entra na planilha em silencio.</caption>",
        "<thead><tr>",
        '<th scope="col">Documento</th>',
        '<th scope="col">Origem</th>',
        '<th scope="col">N. pedido</th>',
        '<th scope="col">Emitente / CNPJ</th>',
        '<th scope="col">Data</th>',
        '<th scope="col">Valor</th>',
        '<th scope="col">Confianca</th>',
        '<th scope="col">Situacao</th>',
        "</tr></thead><tbody>",
    ]
    for linha in linhas:
        classes = []
        if linha["excecoes"]:
            classes.append("excecao")
        if linha["rejeitado"]:
            classes.append("rejeitado")
        classe = f' class="{" ".join(classes)}"' if classes else ""

        emitente = html.escape(_texto(linha["emitente_nome"]) or "—")
        cnpj_formatado = (
            contratos.formatar_cnpj(str(linha["emitente_cnpj"]))
            if linha["emitente_cnpj"]
            else ""
        )
        if cnpj_formatado:
            emitente += f'<span class="tecnico">{html.escape(cnpj_formatado)}</span>'

        situacao = _badge_status(linha["status"])
        if linha["ocr_simulado"]:
            situacao += ' <span class="badge info">OCR simulado</span>'
        if linha["excecoes"]:
            situacao += ' <span class="badge aviso">excecao</span>'
        ja_mostrado: set[tuple[str, str]] = set()
        for pendencia in linha["excecoes"]:
            codigo = html.escape(_texto(pendencia.get("motivo_codigo")))
            campo = html.escape(_texto(pendencia.get("campo_suspeito")))
            detalhe = html.escape(_texto(pendencia.get("detalhe")))
            motivo = html.escape(_texto(pendencia.get("motivo")))
            # duas pendencias do mesmo motivo no mesmo documento: mostra o bloco
            # uma vez so, para o operador nao ler o mesmo texto duas vezes
            chave_visual = (motivo, detalhe)
            if chave_visual in ja_mostrado:
                continue
            ja_mostrado.add(chave_visual)
            situacao += (
                f'<span class="motivo">{motivo}</span>'
                f'<span class="tecnico">{codigo} · campo {campo} · {detalhe}</span>'
            )

        partes.append(f"<tr{classe}>")
        partes.append(f'<td class="truncar">{_celula_documento(linha["arquivo"], linha["documento_id"])}</td>')
        partes.append(f'<td>{html.escape(_texto(linha["origem"]) or "—")}</td>')
        partes.append(
            f'<td class="mono">{html.escape(_texto(linha["numero_pedido"]) or "—")}</td>'
        )
        partes.append(f'<td class="truncar">{emitente}</td>')
        partes.append(
            f'<td class="mono">{html.escape(_texto(linha["data_emissao"]) or "—")}</td>'
        )
        partes.append(f'<td class="num">{_brl(linha["valor_centavos"])}</td>')
        partes.append(f'<td>{_badge_confianca(linha["confianca"])}</td>')
        partes.append(f"<td>{situacao}</td>")
        partes.append("</tr>")
    partes.append("</tbody></table></div>")
    return "".join(partes)


def _tabela_pendencias(pendencias: list[dict]) -> str:
    if not pendencias:
        agora = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
        return (
            f'<div class="vazio">Nada pendente. Ultima atualizacao {agora}. '
            "Fila vazia e fila que nao carregou precisam ser distinguiveis: confira a "
            "tabela <code>fila_excecoes</code> do banco.</div>"
        )
    partes = [
        '<div class="tabela-wrap"><table>',
        "<caption>Pendencias abertas ordenadas por risco e antiguidade. O sistema "
        "nao aprova, nao resolve duplicidade e nao esconde campo que falhou.</caption>",
        "<thead><tr>",
        '<th scope="col">Documento</th>',
        '<th scope="col">N. pedido / emitente</th>',
        '<th scope="col">Motivo</th>',
        '<th scope="col">Campo suspeito</th>',
        '<th scope="col">Valor lido</th>',
        '<th scope="col">Valor calculado</th>',
        '<th scope="col">Diferenca</th>',
        '<th scope="col">Risco</th>',
        '<th scope="col">Aberta</th>',
        "</tr></thead><tbody>",
    ]
    for pendencia in pendencias:
        linhas_tecnico = [
            html.escape(_texto(pendencia.get("motivo_codigo"))),
        ]
        if pendencia.get("detalhe"):
            linhas_tecnico.append(html.escape(_texto(pendencia.get("detalhe"))))
        if pendencia.get("dica"):
            linhas_tecnico.append(html.escape(_texto(pendencia.get("dica"))))
        tecnico = '<span class="tecnico">' + "<br>".join(linhas_tecnico) + "</span>"

        risco = str(pendencia.get("risco") or "")
        classe_risco = "erro" if risco == RISCO_ALTO else "aviso"
        simbolo_risco = "▲" if risco == RISCO_ALTO else "●"
        rotulo_risco = "risco alto" if risco == RISCO_ALTO else "risco medio"
        idade = pendencia.get("idade_dias")
        idade_texto = "" if idade is None else f" ({idade}d)"
        aberta = html.escape(_texto(pendencia.get("aberta_em")) or "—") + idade_texto

        emitente = html.escape(_texto(pendencia.get("emitente_nome")) or "—")
        if pendencia.get("emitente_cnpj"):
            emitente += (
                f'<span class="tecnico">{html.escape(contratos.formatar_cnpj(str(pendencia["emitente_cnpj"])))}</span>'
            )
        marcadores = ""
        if pendencia.get("ocr_simulado"):
            marcadores = ' <span class="badge info">OCR simulado</span>'

        partes.append("<tr>")
        partes.append(
            f'<td class="truncar">{_celula_documento(pendencia.get("arquivo"), pendencia.get("documento_id"))}{marcadores}</td>'
        )
        partes.append(
            f'<td class="truncar"><span class="mono">{html.escape(_texto(pendencia.get("numero_pedido")) or "—")}</span>'
            f"<span class=\"tecnico\">{emitente}</span></td>"
        )
        partes.append(
            f'<td class="truncar"><span class="motivo">{html.escape(_texto(pendencia.get("motivo")))}</span>{tecnico}</td>'
        )
        partes.append(
            f'<td>{html.escape(_texto(pendencia.get("campo_suspeito")) or "—")}</td>'
        )
        partes.append(f'<td class="num">{_brl(pendencia.get("valor_lido_centavos"))}</td>')
        partes.append(
            f'<td class="num">{_brl(pendencia.get("valor_calculado_centavos"))}</td>'
        )
        partes.append(f'<td class="num">{_brl(pendencia.get("diferenca_centavos"))}</td>')
        partes.append(
            f'<td><span class="badge {classe_risco}">{simbolo_risco} '
            f"{html.escape(rotulo_risco)}</span></td>"
        )
        partes.append(f'<td class="mono">{aberta}</td>')
        partes.append("</tr>")
    partes.append("</tbody></table></div>")
    return "".join(partes)


def gerar_painel(conn: sqlite3.Connection, caminho_html) -> str:
    """Gera o painel HTML **autocontido** de acompanhamento e devolve o caminho.

    Conteudo:
      * cartoes de resumo: artefatos lidos, auto-aprovados, deduplicados, em
        revisao e rejeitados;
      * valor total conciliado em BRL (`contratos.formatar_brl`);
      * tabela do que entrou (documento, origem, numero do pedido, emitente/CNPJ,
        data, valor, confianca, status) com as linhas de excecao em destaque;
      * fila de excecoes aberta, com motivo, campo suspeito, valor lido e valor
        calculado;
      * rodape com data/hora da geracao e o aviso de OCR simulado.

    Sem CDN, sem rede, sem framework web e sem JavaScript: todo o CSS vai
    embutido no arquivo. Leitura tolerante: tabela ausente nao quebra o painel,
    a metrica aparece como `—` em vez de um numero inventado.
    """
    destino = Path(caminho_html)
    contexto = _contexto(conn)
    documentos = _todos(conn, "documentos")
    pedidos = _todos(conn, "pedidos")
    pendencias = _listar_pendencias(conn, contexto)
    resumo = _resumo(conn, contexto, documentos, pedidos, pendencias, destino)
    linhas = _linhas_entrada(contexto, pedidos, pendencias)

    artefatos = resumo["artefatos_lidos"]
    cartoes = "".join(
        [
            _cartao(
                "Artefatos lidos",
                artefatos["valor"],
                artefatos["nota"] if artefatos["valor"] is not None else artefatos["falta"],
            ),
            _cartao(
                "Auto-aprovados",
                resumo["auto_aprovados"]["valor"],
                resumo["auto_aprovados"]["nota"]
                if resumo["auto_aprovados"]["valor"] is not None
                else resumo["auto_aprovados"]["falta"],
            ),
            _cartao(
                "Deduplicados",
                resumo["deduplicados"]["valor"],
                resumo["deduplicados"]["nota"]
                if resumo["deduplicados"]["valor"] is not None
                else resumo["deduplicados"]["falta"],
            ),
            _cartao("Em revisao", resumo["em_revisao"]["valor"], resumo["em_revisao"]["nota"]),
            _cartao("Rejeitados", resumo["rejeitados"]["valor"], resumo["rejeitados"]["nota"]),
        ]
    )

    conciliado = resumo["valor_conciliado"]
    if conciliado["valor"] is None:
        numero_conciliado = "—"
        detalhe_conciliado = (
            f"{conciliado['falta']} - nenhum valor foi somado"
        )
    else:
        numero_conciliado = "R$ " + contratos.formatar_brl(int(conciliado["valor"]))
        detalhe_conciliado = (
            f"{conciliado['linhas']} linha(s) aprovada(s)/escrita(s) na planilha<br>"
            f"soma de {len(pedidos)} pedido(s) no banco, em centavos inteiros"
        )

    gerado_em = datetime.now().astimezone()
    rodape = (
        "<footer>"
        f"<p><strong>Gerado em</strong> {gerado_em.strftime('%d/%m/%Y %H:%M:%S')} "
        f"({html.escape(gerado_em.isoformat(timespec='seconds'))}) - painel estatico gerado "
        "localmente pelo pipeline, sem rede e sem CDN.</p>"
        "<p><strong>OCR simulado</strong>: leituras feitas pelo motor simulado aparecem "
        "marcadas como <em>OCR simulado</em> na coluna de situacao e a confianca e menor. "
        "Nenhuma leitura simulada e apresentada como OCR real.</p>"
        "<p><strong>Valor</strong>: todo numero e inteiro em centavos; a soma conciliada usa "
        "apenas linhas aprovadas/escritas. O painel nao decide: valor duvidoso fica na fila "
        "de excecoes ate um humano confirmar.</p>"
        f"<p><strong>Fila</strong>: {len(pendencias)} pendencia(s) aberta(s). "
        "Motivo, campo suspeito, valor lido e valor calculado vem do banco; quando o campo "
        "nao existe na rodada, aparece <em>—</em> em vez de zero.</p>"
        "</footer>"
    )

    documento_html = (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light">\n'
        "<title>Painel de acompanhamento - controle financeiro</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        '<div class="wrap">\n'
        '<header class="topo">\n'
        "<div><div class=\"marca\">Controle financeiro</div>"
        "<h1>Painel de acompanhamento</h1></div>\n"
        f'<div class="meta">Leitura local de notas e pedidos &middot; gerado em '
        f"{gerado_em.strftime('%d/%m/%Y %H:%M')}</div>\n"
        "</header>\n"
        '<section class="secao">\n<h2>Resumo da rodada</h2>\n'
        '<p class="ajuda">Contagens do banco da rodada atual. <em>—</em> significa que o dado '
        "nao existe na rodada (nunca zero por suposicao).</p>\n"
        f'<div class="cartoes">{cartoes}'
        '<div class="cartao destaque">'
        '<div><div class="rotulo">Valor total conciliado</div>'
        f'<div class="numero">{numero_conciliado}</div></div>'
        f'<div class="detalhe">{detalhe_conciliado}</div>'
        "</div></div>\n</section>\n"
        '<section class="secao">\n<h2>O que entrou '
        f'<span class="contador">({len(linhas)} pedido(s))</span></h2>\n'
        f"{_tabela_entradas(linhas)}\n</section>\n"
        '<section class="secao">\n<h2>Fila de excecoes '
        f'<span class="contador">({len(pendencias)} aberta(s))</span></h2>\n'
        '<p class="ajuda">Valor duvidoso nunca entra na planilha em silencio: estas pendencias '
        "esperam decisao humana.</p>\n"
        f"{_tabela_pendencias(pendencias)}\n</section>\n"
        f"{rodape}\n</div>\n</body>\n</html>\n"
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(documento_html, encoding="utf-8")
    return str(destino)
