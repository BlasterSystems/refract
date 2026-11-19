"""Contract: documents that claim to mirror a template stay in sync with it.

Work package 1.5 of tasks/plan-entry-path-consolidation.md (design:
"Mirrored documents" in tasks/research-entry-path-consolidation.md — "a
test compares the template documents that the repository's own ``docs/``
claims to mirror").

Inventory, verified 2026-11-19:

- Repo docs, top level (16): ``AGENT_GUIDED.md``, ``ANSWERS.md``,
  ``ARCHITECTURE.md``, ``DEVELOPMENT_PROCESS.md``,
  ``GENERATED_OUTPUT.md``, ``LLM_WIKI_EVALUATION.md``, ``MIGRATION.md``,
  ``PLATFORM_SUPPORT.md``, ``PROMPTS.md``, ``PROJECT_SUMMARY.md``,
  ``README.md``, ``RELEASING.md``, ``SECURITY_AUDIT.md``,
  ``superpowers-spec.md``, ``TASK_BREAKDOWN.md``, ``THREAT_MODEL.md``.
- Template docs, top level (9): ``AGENT_GUIDED.md``, ``ARCHITECTURE.md``,
  ``DEPLOYMENT.md``, ``DEVELOPMENT_PROCESS.md``,
  ``PLATFORM_SUPPORT.md``, ``README.md``, ``RELEASING.md``,
  ``SECURITY_AUDIT.md``, ``TASK_BREAKDOWN.md``.

Compared pairs (the templates the repo docs claim to mirror, 2) — each
repo document states the claim in its opening paragraph, "Scaffolded
projects receive a project-level copy of this document rendered from
``src/refract/templates/core/docs/<NAME>.md``":

- ``docs/SECURITY_AUDIT.md`` ↔
  ``src/refract/templates/core/docs/SECURITY_AUDIT.md``
- ``docs/TASK_BREAKDOWN.md`` ↔
  ``src/refract/templates/core/docs/TASK_BREAKDOWN.md``

Invariant: for every mirrored pair, the set of ATX section headings must
be identical in both directions — a section added to one side without the
other is drift and fails with the exact heading and the pair name. One
subTest per pair.

Normalization before comparison:

- Lines inside fenced code blocks (``` or ~~~) are skipped, so ``#``
  shell comments are not headings; a heading is an ATX line (0–3 leading
  spaces, 1–6 ``#``, then text).
- Backticks are stripped and whitespace is collapsed.
- Whitespace-delimited tokens that contain ``/`` or start with ``.`` are
  canonicalized to ``<path>``: template docs may reference generated-
  project paths (``.refract/bin/``, ``.agents/``) where repo docs
  reference this repository (``src/refract/``) — that is environment
  spelling, not heading drift.

Name collisions that are NOT mirrors (and ``DEPLOYMENT.md``, which has no
repo counterpart at all) are enumerated in ``NOT_MIRRORED`` with the
reason each pair is a different document rather than a drifted copy: the
repo side describes developing Refract itself, the template side is the
generated project's own documentation written with double-brace
``PLACEHOLDER`` substitution and "Not configured" fill-in sections. Git history agrees:
``src/refract/templates/core/docs/ARCHITECTURE.md`` entered the tree
(9aa47ac) already as a generic skeleton, never as a copy of the repo
document. The repo-only documents (``PROMPTS.md``, ``PROJECT_SUMMARY.md``,
``ANSWERS.md``, ``GENERATED_OUTPUT.md``, ``MIGRATION.md``,
``superpowers-spec.md``, ``THREAT_MODEL.md``,
``LLM_WIKI_EVALUATION.md``) describe Refract and need no classification.

Escape hatch: if a mirrored pair legitimately needs to diverge in one
heading, add that heading to ``HEADING_EXCEPTIONS`` next to a comment
explaining why — never weaken the comparison or the normalization
silently. There are no exceptions today.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_DOCS = REPO_ROOT / "docs"
TEMPLATE_DOCS = REPO_ROOT / "src" / "refract" / "templates" / "core" / "docs"

#: A backticked path into the template docs tree inside a top-level repo
#: document is that document's claim to be the same document as the
#: template, for two audiences. References outside top-level ``docs/*.md``
#: (for example ``docs/adr/``) do not count; incidental unbackticked
#: mentions do not count either.
MIRROR_CLAIM_RE = re.compile(r"`src/refract/templates/core/docs/([A-Za-z0-9_.-]+\.md)`")

#: Template documents that exist on both sides (or only as templates) but
#: are different documents by design, keyed by template file name. Adding
#: a file under ``templates/core/docs/`` requires either a mirror claim in
#: a repo document or an entry here.
NOT_MIRRORED: dict[str, str] = {
    "AGENT_GUIDED.md": (
        "repo doc is the agent-guided bootstrap protocol (roles, inspect, "
        "typed proposal, handoff); template doc is the generated project's "
        "agent-guided maintenance workflow"
    ),
    "ARCHITECTURE.md": (
        "repo doc maps refract's own modules and safety model; template "
        'doc is a fill-in architecture skeleton ("Not configured" sections) '
        "for generated projects"
    ),
    "DEPLOYMENT.md": (
        "generated-project deployment seed; this repository has no "
        "counterpart document"
    ),
    "DEVELOPMENT_PROCESS.md": (
        "repo doc is refract's contribution workflow; template doc is the "
        "generated project's own process with double-brace placeholder commands"
    ),
    "PLATFORM_SUPPORT.md": (
        "repo doc is refract's adapter capability matrix; template doc "
        "renders the user's project report from the PLATFORM_TABLE template token"
    ),
    "README.md": (
        "repo doc indexes refract's documentation; template doc indexes "
        "the generated project's documentation"
    ),
    "RELEASING.md": (
        "repo doc is refract's concrete release procedure; template doc is "
        "a generic release-contract seed"
    ),
}

#: Headings exempt from the comparison for one mirrored pair, keyed by
#: template file name; each entry needs a comment explaining the intended
#: divergence. Empty on purpose — extend only with a written reason.
HEADING_EXCEPTIONS: dict[str, frozenset[str]] = {}

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(\S.*?)\s*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _headings(text: str) -> list[str]:
    """Return every ATX heading line outside fenced code blocks."""
    found: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            continue
        if fence is None and _HEADING_RE.match(line):
            found.append(line.strip())
    return found


def _normalize(heading: str) -> str:
    """Collapse a heading line to its comparable form (see module docstring)."""
    text = heading.lstrip("#").strip().replace("`", "")
    tokens = [
        "<path>" if ("/" in token or token.startswith(".")) else token
        for token in text.split()
    ]
    return " ".join(tokens)


def _canonical(raw_headings: list[str]) -> dict[str, list[str]]:
    """Map normalized heading text back to the exact lines it came from."""
    index: dict[str, list[str]] = {}
    for raw in raw_headings:
        index.setdefault(_normalize(raw), []).append(raw)
    return index


class MirroredDocsContractTests(unittest.TestCase):
    """Template documents the repo claims to mirror must match it."""

    def _claimed_pairs(self) -> list[tuple[str, Path, Path]]:
        """Derive (label, repo doc, template doc) from the mirror claims."""
        pairs: list[tuple[str, Path, Path]] = []
        for doc in sorted(REPO_DOCS.glob("*.md")):
            for name in sorted(set(MIRROR_CLAIM_RE.findall(doc.read_text(encoding="utf-8")))):
                label = f"docs/{doc.name} <-> src/refract/templates/core/docs/{name}"
                pairs.append((label, doc, TEMPLATE_DOCS / name))
        return pairs

    def test_mirror_claims_are_discoverable(self) -> None:
        """The claim pattern must keep finding the documented mirrors.

        If the claim sentence in the docs is reworded, this fails instead
        of letting the pair comparison silently drop to zero pairs.
        """
        pairs = self._claimed_pairs()
        self.assertTrue(
            pairs,
            "no mirror claims found in docs/*.md; if the claim sentence "
            "moved or was reworded, update MIRROR_CLAIM_RE — do not delete "
            "this test",
        )

    def test_mirrored_heading_sets_match(self) -> None:
        """Every section heading of a mirrored pair appears on both sides.

        Checked in both directions: a template section missing from the
        repo doc and a repo section missing from the template are both
        drift, because each document is a copy of the other for its own
        audience.
        """
        for label, repo_doc, template_doc in self._claimed_pairs():
            with self.subTest(pair=label):
                self.assertTrue(
                    template_doc.exists(),
                    f"{label}: claimed template file does not exist",
                )
                template_index = _canonical(
                    _headings(template_doc.read_text(encoding="utf-8"))
                )
                repo_index = _canonical(_headings(repo_doc.read_text(encoding="utf-8")))
                exceptions = HEADING_EXCEPTIONS.get(template_doc.name, frozenset())
                only_in_template = sorted(set(template_index) - set(repo_index) - exceptions)
                only_in_repo = sorted(set(repo_index) - set(template_index) - exceptions)
                self.assertEqual(
                    only_in_template,
                    [],
                    f"{label}: template heading(s) missing from the repo doc "
                    f"({repo_doc.name}) — update both documents, or if the "
                    f"divergence is intended record it in HEADING_EXCEPTIONS: "
                    + "; ".join(repr(h) for h in only_in_template),
                )
                self.assertEqual(
                    only_in_repo,
                    [],
                    f"{label}: repo heading(s) missing from the template doc "
                    f"({template_doc.name}) — update both documents, or if the "
                    f"divergence is intended record it in HEADING_EXCEPTIONS: "
                    + "; ".join(repr(h) for h in only_in_repo),
                )

    def test_every_template_document_is_classified(self) -> None:
        """A template doc is either a claimed mirror or in NOT_MIRRORED.

        Nothing under ``templates/core/docs/`` may silently escape the
        mirror decision: a new file forces an explicit classification
        here, and removing one invalidates its entry.
        """
        templates = {path.name for path in TEMPLATE_DOCS.glob("*.md")}
        claimed = {template.name for _, _, template in self._claimed_pairs()}
        unclassified = sorted(templates - claimed - set(NOT_MIRRORED))
        self.assertEqual(
            unclassified,
            [],
            "template documents with neither a mirror claim nor a "
            "NOT_MIRRORED entry — classify them explicitly: "
            + ", ".join(unclassified),
        )
        stale = sorted(set(NOT_MIRRORED) - templates)
        self.assertEqual(
            stale,
            [],
            "NOT_MIRRORED entries without a template file: " + ", ".join(stale),
        )


if __name__ == "__main__":
    unittest.main()
