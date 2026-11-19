#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
# Only refract's own sources go on the import path. An inherited PYTHONPATH with an empty
# or relative entry would put the current directory back on it.
export PYTHONPATH="$ROOT/src"
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  echo "refract needs Python 3.11 or later as python3" >&2
  exit 1
fi
# -P keeps the current directory off the import path: the wrapper is run from inside
# target repositories, whose files must never shadow the standard library or refract.
exec python3 -P -m refract "$@"
