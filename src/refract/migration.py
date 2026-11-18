"""Findings about an existing agent setup, reported during retrofit.

The scan reads file names, git tracking status, and whether CLAUDE.md imports
AGENTS.md. It never reads other file contents (settings may hold secrets) and
never changes anything; findings become plan warnings for the human applying
the retrofit.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from .gitsafe import run_git

from .planner import Action, Plan, skill_group


def _git_tracked(root: Path, relative: str) -> bool:
    result = run_git(root, "ls-files", "--error-unmatch", "--", relative)
    return result is not None and result.returncode == 0


def _display(name: str) -> str:
    """Escape repository-controlled names so they cannot forge output lines."""
    return "".join(
        f"\\u{ord(char):04x}" if unicodedata.category(char).startswith("C") else char for char in name
    )


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
        shown = ", ".join(_display(name) for name in claude_only[:8]) + (" ..." if len(claude_only) > 8 else "")
        findings.append(
            f"{len(claude_only)} skill(s) exist only in .claude/skills ({shown}); Codex, OpenCode, and omp read "
            ".agents/skills, so copy the project-specific ones there to share them across agents"
        )
    claude_md = root / "CLAUDE.md"
    if claude_md.is_file() and (root / "AGENTS.md").is_file():
        try:
            if claude_md.is_symlink():
                raise OSError("symlink")
            with claude_md.open("rb") as handle:
                imports_agents = b"@AGENTS.md" in handle.read(1_000_000)
        except OSError:
            imports_agents = True
        if not imports_agents:
            findings.append(
                "CLAUDE.md does not import @AGENTS.md; the two context files can drift. Keep shared rules in "
                "AGENTS.md and import it from CLAUDE.md"
            )
    return findings


PLATFORM_CONFIG = {
    ".claude/settings.json": "Claude Code hooks and permissions",
    ".codex/config.toml": "Codex MCP, agent, and permission settings",
    ".codex/hooks.json": "Codex hooks",
    "opencode.json": "OpenCode permissions and MCP",
    ".omp/settings.json": "omp approval policy and autolearn protection",
    ".omp/mcp.json": "omp MCP",
    ".mcp.json": "Claude Code MCP",
}


def plan_findings(plan: Plan) -> list[str]:
    """Explain exactly what --keep-existing kept and what it did not generate."""
    findings: list[str] = []
    kept = sorted(op.path for op in plan.operations if op.action == Action.SKIP_UNMANAGED and "--keep-existing" in op.detail)
    if not kept:
        return findings
    findings.append(f"kept {len(kept)} existing project-owned file(s) instead of refract's versions: {', '.join(map(_display, kept))}")
    by_group: dict[str, dict[str, list[str]]] = {}
    for op in plan.operations:
        group = skill_group(op.path)
        if not group:
            continue
        entry = by_group.setdefault(group, {"kept": [], "skipped": [], "managed": []})
        if op.action == Action.SKIP_UNMANAGED and op.path in kept:
            entry["kept"].append(op.path)
        elif op.action == Action.SKIP_KEPT:
            entry["skipped"].append(op.path)
        elif op.action in {Action.NO_CHANGE, Action.UPDATE_GENERATED, Action.CREATE} and op.path in plan.previous_manifest.files:
            entry["managed"].append(op.path)
    for group, entry in sorted(by_group.items()):
        if not entry["kept"] or not (entry["skipped"] or entry["managed"]):
            continue
        group = _display(group)
        message = f"skill '{group}': project-owned at {', '.join(map(_display, entry['kept']))}"
        if entry["skipped"]:
            message += f"; refract did not generate {', '.join(map(_display, entry['skipped']))}, so agents that read only those locations have no '{group}' skill"
        if entry["managed"]:
            message += f"; refract's copy remains at {', '.join(map(_display, entry['managed']))}, so agents will see different '{group}' skills until one copy is removed"
        findings.append(message)
    for path, what in PLATFORM_CONFIG.items():
        if path in kept:
            findings.append(f"{what} from refract are not installed because {path} was kept")
    return findings
