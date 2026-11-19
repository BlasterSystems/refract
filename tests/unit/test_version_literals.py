"""Contract: documented version floors equal refract.__version__.

scripts/sync-version.py rewrites the version-floor contexts in README.md,
docs/PROMPTS.md and docs/PROJECT_SUMMARY.md. This test is the independent
witness that the checked-in text matches the release version: every literal
inside a documented floor context must equal refract.__version__. A failure
means the docs hold a stale floor; resynchronize by running
``PYTHONPATH=src python3 scripts/sync-version.py``.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from refract import __version__  # noqa: E402

DOC_FILES = ("README.md", "docs/PROMPTS.md", "docs/PROJECT_SUMMARY.md")

# Deliberately mirrors the floor contexts of scripts/sync-version.py instead
# of importing them: this test must stay an independent witness of the docs,
# not a re-run of the script's own logic.
_FLOOR_PATTERN = re.compile(
    r"(?:reports (?:(?:a version below|less than) (?P<below>\d+\.\d+\.\d+)"
    r"|(?P<later>\d+\.\d+\.\d+) or later)"
    r"|Current release:\*{0,2} (?P<release>\d+\.\d+\.\d+))"
)

_GROUPS = ("below", "later", "release")


def _floor_literal(match: re.Match[str]) -> str:
    """Return the version literal captured inside a floor context."""
    for group in _GROUPS:
        if match.group(group) is not None:
            return match.group(group)
    raise AssertionError("unreachable: every pattern alternative captures one group")


class DocumentedVersionFloors(unittest.TestCase):
    """Every documented floor context must hold refract.__version__."""

    def test_documented_floors_match_release_version(self) -> None:
        """Assert every floor-context literal equals the release version.

        Absence of a floor context is not a failure: a document that never
        compares ``refract --version`` against a release has nothing to
        synchronize. All drift is aggregated into one diff-style report so a
        single run names every stale file:line.
        """
        drifts: list[str] = []
        for name in DOC_FILES:
            path = ROOT / name
            display = path.relative_to(ROOT)
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for match in _FLOOR_PATTERN.finditer(line):
                    literal = _floor_literal(match)
                    if literal == __version__:
                        continue
                    group = next(group for group in _GROUPS if match.group(group) is not None)
                    start = match.start(group) - match.start()
                    expected = match.group(0)[:start] + __version__ + match.group(0)[start + len(literal):]
                    drifts.append(f"  {display}:{number}\n-   {match.group(0)}\n+   {expected}")
        if drifts:
            self.fail(
                f"documented version floors drifted from refract.__version__ {__version__}\n"
                + "\n".join(drifts)
                + "\nrun: PYTHONPATH=src python3 scripts/sync-version.py"
            )


if __name__ == "__main__":
    unittest.main()
