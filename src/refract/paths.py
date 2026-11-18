from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath


class UnsafePathError(ValueError):
    pass


def normalize_relative_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(unicodedata.category(char)[0] == "C" or unicodedata.category(char) in {"Zl", "Zp"} for char in value)
    ):
        raise UnsafePathError(f"unsafe generated path: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise UnsafePathError(f"unsafe generated path: {value!r}")
    normalized = pure.as_posix()
    if normalized != value:
        raise UnsafePathError(f"non-normalized generated path: {value!r}")
    return normalized


def assert_safe_target_path(
    root: Path,
    relative: str,
    *,
    allow_missing_leaf: bool = True,
    allow_leaf_symlink: bool = False,
) -> Path:
    relative = normalize_relative_path(relative)
    root = Path(os.path.normpath(str(root.expanduser().absolute())))
    assert_safe_root_parent(root)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"path escapes target: {relative}") from exc

    current = root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        current = current / part
        is_leaf = index == len(parts) - 1
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            if is_leaf and not allow_missing_leaf:
                raise UnsafePathError(f"required path is missing: {relative}")
            continue
        except OSError as exc:
            raise UnsafePathError(f"cannot inspect {current}: {exc}") from exc
        if stat.S_ISLNK(mode):
            if is_leaf and allow_leaf_symlink:
                continue
            raise UnsafePathError(f"symlinked path component is not allowed: {current}")
        if not is_leaf and not stat.S_ISDIR(mode):
            raise UnsafePathError(f"non-directory path component: {current}")
    return candidate


def assert_safe_root_parent(root: Path) -> None:
    """Reject symlinks and non-directories in every existing target component."""
    absolute = Path(os.path.normpath(str(root.expanduser().absolute())))
    anchor = Path(absolute.anchor)
    current = anchor
    relative_parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for index, part in enumerate(relative_parts):
        current = current / part
        is_root = index == len(relative_parts) - 1
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafePathError(f"cannot inspect target ancestor {current}: {exc}") from exc
        if stat.S_ISLNK(mode):
            # macOS and some Unix layouts use fixed top-level aliases such as
            # /var -> /private/var. Treat only those root-owned namespace aliases
            # as part of the filesystem anchor; reject every deeper symlink.
            if current.parent == anchor and not is_root:
                continue
            raise UnsafePathError(f"target ancestor is a symlink: {current}")
        if not is_root and not stat.S_ISDIR(mode):
            raise UnsafePathError(f"target ancestor is not a directory: {current}")
        if is_root and not stat.S_ISDIR(mode):
            raise UnsafePathError(f"target root is not a directory: {current}")


def project_scope_problems(target: Path, *, max_depth: int = 2) -> list[str]:
    """Explain why a target does not look like a single project root.

    refract writes project-scoped agent configuration. Running it on a home
    directory or on a folder that groups several repositories makes every
    nested project (and some agent CLIs' user-scope discovery) inherit one
    project's skills, hooks, and policies.
    """
    resolved = Path(os.path.normpath(str(target.expanduser().absolute())))
    problems: list[str] = []
    if resolved == Path(resolved.anchor):
        problems.append(f"{resolved} is a filesystem root, not a project")
    try:
        is_home = resolved == Path.home().absolute() or resolved.resolve() == Path.home().resolve()
    except (OSError, RuntimeError):
        is_home = False
    if is_home:
        problems.append(f"{resolved} is the home directory, not a project")
    if not _is_dir(resolved) or _exists(resolved / ".git"):
        return problems
    nested: list[str] = []
    frontier = [resolved]
    for _depth in range(max_depth):
        next_frontier: list[Path] = []
        for directory in frontier:
            try:
                children = sorted(child for child in directory.iterdir() if _is_dir(child) and not child.is_symlink())
            except OSError:
                continue
            for child in children:
                if child.name.startswith(".") or child.name in {"node_modules", "vendor"}:
                    continue
                if _exists(child / ".git"):
                    nested.append(child.relative_to(resolved).as_posix())
                else:
                    next_frontier.append(child)
        frontier = next_frontier
    if nested:
        shown = ", ".join(nested[:3]) + (" ..." if len(nested) > 3 else "")
        problems.append(
            f"{resolved} is not a git repository but contains nested repositories ({shown}); "
            "run refract inside each project instead"
        )
    return problems


def _exists(path: Path) -> bool:
    # Python < 3.13 re-raises PermissionError from Path.exists(); an unreadable
    # directory is simply not evidence of a nested repository.
    try:
        return path.exists()
    except OSError:
        return False


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False
