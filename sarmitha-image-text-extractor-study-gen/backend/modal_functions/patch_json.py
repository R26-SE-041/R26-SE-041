"""
Patch script: fix early_stopping:null in all cached HuggingFace JSON files.

transformers>=4.26 rejects early_stopping:null (must be bool or 'never').
Some Sinhala TrOCR models were saved with null in their decoder config.json
and generation_config.json. This script recursively walks both possible
HF cache directories and replaces null with False for early_stopping.
"""
import json
import os


def fix_dict(d):
    """Recursively replace early_stopping:None -> False in a dict."""
    if isinstance(d, dict):
        if "early_stopping" in d and d["early_stopping"] is None:
            d["early_stopping"] = False
        for v in d.values():
            fix_dict(v)
    elif isinstance(d, list):
        for item in d:
            fix_dict(item)


def patch_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fix_dict(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Patched: {path}")
    except Exception:
        pass


cache_dirs = ["/hf_cache", "/root/.cache/huggingface"]
for cache_dir in cache_dirs:
    if not os.path.exists(cache_dir):
        continue
    for root, _, files in os.walk(cache_dir):
        for fname in files:
            if fname.endswith(".json"):
                patch_file(os.path.join(root, fname))

print("Patch complete.")
