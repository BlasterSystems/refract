from __future__ import annotations

import difflib
import json
import os
import stat
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .apply import ApplyError, apply_plan
from .inspection import InspectionArtifact, inspect_project
from .manifest import sha256_bytes
from .model import BootstrapRequest, FeatureSelection, GeneratedFile, ProjectFacts
from .paths import assert_safe_target_path
from .planner import Action, Plan, build_plan
from .protocol import PlanArtifact, ResultArtifact, plan_document
from .renderer import render_project
from .validation import validate_rendered, validate_target


@dataclass
class PreparedBootstrap:
    """Trusted rendered plan. Callers cannot inject desired file maps."""

    request: BootstrapRequest
    desired: dict[str, GeneratedFile]
    plan: Plan
    document: dict[str, Any]
    plan_id: str
    artifact: PlanArtifact
    remove_obsolete: bool = False
    keep_existing: bool = False

    def review_diffs(self, *, include_existing_content: bool = False) -> dict[str, str]:
        """Return diffs; repository-owned before-content requires trusted-terminal consent."""
        diffs: dict[str, str] = {}
        reviewed_actions = {Action.CREATE, Action.UPDATE_GENERATED, Action.REMOVE_OBSOLETE}
        for operation in self.plan.operations:
            if operation.action not in reviewed_actions:
                continue
            desired_text: list[str] = []
            if operation.action != Action.REMOVE_OBSOLETE:
                assert operation.generated is not None
                try:
                    desired_text = operation.generated.content.decode("utf-8").splitlines(keepends=True)
                except UnicodeDecodeError:
                    diffs[operation.path] = "binary generated content; review by SHA-256"
                    continue
            before: list[str] = []
            if operation.action in {Action.UPDATE_GENERATED, Action.REMOVE_OBSOLETE}:
                if not include_existing_content:
                    digest = operation.expected_hash or "unknown"
                    diffs[operation.path] = (
                        "existing repository content withheld from agent preview; "
                        f"expected SHA-256 {digest}; review exact diff in the trusted terminal"
                    )
                    continue
                path = assert_safe_target_path(self.plan.root, operation.path, allow_missing_leaf=False)
                descriptor: int | None = None
                try:
                    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    opened = os.fstat(descriptor)
                    if not stat.S_ISREG(opened.st_mode):
                        raise OSError("destination is not a regular file")
                    with os.fdopen(descriptor, "rb") as handle:
                        descriptor = None
                        current = handle.read()
                    if operation.expected_hash and sha256_bytes(current) != operation.expected_hash:
                        diffs[operation.path] = "destination changed after planning; review a new plan"
                        continue
                    before = current.decode("utf-8").splitlines(keepends=True)
                except (OSError, UnicodeDecodeError):
                    diffs[operation.path] = "existing content is not reviewable text; review by SHA-256"
                    continue
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
            diff = difflib.unified_diff(
                before,
                desired_text,
                fromfile=f"a/{operation.path}" if before else "/dev/null",
                tofile="/dev/null" if operation.action == Action.REMOVE_OBSOLETE else f"b/{operation.path}",
            )
            diffs[operation.path] = "".join(diff)
        return diffs

    def payload(
        self,
        *,
        status: str,
        applied: bool,
        warnings: list[str],
        errors: list[str] | None = None,
        rollback_status: str = "not-needed",
    ) -> dict[str, Any]:
        payload = self.artifact.to_dict()
        payload.update(
            {
                "status": status,
                "applied": applied,
                "warnings": warnings,
                "errors": errors or [],
                "diffs": self.review_diffs(),
            }
        )
        if status in {"applied", "apply-failed", "validation-failed"}:
            payload["result"] = ResultArtifact(
                target=str(self.plan.root),
                status=status,
                applied=applied,
                plan_id=self.plan_id,
                rollback_status=rollback_status,
                warnings=tuple(warnings),
                errors=tuple(errors or []),
            ).to_dict()
        return payload


_STORED_CONFIG_LIMIT = 1_048_576


