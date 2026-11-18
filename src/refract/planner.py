from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .manifest import MANIFEST_PATH, Manifest, ManifestError, sha256_bytes, sha256_path
from .model import GeneratedFile
from .paths import UnsafePathError, assert_safe_root_parent, assert_safe_target_path, normalize_relative_path


class Action(str, Enum):
    CREATE = "CREATE"
    UPDATE_GENERATED = "UPDATE_GENERATED"
    NO_CHANGE = "NO_CHANGE"
    SKIP_UNMANAGED = "SKIP_UNMANAGED"
    SKIP_KEPT = "SKIP_KEPT"
    CONFLICT = "CONFLICT"
    REMOVE_OBSOLETE = "REMOVE_OBSOLETE"
    PRUNE_MISSING = "PRUNE_MISSING"
    MANIFEST_CREATE = "MANIFEST_CREATE"
    MANIFEST_UPDATE = "MANIFEST_UPDATE"


@dataclass(frozen=True)
class Operation:
    path: str
    action: Action
    generated: GeneratedFile | None = None
    detail: str = ""
    expected_hash: str | None = None
    expected_executable: bool | None = None


@dataclass
class Plan:
    root: Path
    operations: list[Operation]
    previous_manifest: Manifest
    manifest_hash: str | None
    root_existed: bool

    @property
    def conflicts(self) -> list[Operation]:
        return [operation for operation in self.operations if operation.action == Action.CONFLICT]

    @property
    def changes(self) -> list[Operation]:
        return [
            operation
            for operation in self.operations
            if operation.action in {
                Action.CREATE,
                Action.UPDATE_GENERATED,
                Action.REMOVE_OBSOLETE,
                Action.PRUNE_MISSING,
                Action.MANIFEST_CREATE,
                Action.MANIFEST_UPDATE,
            }
        ]

    def format(self) -> str:
        lines = [f"Plan for {self.root}:"]
        for operation in self.operations:
            suffix = f" — {operation.detail}" if operation.detail else ""
            lines.append(f"  {operation.action.value:18} {operation.path}{suffix}")
        counts: dict[Action, int] = {}
        for operation in self.operations:
            counts[operation.action] = counts.get(operation.action, 0) + 1
        summary = ", ".join(f"{action.value}={counts[action]}" for action in Action if action in counts)
        lines.append(f"Summary: {summary or 'no operations'}")
        return "\n".join(lines)


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _is_executable(path: Path) -> bool:
    return bool(os.lstat(path).st_mode & stat.S_IXUSR)


def skill_group(relative: str) -> str | None:
    """Skill name for every generated path that renders the same skill."""
    parts = relative.split("/")
    if len(parts) >= 4 and parts[1] == "skills" and parts[0] in {".agents", ".claude"}:
        return parts[2]
    if len(parts) == 3 and parts[:2] == [".opencode", "commands"] and parts[2].endswith(".md"):
        return parts[2][:-3]
    return None


# refract's own control surface: its scripts, configuration, and hooks are
# executed or trusted by generated hooks, so a repository-supplied copy must
# never be kept in place of the generated one.
PROTECTED_PREFIXES = (".refract/", ".githooks/")
PROTECTED_FILES = ("setup-hooks.sh",)


def is_protected(relative: str) -> bool:
    return relative.startswith(PROTECTED_PREFIXES) or relative in PROTECTED_FILES


def _skill_directory_group(relative: str) -> str | None:
    """Skill name for paths that define a skill (not OpenCode command wrappers)."""
    parts = relative.split("/")
    if len(parts) >= 4 and parts[1] == "skills" and parts[0] in {".agents", ".claude"}:
        return parts[2]
    return None


def _unmanaged_existing(root: Path, desired: dict[str, GeneratedFile], manifest: Manifest) -> set[str]:
    found: set[str] = set()
    for relative, generated in desired.items():
        if relative in manifest.files or is_protected(relative):
            continue
        try:
            path = assert_safe_target_path(root, relative)
            mode = os.lstat(path).st_mode
        except (UnsafePathError, OSError):
            continue
        if stat.S_ISREG(mode) and sha256_path(path) != sha256_bytes(generated.content):
            found.add(relative)
    return found


