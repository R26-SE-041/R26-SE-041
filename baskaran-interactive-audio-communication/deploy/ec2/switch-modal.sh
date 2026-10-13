#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run with sudo'; exit 1; }
case "${1:-}" in
  visakanbaskaran|krishnavaranan1|krishnavaranan|varananrp) profile=$1 ;;
  *) echo 'Supply one configured Modal workspace name'; exit 1 ;;
esac
app=$(readlink -f /srv/voicelearn/current)
[[ $app == /srv/voicelearn/releases/* ]] || { echo 'No valid current release'; exit 1; }
python=/opt/voicelearn/tools/bin/python
script="$app/backend/scripts/modal_workspaces.py"
state=/srv/voicelearn/modal-verification
install -d -m 700 "$state"
# Verify live endpoints before changing any production setting.
"$python" "$script" verify "$profile" --state-dir "$state"
backup=/etc/voicelearn/backend.env.before-switch
cp /etc/voicelearn/backend.env "$backup"
"$python" "$script" switch "$profile" --env-file /etc/voicelearn/backend.env --state-dir "$state"
cd "$app/deploy/ec2"
docker compose --env-file /etc/voicelearn/compose.env up -d --force-recreate backend
for attempt in $(seq 1 30); do
  if curl -sf --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
    echo "Selected $profile; frontend address and saved data retained."
    exit 0
  fi
  sleep 2
done
cp "$backup" /etc/voicelearn/backend.env
docker compose --env-file /etc/voicelearn/compose.env up -d --force-recreate backend
echo 'New backend failed health; previous environment restored.' >&2
exit 1
