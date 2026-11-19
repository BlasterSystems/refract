#!/usr/bin/env python3
"""Synchronize refract.__version__ across version-metadata files.

Updates ``generator_version`` in ``.refract/config.json`` and rewrites the
documented version floors in ``DOC_FLOOR_FILES``. ``--check`` reports every
drift without changing files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from refract import __version__  # noqa: E402

# Documented version floors (tasks/plan-entry-path-consolidation.md 1.4): the
# only contexts in which docs compare ``refract --version`` against a
# MAJOR.MINOR.PATCH release. Only the literal inside one of these contexts is
# rewritten; any other version literal (tags, install specs, changelog
# entries) stays untouched.
DOC_FLOOR_FILES: tuple[str, ...] = (
    "README.md",
    "docs/PROMPTS.md",
    "docs/PROJECT_SUMMARY.md",
)

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


def _floor_with_version(match: re.Match[str], version: str) -> str:
    """Return the matched floor context with its literal set to ``version``.

    The context words are rebuilt byte-identically; only the literal changes.
    """
    literal = _floor_literal(match)
    if literal == version:
        return match.group(0)
    group = next(group for group in _GROUPS if match.group(group) is not None)
    start = match.start(group) - match.start()
    return match.group(0)[:start] + version + match.group(0)[start + len(literal):]


def _floor_drifts(text: str, version: str) -> list[tuple[int, str, str]]:
    """Return (line_number, current_context, expected_context) for every
    documented floor context in ``text`` that does not hold ``version``.

    Line numbers are 1-based. Text without floor contexts yields no drifts.
    """
    drifts: list[tuple[int, str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _FLOOR_PATTERN.finditer(line):
            expected = _floor_with_version(match, version)
            if expected != match.group(0):
                drifts.append((number, match.group(0), expected))
    return drifts


def _rewrite_floors(text: str, version: str) -> tuple[str, int]:
    """Rewrite every documented floor context in ``text`` to ``version``.

    Returns the new text and the number of literals changed. The text is
    otherwise byte-identical, so unrelated version literals on the same line
    survive.
    """
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        rewritten = _floor_with_version(match, version)
        if rewritten != match.group(0):
            changed += 1
        return rewritten

    return _FLOOR_PATTERN.sub(replace, text), changed


def _replace_via_temporary(path: Path, contents: str, original: os.stat_result) -> None:
    """Atomically replace ``path`` with ``contents``.

    Temp file in the destination directory, fsync, mode copied from the
    original stat, destination rechecked as a regular file immediately before
    the rename, temporary removed on any failure.
    """
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(stat.S_IMODE(original.st_mode))

        # Recheck immediately before replacement. If a concurrent actor swaps the
        # destination, abort instead of treating the new path as repository state.
        _regular_file_stat(path)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _regular_file_stat(path: Path) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{path} does not exist") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{path} must be a regular file, not a symlink or other file type")
    return metadata


def synchronize(root: Path, version: str, *, check: bool) -> int:
    metadata_dir = root / ".refract"
    try:
        metadata_stat = metadata_dir.lstat()
    except FileNotFoundError:
        print(f"{metadata_dir} does not exist", file=sys.stderr)
        return 1
    if not stat.S_ISDIR(metadata_stat.st_mode):
        print(f"{metadata_dir} must be a real directory", file=sys.stderr)
        return 1

    path = metadata_dir / "config.json"
    try:
        original = _regular_file_stat(path)
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1

    current = data.get("generator_version")
    display_path = path.relative_to(root)

    # Documented version floors: read each file once. A file without any floor
    # context is simply in sync; only drifted literals are rewritten.
    floors: list[tuple[Path, os.stat_result, str]] = []
    for name in DOC_FLOOR_FILES:
        doc_path = root / name
        try:
            doc_stat = _regular_file_stat(doc_path)
            floors.append((doc_path, doc_stat, doc_path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            # A tree without this documented file has no floors to synchronize.
            continue
        except ValueError:
            # Not a regular file: nothing is rewritten there, and no symlink is followed.
            continue
        except OSError as exc:
            print(f"cannot read {doc_path}: {exc}", file=sys.stderr)
            return 1

    failures: list[str] = []
    if current != version:
        failures.append(f"{display_path} has {current!r}; expected {version!r}")
    for doc_path, _, text in floors:
        for number, current_context, expected_context in _floor_drifts(text, version):
            failures.append(
                f"{doc_path.relative_to(root)}:{number}: {current_context!r};"
                f" expected {expected_context!r}"
            )

    if check:
        for failure in failures:
            print(failure, file=sys.stderr)
        if failures:
            return 1
        print(f"{display_path} is synchronized at {version}")
        return 0

    updated_any = False
    if current != version:
        data["generator_version"] = version
        try:
            _replace_via_temporary(path, json.dumps(data, indent=2) + "\n", original)
        except (ValueError, OSError) as exc:
            print(f"cannot update {path}: {exc}", file=sys.stderr)
            return 1
        print(f"updated {display_path} to {version}")
        updated_any = True

    for doc_path, doc_stat, text in floors:
        rewritten, changed = _rewrite_floors(text, version)
        if changed == 0:
            continue
        try:
            _replace_via_temporary(doc_path, rewritten, doc_stat)
        except (ValueError, OSError) as exc:
            print(f"cannot update {doc_path}: {exc}", file=sys.stderr)
            return 1
        print(f"updated {doc_path.relative_to(root)} to {version}")
        updated_any = True

    if not updated_any:
        print(f"{display_path} is synchronized at {version}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize repository-derived version metadata with refract.__version__."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without changing files",
    )
    args = parser.parse_args()
    return synchronize(ROOT, __version__, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
