#!/usr/bin/env bash
# Thin wrapper: refresh helmet data via the uv-managed `helmet-data` CLI.
set -euo pipefail
cd "$(dirname "$0")"
exec uv run helmet-data update "$@"
