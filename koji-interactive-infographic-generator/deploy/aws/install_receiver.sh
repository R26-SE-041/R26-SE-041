#!/usr/bin/env bash
# Run on the existing Ubuntu EC2 host after copying this directory there.
# Supply the same encrypted GitHub production token on stdin, never as an argument.
set -Eeuo pipefail
root=/home/ubuntu/koji
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
control="$root/deploy-control"
test -d "$root/backend/studio"
test -f "$root/backend/.env"
IFS= read -r token
[[ "$token" =~ ^[a-f0-9]{64}$ ]] || { echo 'Expected a 64-character random deployment token' >&2; exit 2; }
umask 077
mkdir -p "$control"
for name in deploy_service.py activate.sh; do
    install -m 700 "$source_dir/$name" "$control/$name"
done
printf 'KOJI_DEPLOY_TOKEN=%s\n' "$token" > "$control/.env"
unset token
sudo -n install -m 644 "$source_dir/koji-deploy.service" /etc/systemd/system/koji-deploy.service
python3 - "$control/Caddyfile.new" <<'PY'
from pathlib import Path
import sys
current = Path('/etc/caddy/Caddyfile').read_text()
assert 'koji-studio-api.duckdns.org' in current, 'Inspect the existing Caddy site before installation'
if '/internal/koji-deploy' not in current:
    target = 'reverse_proxy 127.0.0.1:8000'
    assert current.count(target) == 1, 'Inspect the existing proxy routes before installation'
    current = current.replace(target, '''handle /internal/koji-deploy* {
        request_body {
            max_size 16MB
        }
        reverse_proxy 127.0.0.1:8766
    }
    handle {
        reverse_proxy 127.0.0.1:8000
    }''')
Path(sys.argv[1]).write_text(current)
PY
sudo -n caddy validate --config "$control/Caddyfile.new" --adapter caddyfile
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now koji-deploy.service
sudo -n systemctl restart koji-deploy.service
test "$(curl --silent --max-time 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8766/internal/koji-deploy/invalid)" == 401
backup="$control/Caddyfile.$(date -u +%Y%m%dT%H%M%SZ).backup"
sudo -n cp -a /etc/caddy/Caddyfile "$backup"
sudo -n install -m 644 "$control/Caddyfile.new" /etc/caddy/Caddyfile
if ! sudo -n systemctl reload caddy; then
    sudo -n cp -a "$backup" /etc/caddy/Caddyfile
    sudo -n systemctl reload caddy
    exit 1
fi
curl --fail --silent --max-time 10 http://127.0.0.1:8000/ready
echo
echo 'Release receiver installed; existing API remains ready'
