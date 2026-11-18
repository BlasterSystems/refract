"""Findings about an existing agent setup, reported during retrofit.

The scan reads file names, git tracking status, and whether CLAUDE.md imports
AGENTS.md. It never reads other file contents (settings may hold secrets) and
never changes anything; findings become plan warnings for the human applying
the retrofit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .planner import Action, Plan, skill_group


def _git_tracked(root: Path, relative: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _skill_names(directory: Path) -> set[str]:
    try:
        return {child.name for child in directory.iterdir() if (child / "SKILL.md").is_file()}
    except OSError:
        return set()


def existing_setup_findings(root: Path) -> list[str]:
    root = root.expanduser().absolute()
    if not root.is_dir():
        return []
    findings: list[str] = []
    local_settings = ".claude/settings.local.json"
    if (root / local_settings).is_file() and _git_tracked(root, local_settings):
        findings.append(
            f"{local_settings} is committed; it holds personal Claude Code settings. Move shared policy to "
            ".claude/settings.json (refract --permissions) and untrack the local file"
        )
    if (root / ".claude/claude.json").is_file():
        findings.append(".claude/claude.json is not a Claude Code configuration file and is ignored by Claude Code")
    if (root / ".pi").is_dir():
        findings.append(".pi/ configures the deprecated Pi agent; select the omp platform instead")
    claude_only = sorted(_skill_names(root / ".claude/skills") - _skill_names(root / ".agents/skills"))
    if claude_only:
        shown = ", ".join(claude_only[:8]) + (" ..." if len(claude_only) > 8 else "")
        findings.append(
            f"{len(claude_only)} skill(s) exist only in .claude/skills ({shown}); Codex, OpenCode, and omp read "
            ".agents/skills, so copy the project-specific ones there to share them across agents"
        )
    claude_md = root / "CLAUDE.md"
    if claude_md.is_file() and (root / "AGENTS.md").is_file():
        try:
            imports_agents = "@AGENTS.md" in claude_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            imports_agents = True
        if not imports_agents:
            findings.append(
                "CLAUDE.md does not import @AGENTS.md; the two context files can drift. Keep shared rules in "
                "AGENTS.md and import it from CLAUDE.md"
            )
    return findings


def plan_findings(plan: Plan) -> list[str]:
    """Explain what --keep-existing kept and what it therefore did not generate."""
    findings: list[str] = []
    kept = [op.path for op in plan.operations if op.action == Action.SKIP_UNMANAGED and "--keep-existing" in op.detail]
    skipped = sorted({skill_group(op.path) for op in plan.operations if op.action == Action.SKIP_KEPT} - {None})
    if kept:
        findings.append(f"kept {len(kept)} existing project-owned file(s) instead of refract's versions: {', '.join(kept)}")
    if skipped:
        findings.append(
            "project-owned skills replace refract's on every platform: " + ", ".join(skipped)
            + "; refract's copies for other agents were not generated"
        )
    if ".claude/settings.json" in kept:
        findings.append("Claude Code hooks and permissions from refract are not installed because .claude/settings.json was kept")
    if ".codex/config.toml" in kept:
        findings.append("Codex MCP, agent, and permission settings from refract are not installed because .codex/config.toml was kept")
    return findings
