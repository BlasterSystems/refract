from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from refract.apply import ApplyError, apply_plan
from refract.facade import apply_bootstrap, prepare_bootstrap
from refract.manifest import Manifest, sha256_bytes, sha256_path
from refract.model import GeneratedFile
from refract.planner import Action, build_plan
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

    def test_customized_seed_survives_reruns_that_rewrite_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            first = request(root)
            apply_plan(build_plan(root, render_project(first)), first.features.normalized_platforms())
            self.assertIn('"seed_hashes": "generated"', (root / ".refract/manifest.json").read_text(encoding="utf-8"))
            seed = root / "AGENTS.md"
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            customized = seed.read_bytes()
            runs = (("second description", True), ("third description", True), ("third description", False))
            for description, generated_seed_changed in runs:
                req = request(root)
                req.facts.description = description
                desired = render_project(req)
                plan = build_plan(root, desired)
                operation = self._operations(plan)["AGENTS.md"]
                self.assertEqual(Action.NO_CHANGE, operation.action, description)
                self.assertTrue(operation.customized)
                self.assertIn("customized and is preserved", operation.detail)
                # The review note appears once per change of the generated seed, not forever.
                self.assertEqual(generated_seed_changed, "review the new version manually" in operation.detail)
                self.assertEqual(generated_seed_changed, bool(plan.changes))
                apply_plan(plan, req.features.normalized_platforms())
                self.assertEqual(customized, seed.read_bytes(), description)
                recorded = Manifest.load(root).files["AGENTS.md"]["sha256"]
                self.assertEqual(sha256_bytes(desired["AGENTS.md"].content), recorded)
                self.assertNotEqual(sha256_bytes(customized), recorded)

    def test_seed_matching_the_generated_version_is_tracked_as_generated_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            first = request(root)
            apply_plan(build_plan(root, render_project(first)), first.features.normalized_platforms())
            seed = root / "AGENTS.md"
            seed.write_text("edited\n", encoding="utf-8")
            second = request(root)
            second.facts.description = "second description"
            desired = render_project(second)
            seed.write_bytes(desired["AGENTS.md"].content)
            plan = build_plan(root, desired)
            operation = self._operations(plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, operation.action)
            self.assertFalse(operation.customized)
            self.assertEqual("owned generated file", operation.detail)
            self.assertEqual(Action.MANIFEST_UPDATE, self._operations(plan)[".refract/manifest.json"].action)
            apply_plan(plan, second.features.normalized_platforms())
            third = request(root)
            third.facts.description = "third description"
            self.assertEqual(
                Action.UPDATE_GENERATED, self._operations(build_plan(root, render_project(third)))["AGENTS.md"].action
            )

    def test_edited_seed_that_is_no_longer_generated_is_released_not_conflicted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            with_github = request(root, github=True)
            apply_plan(build_plan(root, render_project(with_github)), with_github.features.normalized_platforms())
            template = root / ".github/PULL_REQUEST_TEMPLATE.md"
            template.write_text("ours\n", encoding="utf-8")
            without = request(root)
            plan = build_plan(root, render_project(without), remove_obsolete=True)
            self.assertEqual([], plan.conflicts)
            operations = self._operations(plan)
            released = operations[".github/PULL_REQUEST_TEMPLATE.md"]
            self.assertEqual(Action.SKIP_UNMANAGED, released.action)
            self.assertIn("released from the manifest", released.detail)
            self.assertEqual(Action.REMOVE_OBSOLETE, operations[".github/workflows/docs-check.yml"].action)
            apply_plan(plan, without.features.normalized_platforms(), remove_obsolete=True)
            self.assertEqual("ours\n", template.read_text(encoding="utf-8"))
            self.assertNotIn(".github/PULL_REQUEST_TEMPLATE.md", Manifest.load(root).files)
            self.assertFalse((root / ".github/workflows/docs-check.yml").exists())
            again = build_plan(root, render_project(without))
            self.assertFalse(again.changes)
            self.assertFalse(again.conflicts)

    def test_seed_edited_under_an_older_manifest_is_preserved_on_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)

            def earlier(version: str) -> dict[str, GeneratedFile]:
                return render_project(req, generator_version=version)

            apply_plan(build_plan(root, earlier("0.0.1")), req.features.normalized_platforms())
            seed = root / "AGENTS.md"
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            customized = seed.read_bytes()
            # The older release recorded the edited content as if it had generated it.
            self._as_older_manifest(root, **{"AGENTS.md": sha256_bytes(customized)})
            plan = build_plan(root, render_project(req), previous_generation=earlier)
            operation = self._operations(plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, operation.action)
            self.assertTrue(operation.customized)
            self.assertIn("did not record whether it was edited", operation.detail)
            self.assertEqual(Action.UPDATE_GENERATED, self._operations(plan)[".refract/config.json"].action)
            apply_plan(plan, req.features.normalized_platforms())
            self.assertEqual(customized, seed.read_bytes())
            self.assertTrue(Manifest.load(root).tracks_generated_seeds)
            again = build_plan(root, render_project(req), previous_generation=earlier)
            self.assertFalse(again.changes)
            self.assertIn("customized and is preserved", self._operations(again)["AGENTS.md"].detail)

    def test_unedited_seed_under_an_older_manifest_updates_only_when_provably_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)

            def earlier(version: str) -> dict[str, GeneratedFile]:
                return render_project(req, generator_version=version)

            apply_plan(build_plan(root, earlier("0.0.1")), req.features.normalized_platforms())
            self._as_older_manifest(root)
            proven = self._operations(build_plan(root, render_project(req), previous_generation=earlier))
            self.assertEqual(Action.UPDATE_GENERATED, proven["AGENTS.md"].action)
            unproven = self._operations(build_plan(root, render_project(req)))["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, unproven.action)
            self.assertTrue(unproven.customized)

    def test_older_manifest_is_rewritten_once_and_never_removes_a_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            with_github = request(root, github=True)
            apply_plan(build_plan(root, render_project(with_github)), with_github.features.normalized_platforms())
            self._as_older_manifest(root, version=Manifest().generator_version)
            unchanged = build_plan(root, render_project(with_github))
            self.assertEqual(
                [".refract/manifest.json"], [operation.path for operation in unchanged.changes]
            )
            # Without tracking, an unchanged obsolete seed may be an edited one, so it is kept.
            without = request(root)
            plan = build_plan(root, render_project(without), remove_obsolete=True)
            self.assertEqual(Action.SKIP_UNMANAGED, self._operations(plan)[".github/PULL_REQUEST_TEMPLATE.md"].action)
            apply_plan(plan, without.features.normalized_platforms(), remove_obsolete=True)
            self.assertTrue((root / ".github/PULL_REQUEST_TEMPLATE.md").is_file())
            self.assertFalse(build_plan(root, render_project(without)).changes)

    def test_prepare_bootstrap_checks_seeds_against_the_earlier_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            req = request(root)
            apply_plan(
                build_plan(root, render_project(req, generator_version="0.0.1")), req.features.normalized_platforms()
            )
            self._as_older_manifest(root)
            unedited = self._operations(prepare_bootstrap(req).plan)
            self.assertEqual(Action.UPDATE_GENERATED, unedited["AGENTS.md"].action)
            seed = root / "AGENTS.md"
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            self._as_older_manifest_hash(root, "AGENTS.md", sha256_path(seed))
            edited = self._operations(prepare_bootstrap(req).plan)["AGENTS.md"]
            self.assertEqual(Action.NO_CHANGE, edited.action)
            self.assertTrue(edited.customized)

    @staticmethod
    def _as_older_manifest_hash(root: Path, relative: str, digest: str) -> None:
        path = root / ".refract/manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["files"][relative]["sha256"] = digest
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_plan_document_ownership_matches_the_written_manifest_for_a_customized_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            first = request(root)
            self.assertTrue(apply_bootstrap(prepare_bootstrap(first)).applied)
            seed = root / "AGENTS.md"
            seed.write_text(seed.read_text(encoding="utf-8") + "\nOur own rule.\n", encoding="utf-8")
            req = request(root)
            req.facts.description = "second description"
            prepared = prepare_bootstrap(req)
            self.assertTrue(apply_bootstrap(prepared).applied)
            self.assertEqual(prepared.document["resulting_ownership"], Manifest.load(root).files)

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
