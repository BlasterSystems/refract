"""Contract: every command documented in the top-level docs must parse.

Work package 1.2 of tasks/plan-entry-path-consolidation.md. The command
surface documented in README.md, AGENTS.md, and docs/*.md (top level only;
docs/adr/ is a historical record, not a command surface) is an API: this
test reads those files, extracts every documented invocation of ``refract
...``, ``scripts/refract.sh ...``, ``uvx --from ... refract ...``, and
``PYTHONPATH=src python3 -m refract ...``, substitutes documentation
placeholders, and parses each one with the real argument parser built by
``refract.cli.build_parser``. A documented command the parser rejects is
docs/CLI drift and fails here with its file and line.

Extraction rules:

- Backslash-continued lines are joined before scanning (docs/PROMPTS.md,
  docs/AGENT_GUIDED.md, and docs/RELEASING.md wrap long commands).
- An invocation needs a leading launcher token — ``refract``,
  ``scripts/refract.sh``, ``uvx --from <spec> refract``, or ``python3 -m
  refract`` — followed by a known subcommand (init, retrofit, inspect,
  validate) or ``--version``. Bare prose mentions (``refract``,
  ``refract ...``) are not invocations and are skipped.
- Commands are read from inline backtick spans anywhere and from bare line
  positions inside fenced blocks (```mermaid labels are diagrams, not
  invocations). Redirections (``> <PLAN_FILE>``), pipes, trailing comments,
  and ``PYTHONPATH=src``-style env prefixes are stripped.
- Placeholders are substituted before parsing (``PLACEHOLDERS`` below).
- Agent-guided invocations that would not reach the interactive-terminal
  rule are additionally checked with ``refract.cli._validate_agent_arguments``.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import unittest
from dataclasses import dataclass
from pathlib import Path

from refract.cli import _validate_agent_arguments, build_parser

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Subcommands the documented surface uses. Anything else after a launcher
#: token (``refract ...``, ``uvx --from ... refract``) is prose, not an
#: invocation.
KNOWN_SUBCOMMANDS = frozenset({"init", "retrofit", "inspect", "validate"})

#: Documentation placeholders mapped to parseable values. ``PLAN_SHA256`` is
#: docs/AGENT_GUIDED.md's bare spelling of the plan identifier.
PLACEHOLDERS: dict[str, str] = {
    "<PLAN_FILE>": "/tmp/refract-plan.json",
    "<PLAN_ID>": "a" * 64,
    "<INTENT_FILE>": "/tmp/refract-intent.json",
    "<HANDOFF_FILE>": "/tmp/refract-handoff.json",
    "<clone>": "/tmp/refract-clone",
    "<our platforms>": "claude",
    "$preview_target": "/tmp/refract-preview",
    "${RUNNER_TEMP}": "/tmp/refract-runner-temp",
    "PLAN_SHA256": "a" * 64,
}

#: Per-file floors for the extraction sanity guard; see the floor test.
PER_FILE_FLOORS: dict[str, int] = {
    "README.md": 5,
    "docs/PROMPTS.md": 8,
    "docs/AGENT_GUIDED.md": 2,
}

#: The documented inventory must stay above this size for the parse loop to
#: mean anything; a silent extractor must fail the floor test first.
MINIMUM_TOTAL_COMMANDS = 20

_LAUNCHER = re.compile(
    r"(?<![\w./\-\"'])(?:refract\b|scripts/refract\.sh\b|uvx\s+--from\b|python3\s+-m\s+refract\b)"
)
_BACKTICK_SPAN = re.compile(r"`([^`]*)`")
_REDIRECT = re.compile(r"\d*[<>]&?\d*")
_PIPE_OPERATORS = frozenset({"|", "||", "|&", "&", "&&", ";", ";;", "&>", "&>>"})
_ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=\S*")
_SPEC_TAIL = re.compile(r"(?:uvx\s+--from\s+\S+|python3\s+-m)\s$")


@dataclass(frozen=True)
class DocumentedCommand:
    """A documented invocation: where it appears and the argv to parse."""

    location: str
    display: str
    argv: tuple[str, ...]


def _logical_lines(text: str) -> list[tuple[int, str, str | None]]:
    """Join backslash continuations; yield (first line, text, fence type).

    Fence type is the opening info string while inside a fenced block and
    None in prose; fence delimiter lines themselves yield nothing.
    """
    logical: list[tuple[int, str, str | None]] = []
    physical = text.splitlines()
    fence: str | None = None
    index = 0
    while index < len(physical):
        stripped = physical[index].lstrip()
        if stripped.startswith("```"):
            info = stripped[3:].strip()
            if fence is None:
                fence = info.split()[0] if info else ""
            else:
                fence = None
            index += 1
            continue
        buffer = physical[index].rstrip()
        start = index + 1
        while buffer.endswith("\\") and index + 1 < len(physical):
            index += 1
            buffer = buffer[:-1].rstrip() + " " + physical[index].strip()
        logical.append((start, buffer, fence))
        index += 1
    return logical


def _command_tokens(source: str) -> list[str]:
    """Tokenize a command, cutting at pipes, redirections, and comments."""
    tokens = shlex.split(source, comments=True)
    for position, token in enumerate(tokens):
        if token in _PIPE_OPERATORS or token.startswith(">") or token.startswith("<"):
            return tokens[:position]
        if _REDIRECT.fullmatch(token) and not token.isdigit():
            return tokens[:position]
    return tokens


def _refract_argv(tokens: list[str]) -> tuple[str, ...] | None:
    """Slice off the documented launcher; None when it is another form."""
    if not tokens:
        return None
    head = tokens[0]
    if head in {"refract", "scripts/refract.sh"}:
        return tuple(tokens[1:])
    if head == "python3" and tokens[1:3] == ["-m", "refract"]:
        return tuple(tokens[3:])
    if head == "uvx" and len(tokens) >= 4 and tokens[1] == "--from" and tokens[3] == "refract":
        return tuple(tokens[4:])
    return None


def _is_spec_tail(text: str, position: int) -> bool:
    """True when position is the ``refract`` of ``uvx --from S refract`` or
    ``python3 -m refract``; the launcher start already yielded that line."""
    prefix = text[max(0, position - 64) : position]
    return bool(_SPEC_TAIL.search(prefix))


def _scan_file(relative: str) -> list[DocumentedCommand]:
    """Extract documented Refract invocations from one markdown file."""
    path = REPO_ROOT / relative
    commands: list[DocumentedCommand] = []
    for line_number, text, fence in _logical_lines(path.read_text(encoding="utf-8")):
        for placeholder, value in PLACEHOLDERS.items():
            text = text.replace(placeholder, value)
        spans = list(_BACKTICK_SPAN.finditer(text))
        candidates: list[str] = [span.group(1) for span in spans if _LAUNCHER.match(span.group(1))]
        if fence is not None and fence != "mermaid":
            inside = [(span.start(), span.end()) for span in spans]
            candidates.extend(
                text[match.start() :]
                for match in _LAUNCHER.finditer(text)
                if not any(start <= match.start() < end for start, end in inside)
                and not _is_spec_tail(text, match.start())
            )
        for source in candidates:
            try:
                tokens = _command_tokens(source)
            except ValueError as error:
                raise AssertionError(
                    f"{relative}:{line_number}: unquotable documented command {source!r}: {error}"
                ) from error
            argv = _refract_argv(tokens)
            if argv is not None and argv and (argv[0] in KNOWN_SUBCOMMANDS or argv[0] == "--version"):
                commands.append(DocumentedCommand(f"{relative}:{line_number}", source.strip(), argv))
    return commands


def _scanned_files() -> list[str]:
    """Top-level documentation files that form the command surface."""
    relatives = ["README.md", "AGENTS.md"]
    docs = REPO_ROOT / "docs"
    relatives.extend(f"docs/{path.name}" for path in sorted(docs.glob("*.md")) if path.is_file())
    return relatives


def _documented_commands() -> list[DocumentedCommand]:
    """Every documented invocation across the scanned files, in doc order."""
    commands: list[DocumentedCommand] = []
    for relative in _scanned_files():
        commands.extend(_scan_file(relative))
    return commands


class DocumentedCommandContractTests(unittest.TestCase):
    """Documented commands and the argument parser cannot drift apart."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.commands: list[DocumentedCommand] = _documented_commands()

    def test_extraction_floor_holds(self) -> None:
        """The extractor keeps finding the documented command inventory.

        Guards the extraction itself so the parse loop cannot vacuously pass
        on a silent extractor. Counts observed at the time of writing; the
        floors are what the test enforces as docs evolve:

        | File                        | Commands | Floor |
        |-----------------------------|---------:|------:|
        | README.md                   |        8 |     5 |
        | AGENTS.md                   |        2 |     0 |
        | docs/AGENT_GUIDED.md        |        3 |     2 |
        | docs/ANSWERS.md             |        1 |     0 |
        | docs/MIGRATION.md           |        2 |     0 |
        | docs/PROMPTS.md             |       19 |     8 |
        | docs/RELEASING.md           |        3 |     0 |
        | docs/DEVELOPMENT_PROCESS.md |        1 |     0 |
        """
        per_file: dict[str, int] = {}
        for command in self.commands:
            file = command.location.rsplit(":", 1)[0]
            per_file[file] = per_file.get(file, 0) + 1
        for relative, floor in sorted(PER_FILE_FLOORS.items()):
            self.assertGreaterEqual(
                per_file.get(relative, 0),
                floor,
                f"{relative} contributed {per_file.get(relative, 0)} commands, expected at least {floor}",
            )
        self.assertGreater(
            len(self.commands),
            MINIMUM_TOTAL_COMMANDS,
            f"only {len(self.commands)} documented commands extracted across {sorted(per_file)}",
        )

    def test_documented_commands_parse(self) -> None:
        """Every documented invocation is accepted by the real parser.

        ``refract --version`` exits 0 through argparse's version action and
        counts as parsed; any other SystemExit is an argparse rejection and
        fails the case with its source location.
        """
        parser = build_parser()
        for command in self.commands:
            with self.subTest(command.location):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    try:
                        args = parser.parse_args(list(command.argv))
                    except SystemExit as exit_code:
                        self.assertEqual(
                            0,
                            exit_code.code,
                            f"{command.location}: {command.display!r} was rejected by the CLI parser",
                        )
                        continue
                    if command.argv[0] in {"init", "retrofit"} and not (
                        args.agent_guided and not args.dry_run
                    ):
                        try:
                            _validate_agent_arguments(args)
                        except ValueError as error:
                            self.fail(
                                f"{command.location}: {command.display!r} violates CLI argument rules: {error}"
                            )


if __name__ == "__main__":
    unittest.main()