def _stored_request(request: BootstrapRequest) -> BootstrapRequest | None:
    """The request recorded in ``.refract/config.json``, or None when it cannot be read.

    The file is repository content. It is used only to render what an earlier release
    would have generated, for comparison by hash; nothing from it is written.
    """
    try:
        path = assert_safe_target_path(request.target, ".refract/config.json", allow_missing_leaf=False)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return None
            raw = handle.read(_STORED_CONFIG_LIMIT + 1)
        if len(raw) > _STORED_CONFIG_LIMIT:
            return None
        config = json.loads(raw)
        project = config["project"]
        requested = config["features"]["requested"]
        commands = project.get("commands") or {}
        stored = BootstrapRequest(
            target=request.target,
            mode=request.mode,
            facts=ProjectFacts(
                name=project["name"],
                description=project.get("description") or "",
                languages=list(project.get("languages") or []),
                build_command=commands.get("build"),
                test_command=commands.get("test"),
                run_command=commands.get("run"),
                ticket_prefix=project.get("ticket_prefix"),
                components=list(project.get("components") or []),
            ),
            features=FeatureSelection(
                platforms=list(requested["platforms"]),
                **{
                    name: bool(requested.get(name, False))
                    for name in ("mcp", "agents", "github", "scheduled_audit", "hooks", "permissions")
                },
            ),
        )
        stored.facts.validate()
        stored.features.normalized_platforms()
        return stored
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def _earlier_generations(request: BootstrapRequest, version: str) -> Iterator[Mapping[str, GeneratedFile]]:
    """What the current templates render with an earlier version string.

    Rendered from the facts and features the project was generated with, when they can
    be read, and from the current request. The planner compares editable seeds with both.
    """
    stored = _stored_request(request)
    if stored is not None:
        yield render_project(stored, generator_version=version)
    yield render_project(request, generator_version=version)


def prepare_bootstrap(
    request: BootstrapRequest, *, remove_obsolete: bool = False, keep_existing: bool = False
) -> PreparedBootstrap:
    desired = render_project(request)
    errors = validate_rendered(desired)
    if errors:
        raise ValueError("rendered output is invalid: " + "; ".join(errors))
    plan = build_plan(
        request.target,
        desired,
        remove_obsolete=remove_obsolete,
        keep_existing=keep_existing,
        earlier_generations=lambda version: _earlier_generations(request, version),
    )
    document = plan_document(
        request, desired, plan, remove_obsolete=remove_obsolete, keep_existing=keep_existing
    )
    artifact = PlanArtifact.create(document)
    return PreparedBootstrap(
        request=request,
        desired=desired,
        plan=plan,
        document=document,
        plan_id=artifact.identifier,
        artifact=artifact,
        remove_obsolete=remove_obsolete,
        keep_existing=keep_existing,
    )


def apply_bootstrap(prepared: PreparedBootstrap, *, expected_plan_id: str | None = None) -> ResultArtifact:
    """Recompute trusted rendering and return a schema-versioned apply result."""
    expected = prepared.plan_id if expected_plan_id is None else expected_plan_id
    try:
        fresh = prepare_bootstrap(
            prepared.request,
            remove_obsolete=prepared.remove_obsolete,
            keep_existing=prepared.keep_existing,
        )
        if fresh.plan_id != expected:
            raise ValueError(f"plan identifier mismatch: expected {expected}, recomputed {fresh.plan_id}")
        apply_plan(
            fresh.plan,
            fresh.request.features.normalized_platforms(),
            remove_obsolete=fresh.remove_obsolete,
            validator=validate_target,
        )
    except (ApplyError, ValueError) as exc:
        result_plan_id = (
            expected
            if isinstance(expected, str)
            and len(expected) == 64
            and all(char in "0123456789abcdef" for char in expected)
            else prepared.plan_id
        )
        return ResultArtifact(
            target=str(prepared.plan.root),
            status="apply-failed",
            applied=False,
            plan_id=result_plan_id,
            rollback_status=getattr(exc, "rollback_status", "not-needed"),
            errors=(str(exc),),
        )
    return ResultArtifact(
        target=str(fresh.plan.root),
        status="applied",
        applied=True,
        plan_id=fresh.plan_id,
        rollback_status="not-needed",
    )


__all__ = [
    "InspectionArtifact",
    "PreparedBootstrap",
    "apply_bootstrap",
    "inspect_project",
    "prepare_bootstrap",
]
