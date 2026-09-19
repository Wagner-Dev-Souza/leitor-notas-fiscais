#!/usr/bin/env python
"""Monitor do Run de orquestracao. Le a inbox do coordenador, imprime mensagens novas
e encerra quando todas as frentes da onda enviarem worker_done (ou no teto de tempo).

Uso: python docs/execucao/_monitor.py <run_id> <coord_handle> <frentes...>
"""
import json
import subprocess
import sys
import time
from pathlib import Path

RUN = sys.argv[1]
COORD = sys.argv[2]
FRENTES = sys.argv[3:]
IDS = Path("docs/execucao/_ids")
IDS.mkdir(parents=True, exist_ok=True)
SEEN = IDS / "seen_ids.txt"
LOG = IDS / "monitor.log"


def payload_de(m):
    p = m.get("payload")
    if isinstance(p, str):
        try:
            return json.loads(p)
        except Exception:
            return {}
    return p or {}


def ler_inbox():
    r = subprocess.run(
        ["orca", "orchestration", "check", "--terminal", COORD, "--run", RUN,
         "--all", "--json"],
        capture_output=True, text=True, timeout=120,
    )
    try:
        return json.loads(r.stdout).get("result", {}).get("messages") or []
    except Exception:
        return []


def main():
    vistos = set(SEEN.read_text(encoding="utf-8").split()) if SEEN.exists() else set()
    teto = time.time() + 5400
    print(f"monitor iniciado | run={RUN} | frentes={len(FRENTES)}", flush=True)
    while time.time() < teto:
        msgs = ler_inbox()
        novos = False
        for m in sorted(msgs, key=lambda x: x.get("created_at") or ""):
            if m.get("id") in vistos:
                continue
            vistos.add(m["id"])
            novos = True
            p = payload_de(m)
            who = str(m.get("from_handle"))[-8:]
            if m.get("type") == "heartbeat":
                print(f"  . hb {who} {p.get('phase','')}", flush=True)
            else:
                linha = (f"{m.get('created_at')} | {m.get('type')} | {m.get('subject')} "
                         f"| outcome={p.get('outcome')}\n")
                with LOG.open("a", encoding="utf-8") as fh:
                    fh.write(linha)
                print(f"  > {str(m.get('type')).upper()} {who}: {m.get('subject')} "
                      f"[outcome={p.get('outcome')}]", flush=True)
            with SEEN.open("a", encoding="utf-8") as fh:
                fh.write(m["id"] + "\n")
        feitas = {payload_de(m).get("taskId") for m in msgs if m.get("type") == "worker_done"}
        n = sum(1 for f in FRENTES if f in feitas)
        if novos or n:
            print(f"  [frentes concluidas: {n}/{len(FRENTES)}]", flush=True)
        (IDS / "frentes_done.txt").write_text(str(n), encoding="utf-8")
        if n >= len(FRENTES):
            print("TODAS AS FRENTES CONCLUIDAS", flush=True)
            return
        time.sleep(40)
    print("monitor encerrado por teto de tempo", flush=True)


main()
