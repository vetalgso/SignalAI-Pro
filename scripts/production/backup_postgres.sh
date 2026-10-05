#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

script_dir="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
  pwd
)"
project_root="$(
  cd -- "$script_dir/../.."
  pwd
)"

env_file="$project_root/.env.production"
output_dir="$project_root/backups/postgres"

usage() {
  echo "Usage:"
  echo "  $0 [--env-file PATH] [--output-dir PATH]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --env-file)
      env_file="${2:?Missing --env-file value}"
      shift 2
      ;;
    --output-dir)
      output_dir="${2:?Missing --output-dir value}"
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

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $env_file" >&2
  exit 1
fi

if [ -z "$output_dir" ] || [ "$output_dir" = "/" ]; then
  echo "Unsafe backup directory: $output_dir" >&2
  exit 1
fi

mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"

output_dir="$(
  cd -- "$output_dir"
  pwd
)"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="signalai-postgres-${timestamp}.dump"
final_path="$output_dir/$filename"
checksum_path="${final_path}.sha256"

if [ -e "$final_path" ] || [ -e "$checksum_path" ]; then
  echo "Backup already exists: $final_path" >&2
  exit 1
fi

temporary_path="$(
  mktemp "$output_dir/.signalai-postgres.XXXXXX"
)"

cleanup() {
  rm -f -- "$temporary_path"
}

trap cleanup EXIT INT TERM

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

echo "Creating PostgreSQL backup..."

"${compose[@]}" exec -T db \
  sh -ec '
    exec pg_dump \
      -U "$POSTGRES_USER" \
      -d "$POSTGRES_DB" \
      --format=custom \
      --compress=6 \
      --no-owner \
      --no-privileges \
      --lock-wait-timeout=30s
  ' > "$temporary_path"

if [ ! -s "$temporary_path" ]; then
  echo "PostgreSQL backup is empty." >&2
  exit 1
fi

"${compose[@]}" exec -T db \
  pg_restore --list \
  < "$temporary_path" \
  > /dev/null

chmod 600 -- "$temporary_path"
mv -- "$temporary_path" "$final_path"

(
  cd -- "$output_dir"
  sha256sum -- "$filename" \
    > "${filename}.sha256.tmp"
  chmod 600 -- "${filename}.sha256.tmp"
  mv -- \
    "${filename}.sha256.tmp" \
    "${filename}.sha256"
)

trap - EXIT INT TERM

echo "Backup created successfully."
echo "Backup:   $final_path"
echo "Checksum: $checksum_path"
echo "Size:     $(stat -c '%s' "$final_path") bytes"
