"""Aprovacao humana NA PLANILHA - o caminho que fecha a fila de excecoes.

Ate aqui a pendencia de revisao nascia `aberta` e **nunca** fechava: o schema tinha
`resolvida_em`/`resolvida_por`, o painel mostrava a fila, mas nenhum codigo escrevia
`resolvida` - o passo humano "conferi e aprovo" nao existia em lugar nenhum.

Aqui ele passa a existir, e acontece ONDE o financeiro ja trabalha: numa aba `Revisao` da
propria planilha de controle. Ciclo de uma rodada:

1. `aplicar_decisoes` le a aba `Revisao` deixada pela rodada anterior: a linha marcada para
   aprovar promove o pedido a `validado` (com as correcoes digitadas a mao) e fecha a
   pendencia como `resolvida`; a marcada para rejeitar fecha como rejeitada.
2. `escrever_ledger` (persistencia) grava a linha do pedido validado na aba oficial -
   **a regra de ouro continua de pe**: nenhuma linha entra sem aprovacao humana explicita.
3. `exportar_revisao` reescreve a aba com o que ainda esta aberto.

Seguranca deliberada: aprovacao sem valor total nao vira linha (o valor do erro monetario e
o pior modo de falha do projeto). Nesse caso a pendencia continua aberta e a rodada registra
um aviso dizendo o que faltou.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from . import contratos, normaliza

__all__ = [
    "ABA_REVISAO",
    "DECISAO_APROVAR",
    "DECISAO_REJEITAR",
    "COLUNAS_REVISAO",
    "COLUNAS_DECISAO",
    "rotulo_decisao",
    "exportar_revisao",
    "ler_decisoes",
    "aplicar_decisoes",
]

ABA_REVISAO = "Revisao"
ABA_OFICIAL = "controle_financeiro"

DECISAO_APROVAR = "aprovado"
DECISAO_REJEITAR = "rejeitado"

# Rotulos aceitos na coluna DECISAO. A escrita e texto livre numa planilha: quem revisa digita
# "aprovar", "APROVADO", "ok", "sim", "x" - e tudo isso e a MESMA decisao. Qualquer outra coisa
# (inclusive celula vazia) e "sem decisao": o sistema nao adivinha intencao.
_ROTULOS_APROVAR = ("APROVAR", "APROVADO", "APROVA", "OK", "SIM", "S", "X", "V")
_ROTULOS_REJEITAR = ("REJEITAR", "REJEITADO", "REJEITA", "NAO", "NÃO", "N", "NAO APROVAR")

# Colunas de identificacao/leitura (nao se digita nada aqui) e colunas de decisao (essas sim).
COLUNAS_REVISAO: tuple[str, ...] = (
    "pendencia_id",
    "documento_id",
    "pedido_id",
    "motivo_codigo",
    "motivo",
    "risco",
    "idade_dias",
    "origem",
    "tipo_documento",
    "arquivo_origem",
    "numero_pedido",
    "emitente_nome",
    "emitente_cnpj",
    "data_emissao",
    "valor_total",
    "valor_lido",
    "valor_calculado",
    "diferenca",
    "confianca_texto",
    "detalhe",
    "dica",
)

COLUNAS_DECISAO: tuple[str, ...] = (
    "DECISAO",
    "VALOR_TOTAL_CORRIGIDO",
    "NUMERO_PEDIDO_CORRIGIDO",
    "EMITENTE_CNPJ_CORRIGIDO",
    "DATA_EMISSAO_CORRIGIDA",
    "REVISOR",
    "OBSERVACAO",
)

# Colunas de apoio do fluxo de decisao (o campo "por que" fica na propria planilha).
COLUNAS_FLUXO: tuple[str, ...] = ("DECIDIDO_EM", "DECIDIDO_POR")

# A pendencia vem da fila (`revisao.listar_pendencias`) com nomes proprios: aqui ficam os
# poucos que nao batem com o titulo da coluna na planilha.
_PENDENCIA_POR_COLUNA = {"pendencia_id": "id", "arquivo_origem": "arquivo"}

_CABECALHO = COLUNAS_REVISAO + COLUNAS_DECISAO + COLUNAS_FLUXO

_CORRECAO_POR_CAMPO = {
    "valor_total_centavos": "VALOR_TOTAL_CORRIGIDO",
    "numero_pedido": "NUMERO_PEDIDO_CORRIGIDO",
    "emitente_cnpj": "EMITENTE_CNPJ_CORRIGIDO",
    "data_emissao": "DATA_EMISSAO_CORRIGIDA",
}

INSTRUCOES = (
    "Como aprovar: preencha a coluna DECISAO com APROVAR ou REJEITAR e salve o arquivo. "
    "O que a leitura automatica nao preencheu (ou preencheu errado), corrija nas colunas "
    "*_CORRIGIDO - so o que estiver preenchido e usado, o resto fica como esta. "
    "A linha entra na aba 'controle_financeiro' na proxima rodada e a pendencia sai da fila."
)


# ------------------------------------------------------------------ utilidades


def _agora_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _texto(valor: Any) -> str:
    """Texto de celula/valor. A fila devolve `'None'` como texto para nulo: isso e vazio."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() in ("none", "null", "nan") else texto


