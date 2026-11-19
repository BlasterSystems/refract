"""The documented preview/apply pairs in docs/PROMPTS.md run end to end.

Each pair is anchored by a ``<!-- flow:... -->`` marker comment on its own
line directly before the command. The tests extract the documented command
text, substitute the placeholders, run the preview in a fixture repository
with stdout captured to a plan file outside the repository, read ``status``
and ``plan_id`` from the JSON, substitute the real plan identifier into the
apply command, and apply in a pseudo-terminal, answering prompts from their
text alone. The apply must exit 0, write the generated project, keep
repository-owned files byte-identical, and leave the target passing
``refract validate`` without errors.
"""

from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

try:
    import pty

    _NO_PTY: str | None = None
except ImportError as error:  # pragma: no cover - non-POSIX platforms
    _NO_PTY = f"no pty available: {error}"

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "docs" / "PROMPTS.md"
SCRIPT = ROOT / "scripts" / "refract.sh"
SRC = ROOT / "src"

APPLY_CONFIRMATION = "Apply the complete recomputed plan"
# Labels of the interactive prompts in refract.cli._request_from_args. The
# driver answers each with its default (an empty line); the boolean prompts
# are matched by their shared "? [y/N]: " / "? [Y/n]: " suffix instead.
PROMPT_LABELS = (
    "Project name",
    "Project description",
    "Build command (leave empty if not configured)",
    "Test command (leave empty if not configured)",
    "Run command (leave empty if not configured)",
    "Ticket prefix (use 'none' if not configured)",
    "Platforms (comma-separated)",
)
APPLIED_FILES = (
    "AGENTS.md",
    ".refract/manifest.json",
    ".refract/config.json",
    "docs/README.md",
    ".agents/skills/refract/SKILL.md",
    ".omp/RULES.md",
)


def _fixture_env() -> dict[str, str]:
    """The test environment plus the repository's src on the import path."""
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = f"{SRC}{os.pathsep}{existing}" if existing else str(SRC)
    return environment


def _documented_argv(marker: str) -> list[str]:
    """Return the tokens of the command following the marker in docs/PROMPTS.md.

    The marker sits on its own line immediately before the command; a trailing
    backslash continues the command on the next line and inline-code commands
    are wrapped in backticks. A missing marker is an assertion failure, so the
    test breaks when a documented flow moves.
    """
    lines = PROMPTS.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() == f"<!-- {marker} -->":
            break
    else:
        raise AssertionError(f"docs/PROMPTS.md has no <!-- {marker} --> marker")
    body = [lines[index + 1].strip()]
    cursor = index + 2
    while body[-1].endswith("\\"):
        body[-1] = body[-1].rstrip("\\").rstrip()
        if cursor >= len(lines):
            raise AssertionError(f"docs/PROMPTS.md: unterminated command after <!-- {marker} -->")
        body.append(lines[cursor].strip())
        cursor += 1
    return shlex.split(" ".join(body).strip("`"))


def _substitute(argv: list[str], values: dict[str, str]) -> list[str]:
    """Replace the documented <PLAN_FILE>, <PLAN_ID> and <INTENT_FILE> placeholders."""
    return [values.get(token, token) for token in argv]


def _in_tree(argv: list[str]) -> list[str]:
    """Map a documented command onto an in-tree interpreter invocation.

    Bare ``refract`` runs as ``PYTHONPATH=src python3 -P -m refract``: the
    command scripts/refract.sh itself execs, where ``-P`` keeps the working
    directory off the import path so a fixture's planted refract/ package
    cannot shadow the CLI. A documented ``scripts/refract.sh`` command
    resolves to the repository's own wrapper.
    """
    if argv[0] == "refract":
        return [sys.executable, "-P", "-m", "refract", *argv[1:]]
    if argv[0] == "scripts/refract.sh":
        return [str(SCRIPT), *argv[1:]]
    raise AssertionError(f"documented command does not run refract in place: {argv[0]!r}")


def _prompt_answer(fragment: str) -> str | None:
    """Return the answer for a pending prompt at the fragment tail, if any.

    Prompts are written without a trailing newline, so a pending prompt is the
    text after the last line break of the terminal output. The final apply
    confirmation is answered with ``y``; every other prompt takes its default.
    """
    tail = fragment.rsplit("\n", 1)[-1].rsplit("\r", 1)[-1]
    if APPLY_CONFIRMATION in tail:
        return "y\n"
    if tail.startswith(PROMPT_LABELS):
        return "\n"
    if tail.endswith("? [y/N]: ") or tail.endswith("? [Y/n]: "):
        return "\n"
    return None


