## Fase de execucao ENCERRADA - entrega do produto concluida

**Fim da sprint de execucao em IA: 2026-09-19 13:20:50 -03.**
Duracao total da fase: **40 min 04 s** de tempo de parede (inicio 12:40:46 -03).

### Estado final

- `.venv/Scripts/python.exe -m app.run --mock` roda de ponta a ponta: 20 artefatos
  ingeridos, 7 auto-aprovados, 10 em revisao humana, 2 rejeitados, 1 deduplicado,
  **7 linhas** na planilha.
- Segunda rodada: 20 artefatos deduplicados, **7 linhas** - idempotencia provada em 3
  rodadas independentes (o PO rodou; `tools/verificar.py` tambem passa).
- `.venv/Scripts/python.exe -m pytest -q` -> **284 passed, 0 failed**.
- `data/out/`: planilha `.xlsx` (20 colunas) e `.csv`, `auditoria.jsonl` cumulativa com
  `rodada_id`, `auditoria_rodada_*.jsonl`, `fila_excecoes.json`, `painel.html`,
  `pipeline.db`.
- PDF escaneado sem camada de texto entra pelo caminho de OCR **simulado**, rotulado como
  simulado na trilha e no resumo; CNPJ e chave de acesso saem corretos mesmo com a
  degradacao.

### Defeitos encontrados e fechados (nao maquiados)

O QA (ira) reportou honestamente 4 falhas / 3 defeitos em vez de ajustar as assercoes, e o
PO devolveu cada um ao dono. Todos corrigidos e reverificados pelo PO:

| # | Defeito | Dono | Correcao |
|---|---|---|---|
| D1 | `manifest.json` dava a copia B4 uma chave de acesso que o documento (byte-identico ao original) nao contem | preguica | manifest regenerado, chave igual a do original |
| D2 | OCR simulado degradava `F` por `E`, fora do conjunto congelado | preguica | degradacao restrita a `0/O, 1/l/I, 5/S, 2/Z` + espacos |
| D3 | `decidir()` dizia `divergencia_soma_itens` quando a soma nem podia ser calculada | gula | agora `total_sem_detalhamento` |
| D4 | `tem_camada_texto` voltava `True` num PDF de imagem | avareza | agora `False` |

### Correcao minha (PO), declarada

O defeito mais grave da fase foi encontrado por mim na verificacao de aceite:
`app/pipeline.py` **apagava** `data/out/auditoria.jsonl` a cada rodada - a trilha de
auditoria se destruia. A trilha agora e cumulativa. Achado, dono, conserto e nova
emenda ao contrato.

### Quem andou cada card

| Card | Frente | Dono | Andou |
|---|---|---|---|
| PROJ-13 | F1 nucleo | avareza | avareza (In Progress -> Done) |
| PROJ-14 | F2 dados | gula | gula |
| PROJ-15 | F3 dados sinteticos | preguica | preguica |
| PROJ-16 | F4 revisao humana | inveja | inveja |
| PROJ-17 | F5 testes | ira | **PO** (fechado na consolidacao - o dono entregou e reportou, mas nao moveu o card) |
| PROJ-18 | F6 documentacao | luxuria | **PO** (idem) |
| PROJ-12 | fase de execucao | PO soberba | PO |

Falha de processo assumida: o adendo pedindo que cada dono andasse o proprio card chegou,
mas F5 e F6 nao o executaram - os donos entregaram o trabalho e reportaram `worker_done`,
porem sem mover o card. O PO fechou os dois na consolidacao para nao deixar a fase em
estado ambiguo. Registrado para a proxima fase: o passo de andar o card precisa entrar no
proprio `worker_done` como item obrigatorio, nao como adendo separado.

### Fica fora desta fase (projeto NAO encerrado)

PROJ-2 permanece **In Progress**: a entrega do produto e uma fase, nao o projeto. Falta a
homologacao com dados reais do cliente, a decisao de infraestrutura de producao (divergencia
entre docs 01 e 04, ainda aberta) e a decisao sobre o numero de WhatsApp.
