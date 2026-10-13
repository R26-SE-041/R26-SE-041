#!/usr/bin/env bash
# Install next to the release receiver; all routing stays outside release archives.
set -Eeuo pipefail
root="${KOJI_DEPLOY_ROOT:-/home/ubuntu/koji}"
export KOJI_MODAL_ACCOUNTS_FILE="${KOJI_MODAL_ACCOUNTS_FILE:-$root/backend/modal-accounts.json}"
export KOJI_MODAL_STATE_FILE="${KOJI_MODAL_STATE_FILE:-$root/backend/modal-active.json}"
cd "$root/backend"
action="${1:?Usage: switch-modal.sh ACCOUNT | list | status | check ACCOUNT | rollback}"
shift
case "$action" in
    list|status|check|switch|rollback) ;;
    *) set -- "$action" "$@"; action=switch ;;
esac
exec "$root/backend/.venv/bin/python" -m studio.modal_accounts "$action" "$@"