def _drive_apply(argv: list[str], cwd: Path, timeout: float = 120.0) -> tuple[int, str]:
    """Run argv in a pseudo-terminal, answering prompts until the process exits.

    Drives purely on prompt text and process exit, never on timing: the loop
    waits on the terminal file descriptor and answers whatever prompt text is
    pending. Returns the exit code and the full transcript.
    """
    master, slave = pty.openpty()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=_fixture_env(),
        close_fds=True,
        start_new_session=True,
    )
    os.close(slave)  # the child owns its copy now
    deadline = time.monotonic() + timeout
    fragment = ""
    transcript: list[str] = []
    try:
        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise AssertionError(
                    f"interactive apply did not finish within {timeout:.0f}s; "
                    f"transcript tail:\n{''.join(transcript)[-4000:]}"
                )
            ready, _, _ = select.select([master], [], [], min(remaining, 1.0))
            if not ready:
                continue
            try:
                chunk = os.read(master, 65_536)
            except OSError:
                break  # terminal closed: the process is done
            if not chunk:
                break
            text = chunk.decode("utf-8", "replace")
            transcript.append(text)
            fragment += text
            answer = _prompt_answer(fragment)
            if answer is not None:
                try:
                    os.write(master, answer.encode())
                except OSError:
                    break
                fragment = ""
    finally:
        os.close(master)
        if process.poll() is None:
            process.kill()
            process.wait()
    return process.returncode, "".join(transcript)


