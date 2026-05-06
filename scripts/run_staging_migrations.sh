#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env.staging}"
COMPOSE_FILE="${STAGING_COMPOSE_FILE:-docker-compose.staging.yml}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' is not available."
}

get_env_value() {
  local key="$1"
  local value
  value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf "%s" "$value"
}

require_command docker

[[ -f "$ENV_FILE" ]] || fail "Env file '$ENV_FILE' not found."
[[ -f "$COMPOSE_FILE" ]] || fail "Compose file '$COMPOSE_FILE' not found."

app_env="$(get_env_value APP_ENV)"
[[ "$app_env" != "production" ]] || fail "Refusing to run staging migrations with APP_ENV=production."

export STAGING_ENV_FILE="$ENV_FILE"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

echo "Preparing API migration image..."
"${compose[@]}" build api

echo "Starting local Postgres/Redis if this staging Compose stack owns them..."
"${compose[@]}" up -d postgres redis

echo "Alembic heads before upgrade:"
"${compose[@]}" run --rm api alembic heads

echo "Alembic current before upgrade:"
"${compose[@]}" run --rm api alembic current || true

echo "Applying Alembic migrations to staging database..."
"${compose[@]}" run --rm api alembic upgrade head

echo "Alembic current after upgrade:"
"${compose[@]}" run --rm api alembic current

echo "Staging migrations complete."
