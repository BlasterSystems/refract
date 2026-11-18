from __future__ import annotations

import json

from ..model import GeneratedFile
from .base import AdapterContext
from .shared import CONTEXT7_URL


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class CodexAdapter:
    name = "codex"

    def render(self, context: AdapterContext) -> dict[str, GeneratedFile]:
        features = context.request.features
        files: dict[str, GeneratedFile] = {}
        # Safe project defaults: ask before leaving the sandbox, write only
        # inside the workspace, no outbound network from tool commands.
        # Codex loads the project .codex/ layer only for trusted projects.
        sections: list[str] = [
            f"approval_policy = {_toml_string('on-request')}",
            f"sandbox_mode = {_toml_string('workspace-write')}",
            "",
            "[sandbox_workspace_write]",
            "network_access = false",
            "",
        ]
        if features.agents:
            sections.extend(["[agents]", "enabled = true", "max_concurrent_threads_per_session = 4", ""])
            target = ".codex/agents/architecture-reviewer.toml"
            files[target] = GeneratedFile.text(
                target,
                context.templates.render("adapters/codex/agents/architecture-reviewer.toml", context.values),
            )
        if features.mcp:
            sections.extend(["[mcp_servers.context7]", f"url = {_toml_string(CONTEXT7_URL)}", ""])
        files[".codex/config.toml"] = GeneratedFile.text(".codex/config.toml", "\n".join(sections).rstrip())

        if features.hooks:
            hooks = {
                "description": "refract deterministic end-of-turn validation",
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": '"$(git rev-parse --show-toplevel)/.refract/bin/agent-check" --format json',
                                    "timeout": 120,
                                    "statusMessage": "refract validation",
                                }
                            ]
                        }
                    ]
                },
            }
            files[".codex/hooks.json"] = GeneratedFile.text(".codex/hooks.json", json.dumps(hooks, indent=2))
        return files
