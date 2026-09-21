#!/usr/bin/env bash
# Cria as 6 tarefas da fase de execucao no Run ja criado.
set -u
export PATH="$LOCALAPPDATA/Programs/orca/resources/bin:$PATH"
cd "<worktree>" || exit 1

COORD="term_1d23b48f-7417-485e-ad32-dd2c9e385b7d"
OUT="docs/execucao/_ids"
RUN_ID=$(python -c "import json;print(json.load(open('$OUT/run.json'))['result']['run']['id'])")
echo "RUN_ID=$RUN_ID"; echo "$RUN_ID" > "$OUT/run_id.txt"

mk() {   # mk <rotulo> <titulo> <arquivo-spec>
  local lbl="$1" title="$2" spec="$3"
  orca orchestration task-create --run "$RUN_ID" --from "$COORD" \
    --task-title "$title" --display-name "$lbl" \
    --spec "$(cat "$spec")" --json > "$OUT/task_$lbl.json" 2>"$OUT/task_$lbl.err"
  local tid
  tid=$(python -c "
import json
try:
    d=json.load(open('$OUT/task_$lbl.json'))
    r=d.get('result',{})
    t=r.get('task') or {}
    print(t.get('id') or r.get('taskId') or '')
except Exception as e:
    print('')
")
  echo "$lbl -> [$tid]"
  [ -n "$tid" ] && echo "$tid" > "$OUT/task_$lbl.id"
  [ -s "$OUT/task_$lbl.err" ] && { echo "  stderr:"; head -c 200 "$OUT/task_$lbl.err"; echo; }
}

mk F1 "F1 Nucleo: ingestao PDF+OCR+mensagens, extracao, pipeline e CLI"       docs/execucao/spec-F1.md
mk F2 "F2 Normalizacao, modelo de dados, idempotencia, planilha e auditoria"  docs/execucao/spec-F2.md
mk F3 "F3 Dados sinteticos: gerador de mocks e verificador de idempotencia"   docs/execucao/spec-F3.md
mk F4 "F4 Revisao humana: fila de excecoes e painel de acompanhamento"        docs/execucao/spec-F4.md
mk F5 "F5 Testes automatizados, casos adversariais e evidencia"              docs/execucao/spec-F5.md
mk F6 "F6 README e relatorio final da entrega"                               docs/execucao/spec-F6.md
echo "== fim =="
