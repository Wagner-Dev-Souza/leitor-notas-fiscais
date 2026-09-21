"""Ingestao da inbox: PDF, imagem (foto/print) e mensagens WhatsApp/Telegram.

A pasta `pdf/` da inbox e a pasta de DOCUMENTOS: aceita `.pdf` e tambem imagem
(`.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff`, `.bmp`). Imagem nao tem camada de
texto: ela e lida pelo Tesseract real, e o artefato sai com `canal=imagem`.

Dono: avareza (F1 - nucleo). Fronteira congelada na secao 5 do
`docs/execucao/00-contrato-execucao.md`:

    ler_pdf(caminho) -> TextoExtraido
    ocr_pdf(caminho) -> TextoExtraido
    ler_mensagens_whatsapp(caminho_jsonl) -> list[MensagemBruta]
    ler_mensagens_telegram(caminho_jsonl) -> list[MensagemBruta]
    ingerir(inbox) -> list[Artefato]

Nenhuma rede, nenhum servico pago, nenhum segredo. Somente biblioteca padrao +
`pdfplumber`/`pypdf` (ja instalados no venv). O OCR real (tesseract) existe apenas
como caminho opcional: quando o binario nao esta na maquina, o motor simulado e
usado e **rotulado como simulado** (`MOTOR_OCR_SIMULADO`) em toda a trilha.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .contratos import (
    CANAL_IMAGEM,
    CANAL_PDF,
    CANAL_TELEGRAM,
    CANAL_WHATSAPP,
    MOTOR_OCR_SIMULADO,
    MOTOR_PDFPLUMBER,
    MOTOR_PYPDF,
    MOTOR_TESSERACT,
    Artefato,
    MensagemBruta,
    TextoExtraido,
    sha256_arquivo,
    sha256_bytes,
)

# --------------------------------------------------------------------- utilidades

# Confusoes tipicas de OCR usadas pelo gerador de mocks (contrato 4.3): 0/O, 1/l/I,
# 5/S, 2/Z. A tabela abaixo mapeia os caracteres "confundiveis" para uma forma
# canonica, de modo que o texto lido por OCR e o rotulo esperado caiam na mesma
# representacao. E usada pelo extrator (`app/extracao.py`) — a tabela vive aqui
# porque os dois modulos sao da mesma frente (F1).
TABELA_OCR = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "Z": "2"})

SIDECAR_OCR_SUFIXO = ".ocr.txt"

# Extensoes de imagem aceitas como documento de entrada. O sidecar `.ocr.txt` NAO vale
# para imagem: ele e um mecanismo do PDF (o contrato 4.3 nao preve "OCR simulado" de
# imagem). Sem Tesseract na maquina, a imagem entra sem texto, com confianca 0.0, e cai
# na fila de revisao humana como `documento_ilegivel` - nunca e chutada.
EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")

IDIOMA_OCR = "por"

# Ordem de preferencia de idioma. O Tesseract RECUSA um idioma que nao tem instalado, e o
# instalador oficial do Windows vem so com `eng` + `osd` por padrao: pedir `por` num parque
# sem o pacote de portugues dava leitura VAZIA. Ler uma nota brasileira em ingles e pior que
# ler em portugues - e muito melhor que nao ler nada. O motor continua rotulado `tesseract`
# e a confianca de OCR (0,65) ja manda o documento para revisao humana.
IDIOMAS_OCR = ("por", "eng")

# Resolucao (dpi) da rasterizacao da pagina antes do OCR. Ver a nota em `_ocr_tesseract`.
RESOLUCAO_OCR_DPI = 300


def busca_ocr(texto: str) -> str:
    """Forma canonica usada para casar rotulos em texto nativo ou degradado por OCR.

    `str.translate` preserva o comprimento, entao as posicoes achadas aqui podem ser
    usadas para recortar a evidencia no texto original.
    """
    return (texto or "").upper().translate(TABELA_OCR)


def confianca_ocr_simulado(texto: str) -> float:
    """Confianca do OCR simulado, deterministica, sempre entre 0.55 e 0.75.

    Estimada pela densidade de caracteres confundiveis (0/O, 1/l/I, 5/S, 2/Z): quanto
    mais ruido, menor a confianca. Nao ha margem para "achar" qualidade: o numero e a
    leitura honesta da degradacao presente no sidecar.
    """
    util = "".join(c for c in texto if not c.isspace())
    if not util:
        return 0.0
    suspeitos = sum(1 for c in util.upper() if c in "0O1LI5S2Z")
    densidade = suspeitos / len(util)
    # densidade 0.0 -> 0.75 ; densidade >= 0.60 -> 0.55
    conf = 0.75 - 0.20 * min(1.0, densidade / 0.60)
    return round(min(0.75, max(0.55, conf)), 4)


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso_de_epoch(bruto: Any) -> Optional[str]:
    """Timestamp de webhook (epoch em segundos, str ou int) -> ISO 8601 em UTC."""
    if bruto is None or bruto == "":
        return None
    try:
        ts = int(str(bruto).strip())
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return None


def _limpar(texto: Any) -> str:
    return " ".join(str(texto or "").split())


# --------------------------------------------------------------------- leitura de PDF


def _texto_pdfplumber(caminho: Path) -> tuple[str, int]:
    import pdfplumber

    with pdfplumber.open(str(caminho)) as pdf:
        partes = [pagina.extract_text() or "" for pagina in pdf.pages]
    return "\n".join(partes), len(partes)


def _texto_pypdf(caminho: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    paginas = leitor.pages
    return "\n".join((pagina.extract_text() or "") for pagina in paginas), len(paginas)


def _numero_paginas(caminho: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(caminho)).pages)
    except Exception:
        return 1


def ler_pdf(caminho) -> TextoExtraido:
    """Camada de texto do PDF. `pdfplumber` primeiro, `pypdf` como fallback.

    `tem_camada_texto=False` quando o texto extraido e vazio (caso do PDF escaneado).
    """
    caminho_pdf = Path(caminho)
    if not caminho_pdf.is_file():
        raise FileNotFoundError(f"PDF nao encontrado: {caminho_pdf}")

    texto_plumber: Optional[str] = None
    paginas_plumber = 1
    texto_pypdf: Optional[str] = None
    paginas_pypdf = 1

    try:
        texto_plumber, paginas_plumber = _texto_pdfplumber(caminho_pdf)
    except Exception:
        texto_plumber = None

    if texto_plumber is not None and texto_plumber.strip():
        return TextoExtraido(
            texto=texto_plumber,
            paginas=paginas_plumber,
            tem_camada_texto=True,
            motor=MOTOR_PDFPLUMBER,
            confianca_leitura=1.0,
            arquivo=str(caminho_pdf),
        )

    # pdfplumber vazio (ou indisponivel/falhou): tenta o fallback pypdf.
    try:
        texto_pypdf, paginas_pypdf = _texto_pypdf(caminho_pdf)
    except Exception:
        texto_pypdf = None

    if texto_pypdf is not None and texto_pypdf.strip():
        return TextoExtraido(
            texto=texto_pypdf,
            paginas=paginas_pypdf,
            tem_camada_texto=True,
            motor=MOTOR_PYPDF,
            confianca_leitura=1.0,
            arquivo=str(caminho_pdf),
        )

    if texto_plumber is None and texto_pypdf is None:
        raise RuntimeError(
            f"nao foi possivel ler o PDF {caminho_pdf} (pdfplumber e pypdf falharam)"
        )

    # Leitura valida, porem sem texto: PDF de imagem (escaneado).
    return TextoExtraido(
        texto=texto_plumber if texto_plumber is not None else "",
        paginas=paginas_plumber,
        tem_camada_texto=False,
        motor=MOTOR_PDFPLUMBER if texto_plumber is not None else MOTOR_PYPDF,
        confianca_leitura=1.0,
        arquivo=str(caminho_pdf),
    )


def caminho_sidecar_ocr(caminho) -> Path:
    return Path(str(caminho) + SIDECAR_OCR_SUFIXO)


def localizar_tesseract() -> Optional[str]:
    """Caminho do binario do Tesseract, ou None se ele nao existir de verdade.

    Ordem: `TESSERACT_CMD` (variavel de ambiente opcional) -> PATH do sistema ->
    locais de instalacao padrao no Windows. **O PATH sozinho nao basta:** o instalador
    registra o PATH para processos NOVOS, e um processo ja em execucao (a suite, o
    receptor, o gateway) continua sem enxergar. Por isso a busca no local padrao e
    parte da funcao, e nao um detalhe.

    Nao inventa motor: sem binario devolve None e quem chamou decide o que fazer.
    """
    import os
    import shutil

    try:
        import pytesseract  # type: ignore
    except Exception:
        return None

    candidatos: list[str] = []
    do_ambiente = os.environ.get("TESSERACT_CMD")
    if do_ambiente:
        candidatos.append(do_ambiente)
    achado = shutil.which("tesseract")
    if achado:
        candidatos.append(achado)
    for base in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        raiz = os.environ.get(base)
        if not raiz:
            continue
        candidatos.append(str(Path(raiz) / "Tesseract-OCR" / "tesseract.exe"))
        candidatos.append(str(Path(raiz) / "Programs" / "Tesseract-OCR" / "tesseract.exe"))

    for candidato in candidatos:
        if candidato and Path(candidato).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidato
            return candidato
    return None


def idioma_ocr(pytesseract_mod) -> str:
    """Primeiro idioma disponivel na maquina: `por` se houver, senao `eng`."""
    try:
        disponiveis = set(pytesseract_mod.get_languages(config=""))
    except Exception:
        return IDIOMAS_OCR[0]
    for idioma in IDIOMAS_OCR:
        if idioma in disponiveis:
            return idioma
    return IDIOMAS_OCR[0]


def _tesseract_imagem(caminho: Path) -> Optional[TextoExtraido]:
    """Tesseract real sobre uma imagem. None quando o motor nao existe na maquina."""
    try:
        import pytesseract  # type: ignore
    except Exception:
        return None

    if not localizar_tesseract():
        return None

    try:
        texto = pytesseract.image_to_string(str(caminho), lang=idioma_ocr(pytesseract)) or ""
    except Exception:
        return None

    return TextoExtraido(
        texto=texto,
        paginas=1,
        # Imagem nao tem camada de texto - o campo ja nasce `False`, como no PDF de imagem.
        tem_camada_texto=False,
        motor=MOTOR_TESSERACT,
        confianca_leitura=1.0,
        arquivo=str(caminho),
    )


def ocr_imagem(caminho) -> TextoExtraido:
    """Le uma imagem (foto/print de nota) com o Tesseract real.

    Sem Tesseract instalado devolve texto vazio, `motor=tesseract` (foi o motor
    escolhido para resolver uma imagem; e o unico que resolve) e
    `confianca_leitura=0.0` - o extrator transforma isso em `documento_ilegivel` e o
    documento vai para a fila de revisao humana. Nao existe leitura simulada de
    imagem: o sidecar `.ocr.txt` e mecanismo do PDF.
    """
    caminho_imagem = Path(caminho)

    real = _tesseract_imagem(caminho_imagem)
    if real is not None:
        return real

    return TextoExtraido(
        texto="",
        paginas=1,
        tem_camada_texto=False,
        motor=MOTOR_TESSERACT,
        confianca_leitura=0.0,
        arquivo=str(caminho_imagem),
    )


def _ocr_tesseract(caminho: Path) -> Optional[TextoExtraido]:
    """Caminho 1 do contrato 4.3: tesseract real, **somente** se existir de verdade.

    Sem o binario, devolve None e o motor simulado assume - nunca fingimos OCR real.
    """
    try:
        import pytesseract  # type: ignore
    except Exception:
        return None

    if not localizar_tesseract():
        return None

    try:
        import pdfplumber

        textos: list[str] = []
        with pdfplumber.open(str(caminho)) as pdf:
            for pagina in pdf.pages:
                # 300 dpi, nao 200: medido nesta maquina contra a NF escaneada do corpus,
                # 200 dpi faz o Tesseract perder a virgula decimal dos itens ("2,35 17,50"
                # sai "2,35 1750") e a extracao perde a soma; 400 dpi ou mais funde
                # colunas ("V.UNITARIO" colado na QTD). 300 e o ponto medido como correto.
                imagem = pagina.to_image(resolution=RESOLUCAO_OCR_DPI).original
                textos.append(pytesseract.image_to_string(imagem, lang=idioma_ocr(pytesseract)) or "")
        texto = "\n".join(textos)
    except Exception:
        return None

    return TextoExtraido(
        texto=texto,
        paginas=len(textos),
        # O campo descreve o PDF, nao a origem do texto (contrato 4.3, emenda do PO):
        # o arquivo que chega ao OCR e um PDF de imagem, sem camada de texto. Quem
        # rotula a origem da leitura e `motor` (+ `ocr_usado` na Extracao).
        tem_camada_texto=False,
        motor=MOTOR_TESSERACT,
        confianca_leitura=1.0,
        arquivo=str(caminho),
    )


def ocr_pdf(caminho) -> TextoExtraido:
    """Resolve a leitura do PDF escaneado na ordem exata da secao 4.3 do contrato.

    1. tesseract real (se o pacote E o binario existirem);
    2. motor simulado: sidecar `<arquivo>.ocr.txt`, `motor=ocr_simulado`,
       `confianca_leitura` entre 0.55 e 0.75;
    3. sem sidecar e sem tesseract: texto vazio, `tem_camada_texto=False`,
       confianca 0.0 (o documento vira excecao `documento_ilegivel`).

    `tem_camada_texto` descreve o **PDF**, nao a origem do texto (contrato 4.3, emenda
    do PO): o caminho de OCR so e acionado justamente quando o PDF nao tem camada de
    texto, entao o campo volta `False` nos tres ramos. Quem registra que a leitura veio
    de OCR e `motor` (`ocr_simulado`/`tesseract`) e, na `Extracao`, `ocr_usado=True` -
    o texto existe (`texto` nao e vazio), mas ele nao veio de camada de texto do PDF.
    """
    caminho_pdf = Path(caminho)

    real = _ocr_tesseract(caminho_pdf)
    if real is not None:
        return real

    sidecar = caminho_sidecar_ocr(caminho_pdf)
    if sidecar.is_file():
        texto = sidecar.read_text(encoding="utf-8", errors="replace")
        return TextoExtraido(
            texto=texto,
            paginas=_numero_paginas(caminho_pdf),
            tem_camada_texto=False,
            motor=MOTOR_OCR_SIMULADO,
            confianca_leitura=confianca_ocr_simulado(texto),
            arquivo=str(caminho_pdf),
        )

    return TextoExtraido(
        texto="",
        paginas=_numero_paginas(caminho_pdf),
        tem_camada_texto=False,
        motor=MOTOR_OCR_SIMULADO,
        confianca_leitura=0.0,
        arquivo=str(caminho_pdf),
    )


# ------------------------------------------------------------- leitura de mensagens


def _iter_jsonl(caminho) -> Iterator[dict]:
    """Le um .jsonl tolerando linha vazia; linha invalida e ignorada (nao explode)."""
    caminho_jsonl = Path(caminho)
    if not caminho_jsonl.is_file():
        raise FileNotFoundError(f"arquivo de mensagens nao encontrado: {caminho_jsonl}")
    with caminho_jsonl.open("r", encoding="utf-8", errors="replace") as fh:
        for linha in fh:
            linha = linha.strip()
            if not linha:
                continue
            try:
                obj = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _texto_e_midia_whatsapp(msg: dict) -> tuple[str, Optional[dict]]:
    tipo = str(msg.get("type") or "texto")
    midia: Optional[dict] = None

    if tipo == "text":
        return str((msg.get("text") or {}).get("body") or ""), None
    if tipo in ("image", "document", "video", "audio", "sticker"):
        bloco = msg.get(tipo) or {}
        midia = {k: bloco.get(k) for k in ("id", "mime_type", "filename", "sha256")}
        return str(bloco.get("caption") or ""), midia
    if tipo == "button":
        return str((msg.get("button") or {}).get("text") or ""), None
    if tipo == "interactive":
        interativo = msg.get("interactive") or {}
        for chave in ("button_reply", "list_reply"):
            if chave in interativo:
                return str((interativo[chave] or {}).get("title") or ""), None
        return "", None
    if tipo == "location":
        local = msg.get("location") or {}
        return f"{local.get('name', '')} {local.get('address', '')}".strip(), None
    return "", None


def ler_mensagens_whatsapp(caminho_jsonl) -> list[MensagemBruta]:
    """Envelope do WhatsApp Cloud API (contrato 4.4) -> `MensagemBruta`."""
    caminho = Path(caminho_jsonl)
    saida: list[MensagemBruta] = []

    for envelope in _iter_jsonl(caminho):
        if "entry" not in envelope:
            continue  # webhook de status, sem mensagem
        for entrada in envelope.get("entry") or []:
            for mudanca in (entrada or {}).get("changes") or []:
                valor = (mudanca or {}).get("value") or {}
                contatos = {
                    (c or {}).get("wa_id"): ((c or {}).get("profile") or {}).get("name")
                    for c in (valor.get("contacts") or [])
                }
                metadata = valor.get("metadata") or {}
                conversa = str(
                    metadata.get("phone_number_id")
                    or metadata.get("display_phone_number")
                    or (entrada or {}).get("id")
                    or ""
                )
                for msg in valor.get("messages") or []:
                    id_externo = str((msg or {}).get("id") or "")
                    if not id_externo:
                        continue  # sem id nao ha chave de idempotencia: nao inventa
                    texto, midia = _texto_e_midia_whatsapp(msg)
                    remetente = str(msg.get("from") or "")
                    saida.append(
                        MensagemBruta(
                            canal=CANAL_WHATSAPP,
                            id_externo=id_externo,
                            conversa_id=conversa,
                            remetente_id=remetente,
                            remetente_nome=str(contatos.get(remetente) or ""),
                            texto=texto,
                            enviada_em=_iso_de_epoch(msg.get("timestamp")),
                            tipo=str(msg.get("type") or "texto"),
                            midia=midia,
                            arquivo_origem=str(caminho),
                        )
                    )
    return saida


def _texto_e_midia_telegram(msg: dict) -> tuple[str, Optional[dict]]:
    if msg.get("text"):
        return str(msg["text"]), None
    if msg.get("caption"):
        midia = None
        for chave in ("document", "photo", "video", "audio", "voice"):
            if chave in msg:
                bloco = msg[chave]
                if isinstance(bloco, list) and bloco:
                    bloco = bloco[-1]
                if isinstance(bloco, dict):
                    midia = {k: bloco.get(k) for k in ("file_id", "file_name", "mime_type")}
                break
        return str(msg["caption"]), midia
    for chave in ("document", "photo", "video", "audio", "voice"):
        if chave in msg:
            bloco = msg[chave]
            if isinstance(bloco, list) and bloco:
                bloco = bloco[-1]
            midia = (
                {k: bloco.get(k) for k in ("file_id", "file_name", "mime_type")}
                if isinstance(bloco, dict)
                else None
            )
            return "", midia
    return "", None


def ler_mensagens_telegram(caminho_jsonl) -> list[MensagemBruta]:
    """Envelope do Telegram Bot API (contrato 4.4) -> `MensagemBruta`."""
    caminho = Path(caminho_jsonl)
    saida: list[MensagemBruta] = []

    for envelope in _iter_jsonl(caminho):
        msg = envelope.get("message") or envelope.get("edited_message") or envelope.get("channel_post")
        if not isinstance(msg, dict):
            continue
        update_id = envelope.get("update_id")
        message_id = msg.get("message_id")
        if update_id is None and message_id is None:
            continue
        id_externo = f"{update_id}:{message_id}"
        chat = msg.get("chat") or {}
        autor = msg.get("from") or {}
        nome = " ".join(
            parte for parte in (autor.get("first_name"), autor.get("last_name")) if parte
        ) or str(autor.get("username") or "")
        texto, midia = _texto_e_midia_telegram(msg)
        saida.append(
            MensagemBruta(
                canal=CANAL_TELEGRAM,
                id_externo=id_externo,
                conversa_id=str(chat.get("id") or ""),
                remetente_id=str(autor.get("id") or ""),
                remetente_nome=nome,
                texto=texto,
                enviada_em=_iso_de_epoch(msg.get("date")),
                tipo="texto" if msg.get("text") else "midia",
                midia=midia,
                arquivo_origem=str(caminho),
            )
        )
    return saida


# ------------------------------------------------------------------- ingestao


def hash_mensagem(msg: MensagemBruta) -> str:
    """Chave de idempotencia de uma mensagem (deterministica, um registro por mensagem).

    NAO e o sha256 do arquivo: um .jsonl tem varias mensagens. O hash cobre a
    identidade da mensagem (provedor, id externo e conteudo), na mesma regra do
    UNIQUE `(provedor, id_externo)` do doc 02 secao 3.1.
    """
    canonico = json.dumps(
        {
            "canal": msg.canal,
            "id_externo": msg.id_externo,
            "conversa_id": msg.conversa_id,
            "remetente_id": msg.remetente_id,
            "texto": msg.texto,
            "enviada_em": msg.enviada_em,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256_bytes(canonico.encode("utf-8"))


def _artefato_pdf(caminho: Path) -> Artefato:
    leitura = ler_pdf(caminho)
    if not leitura.tem_camada_texto:
        # PDF de imagem: o leitor correto e o OCR (real ou simulado).
        leitura = ocr_pdf(caminho)
    return Artefato(
        tipo_artefato="pdf",
        caminho=str(caminho),
        canal=CANAL_PDF,
        hash_conteudo=sha256_arquivo(caminho),
        texto=leitura.texto,
        paginas=leitura.paginas,
        tem_camada_texto=leitura.tem_camada_texto,
        motor=leitura.motor,
        confianca_leitura=leitura.confianca_leitura,
        mensagem=None,
    )


def _artefato_imagem(caminho: Path) -> Artefato:
    """Imagem da pasta de documentos: lida por OCR, nunca por camada de texto."""
    leitura = ocr_imagem(caminho)
    return Artefato(
        tipo_artefato="imagem",
        caminho=str(caminho),
        canal=CANAL_IMAGEM,
        hash_conteudo=sha256_arquivo(caminho),
        texto=leitura.texto,
        paginas=leitura.paginas,
        tem_camada_texto=False,
        motor=leitura.motor,
        confianca_leitura=leitura.confianca_leitura,
        mensagem=None,
    )


def _artefato_mensagem(msg: MensagemBruta, caminho: Path) -> Artefato:
    return Artefato(
        tipo_artefato="mensagem",
        caminho=str(caminho),
        canal=msg.canal,
        hash_conteudo=hash_mensagem(msg),
        texto=msg.texto,
        paginas=1,
        tem_camada_texto=True,
        motor="parser",
        confianca_leitura=1.0,
        mensagem=msg,
    )


def ingerir(inbox) -> list[Artefato]:
    """Varre `pdf/`, `whatsapp/` e `telegram/` da inbox e devolve artefatos prontos.

    Ordem deterministica (caminho ordenado) para que duas rodadas produzam o mesmo
    resultado. O sidecar `.ocr.txt` nunca vira artefato por si: ele e insumo do OCR.
    Artefato de mensagem tem `hash_conteudo` proprio (ver `hash_mensagem`), senao
    todas as mensagens de um mesmo .jsonl colidiriam na deduplicacao por binario.
    """
    raiz = Path(inbox)
    if not raiz.is_dir():
        raise FileNotFoundError(f"inbox nao encontrada: {raiz}")

    artefatos: list[Artefato] = []

    # A pasta `pdf/` e a pasta de DOCUMENTOS: aceita PDF e imagem. O sidecar
    # `.ocr.txt` continua sendo insumo do OCR, nunca artefato por si.
    diretorio_documentos = raiz / "pdf"
    for caminho in sorted(diretorio_documentos.glob("*")):
        if not caminho.is_file():
            continue
        sufixo = caminho.suffix.lower()
        if sufixo == ".pdf":
            artefatos.append(_artefato_pdf(caminho))
        elif sufixo in EXTENSOES_IMAGEM:
            artefatos.append(_artefato_imagem(caminho))

    for caminho in sorted((raiz / "whatsapp").glob("*.jsonl")):
        for msg in ler_mensagens_whatsapp(caminho):
            artefatos.append(_artefato_mensagem(msg, caminho))

    for caminho in sorted((raiz / "telegram").glob("*.jsonl")):
        for msg in ler_mensagens_telegram(caminho):
            artefatos.append(_artefato_mensagem(msg, caminho))

    return artefatos


__all__ = [
    "EXTENSOES_IMAGEM",
    "localizar_tesseract",
    "ler_pdf",
    "ocr_imagem",
    "ocr_pdf",
    "ler_mensagens_whatsapp",
    "ler_mensagens_telegram",
    "ingerir",
    "hash_mensagem",
    "busca_ocr",
    "confianca_ocr_simulado",
    "caminho_sidecar_ocr",
    "agora_iso",
    "TABELA_OCR",
]
