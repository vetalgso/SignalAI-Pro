#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
  pwd
)"
project_root="$(
  cd -- "$script_dir/../.."
  pwd
)"

env_file="$project_root/.env.production"
backup_path=""
target_database=""
confirmation=""

usage() {
  echo "Usage:"
  echo "  $0 --backup PATH --target-db NAME \\"
  echo "     --confirm RESTORE:NAME [--env-file PATH]"
  echo
  echo "Restore is allowed only into a new database."
  echo "The primary PostgreSQL database cannot be replaced."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup)
      backup_path="${2:?Missing --backup value}"
      shift 2
      ;;
    --target-db)
      target_database="${2:?Missing --target-db value}"
      shift 2
      ;;
    --confirm)
      confirmation="${2:?Missing --confirm value}"
      shift 2
      ;;
    --env-file)
      env_file="${2:?Missing --env-file value}"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$backup_path" ]; then
  echo "--backup is required." >&2
  exit 2
fi

if [ -z "$target_database" ]; then
  echo "--target-db is required." >&2
  exit 2
fi

if ! [[ "$target_database" =~ ^[A-Za-z][A-Za-z0-9_]{0,62}$ ]]; then
  echo "Unsafe target database name." >&2
  exit 2
fi

expected_confirmation="RESTORE:${target_database}"

if [ "$confirmation" != "$expected_confirmation" ]; then
  echo "Confirmation mismatch." >&2
  echo "Required: $expected_confirmation" >&2
  exit 2
fi

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $env_file" >&2
  exit 1
fi

if [ ! -s "$backup_path" ]; then
  echo "Backup is missing or empty: $backup_path" >&2
  exit 1
fi

backup_dir="$(
  cd -- "$(dirname -- "$backup_path")"
  pwd
)"
backup_name="$(basename -- "$backup_path")"
backup_path="$backup_dir/$backup_name"
checksum_name="${backup_name}.sha256"

if [ ! -f "$backup_dir/$checksum_name" ]; then
  echo "Checksum is missing." >&2
  exit 1
fi

(
  cd -- "$backup_dir"
  sha256sum -c -- "$checksum_name"
)

compose=(
  docker compose
  --env-file "$env_file"
  -f "$project_root/docker-compose.yml"
  -f "$project_root/docker-compose.prod.yml"
)

"${compose[@]}" config --quiet

if ! "${compose[@]}" \
  ps --status running --services \
  | grep -Fxq db; then
  echo "PostgreSQL service is not running." >&2
  exit 1
fi

primary_database="$(
  "${compose[@]}" exec -T db \
    sh -ec 'printf "%s" "$POSTGRES_DB"' \
    | tr -d '\r'
)"

if [ "$target_database" = "$primary_database" ]; then
  echo "Refusing to overwrite primary database." >&2
  exit 1
fi

primary_user="$(
  "${compose[@]}" exec -T db \
    sh -ec 'printf "%s" "$POSTGRES_USER"' \
    | tr -d '\r'
)"

database_exists="$(
  "${compose[@]}" exec -T db \
    psql \
      -U "$primary_user" \
      -d postgres \
      -Atqc "
        SELECT 1
        FROM pg_database
        WHERE datname = '$target_database';
      " \
    | tr -d '\r'
)"

if [ "$database_exists" = "1" ]; then
  echo "Target database already exists." >&2
  exit 1
fi

"${compose[@]}" exec -T db \
  pg_restore --list \
  < "$backup_path" \
  > /dev/null

echo "Creating restore database: $target_database"

"${compose[@]}" exec -T db \
  sh -ec '
    exec createdb \
      -U "$POSTGRES_USER" \
      "$1"
  ' sh "$target_database"

echo "Restoring backup..."

if ! "${compose[@]}" exec -T db \
  sh -ec '
    exec pg_restore \
      -U "$POSTGRES_USER" \
      -d "$1" \
      --no-owner \
      --no-privileges \
      --exit-on-error
  ' sh "$target_database" \
  < "$backup_path"; then
  echo "Restore failed." >&2
  echo "Database was left for inspection:" >&2
  echo "$target_database" >&2
  exit 1
fi

table_count="$(
  "${compose[@]}" exec -T db \
    sh -ec '
      exec psql \
        -U "$POSTGRES_USER" \
        -d "$1" \
        -Atqc "
          SELECT count(*)
          FROM pg_tables
          WHERE schemaname = '\''public'\'';
        "
    ' sh "$target_database" \
    | tr -d '\r'
)"

if [ "$table_count" -le 0 ]; then
  echo "Restored database has no public tables." >&2
  exit 1
fi

echo "Restore completed successfully."
echo "Target database: $target_database"
echo "Public tables:   $table_count"
echo "Primary database was not modified."
