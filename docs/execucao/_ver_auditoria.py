import json
import os
import sys

caminho = sys.argv[1] if len(sys.argv) > 1 else "data/out/auditoria.jsonl"
for linha in open(caminho, encoding="utf-8"):
    linha = linha.strip()
    if not linha:
        continue
    r = json.loads(linha)
    a = os.path.basename(str(r.get("artefato", "")))
    print(f"{a:44s} {str(r.get('acao')):12s} motor={str(r.get('motor')):13s} "
          f"ocr={str(r.get('ocr_usado')):5s} ped={str(r.get('numero_pedido')):6s} "
          f"val={str(r.get('valor_total_centavos')):8s} conf={str(r.get('confianca')):7s} "
          f"{r.get('motivos')}")
