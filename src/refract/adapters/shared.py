from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import AdapterContext

CONTEXT7_URL = "https://mcp.context7.com/mcp"

# Project-relative secret locations every platform's permission policy denies.
SECRET_GLOBS = (".env", ".env.*")

_DESCRIPTION = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)


def skill_description(skill_markdown: str) -> str:
    """Return the front-matter description of a rendered SKILL.md."""
    if skill_markdown.startswith("---\n"):
        end = skill_markdown.find("\n---", 4)
        match = _DESCRIPTION.search(skill_markdown[4:end] if end != -1 else "")
        if match:
            return match.group(1)
    raise ValueError("skill front matter is missing a description")


# Hook launcher: a hook command runs outside any agent sandbox, while the
# scripts it executes live in the agent-writable workspace. The launcher
# therefore runs agent-check only if both scripts still match the SHA-256
# digests pinned into the hook configuration at generation time (Codex keeps
# .codex/ read-only under workspace-write). A mismatch, including a cwd that
# resolves to a different repository, skips the check with a JSON notice.
# The project root is the nearest ancestor of the start directory holding
# .refract/bin/agent-check, so non-git and monorepo-subdirectory projects work.
_LAUNCHER = (
    "import hashlib,json,os,subprocess,sys\n"
    "r=os.path.abspath(sys.argv[1] or os.curdir)\n"
    "while not os.path.isfile(os.path.join(r,\".refract/bin/agent-check\")) and os.path.dirname(r)!=r:\n"
    " r=os.path.dirname(r)\n"
    "pins=json.loads(sys.argv[2])\n"
    "def ok(rel,digest):\n"
    " p=os.path.join(r,rel)\n"
    " return os.path.isfile(p) and not os.path.islink(p) and hashlib.sha256(open(p,\"rb\").read()).hexdigest()==digest\n"
    "if not all(ok(k,v) for k,v in pins.items()):\n"
    " print(json.dumps({\"systemMessage\":\"refract hook skipped: hook scripts do not match the generated hashes; re-run refract\"}))\n"
    " sys.exit(0)\n"
    "sys.exit(subprocess.call([sys.executable,\"-I\",os.path.join(r,\".refract/bin/agent-check\"),\"--format\",\"json\"]))"
)


def pinned_hook_command(root_expression: str, digests: dict[str, str]) -> str:
    """Shell command for JSON-protocol Stop hooks (Claude Code, Codex).

    `root_expression` is a shell word resolving to the project root. The
    launcher source contains no single quotes, so it is safe inside them.
    """
    pins = json.dumps(digests, sort_keys=True, separators=(",", ":"))
    assert "'" not in _LAUNCHER and "'" not in pins
    return f"python3 -I -c '{_LAUNCHER}' {root_expression} '{pins}'"


def hook_script_digests(context: "AdapterContext") -> dict[str, str]:
    """SHA-256 of the exact bytes the core renders for each hook script."""
    from ..model import GeneratedFile

    sources = {".refract/bin/agent-check": "core/bin/agent-check.py", ".refract/bin/validate": "core/bin/validate.py"}
    return {
        target: hashlib.sha256(
            GeneratedFile.text(target, context.templates.render(source, context.values)).content
        ).hexdigest()
        for target, source in sources.items()
    }
