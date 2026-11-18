from __future__ import annotations

import re

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
