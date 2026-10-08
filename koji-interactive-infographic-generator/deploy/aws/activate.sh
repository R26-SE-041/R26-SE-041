#!/usr/bin/env bash
# Run as koji, with narrowly scoped sudo rights for these two units.
set -euo pipefail
sha="${1:?tested commit required}"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || exit 2
release="/opt/koji/releases/$sha"
test -f "$release/backend/studio/requirements.txt"
python3 -m venv "$release/venv"
"$release/venv/bin/python" -m pip install --disable-pip-version-check -r "$release/backend/studio/requirements.txt"
previous="$(readlink /opt/koji/current || true)"
ln -sfn "$release" /opt/koji/current.next
mv -Tf /opt/koji/current.next /opt/koji/current
sudo systemctl restart koji-api.service koji-worker.service
for attempt in {1..30}; do
    if curl --fail --silent http://127.0.0.1:8000/ready >/dev/null && systemctl is-active --quiet koji-worker.service; then
        echo "Koji API ready and worker active at $sha"
        exit 0
    fi
    sleep 2
done
if [[ -n "$previous" ]]; then
    ln -sfn "$previous" /opt/koji/current.next
    mv -Tf /opt/koji/current.next /opt/koji/current
    sudo systemctl restart koji-api.service koji-worker.service
fi
echo "Deployment failed readiness checks; previous release restored when available" >&2
exit 1
