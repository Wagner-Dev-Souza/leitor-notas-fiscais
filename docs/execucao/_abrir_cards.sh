#!/usr/bin/env bash
# PO abre a fase no Linear (cards -> In Progress) e envia o adendo de card aos devs da onda 1.
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<worktree>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"

echo "=== abrindo cards (In Progress) ==="
for k in PROJ-12 PROJ-13 PROJ-14 PROJ-15 PROJ-16 PROJ-17 PROJ-18; do
  r=$(orca linear save-issue "$k" --state "In Progress" 2>&1 | grep -io 'identifier"\?: *"[A-Z]*-[0-9]*' | head -1)
  echo "  $k -> ${r:-ok(sem echo)}"
done

adendo() {  # adendo <handle> <card> <papel>
  orca orchestration send --from "$COORD" --type question \
    --subject "Adendo do PO: ande seu card no Linear" \
    --to "$1" \
    --body "ADENDO DO PO (nao muda o escopo tecnico). Ao concluir e verificar seu codigo, ande seu card na sua fase: rode  orca linear save-issue $2 --state Done  e informe esse estado final no seu worker_done. Nao rode nenhum comando git - o PO versiona. Responda a esta mensagem apenas se estiver bloqueado; fora isso, siga trabalhando e reporte no worker_done." \
    --json > "docs/execucao/_ids/addendo_$2.json" 2>&1
  echo "  adendo -> $3 ($2): $(head -c 150 "docs/execucao/_ids/addendo_$2.json" | tr -d '\n')"
}

echo "=== adendo aos donos ==="
adendo term_b547b3bc-4357-430e-b8d4-9c726072f359 PROJ-13 avareza
adendo term_c0918dc8-6a5b-416c-a916-9c8e9f1ecdee PROJ-14 gula
adendo term_70d39b7e-f03c-4958-959d-d0445491f13a PROJ-15 preguica
adendo term_e1f5c6ca-d328-4379-a180-8870cc285941 PROJ-16 inveja
echo "== fim =="
