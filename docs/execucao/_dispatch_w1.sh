#!/usr/bin/env bash
# Despacha a onda 1 (F1..F4) para os terminais dos devs via --inject.
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<worktree>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"
OUT="docs/execucao/_ids"
RUN_ID=$(cat "$OUT/run_id.txt")

T_AVAREZA="term_b547b3bc-4357-430e-b8d4-9c726072f359"
T_GULA="term_c0918dc8-6a5b-416c-a916-9c8e9f1ecdee"
T_PREGUICA="term_70d39b7e-f03c-4958-959d-d0445491f13a"
T_INVEJA="term_e1f5c6ca-d328-4379-a180-8870cc285941"

disp() {  # disp <lbl> <handle>
  local lbl="$1" handle="$2"
  local tid; tid=$(cat "$OUT/task_$lbl.id")
  orca orchestration dispatch --run "$RUN_ID" --from "$COORD" \
    --task "$tid" --to "$handle" --inject --json \
    > "$OUT/dispatch_$lbl.json" 2>"$OUT/dispatch_$lbl.err"
  python -c "
import json
try:
    d=json.load(open('$OUT/dispatch_$lbl.json'))
    r=d.get('result',{})
    dp=r.get('dispatch') or {}
    print('$lbl', 'injected=', r.get('injected'), 'dispatchId=', dp.get('id') or dp.get('dispatchId'), 'ok=', d.get('ok'))
except Exception as e:
    print('$lbl PARSE-ERR', e)
    print(open('$OUT/dispatch_$lbl.json').read()[:300])
"
  if [ -s "$OUT/dispatch_$lbl.err" ]; then echo "  stderr: $(head -c 200 "$OUT/dispatch_$lbl.err")"; fi
}

echo "=== SPRINT IA INICIO: $(date '+%Y-%m-%d %H:%M:%S %z') ===" | tee "$OUT/sprint_inicio.txt"
disp F1 "$T_AVAREZA"
disp F2 "$T_GULA"
disp F3 "$T_PREGUICA"
disp F4 "$T_INVEJA"
echo "== onda 1 despachada =="
