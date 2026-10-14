#!/usr/bin/env bash
# Run as the existing EC2 deployment administrator after staging the checked package.
set -Eeuo pipefail
root="${KOJI_DEPLOY_ROOT:-/home/ubuntu/koji}"
stage="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ "$stage" == "$root/deploy-staging/modal-switch-"* ]] || exit 2
exec 9>"$root/deploy.lock"
flock -w 600 9
backend="$root/backend"
control="$root/deploy-control"
test -x "$backend/.venv/bin/python"
test -f "$backend/.env"
test -f "$control/.env"
test -f "$control/deploy_service.py"
test ! -e "$stage/package"
mkdir "$stage/package"
python3 - "$stage/modal-switch.tar.gz" "$stage/package" <<'PY'
import hashlib,json,sys,tarfile
from pathlib import Path
archive,directory=sys.argv[1:]
allowed={'studio/main.py','studio/pipeline.py','studio/modal_accounts.py','studio/modal_remote.py',
         'control/deploy_service.py','control/switch-modal.sh','modal-accounts.json','manifest.json'}
with tarfile.open(archive) as bundle:
    members=bundle.getmembers()
    assert {item.name for item in members} == allowed
    assert len(members)==len(allowed) and all(item.isfile() for item in members)
    bundle.extractall(directory,filter='data')
manifest=json.loads((Path(directory)/'manifest.json').read_text())
assert set(manifest['files']) == allowed-{'manifest.json'}
for name,digest in manifest['files'].items():
    assert hashlib.sha256((Path(directory)/name).read_bytes()).hexdigest()==digest,name
print('Modal routing package checksums verified')
PY
"$backend/.venv/bin/python" -m compileall -q "$stage/package/studio" "$stage/package/control/deploy_service.py"
# An installed control service must not be restarted during an active release.
python3 - "$root/deploy-staging" <<'PY'
import json,sys
from pathlib import Path
for path in Path(sys.argv[1]).glob('*/status.json'):
    assert json.loads(path.read_text()).get('status')!='running','Wait for active release before installing account control'
PY
backup="$(mktemp -d "$root/deploy-backups/modal-switch.XXXXXXXX")"
targets=(studio/main.py studio/pipeline.py studio/modal_accounts.py studio/modal_remote.py modal-accounts.json)
for name in "${targets[@]}"; do
    if [[ -f "$backend/$name" ]]; then
        mkdir -p "$backup/backend/$(dirname "$name")"
        cp -a "$backend/$name" "$backup/backend/$name"
    fi
done
mkdir "$backup/control"
for name in deploy_service.py switch-modal.sh; do
    [[ ! -f "$control/$name" ]] || cp -a "$control/$name" "$backup/control/$name"
done
restore() {
    trap - ERR
    set +e
    for name in "${targets[@]}"; do
        if [[ -f "$backup/backend/$name" ]]; then
            cp -a "$backup/backend/$name" "$backend/$name"
        else
            rm -f -- "$backend/$name"
        fi
    done
    for name in deploy_service.py switch-modal.sh; do
        if [[ -f "$backup/control/$name" ]]; then
            cp -a "$backup/control/$name" "$control/$name"
        else
            rm -f -- "$control/$name"
        fi
    done
    sudo -n systemctl restart koji-api.service koji-deploy.service
    echo "Installation failed; previous source restored from $backup" >&2
    exit 1
}
trap restore ERR
for name in "${targets[@]}"; do
    install -m 644 "$stage/package/$name" "$backend/$name"
done
for name in deploy_service.py switch-modal.sh; do
    install -m 700 "$stage/package/control/$name" "$control/$name"
done
cd "$backend"
"$backend/.venv/bin/python" - <<'PY'
from dotenv import load_dotenv
load_dotenv('.env')
from studio.main import ready
from studio.modal_accounts import accounts,routing_endpoints
assert accounts()
assert routing_endpoints()
ready()
print('Installed API imports, routing configuration and database readiness verified')
PY
# The worker already uses URLs stored with each job. Preserve active worker calls.
sudo -n systemctl restart koji-api.service koji-deploy.service
healthy=false
for attempt in {1..30}; do
    if curl --fail --silent --max-time 5 http://127.0.0.1:8000/ready >/dev/null &&
        systemctl is-active --quiet koji-api.service koji-worker.service koji-deploy.service; then
        healthy=true
        break
    fi
    sleep 2
done
[[ "$healthy" == true ]]
"$backend/.venv/bin/python" - "$control/.env" <<'PY'
import json,sys
from dotenv import dotenv_values
from urllib.request import Request,urlopen
token=dotenv_values(sys.argv[1])['KOJI_DEPLOY_TOKEN']
request=Request('http://127.0.0.1:8766/internal/koji-deploy/modal/status',headers={'Authorization':'Bearer '+token})
with urlopen(request,timeout=15) as response:
    assert 'active_account' in json.load(response)
print('Authenticated EC2 account control verified')
PY
trap - ERR
echo "Modal remote control installed; existing jobs preserved. Backup: $backup"
