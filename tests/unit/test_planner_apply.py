from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from refract.apply import ApplyError, apply_plan
from refract.facade import _stored_request, apply_bootstrap, prepare_bootstrap
from refract.manifest import UNKNOWN_SEED_BASE, Manifest, sha256_bytes, sha256_path
from refract.model import SEED_PATHS, SUPPORTED_PLATFORMS, BootstrapRequest, GeneratedFile
from refract.planner import _RELEASE_VERSION, Action, build_plan
from refract.renderer import render_project
from tests.helpers import request


class PlannerApplyTests(unittest.TestCase):
    def test_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)
            first = build_plan(root, render_project(req))
            self.assertTrue(
                all(op.action in {Action.CREATE, Action.MANIFEST_CREATE} for op in first.operations)
            )
            apply_plan(first, req.features.normalized_platforms())
            second = build_plan(root, render_project(req))
            self.assertFalse(second.changes)
            self.assertFalse(second.conflicts)
            manifest_path = root / ".refract/manifest.json"
            before = manifest_path.read_bytes()
            apply_plan(second, req.features.normalized_platforms())
            self.assertEqual(before, manifest_path.read_bytes())

    def test_unmanaged_file_is_conflict_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = root / "AGENTS.md"
            agents.write_text("user owned\n", encoding="utf-8")
            original = sha256_path(agents)
            plan = build_plan(root, render_project(request(root)))
            self.assertTrue(any(op.path == "AGENTS.md" and op.action == Action.CONFLICT for op in plan.operations))
            with self.assertRaises(ApplyError):
                apply_plan(plan, ["claude"])
            self.assertEqual(original, sha256_path(agents))

    def test_user_modified_generated_file_becomes_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)
            apply_plan(build_plan(root, render_project(req)), req.features.normalized_platforms())
            (root / ".refract/bin/validate").write_text("modified\n", encoding="utf-8")
            plan = build_plan(root, render_project(req))
            self.assertTrue(
                any(
                    op.path == ".refract/bin/validate" and op.action == Action.CONFLICT
                    for op in plan.operations
                )
            )

    def test_apply_failure_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)
            plan = build_plan(root, render_project(req))
            real_link = os.link
            calls = 0

            def fail_second(source, destination, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected failure")
                return real_link(source, destination, **kwargs)

            with mock.patch("refract.apply.os.link", side_effect=fail_second):
                with self.assertRaises(ApplyError):
                    apply_plan(plan, req.features.normalized_platforms())
            self.assertFalse(root.exists())

    def test_mode_drift_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)
            apply_plan(build_plan(root, render_project(req)), req.features.normalized_platforms())
            validator = root / ".refract/bin/validate"
            validator.chmod(0o644)
            plan = build_plan(root, render_project(req))
            operation = next(op for op in plan.operations if op.path == ".refract/bin/validate")
            self.assertEqual(Action.UPDATE_GENERATED, operation.action)
            apply_plan(plan, req.features.normalized_platforms())
            self.assertTrue(os.access(validator, os.X_OK))

    def test_stale_no_change_plan_never_rebaselines_modified_owned_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root)
            apply_plan(build_plan(root, render_project(req)), req.features.normalized_platforms())
            plan = build_plan(root, render_project(req))
            validator = root / ".refract/bin/validate"
            validator.write_text("changed after planning\n", encoding="utf-8")
            with self.assertRaises(ApplyError):
                apply_plan(plan, req.features.normalized_platforms())
            self.assertEqual("changed after planning\n", validator.read_text(encoding="utf-8"))

    def test_stale_skip_unmanaged_plan_never_accepts_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root)
            desired = render_project(req)
            (root / "AGENTS.md").write_bytes(desired["AGENTS.md"].content)
            plan = build_plan(root, desired)
            (root / "AGENTS.md").write_text("changed after planning\n", encoding="utf-8")
            with self.assertRaises(ApplyError):
                apply_plan(plan, req.features.normalized_platforms())
            self.assertFalse((root / ".refract/manifest.json").exists())

    def test_stale_create_plan_never_overwrites_new_unmanaged_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root)
            plan = build_plan(root, render_project(req))
            agents = root / "AGENTS.md"
            agents.write_text("appeared after planning\n", encoding="utf-8")
            with self.assertRaises(ApplyError):
                apply_plan(plan, req.features.normalized_platforms())
            self.assertEqual("appeared after planning\n", agents.read_text(encoding="utf-8"))

    def test_symlinked_parent_is_conflict_and_external_files_are_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external_directory:
            root = Path(directory)
            external = Path(external_directory)
            victim = external / "ARCHITECTURE.md"
            victim.write_text("external\n", encoding="utf-8")
            (root / "docs").symlink_to(external, target_is_directory=True)
            plan = build_plan(root, render_project(request(root)))
            self.assertTrue(any(op.action == Action.CONFLICT and op.path.startswith("docs/") for op in plan.operations))
            with self.assertRaises(ApplyError):
                apply_plan(plan, ["pi"])
            self.assertEqual("external\n", victim.read_text(encoding="utf-8"))

    def test_symlinked_target_ancestor_is_conflict_and_external_tree_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external_directory:
            base = Path(directory)
            external_root = Path(external_directory) / "nested/project"
            external_root.mkdir(parents=True)
            alias = base / "alias"
            alias.symlink_to(Path(external_directory), target_is_directory=True)
            root = alias / "nested/project"
            plan = build_plan(root, render_project(request(root)))
            self.assertTrue(plan.conflicts)
            self.assertIn("target ancestor is a symlink", plan.conflicts[0].detail)
            with self.assertRaises(ApplyError):
                apply_plan(plan, ["pi"])
            self.assertEqual([], list(external_root.iterdir()))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO support required")
    def test_special_destination_and_manifest_are_conflicts_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.mkfifo(root / "AGENTS.md")
            plan = build_plan(root, render_project(request(root)))
            operation = next(op for op in plan.operations if op.path == "AGENTS.md")
            self.assertEqual(Action.CONFLICT, operation.action)
            self.assertIn("not a regular file", operation.detail)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".refract").mkdir()
            os.mkfifo(root / ".refract/manifest.json")
            plan = build_plan(root, render_project(request(root)))
            operation = next(op for op in plan.operations if op.path == ".refract/manifest.json")
            self.assertEqual(Action.CONFLICT, operation.action)
            self.assertIn("regular file", operation.detail)

    def test_malicious_manifest_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".refract").mkdir()
            manifest = {
                "schema": "refract-manifest/v1",
                "generator_version": "0.1.0",
                "platforms": ["pi"],
                "files": {"../victim": {"sha256": "0" * 64, "executable": False}},
            }
            (root / ".refract/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            plan = build_plan(root, render_project(request(root)))
            self.assertTrue(any(op.path == ".refract/manifest.json" and op.action == Action.CONFLICT for op in plan.operations))

    def test_unmanaged_manifest_is_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".refract").mkdir()
            original = '{"files": {}}\n'
            path = root / ".refract/manifest.json"
            path.write_text(original, encoding="utf-8")
            plan = build_plan(root, render_project(request(root)))
            self.assertTrue(plan.conflicts)
            with self.assertRaises(ApplyError):
                apply_plan(plan, ["pi"])
            self.assertEqual(original, path.read_text(encoding="utf-8"))

    def test_rollback_removes_created_directories_in_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root)
            plan = build_plan(root, render_project(req))
            real_link = os.link
            calls = 0

            def fail_second(source, destination, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected failure")
                return real_link(source, destination, **kwargs)

            with mock.patch("refract.apply.os.link", side_effect=fail_second):
                with self.assertRaises(ApplyError):
                    apply_plan(plan, req.features.normalized_platforms())
            self.assertEqual([], list(root.iterdir()))

    def test_obsolete_files_require_explicit_removal_and_manifest_is_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"owned.txt": GeneratedFile.text("owned.txt", "owned")}
            apply_plan(build_plan(root, desired), ["pi"])
            keep_plan = build_plan(root, {})
            self.assertTrue(any(op.action == Action.REMOVE_OBSOLETE for op in keep_plan.operations))
            before = (root / ".refract/manifest.json").read_bytes()
            apply_plan(keep_plan, ["pi"], remove_obsolete=False)
            self.assertTrue((root / "owned.txt").exists())
            self.assertEqual(before, (root / ".refract/manifest.json").read_bytes())
            remove_plan = build_plan(root, {}, remove_obsolete=True)
            apply_plan(remove_plan, ["pi"], remove_obsolete=True)
            self.assertFalse((root / "owned.txt").exists())
            manifest = Manifest.load(root)
            self.assertNotIn("owned.txt", manifest.files)

    @staticmethod
    def _operations(plan: object) -> dict[str, object]:
        return {operation.path: operation for operation in plan.operations}  # type: ignore[attr-defined]

    @staticmethod
    def _as_older_manifest(root: Path, *, version: str = "0.0.1", **hashes: str) -> None:
        """Rewrite the manifest as a release without seed-hash tracking wrote it."""
        path = root / ".refract/manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("seed_hashes")
        data["generator_version"] = version
        for relative, digest in hashes.items():
            data["files"][relative]["sha256"] = digest
        path.write_text(json.dumps(data), encoding="utf-8")

    # Editable seeds, ADR-0013. One test per state: manifest with or without seed tracking,
    # content shown to be generated or not, and the path still generated, obsolete, or
    # now fully generated.

    PULL_REQUEST = ".github/PULL_REQUEST_TEMPLATE.md"
    WORKFLOW = ".github/workflows/docs-check.yml"

    def _project(self, root: Path, *, version: str | None = None, github: bool = False) -> BootstrapRequest:
        req = request(root, github=github)
        desired = render_project(req) if version is None else render_project(req, generator_version=version)
        apply_plan(build_plan(root, desired), req.features.normalized_platforms())
        return req

    @staticmethod
    def _earlier(req: BootstrapRequest):  # type: ignore[no-untyped-def]
        return lambda version: [render_project(req, generator_version=version)]

    def test_tracked_edited_seed_survives_reruns_that_rewrite_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self._project(root)
            self.assertIn('"seed_hashes": "generated"', (root / ".refract/manifest.json").read_text(encoding="utf-8"))
            seed = root / "AGENTS.md"
            generated_base = Manifest.load(root).files["AGENTS.md"]
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            edited = seed.read_bytes()
            runs = (("second description", True), ("third description", True), ("third description", False))
            for description, plan_has_changes in runs:
                req = request(root)
                req.facts.description = description
                plan = build_plan(root, render_project(req))
                operation = self._operations(plan)["AGENTS.md"]
                self.assertEqual(Action.NO_CHANGE, operation.action, description)
                self.assertIn("customized and is preserved", operation.detail)
                self.assertIn("review the new version manually", operation.detail)
                self.assertEqual(plan_has_changes, bool(plan.changes))
                apply_plan(plan, req.features.normalized_platforms())
                self.assertEqual(edited, seed.read_bytes(), description)
                # The manifest keeps the generated version the edits started from.
                self.assertEqual(generated_base, Manifest.load(root).files["AGENTS.md"], description)

    def test_tracked_seed_matching_the_generated_version_is_tracked_as_generated_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self._project(root)
            seed = root / "AGENTS.md"
            seed.write_text("edited\n", encoding="utf-8")
            second = request(root)
            second.facts.description = "second description"
            desired = render_project(second)
            seed.write_bytes(desired["AGENTS.md"].content)
            plan = build_plan(root, desired)
            operation = self._operations(plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, operation.action)
            self.assertIsNone(operation.seed_base)
            self.assertEqual("owned generated file", operation.detail)
            self.assertEqual(Action.MANIFEST_UPDATE, self._operations(plan)[".refract/manifest.json"].action)
            apply_plan(plan, second.features.normalized_platforms())
            third = request(root)
            third.facts.description = "third description"
            self.assertEqual(
                Action.UPDATE_GENERATED, self._operations(build_plan(root, render_project(third)))["AGENTS.md"].action
            )

    def test_tracked_obsolete_seed_is_removed_when_unedited_and_kept_when_edited(self) -> None:
        for edit_seed in (False, True):
            with self.subTest(edited=edit_seed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                self._project(root, github=True)
                template = root / self.PULL_REQUEST
                if edit_seed:
                    template.write_text("ours\n", encoding="utf-8")
                    # A re-run that rewrites the manifest must not make the edit look generated.
                    changed = request(root, github=True)
                    changed.facts.description = "second description"
                    apply_plan(build_plan(root, render_project(changed)), changed.features.normalized_platforms())
                without = request(root)
                without.facts.description = "second description" if edit_seed else without.facts.description
                plan = build_plan(root, render_project(without), remove_obsolete=True)
                self.assertEqual([], plan.conflicts)
                operations = self._operations(plan)
                self.assertEqual(Action.REMOVE_OBSOLETE, operations[self.WORKFLOW].action)
                expected = Action.NO_CHANGE if edit_seed else Action.REMOVE_OBSOLETE
                self.assertEqual(expected, operations[self.PULL_REQUEST].action)
                apply_plan(plan, without.features.normalized_platforms(), remove_obsolete=True)
                self.assertFalse((root / self.WORKFLOW).exists())
                self.assertEqual(edit_seed, template.exists())
                if edit_seed:
                    self.assertIn("kept because it may hold project edits", operations[self.PULL_REQUEST].detail)
                    self.assertEqual("ours\n", template.read_text(encoding="utf-8"))
                    # The claim stays, so later runs keep the file without changes or conflicts.
                    self.assertIn(self.PULL_REQUEST, Manifest.load(root).files)
                    again = build_plan(root, render_project(without), remove_obsolete=True)
                    self.assertFalse(again.changes)
                    self.assertFalse(again.conflicts)
                    # Deleting the file is how the project drops it.
                    template.unlink()
                    dropped = self._operations(build_plan(root, render_project(without)))[self.PULL_REQUEST]
                    self.assertEqual(Action.PRUNE_MISSING, dropped.action)

    def test_untracked_seed_that_is_not_shown_to_be_generated_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            seed = root / "AGENTS.md"
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            edited = seed.read_bytes()
            # The older release recorded the edited content as if it had generated it.
            self._as_older_manifest(root, **{"AGENTS.md": sha256_bytes(edited)})
            plan = build_plan(root, render_project(req), earlier_generations=self._earlier(req))
            operation = self._operations(plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, operation.action)
            self.assertIn("no record of the generated version", operation.detail)
            self.assertEqual(Action.UPDATE_GENERATED, self._operations(plan)[".refract/config.json"].action)
            apply_plan(plan, req.features.normalized_platforms())
            self.assertEqual(edited, seed.read_bytes())
            manifest = Manifest.load(root)
            self.assertTrue(manifest.tracks_generated_seeds)
            self.assertEqual(UNKNOWN_SEED_BASE, manifest.files["AGENTS.md"]["sha256"])
            # The state and its way out stay visible on every later run.
            again = build_plan(root, render_project(req), earlier_generations=self._earlier(req))
            self.assertFalse(again.changes)
            self.assertIn("delete it and re-run", self._operations(again)["AGENTS.md"].detail)
            apply_plan(again, req.features.normalized_platforms())
            self.assertEqual(edited, seed.read_bytes())
            # Deleting the file is how the project takes the generated version.
            seed.unlink()
            recreated = build_plan(root, render_project(req), earlier_generations=self._earlier(req))
            self.assertEqual(Action.CREATE, self._operations(recreated)["AGENTS.md"].action)
            apply_plan(recreated, req.features.normalized_platforms())
            self.assertFalse(build_plan(root, render_project(req)).changes)

    def test_untracked_seed_shown_to_be_generated_is_updated_whatever_hash_was_recorded(self) -> None:
        for recorded in (None, "a" * 64):
            with self.subTest(recorded=recorded), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                req = self._project(root, version="0.0.1")
                # An edit recorded by the older release and later reverted leaves another hash.
                self._as_older_manifest(root, **({"AGENTS.md": recorded} if recorded else {}))
                plan = build_plan(root, render_project(req), earlier_generations=self._earlier(req))
                self.assertEqual([], plan.conflicts)
                self.assertEqual(Action.UPDATE_GENERATED, self._operations(plan)["AGENTS.md"].action)
                apply_plan(plan, req.features.normalized_platforms())
                self.assertFalse(build_plan(root, render_project(req)).changes)

    def test_untracked_unedited_seed_is_preserved_without_a_matching_earlier_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            self._as_older_manifest(root)
            # A changed template or fact, or no renderer: the content cannot be shown to be generated.
            for unproven_generation in (None, lambda version: []):
                operation = self._operations(
                    build_plan(root, render_project(req), earlier_generations=unproven_generation)
                )["AGENTS.md"]
                self.assertEqual(Action.NO_CHANGE, operation.action)
                self.assertEqual(UNKNOWN_SEED_BASE, operation.seed_base)

    def test_untracked_obsolete_seed_is_kept_and_never_blocks_or_is_removed(self) -> None:
        for remove_obsolete in (False, True):
            with self.subTest(remove_obsolete=remove_obsolete), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                self._project(root, github=True)
                self._as_older_manifest(root, version=Manifest().generator_version)
                without = request(root)
                plan = build_plan(root, render_project(without), remove_obsolete=remove_obsolete)
                self.assertEqual([], plan.conflicts)
                operations = self._operations(plan)
                self.assertEqual(Action.NO_CHANGE, operations[self.PULL_REQUEST].action)
                self.assertEqual(UNKNOWN_SEED_BASE, operations[self.PULL_REQUEST].seed_base)
                self.assertEqual(Action.REMOVE_OBSOLETE, operations[self.WORKFLOW].action)
                apply_plan(plan, without.features.normalized_platforms(), remove_obsolete=remove_obsolete)
                self.assertTrue((root / self.PULL_REQUEST).is_file())
                self.assertEqual(not remove_obsolete, (root / self.WORKFLOW).exists())
                manifest = Manifest.load(root)
                self.assertTrue(manifest.tracks_generated_seeds)
                self.assertEqual(UNKNOWN_SEED_BASE, manifest.files[self.PULL_REQUEST]["sha256"])
                again = build_plan(root, render_project(without), remove_obsolete=remove_obsolete)
                # Only the still-pending removal of the generated workflow remains.
                self.assertEqual(
                    [] if remove_obsolete else [self.WORKFLOW], [operation.path for operation in again.changes]
                )
                self.assertFalse(again.conflicts)
                self.assertEqual(Action.NO_CHANGE, self._operations(again)[self.PULL_REQUEST].action)

    def test_untracked_manifest_is_rewritten_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root)
            self._as_older_manifest(root, version=Manifest().generator_version)
            plan = build_plan(root, render_project(req))
            self.assertEqual([".refract/manifest.json"], [operation.path for operation in plan.changes])
            apply_plan(plan, req.features.normalized_platforms())
            self.assertFalse(build_plan(root, render_project(req)).changes)

    def test_untracked_seed_that_became_fully_generated_updates_only_when_shown_generated(self) -> None:
        for edit_seed in (False, True):
            with self.subTest(edited=edit_seed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                req = self._project(root, version="0.0.1")
                seed = root / "AGENTS.md"
                if edit_seed:
                    seed.write_text("our edits\n", encoding="utf-8")
                self._as_older_manifest(root, **{"AGENTS.md": sha256_path(seed)})
                desired = render_project(req)
                desired["AGENTS.md"] = GeneratedFile.text("AGENTS.md", "now fully generated\n")
                self.assertFalse(desired["AGENTS.md"].mutable)
                operation = self._operations(build_plan(root, desired, earlier_generations=self._earlier(req)))[
                    "AGENTS.md"
                ]
                self.assertEqual(Action.CONFLICT if edit_seed else Action.UPDATE_GENERATED, operation.action)

    def test_untracked_manifest_cannot_claim_a_control_path_as_a_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            data = json.loads((root / ".refract/manifest.json").read_text(encoding="utf-8"))
            data["files"][".refract/config.json"]["mutable"] = True
            (root / ".refract/manifest.json").write_text(json.dumps(data), encoding="utf-8")
            self._as_older_manifest(root)
            # No earlier rendering is offered, so a seed claim would turn this into a conflict.
            plan = build_plan(root, render_project(req))
            self.assertEqual([], plan.conflicts)
            self.assertEqual(Action.UPDATE_GENERATED, self._operations(plan)[".refract/config.json"].action)

    def test_seed_paths_list_matches_what_the_renderer_marks_editable(self) -> None:
        everything = request(Path("unused"), platforms=list(SUPPORTED_PLATFORMS), mcp=True, agents=True,
                             github=True, scheduled_audit=True, hooks=True, permissions=True)
        editable = {path for path, generated in render_project(everything).items() if generated.mutable}
        # A subset, not equality: a path that stops being a seed must stay listed.
        self.assertLessEqual(editable, SEED_PATHS)

    def test_tracked_unedited_seed_with_a_changed_mode_is_updated_not_conflicted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self._project(root)
            seed = root / "AGENTS.md"
            seed.chmod(0o755)
            second = request(root)
            second.facts.description = "second description"
            plan = build_plan(root, render_project(second))
            self.assertEqual([], plan.conflicts)
            self.assertEqual(Action.UPDATE_GENERATED, self._operations(plan)["AGENTS.md"].action)
            apply_plan(plan, second.features.normalized_platforms())
            self.assertFalse(os.access(seed, os.X_OK))
            self.assertFalse(build_plan(root, render_project(second)).changes)

    def test_manifest_cannot_claim_an_obsolete_generated_file_as_a_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self._project(root, github=True)
            (root / self.WORKFLOW).write_text("tampered\n", encoding="utf-8")
            data = json.loads((root / ".refract/manifest.json").read_text(encoding="utf-8"))
            data["files"][self.WORKFLOW]["mutable"] = True
            (root / ".refract/manifest.json").write_text(json.dumps(data), encoding="utf-8")
            operation = self._operations(build_plan(root, render_project(request(root)), remove_obsolete=True))[
                self.WORKFLOW
            ]
            self.assertEqual(Action.CONFLICT, operation.action)
            self.assertEqual("obsolete generated path was modified", operation.detail)

    def test_untracked_seeds_are_recognized_from_the_stored_facts_when_facts_changed(self) -> None:
        for edit_seed in (False, True):
            with self.subTest(edited=edit_seed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                self._project(root, version="0.0.1", github=True)
                self._as_older_manifest(root)
                if edit_seed:
                    for relative in ("AGENTS.md", self.PULL_REQUEST):
                        (root / relative).write_text("our edits\n", encoding="utf-8")
                # The first run after the upgrade also changes facts and drops a feature.
                changed = request(root)
                changed.facts.description = "another description"
                changed.facts.languages = ["Go"]
                changed.facts.test_command = "go test ./..."
                prepared = prepare_bootstrap(changed, remove_obsolete=True)
                self.assertEqual([], prepared.plan.conflicts)
                operations = self._operations(prepared.plan)
                if edit_seed:
                    self.assertEqual(UNKNOWN_SEED_BASE, operations["AGENTS.md"].seed_base)
                    self.assertEqual(UNKNOWN_SEED_BASE, operations[self.PULL_REQUEST].seed_base)
                else:
                    self.assertEqual(Action.UPDATE_GENERATED, operations["AGENTS.md"].action)
                    self.assertEqual(Action.REMOVE_OBSOLETE, operations[self.PULL_REQUEST].action)
                self.assertTrue(apply_bootstrap(prepared).applied)
                self.assertEqual(edit_seed, (root / self.PULL_REQUEST).exists())
                self.assertEqual(
                    edit_seed, (root / "AGENTS.md").read_text(encoding="utf-8") == "our edits\n"
                )

    def test_stored_request_is_the_inverse_of_the_rendered_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            variants = [
                request(root, github=True, hooks=True, ticket_prefix="ABC"),
                request(root, platforms=["claude"], mcp=True, agents=True, scheduled_audit=True, permissions=True),
            ]
            variants[1].facts.description = ""
            variants[1].facts.build_command = None
            variants[1].facts.run_command = "make run"
            for req in variants:
                config = root / ".refract/config.json"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_bytes(render_project(req)[".refract/config.json"].content)
                stored = _stored_request(req)
                self.assertIsNotNone(stored)
                self.assertEqual(req.facts, stored.facts)
                self.assertEqual(req.features.normalized_platforms(), stored.features.normalized_platforms())
                for flag in ("mcp", "agents", "github", "scheduled_audit", "hooks", "permissions"):
                    self.assertEqual(getattr(req.features, flag), getattr(stored.features, flag), flag)
                # Every file renders the same from the stored request as from the original.
                self.assertEqual(render_project(req), render_project(stored))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs named pipes")
    def test_stored_facts_reader_does_not_block_on_a_named_pipe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            (root / ".refract").mkdir(parents=True)
            os.mkfifo(root / ".refract/config.json")
            outcome: list[object] = []
            worker = threading.Thread(target=lambda: outcome.append(_stored_request(request(root))), daemon=True)
            worker.start()
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive(), "reading the stored configuration blocked")
            self.assertEqual([None], outcome)

    def test_invalid_stored_facts_do_not_stop_recognition_from_the_current_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            self._as_older_manifest(root)
            config = root / ".refract/config.json"
            data = json.loads(config.read_text(encoding="utf-8"))
            data["project"]["languages"] = [1]
            config.write_text(json.dumps(data), encoding="utf-8")
            self.assertIsNone(_stored_request(req))
            operation = self._operations(prepare_bootstrap(req).plan)["AGENTS.md"]
            self.assertEqual(Action.UPDATE_GENERATED, operation.action)

    def test_hostile_stored_facts_crash_cleanly_not_with_a_traceback(self) -> None:
        # Release-gate audit (0.3.1): ~1 MiB of nested "[" sent json.loads into a
        # RecursionError that escaped every catch tuple on the planning path.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            self._as_older_manifest(root)
            (root / ".refract/config.json").write_text("[" * 1_048_575, encoding="utf-8")
            self.assertIsNone(_stored_request(req))
            operation = self._operations(prepare_bootstrap(req).plan)["AGENTS.md"]
            self.assertEqual(Action.UPDATE_GENERATED, operation.action)

    def test_unbounded_manifest_version_stops_rendering_earlier_generations(self) -> None:
        # Release-gate audit (0.3.1): a hostile generator_version of unbounded digits
        # passed the release gate and was rendered into every candidate, multiplying
        # allocation and hashing. The gate now bounds each component to nine digits.
        self.assertIsNone(_RELEASE_VERSION.fullmatch("9" * 10 + ".0.0"))
        self.assertIsNone(_RELEASE_VERSION.fullmatch("1.2." + "9" * 10))
        self.assertEqual(_RELEASE_VERSION.fullmatch("10.20.30").group(0), "10.20.30")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            self._as_older_manifest(root, version="9" * 40 + ".0.0")
            operation = self._operations(prepare_bootstrap(req).plan)["AGENTS.md"]
            # Not shown to be generated under a version that cannot match: preserved.
            self.assertEqual(Action.NO_CHANGE, operation.action)

    def test_untracked_unedited_seed_of_a_feature_dropped_earlier_is_still_removable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self._project(root, version="0.0.1", github=True)
            # The feature was dropped before the upgrade, so the stored facts no longer have it.
            without = request(root)
            apply_plan(
                build_plan(root, render_project(without, generator_version="0.0.1")),
                without.features.normalized_platforms(),
            )
            self.assertTrue((root / self.PULL_REQUEST).is_file())
            self._as_older_manifest(root)
            prepared = prepare_bootstrap(without, remove_obsolete=True)
            self.assertEqual(Action.REMOVE_OBSOLETE, self._operations(prepared.plan)[self.PULL_REQUEST].action)
            self.assertTrue(apply_bootstrap(prepared).applied)
            self.assertFalse((root / self.PULL_REQUEST).exists())

    def test_unreadable_stored_facts_leave_seeds_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self._project(root, version="0.0.1")
            self._as_older_manifest(root)
            (root / ".refract/config.json").write_text("{not json", encoding="utf-8")
            changed = request(root)
            changed.facts.description = "another description"
            operation = self._operations(prepare_bootstrap(changed).plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, operation.action)
            self.assertEqual(UNKNOWN_SEED_BASE, operation.seed_base)

    def test_manifest_states_seed_tracking_only_when_it_holds(self) -> None:
        self.assertIn(b'"seed_hashes": "generated"', Manifest().to_bytes())
        self.assertNotIn(b"seed_hashes", Manifest(tracks_generated_seeds=False).to_bytes())

    def test_prepare_bootstrap_checks_seeds_against_the_earlier_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = self._project(root, version="0.0.1")
            self._as_older_manifest(root)
            unedited = self._operations(prepare_bootstrap(req).plan)
            self.assertEqual(Action.UPDATE_GENERATED, unedited["AGENTS.md"].action)
            seed = root / "AGENTS.md"
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            edited = self._operations(prepare_bootstrap(req).plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, edited.action)
            self.assertEqual(UNKNOWN_SEED_BASE, edited.seed_base)

    def test_plan_document_ownership_matches_the_written_manifest_for_preserved_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            first = request(root, github=True)
            self.assertTrue(apply_bootstrap(prepare_bootstrap(first)).applied)
            for relative in ("AGENTS.md", self.PULL_REQUEST):
                (root / relative).write_text("our edits\n", encoding="utf-8")
            # One seed stays generated and is preserved; the other becomes obsolete and is kept.
            req = request(root)
            req.facts.description = "second description"
            prepared = prepare_bootstrap(req)
            self.assertTrue(apply_bootstrap(prepared).applied)
            written = Manifest.load(root).files
            self.assertEqual(prepared.document["resulting_ownership"], written)
            self.assertIn(self.PULL_REQUEST, written)

    def test_identical_unmanaged_file_remains_unowned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = render_project(request(root))
            (root / "AGENTS.md").write_bytes(desired["AGENTS.md"].content)
            plan = build_plan(root, desired)
            op = next(op for op in plan.operations if op.path == "AGENTS.md")
            self.assertEqual(Action.SKIP_UNMANAGED, op.action)


if __name__ == "__main__":
    unittest.main()
