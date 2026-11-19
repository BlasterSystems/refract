from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .paths import UnsafePathError, normalize_relative_path

MANIFEST_PATH = ".refract/manifest.json"
MANIFEST_SCHEMA = "refract-manifest/v1"
# Value of the manifest's "seed_hashes" key. It states that the hash recorded for an
# editable seed is the hash of a version refract generated, never of an edited file.
# Manifests written before this key existed may hold an edited file's hash instead.
SEED_HASHES_GENERATED = "generated"
# Recorded for a preserved seed when the generated version it started from is unknown.
# No file hashes to this value, so such a seed is never mistaken for an unedited one.
UNKNOWN_SEED_BASE = "0" * 64


class ManifestError(ValueError):
    pass


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def preserved_seed_entry(previous: Mapping[str, Any], base: str) -> dict[str, Any]:
    """Manifest entry for an editable seed that is kept as the project left it.

    ``base`` is the hash of the generated version the content started from, or
    ``UNKNOWN_SEED_BASE``. It is never the hash of the file on disk: recording that would
    make the file look unedited on the next run, and a later change would overwrite it.
    """
    return {"sha256": base, "executable": bool(previous.get("executable", False)), "mutable": True}


@dataclass
class Manifest:
    generator_version: str = __version__
    platforms: list[str] = field(default_factory=list)
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    updated_at: str = ""
    schema: str = MANIFEST_SCHEMA
    tracks_generated_seeds: bool = True

    @classmethod
    def load(cls, root: Path) -> "Manifest":
        path = root / MANIFEST_PATH
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"invalid ownership manifest: {exc}") from exc
        if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA:
            raise ManifestError("existing .refract/manifest.json is not an owned v1 manifest")
        raw_files = data.get("files")
        if not isinstance(raw_files, dict):
            raise ManifestError("manifest files must be an object")
        files: dict[str, dict[str, Any]] = {}
        for relative, metadata in raw_files.items():
            try:
                normalized = normalize_relative_path(relative)
            except UnsafePathError as exc:
                raise ManifestError(str(exc)) from exc
            if normalized == MANIFEST_PATH:
                raise ManifestError("manifest must not claim ownership of itself")
            if not isinstance(metadata, dict):
                raise ManifestError(f"manifest metadata must be an object: {relative}")
            digest = metadata.get("sha256")
            executable = metadata.get("executable")
            mutable = metadata.get("mutable", False)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or not isinstance(executable, bool)
                or not isinstance(mutable, bool)
            ):
                raise ManifestError(f"invalid manifest metadata: {relative}")
            files[normalized] = {
                "sha256": digest,
                "executable": executable,
                "mutable": mutable,
            }
        platforms = data.get("platforms", [])
        if not isinstance(platforms, list) or not all(isinstance(item, str) for item in platforms):
            raise ManifestError("manifest platforms must be an array of strings")
        return cls(
            generator_version=str(data.get("generator_version", "unknown")),
            platforms=platforms,
            files=files,
            updated_at=str(data.get("updated_at", "")),
            schema=MANIFEST_SCHEMA,
            tracks_generated_seeds=data.get("seed_hashes") == SEED_HASHES_GENERATED,
        )

    def to_bytes(self) -> bytes:
        self.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        data = {
            "schema": MANIFEST_SCHEMA,
            "generator_version": self.generator_version,
            "platforms": self.platforms,
            "updated_at": self.updated_at,
            "files": dict(sorted(self.files.items())),
        }
        if self.tracks_generated_seeds:
            data["seed_hashes"] = SEED_HASHES_GENERATED
        return (json.dumps(data, indent=2, sort_keys=False) + "\n").encode("utf-8")
