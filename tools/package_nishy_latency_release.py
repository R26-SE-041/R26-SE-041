"""Create a self-contained EC2 Session Manager update; embeds source, never secrets."""
import base64
import hashlib
import io
from pathlib import Path
import textwrap
import zipfile


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "nishy-adaptive-quiz-recommender"
FILES = [
    "backend/app/main.py",
    "backend/app/agents/quiz_agent.py",
    "backend/app/graph/graph.py",
    "backend/app/services/llm_service.py",
    "backend/app/services/grounding_service.py",
]


def main():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            archive.writestr(name, (COMPONENT / name).read_bytes())
    payload = stream.getvalue()
    encoded = "\n".join(textwrap.wrap(base64.b64encode(payload).decode(), 100))
    digest = hashlib.sha256(payload).hexdigest()
    script = r'''sudo bash <<'NISHY_LATENCY_RELEASE'
set -Eeuo pipefail
umask 077
root=/opt/nishy-quiz
cd "$root/deploy"
test -f compose.yml
test -f backend.env
command -v python3 >/dev/null
docker compose config --quiet
old_container=$(docker compose ps -q api)
test -n "$old_container"
old_image=$(docker inspect --format '{{.Image}}' "$old_container")
backup=$(mktemp -d "$root/latency-backup-XXXXXXXX")
export NISHY_RELEASE_ROOT="$root" NISHY_RELEASE_BACKUP="$backup"
cp -p backend.env "$backup/backend.env"
printf 'Backup directory: %s\n' "$backup"

rollback() {
    trap - ERR
    printf 'Deployment failed. Restoring previous files and image.\n' >&2
    python3 - <<'RESTORE'
import os, shutil
from pathlib import Path
root = Path(os.environ['NISHY_RELEASE_ROOT'])
backup = Path(os.environ['NISHY_RELEASE_BACKUP'])
for original in backup.glob('backend/app/**/*.py'):
    target = root / original.relative_to(backup)
    shutil.copy2(original, target)
shutil.copy2(backup / 'backend.env', root / 'deploy/backend.env')
RESTORE
    docker tag "$old_image" nishy-quiz-api:local
    docker compose up -d --no-deps --wait --wait-timeout 240 api || true
    printf 'Update failed; check docker compose ps. Backup: %s\n' "$backup" >&2
    exit 1
}
trap rollback ERR

python3 - <<'INSTALL'
import base64, hashlib, io, os, re, shutil, zipfile
from pathlib import Path
root = Path(os.environ['NISHY_RELEASE_ROOT']).resolve()
backup = Path(os.environ['NISHY_RELEASE_BACKUP']).resolve()
payload = base64.b64decode("""__PAYLOAD__""")
assert hashlib.sha256(payload).hexdigest() == '__DIGEST__', 'Release payload checksum mismatch'
allowed = __FILES__
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    assert set(archive.namelist()) == set(allowed), 'Unexpected release contents'
    for name in allowed:
        target = (root / name).resolve()
        assert root in target.parents and target.is_file(), f'Missing deployed source: {name}'
    for name in allowed:
        target = root / name
        saved = backup / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        target.write_bytes(archive.read(name))
        os.chmod(target, saved.stat().st_mode & 0o777)
env = root / 'deploy/backend.env'
content = env.read_text()
updates = {'QUIZ_GENERATION_BUDGET_SEC': '15', 'PRELOAD_EMBEDDINGS': 'true',
           'MODAL_HEALTH_CACHE_SEC': '30', 'MODAL_FAILURE_COOLDOWN_SEC': '30',
           'EMBEDDING_CACHE_SIZE': '2048'}
for key, value in updates.items():
    pattern = rf'(?m)^(?:export\s+)?{re.escape(key)}=.*$'
    replacement = f'{key}={value}'
    content = re.sub(pattern, replacement, content) if re.search(pattern, content) else content.rstrip() + '\n' + replacement + '\n'
env.write_text(content)
os.chmod(env, 0o600)
print('Installed five backend source files; generation budget: 15 seconds.')
print('Existing database credentials and persistent volumes preserved.')
INSTALL

# Reuse the existing dependency/image cache; no model or database migration changes.
docker compose build api
docker compose up -d --no-deps --wait --wait-timeout 240 api
docker compose exec -T api python - <<'VERIFY'
import urllib.request, json, os
for path in ('health', 'ready'):
    with urllib.request.urlopen('http://127.0.0.1:8000/' + path, timeout=15) as response:
        result = json.load(response)
        assert response.status == 200, path
        print(path + ': ' + result['status'])
import app.graph.graph  # Match the API startup import order before importing agents.
from app.services.llm_service import EmbeddingService
from app.agents.quiz_agent import _session_source_chunks
assert os.environ.get('QUIZ_GENERATION_BUDGET_SEC') == '15'
print('New source imports and 15-second runtime budget verified.')
VERIFY
trap - ERR
printf '\nBACKEND LATENCY UPDATE SUCCESSFUL\nRollback files: %s\n' "$backup"
printf 'No GPU warm-up or inference request was made by this script.\n'
printf 'Runtime backend.env updated. Keep the same non-secret settings in SSM before a future environment refresh.\n'
docker compose ps
NISHY_LATENCY_RELEASE
'''
    script = script.replace("__PAYLOAD__", encoded).replace("__DIGEST__", digest).replace("__FILES__", repr(FILES))
    output = COMPONENT / "deploy" / "artifacts" / "latency-update-20261019.sh"
    output.parent.mkdir(exist_ok=True)
    output.write_text(script, encoding="utf-8", newline="\n")
    print(f"Created {output}")
    print(f"Source files: {len(FILES)}; script bytes: {len(script.encode())}; payload SHA256: {digest}")


if __name__ == "__main__":
    main()
