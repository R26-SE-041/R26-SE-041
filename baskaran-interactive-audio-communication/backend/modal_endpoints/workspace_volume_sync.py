"""Copy existing production weights between authorized Modal workspaces.

Credentials travel only as encrypted function arguments and are never printed
or stored in files. Existing volumes and unrelated files are retained.
"""
from pathlib import Path
import modal

app = modal.App("voicelearn-workspace-volume-sync")
image = modal.Image.debian_slim(python_version="3.11").pip_install("modal==1.6.1")
target = modal.Volume.from_name("voicelearn-models", create_if_missing=True)


@app.function(image=image, cpu=2, memory=2048, timeout=3600, volumes={"/target": target})
def sync(source_token_id: str, source_token_secret: str):
    client = modal.Client.from_credentials(source_token_id, source_token_secret)
    source = modal.Volume.from_name("voicelearn-models", environment_name="main", client=client)
    copied, retained = [], []
    for directory in ("/gemma/adapters/v2", "/sinhala_asr/stage2_final"):
        for entry in source.iterdir(directory, recursive=True):
            if entry.type != modal.volume.FileEntryType.FILE or "/.cache/" in entry.path:
                continue
            relative = entry.path.lstrip("/")
            destination = Path("/target") / relative
            # Preserve large complete files; refresh small configuration files.
            if destination.is_file() and destination.stat().st_size == entry.size and entry.size > 1_000_000:
                retained.append(relative)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_suffix(destination.suffix + ".sync-partial")
            with partial.open("wb") as handle:
                for chunk in source.read_file(entry.path):
                    handle.write(chunk)
            if partial.stat().st_size != entry.size:
                raise RuntimeError(f"Incomplete transfer: {relative}")
            partial.replace(destination)
            copied.append(relative)
        target.commit()
    return {"copied": copied, "retained": retained}


@app.local_entrypoint()
def main():
    import json
    import tomllib
    config = tomllib.loads((Path.home() / ".modal.toml").read_text())
    credentials = config["visakanbaskaran"]
    print(json.dumps(sync.remote(credentials["token_id"], credentials["token_secret"])))
