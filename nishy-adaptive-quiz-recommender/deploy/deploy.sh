#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
for config in .env backend.env; do
    if [[ ! -f "$config" ]]; then
        printf 'Missing %s. Copy its example and fill in your deployment settings.\n' "$config" >&2
        exit 1
    fi
done
# Validate without printing resolved credentials.
docker compose config --quiet
docker compose build api
# Migration failure stops the deployment before the running API is replaced.
docker compose run --rm --no-deps api python scripts/migrate.py
docker compose up -d --wait --wait-timeout 240
printf 'Deployment is running. Check your HTTPS API /ready endpoint.\n'
