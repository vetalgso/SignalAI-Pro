#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
SILENCE_AUTHOR="${SILENCE_AUTHOR:-SignalAI operator}"

amtool_cmd() {
  docker compose exec -T alertmanager \
    amtool "--alertmanager.url=${ALERTMANAGER_URL}" "$@"
}

usage() {
  cat <<'EOF'
Usage:
  silence.sh add <duration> <comment> <matcher> [matcher...]
  silence.sh list [matcher...]
  silence.sh ids [matcher...]
  silence.sh expire <silence-id>

Examples:
  silence.sh add 30m 'Scheduler maintenance' \
    'alertname=~SignalAIScheduler.*'

  silence.sh list component=scheduler
  silence.sh expire <silence-id>
EOF
}

command="${1:-}"

case "$command" in
  add)
    if [[ "$#" -lt 4 ]]; then
      usage
      exit 2
    fi

    duration="$2"
    comment="$3"
    shift 3

    amtool_cmd silence add \
      "--duration=${duration}" \
      "--author=${SILENCE_AUTHOR}" \
      "--comment=${comment}" \
      "$@"
    ;;

  list)
    shift
    amtool_cmd silence query "$@"
    ;;

  ids)
    shift
    amtool_cmd silence query -q "$@"
    ;;

  expire)
    if [[ "$#" -ne 2 ]]; then
      usage
      exit 2
    fi

    amtool_cmd silence expire "$2"
    ;;

  *)
    usage
    exit 2
    ;;
esac
