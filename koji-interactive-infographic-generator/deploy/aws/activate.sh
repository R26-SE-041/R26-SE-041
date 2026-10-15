#!/usr/bin/env bash
# Preserve the Ubuntu installation, .env, and existing systemd service paths.
set -Eeuo pipefail
sha="${1:?tested commit required}"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || exit 2
root="${KOJI_DEPLOY_ROOT:-/home/ubuntu/koji}"
backend="$root/backend"
stage="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ "$stage" == "$root/deploy-staging/"* ]] || exit 2
exec 9>"$root/deploy.lock"
flock -w 600 9
test -d "$backend/studio"
test -d "$backend/shared"
test -x "$backend/.venv/bin/python"
test -f "$backend/.env"
test ! -e "$stage/package"
mkdir "$stage/package"
python3 - "$stage/backend.tar.gz" "$stage/package" "$sha" <<'PY'
import hashlib,json,sys,tarfile
from pathlib import Path,PurePosixPath
archive,destination,commit=sys.argv[1:]
with tarfile.open(archive) as bundle:
    for entry in bundle.getmembers():
        parts=PurePosixPath(entry.name).parts
        assert entry.isfile() and parts and not entry.name.startswith('/') and '..' not in parts
        assert entry.name=='release.json' or parts[0] in {'studio','shared'}
    bundle.extractall(destination,filter='data')
manifest=json.loads((Path(destination)/'release.json').read_text())
assert manifest['commit']==commit
for name,digest in manifest['files'].items():
    path=PurePosixPath(name)
    assert not path.is_absolute() and '..' not in path.parts and path.parts[0] in {'studio','shared'}
    assert hashlib.sha256((Path(destination)/name).read_bytes()).hexdigest()==digest,name
print('Tested CPU backend artifact verified')
PY
mkdir -p "$root/deploy-environments" "$root/deploy-backups"
# Keep two previous releases and the active environment under the deployment lock.
# Only generated release directories with the expected contents are eligible.
python3 - "$root" <<'PY'
from pathlib import Path
import re, shutil, sys
root = Path(sys.argv[1]).resolve()
backups, environments = root / 'deploy-backups', root / 'deploy-environments'
managed = re.compile(r'[a-f0-9]{40}\.[A-Za-z0-9]{8}')
def generated(path, parent):
    return (path.is_dir() and not path.is_symlink() and path.resolve().parent == parent
            and managed.fullmatch(path.name))
releases = sorted((path for path in backups.iterdir() if generated(path, backups)
                   and {item.name for item in path.iterdir()} <= {'studio', 'shared', '.venv', 'release.json'}
                   and (path / 'release.json').is_file()), key=lambda path: path.stat().st_mtime, reverse=True)
for path in releases[2:]:
    shutil.rmtree(path)
    print('Removed old release backup:', path.name)
protected = {(root / 'backend/.venv').resolve()}
protected.update((path / '.venv').resolve() for path in backups.iterdir() if (path / '.venv').exists())
for path in environments.iterdir():
    if generated(path, environments) and path.resolve() not in protected:
        shutil.rmtree(path)
        print('Removed unused release environment:', path.name)
PY
# Keep virtual environments at stable absolute paths across activation.
environment="$(mktemp -d "$root/deploy-environments/$sha.XXXXXXXX")"
python3 -m venv "$environment"
"$environment/bin/python" -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cpu
"$environment/bin/python" -m pip install --disable-pip-version-check -r "$stage/package/studio/requirements.txt"
"$environment/bin/python" -m compileall -q "$stage/package/studio" "$stage/package/shared"
cd "$stage/package"
"$environment/bin/python" - "$backend/.env" <<'PY'
import sys
from dotenv import load_dotenv
load_dotenv(sys.argv[1])
from studio.main import app,ready
import studio.worker
assert '/studio/chats' in app.openapi()['paths']
ready()
from studio.documents import embed_texts
assert len(embed_texts(['Student PDF retrieval readiness'])[0]) == 384
print('Staged API, worker and existing database configuration verified')
PY
backup="$(mktemp -d "$root/deploy-backups/$sha.XXXXXXXX")"
[[ ! -f "$backend/release.json" ]] || cp "$backend/release.json" "$backup/release.json"
rollback() {
    trap - ERR
    set +e
    sudo -n systemctl stop koji-api.service koji-worker.service
    mkdir -p "$stage/failed"
    for name in studio shared .venv; do
        if [[ -e "$backup/$name" || -L "$backup/$name" ]]; then
            if [[ -e "$backend/$name" || -L "$backend/$name" ]]; then
                mv "$backend/$name" "$stage/failed/$name"
            fi
            mv "$backup/$name" "$backend/$name"
        fi
    done
    if [[ -f "$backup/release.json" ]]; then
        cp "$backup/release.json" "$backend/release.json"
    fi
    sudo -n systemctl restart koji-api.service koji-worker.service
    echo 'Deployment failed; previous backend and environment restored' >&2
    exit 1
}
trap rollback ERR
sudo -n systemctl stop koji-api.service koji-worker.service
for name in studio shared .venv; do
    mv "$backend/$name" "$backup/$name"
done
mv "$stage/package/studio" "$backend/studio"
mv "$stage/package/shared" "$backend/shared"
ln -s "$environment" "$backend/.venv"
sudo -n systemctl restart koji-api.service koji-worker.service
healthy=false
for attempt in {1..30}; do
    if curl --fail --silent --max-time 5 http://127.0.0.1:8000/ready >/dev/null &&
        systemctl is-active --quiet koji-api.service koji-worker.service; then
        healthy=true
        break
    fi
    sleep 2
done
[[ "$healthy" == true ]]
cp "$stage/package/release.json" "$backend/release.json"
trap - ERR
echo "Koji API ready and worker active at $sha"
echo "Rollback backup: $backup"
