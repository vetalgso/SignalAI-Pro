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

usage() {
  echo "Usage:"
  echo "  $0 --backup PATH [--env-file PATH]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup)
      backup_path="${2:?Missing --backup value}"
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
checksum_path="$backup_dir/$checksum_name"

if [ ! -f "$checksum_path" ]; then
  echo "Checksum is missing: $checksum_path" >&2
  exit 1
fi

(
  cd -- "$backup_dir"
  sha256sum -c -- "$checksum_name"
)

mode="$(stat -c '%a' "$backup_path")"

if [ "$mode" != "600" ]; then
  echo "Unsafe backup permissions: $mode" >&2
  exit 1
fi

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

"${compose[@]}" exec -T db \
  pg_restore --list \
  < "$backup_path" \
  > /dev/null

echo "Backup verification: OK"
echo "Backup: $backup_path"
echo "Size:   $(stat -c '%s' "$backup_path") bytes"
echo "Mode:   $mode"