def _preview(marker: str, cwd: Path, plan_file: Path, values: dict[str, str]) -> dict:
    """Run a documented preview command and return its JSON payload.

    The documented ``> <PLAN_FILE>`` shell redirect is replaced by capturing
    stdout into plan_file, which sits outside the repository as the prompts
    require.
    """
    argv = _documented_argv(marker)
    if len(argv) >= 2 and argv[-2] == ">":
        argv = argv[:-2]
    result = subprocess.run(
        _in_tree(_substitute(argv, values)),
        cwd=cwd,
        env=_fixture_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    plan_file.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise AssertionError(
            f"documented preview {marker} exited {result.returncode}: {result.stderr[-2000:]}"
        )
    return json.loads(plan_file.read_text(encoding="utf-8"))


def _run_pair(
    preview_marker: str,
    apply_marker: str,
    cwd: Path,
    outside: Path,
    values: dict[str, str] | None = None,
) -> dict:
    """Run one documented preview/apply pair in cwd; return the preview payload.

    The plan identifier from the preview JSON is substituted into the apply
    command, which then runs in a pseudo-terminal answering the interactive
    prompts. The apply must exit 0.
    """
    supplied = dict(values or {})
    plan_file = outside / "plan.json"
    payload = _preview(preview_marker, cwd, plan_file, supplied)
    assert payload["status"] == "dry-run", f"preview status {payload['status']!r}, expected 'dry-run'"
    plan_id = payload["plan_id"]
    assert isinstance(plan_id, str) and len(plan_id) == 64, plan_id
    supplied["<PLAN_ID>"] = plan_id
    supplied.setdefault("<PLAN_FILE>", str(plan_file))
    returncode, transcript = _drive_apply(
        _in_tree(_substitute(_documented_argv(apply_marker), supplied)), cwd
    )
    if returncode != 0:
        raise AssertionError(
            f"documented apply {apply_marker} exited {returncode}; transcript tail:\n{transcript[-4000:]}"
        )
    return payload


def _assert_applied_and_valid(root: Path) -> None:
    """Assert the apply wrote the generated project and validation reports no errors."""
    for relative in APPLIED_FILES:
        assert (root / relative).is_file(), f"apply did not write {relative}"
    result = subprocess.run(
        [sys.executable, "-P", "-m", "refract", "validate", "--target", "."],
        cwd=root,
        env=_fixture_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"validate exited {result.returncode}: {result.stderr[-2000:] or result.stdout[-2000:]}"
    )
    assert "Validation passed." in result.stdout


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _commit(root: Path, subject: str) -> None:
    subprocess.run(
        [
            "git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
            "commit", "--allow-empty", "-q", "-m", subject,
        ],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _fixture_empty(root: Path) -> None:
    """An empty repository (git init, no files)."""
    _git(root, "init", "-q")


def _fixture_own_agents(root: Path) -> None:
    """A repository that owns AGENTS.md and .claude/settings.json."""
    _git(root, "init", "-q")
    (root / "AGENTS.md").write_text("# Our own agents guide with distinctive content\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text('{"our": true}\n', encoding="utf-8")


def _fixture_hostile(root: Path) -> None:
    """A repository shaped to mislead naive detection.

    A root token.py and a refract/ package shadow the CLI unless it keeps the
    working directory off the import path, 250 documentation files and an
    oversized lockfile exceed the bounded inspection budgets, and ticket-style
    commit subjects exercise prefix detection.
    """
    _git(root, "init", "-q")
    (root / "token.py").write_text("TOKEN = 'unused placeholder'\n", encoding="utf-8")
    (root / "refract").mkdir()
    (root / "refract" / "__init__.py").write_text("", encoding="utf-8")
    documents = root / "docs"
    documents.mkdir()
    for index in range(250):
        (documents / f"page-{index:03d}.md").write_text("# page\n", encoding="utf-8")
    (root / "package-lock.json").write_bytes(b"0" * (1_048_576 + 1))
    for number in range(12, 17):
        _commit(root, f"ABC-{number} fix thing")


def _advisory_intent(cwd: Path, outside: Path) -> tuple[Path, str, str]:
    """Write the advisory intent file from ``refract inspect`` evidence.

    Mirrors the Advisory setup prompt: the schema is refract-intent/v1, the
    name and description come from detection, commands absent from the
    evidence stay null, and every privileged feature is false. Returns the
    intent path and the detected name and description.
    """
    result = subprocess.run(
        [sys.executable, "-P", "-m", "refract", "inspect", "--target", "."],
        cwd=cwd,
        env=_fixture_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"inspect exited {result.returncode}: {result.stderr[-2000:]}"
    evidence = json.loads(result.stdout)
    name = evidence["facts"]["name"]
    description = evidence["facts"]["description"]
    intent = {
        "schema": "refract-intent/v1",
        "project": {
            "name": name,
            "description": description,
            "build_command": None,
            "test_command": None,
            "run_command": None,
            "ticket_prefix": None,
        },
        "features": {
            "platforms": ["claude", "codex", "opencode", "omp"],
            "mcp": False,
            "agents": False,
            "github": False,
            "scheduled_audit": False,
            "hooks": False,
            "permissions": False,
        },
    }
    path = outside / "intent.json"
    path.write_text(json.dumps(intent, indent=2) + "\n", encoding="utf-8")
    return path, name, description


class DocumentedFlowTests(unittest.TestCase):
    """Every marked preview/apply pair in docs/PROMPTS.md runs end to end."""

    def test_setup_pair_in_repository_with_own_agent_files(self) -> None:
        """The Set-up pair keeps the repository's own AGENTS.md byte-identical."""
        if _NO_PTY:
            self.skipTest(_NO_PTY)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"
            outside.mkdir()
            root = Path(directory) / "repo"
            root.mkdir()
            _fixture_own_agents(root)
            own_agents = (root / "AGENTS.md").read_bytes()
            own_settings = (root / ".claude" / "settings.json").read_bytes()
            _run_pair("flow:setup-preview", "flow:setup-apply", root, outside)
            self.assertEqual(
                own_agents,
                (root / "AGENTS.md").read_bytes(),
                "--keep-existing must keep the repository's own AGENTS.md",
            )
            self.assertEqual(own_settings, (root / ".claude" / "settings.json").read_bytes())
            _assert_applied_and_valid(root)

    def test_new_project_pair_in_empty_repository(self) -> None:
        """The New-project pair applies into an empty repository with --target ."""
        if _NO_PTY:
            self.skipTest(_NO_PTY)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"
            outside.mkdir()
            root = Path(directory) / "repo"
            root.mkdir()
            _fixture_empty(root)
            _run_pair("flow:new-project-preview", "flow:new-project-apply", root, outside)
            _assert_applied_and_valid(root)

    def test_existing_pair_in_repository_with_own_agent_files(self) -> None:
        """The Existing-project pair keeps the repository's own agent files."""
        if _NO_PTY:
            self.skipTest(_NO_PTY)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"
            outside.mkdir()
            root = Path(directory) / "repo"
            root.mkdir()
            _fixture_own_agents(root)
            own_agents = (root / "AGENTS.md").read_bytes()
            own_settings = (root / ".claude" / "settings.json").read_bytes()
            _run_pair("flow:existing-preview", "flow:existing-apply", root, outside)
            self.assertEqual(
                own_agents,
                (root / "AGENTS.md").read_bytes(),
                "--keep-existing must keep the repository's own AGENTS.md",
            )
            self.assertEqual(own_settings, (root / ".claude" / "settings.json").read_bytes())
            _assert_applied_and_valid(root)

    def test_existing_pair_in_hostile_repository(self) -> None:
        """The Existing-project pair survives a repository shaped to mislead it."""
        if _NO_PTY:
            self.skipTest(_NO_PTY)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"
            outside.mkdir()
            root = Path(directory) / "repo"
            root.mkdir()
            _fixture_hostile(root)
            _run_pair("flow:existing-preview", "flow:existing-apply", root, outside)
            _assert_applied_and_valid(root)

    def test_advisory_pair_in_hostile_repository(self) -> None:
        """The Advisory pair plans and applies from an intent built from detection."""
        if _NO_PTY:
            self.skipTest(_NO_PTY)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside"
            outside.mkdir()
            root = Path(directory) / "repo"
            root.mkdir()
            _fixture_hostile(root)
            intent, name, description = _advisory_intent(root, outside)
            payload = _run_pair(
                "flow:advisory-preview",
                "flow:advisory-apply",
                root,
                outside,
                {"<INTENT_FILE>": str(intent)},
            )
            self.assertEqual(name, payload["request"]["project"]["name"])
            self.assertEqual(description, payload["request"]["project"]["description"])
            _assert_applied_and_valid(root)


if __name__ == "__main__":
    unittest.main()
