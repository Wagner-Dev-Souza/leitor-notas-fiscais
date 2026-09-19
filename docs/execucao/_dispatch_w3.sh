#!/usr/bin/env bash
# Onda 3: correcoes dos 3 defeitos apontados pelo QA, devolvidas aos donos.
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<local>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"
OUT="docs/execucao/_ids"
RUN=$(cat "$OUT/run_id.txt")

T_AVAREZA="term_b547b3bc-4357-430e-b8d4-9c726072f359"
T_GULA="term_c0918dc8-6a5b-416c-a916-9c8e9f1ecdee"
T_PREGUICA="term_70d39b7e-f03c-4958-959d-d0445491f13a"

novo(){  # novo <lbl> <titulo> <spec>
  orca orchestration task-create --run "$RUN" --from "$COORD" \
    --task-title "$2" --display-name "$1" --spec "$(cat "$3")" --json > "$OUT/task_$1.json" 2>&1
  python -c "
import json
try:
    d=json.load(open('$OUT/task_$1.json')); print(d['result']['task']['id'])
except Exception as e: print('')" > "$OUT/task_$1.id"
  echo "  $1 task=[$(cat "$OUT/task_$1.id")]"
}

disp(){  # disp <lbl> <handle>
  local lbl="$1" handle="$2"
  orca orchestration dispatch --run "$RUN" --from "$COORD" \
    --task "$(cat "$OUT/task_$lbl.id")" --to "$handle" --inject --json > "$OUT/dispatch_$lbl.json" 2>&1
  python -c "
import json
try:
    d=json.load(open('$OUT/dispatch_$lbl.json')); r=d.get('result',{})
    print('  $lbl injected=', r.get('injected'), 'dispatch=', (r.get('dispatch') or {}).get('id'))
except Exception as e: print('  $lbl ERRO', e)"
}

echo "== criando tarefas de correcao =="
novo F3b "F3b Correcao: chave B4 inventada no manifesto + degradacao OCR fora do contrato" docs/execucao/spec-F3b.md
novo F2b "F2b Correcao: motivo total_sem_detalhamento quando a soma nao e calculavel"      docs/execucao/spec-F2b.md
novo F1c "F1c Correcao: tem_camada_texto no caminho de OCR simulado"                       docs/execucao/spec-F1c.md

echo "== despachando =="
disp F3b "$T_PREGUICA"
disp F2b "$T_GULA"
disp F1c "$T_AVAREZA"
echo "== fim =="
