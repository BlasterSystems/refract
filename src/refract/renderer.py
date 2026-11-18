from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .adapters import ADAPTERS
from .adapters.base import AdapterContext
from .capabilities import effective_features, platform_rows, platform_table_header
from .model import CORE_SKILLS, BootstrapRequest, GeneratedFile
from .templating import TemplateEngine


def packaged_template_root() -> Path:
    return Path(__file__).resolve().parent / "templates"


def _display(value: str | None, fallback: str = "Not configured") -> str:
    return value.strip() if value and value.strip() else fallback


def _ticket_lifecycle(prefix: str) -> str:
    """Rendered only when a ticket prefix is configured (section 9 of the
    development process). Status transitions are part of the definition of
    done; wording stays tracker-neutral."""
    return f"""## 9. Ticket lifecycle

Work is tracked in the project's issue tracker: task identifiers use the `{prefix}-<number>` convention. **Status transitions are part of the definition of done: a ticket is never left in a state that contradicts the code.**

1. **Fetch** the ticket (description + acceptance criteria) before implementing anything.
2. **Before coding**: transition the ticket to "In Progress" and assign yourself; record the assignment in the ticket.
3. **Plan** in `tasks/<TICKET>.md` from `tasks/task-template.md`; keep it updated with decisions, evidence, and residual risks as the work progresses.
4. **Deliver — always via pull request**: push a branch and open a PR whose title references the ticket and whose body links the ticket and the task file. Direct pushes to the default branch are a process violation — including fixes, hotfixes, docs, and process changes themselves.
5. **On merge — mandatory status update**: transition the ticket to "Done" and post an evidence comment (commands run + observed results). This step is blocking: merging without the status update is a process violation, not optional cleanup.
6. **Multi-ticket changes**: a PR that covers several tickets (e.g. an epic landing its child stories) reconciles every covered ticket's status in the same pass — including epics and parents whose state the change completes. A ticket whose feature is only partially delivered stays "In Progress" with a comment naming the remainder.
7. **Reconciliation**: when work lands at a coarser grain than the tickets describe (an epic PR implementing many stories), verify each covered ticket against the actual code before transitioning it; tickets whose feature is genuinely absent stay open and become the next work items, not silent "Done"s."""


def _values(request: BootstrapRequest) -> dict[str, str]:
    facts = request.facts
    return {
        "PROJECT_NAME": facts.name,
        "PROJECT_DESCRIPTION": _display(facts.description, "No description configured"),
        "LANGUAGES": ", ".join(facts.languages) if facts.languages else "Not detected",
        "BUILD_COMMAND": _display(facts.build_command),
        "TEST_COMMAND": _display(facts.test_command),
        "RUN_COMMAND": _display(facts.run_command),
        "SCHEDULE_TRIGGER": (
            "  schedule:\n    - cron: '0 9 * * 1'"
            if request.features.scheduled_audit
            else ""
        ),
        "TICKET_POLICY": (
            f"Task identifiers use the `{facts.ticket_prefix}-<number>` convention."
            if facts.ticket_prefix
            else "No issue-tracker or ticket-prefix convention is configured."
        ),
        "TICKET_LIFECYCLE": (
            _ticket_lifecycle(facts.ticket_prefix) if facts.ticket_prefix else ""
        ),
        "GENERATED_VERSION": __version__,
    }


