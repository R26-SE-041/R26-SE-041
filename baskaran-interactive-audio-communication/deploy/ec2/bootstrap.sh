#!/usr/bin/env bash
# Ubuntu 24.04 LTS x86_64. Run once with sudo; never formats or deletes a disk.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo'; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo 'Ubuntu 24.04 required'; exit 1; }
apt-get update
apt-get install -y docker.io docker-compose-v2 python3 python3-venv ca-certificates curl git
systemctl enable --now docker
install -d -m 700 /etc/voicelearn
install -d /opt/voicelearn
if [[ ! -x /opt/voicelearn/tools/bin/python ]]; then
  python3 -m venv /opt/voicelearn/tools
  /opt/voicelearn/tools/bin/pip install 'httpx==0.27.2'
fi
install -d /srv/voicelearn/releases /srv/voicelearn/data /srv/voicelearn/caddy/data /srv/voicelearn/caddy/config
# The free-plan t3.small has 2 GiB RAM. Swap helps installation bursts; it is
# not a substitute for measuring the running stack's memory and responsiveness.
if [[ ! -e /srv/voicelearn/swapfile ]]; then
  fallocate -l 4G /srv/voicelearn/swapfile
  chmod 600 /srv/voicelearn/swapfile
  mkswap /srv/voicelearn/swapfile
fi
if [[ "$(swapon --show=NAME --noheadings)" != *'/srv/voicelearn/swapfile'* ]]; then
  swapon /srv/voicelearn/swapfile
fi
if ! awk '$1=="/srv/voicelearn/swapfile" {found=1} END {exit !found}' /etc/fstab; then
  printf '\n/srv/voicelearn/swapfile none swap sw 0 0\n' >> /etc/fstab
fi
for folder in chroma documents history actions; do
  install -d -o 1001 -g 1001 -m 700 "/srv/voicelearn/data/$folder"
done
install -d -o 1000 -g 1000 -m 700 /srv/voicelearn/openclaw /srv/voicelearn/openclaw/workspace
echo 'Prepared persistent paths. Configure /etc/voicelearn secrets and DNS before deployment.'
