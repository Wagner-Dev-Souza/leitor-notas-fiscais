#!/usr/bin/env bash
# Monitor durável do Run: imprime mensagens novas e para quando as 4 frentes da onda 1 concluirem.
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<local>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"
RUN=$(cat docs/execucao/_ids/run_id.txt)
IDS="docs/execucao/_ids"
SEEN="$IDS/seen_ids.txt"; : > "$SEEN"
LOG="$IDS/monitor.log"; : > "$LOG"

T_W1="task_73228873f5e4 task_92daee272b4e task_572a9ab00fa6 task_2900551aaf36"
DEADLINE=$(( $(date +%s) + 5400 ))   # teto de 90 min

log(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
log "monitor iniciado - run=$RUN"

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  orca orchestration check --terminal "$COORD" --run "$RUN" --all --json > "$IDS/inbox_live.json" 2>/dev/null
  python - "$IDS/inbox_live.json" "$SEEN" "$LOG" "$T_W1" <<'PY'
import json, sys, datetime
inbox, seen_path, log_path, w1 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split()
try:
    d = json.load(open(inbox, encoding='utf-8'))
except Exception:
    sys.exit(0)
seen = set(open(seen_path, encoding='utf-8').read().split())
msgs = d.get('result', {}).get('messages') or []
novos = [m for m in msgs if m.get('id') not in seen]
for m in sorted(novos, key=lambda x: x.get('created_at') or ''):
    p = m.get('payload') or {}
    if isinstance(p, str):
        try: p = json.loads(p)
        except Exception: p = {}
    if m.get('type') == 'heartbeat':
        print(f"  . heartbeat {m.get('from_handle','')[-8:]} {p.get('phase','')}")
    else:
        with open(log_path, 'a', encoding='utf-8') as fh:
            fh.write(f"{m.get('created_at')} | {m.get('type')} | {m.get('subject')} | outcome={p.get('outcome')}\n")
        print(f"  > {m.get('type').upper()} de {str(m.get('from_handle'))[-8:]}: {m.get('subject')} [outcome={p.get('outcome')}]")
    with open(seen_path, 'a', encoding='utf-8') as fh:
        fh.write(str(m.get('id')) + "\n")
done_count = sum(1 for m in msgs
                 if m.get('type') == 'worker_done'
                 and str((m.get('payload') or {}).get('taskId')) in w1)
print(f"  [frentes onda1 concluidas: {done_count}/4]")
open(seen_path.replace('seen_ids', 'w1_done_count'), 'w').write(str(done_count))
PY
  DONE=$(cat "$IDS/w1_done_count" 2>/dev/null || echo 0)
  if [ "$DONE" = "4" ]; then log "onda 1 completa (4/4)"; break; fi
  sleep 45
done
log "monitor encerrado"
