#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
[ -f backend/.env ] || cp backend/.env.example backend/.env
docker compose up -d --build
docker compose ps
