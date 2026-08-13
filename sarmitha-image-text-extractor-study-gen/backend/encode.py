import base64
code = """import json, os
def fd(d):
    if isinstance(d, dict):
        if d.get("early_stopping") is None and "early_stopping" in d: d["early_stopping"] = False
        [fd(v) for v in d.values()]
    elif isinstance(d, list): [fd(i) for i in d]
for c in ["/hf_cache", "/root/.cache/huggingface"]:
    for r, _, fs in os.walk(c):
        for f in fs:
            if f.endswith(".json"):
                p = os.path.join(r, f)
                try:
                    d = json.load(open(p))
                    fd(d)
                    open(p, "w").write(json.dumps(d))
                    print("patched", p)
                except: pass
"""
print(base64.b64encode(code.encode('utf-8')).decode('utf-8'))
