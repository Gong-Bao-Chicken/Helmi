#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f web/public/data/helmets.json ]]; then
  echo "Missing web/public/data/helmets.json. Fetch data first:"
  echo "  uv run helmet-data update --quick    # Virginia Tech only (~5 s)"
  exit 1
fi

[[ -d web/node_modules ]] || npm --prefix web install
exec npm --prefix web run dev -- "$@"
