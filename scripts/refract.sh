#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
# -P keeps the current directory off the import path: the wrapper is run from inside
# target repositories, whose files must never shadow the standard library or refract.
exec python3 -P -m refract "$@"
