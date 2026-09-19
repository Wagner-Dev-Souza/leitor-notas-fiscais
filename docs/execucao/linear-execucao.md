## Fase de execucao - entrega do produto

Fase 2 do projeto PROJ-2. Planejamento encerrado (docs/01..06, PROJ-6..PROJ-11).
Ordem do cliente: entregar o **produto final executavel**, nao mais planejamento.
Execucao comeca automaticamente; so para com STOP do cliente ou projeto completo.

### O que e o produto

Pipeline local e offline que le PDFs de nota fiscal e de pedido (incluindo um caso
escaneado por OCR), le mensagens simuladas de WhatsApp e Telegram, extrai numero do
pedido, emitente/CNPJ, datas, valor total e itens, e grava numa planilha de controle
financeiro, de forma **idempotente** e com **trilha de auditoria**.

Comando unico de ponta a ponta:
`.venv/Scripts/python.exe -m app.run --mock`

### Material do cliente

Nao vira nenhum. O cliente nao envia PDFs, mensagens nem planilha. Todo o material e
**sintetico e gerado por script no proprio repositorio** (`tools/gerar_mocks.py`):
PDFs de nota fiscal/pedido (nativos e um escaneado), mensagens de WhatsApp/Telegram em
formato realista, e a planilha de destino criada pelo sistema. Zero servico pago,
zero numero real, zero chave nova, zero rede em tempo de execucao.

### Decisoes do PO (registradas)

- Alvo desta entrega: processo local unico + SQLite (recomendacao do doc 01). A divergencia
  com o doc 04 (VPS/Docker/Postgres) fica aberta para a fase de producao - nao se resolve aqui.
- OCR: nao ha Tesseract nesta maquina. O caminho escaneado usa **motor de OCR simulado**
  rotulado como simulado na auditoria e no README. Nao se apresenta OCR simulado como real.
- Contrato de integracao congelado em `docs/execucao/00-contrato-execucao.md` e
  `app/contratos.py` (propriedade do PO, nao editavel pelos workers).
- Versionamento: **somente o PO roda `git`**, nos limites de onda. Elimina disputa de
  `index.lock` entre 7 processos no mesmo worktree.

### Frentes e donos

| Frente | Escopo | Dono | Card |
|---|---|---|---|
| F1 | Nucleo: ingestao (PDF nativo + OCR + mensagens), extracao, pipeline, CLI | avareza | filho |
| F2 | Dados: normalizacao, modelo, idempotencia, planilha, auditoria | gula | filho |
| F3 | Dados sinteticos: gerador de PDFs e mensagens, verificador de idempotencia | preguica | filho |
| F4 | Revisao humana: fila de excecoes e painel de acompanhamento | inveja | filho |
| F5 | Qualidade: testes automatizados + evidencia + casos adversariais | ira | filho |
| F6 | Documentacao: README e relatorio/apresentacao final | luxuria | filho |

Regra de dono do card por fase (em vigor): criacao = PO; construcao = dev da frente;
teste = ira; documentacao/relatorio = luxuria. Cada um anda o card na sua fase.

### Aceite

Ver secao 9 de `docs/execucao/00-contrato-execucao.md`. So vale o que voltou de execucao
real: comando que nao rodou nao aconteceu.
