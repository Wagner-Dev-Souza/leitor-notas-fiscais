#!/usr/bin/env python
"""Gera o painel do quadro do squad (Linear) como arquivo versionado no repositorio.

Por que existe
--------------
O Linear nao oferece link publico de quadro: quem nao e membro do workspace nao ve
nada, mesmo com o link no README. Este script le o estado real dos cards pela API e
escreve uma tabela legivel em `docs/linear/painel.md`. O quadro passa a ter uma
versao que acompanha a evolucao do projeto e que qualquer pessoa consegue ler.

O que ele NAO faz
-----------------
Nao grava dump da API. A saida tem o que o quadro mostra -- card, frente, dono,
situacao, data de conclusao e link -- e nada de id interno de execucao, payload de
dispatch ou resposta crua da API. A chave e lida do ambiente e nunca e escrita.

Uso
---
    LINEAR_API_KEY=<chave> python tools/painel_linear.py

Variaveis opcionais:
    LINEAR_TIMEKEY   chave do time no Linear (padrao: PROJ)
    LINEAR_SAIDA     arquivo gerado (padrao: docs/linear/painel.md)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

URL_API = "https://api.linear.app/graphql"
RAIZ_PROJETO = Path(__file__).resolve().parent.parent

# O quadro cabe em uma consulta. Os cards sao filtrados por time aqui, no script, em
# vez de na consulta: menos dependencia do formato de filtro da API.
CONSULTA = """
query Painel {
  issues(first: 250, includeArchived: true) {
    nodes {
      identifier
      title
      url
      createdAt
      completedAt
      state { name type }
      assignee { name }
      parent { identifier }
      team { key }
    }
  }
}
"""

SITUACAO = {
    "completed": "✅ Concluído",
    "started": "🔄 Em andamento",
    "unstarted": "⬜ A fazer",
    "backlog": "📋 Backlog",
    "triage": "🔎 Triagem",
    "canceled": "🚫 Cancelado",
}

ORDEM_SITUACAO = ("completed", "started", "unstarted", "backlog", "triage", "canceled")

# Situacoes que ficam fora do fluxo principal do projeto. Cards assim, sem filhos,
# entram em um bloco unico no fim: senao o painel vira uma lista de secoes de uma
# linha so.
FORA_DO_FLUXO = ("canceled", "backlog", "triage")

# Offset fixo: o horario de Brasilia nao usa mais horario de verao (UTC-3 o ano todo).
OFFSET_BRASILIA = timedelta(hours=-3)

# Titulos do tipo "Arquitetura da solucao (avareza: arquiteto/backend)" carregam o
# papel de quem assumiu a frente. O quadro nao tem responsavel atribuido, entao esse
# e o dono disponivel -- e vale registrar. O ":" dentro do parenteses e o que separa
# papel de anotacao solta (ex.: "(msg_509f61d3a612)" e anotacao, nao papel).
PAPEL_NO_TITULO = re.compile(r"\(([^()]*:[^()]*)\)\s*$")
DIGITOS_FINAIS = re.compile(r"(\d+)$")


def consultar(chave: str) -> list[dict]:
    """Le o quadro do Linear. Devolve apenas os cards, sem payload cru da API."""
    corpo = json.dumps({"query": CONSULTA}).encode("utf-8")
    requisicao = urllib.request.Request(
        URL_API,
        data=corpo,
        headers={"Content-Type": "application/json", "Authorization": chave},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=60) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code in (400, 401, 403):
            raise SystemExit(
                f"a API do Linear recusou a consulta (HTTP {erro.code}): "
                "confira se LINEAR_API_KEY esta valido e nao expirado"
            )
        raise SystemExit(f"falha ao consultar o Linear (HTTP {erro.code})")
    except urllib.error.URLError as erro:
        raise SystemExit(f"nao foi possivel falar com o Linear: {erro.reason}")

    if dados.get("errors"):
        raise SystemExit(f"o Linear devolveu erro: {dados['errors'][0].get('message', 'sem detalhe')}")

    return dados["data"]["issues"]["nodes"]


def em_brasilia(instante: str | None) -> str:
    """Converte o instante ISO (UTC) do Linear para o formato de leitura local."""
    if not instante:
        return "—"
    try:
        momento = datetime.fromisoformat(instante.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    return (momento + OFFSET_BRASILIA).strftime("%d/%m/%Y %H:%M")


def chave_ordenacao(identificador: str) -> tuple[str, int]:
    achado = DIGITOS_FINAIS.search(identificador)
    return (identificador[: achado.start()] if achado else identificador, int(achado.group(1)) if achado else 0)


def dono_do_card(card: dict) -> str:
    """Responsavel atribuido no quadro ou, na falta dele, o papel declarado no titulo."""
    nome = (card.get("assignee") or {}).get("name")
    if nome:
        return nome
    achado = PAPEL_NO_TITULO.search(card.get("title", "").strip())
    return achado.group(1) if achado else "—"


def situacao_do_card(card: dict) -> str:
    tipo = (card.get("state") or {}).get("type", "unstarted")
    return SITUACAO.get(tipo, (card.get("state") or {}).get("name", tipo))


def tipo_do_card(card: dict) -> str:
    return (card.get("state") or {}).get("type", "unstarted")


def montar_painel(cards: list[dict], timekey: str) -> str:
    """Monta o markdown: uma secao por projeto raiz, uma tabela por projeto."""
    por_id = {card["identifier"]: card for card in cards}

    def pai_de(identificador: str) -> str:
        return (por_id.get(identificador, {}).get("parent") or {}).get("identifier", "")

    def raiz_de(identificador: str) -> str:
        visto = {identificador}
        atual = identificador
        while True:
            pai = pai_de(atual)
            if not pai or pai not in por_id or pai in visto:
                return atual
            visto.add(pai)
            atual = pai

    grupos: dict[str, list[dict]] = {}
    for card in cards:
        grupos.setdefault(raiz_de(card["identifier"]), []).append(card)

    # Cards soltos e fora do fluxo (teste cancelado, card de backlog orfao) nao merecem
    # secao propria: vao para um bloco unico no fim.
    soltos: list[dict] = []
    secoes: list[str] = []
    for raiz in sorted(grupos, key=chave_ordenacao):
        card_raiz = por_id[raiz]
        if len(grupos[raiz]) == 1 and tipo_do_card(card_raiz) in FORA_DO_FLUXO:
            soltos.append(card_raiz)
        else:
            secoes.append(raiz)

    linhas: list[str] = []
    agora = datetime.now() + OFFSET_BRASILIA
    linhas.append(f"# Painel do squad — quadro do Linear (time `{timekey}`)")
    linhas.append("")
    linhas.append(
        f"> Retrato do quadro em **{agora.strftime('%d/%m/%Y %H:%M')}** (horário de Brasília)."
    )
    linhas.append(
        "> Arquivo gerado por `tools/painel_linear.py` a partir dos cards. Não edite à mão: "
        "o próximo ciclo sobrescreve."
    )
    linhas.append("")

    contagem: dict[str, int] = {}
    for card in cards:
        contagem[tipo_do_card(card)] = contagem.get(tipo_do_card(card), 0) + 1

    linhas.append("## Resumo")
    linhas.append("")
    linhas.append("| Situação | Cards |")
    linhas.append("|---|---|")
    for tipo in ORDEM_SITUACAO:
        if contagem.get(tipo):
            linhas.append(f"| {SITUACAO[tipo]} | {contagem[tipo]} |")
    linhas.append(f"| **Total** | **{len(cards)}** |")
    linhas.append("")

    for raiz in secoes:
        card_raiz = por_id[raiz]
        linhas.append(f"## {raiz} — {card_raiz.get('title', '')}")
        linhas.append("")
        linhas.append(f"{situacao_do_card(card_raiz)}" + (f" · [abrir no Linear]({card_raiz['url']})" if card_raiz.get("url") else ""))
        linhas.append("")

        itens = [c for c in sorted(grupos[raiz], key=lambda c: chave_ordenacao(c["identifier"])) if c["identifier"] != raiz]
        if itens:
            linhas.append("| Frente | Card | Dono | Situação | Concluído em |")
            linhas.append("|---|---|---|---|---|")
            for item in itens:
                frente = pai_de(item["identifier"]) or "—"
                titulo = item.get("title", "").replace("|", "/")
                linhas.append(
                    f"| {frente} | {item['identifier']} — {titulo} | {dono_do_card(item)} | "
                    f"{situacao_do_card(item)} | {em_brasilia(item.get('completedAt'))} |"
                )
            linhas.append("")

    if soltos:
        linhas.append("## Outros cards")
        linhas.append("")
        linhas.append("| Card | Dono | Situação | Concluído em |")
        linhas.append("|---|---|---|---|")
        for card in sorted(soltos, key=lambda c: chave_ordenacao(c["identifier"])):
            titulo = card.get("title", "").replace("|", "/")
            linhas.append(
                f"| {card['identifier']} — {titulo} | {dono_do_card(card)} | "
                f"{situacao_do_card(card)} | {em_brasilia(card.get('completedAt'))} |"
            )
        linhas.append("")

    linhas.append("---")
    linhas.append("")
    linhas.append(
        "A coluna **Frente** é o card pai: é ela que mostra as ondas de trabalho — as frentes "
        "especializadas, a execução do produto e o fechamento. O quadro vivo fica no Linear, "
        "com acesso restrito aos membros do workspace; este arquivo é o retrato versionado."
    )
    linhas.append("")
    return "\n".join(linhas)


def main() -> int:
    chave = os.environ.get("LINEAR_API_KEY", "").strip()
    if not chave:
        print(
            "LINEAR_API_KEY nao esta definida no ambiente. "
            "Defina a chave (nunca no codigo) e rode de novo.",
            file=sys.stderr,
        )
        return 2

    timekey = os.environ.get("LINEAR_TIMEKEY", "PROJ").strip()
    saida = Path(os.environ.get("LINEAR_SAIDA", RAIZ_PROJETO / "docs/linear/painel.md"))

    cards = [c for c in consultar(chave) if ((c.get("team") or {}).get("key") == timekey)]
    if not cards:
        print(f"nenhum card encontrado para o time {timekey}", file=sys.stderr)
        return 1

    conteudo = montar_painel(cards, timekey)
    anterior = saida.read_text(encoding="utf-8") if saida.exists() else ""
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(conteudo, encoding="utf-8")

    print(
        f"{saida.relative_to(RAIZ_PROJETO)}: {len(cards)} card(s) lidos, "
        f"arquivo {'atualizado' if conteudo != anterior else 'sem alteracao'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
