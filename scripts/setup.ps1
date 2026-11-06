$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait for the engine, then retry.' }
New-Item -ItemType Directory -Force private, artifacts, .secrets | Out-Null
docker compose --env-file docker/compose.env build demo gateway
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose --env-file docker/compose.env run --rm --no-deps -T setup init
exit $LASTEXITCODE
