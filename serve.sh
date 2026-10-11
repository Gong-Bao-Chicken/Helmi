#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f web/data/helmets.json ]]; then
  echo "Missing web/data/helmets.json"
  echo ""
  echo "Fetch data first:"
  echo "  ./update-data.sh --quick    # Virginia Tech only (~5 s)"
  echo "  ./update-data.sh            # VT + CERTIMOOV / Folksam / NSW (~2 min)"
  exit 1
fi

PORT="${PORT:-8080}"
echo "Helmet Compare → http://localhost:${PORT}/"
echo "Press Ctrl+C to stop."
echo ""
exec python3 -m http.server "$PORT" --directory web
