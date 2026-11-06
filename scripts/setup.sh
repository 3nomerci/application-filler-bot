#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker info --format '{{.ServerVersion}}'
if [ "$(id -u)" = 0 ]; then
  echo 'Run setup as your normal user with access to Docker, not as root.' >&2
  exit 1
fi
umask 077
mkdir -p private artifacts .secrets
# Bind mounts on Linux preserve ownership. The gateway must also be able to read
# a mode-600 secret owned by this user. Keep this machine-specific override local.
if [ ! -e compose.override.yaml ] && [ ! -e compose.override.yml ]; then
  for service in agent demo setup gateway; do
    if [ "$service" = agent ]; then printf 'services:\n'; fi
    printf '  %s:\n    user: "%s:%s"\n' "$service" "$(id -u)" "$(id -g)"
  done > compose.override.yaml
fi
docker compose --env-file docker/compose.env build demo gateway
docker compose --env-file docker/compose.env run --rm --no-deps -T setup init
