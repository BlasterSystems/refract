"""Run git against an untrusted target repository without executing its config.

A repository's own `.git/config` can name programs that git executes
(`core.fsmonitor`, `gpg.program` when signatures are shown, and others).
refract only needs read-only plumbing output, so every invocation disables
those helpers, ignores system config, and never walks above the target.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_SAFE_CONFIG = (
    "-c", "core.fsmonitor=false",
    "-c", "log.showSignature=false",
    "-c", "core.hooksPath=/dev/null",
)


def run_git(root: Path, *args: str, timeout: float = 10) -> subprocess.CompletedProcess[str] | None:
    """Run a read-only git command in `root`'s own repository, or return None."""
    root = root.expanduser().absolute()
    if not (root / ".git").exists():
        return None
    environment = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(root.parent),
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", *_SAFE_CONFIG, "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
