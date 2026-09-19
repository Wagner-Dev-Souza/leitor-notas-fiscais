### Fase de execucao aberta - PO (soberba)

**Inicio da sprint de execucao em IA: 2026-09-19 12:40:46 -03** (Run `run_50dff8b29067`).

**Bloqueio de interface resolvido antes do disparo.** Para que quatro agentes escrevessem no
mesmo worktree sem colidir, o PO congelou a fronteira de integracao antes de distribuir:

- `app/contratos.py` - dataclasses, limiares e o payload normalizado. Propriedade do PO,
  **nao editavel** pelos workers. Derivado dos docs 01 (secao 3.3) e 02 (secoes 2 a 4) que o
  proprio squad produziu no planejamento - nada foi inventado aqui.
- `docs/execucao/00-contrato-execucao.md` - a lei da fase: layout de arquivos com **dono
  nomeado por arquivo**, formatos de mock, as 20 colunas da planilha, as assinaturas de funcao
  obrigatorias e a definicao de pronto.
- **Somente o PO roda `git`**, nos limites de onda. Sete processos no mesmo worktree disputando
  `index.lock` seria falha garantida; os workers deixam o arquivo e o PO versiona.

**Ambiente preparado pelo PO** (fundacao compartilhada, para nao haver corrida de venv):
`.venv` com CPython 3.12.14 via `uv`, com `pypdf`, `pdfplumber`, `reportlab`, `openpyxl`,
`pytest` e `pillow`. Toolchain validada por teste de fumaca antes do disparo: PDF com camada
de texto lido corretamente, PDF de imagem retornando zero caractere (simulacao de escaneado)
e `.xlsx` gravado e relido.

**Decisao de OCR, registrada com honestidade:** nao existe Tesseract nesta maquina e o cliente
proibiu instalar servico/infra. O caminho de documento escaneado usa **motor de OCR simulado**
(sidecar de transcricao com degradacao realista), **rotulado como simulado** na trilha de
auditoria e no README. OCR real e usado se e somente se houver Tesseract instalado. Nao se
apresenta saida simulada como OCR real.

**Onda 1 despachada** (`--inject`, quatro frentes em paralelo, arquivos disjuntos):

| Frente | Card | Dono | Arquivos |
|---|---|---|---|
| F1 nucleo (ingestao, extracao, pipeline, CLI) | PROJ-13 | avareza | `app/ingress.py`, `app/extracao.py`, `app/pipeline.py`, `app/run.py` |
| F2 dados (normalizacao, idempotencia, planilha, auditoria) | PROJ-14 | gula | `app/normaliza.py`, `app/persistencia.py` |
| F3 dados sinteticos (gerador + verificador) | PROJ-15 | preguica | `tools/gerar_mocks.py`, `tools/verificar.py` |
| F4 revisao humana (fila + painel) | PROJ-16 | inveja | `app/revisao.py` |

Onda 2 (F5 testes - ira / PROJ-17; F6 documentacao - luxuria / PROJ-18) entra quando a onda 1
fechar, porque depende do codigo existir.

**Regra de dono do card por fase aplicada:** criacao = PO (feito); construcao = dev da frente
(cada um anda o proprio card); teste = ira; documentacao/relatorio = luxuria.