def rotulo_decisao(bruto: Any) -> Optional[str]:
    """`DECISAO_APROVAR`, `DECISAO_REJEITAR` ou None (sem decisao / rotulo desconhecido)."""
    texto = _texto(bruto).upper()
    if not texto:
        return None
    if texto.startswith("NÃO") or texto.startswith("NAO"):
        return DECISAO_REJEITAR if texto in _ROTULOS_REJEITAR else None
    if texto in _ROTULOS_APROVAR:
        return DECISAO_APROVAR
    if texto in _ROTULOS_REJEITAR:
        return DECISAO_REJEITAR
    return None


def _pendencias_abertas(conn: sqlite3.Connection) -> list[dict]:
    """Pendencias a revisar, vindas do modulo da fila (sem reimplementar a regra)."""
    from . import revisao

    return list(revisao.listar_pendencias(conn))


def _linha_da_pendencia(pendencia: Mapping) -> dict[str, Any]:
    valores: dict[str, Any] = {}
    for coluna in COLUNAS_REVISAO:
        valores[coluna] = _texto(pendencia.get(_PENDENCIA_POR_COLUNA.get(coluna, coluna)))
    valores.update({coluna: "" for coluna in COLUNAS_DECISAO + COLUNAS_FLUXO})
    return valores


# ------------------------------------------------------------------ escrita da aba


