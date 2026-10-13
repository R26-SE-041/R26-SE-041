"""Inspect existing workspace-owned TTS cache metadata; never copy weights."""
from pathlib import Path
import hashlib
import os
import modal

app = modal.App("voicelearn-tts-cache-inventory")
volume = modal.Volume.from_name("voicelearn-models")


@app.function(cpu=1, memory=1024, timeout=120, volumes={"/models": volume})
def inspect_cache():
    result = {}
    root = Path("/models/indic-parler-tts")
    for repo in ("models--ai4bharat--indic-parler-tts", "models--google--flan-t5-large"):
        snapshots = {}
        for snapshot in (root / repo / "snapshots").glob("*"):
            files = {}
            for path in snapshot.iterdir():
                if path.is_file():
                    files[path.name] = {"bytes": path.stat().st_size,
                        "blob": os.readlink(path) if path.is_symlink() else None,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.stat().st_size < 1_000_000 else None}
            snapshots[snapshot.name] = files
        result[repo] = snapshots
    return result


@app.local_entrypoint()
def main():
    import json
    print(json.dumps(inspect_cache.remote()))
