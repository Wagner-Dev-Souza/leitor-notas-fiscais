"""Monta a rastreabilidade da fase de execucao: run, tarefas, dispatches e
os relatos (worker_done) de cada frente. Le o dump da inbox do coordenador.
"""
import json
import subprocess
import sys
from pathlib import Path

IDS = Path("docs/execucao/_ids")
RUN = (IDS / "run_id.txt").read_text(encoding="utf-8").strip()

# dump fresco da inbox
r = subprocess.run(
    ["orca", "orchestration", "check", "--terminal",
     "term_1d23b48f-7417-485e-ad32-dd2c9e385b7d", "--run", RUN, "--all", "--json"],
    capture_output=True, text=True, timeout=180,
)
msgs = json.loads(r.stdout)["result"]["messages"]


def payload(m):
    p = m.get("payload")
    if isinstance(p, str):
        try:
            return json.loads(p)
        except Exception:
            return {}
    return p or {}


linhas = []
for m in msgs:
    p = payload(m)
    if m.get("type") == "worker_done":
        linhas.append({
            "task": p.get("taskId"),
            "dispatch": p.get("dispatchId"),
            "outcome": p.get("outcome"),
            "subject": m.get("subject"),
            "from": m.get("from_handle"),
            "at": m.get("created_at"),
            "files": p.get("filesModified") or [],
            "report": p.get("reportPath"),
            "body": (m.get("body") or "").strip(),
        })

linhas.sort(key=lambda x: x["at"] or "")
print(f"RUN = {RUN}")
print(f"worker_done recebidos: {len(linhas)}\n")
for x in linhas:
    print("=" * 100)
    print(f"{x['at']} | {x['subject']} | outcome={x['outcome']}")
    print(f"  task={x['task']} dispatch={x['dispatch']} from={x['from']}")
    if x["files"]:
        print(f"  arquivos: {x['files']}")
    if x["report"]:
        print(f"  relatorio: {x['report']}")
    print("-" * 100)
    print(x["body"])

# dump completo para o relatorio
(IDS / "relatos_worker_done.md").write_text(
    "\n\n".join(
        f"## {x['at']} - {x['subject']}\n\n- task: `{x['task']}`\n- dispatch: `{x['dispatch']}`\n"
        f"- outcome: **{x['outcome']}**\n- arquivos: {x['files']}\n\n{x['body']}"
        for x in linhas
    ),
    encoding="utf-8",
)
print("\n[salvo em docs/execucao/_ids/relatos_worker_done.md]")
