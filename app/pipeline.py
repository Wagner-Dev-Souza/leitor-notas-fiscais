"""Orquestracao da rodada: ingestao -> extracao -> decisao -> planilha -> trilhas.

Dono: avareza (F1 - nucleo). Fronteira congelada na secao 5 do contrato:

    processar(inbox, out_dir, db_path) -> dict

Ordem executada (contrato 4.5/4.6):

    ingerir -> registrar_documento -> extrair -> persistencia.decidir()
            -> gravar_extracao -> escrever_ledger -> auditoria -> fila -> painel

Cada etapa pertence a um dono: a leitura e o extrator sao desta frente (F1); o banco,
a planilha e a decisao de validacao sao de F2 (gula); a fila e o painel sao de F4
(inveja). Este modulo **nao** reimplementa regra de decisao: chama `decidir()` e obedece
ao status devolvido.

Marcacao honesta: quando o documento entra pelo caminho de OCR simulado, o motor
(`ocr_simulado`) vai para a trilha de auditoria, para o resumo e para o painel. Em
nenhum ponto a saida simulada e apresentada como OCR real.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from . import extracao as extracao_mod
from . import ingress, persistencia
from .contratos import (
    MOTIVO_BAIXA_CONFIANCA,
    MOTIVO_DIVERGENCIA_ITENS,
    MOTIVO_INJECAO_SUSPEITA,
    MOTIVO_SUSPEITA_ITENS,
    MOTOR_OCR_SIMULADO,
    MOTOR_TESSERACT,
    STATUS_AUTO_APROVADO,
    STATUS_DOC_EXCECAO,
    STATUS_DOC_EXTRAIDO,
    STATUS_DOC_REJEITADO,
    STATUS_DOC_VALIDADO,
    STATUS_REJEITADO,
    STATUS_REVISAO_HUMANA,
    sha256_texto_normalizado,
)
from .ingress import agora_iso

try:  # F4 (inveja) entrega a fila e o painel; o pipeline nao reimplementa isso
    from . import revisao
except ImportError:  # pragma: no cover - so quando F4 ainda nao chegou
    revisao = None


NOMES_ARQUIVO = {
    "xlsx": "controle_financeiro.xlsx",
    "csv": "controle_financeiro.csv",
    "auditoria": "auditoria.jsonl",
    "fila_excecoes": "fila_excecoes.json",
    "painel": "painel.html",
    "resumo": "resumo.json",
}

STATUS_DOC_POR_VALIDACAO = {
    STATUS_AUTO_APROVADO: STATUS_DOC_VALIDADO,
    STATUS_REVISAO_HUMANA: STATUS_DOC_EXCECAO,
    STATUS_REJEITADO: STATUS_DOC_REJEITADO,
}

ACAO_POR_STATUS = {
    STATUS_AUTO_APROVADO: "inserido",
    STATUS_REVISAO_HUMANA: "revisao",
    STATUS_REJEITADO: "rejeitado",
}


# --------------------------------------------------------------------- detalhes


def _detalhe_motivo(extracao: Any, motivo: str) -> str:
    """Explicacao legivel do motivo, com os numeros que a decisao usou."""
    if motivo in (MOTIVO_DIVERGENCIA_ITENS, MOTIVO_SUSPEITA_ITENS):
        soma = extracao.soma_itens_centavos()
        calculado = extracao.total_calculado_centavos()
        diferenca = extracao.diferenca_itens_centavos()
        return (
            f"soma_itens={soma} total_calculado={calculado} "
            f"valor_total_lido={extracao.valor_total_centavos} diferenca_centavos={diferenca}"
        )
    if motivo == MOTIVO_INJECAO_SUSPEITA:
        return str(extracao.evidencia.get("injecao_suspeita") or "")[:300]
    ausentes = [
        campo
        for campo in ("valor_total_centavos", "emitente_cnpj", "data_emissao")
        if getattr(extracao, campo, None) is None
    ]
    if motivo == MOTIVO_BAIXA_CONFIANCA:
        return f"confianca_geral={extracao.confianca_geral} campos_ausentes={ausentes}"
    return f"tipo={extracao.tipo_documento} confianca={extracao.confianca_geral} campos_ausentes={ausentes}"


def _registro_auditoria(
    artefato: Any,
    documento_id: Optional[str],
    pedido_id: Optional[str],
    acao: str,
    extracao: Any = None,
    motivos: Optional[list[str]] = None,
) -> dict:
    """Uma linha da trilha de auditoria (campos minimos da secao 4.6 do contrato)."""
    return {
        "ts": agora_iso(),
        "artefato": str(artefato.caminho),
        "canal": artefato.canal,
        "hash_conteudo": artefato.hash_conteudo,
        "documento_id": documento_id,
        "pedido_id": pedido_id,
        "acao": acao,
        "motivos": list(motivos or []),
        "motor": artefato.motor,
        "ocr_usado": bool(getattr(extracao, "ocr_usado", False) or artefato.motor in (MOTOR_OCR_SIMULADO, MOTOR_TESSERACT)),
        "ocr_simulado": artefato.motor == MOTOR_OCR_SIMULADO,
        "tipo_documento": getattr(extracao, "tipo_documento", None),
        "numero_pedido": getattr(extracao, "numero_pedido", None),
        "valor_total_centavos": getattr(extracao, "valor_total_centavos", None),
        "confianca": getattr(extracao, "confianca_geral", None),
        "status_validacao": getattr(extracao, "status_validacao", None),
    }


# --------------------------------------------------------------------- rodada


def processar(inbox, out_dir, db_path, incluir_detalhes: bool = False) -> dict:
    """Roda a rodada inteira e devolve o resumo com as contagens.

    Nao engole erro: falha de biblioteca, disco ou contrato sobe para quem chamou. O que
    este modulo nunca faz e inventar resultado para parecer que rodou.
    """
    inicio = time.perf_counter()

    raiz_saida = Path(out_dir)
    raiz_saida.mkdir(parents=True, exist_ok=True)
    caminho_db = Path(db_path)
    if caminho_db.parent and str(caminho_db.parent) not in ("", "."):
        caminho_db.parent.mkdir(parents=True, exist_ok=True)

    caminhos = {
        chave: raiz_saida / nome
        for chave, nome in NOMES_ARQUIVO.items()
        if chave != "resumo"
    }
    caminho_resumo = raiz_saida / NOMES_ARQUIVO["resumo"]

    # trilha de auditoria e um append por rodada: comeca limpa para nao misturar rodadas
    if caminhos["auditoria"].exists():
        caminhos["auditoria"].unlink()

    artefatos = ingress.ingerir(inbox)
    conn = persistencia.abrir_db(str(caminho_db))

    contadores = {
        "artefatos": len(artefatos),
        "pdfs": 0,
        "mensagens": 0,
        "auto_aprovados": 0,
        "revisao": 0,
        "rejeitados": 0,
        "deduplicados": 0,
    }
    por_motor: dict[str, int] = {}
    motivos_contagem: dict[str, int] = {}
    detalhes: list[dict] = []
    pedidos_vistos: set[str] = set()
    avisos: list[str] = []

    try:
        for artefato in artefatos:
            if artefato.tipo_artefato == "pdf":
                contadores["pdfs"] += 1
            else:
                contadores["mensagens"] += 1
            por_motor[artefato.motor] = por_motor.get(artefato.motor, 0) + 1

            documento_id, dedupe = persistencia.registrar_documento(conn, artefato)

            if dedupe:
                contadores["deduplicados"] += 1
                persistencia.registrar_auditoria(
                    str(caminhos["auditoria"]),
                    _registro_auditoria(artefato, documento_id, None, "deduplicado"),
                )
                detalhes.append(
                    {
                        "artefato": str(artefato.caminho),
                        "documento_id": documento_id,
                        "acao": "deduplicado",
                        "motivo": "sha256/identidade de mensagem ja processada",
                    }
                )
                continue

            # ------------------------------------------------------------ extracao
            if artefato.tipo_artefato == "pdf":
                extracao = extracao_mod.extrair(artefato.texto, artefato.canal, artefato.caminho)
            else:
                extracao = extracao_mod.extrair_mensagem(artefato.mensagem)

            extracao.documento_id = documento_id
            extracao.arquivo_origem = str(artefato.caminho)
            extracao.hash_conteudo = artefato.hash_conteudo
            extracao.motor = artefato.motor
            extracao.ocr_usado = artefato.motor in (MOTOR_OCR_SIMULADO, MOTOR_TESSERACT)
            extracao.texto_norm_sha256 = sha256_texto_normalizado(artefato.texto or "")
            if not extracao.recebido_em:
                extracao.recebido_em = agora_iso()

            persistencia.atualizar_documento(
                conn,
                documento_id,
                status=STATUS_DOC_EXTRAIDO,
                tipo_doc=extracao.tipo_documento,
                processado_em=agora_iso(),
                texto_norm_sha256=extracao.texto_norm_sha256,
            )

            # ------------------------------------------------------------- decisao
            status, motivos = persistencia.decidir(extracao)
            motivos = list(dict.fromkeys([*(extracao.motivos or []), *motivos]))

            # Regra de seguranca do proprio extrator (contrato 4.6/B5): documento com
            # instrucao embutida nunca publica sozinho. `decidir()` tambem sinaliza;
            # esta linha e o cinto e o suspensorio.
            if MOTIVO_INJECAO_SUSPEITA in motivos and status == STATUS_AUTO_APROVADO:
                status = STATUS_REVISAO_HUMANA
                extracao.status_validacao = status
            extracao.motivos = motivos

            # ------------------------------------------------------------ gravacao
            pedido_id = persistencia.gravar_extracao(conn, extracao)

            acao = ACAO_POR_STATUS.get(status, "revisao")
            if acao == "inserido" and pedido_id in pedidos_vistos:
                acao = "atualizado"
            pedidos_vistos.add(pedido_id)

            persistencia.atualizar_documento(
                conn, documento_id, status=STATUS_DOC_POR_VALIDACAO.get(status, STATUS_DOC_EXTRAIDO)
            )

            persistencia.registrar_auditoria(
                str(caminhos["auditoria"]),
                _registro_auditoria(artefato, documento_id, pedido_id, acao, extracao, motivos),
            )

            if status != STATUS_AUTO_APROVADO:
                for motivo in motivos or [MOTIVO_BAIXA_CONFIANCA]:
                    motivos_contagem[motivo] = motivos_contagem.get(motivo, 0) + 1
                    persistencia.registrar_excecao(conn, extracao, motivo, _detalhe_motivo(extracao, motivo))

            if status == STATUS_AUTO_APROVADO:
                contadores["auto_aprovados"] += 1
            elif status == STATUS_REJEITADO:
                contadores["rejeitados"] += 1
            else:
                contadores["revisao"] += 1

            if incluir_detalhes:
                detalhes.append(
                    {
                        "artefato": str(artefato.caminho),
                        "canal": artefato.canal,
                        "documento_id": documento_id,
                        "pedido_id": pedido_id,
                        "acao": acao,
                        "tipo_documento": extracao.tipo_documento,
                        "numero_pedido": extracao.numero_pedido,
                        "valor_total_centavos": extracao.valor_total_centavos,
                        "confianca": extracao.confianca_geral,
                        "motor": artefato.motor,
                        "ocr_simulado": artefato.motor == MOTOR_OCR_SIMULADO,
                        "status": status,
                        "motivos": motivos,
                    }
                )

        # ------------------------------------------------------------ planilha
        linhas_planilha = persistencia.escrever_ledger(
            conn, str(caminhos["xlsx"]), str(caminhos["csv"])
        )

        # ------------------------------------------------- fila de excecoes + painel
        arquivos_gerados: dict[str, Optional[str]] = {}
        if revisao is not None:
            revisao.exportar_fila(conn, str(caminhos["fila_excecoes"]))
            revisao.gerar_painel(conn, str(caminhos["painel"]))
            arquivos_gerados["fila_excecoes"] = str(caminhos["fila_excecoes"])
            arquivos_gerados["painel"] = str(caminhos["painel"])
        else:
            avisos.append("modulo app/revisao.py ausente: fila de excecoes e painel nao foram gerados")
    finally:
        try:
            conn.close()
        except Exception:  # conexao ja fechada/indisponivel nao invalida a rodada
            pass

    for chave in ("xlsx", "csv", "auditoria"):
        arquivos_gerados[chave] = str(caminhos[chave])
    arquivos_gerados["db"] = str(caminho_db)
    arquivos_gerados["resumo"] = str(caminho_resumo)

    ocr_simulado = por_motor.get(MOTOR_OCR_SIMULADO, 0)
    resumo = {
        "ts": agora_iso(),
        "inbox": str(inbox),
        "out_dir": str(raiz_saida),
        "db": str(caminho_db),
        **contadores,
        "linhas_planilha": linhas_planilha,
        "por_motor": por_motor,
        "ocr_simulado_artefatos": ocr_simulado,
        "ocr_real_artefatos": por_motor.get(MOTOR_TESSERACT, 0),
        "aviso_ocr": (
            f"{ocr_simulado} artefato(s) lido(s) por OCR SIMULADO (sidecar .ocr.txt): "
            "a leitura nao vem de motor de OCR real e esta marcada como simulada."
            if ocr_simulado
            else "nenhum artefato usou OCR simulado nesta rodada"
        ),
        "motivos": dict(sorted(motivos_contagem.items(), key=lambda kv: (-kv[1], kv[0]))),
        "arquivos": arquivos_gerados,
        "duracao_s": round(time.perf_counter() - inicio, 3),
        "avisos": avisos,
    }
    if incluir_detalhes:
        resumo["detalhes"] = detalhes

    caminho_resumo.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo


__all__ = ["processar", "NOMES_ARQUIVO"]