def render_project(request: BootstrapRequest, template_root: Path | None = None) -> dict[str, GeneratedFile]:
    templates = TemplateEngine(template_root or packaged_template_root())
    values = _values(request)
    files: dict[str, GeneratedFile] = {}

    core_templates = {
        "AGENTS.md": ("core/AGENTS.md", True),
        "docs/AGENT_GUIDED.md": ("core/docs/AGENT_GUIDED.md", True),
        "docs/ARCHITECTURE.md": ("core/docs/ARCHITECTURE.md", True),
        "docs/DEVELOPMENT_PROCESS.md": ("core/docs/DEVELOPMENT_PROCESS.md", True),
        "docs/DEPLOYMENT.md": ("core/docs/DEPLOYMENT.md", True),
        "docs/branches/README.md": ("core/docs/branches/README.md", True),
        "docs/README.md": ("core/docs/README.md", True),
        "docs/RELEASING.md": ("core/docs/RELEASING.md", True),
        "docs/SECURITY_AUDIT.md": ("core/docs/SECURITY_AUDIT.md", True),
        "docs/TASK_BREAKDOWN.md": ("core/docs/TASK_BREAKDOWN.md", True),
        "docs/adr/README.md": ("core/docs/adr/README.md", True),
        "docs/adr/template.md": ("core/docs/adr/template.md", True),
        "tasks/task-template.md": ("core/tasks/task-template.md", True),
    }
    for target, (source, mutable) in core_templates.items():
        files[target] = GeneratedFile.text(
            target,
            templates.render(source, values),
            mutable=mutable,
        )

    for skill in CORE_SKILLS:
        target = f".agents/skills/{skill}/SKILL.md"
        files[target] = GeneratedFile.text(
            target, templates.render(f"core/skills/{skill}/SKILL.md", values)
        )

    for name in ("validate", "docs-check", "deploy-ready"):
        target = f".refract/bin/{name}"
        files[target] = GeneratedFile.text(
            target, templates.render(f"core/bin/{name}.py", values), executable=True
        )

    config = {
        "schema_version": 1,
        "generator_version": __version__,
        "project": {
            "name": request.facts.name,
            "description": request.facts.description or None,
            "languages": request.facts.languages,
            "components": request.facts.components,
            "commands": {
                "build": request.facts.build_command,
                "test": request.facts.test_command,
                "run": request.facts.run_command,
            },
            "ticket_prefix": request.facts.ticket_prefix,
        },
        "features": {
            "requested": {
                "platforms": request.features.normalized_platforms(),
                "mcp": request.features.mcp,
                "agents": request.features.agents,
                "github": request.features.github,
                "scheduled_audit": request.features.scheduled_audit,
                "hooks": request.features.hooks,
                "permissions": request.features.permissions,
            },
            "effective_by_platform": {
                platform: effective_features(platform, request.features)
                for platform in request.features.normalized_platforms()
            },
        },
    }
    files[".refract/config.json"] = GeneratedFile.text(
        ".refract/config.json", json.dumps(config, indent=2)
    )

    support_values = dict(values)
    support_values["PLATFORM_TABLE"] = platform_table_header() + "\n" + platform_rows(request.features)
    files["docs/PLATFORM_SUPPORT.md"] = GeneratedFile.text(
        "docs/PLATFORM_SUPPORT.md",
        templates.render("core/docs/PLATFORM_SUPPORT.md", support_values),
    )

    for platform in request.features.normalized_platforms():
        adapter_context = AdapterContext(request=request, templates=templates, values=values)
        for path, generated in ADAPTERS[platform].render(adapter_context).items():
            if path in files and files[path].content != generated.content:
                raise ValueError(f"platform adapters produced conflicting output for {path}")
            files[path] = generated

    if request.features.hooks and any(
        effective_features(platform, request.features)["hooks"]
        for platform in request.features.normalized_platforms()
    ):
        files[".refract/bin/agent-check"] = GeneratedFile.text(
            ".refract/bin/agent-check",
            templates.render("core/bin/agent-check.py", values),
            executable=True,
        )

    if request.features.hooks:
        files[".githooks/pre-commit"] = GeneratedFile.text(
            ".githooks/pre-commit",
            templates.render("core/githooks/pre-commit.sh", values),
            executable=True,
        )
        files["setup-hooks.sh"] = GeneratedFile.text(
            "setup-hooks.sh",
            templates.render("core/githooks/setup-hooks.sh", values),
            executable=True,
        )

    if request.features.github:
        files[".github/workflows/docs-check.yml"] = GeneratedFile.text(
            ".github/workflows/docs-check.yml",
            templates.render("integrations/github/docs-check.yml", values),
        )
        files[".github/PULL_REQUEST_TEMPLATE.md"] = GeneratedFile.text(
            ".github/PULL_REQUEST_TEMPLATE.md",
            templates.render("integrations/github/PULL_REQUEST_TEMPLATE.md", values),
            mutable=True,
        )

    return dict(sorted(files.items()))