def build_plan(
    root: Path,
    desired: dict[str, GeneratedFile],
    *,
    remove_obsolete: bool = False,
    keep_existing: bool = False,
) -> Plan:
    """Plan an ownership-aware write.

    With ``keep_existing``, an unmanaged file at a generated path is kept as
    user-owned (SKIP_UNMANAGED) instead of blocking the apply as a conflict.
    Kept skills stay consistent across platforms: the other generated copies
    of a kept skill are not created (SKIP_KEPT), so every agent sees one
    version. Modified refract-owned files, symlinks, and non-regular files
    still conflict.
    """
    root = Path(os.path.normpath(str(root.expanduser().absolute())))
    operations: list[Operation] = []
    root_existed = root.exists() or root.is_symlink()

    try:
        assert_safe_root_parent(root)
    except UnsafePathError as exc:
        empty = Manifest()
        return Plan(root, [Operation(".", Action.CONFLICT, detail=str(exc))], empty, None, root_existed)

    normalized_desired: dict[str, GeneratedFile] = {}
    for relative, generated in desired.items():
        try:
            normalized = normalize_relative_path(relative)
        except UnsafePathError as exc:
            operations.append(Operation(str(relative), Action.CONFLICT, generated, str(exc)))
            continue
        if normalized == MANIFEST_PATH:
            operations.append(Operation(normalized, Action.CONFLICT, generated, "manifest is managed internally"))
            continue
        normalized_desired[normalized] = generated

    manifest_path = root / MANIFEST_PATH
    manifest_hash: str | None = None
    manifest = Manifest()
    manifest_metadata_changed = False
    manifest_error: str | None = None
    if _exists(manifest_path):
        try:
            assert_safe_target_path(root, MANIFEST_PATH, allow_missing_leaf=False)
            if not stat.S_ISREG(os.lstat(manifest_path).st_mode):
                raise ManifestError("ownership manifest must be a regular file")
            manifest_hash = sha256_path(manifest_path)
            manifest = Manifest.load(root)
        except (UnsafePathError, ManifestError, OSError) as exc:
            manifest_error = str(exc)
            operations.append(Operation(MANIFEST_PATH, Action.CONFLICT, detail=manifest_error))

    kept: set[str] = set()
    if keep_existing and not manifest_error:
        kept = _unmanaged_existing(root, normalized_desired, manifest)
        kept_skills = {group for group in map(_skill_directory_group, kept) if group}
        for relative in sorted(normalized_desired):
            if relative in kept or skill_group(relative) not in kept_skills or relative in manifest.files:
                continue
            if not _exists(root / relative):
                operations.append(
                    Operation(
                        relative,
                        Action.SKIP_KEPT,
                        normalized_desired.pop(relative),
                        f"not generated: the project keeps its own '{skill_group(relative)}' skill",
                    )
                )

    for relative, generated in sorted(normalized_desired.items()):
        try:
            path = assert_safe_target_path(root, relative)
        except UnsafePathError as exc:
            operations.append(Operation(relative, Action.CONFLICT, generated, str(exc)))
            continue
        previous = manifest.files.get(relative)
        if not _exists(path):
            operations.append(Operation(relative, Action.CREATE, generated))
            continue
        try:
            destination_mode = os.lstat(path).st_mode
        except OSError as exc:
            operations.append(Operation(relative, Action.CONFLICT, generated, f"cannot inspect destination: {exc}"))
            continue
        if stat.S_ISLNK(destination_mode):
            operations.append(Operation(relative, Action.CONFLICT, generated, "symlink destination is unmanaged"))
            continue
        if not stat.S_ISREG(destination_mode):
            operations.append(Operation(relative, Action.CONFLICT, generated, "destination is not a regular file"))
            continue
        try:
            current_hash = sha256_path(path)
        except OSError as exc:
            operations.append(Operation(relative, Action.CONFLICT, generated, f"cannot read destination: {exc}"))
            continue
        desired_hash = sha256_bytes(generated.content)
        if previous and bool(previous.get("mutable", False)) != generated.mutable:
            manifest_metadata_changed = True
        if (
            previous
            and previous.get("mutable", False)
            and current_hash != previous.get("sha256")
        ):
            seed_changed = desired_hash != previous.get("sha256")
            operations.append(
                Operation(
                    relative,
                    Action.NO_CHANGE,
                    generated,
                    "mutable generated seed was customized and is preserved"
                    + ("; the generated seed changed since it was customized, review the new version manually" if seed_changed else ""),
                    expected_hash=current_hash,
                    expected_executable=_is_executable(path),
                )
            )
            continue
        if current_hash == desired_hash:
            if previous:
                if _is_executable(path) != generated.executable:
                    operations.append(
                        Operation(
                            relative,
                            Action.UPDATE_GENERATED,
                            generated,
                            "executable mode drift",
                            expected_hash=current_hash,
                            expected_executable=_is_executable(path),
                        )
                    )
                else:
                    operations.append(
                        Operation(
                            relative,
                            Action.NO_CHANGE,
                            generated,
                            "owned generated file",
                            expected_hash=current_hash,
                            expected_executable=_is_executable(path),
                        )
                    )
            else:
                operations.append(
                    Operation(
                        relative,
                        Action.SKIP_UNMANAGED,
                        generated,
                        "identical unmanaged file remains user-owned",
                        expected_hash=current_hash,
                        expected_executable=_is_executable(path),
                    )
                )
            continue
        if previous:
            if current_hash == previous.get("sha256") and _is_executable(path) == previous.get("executable"):
                operations.append(
                    Operation(
                        relative,
                        Action.UPDATE_GENERATED,
                        generated,
                        expected_hash=current_hash,
                        expected_executable=_is_executable(path),
                    )
                )
            else:
                operations.append(Operation(relative, Action.CONFLICT, generated, "generated file content or mode was modified"))
        elif relative in kept:
            operations.append(
                Operation(
                    relative,
                    Action.SKIP_UNMANAGED,
                    generated,
                    "existing unmanaged file kept as project-owned (--keep-existing)",
                    expected_hash=current_hash,
                    expected_executable=_is_executable(path),
                )
            )
        elif is_protected(relative):
            operations.append(
                Operation(
                    relative,
                    Action.CONFLICT,
                    generated,
                    "unmanaged destination exists at a refract control path; move it aside (cannot be kept)",
                )
            )
        else:
            operations.append(
                Operation(
                    relative,
                    Action.CONFLICT,
                    generated,
                    "unmanaged destination exists (use --keep-existing to keep it)",
                )
            )

    if not manifest_error:
        for relative in sorted(set(manifest.files) - set(normalized_desired)):
            try:
                path = assert_safe_target_path(root, relative)
            except UnsafePathError as exc:
                operations.append(Operation(relative, Action.CONFLICT, None, str(exc)))
                continue
            if not _exists(path):
                operations.append(Operation(relative, Action.PRUNE_MISSING, None, "remove stale manifest claim"))
                continue
            previous = manifest.files[relative]
            if path.is_file() and not path.is_symlink() and sha256_path(path) == previous.get("sha256") and _is_executable(path) == previous.get("executable"):
                operations.append(
                    Operation(
                        relative,
                        Action.REMOVE_OBSOLETE,
                        None,
                        "requires --remove-obsolete",
                        expected_hash=previous.get("sha256"),
                        expected_executable=previous.get("executable"),
                    )
                )
            else:
                operations.append(Operation(relative, Action.CONFLICT, None, "obsolete generated path was modified"))

    content_changes = any(
        operation.action in {
            Action.CREATE,
            Action.UPDATE_GENERATED,
            Action.PRUNE_MISSING,
        }
        for operation in operations
    ) or manifest_metadata_changed or (
        remove_obsolete
        and any(operation.action == Action.REMOVE_OBSOLETE for operation in operations)
    )
    if manifest_error:
        pass
    elif manifest_hash is None:
        operations.append(Operation(MANIFEST_PATH, Action.MANIFEST_CREATE))
    elif content_changes:
        operations.append(Operation(MANIFEST_PATH, Action.MANIFEST_UPDATE))
    else:
        operations.append(Operation(MANIFEST_PATH, Action.NO_CHANGE, detail="owned manifest"))

    return Plan(
        root=root,
        operations=operations,
        previous_manifest=manifest,
        manifest_hash=manifest_hash,
        root_existed=root_existed,
    )
