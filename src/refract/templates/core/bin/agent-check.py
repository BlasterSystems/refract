#!/usr/bin/env python3
"""Deterministic end-of-turn check shared by every agent CLI hook.

Runs the project validator and reports the result in the hook protocol of
the calling CLI. It never invokes an LLM, never edits files, and never
touches anything outside this repository.

  --format json   Claude Code / Codex Stop hooks: reads the hook payload on
                  stdin and prints a JSON decision on stdout.
  --format plain  OpenCode plugin / omp hook: prints a human summary.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / ".refract/bin/validate"


def run_validator() -> list[str]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode == 0:
        return []
    lines = [line[2:] for line in result.stdout.splitlines() if line.startswith("- ")]
    return lines or [result.stdout.strip() or result.stderr.strip() or "validator failed"]


def read_payload() -> dict:
    if sys.stdin.isatty():
        return {}
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def stop_decision(errors: list[str], stop_hook_active: bool) -> dict:
    """Return the JSON hook decision for Claude Code / Codex Stop hooks.

    `{}` lets the agent stop normally. `{"decision": "block", "reason": ...}`
    makes the agent continue with `reason` as its next instruction.
    `stop_hook_active` is true when this turn was already continued by a
    Stop hook, so blocking again risks an endless fix loop.
    """
    # Policy: block once so the agent fixes validation failures before
    # finishing; on an already-continued turn only report, so a failure the
    # agent cannot fix never becomes an endless loop.
    if not errors:
        return {}
    summary = "refract validation failed:\n" + "\n".join(f"- {e}" for e in errors)
    if stop_hook_active:
        return {"systemMessage": summary}
    return {
        "decision": "block",
        "reason": summary + "\nFix these issues (run .refract/bin/validate) before finishing.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "plain"), default="plain")
    args = parser.parse_args()
    payload = read_payload() if args.format == "json" else {}
    errors = run_validator()
    if args.format == "json":
        print(json.dumps(stop_decision(errors, bool(payload.get("stop_hook_active")))))
        return 0
    if errors:
        print("refract validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("refract validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
