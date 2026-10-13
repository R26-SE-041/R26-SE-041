#!/usr/bin/env bash
# Run from an extracted, reviewed component release; no runtime data is replaced.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo'; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 validate_env.py /etc/voicelearn/backend.env /etc/voicelearn/openclaw.env /etc/voicelearn/compose.env
chmod 600 /etc/voicelearn/{backend,openclaw,compose}.env
docker compose --env-file /etc/voicelearn/compose.env build backend openclaw
docker compose --env-file /etc/voicelearn/compose.env run --rm --no-deps openclaw openclaw config validate
docker compose --env-file /etc/voicelearn/compose.env up -d
for attempt in $(seq 1 60); do
  if curl --silent --fail --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
    echo 'Backend health passed; verify HTTPS and OpenClaw MCP before connecting Vercel.'
    exit 0
  fi
  sleep 2
done
echo 'Backend did not become healthy. Inspect docker compose logs; do not connect frontend yet.' >&2
exit 1
