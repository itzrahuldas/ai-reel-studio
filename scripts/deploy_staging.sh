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

require_command git
require_command docker
require_command curl

[[ -f "$ENV_FILE" ]] || fail "Env file '$ENV_FILE' not found. Copy .env.staging.example and fill staging values."
[[ -f "$COMPOSE_FILE" ]] || fail "Compose file '$COMPOSE_FILE' not found."

app_env="$(get_env_value APP_ENV)"
[[ "$app_env" != "production" ]] || fail "Refusing to deploy with APP_ENV=production."

export STAGING_ENV_FILE="$ENV_FILE"

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

echo "Staging deployment setup"
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short HEAD)"
echo "Compose file: $COMPOSE_FILE"
echo "Env file: $ENV_FILE"

echo "Building staging images..."
"${compose[@]}" build

echo "Starting staging Postgres and Redis for self-hosted Compose staging..."
"${compose[@]}" up -d postgres redis

echo "Running Alembic migrations..."
"${compose[@]}" run --rm api alembic heads
"${compose[@]}" run --rm api alembic upgrade head
"${compose[@]}" run --rm api alembic current

echo "Starting API, web, workers, and Celery Beat..."
"${compose[@]}" up -d api web worker-generation worker-rendering worker-publishing celery-beat

echo "Service status:"
"${compose[@]}" ps

api_base="$(get_env_value API_PUBLIC_BASE_URL)"
if [[ -z "$api_base" ]]; then
  api_port="$(get_env_value API_PORT)"
  api_base="http://localhost:${api_port:-8000}"
fi

echo "Checking API health endpoints at $api_base ..."
for path in /health /api/v1/health/readiness /api/v1/health/config; do
  curl --fail --silent --show-error --max-time 15 "$api_base$path" >/dev/null
  echo "OK $path"
done

frontend_base="$(get_env_value FRONTEND_URL)"
echo "Staging deploy sequence complete."
echo
echo "Run smoke tests from a trusted machine:"
echo "SMOKE_API_BASE_URL=$api_base \\"
if [[ -n "$frontend_base" ]]; then
  echo "SMOKE_FRONTEND_BASE_URL=$frontend_base \\"
else
  echo "SMOKE_FRONTEND_BASE_URL=<staging-frontend-url> \\"
fi
echo "SMOKE_TEST_EMAIL=<staging-smoke-email> \\"
echo "SMOKE_TEST_PASSWORD=<staging-smoke-password> \\"
echo "SMOKE_CREATE_REEL=true \\"
echo "SMOKE_TEST_STRIPE_MOCK=true \\"
echo "SMOKE_TEST_INSTAGRAM_MOCK=true \\"
echo "python scripts/staging_smoke_test.py"
