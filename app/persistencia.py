"""Persistencia, idempotencia, decisao de validacao e planilha - frente F2 (dono: gula).

Implementa `docs/02-dados-e-ia.md` secoes 3 (modelo de dados, idempotencia,
deduplicacao e escrita na planilha) e 4 (rejeicao automatica, reconciliacao
aritmetica, juizo de qualidade, score de confianca) e as assinaturas congeladas da
secao 5 de `docs/execucao/00-contrato-execucao.md`.

Regras de ouro:

1. Dinheiro **nunca** em float: centavos sao `INTEGER`; `valor_total` na planilha e
   a string BR de `contratos.formatar_brl`.
2. A planilha e **destino**, nunca fonte da verdade: a fonte e `pedidos`/`itens_pedido`.
3. So entra na planilha o pedido que `decidir()` marcou `auto_aprovado`
   (ou que um humano liberou como `validado`). Rejeitado e revisao ficam fora.
4. Rejeitar nao e apagar: documento, extrato e motivo continuam no banco e na fila.

Decisoes de projeto documentadas (para o PO revisar se quiser):

- **`documento_id` e `pedido_id` sao deterministicos** (`doc_<sha256[:24]>`,
  `ped_<sha256(identidade)[:16]>`) para que a mesma peca gere a mesma linha mesmo
  com banco recriado. Sem isso a planilha mudaria de identificador entre rodadas.
- **Indice UNIQUE de fingerprint NAO inclui `valor_total_centavos`**: a identidade e
  `(emitente_cnpj, numero_pedido, data_emissao)`. Assim o "fingerprint igual com valor
  diferente" (contrato secao 6.6) e detectavel como conflito em vez de virar uma
  segunda linha - e a linha existente **nao** e sobrescrita.
- **Score do documento e recalculado aqui** pela media ponderada da secao 4.4 do doc 02
  (peso 3 para `valor_total`/`emitente_cnpj`, 2 para datas, 1 para o resto). Os scores
  por campo do extrator sao respeitados quando informados; a corroboracao independente
  (`chave_acesso` conferindo CNPJ/ano-mes/numero, aritmetica dos itens fechando) eleva o
  fator de consenso para 1,00 - "duas fontes independentes concordam" (4.4) e "chave
  valida permite validacao cruzada" (1.2). Documento lido por OCR tem o score limitado
  a 0,65 (base_motor de OCR, 4.4), nunca auto-aprovado.
- **`data_ambigua` nao derruba o score**: entra como motivo (visivel na fila/painel),
  porque qualquer reducao em campo de peso 2 empurraria documento correto para fora do
  portao de 0,90 - e o doc 02 4.3 diz que a data ambigua "nao bloqueia sozinho".
- **Divergencia de itens > R$ 0,10 -> `revisao_humana`** (nao rejeicao): contrato secao 5,
  doc 02 4.2 e caso B2 mandam revisao humana obrigatoria, sem escrever o valor.
- **Soma de itens que nao pode ser calculada -> `MOTIVO_TOTAL_SEM_DETALHAMENTO`** (emenda do
  PO de 2026-09-19, contrato secao 5): item sem quantidade ou sem valor unitario, itens
  ausentes ou parciais nao sao "divergencia" - divergencia exige diferenca calculada.
- **Documento com injecao de prompt -> `revisao_humana`** com
  `MOTIVO_INJECAO_SUSPEITA`: o valor lido e preservado (nunca obedecer a instrucao do
  documento), mas documento hostil nao publica sozinho.
- **Pedido rejeitado continua em `pedidos`** com `status='rejeitado'` (rastreabilidade);
  o que o doc 02 4.1 proibe e a linha na planilha, e `escrever_ledger` filtra por status.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Optional

from . import contratos
from . import normaliza

__all__ = [
    "abrir_db",
    "registrar_documento",
    "decidir",
    "gravar_extracao",
    "escrever_ledger",
    "registrar_auditoria",
    "registrar_excecao",
    "atualizar_documento",
]

STATUS_VALIDADO_PLANILHA = (contratos.STATUS_AUTO_APROVADO, contratos.STATUS_DOC_VALIDADO)

# ------------------------------------------------------------------ schema 3.1 do doc 02

SCHEMA_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS documentos (
        id                 TEXT PRIMARY KEY,          -- documento_id (doc_<hash>)
        origem             TEXT NOT NULL,             -- pdf | whatsapp | telegram
        arquivo_uri        TEXT,
        mime               TEXT,
        paginas            INTEGER,
        sha256_conteudo    TEXT NOT NULL UNIQUE,      -- 1a barreira de idempotencia
        texto_norm_sha256  TEXT,                      -- 2a barreira (3.2)
        tipo_doc           TEXT,
        recebido_em        TEXT,
        processado_em      TEXT,
        status             TEXT NOT NULL DEFAULT 'recebido'
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_documentos_texto_norm ON documentos(texto_norm_sha256)",
    "CREATE INDEX IF NOT EXISTS ix_documentos_status ON documentos(status)",
    """
    CREATE TABLE IF NOT EXISTS mensagens (
        id            TEXT PRIMARY KEY,               -- '<provedor>:<id_externo>'
        provedor      TEXT NOT NULL,                  -- whatsapp | telegram
        id_externo    TEXT NOT NULL,
        conversa_id   TEXT,
        remetente     TEXT,
        texto         TEXT,
        enviada_em    TEXT,
        recebida_em   TEXT,
        documento_id  TEXT REFERENCES documentos(id),
        UNIQUE (provedor, id_externo)                 -- reentrega de webhook
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pedidos (
        id                    TEXT PRIMARY KEY,       -- pedido_id (ped_<hash>)
        documento_id          TEXT REFERENCES documentos(id),
        mensagem_id           TEXT REFERENCES mensagens(id),
        chave_acesso          TEXT,
        numero_pedido         TEXT,
        emitente_nome         TEXT,
        emitente_cnpj         TEXT,                   -- 14 digitos, sem pontuacao
        data_emissao          TEXT,                   -- ISO
        data_vencimento       TEXT,                   -- ISO
        valor_total_centavos  INTEGER,                -- dinheiro em centavos
        desconto_centavos     INTEGER,
        frete_centavos        INTEGER,
        forma_pagamento       TEXT,
        confianca_doc         REAL,
        status                TEXT,                   -- auto_aprovado|revisao_humana|rejeitado|validado
        row_id_planilha       TEXT,                   -- linha fisica na planilha
        origem                TEXT,
        tipo_documento        TEXT,
        arquivo_origem        TEXT,
        hash_conteudo         TEXT,
        criado_em             TEXT,
        atualizado_em         TEXT,
        data_processamento    TEXT                    -- 1a escrita na planilha (estavel)
    )
    """,
    # identidade nacional: chave de acesso unica quando presente
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_pedidos_chave
        ON pedidos(chave_acesso) WHERE chave_acesso IS NOT NULL
    """,
    # fingerprint (cnpj, numero, data) - sem o valor, de proposito (3.3)
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_pedidos_fingerprint
        ON pedidos(emitente_cnpj, numero_pedido, data_emissao)
        WHERE chave_acesso IS NULL
          AND numero_pedido IS NOT NULL
          AND emitente_cnpj IS NOT NULL
          AND data_emissao IS NOT NULL
    """,
    # fingerprint fraco (sem numero do pedido): mesma data + valor
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_pedidos_fraco
        ON pedidos(emitente_cnpj, data_emissao, valor_total_centavos)
        WHERE chave_acesso IS NULL
          AND numero_pedido IS NULL
          AND emitente_cnpj IS NOT NULL
          AND data_emissao IS NOT NULL
          AND valor_total_centavos IS NOT NULL
    """,
    "CREATE INDEX IF NOT EXISTS ix_pedidos_status ON pedidos(status)",
    "CREATE INDEX IF NOT EXISTS ix_pedidos_documento ON pedidos(documento_id)",
    "CREATE INDEX IF NOT EXISTS ix_pedidos_emissao ON pedidos(emitente_cnpj, data_emissao, valor_total_centavos)",
    """
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id              TEXT NOT NULL REFERENCES pedidos(id),
        linha                  INTEGER,
        descricao              TEXT,
        quantidade             TEXT,                  -- Decimal como texto (12,4)
        valor_unitario         INTEGER,               -- CENTAVOS (nunca float)
        valor_linha_centavos   INTEGER,               -- CENTAVOS
        confianca              REAL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_itens_pedido ON itens_pedido(pedido_id)",
    """
    CREATE TABLE IF NOT EXISTS fornecedores (
        id                TEXT PRIMARY KEY,           -- for_<cnpj>
        cnpj              TEXT NOT NULL UNIQUE,
        razao             TEXT,
        nome_fantasia     TEXT,
        template_id       TEXT,
        primeira_vez_em   TEXT,
        ultimo_doc_em     TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS templates (
        id             TEXT PRIMARY KEY,
        fornecedor_id  TEXT REFERENCES fornecedores(id),
        versao         TEXT,
        regex_json     TEXT,
        ativo_em       TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS log_extracao (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        documento_id    TEXT REFERENCES documentos(id),
        etapa           TEXT,
        motor           TEXT,                         -- parser | ocr | llm ...
        modelo_versao   TEXT,
        prompt_versao   TEXT,
        tokens_in       INTEGER,
        tokens_out      INTEGER,
        latencia_ms     INTEGER,
        campos_json     TEXT,
        confianca_json  TEXT,
        criado_em       TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_log_documento ON log_extracao(documento_id)",
    """
    CREATE TABLE IF NOT EXISTS fila_excecoes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        documento_id    TEXT REFERENCES documentos(id),
        pedido_id       TEXT REFERENCES pedidos(id),
        motivo_codigo   TEXT NOT NULL,
        detalhe         TEXT,
        valor_suspeito  INTEGER,
        status          TEXT NOT NULL DEFAULT 'aberta',   -- aberta|em_analise|resolvida
        aberta_em       TEXT,
        resolvida_em    TEXT,
        resolvida_por   TEXT,
        decisao         TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fila_status ON fila_excecoes(status, motivo_codigo)",
)

COLUNAS_DOCUMENTO_ATUALIZAVEIS = (
    "origem", "arquivo_uri", "mime", "paginas", "texto_norm_sha256",
    "tipo_doc", "recebido_em", "processado_em", "status",
)

# ------------------------------------------------------------------ limiares e pesos (doc 02 secao 4.4)

PESOS_CAMPO: dict[str, int] = {
    "valor_total_centavos": 3,
    "emitente_cnpj": 3,
    "data_emissao": 2,
    "data_vencimento": 2,
    "numero_pedido": 1,
    "chave_acesso_nf": 1,
    "forma_pagamento": 1,
    "itens": 1,
}
CAMPOS_OBRIGATORIOS = ("valor_total_centavos", "emitente_cnpj", "data_emissao")
BASE_MOTOR_ANCORA = 0.95
BASE_MOTOR_SEM_ANCORA = 0.80
BASE_MOTOR_OCR = 0.65
FATOR_CONSENSO_CORROBORADO = 1.00
FATOR_CONSENSO_EVIDENCIA = 0.85
FATOR_CONSENSO_SEM_EVIDENCIA = 0.60

# nomes alternativos aceitos em `evidencia` / `confianca_por_campo` (o extrator e
# dono dessas chaves; aceitamos as variacoes previsiveis para nao gerar falso baixo)
_ALIASES = {
    "valor_total_centavos": ("valor_total_centavos", "valor_total"),
    "emitente_cnpj": ("emitente_cnpj", "cnpj"),
    "chave_acesso_nf": ("chave_acesso_nf", "chave_acesso", "chave"),
    "data_emissao": ("data_emissao", "emissao"),
    "data_vencimento": ("data_vencimento", "vencimento"),
    "numero_pedido": ("numero_pedido", "pedido", "numero"),
    "forma_pagamento": ("forma_pagamento", "pagamento"),
    "itens": ("itens", "itens_descricao", "descricao_itens"),
}

_MOTORES_OCR = (contratos.MOTOR_OCR_SIMULADO, contratos.MOTOR_TESSERACT)


def _agora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ------------------------------------------------------------------ conexao e schema


def abrir_db(caminho: Any) -> sqlite3.Connection:
    """Abre (criando se preciso) o SQLite com o schema da secao 3.1 do doc 02.

    Idempotente: `CREATE ... IF NOT EXISTS` em tudo - rodar de novo nao quebra nem
    apaga dado. Devolve conexao com `row_factory = sqlite3.Row` e FKs ligadas.
    """
    if caminho is None:
        raise ValueError("caminho do banco obrigatorio")
    texto = str(caminho)
    if texto != ":memory:":
        alvo = Path(texto)
        if alvo.parent and str(alvo.parent) not in ("", "."):
            alvo.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(texto)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    with conn:
        for ddl in SCHEMA_DDL:
            conn.execute(ddl)
    return conn


def atualizar_documento(conn: sqlite3.Connection, documento_id: str, **campos: Any) -> None:
    """Atualiza colunas permitidas de `documentos` (uso do pipeline/extracao)."""
    desconhecidos = set(campos) - set(COLUNAS_DOCUMENTO_ATUALIZAVEIS)
    if desconhecidos:
        raise ValueError(f"coluna nao atualizavel em documentos: {sorted(desconhecidos)}")
    if not campos:
        return
    sets = ", ".join(f"{c} = ?" for c in campos)
    with conn:
        conn.execute(
            f"UPDATE documentos SET {sets} WHERE id = ?",
            (*campos.values(), documento_id),
        )


# ------------------------------------------------------------------ documento (idempotencia)

def _id_documento(sha256: str, artefato: Any) -> str:
    if sha256:
        return "doc_" + sha256[:24]
    base = f"{getattr(artefato, 'canal', '')}|{getattr(artefato, 'caminho', '')}|{id(artefato)}"
    return "doc_" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def _mime_de(caminho: Any) -> Optional[str]:
    if not caminho:
        return None
    sufixo = Path(str(caminho)).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".jsonl": "application/jsonl",
        ".json": "application/json",
        ".txt": "text/plain",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(sufixo)


def registrar_documento(conn: sqlite3.Connection, artefato: Any) -> tuple[str, bool]:
    """`(documento_id, dedupe)`.

    Barreiras na ordem do doc 02 secao 3.2:
      1. `sha256_conteudo` (mesmo binario reenviado);
      2. `(provedor, id_externo)` para mensagem (reentrega de webhook);
      3. `texto_norm_sha256` para PDF com texto longo (mesmo conteudo, arquivo diferente).
    """
    sha = (getattr(artefato, "hash_conteudo", None) or "").strip()
    mensagem = getattr(artefato, "mensagem", None)
    texto = getattr(artefato, "texto", None) or ""
    texto_norm = contratos.sha256_texto_normalizado(texto) if texto.strip() else None

    # 1) mensagem reentregue: a identidade dela e (provedor, id_externo)
    if mensagem is not None and getattr(mensagem, "id_externo", None):
        linha = conn.execute(
            "SELECT documento_id FROM mensagens WHERE provedor = ? AND id_externo = ?",
            (mensagem.canal, mensagem.id_externo),
        ).fetchone()
        if linha is not None and linha["documento_id"]:
            return (linha["documento_id"], True)

    # 2) mesmo binario
    if sha:
        linha = conn.execute(
            "SELECT id FROM documentos WHERE sha256_conteudo = ?", (sha,)
        ).fetchone()
        if linha is not None:
            return (linha["id"], True)

    # 3) mesmo conteudo em arquivo diferente (PDF ou imagem com texto substancial: evita
    #    colidir mensagens curtas e legitimamente iguais). E por aqui que a MESMA nota
    #    chegando como PDF e como foto vira uma linha so - os bytes diferem, o texto nao.
    if (
        texto_norm
        and getattr(artefato, "tipo_artefato", "") in ("pdf", "imagem")
        and len(texto.strip()) >= 200
    ):
        linha = conn.execute(
            "SELECT id FROM documentos WHERE texto_norm_sha256 = ? LIMIT 1", (texto_norm,)
        ).fetchone()
        if linha is not None:
            return (linha["id"], True)

    documento_id = _id_documento(sha, artefato)
    agora = _agora_iso()
    with conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO documentos (
                id, origem, arquivo_uri, mime, paginas, sha256_conteudo,
                texto_norm_sha256, tipo_doc, recebido_em, processado_em, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                documento_id,
                getattr(artefato, "canal", None) or "",
                str(getattr(artefato, "caminho", "") or ""),
                _mime_de(getattr(artefato, "caminho", None)),
                int(getattr(artefato, "paginas", 1) or 1),
                sha or documento_id,
                texto_norm,
                contratos.TIPO_DESCONHECIDO,
                agora,
                contratos.STATUS_DOC_RECEBIDO,
            ),
        )
        if cursor.rowcount == 0:
            # perdeu a corrida ou caiu no UNIQUE de sha256: devolve o dono existente
            linha = conn.execute(
                "SELECT id FROM documentos WHERE sha256_conteudo = ?", (sha or documento_id,)
            ).fetchone()
            if linha is None:
                linha = conn.execute(
                    "SELECT id FROM documentos WHERE id = ?", (documento_id,)
                ).fetchone()
            return (linha["id"], True)

        if mensagem is not None and getattr(mensagem, "id_externo", None):
            conn.execute(
                """
                INSERT OR IGNORE INTO mensagens (
                    id, provedor, id_externo, conversa_id, remetente, texto,
                    enviada_em, recebida_em, documento_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{mensagem.canal}:{mensagem.id_externo}",
                    mensagem.canal,
                    mensagem.id_externo,
                    getattr(mensagem, "conversa_id", None),
                    getattr(mensagem, "remetente_id", None) or getattr(mensagem, "remetente_nome", None),
                    getattr(mensagem, "texto", None),
                    getattr(mensagem, "enviada_em", None),
                    agora,
                    documento_id,
                ),
            )
    return (documento_id, False)


# ------------------------------------------------------------------ decisao (doc 02 secao 4)


def _aamm_da_chave(chave: str) -> tuple[Optional[int], Optional[int]]:
    if len(chave) != 44:
        return (None, None)
    ano = 2000 + int(chave[2:4])
    mes = int(chave[4:6])
    if not 1 <= mes <= 12:
        return (None, None)
    return (ano, mes)


def _ano_mes(iso: Any) -> tuple[Optional[int], Optional[int]]:
    if not iso:
        return (None, None)
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return (None, None)
    return (d.year, d.month)


def _numeros_iguais(a: Any, b: Any) -> bool:
    da, db = normaliza.so_digitos(a), normaliza.so_digitos(b)
    if not da or not db:
        return False
    return int(da) == int(db)


def _tem(mapa: dict, campo: str) -> bool:
    for chave in _ALIASES.get(campo, (campo,)):
        valor = mapa.get(chave)
        if valor is not None and (not isinstance(valor, str) or valor.strip()):
            return True
    return False


def _base_extrator(extracao: Any, campo: str) -> Optional[float]:
    confiancas = getattr(extracao, "confianca_por_campo", None) or {}
    for chave in _ALIASES.get(campo, (campo,)):
        valor = confiancas.get(chave)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            continue
        if 0.0 < float(valor) <= 1.0:
            return float(valor)
    return None


def _contexto(extracao: Any) -> dict:
    """Calcula o que o score precisa: presenca, checksum e corroboracao independente."""
    evidencia = dict(getattr(extracao, "evidencia", None) or {})
    cnpj14, cnpj_dv = normaliza.normalizar_cnpj(getattr(extracao, "emitente_cnpj", None))
    chave_presente = bool(getattr(extracao, "chave_acesso_nf", None))
    chave_ok = chave_presente and normaliza.validar_chave_nf_dv(extracao.chave_acesso_nf)
    chave = normaliza.so_digitos(extracao.chave_acesso_nf) if chave_ok else ""

    itens = list(getattr(extracao, "itens", None) or [])
    dif = extracao.diferenca_itens_centavos()
    itens_completos = bool(itens) and dif is not None
    aritmetica_fecha = itens_completos and dif <= contratos.TOLERANCIA_ITENS_CASA_CENTAVOS

    emissao_ok = normaliza.data_plausivel(getattr(extracao, "data_emissao", None))
    vencimento = getattr(extracao, "data_vencimento", None)
    vencimento_ok = normaliza.data_plausivel(vencimento)
    if vencimento and getattr(extracao, "data_emissao", None) and vencimento_ok:
        if str(vencimento)[:10] < str(extracao.data_emissao)[:10]:
            vencimento_ok = False

    ano_chave, mes_chave = _aamm_da_chave(chave)
    ano_doc, mes_doc = _ano_mes(getattr(extracao, "data_emissao", None))

    presentes = {
        "valor_total_centavos": getattr(extracao, "valor_total_centavos", None) is not None,
        "emitente_cnpj": cnpj14 is not None,
        "data_emissao": bool(getattr(extracao, "data_emissao", None)),
        "data_vencimento": bool(vencimento),
        "numero_pedido": bool(getattr(extracao, "numero_pedido", None)),
        "chave_acesso_nf": chave_presente,
        "forma_pagamento": bool(getattr(extracao, "forma_pagamento", None)),
        "itens": bool(itens),
    }
    corroborado = {
        "valor_total_centavos": aritmetica_fecha,
        "itens": aritmetica_fecha,
        "emitente_cnpj": bool(chave) and chave[6:20] == (cnpj14 or ""),
        "data_emissao": bool(chave) and (ano_chave, mes_chave) == (ano_doc, mes_doc) and ano_doc is not None,
        "numero_pedido": bool(chave) and _numeros_iguais(chave[25:34], getattr(extracao, "numero_pedido", None)),
    }
    # fator_checksum (4.4): 1,00 passou | 0,00 falhou | 0,50 quando o checksum EXISTE
    # mas ficou inconclusivo (itens parciais). Campo que nao tem checksum por natureza
    # (numero, forma) e neutro (1,00): penalizar 0,5 ali derrubaria toda nota limpa para
    # fora do portao de 0,90 e tornaria o proprio limiar do doc 02 inalcancavel.
    checksum = {
        "valor_total_centavos": 1.0 if aritmetica_fecha else (0.5 if itens and not itens_completos else 1.0),
        "itens": 1.0 if aritmetica_fecha else (0.5 if itens and not itens_completos else 1.0),
        "emitente_cnpj": 1.0 if cnpj_dv else (0.0 if cnpj14 else 0.5),
        "data_emissao": 1.0 if emissao_ok else (0.0 if getattr(extracao, "data_emissao", None) else 0.5),
        "data_vencimento": 1.0 if vencimento_ok else (0.0 if vencimento else 0.5),
        "chave_acesso_nf": 1.0 if chave_ok else (0.0 if chave_presente else 0.5),
        "numero_pedido": 1.0,
        "forma_pagamento": 1.0,
    }
    ocr = bool(getattr(extracao, "ocr_usado", False)) or getattr(extracao, "motor", None) in _MOTORES_OCR
    return {
        "evidencia": evidencia,
        "cnpj14": cnpj14,
        "cnpj_dv": cnpj_dv,
        "chave": chave,
        "chave_ok": chave_ok,
        "dif": dif,
        "itens_completos": itens_completos,
        "aritmetica_fecha": aritmetica_fecha,
        "presentes": presentes,
        "corroborado": corroborado,
        "checksum": checksum,
        "ocr": ocr,
    }


def _score_campo(extracao: Any, campo: str, ctx: dict) -> float:
    """`base_motor x fator_checksum x fator_coerencia x fator_consenso` (doc 02 4.4)."""
    tem_evidencia = _tem(ctx["evidencia"], campo)
    corroborado = bool(ctx["corroborado"].get(campo))
    checksum = float(ctx["checksum"].get(campo, 0.5))
    ocr = bool(ctx["ocr"])

    informado = _base_extrator(extracao, campo)
    if informado is not None:
        score = informado
    else:
        base = BASE_MOTOR_OCR if ocr else (BASE_MOTOR_ANCORA if tem_evidencia else BASE_MOTOR_SEM_ANCORA)
        if corroborado:
            consenso = FATOR_CONSENSO_CORROBORADO
        else:
            consenso = FATOR_CONSENSO_EVIDENCIA if tem_evidencia else FATOR_CONSENSO_SEM_EVIDENCIA
        score = base * checksum * consenso

    if corroborado and checksum > 0.0:
        # duas fontes independentes concordam: consenso 1,00 (4.4) + validacao cruzada
        # pela chave de acesso (1.2). Nunca promove leitura de OCR.
        score = max(score, BASE_MOTOR_ANCORA)
    if ocr:
        score = min(score, BASE_MOTOR_OCR)
    return round(min(max(score, 0.0), 1.0), 4)


def _score_documento(extracao: Any, ctx: dict) -> tuple[float, dict, list[str]]:
    por_campo: dict[str, float] = {}
    fracos: list[str] = []
    soma, peso_total = 0.0, 0
    tipo_pedido = getattr(extracao, "tipo_documento", None) == contratos.TIPO_PEDIDO

    for campo, peso in PESOS_CAMPO.items():
        obrigatorio = campo in CAMPOS_OBRIGATORIOS or (campo == "numero_pedido" and tipo_pedido)
        presente = bool(ctx["presentes"].get(campo))
        if not presente and not obrigatorio:
            continue
        score = _score_campo(extracao, campo, ctx) if presente else 0.0
        por_campo[campo] = score
        if obrigatorio and score < contratos.LIMIAR_CAMPO_OBRIGATORIO:
            fracos.append(campo)
        soma += peso * score
        peso_total += peso

    geral = round(soma / peso_total, 4) if peso_total else 0.0
    return geral, por_campo, fracos


def decidir(extracao: Any) -> tuple[str, list[str]]:
    """`(status_validacao, motivos)` - doc 02 secao 4.

    Rejeicao automatica (4.1) > bloqueios de publicacao (4.2/4.3/4.5) > score (4.4).
    Escreve de volta na `Extracao`: `status_validacao`, `motivos`, `confianca_geral` e
    `confianca_por_campo` (o score e **calculado** aqui, nao "perguntado" ao extrator).
    """
    motivos: list[str] = []

    def add(motivo: Optional[str]) -> None:
        if motivo and motivo not in motivos:
            motivos.append(motivo)

    # o extrator ja pode ter sinalizado coisas (ex.: injecao detectada no texto)
    for motivo in list(getattr(extracao, "motivos", None) or []):
        add(motivo)

    ctx = _contexto(extracao)
    rejeicoes: list[str] = []
    bloqueios: list[str] = []

    tem_algum_dado = any(ctx["presentes"].values())

    # 1) documento ilegivel / sem nenhum campo (4.1)
    if not tem_algum_dado:
        vazio = float(getattr(extracao, "confianca_geral", 0.0) or 0.0) <= 0.0
        rejeicoes.append(contratos.MOTIVO_DOC_ILEGIVEL if vazio else contratos.MOTIVO_SEM_CAMPOS_OBRIGATORIOS)

    # 2) CNPJ e chave: DV invalido nunca passa (4.1)
    if getattr(extracao, "emitente_cnpj", None) is not None and not ctx["cnpj_dv"]:
        rejeicoes.append(contratos.MOTIVO_CNPJ_INVALIDO)
    if getattr(extracao, "chave_acesso_nf", None) is not None and not ctx["chave_ok"]:
        rejeicoes.append(contratos.MOTIVO_CHAVE_INVALIDA)

    # 3) valor total: ausente e fora da faixa (4.1)
    valor = getattr(extracao, "valor_total_centavos", None)
    if valor is None and not rejeicoes:
        rejeicoes.append(contratos.MOTIVO_VALOR_AUSENTE)
    elif valor is not None and not (
        contratos.VALOR_TOTAL_MIN_CENTAVOS <= int(valor) <= contratos.VALOR_TOTAL_MAX_CENTAVOS
    ):
        rejeicoes.append(contratos.MOTIVO_VALOR_FORA_FAIXA)

    # 4) janela de plausibilidade das datas (4.1) e vencimento antes da emissao (4.3)
    emissao = getattr(extracao, "data_emissao", None)
    vencimento = getattr(extracao, "data_vencimento", None)
    if emissao and not normaliza.data_plausivel(emissao):
        rejeicoes.append(contratos.MOTIVO_DATA_IMPLAUSIVEL)
    if emissao and vencimento and str(vencimento)[:10] < str(emissao)[:10]:
        bloqueios.append(contratos.MOTIVO_DATA_IMPLAUSIVEL)

    # 5) data ambigua (4.3): sinaliza, nao bloqueia sozinho
    bruto_emissao = None
    for chave_ev in _ALIASES["data_emissao"]:
        bruto_emissao = ctx["evidencia"].get(chave_ev)
        if isinstance(bruto_emissao, str):
            break
    if isinstance(bruto_emissao, str) and normaliza.normalizar_data(bruto_emissao)[1]:
        add(contratos.MOTIVO_DATA_AMBIGUA)

    # 6) reconciliacao aritmetica dos itens (4.2 + emenda do PO de 2026-09-19)
    # `MOTIVO_DIVERGENCIA_ITENS` exige diferenca **calculada**. Quando a soma nao pode
    # ser calculada (item sem quantidade ou sem valor unitario, itens ausentes ou
    # parciais), o motivo e `MOTIVO_TOTAL_SEM_DETALHAMENTO` - nao se chama "divergencia"
    # aquilo que nao foi medido (dois codigos para o mesmo fato quebram a triagem).
    if ctx["itens_completos"]:
        dif = int(ctx["dif"])
        if dif <= contratos.TOLERANCIA_ITENS_CASA_CENTAVOS:
            pass
        elif dif <= contratos.TOLERANCIA_ITENS_SUSPEITA_CENTAVOS:
            bloqueios.append(contratos.MOTIVO_SUSPEITA_ITENS)
        else:
            bloqueios.append(contratos.MOTIVO_DIVERGENCIA_ITENS)
    elif valor is not None:
        bloqueios.append(contratos.MOTIVO_TOTAL_SEM_DETALHAMENTO)

    # 7) regra dura do dinheiro (4.5): ancora deterministica ou aritmetica que fecha
    if valor is not None and not rejeicoes:
        ancora = _tem(ctx["evidencia"], "valor_total_centavos")
        conf_valor = _base_extrator(extracao, "valor_total_centavos") or 0.0
        if not (ancora or ctx["aritmetica_fecha"] or conf_valor >= contratos.LIMIAR_CAMPO_OBRIGATORIO):
            if contratos.MOTIVO_SUSPEITA_ITENS not in bloqueios:
                bloqueios.append(contratos.MOTIVO_SUSPEITA_ITENS)

    # 8) injecao de prompt: nunca obedecer e nunca publicar sozinho
    if contratos.MOTIVO_INJECAO_SUSPEITA not in motivos:
        alvos = [bruto_emissao] if isinstance(bruto_emissao, str) else []
        alvos += [v for v in ctx["evidencia"].values() if isinstance(v, str)]
        obs = getattr(extracao, "observacoes", None)
        if isinstance(obs, str):
            alvos.append(obs)
        if normaliza.detectar_injecao(" \n ".join(alvos)):
            add(contratos.MOTIVO_INJECAO_SUSPEITA)
    if contratos.MOTIVO_INJECAO_SUSPEITA in motivos:
        bloqueios.append(contratos.MOTIVO_INJECAO_SUSPEITA)

    # 9) score (4.4)
    geral, por_campo, fracos = _score_documento(extracao, ctx)

    for motivo in rejeicoes + bloqueios:
        add(motivo)

    if rejeicoes:
        status = contratos.STATUS_REJEITADO
    elif bloqueios:
        status = contratos.STATUS_REVISAO_HUMANA
    elif geral >= contratos.LIMIAR_AUTO_APROVACAO and not fracos:
        status = contratos.STATUS_AUTO_APROVADO
    elif geral >= contratos.LIMIAR_REJEICAO:
        status = contratos.STATUS_REVISAO_HUMANA
        add(contratos.MOTIVO_BAIXA_CONFIANCA)
    else:
        status = contratos.STATUS_REJEITADO
        add(contratos.MOTIVO_BAIXA_CONFIANCA)

    try:  # devolve o calculo para quem grava (pedidos.confianca_doc / planilha)
        extracao.status_validacao = status
        extracao.motivos = list(motivos)
        extracao.confianca_geral = geral
        extracao.confianca_por_campo = {**dict(getattr(extracao, "confianca_por_campo", None) or {}), **por_campo}
    except AttributeError:  # objeto imutavel/congelado: decidir continua puro
        pass
    return (status, list(motivos))


# ------------------------------------------------------------------ gravacao do pedido


def _id_pedido(extracao: Any) -> str:
    """Identidade estavel (sem o valor) - inclui a precedencia da `chave_dedupe()`."""
    chave = extracao.chave_dedupe()
    tipo = chave[0]
    if tipo == "chave":
        base = f"chave|{chave[1]}"
    elif tipo == "fingerprint":
        base = "fmt|{}|{}|{}".format(*[str(x) for x in chave[1:4]])
    elif tipo == "fraco":
        base = "fraco|{}|{}".format(str(chave[1]), str(chave[2]))
    else:
        base = f"documento|{extracao.documento_id}"
    return "ped_" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _buscar_pedido(conn: sqlite3.Connection, extracao: Any) -> Optional[sqlite3.Row]:
    linha = conn.execute(
        "SELECT * FROM pedidos WHERE id = ?", (_id_pedido(extracao),)
    ).fetchone()
    if linha is not None:
        return linha

    chave = normaliza.so_digitos(getattr(extracao, "chave_acesso_nf", None))
    cnpj = normaliza.so_digitos(getattr(extracao, "emitente_cnpj", None))
    numero = getattr(extracao, "numero_pedido", None)
    data = getattr(extracao, "data_emissao", None)

    if len(chave) == 44:
        return conn.execute("SELECT * FROM pedidos WHERE chave_acesso = ?", (chave,)).fetchone()
    if cnpj and numero and data:
        return conn.execute(
            """SELECT * FROM pedidos
               WHERE chave_acesso IS NULL AND emitente_cnpj = ? AND numero_pedido = ? AND data_emissao = ?""",
            (cnpj, numero, data),
        ).fetchone()
    if cnpj and data:
        return conn.execute(
            """SELECT * FROM pedidos
               WHERE chave_acesso IS NULL AND numero_pedido IS NULL
                 AND emitente_cnpj = ? AND data_emissao = ?""",
            (cnpj, data),
        ).fetchone()
    if getattr(extracao, "documento_id", None):
        return conn.execute(
            "SELECT * FROM pedidos WHERE documento_id = ? AND chave_acesso IS NULL AND emitente_cnpj IS NULL",
            (extracao.documento_id,),
        ).fetchone()
    return None


_CAMPOS_CRITICOS = ("valor_total_centavos", "emitente_cnpj", "data_emissao", "numero_pedido", "chave_acesso")


def _valor_do_campo(extracao: Any, campo: str) -> Any:
    if campo == "chave_acesso":
        return normaliza.so_digitos(getattr(extracao, "chave_acesso_nf", None)) or None
    if campo == "valor_total_centavos":
        valor = getattr(extracao, "valor_total_centavos", None)
        return None if valor is None else int(valor)
    return getattr(extracao, campo, None)


def _conflitos(pedido: sqlite3.Row, extracao: Any) -> list[str]:
    """Campos em que a chave e a mesma mas o valor lido e diferente (contrato 6.6)."""
    divergentes = []
    for campo in _CAMPOS_CRITICOS:
        antigo = pedido[campo]
        novo = _valor_do_campo(extracao, campo)
        if antigo is None or novo is None:
            continue
        if str(antigo) != str(novo):
            divergentes.append(f"{campo}: banco={antigo} documento={novo}")
    return divergentes


def _possivel_duplicata(conn: sqlite3.Connection, extracao: Any) -> Optional[sqlite3.Row]:
    """Doc 02 3.3 item 3: sem chave e sem numero, mesmo CNPJ + mesmo valor dentro de
    3 dias -> nao publica, vira excecao `possivel_duplicata` (nao decide sozinho)."""
    cnpj = normaliza.so_digitos(getattr(extracao, "emitente_cnpj", None))
    valor = getattr(extracao, "valor_total_centavos", None)
    data = getattr(extracao, "data_emissao", None)
    if not (cnpj and valor is not None and data) or getattr(extracao, "numero_pedido", None):
        return None
    if normaliza.so_digitos(getattr(extracao, "chave_acesso_nf", None)):
        return None
    try:
        referencia = date.fromisoformat(str(data)[:10])
    except ValueError:
        return None
    janela = [(referencia + timedelta(days=d)).isoformat() for d in range(-3, 4)]
    marcadores = ",".join("?" for _ in janela)
    return conn.execute(
        f"""SELECT * FROM pedidos
            WHERE emitente_cnpj = ? AND valor_total_centavos = ?
              AND data_emissao IN ({marcadores})
              AND data_emissao IS NOT NULL
            LIMIT 1""",
        (cnpj, int(valor), *janela),
    ).fetchone()


def _inserir_itens(conn: sqlite3.Connection, pedido_id: str, extracao: Any) -> None:
    for indice, item in enumerate(getattr(extracao, "itens", None) or [], start=1):
        quantidade = getattr(item, "quantidade", None)
        unitario = getattr(item, "valor_unitario_centavos", None)
        total = getattr(item, "valor_total_centavos", None)
        if total is None and quantidade is not None and unitario is not None:
            total = int(
                (Decimal(str(quantidade)) * Decimal(int(unitario))).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
        conn.execute(
            """INSERT INTO itens_pedido
               (pedido_id, linha, descricao, quantidade, valor_unitario, valor_linha_centavos, confianca)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                pedido_id,
                indice,
                getattr(item, "descricao", None),
                None if quantidade is None else str(quantidade),
                None if unitario is None else int(unitario),
                total,
                float(getattr(item, "confianca", 0.0) or 0.0),
            ),
        )


def _mensagem_do_documento(conn: sqlite3.Connection, documento_id: Optional[str]) -> Optional[str]:
    if not documento_id:
        return None
    linha = conn.execute(
        "SELECT id FROM mensagens WHERE documento_id = ? LIMIT 1", (documento_id,)
    ).fetchone()
    return linha["id"] if linha is not None else None


def _rank_status(status: Any) -> int:
    return {
        contratos.STATUS_AUTO_APROVADO: 3,
        contratos.STATUS_DOC_VALIDADO: 3,
        contratos.STATUS_REVISAO_HUMANA: 2,
        contratos.STATUS_REJEITADO: 1,
    }.get(status, 0)


def _registrar_excecoes(conn: sqlite3.Connection, extracao: Any) -> None:
    if getattr(extracao, "status_validacao", None) == contratos.STATUS_AUTO_APROVADO:
        return
    for motivo in list(getattr(extracao, "motivos", None) or []):
        registrar_excecao(conn, extracao, motivo, _detalhe_motivo(extracao, motivo))


def _detalhe_motivo(extracao: Any, motivo: str) -> str:
    if motivo == contratos.MOTIVO_DIVERGENCIA_ITENS or motivo == contratos.MOTIVO_SUSPEITA_ITENS:
        calc = extracao.total_calculado_centavos()
        dif = extracao.diferenca_itens_centavos()
        return (
            f"total lido={contratos.formatar_brl(getattr(extracao, 'valor_total_centavos', None))} "
            f"total calculado={contratos.formatar_brl(calc)} diferenca={contratos.formatar_brl(dif)}"
        )
    if motivo == contratos.MOTIVO_CNPJ_INVALIDO:
        return f"cnpj lido={getattr(extracao, 'emitente_cnpj', None)} (DV invalido)"
    if motivo == contratos.MOTIVO_CHAVE_INVALIDA:
        return f"chave lida={getattr(extracao, 'chave_acesso_nf', None)} (DV invalido)"
    if motivo == contratos.MOTIVO_TOTAL_SEM_DETALHAMENTO:
        return "total lido sem itens detalhados no documento"
    if motivo == contratos.MOTIVO_CONFLITO_VALOR:
        return "chave natural igual com valor diferente - valor do banco preservado"
    if motivo == contratos.MOTIVO_INJECAO_SUSPEITA:
        return "texto do documento contem instrucao dirigida ao leitor automatico - ignorada"
    if motivo == contratos.MOTIVO_DATA_AMBIGUA:
        return "data com dia <= 12: leitura dd/mm assumida, pode ser mm/dd"
    return f"status={getattr(extracao, 'status_validacao', None)} confianca={getattr(extracao, 'confianca_geral', None)}"


def gravar_extracao(conn: sqlite3.Connection, extracao: Any) -> str:
    """Persiste o pedido e devolve `pedido_id`.

    Deduplica pela `Extracao.chave_dedupe()` na ordem de precedencia (3.3). Chave igual
    com valor diferente **nao** sobrescreve: abre excecao `MOTIVO_CONFLITO_VALOR` e mantem
    o registro existente. Pedido ja existente e **enriquecido** (campos nulos preenchidos,
    itens ausentes completados, status nunca rebaixado).
    """
    if getattr(extracao, "status_validacao", None) not in contratos.STATUS_VALIDACAO:
        extracao.status_validacao = contratos.STATUS_REVISAO_HUMANA
    agora = _agora_iso()
    mensagem_id = _mensagem_do_documento(conn, getattr(extracao, "documento_id", None))

    existente = _buscar_pedido(conn, extracao)
    if existente is not None:
        pedido_id = existente["id"]
        conflitos = _conflitos(existente, extracao)
        if conflitos:
            detalhe = "; ".join(conflitos)
            registrar_excecao(conn, extracao, contratos.MOTIVO_CONFLITO_VALOR, detalhe)
            _sincronizar_documento(conn, extracao, status=contratos.STATUS_DOC_EXCECAO)
            return pedido_id

        campos = {
            "documento_id": getattr(extracao, "documento_id", None),
            "mensagem_id": mensagem_id,
            "emitente_nome": getattr(extracao, "emitente_nome", None),
            "emitente_cnpj": normaliza.so_digitos(getattr(extracao, "emitente_cnpj", None)) or None,
            "data_emissao": getattr(extracao, "data_emissao", None),
            "data_vencimento": getattr(extracao, "data_vencimento", None),
            "valor_total_centavos": getattr(extracao, "valor_total_centavos", None),
            "desconto_centavos": getattr(extracao, "desconto_centavos", None),
            "frete_centavos": getattr(extracao, "frete_centavos", None),
            "forma_pagamento": getattr(extracao, "forma_pagamento", None),
            "chave_acesso": normaliza.so_digitos(getattr(extracao, "chave_acesso_nf", None)) or None,
            "numero_pedido": getattr(extracao, "numero_pedido", None),
            "origem": getattr(extracao, "origem_canal", None),
            "tipo_documento": getattr(extracao, "tipo_documento", None),
            "arquivo_origem": getattr(extracao, "arquivo_origem", None),
            "hash_conteudo": getattr(extracao, "hash_conteudo", None),
        }
        # so preenche o que esta nulo: nunca troca dado bom por dado novo (3.3)
        preenchidos = {c: v for c, v in campos.items() if existente[c] is None and v is not None}
        status_final = existente["status"]
        if _rank_status(extracao.status_validacao) > _rank_status(status_final):
            status_final = extracao.status_validacao
            preenchidos["status"] = status_final
        nova_confianca = float(getattr(extracao, "confianca_geral", 0.0) or 0.0)
        antiga_confianca = existente["confianca_doc"] or 0.0
        if nova_confianca > antiga_confianca:
            preenchidos["confianca_doc"] = nova_confianca
        if preenchidos:
            preenchidos["atualizado_em"] = agora
            sets = ", ".join(f"{c} = ?" for c in preenchidos)
            with conn:
                conn.execute(
                    f"UPDATE pedidos SET {sets} WHERE id = ?", (*preenchidos.values(), pedido_id)
                )
        tem_itens = conn.execute(
            "SELECT COUNT(*) AS n FROM itens_pedido WHERE pedido_id = ?", (pedido_id,)
        ).fetchone()["n"]
        if not tem_itens and getattr(extracao, "itens", None):
            with conn:
                _inserir_itens(conn, pedido_id, extracao)
        _sincronizar_documento(conn, extracao)
        return pedido_id

    duplicata = _possivel_duplicata(conn, extracao)
    if duplicata is not None:
        extracao.status_validacao = contratos.STATUS_REVISAO_HUMANA
        motivo = contratos.MOTIVO_POSSIVEL_DUPLICATA
        if motivo not in (extracao.motivos or []):
            extracao.motivos = list(extracao.motivos or []) + [motivo]
        registrar_excecao(
            conn, extracao, motivo,
            f"mesmo emitente/valor do pedido {duplicata['id']} em ate 3 dias "
            f"(data {duplicata['data_emissao']})",
        )
        return duplicata["id"]

    pedido_id = _id_pedido(extracao)
    with conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO pedidos (
                id, documento_id, mensagem_id, chave_acesso, numero_pedido, emitente_nome,
                emitente_cnpj, data_emissao, data_vencimento, valor_total_centavos,
                desconto_centavos, frete_centavos, forma_pagamento, confianca_doc, status,
                row_id_planilha, origem, tipo_documento, arquivo_origem, hash_conteudo,
                criado_em, atualizado_em, data_processamento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                pedido_id,
                getattr(extracao, "documento_id", None),
                mensagem_id,
                normaliza.so_digitos(getattr(extracao, "chave_acesso_nf", None)) or None,
                getattr(extracao, "numero_pedido", None),
                getattr(extracao, "emitente_nome", None),
                normaliza.so_digitos(getattr(extracao, "emitente_cnpj", None)) or None,
                getattr(extracao, "data_emissao", None),
                getattr(extracao, "data_vencimento", None),
                getattr(extracao, "valor_total_centavos", None),
                getattr(extracao, "desconto_centavos", None),
                getattr(extracao, "frete_centavos", None),
                getattr(extracao, "forma_pagamento", None),
                float(getattr(extracao, "confianca_geral", 0.0) or 0.0),
                extracao.status_validacao,
                getattr(extracao, "origem_canal", None),
                getattr(extracao, "tipo_documento", None),
                getattr(extracao, "arquivo_origem", None),
                getattr(extracao, "hash_conteudo", None),
                agora,
                agora,
            ),
        )
        if cursor.rowcount == 0:
            # colidiu em algum UNIQUE parcial: relê pela identidade e enriquece
            existente = _buscar_pedido(conn, extracao)
            if existente is not None:
                return existente["id"]
        _inserir_itens(conn, pedido_id, extracao)

    _sincronizar_documento(conn, extracao)
    _registrar_excecoes(conn, extracao)
    return pedido_id


def _sincronizar_documento(conn: sqlite3.Connection, extracao: Any, status: Optional[str] = None) -> None:
    """Espelha no documento o desfecho do pedido (rastreabilidade, doc 02 3.2)."""
    documento_id = getattr(extracao, "documento_id", None)
    if not documento_id:
        return
    if status is None:
        status = {
            contratos.STATUS_AUTO_APROVADO: contratos.STATUS_DOC_VALIDADO,
            contratos.STATUS_REVISAO_HUMANA: contratos.STATUS_DOC_EXCECAO,
            contratos.STATUS_REJEITADO: contratos.STATUS_DOC_REJEITADO,
        }.get(getattr(extracao, "status_validacao", None), contratos.STATUS_DOC_EXTRAIDO)
    with conn:
        conn.execute(
            """UPDATE documentos
               SET status = ?, processado_em = ?, tipo_doc = COALESCE(?, tipo_doc),
                   texto_norm_sha256 = COALESCE(texto_norm_sha256, ?)
               WHERE id = ?""",
            (
                status,
                _agora_iso(),
                getattr(extracao, "tipo_documento", None),
                getattr(extracao, "texto_norm_sha256", None),
                documento_id,
            ),
        )


# ------------------------------------------------------------------ fila e auditoria


def registrar_excecao(conn: sqlite3.Connection, extracao: Any, motivo: str, detalhe: str) -> None:
    """Abre (ou reaproveita) uma pendencia de revisao humana para este documento.

    Idempotente: nao cria segunda pendencia aberta com o mesmo
    `(documento_id, pedido_id, motivo_codigo)`.
    """
    documento_id = getattr(extracao, "documento_id", None)
    pedido_id = None
    linha = _buscar_pedido(conn, extracao)
    if linha is not None:
        pedido_id = linha["id"]
    with conn:
        aberta = conn.execute(
            """SELECT id FROM fila_excecoes
               WHERE status = 'aberta' AND motivo_codigo = ?
                 AND IFNULL(documento_id, '') = IFNULL(?, '')
                 AND IFNULL(pedido_id, '') = IFNULL(?, '')
               LIMIT 1""",
            (motivo, documento_id, pedido_id),
        ).fetchone()
        if aberta is not None:
            conn.execute(
                "UPDATE fila_excecoes SET detalhe = ? WHERE id = ?",
                (detalhe, aberta["id"]),
            )
            return
        conn.execute(
            """INSERT INTO fila_excecoes
               (documento_id, pedido_id, motivo_codigo, detalhe, valor_suspeito, status, aberta_em)
               VALUES (?, ?, ?, ?, ?, 'aberta', ?)""",
            (
                documento_id,
                pedido_id,
                motivo,
                detalhe,
                getattr(extracao, "valor_total_centavos", None),
                _agora_iso(),
            ),
        )


def registrar_auditoria(caminho_jsonl: Any, registro: dict) -> None:
    """Acrescenta UMA linha JSON a trilha de auditoria (append, `ensure_ascii=False`)."""
    if not isinstance(registro, dict):
        raise TypeError("registro de auditoria precisa ser dict")
    linha = dict(registro)
    linha.setdefault("ts", _agora_iso())
    destino = Path(caminho_jsonl)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")


# ------------------------------------------------------------------ planilha (destino, nao fonte)


# ------------------------------------------- lancamento direto com destaque (PO, 25/09/2026)
#
# Decisao do cliente: TODA nota vai para a planilha, sem aprovacao manual e sem aba de revisao.
# A conferencia passa a ser visual, na propria linha - e o que nao veio certo se destaca:
#
#   campo nao encontrado .......... texto "NAO ENCONTRADO" + celula AMARELA
#   documento ilegivel ............ texto "ILEGIVEL"      + celula AMARELA
#   valor contraditorio ........... celula VERMELHA, sem numero (valor duvidoso nao se afirma)
#   leitura duvidosa (OCR, DV, data) valor lido          + celula AMARELA
#
# A linha inteira fica com fundo amarelo claro quando tem algo a conferir: e assim que se acha a
# falha sem ler documento por documento. O status da coluna `status_validacao` tambem vira rotulo
# de negocio (OK / CONFERIR / ILEGIVEL) em vez do codigo interno.
TEXTO_NAO_ENCONTRADO = "NAO ENCONTRADO"
TEXTO_ILEGIVEL = "ILEGIVEL"

# Nome das abas da planilha. `Revisao` e o nome HISTORICO da aba de aprovacao: nao se cria mais,
# e a rodada apaga se encontrar uma (o produto passou a lancar direto).
ABA_OFICIAL = "controle_financeiro"
ABA_REVISAO_ANTIGA = "Revisao"

MARCA_OK = "ok"
MARCA_AUSENTE = "ausente"
MARCA_ILEGIVEL = "ilegivel"
MARCA_LEITURA = "leitura"            # valor presente, leitura fraca/duvidosa
MARCA_CONTRADICAO = "contradicao"    # valor presente, mas contradiz outra informacao

COR_ATENCAO = "FFFFF2CC"        # fundo da linha que tem algo a conferir (amarelo claro)
COR_CONFERIR = "FFFFC000"       # celula do campo nao encontrado / ilegivel / leitura fraca
COR_CONTRADICAO = "FFFF0000"    # celula do valor contraditorio (vermelho)

STATUS_PLANILHA_OK = "OK"
STATUS_PLANILHA_CONFERIR = "CONFERIR"
STATUS_PLANILHA_ILEGIVEL = "ILEGIVEL"

# Campos de conteudo: sao eles que o financeiro confere na planilha.
CAMPOS_DESTAQUE: tuple[str, ...] = (
    "numero_pedido",
    "emitente_nome",
    "emitente_cnpj",
    "data_emissao",
    "valor_total",
    "valor_total_centavos",
    "chave_acesso_nf",
)

# Coluna da planilha -> coluna do banco onde o valor vive de verdade. `valor_total` so existe na
# planilha (e a string BR formatada); quem diz se o valor esta preenchido e `valor_total_centavos`.
_CAMPO_PLANILHA_PARA_PEDIDO = {
    "numero_pedido": "numero_pedido",
    "emitente_nome": "emitente_nome",
    "emitente_cnpj": "emitente_cnpj",
    "data_emissao": "data_emissao",
    "valor_total": "valor_total_centavos",
    "valor_total_centavos": "valor_total_centavos",
    "chave_acesso_nf": "chave_acesso",
}

# Motivo -> efeito. O CAMPO de cada motivo vem de `revisao.info_motivo` (fonte unica).
MOTIVOS_ILEGIVEL = (
    contratos.MOTIVO_DOC_ILEGIVEL,
    contratos.MOTIVO_SEM_CAMPOS_OBRIGATORIOS,
)
MOTIVOS_CONTRADICAO = (
    contratos.MOTIVO_DIVERGENCIA_ITENS,
    contratos.MOTIVO_CONFLITO_VALOR,
    contratos.MOTIVO_POSSIVEL_DUPLICATA,
)
# Motivos que pintam a LINHA inteira de vermelho: nao e duvida de leitura, e risco.
MOTIVOS_DE_RISCO = (
    contratos.MOTIVO_INJECAO_SUSPEITA,
    contratos.MOTIVO_POSSIVEL_DUPLICATA,
    contratos.MOTIVO_CONFLITO_VALOR,
)
# Todo o resto (baixa_confianca, CNPJ/chave com DV invalido, data ambigua/implausivel, valor fora
# da faixa, suspeita de soma, total sem detalhamento, injecao de instrucao) = leitura duvidosa:
# o valor LIDO fica visivel e a celula se destaca.
_CAMPO_DO_MOTIVO_PARA_COLUNA = {
    "valor_total": ("valor_total", "valor_total_centavos"),
    "emitente_cnpj": ("emitente_cnpj",),
    "chave_acesso_nf": ("chave_acesso_nf",),
    "data_emissao": ("data_emissao",),
    "numero_pedido": ("numero_pedido",),
    "emitente_nome": ("emitente_nome",),
}


def _motivos_do_pedido(conn: sqlite3.Connection, pedido_id: str, documento_id: str) -> set[str]:
    """Motivos ja registrados para o pedido/documento (qualquer status da pendencia).

    A pendencia nao decide mais nada: ela e a memoria do que a leitura achou duvidoso, e e dela
    que sai o destaque da linha.
    """
    linhas = conn.execute(
        """
        SELECT motivo_codigo FROM fila_excecoes
         WHERE pedido_id = ? OR (documento_id = ? AND (pedido_id IS NULL OR pedido_id = ''))
        """,
        (pedido_id or "", documento_id or ""),
    ).fetchall()
    return {str(linha[0]) for linha in linhas if linha[0]}


def _marcas_da_linha(
    conn: sqlite3.Connection, registro: Any
) -> tuple[dict[str, str], bool, bool]:
    """Marca cada campo de conteudo. -> `(marcas, atencao, linha_de_risco)`.

    Precedencia por campo: ilegivel > nao encontrado > contradicao > leitura duvidosa.
    Motivo que nao aponta para um campo da planilha (confianca, itens, texto) marca a LEITURA
    inteira como duvidosa - e o que o cliente pediu: achou o valor, mas tem duvida, pinta de
    amarelo. Injeção de instrucao e suspeita de duplicidade pintam a LINHA de vermelho.
    """
    from . import revisao  # import tardio: revisao nao depende deste modulo no topo

    marcas = {campo: MARCA_OK for campo in CAMPOS_DESTAQUE}
    motivos = _motivos_do_pedido(conn, str(registro["id"]), str(registro["documento_id"] or ""))

    if motivos & set(MOTIVOS_ILEGIVEL):
        # Nada foi lido: afirmar ausencia campo a campo nao ajuda ninguem.
        return {campo: MARCA_ILEGIVEL for campo in CAMPOS_DESTAQUE}, True, False

    for campo in CAMPOS_DESTAQUE:
        valor = registro[_CAMPO_PLANILHA_PARA_PEDIDO[campo]]
        if valor is None or str(valor).strip() == "":
            marcas[campo] = MARCA_AUSENTE

    duvida_de_leitura = False
    for motivo in motivos:
        colunas = _CAMPO_DO_MOTIVO_PARA_COLUNA.get(revisao.info_motivo(motivo)["campo"], ())
        if not colunas:
            # Motivo sem campo proprio: atinge a leitura como um todo.
            duvida_de_leitura = True
            continue
        for coluna in colunas:
            if motivo in MOTIVOS_CONTRADICAO:
                marcas[coluna] = MARCA_CONTRADICAO
            elif marcas[coluna] == MARCA_OK:
                marcas[coluna] = MARCA_LEITURA

    if duvida_de_leitura:
        for campo in CAMPOS_DESTAQUE:
            if marcas[campo] == MARCA_OK:
                marcas[campo] = MARCA_LEITURA

    linha_de_risco = bool(motivos & set(MOTIVOS_DE_RISCO))
    atencao = bool(motivos) or any(marca != MARCA_OK for marca in marcas.values())
    return marcas, atencao, linha_de_risco


def _valores_linha_destacada(conn: sqlite3.Connection, registro: Any) -> tuple[dict, dict, bool, bool]:
    """`(valores, marcas, atencao, linha_de_risco)` da linha, ja com os textos de ausencia."""
    marcas, atencao, linha_de_risco = _marcas_da_linha(conn, registro)
    valores = _valores_linha(registro)
    for campo, marca in marcas.items():
        if marca == MARCA_ILEGIVEL:
            valores[campo] = TEXTO_ILEGIVEL
        elif marca == MARCA_AUSENTE:
            valores[campo] = TEXTO_NAO_ENCONTRADO
        elif marca == MARCA_CONTRADICAO:
            valores[campo] = ""  # valor duvidoso nao se afirma

    if any(marca == MARCA_ILEGIVEL for marca in marcas.values()):
        valores["status_validacao"] = STATUS_PLANILHA_ILEGIVEL
    elif atencao:
        valores["status_validacao"] = STATUS_PLANILHA_CONFERIR
    else:
        valores["status_validacao"] = STATUS_PLANILHA_OK
    return valores, marcas, atencao, linha_de_risco


def contar_linhas_destacadas(conn: sqlite3.Connection) -> dict[str, int]:
    """Placar do destaque: quantas linhas da planilha pedem conferencia, e de que tipo.

    Ordem de gravidade por linha: ilegivel > contradicao > leitura duvidosa.
    """
    placar = {
        "ilegiveis": 0,
        "contradicoes": 0,
        "risco": 0,
        "leituras_duvidosas": 0,
        "linhas_destacadas": 0,
    }
    for registro in _linhas_para_planilha(conn):
        marcas, atencao, linha_de_risco = _marcas_da_linha(conn, registro)
        valores = set(marcas.values())
        if not atencao:
            continue
        placar["linhas_destacadas"] += 1
        if MARCA_ILEGIVEL in valores:
            placar["ilegiveis"] += 1
        elif linha_de_risco:
            placar["risco"] += 1
        elif MARCA_CONTRADICAO in valores:
            placar["contradicoes"] += 1
        else:
            placar["leituras_duvidosas"] += 1
    return placar


def _linhas_para_planilha(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """TODOS os pedidos vao para a planilha (lancamento direto: nada fica de fora).

    Quem marca o que precisa de olho humano e o destaque da linha (`_marcas_da_linha`), nao o
    direito de entrar no livro-caixa.

    Excecao unica: **mensagem sem texto e sem nada lido** nao e nota - e envelope de mensagem
    (arquivo `.jsonl`) que chegou vazio ou cujo anexo ja virou artefato proprio (a imagem lida
    tem a linha dela). Essa linha nao entra; o rastro dela continua na auditoria e na fila.
    """
    return conn.execute(
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM itens_pedido i WHERE i.pedido_id = p.id) AS qtd_itens
        FROM pedidos p
        LEFT JOIN documentos d ON d.id = p.documento_id
        WHERE NOT (
            d.arquivo_uri LIKE '%.jsonl'
            AND p.valor_total_centavos IS NULL
            AND p.numero_pedido IS NULL
            AND p.emitente_cnpj IS NULL
            AND p.emitente_nome IS NULL
            AND p.data_emissao IS NULL
            AND p.chave_acesso IS NULL
        )
        ORDER BY p.rowid
        """
    ).fetchall()


def _valores_linha(registro: Any) -> dict:
    valor_centavos = registro["valor_total_centavos"]
    confianca = registro["confianca_doc"]
    return {
        "data_processamento": registro["data_processamento"] or "",
        "documento_id": registro["documento_id"] or "",
        "pedido_id": registro["id"],
        "origem": registro["origem"] or "",
        "tipo_documento": registro["tipo_documento"] or "",
        "numero_pedido": registro["numero_pedido"] or "",
        "emitente_nome": registro["emitente_nome"] or "",
        "emitente_cnpj": registro["emitente_cnpj"] or "",
        "data_emissao": registro["data_emissao"] or "",
        "data_vencimento": registro["data_vencimento"] or "",
        "valor_total": "" if valor_centavos is None else contratos.formatar_brl(valor_centavos),
        "valor_total_centavos": "" if valor_centavos is None else int(valor_centavos),
        "forma_pagamento": registro["forma_pagamento"] or "",
        "qtd_itens": int(registro["qtd_itens"] or 0),
        "chave_acesso_nf": registro["chave_acesso"] or "",
        "confianca": "" if confianca is None else round(float(confianca), 4),
        "status_validacao": registro["status"] or "",
        "hash_conteudo": registro["hash_conteudo"] or "",
        "arquivo_origem": registro["arquivo_origem"] or "",
        "row_id_planilha": registro["row_id_planilha"] or "",
    }


def _mapa_linhas_existentes(ws: Any) -> dict[str, str]:
    """`{row_id_planilha: pedido_id}` lido da propria planilha."""
    indices = {nome: i + 1 for i, nome in enumerate(contratos.COLUNAS_PLANILHA)}
    col_row = indices["row_id_planilha"]
    col_pedido = indices["pedido_id"]
    mapa: dict[str, str] = {}
    for numero in range(2, ws.max_row + 1):
        row_id = ws.cell(row=numero, column=col_row).value
        if row_id in (None, ""):
            continue
        mapa[str(row_id).strip()] = str(ws.cell(row=numero, column=col_pedido).value or "")
    return mapa


def _escrever_cabecalho(ws: Any) -> None:
    for indice, nome in enumerate(contratos.COLUNAS_PLANILHA, start=1):
        ws.cell(row=1, column=indice, value=nome)


def escrever_ledger(conn: sqlite3.Connection, caminho_xlsx: Any, caminho_csv: Any) -> int:
    """Grava a planilha de controle (openpyxl) e o CSV equivalente.

    - Exatamente as 20 colunas de `contratos.COLUNAS_PLANILHA`, na ordem, uma linha por
      `pedido_id`: **todo pedido entra** (lancamento direto decidido pelo PO em 25/09/2026).
    - O que nao veio certo nao fica de fora: entra marcado - texto `NAO ENCONTRADO`/`ILEGIVEL`
      e celula/linha destacada (`_marcas_da_linha`).
    - `row_id_planilha` e a posicao da linha na planilha: o corpo e reescrito por inteiro a cada
      rodada (a planilha e DESTINO regeneravel, o banco e a fonte) e o `pedidos` guarda a posicao
      atual. Por isso rodar duas vezes nao duplica linha.
    - `valor_total` e a string BR (`contratos.formatar_brl`) e `valor_total_centavos` e int.
    - Chamar duas vezes nao duplica linha: devolve o numero de linhas do ledger.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import PatternFill

    destino_xlsx = Path(caminho_xlsx)
    destino_csv = Path(caminho_csv)
    destino_xlsx.parent.mkdir(parents=True, exist_ok=True)
    if destino_csv.parent and str(destino_csv.parent) not in ("", "."):
        destino_csv.parent.mkdir(parents=True, exist_ok=True)

    registros = _linhas_para_planilha(conn)
    if destino_xlsx.exists():
        wb = load_workbook(destino_xlsx)
        # A aba de revisao saiu do produto (lancamento direto): se sobrou de uma rodada antiga,
        # ela sai daqui - planilha com duas verdades confunde quem confere.
        if ABA_REVISAO_ANTIGA in wb.sheetnames:
            del wb[ABA_REVISAO_ANTIGA]
        ws = wb[ABA_OFICIAL] if ABA_OFICIAL in wb.sheetnames else wb.active
        ws.title = ABA_OFICIAL
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = ABA_OFICIAL
    wb.active = wb.sheetnames.index(ABA_OFICIAL)
    _escrever_cabecalho(ws)
    # A planilha e DESTINO regeneravel a partir do banco: o corpo antigo e reescrito por inteiro.
    # Sem isso, linha que saiu do ledger (mensagem sem texto, pedido removido) ficaria de heranca
    # e a planilha mostraria uma verdade que o banco nao tem mais.
    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row)

    preenchimento_atencao = PatternFill("solid", fgColor=COR_ATENCAO)
    preenchimento_conferir = PatternFill("solid", fgColor=COR_CONFERIR)
    preenchimento_contradicao = PatternFill("solid", fgColor=COR_CONTRADICAO)
    preenchimento_limpo = PatternFill(fill_type=None)

    linhas_saida: list[dict] = []
    fisica = 2
    for registro in registros:
        data_processamento = registro["data_processamento"] or _agora_iso()

        registro_dict = dict(registro)
        registro_dict["data_processamento"] = data_processamento
        registro_dict["row_id_planilha"] = str(fisica)
        valores, marcas, atencao, linha_de_risco = _valores_linha_destacada(conn, registro_dict)

        for indice, nome in enumerate(contratos.COLUNAS_PLANILHA, start=1):
            valor = valores[nome]
            celula = ws.cell(row=fisica, column=indice, value=valor if valor != "" else None)
            marca = marcas.get(nome)
            if marca in (MARCA_ILEGIVEL, MARCA_AUSENTE, MARCA_LEITURA):
                celula.fill = preenchimento_conferir
            elif marca == MARCA_CONTRADICAO:
                celula.fill = preenchimento_contradicao
            elif linha_de_risco:
                celula.fill = preenchimento_contradicao
            elif atencao:
                celula.fill = preenchimento_atencao
            else:
                celula.fill = preenchimento_limpo

        if (registro["row_id_planilha"] or "").strip() != str(fisica) or not registro[
            "data_processamento"
        ]:
            with conn:
                conn.execute(
                    """UPDATE pedidos SET row_id_planilha = ?, data_processamento = ?,
                       atualizado_em = ? WHERE id = ?""",
                    (str(fisica), data_processamento, _agora_iso(), registro["id"]),
                )
        linhas_saida.append(valores)
        fisica += 1

    wb.save(destino_xlsx)

    with open(destino_csv, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(contratos.COLUNAS_PLANILHA)
        for valores in linhas_saida:
            escritor.writerow([valores[nome] for nome in contratos.COLUNAS_PLANILHA])

    return len(linhas_saida)
