#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.yml")
BOOKSTACK_CONTAINER=bookstack-cli-bookstack
ADMIN_EMAIL=admin@example.com
ADMIN_NAME="CLI Admin"
ADMIN_PASSWORD=bookstack-admin-pass
TOKEN_NAME=bookstack-cli-local

up() {
  "${COMPOSE[@]}" up -d
  wait_http
  create_admin
  create_token
}

down() {
  "${COMPOSE[@]}" down "$@"
}

wait_http() {
  for _ in {1..90}; do
    if curl -fsS http://localhost:6875 >/dev/null; then
      return 0
    fi
    sleep 2
  done
  docker logs "$BOOKSTACK_CONTAINER" >&2 || true
  echo "BookStack did not become ready at http://localhost:6875" >&2
  return 1
}

create_admin() {
  docker exec "$BOOKSTACK_CONTAINER" php /app/www/artisan bookstack:create-admin \
    --initial \
    --email="$ADMIN_EMAIL" \
    --name="$ADMIN_NAME" \
    --password="$ADMIN_PASSWORD" >/dev/null || true
}

create_token() {
  local output
  output="$(docker exec \
    -e BOOKSTACK_CLI_ADMIN_EMAIL="$ADMIN_EMAIL" \
    -e BOOKSTACK_CLI_TOKEN_NAME="$TOKEN_NAME" \
    "$BOOKSTACK_CONTAINER" php /app/www/artisan tinker --execute='
      $email = getenv("BOOKSTACK_CLI_ADMIN_EMAIL");
      $name = getenv("BOOKSTACK_CLI_TOKEN_NAME");
      $user = \BookStack\Users\Models\User::query()->where("email", $email)->firstOrFail();
      \BookStack\Api\ApiToken::query()->where("user_id", $user->id)->where("name", $name)->delete();
      $secret = bin2hex(random_bytes(32));
      $token = new \BookStack\Api\ApiToken();
      $token->name = $name;
      $token->token_id = bin2hex(random_bytes(16));
      $token->secret = \Illuminate\Support\Facades\Hash::make($secret);
      $token->expires_at = \BookStack\Api\ApiToken::defaultExpiry();
      $token->user_id = $user->id;
      $token->save();
      echo $token->token_id . ":" . $secret;
    ')"

  {
    echo "BOOKSTACK_URL=http://localhost:6875"
    echo "BOOKSTACK_TOKEN_ID=${output%%:*}"
    echo "BOOKSTACK_TOKEN_SECRET=${output#*:}"
  } > "$ROOT_DIR/.env"
  chmod 600 "$ROOT_DIR/.env"
  echo "Wrote $ROOT_DIR/.env"
}

case "${1:-up}" in
  up) up ;;
  down) shift; down "$@" ;;
  token) create_token ;;
  *) echo "Usage: $0 [up|token|down [docker compose down args...]]" >&2; exit 2 ;;
esac
