#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker info --format '{{.ServerVersion}}'
mkdir -p private artifacts .secrets
docker compose --env-file docker/compose.env build demo gateway
docker compose --env-file docker/compose.env run --rm --no-deps \
  --user "$(id -u):$(id -g)" setup init --upgrade
