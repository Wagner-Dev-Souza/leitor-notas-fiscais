#!/usr/bin/env bash
# Onda 2: correcao de auditoria (avareza) + testes (ira) + documentacao (luxuria).
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<local>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"
OUT="docs/execucao/_ids"
RUN=$(cat "$OUT/run_id.txt")

T_AVAREZA="term_b547b3bc-4357-430e-b8d4-9c726072f359"
T_IRA="term_8af70f3d-9c87-4d42-a823-cb7db2d5a9bd"
T_LUXURIA="term_19b203fa-cde6-4fe7-840a-155eb35a57f5"

echo "== task F1b (correcao de auditoria) =="
orca orchestration task-create --run "$RUN" --from "$COORD" \
  --task-title "F1b Correcao: trilha de auditoria cumulativa (nao truncar)" \
  --display-name "F1b" --spec "$(cat docs/execucao/spec-F1b.md)" --json > "$OUT/task_F1b.json" 2>&1
F1B=$(python -c "
import json
try:
    d=json.load(open('$OUT/task_F1b.json')); print(d['result']['task']['id'])
except Exception as e:
    print('')")
echo "F1b task=[$F1B]"; echo "$F1B" > "$OUT/task_F1b.id"

disp(){  # disp <lbl> <handle> <taskid>
  orca orchestration dispatch --run "$RUN" --from "$COORD" --task "$3" --to "$2" --inject --json \
    > "$OUT/dispatch_$1.json" 2>&1
  python -c "
import json
try:
    d=json.load(open('$OUT/dispatch_$1.json')); r=d.get('result',{})
    print('  $1 injected=', r.get('injected'), 'dispatch=', (r.get('dispatch') or {}).get('id'))
except Exception as e: print('  $1 ERRO', e)
"
}

echo "== despachando F1b -> avareza =="
[ -n "$F1B" ] && disp F1b "$T_AVAREZA" "$F1B"

echo "== despachando onda 2 =="
disp F5 "$T_IRA" "$(cat "$OUT/task_F5.id")"
disp F6 "$T_LUXURIA" "$(cat "$OUT/task_F6.id")"
echo "== fim =="
