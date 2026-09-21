#!/usr/bin/env bash
# Cria o Run de orquestracao e as 6 tarefas da fase de execucao.
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<local>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"   # painel soberba = endereco do coordenador PO
OUT="docs/execucao/_ids"
mkdir -p "$OUT"

echo "== run-create =="
orca orchestration run-create --from "$COORD" \
  --objective "Execucao da fase 2 (entrega do produto): pipeline local offline que le PDFs de NF/pedido (nativo + escaneado via OCR) e mensagens mock de WhatsApp/Telegram, extrai numero do pedido, emitente/CNPJ, datas, valor total e itens, e grava numa planilha de controle financeiro de forma idempotente e auditavel, executavel por um comando unico." \
  --json > "$OUT/run.json" 2>"$OUT/run.err"
head -c 900 "$OUT/run.json"; echo; echo "-- stderr --"; head -c 400 "$OUT/run.err"

RUN_ID=$(python -c "import json,sys;d=json.load(open('$OUT/run.json'));print(d.get('runId') or d.get('run',{}).get('id') or d.get('id',''))" 2>/dev/null)
echo "RUN_ID=[$RUN_ID]"
echo "$RUN_ID" > "$OUT/run_id.txt"
