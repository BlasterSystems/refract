#!/usr/bin/env bash
# Runs every CI check locally, in the same order CI runs them. CI calls this script
# (see .github/workflows/test.yml), so local and CI results cannot drift. The strict
# docs check diffs against CHECK_BASE (default origin/main).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src

echo "== sync-version --check"
python3 scripts/sync-version.py --check

echo "== unit, integration, and contract tests"
python3 -m unittest discover -s tests

echo "== repository validation"
python3 -m refract validate --target .
.refract/bin/validate

echo "== strict docs check against ${CHECK_BASE:-origin/main}"
.refract/bin/docs-check --strict --base "${CHECK_BASE:-origin/main}"

echo "== wheel build and installed-CLI smoke test"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
# The smoke must exercise the wheel, not the checkout: drop PYTHONPATH so the
# repository's src/ cannot shadow or satisfy the installed package.
unset PYTHONPATH
echo "python3: $(python3 -V 2>&1)"
if python3 -m pip --version >/dev/null 2>&1; then
    python3 -m pip wheel --no-deps -w "$scratch/wheel" .
    python3 -m venv "$scratch/venv"
    "$scratch/venv/bin/python" -m pip install --no-deps "$scratch"/wheel/*.whl
else
    uv build --wheel --out-dir "$scratch/wheel" .
    uv venv "$scratch/venv"
    uv pip install --python "$scratch/venv/bin/python" "$scratch"/wheel/*.whl
fi
echo "venv bin: $(ls "$scratch/venv/bin")"
"$scratch/venv/bin/refract" --version
"$scratch/venv/bin/refract" init --platform all --dry-run --yes --target "$scratch/smoke"

echo "check.sh: all gates passed."
