from __future__ import annotations

from pathlib import Path

from refract.model import BootstrapRequest, FeatureSelection, ProjectFacts


def request(
    target: Path,
    platforms: list[str] | None = None,
    *,
    mcp: bool = False,
    agents: bool = False,
    github: bool = False,
    scheduled_audit: bool = False,
    hooks: bool = False,
    permissions: bool = False,
    ticket_prefix: str | None = None,
) -> BootstrapRequest:
    return BootstrapRequest(
        target=target,
        mode="init",
        facts=ProjectFacts(
            name="fixture-project",
            description="Contract fixture",
            languages=["Python", "TypeScript"],
            build_command="python -m build",
            test_command="python -m unittest",
            run_command=None,
            ticket_prefix=ticket_prefix,
            components=["python", "node"],
        ),
        features=FeatureSelection(
            platforms=platforms or ["claude", "codex", "opencode", "omp"],
            mcp=mcp,
            agents=agents,
            github=github or scheduled_audit,
            scheduled_audit=scheduled_audit,
            hooks=hooks,
            permissions=permissions,
        ),
    )
