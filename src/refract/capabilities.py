"""Single source of truth for per-platform capability support (ADR-0010).

Every capability is either rendered in the platform's native format or
recorded as unsupported with a reason. Renderer support rows, effective
feature flags, and CLI warnings all derive from this table so that a
selected feature is never dropped silently.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import FeatureSelection


@dataclass(frozen=True)
class Support:
    artifact: str | None
    note: str = ""

    @property
    def native(self) -> bool:
        return self.artifact is not None


# Capability -> FeatureSelection attribute that opts into it (None = always on).
CAPABILITIES: dict[str, str | None] = {
    "instructions": None,
    "skills": None,
    "skill_invocation": None,
    "permissions": "permissions",
    "rules": None,
    "subagents": "agents",
    "mcp": "mcp",
    "agent_hooks": "hooks",
}

LABELS = {
    "claude": "Claude Code",
    "codex": "OpenAI Codex",
    "opencode": "OpenCode",
    "omp": "OhMyPi (omp)",
    "pi": "Pi Coding Agent (deprecated)",
}

DEPRECATED_PLATFORMS = {
    "pi": "Pi is deprecated in favour of omp and will be removed in the next major release",
}

_UNSUPPORTED = Support(None)

MATRIX: dict[str, dict[str, Support]] = {
    "claude": {
        "instructions": Support("CLAUDE.md (imports AGENTS.md)"),
        "skills": Support(".claude/skills mirror"),
        "skill_invocation": Support("/<skill>"),
        "permissions": Support(".claude/settings.json"),
        "rules": Support("CLAUDE.md"),
        "subagents": Support(".claude/agents/*.md"),
        "mcp": Support(".mcp.json"),
        "agent_hooks": Support(".claude/settings.json Stop hook"),
    },
    "codex": {
        "instructions": Support("AGENTS.md"),
        "skills": Support(".agents/skills"),
        "skill_invocation": Support("$<skill> or /skills"),
        "permissions": Support(".codex/config.toml approval_policy/sandbox_mode", "project .codex/ layer loads only for trusted projects"),
        "rules": Support("AGENTS.md"),
        "subagents": Support(".codex/agents/*.toml"),
        "mcp": Support(".codex/config.toml"),
        "agent_hooks": Support(".codex/hooks.json Stop hook", "project .codex/ layer loads only for trusted projects"),
    },
    "opencode": {
        "instructions": Support("AGENTS.md"),
        "skills": Support(".agents/skills"),
        "skill_invocation": Support(".opencode/commands/<skill>.md"),
        "permissions": Support("opencode.json permission"),
        "rules": Support("AGENTS.md"),
        "subagents": Support(".opencode/agents/*.md"),
        "mcp": Support("opencode.json mcp"),
        "agent_hooks": Support(".opencode/plugins/refract-check.js (session.idle)"),
    },
    "omp": {
        "instructions": Support("AGENTS.md"),
        "skills": Support(".agents/skills"),
        "skill_invocation": Support("/skill:<skill>"),
        "permissions": Support(".omp/settings.json tools.approvalMode", "autolearn is disabled for every omp project regardless of this flag"),
        "rules": Support(".omp/RULES.md"),
        "subagents": Support(".omp/agents/*.md"),
        "mcp": Support(".omp/mcp.json"),
        "agent_hooks": Support(".omp/hooks/post/refract-check.ts (agent_end)"),
    },
    "pi": {
        "instructions": Support("AGENTS.md"),
        "skills": Support(".agents/skills"),
        "skill_invocation": Support("/skill:<skill>"),
        "permissions": Support(None, "Pi has no project permission policy"),
        "rules": Support("AGENTS.md"),
        "subagents": Support(None, "Pi has no built-in subagents"),
        "mcp": Support(None, "Pi has no built-in MCP"),
        "agent_hooks": Support(None, "Pi hooks require separately reviewed extensions"),
    },
}


def supports(platform: str, capability: str) -> bool:
    return MATRIX[platform].get(capability, _UNSUPPORTED).native


def effective_features(platform: str, features: FeatureSelection) -> dict[str, bool]:
    return {
        attribute: bool(getattr(features, attribute)) and supports(platform, capability)
        for capability, attribute in CAPABILITIES.items()
        if attribute is not None
    }


def capability_warnings(features: FeatureSelection) -> list[str]:
    warnings: list[str] = []
    for platform in features.normalized_platforms():
        if platform in DEPRECATED_PLATFORMS:
            warnings.append(DEPRECATED_PLATFORMS[platform])
        for capability, attribute in CAPABILITIES.items():
            if attribute is None or not getattr(features, attribute):
                continue
            support = MATRIX[platform][capability]
            if not support.native:
                reason = support.note or f"{LABELS[platform]} does not support {capability}"
                warnings.append(f"{reason}; no {LABELS[platform]} {capability} configuration is generated")
    return warnings


def platform_rows(features: FeatureSelection) -> str:
    enabled = set(features.normalized_platforms())
    rows = []
    for platform, label in LABELS.items():
        selection = "Enabled" if platform in enabled else "Not selected"
        cells = []
        for capability in CAPABILITIES:
            support = MATRIX[platform][capability]
            text = support.artifact if support.native else "Unsupported"
            if support.note:
                text = f"{text} ({support.note})"
            cells.append(text)
        rows.append(f"| {label} | {selection} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def platform_table_header() -> str:
    headers = ["Platform", "Selection", *(name.replace("_", " ").capitalize() for name in CAPABILITIES)]
    return "| " + " | ".join(headers) + " |\n|" + "---|" * len(headers)
