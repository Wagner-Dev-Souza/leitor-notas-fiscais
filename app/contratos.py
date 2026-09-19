"""CONTRATOS CONGELADOS DO PIPELINE - propriedade do PO (soberba).

NAO EDITE ESTE ARQUIVO. Ele e a fronteira de integracao entre as frentes de
execucao. Foi derivado dos documentos de planejamento do proprio squad
(`docs/01-arquitetura.md` secao 3.3 e `docs/02-dados-e-ia.md` secoes 2, 3 e 4):
o payload normalizado, a regra de dinheiro em centavos inteiros, datas ISO e o
schema de idempotencia ja eram decisao tomada pelo time.

Somente biblioteca padrao - importavel sem dependencia externa.

Regras de ouro (nao negociaveis):
  1. Dinheiro NUNCA em float. Sempre inteiro em centavos.
  2. Data sempre ISO `YYYY-MM-DD` (str), ou None.
  3. Campo ausente e None. Nunca 0, nunca string vazia, nunca chute.
  4. `hash_conteudo` (sha256 do binario) e a chave de idempotencia ponta a ponta.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------- enums de texto

CANAL_PDF = "pdf"
CANAL_WHATSAPP = "whatsapp"
CANAL_TELEGRAM = "telegram"
CANAIS = (CANAL_PDF, CANAL_WHATSAPP, CANAL_TELEGRAM)

TIPO_NF = "nf"
TIPO_PEDIDO = "pedido"
TIPO_DESCONHECIDO = "desconhecido"
TIPOS_DOC = (TIPO_NF, TIPO_PEDIDO, TIPO_DESCONHECIDO)

# Decisao de validacao (docs/02 secao 4.4)
STATUS_AUTO_APROVADO = "auto_aprovado"
STATUS_REVISAO_HUMANA = "revisao_humana"
STATUS_REJEITADO = "rejeitado"
STATUS_VALIDACAO = (STATUS_AUTO_APROVADO, STATUS_REVISAO_HUMANA, STATUS_REJEITADO)

# Status do documento no banco (docs/02 secao 3.1)
STATUS_DOC_RECEBIDO = "recebido"
STATUS_DOC_EXTRAIDO = "extraido"
STATUS_DOC_VALIDADO = "validado"
STATUS_DOC_REJEITADO = "rejeitado"
STATUS_DOC_EXCECAO = "excecao"

# Motor de leitura, gravado na trilha de auditoria
MOTOR_PARSER = "parser"
MOTOR_PDFPLUMBER = "pdfplumber"
MOTOR_PYPDF = "pypdf"
MOTOR_OCR_SIMULADO = "ocr_simulado"
MOTOR_TESSERACT = "tesseract"

FORMAS_PAGAMENTO = (
    "dinheiro", "pix", "boleto", "cartao_credito",
    "cartao_debito", "transferencia", "prazo", "outro",
)

# --------------------------------------------------------------- limiares (docs/02 secao 4)

LIMIAR_AUTO_APROVACAO = 0.90        # >= auto-aprova
LIMIAR_REJEICAO = 0.60              # < rejeitado no fluxo automatico
LIMIAR_CAMPO_OBRIGATORIO = 0.80     # nenhum campo obrigatorio abaixo disso
TOLERANCIA_ITENS_CASA_CENTAVOS = 2      # diferenca <= R$ 0,02 -> casa
TOLERANCIA_ITENS_SUSPEITA_CENTAVOS = 10  # <= R$ 0,10 -> suspeita; acima -> divergencia
VALOR_TOTAL_MIN_CENTAVOS = 1
VALOR_TOTAL_MAX_CENTAVOS = 1_000_000_000  # R$ 10.000.000,00

# Motivos de excecao (codigos estaveis, usados em testes)
MOTIVO_CNPJ_INVALIDO = "cnpj_dv_invalido"
MOTIVO_CHAVE_INVALIDA = "chave_acesso_dv_invalido"
MOTIVO_VALOR_AUSENTE = "valor_total_ausente"
MOTIVO_VALOR_FORA_FAIXA = "valor_total_fora_da_faixa"
MOTIVO_DIVERGENCIA_ITENS = "divergencia_soma_itens"
MOTIVO_SUSPEITA_ITENS = "suspeita_soma_itens"
MOTIVO_DATA_IMPLAUSIVEL = "data_implausivel"
MOTIVO_DATA_AMBIGUA = "data_ambigua"
MOTIVO_DOC_ILEGIVEL = "documento_ilegivel"
MOTIVO_SEM_CAMPOS_OBRIGATORIOS = "sem_campos_obrigatorios"
MOTIVO_BAIXA_CONFIANCA = "baixa_confianca"
MOTIVO_POSSIVEL_DUPLICATA = "possivel_duplicata"
MOTIVO_CONFLITO_VALOR = "conflito_valor_mesma_chave"
MOTIVO_INJECAO_SUSPEITA = "texto_instrucao_suspeita"
MOTIVO_TOTAL_SEM_DETALHAMENTO = "total_sem_detalhamento"

# --------------------------------------------------------------- utilidades de hash


def sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def sha256_arquivo(caminho: str | Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def sha256_texto_normalizado(texto: str) -> str:
    """Segunda barreira de deduplicacao (docs/02 secao 3.2).

    Remove espacos, pontuacao, acentos e caixa para que o mesmo conteudo em
    formatos diferentes colapse no mesmo hash.
    """
    import unicodedata

    if not texto:
        return sha256_bytes(b"")
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    limpo = "".join(c for c in sem_acento.lower() if c.isalnum())
    return sha256_bytes(limpo.encode("utf-8"))


# --------------------------------------------------------------- estruturas de entrada


@dataclass
class TextoExtraido:
    """Saida de qualquer leitor de PDF (nativo ou OCR)."""

    texto: str
    paginas: int = 1
    tem_camada_texto: bool = True
    motor: str = MOTOR_PYPDF
    confianca_leitura: float = 1.0
    arquivo: Optional[str] = None


@dataclass
class MensagemBruta:
    """Mensagem normalizada de WhatsApp/Telegram (docs/01 secao 3.2)."""

    canal: str                      # whatsapp | telegram
    id_externo: str                 # wamid.* ou update_id/message_id
    conversa_id: str
    remetente_id: str
    remetente_nome: str
    texto: str
    enviada_em: Optional[str] = None   # ISO 8601
    tipo: str = "texto"
    midia: Optional[dict] = None
    arquivo_origem: Optional[str] = None


@dataclass
class Artefato:
    """Unidade de trabalho ingerida da inbox."""

    tipo_artefato: str              # "pdf" | "mensagem"
    caminho: str
    canal: str
    hash_conteudo: str
    texto: str = ""
    paginas: int = 1
    tem_camada_texto: bool = True
    motor: str = MOTOR_PYPDF
    confianca_leitura: float = 1.0
    mensagem: Optional[MensagemBruta] = None


# --------------------------------------------------------------- estruturas de saida


@dataclass
class Item:
    descricao: str
    quantidade: Any                       # Decimal como str; None se ausente
    unidade: Optional[str] = None
    valor_unitario_centavos: Optional[int] = None
    valor_total_centavos: Optional[int] = None
    confianca: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["quantidade"] = None if self.quantidade is None else str(self.quantidade)
        return d


@dataclass
class Extracao:
    """Payload normalizado - contrato central do sistema (docs/01 secao 3.3).

    E a saida do extrator, a entrada do validador e a base da linha na planilha.
    Nenhum componente troca dado fora deste formato.
    """

    documento_id: str
    origem_canal: str
    tipo_documento: str = TIPO_DESCONHECIDO

    numero_pedido: Optional[str] = None
    chave_acesso_nf: Optional[str] = None
    emitente_nome: Optional[str] = None
    emitente_cnpj: Optional[str] = None       # 14 digitos, sem pontuacao
    data_emissao: Optional[str] = None        # ISO
    data_vencimento: Optional[str] = None     # ISO
    valor_total_centavos: Optional[int] = None
    desconto_centavos: Optional[int] = None
    frete_centavos: Optional[int] = None
    forma_pagamento: Optional[str] = None
    forma_pagamento_raw: Optional[str] = None
    observacoes: Optional[str] = None

    itens: list[Item] = field(default_factory=list)

    # controle
    origem_remetente: Optional[str] = None
    recebido_em: Optional[str] = None
    arquivo_origem: Optional[str] = None
    hash_conteudo: Optional[str] = None
    texto_norm_sha256: Optional[str] = None
    evidencia: dict = field(default_factory=dict)      # campo -> trecho literal
    confianca_geral: float = 0.0
    confianca_por_campo: dict = field(default_factory=dict)
    status_validacao: str = STATUS_REVISAO_HUMANA
    motivos: list[str] = field(default_factory=list)
    motor: str = MOTOR_PARSER
    ocr_usado: bool = False
    template_versao: str = "extrator-v1"

    # -------------------------------------------------- helpers de dominio

    def soma_itens_centavos(self) -> Optional[int]:
        """SUM(quantidade x valor_unitario) em centavos, arredondado ao centavo."""
        if not self.itens:
            return None
        total = 0
        for it in self.itens:
            if it.quantidade is None or it.valor_unitario_centavos is None:
                return None
            from decimal import Decimal, ROUND_HALF_UP

            q = Decimal(str(it.quantidade))
            bruto = q * Decimal(int(it.valor_unitario_centavos))
            total += int(bruto.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return total

    def total_calculado_centavos(self) -> Optional[int]:
        """soma_itens - desconto + frete (docs/02 secao 4.2)."""
        soma = self.soma_itens_centavos()
        if soma is None:
            return None
        return soma - int(self.desconto_centavos or 0) + int(self.frete_centavos or 0)

    def diferenca_itens_centavos(self) -> Optional[int]:
        """|total_calculado - valor_total_lido| em centavos."""
        calc = self.total_calculado_centavos()
        if calc is None or self.valor_total_centavos is None:
            return None
        return abs(calc - int(self.valor_total_centavos))

    def chave_dedupe(self) -> tuple:
        """Chave natural de deduplicacao em ordem de precedencia (docs/02 secao 3.3).

        A ordem importa: chave de acesso > fingerprint completo > fingerprint fraco.
        """
        if self.chave_acesso_nf:
            return ("chave", self.chave_acesso_nf)
        if self.emitente_cnpj and self.numero_pedido and self.data_emissao \
                and self.valor_total_centavos is not None:
            return ("fingerprint", self.emitente_cnpj, self.numero_pedido,
                    self.data_emissao, self.valor_total_centavos)
        if self.emitente_cnpj and self.data_emissao and self.valor_total_centavos is not None:
            return ("fraco", self.emitente_cnpj, self.data_emissao,
                    self.valor_total_centavos)
        return ("sem_chave", self.documento_id)

    def to_dict(self) -> dict:
        """Payload normalizado exatamente no schema 3.3 do doc 01."""
        return {
            "schema_version": SCHEMA_VERSION,
            "documento_id": self.documento_id,
            "origem": {
                "canal": self.origem_canal,
                "remetente": self.origem_remetente,
                "recebido_em": self.recebido_em,
                "arquivo": self.arquivo_origem,
            },
            "tipo_documento": self.tipo_documento,
            "campos": {
                "numero_pedido": self.numero_pedido,
                "chave_acesso_nf": self.chave_acesso_nf,
                "emitente": {"nome": self.emitente_nome, "cnpj": self.emitente_cnpj},
                "data_emissao": self.data_emissao,
                "data_vencimento": self.data_vencimento,
                "valor_total_centavos": self.valor_total_centavos,
                "desconto_centavos": self.desconto_centavos,
                "frete_centavos": self.frete_centavos,
                "forma_pagamento": self.forma_pagamento,
                "forma_pagamento_raw": self.forma_pagamento_raw,
                "observacoes": self.observacoes,
            },
            "itens": [it.to_dict() for it in self.itens],
            "moeda": "BRL",
            "confianca": {
                "geral": round(self.confianca_geral, 4),
                "por_campo": {k: round(v, 4) for k, v in self.confianca_por_campo.items()},
            },
            "validacao": {
                "status": self.status_validacao,
                "motivos": list(self.motivos),
            },
            "extracao": {
                "modelo": "parser-deterministico",
                "versao_prompt": self.template_versao,
                "ocr_usado": self.ocr_usado,
                "motor": self.motor,
                "tokens_entrada": 0,
                "tokens_saida": 0,
            },
            "evidencia": dict(self.evidencia),
            "hash_conteudo": self.hash_conteudo,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)


# --------------------------------------------------------------- contrato da planilha

# Ordem e nomes das colunas da planilha de controle financeiro. CONGELADO:
# os testes e o README dependem destes nomes.
COLUNAS_PLANILHA = (
    "data_processamento",
    "documento_id",
    "pedido_id",
    "origem",
    "tipo_documento",
    "numero_pedido",
    "emitente_nome",
    "emitente_cnpj",
    "data_emissao",
    "data_vencimento",
    "valor_total",
    "valor_total_centavos",
    "forma_pagamento",
    "qtd_itens",
    "chave_acesso_nf",
    "confianca",
    "status_validacao",
    "hash_conteudo",
    "arquivo_origem",
    "row_id_planilha",
)


def formatar_brl(centavos: Optional[int]) -> str:
    """1234567 -> '12345,67' (formato BR, sem simbolo - o simbolo vai no cabecalho)."""
    if centavos is None:
        return ""
    s = str(abs(int(centavos))).rjust(3, "0")
    return f"{'-' if centavos < 0 else ''}{s[:-2]},{s[-2:]}"


def formatar_cnpj(cnpj14: Optional[str]) -> str:
    if not cnpj14 or len(cnpj14) != 14:
        return cnpj14 or ""
    return f"{cnpj14[0:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:14]}"