def exportar_revisao(
    conn: sqlite3.Connection,
    caminho_xlsx: Any,
    pendencias: Optional[Sequence[Mapping]] = None,
) -> int:
    """(Re)escreve a aba `Revisao` com as pendencias abertas. Devolve quantas linhas tem.

    A aba oficial (`controle_financeiro`) fica intacta - inclusive as 20 colunas do contrato e
    a linha de cabecalho. A aba de revisao e recriada a cada rodada: pendencia resolvida nao
    aparece mais, pendencia nova entra.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    destino = Path(caminho_xlsx)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        wb = load_workbook(destino)
    else:
        wb = Workbook()
        wb.active.title = ABA_OFICIAL

    if ABA_REVISAO in wb.sheetnames:
        del wb[ABA_REVISAO]
    ws = wb.create_sheet(ABA_REVISAO)

    linhas = list(pendencias) if pendencias is not None else _pendencias_abertas(conn)

    for indice, titulo in enumerate(_CABECALHO, start=1):
        celula = ws.cell(row=1, column=indice, value=titulo)
        celula.font = Font(bold=True)
        if titulo in COLUNAS_DECISAO:
            celula.fill = PatternFill("solid", fgColor="FFF2CC")
    ws.cell(row=2, column=1, value=INSTRUCOES)
    ws.freeze_panes = "A3"

    for offset, pendencia in enumerate(linhas):
        valores = _linha_da_pendencia(pendencia)
        for indice, titulo in enumerate(_CABECALHO, start=1):
            valor = valores.get(titulo, "")
            if isinstance(valor, (dict, list)):
                valor = ", ".join(str(v) for v in valor) if isinstance(valor, list) else str(valor)
            ws.cell(row=3 + offset, column=indice, value=valor if valor != "" else None)

    larguras = {
        "motivo": 42,
        "detalhe": 40,
        "dica": 40,
        "arquivo_origem": 44,
        "emitente_nome": 28,
        "DECISAO": 14,
        "OBSERVACAO": 30,
    }
    for indice, titulo in enumerate(_CABECALHO, start=1):
        ws.column_dimensions[get_column_letter(indice)].width = larguras.get(titulo, 18)
    ws.cell(row=1, column=1).alignment = Alignment(vertical="center")

    # A aba ATIVA tem de continuar sendo a oficial: `escrever_ledger` escreve na ativa, e a
    # revisao so existe para o humano decidir.
    wb.active = wb.sheetnames.index(ABA_OFICIAL) if ABA_OFICIAL in wb.sheetnames else 0
    wb.save(destino)
    return len(linhas)


# ------------------------------------------------------------------ leitura da decisao


def ler_decisoes(caminho_xlsx: Any) -> list[dict[str, Any]]:
    """Decisoes preenchidas na aba `Revisao`. Sem arquivo/aba/sem decisao -> `[]`."""
    from openpyxl import load_workbook

    destino = Path(caminho_xlsx)
    if not destino.exists():
        return []
    wb = load_workbook(destino, data_only=True)
    if ABA_REVISAO not in wb.sheetnames:
        return []
    ws = wb[ABA_REVISAO]
    cabecalho = [_texto(celula.value) for celula in ws[1]]
    indice = {titulo: posicao for posicao, titulo in enumerate(cabecalho)}
    if "DECISAO" not in indice:
        return []

    decisoes: list[dict[str, Any]] = []
    for linha in ws.iter_rows(min_row=3, values_only=True):
        decisao = rotulo_decisao(linha[indice["DECISAO"]] if indice["DECISAO"] < len(linha) else None)
        if decisao is None:
            continue
        item: dict[str, Any] = {"decisao": decisao}
        for coluna in _CABECALHO:
            posicao = indice.get(coluna)
            item[coluna] = _texto(linha[posicao]) if posicao is not None and posicao < len(linha) else ""
        decisoes.append(item)
    return decisoes


# ------------------------------------------------------------------ aplicacao


def _resolver_pendencias(
    conn: sqlite3.Connection,
    documento_id: str,
    pedido_id: str,
    decisao: str,
    revisor: str,
    agora: str,
) -> int:
    """Fecha as pendencias abertas do documento/pedido: e o passo que faltava no produto."""
    cursor = conn.execute(
        """
        UPDATE fila_excecoes
           SET status = 'resolvida', resolvida_em = ?, resolvida_por = ?, decisao = ?
         WHERE status IN ('aberta', 'em_analise')
           AND (pedido_id = ? OR (documento_id = ? AND ? = ''))
        """,
        (agora, revisor, decisao, pedido_id, documento_id, pedido_id),
    )
    return int(cursor.rowcount or 0)


def aplicar_decisoes(conn: sqlite3.Connection, caminho_xlsx: Any) -> dict[str, Any]:
    """Aplica as decisoes da aba `Revisao` ao banco. -> resumo da aplicacao.

    Aprovacao: pedido -> `validado` (com as correcoes), documento -> `validado`, pendencias do
    pedido -> `resolvida`. Rejeicao: pedido/documento -> `rejeitado`, pendencias -> `resolvida`
    com a decisao registrada.

    Idempotente: pedido ja em `validado`/`rejeitado` nao sofre nada. Aprovacao sem valor total
    (lido ou digitado) **nao** vira linha: entra em `avisos` e a pendencia continua aberta.
    """
    resumo: dict[str, Any] = {
        "lidas": 0,
        "aprovadas": 0,
        "rejeitadas": 0,
        "ignoradas": 0,
        "pendencias_fechadas": 0,
        "avisos": [],
    }
    decisoes = ler_decisoes(caminho_xlsx)
    resumo["lidas"] = len(decisoes)
    if not decisoes:
        return resumo

    for item in decisoes:
        pedido_id = _texto(item.get("pedido_id"))
        documento_id = _texto(item.get("documento_id"))
        rotulo = f"pendencia {_texto(item.get('pendencia_id')) or '?'}"
        revisor = _texto(item.get("REVISOR")) or "nao informado"

        pedido = None
        if pedido_id:
            pedido = conn.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if pedido is None:
            resumo["ignoradas"] += 1
            resumo["avisos"].append(f"{rotulo}: pedido '{pedido_id}' nao existe no banco")
            continue

        status_atual = _texto(pedido["status"])
        if item["decisao"] == DECISAO_REJEITAR and status_atual in (
            contratos.STATUS_AUTO_APROVADO,
            contratos.STATUS_DOC_VALIDADO,
        ):
            # Rejeitar o que JA esta no livro-caixa nao apaga a linha de la (o ledger so
            # escreve, nao remove): isso exige intervencao humana no arquivo. Nao decidir em
            # silencio e a unica saida honesta.
            resumo["ignoradas"] += 1
            resumo["avisos"].append(
                f"{rotulo}: pedido ja esta na planilha ('{status_atual}') - rejeitar agora "
                "exigiria apagar a linha na mao; nada foi alterado"
            )
            continue

        agora = _agora_iso()
        if item["decisao"] == DECISAO_REJEITAR:
            conn.execute(
                "UPDATE pedidos SET status = ?, atualizado_em = ? WHERE id = ?",
                ("rejeitado", agora, pedido_id),
            )
            if documento_id:
                conn.execute(
                    "UPDATE documentos SET status = ? WHERE id = ?",
                    (contratos.STATUS_DOC_REJEITADO, documento_id),
                )
            resumo["pendencias_fechadas"] += _resolver_pendencias(
                conn, documento_id, pedido_id, DECISAO_REJEITAR, revisor, agora
            )
            resumo["rejeitadas"] += 1
            continue

        campos: dict[str, Any] = {}
        for campo, coluna in _CORRECAO_POR_CAMPO.items():
            bruto = _texto(item.get(coluna))
            if not bruto:
                continue
            if campo == "valor_total_centavos":
                centavos = normaliza.normalizar_moeda_centavos(bruto)
                if centavos is None:
                    resumo["avisos"].append(
                        f"{rotulo}: valor '{bruto}' nao foi entendido - a rodada nao usa o valor"
                    )
                    continue
                campos[campo] = centavos
            elif campo == "emitente_cnpj":
                cnpj14, _dv = normaliza.normalizar_cnpj(bruto)
                if cnpj14 is None:
                    resumo["avisos"].append(f"{rotulo}: CNPJ '{bruto}' nao foi entendido")
                    continue
                campos[campo] = cnpj14
            else:
                campos[campo] = bruto

        valor_final = campos.get("valor_total_centavos", pedido["valor_total_centavos"])
        if valor_final is None:
            resumo["avisos"].append(
                f"{rotulo}: aprovacao sem valor total (nada lido e nada digitado) - "
                "a linha nao entra e a pendencia continua aberta"
            )
            resumo["ignoradas"] += 1
            continue

        campos["valor_total_centavos"] = int(valor_final)
        if not _texto(campos.get("numero_pedido", pedido["numero_pedido"])):
            # numero_pedido e NOT NULL na planilha: sem ele a linha sai sem identificacao.
            campos["numero_pedido"] = f"SEM-NUMERO-{pedido_id}"

        conjunto = ", ".join(f"{campo} = ?" for campo in campos)
        conn.execute(
            f"UPDATE pedidos SET {conjunto}, status = ?, atualizado_em = ? WHERE id = ?",
            (*[campos[campo] for campo in campos], "validado", agora, pedido_id),
        )
        if documento_id:
            conn.execute(
                "UPDATE documentos SET status = ? WHERE id = ?",
                (contratos.STATUS_DOC_VALIDADO, documento_id),
            )
        resumo["pendencias_fechadas"] += _resolver_pendencias(
            conn, documento_id, pedido_id, DECISAO_APROVAR, revisor, agora
        )
        resumo["aprovadas"] += 1

    conn.commit()
    return resumo
