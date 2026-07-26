from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import check_changed_paths  # noqa: E402

RECEIPT = ROOT / "ci_receipt.py"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class CiSupportTests(unittest.TestCase):
    def init_repo(self, path: Path) -> str:
        git(path, "init", "-q")
        git(path, "config", "user.name", "proof")
        git(path, "config", "user.email", "proof@example.invalid")
        (path / "README.md").write_text("base\n", encoding="utf-8")
        git(path, "add", "README.md")
        git(path, "commit", "-qm", "base")
        return git(path, "rev-parse", "HEAD")

    def test_allowlist_predicate(self) -> None:
        self.assertTrue(
            check_changed_paths.is_allowed(
                ".github/workflows/mxfile-composition-proof.yml"
            )
        )
        self.assertTrue(
            check_changed_paths.is_allowed(
                "docs/architecture/mxfile-composition.md"
            )
        )
        self.assertTrue(
            check_changed_paths.is_allowed(
                "proposal-evidence/mxfile-composition/composer.py"
            )
        )
        self.assertFalse(check_changed_paths.is_allowed("src/core.py"))
        self.assertFalse(
            check_changed_paths.is_allowed("proposal-evidence/dvm-elimination/x.py")
        )

    def test_changed_path_reader_preserves_allowed_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            base = self.init_repo(repo)
            allowed = repo / "proposal-evidence" / "mxfile-composition" / "proof.txt"
            allowed.parent.mkdir(parents=True)
            allowed.write_text("proof\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "allowed")
            head = git(repo, "rev-parse", "HEAD")
            self.assertEqual(
                check_changed_paths.changed_paths(base, head, repo),
                ["proposal-evidence/mxfile-composition/proof.txt"],
            )

    def test_changed_path_reader_exposes_forbidden_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            base = self.init_repo(repo)
            forbidden = repo / "src" / "core.py"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("bad\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "forbidden")
            head = git(repo, "rev-parse", "HEAD")
            paths = check_changed_paths.changed_paths(base, head, repo)
            self.assertEqual(paths, ["src/core.py"])
            self.assertFalse(check_changed_paths.is_allowed(paths[0]))

    def test_rename_cannot_hide_forbidden_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            forbidden = repo / "proposal-evidence" / "dvm-elimination" / "owned.py"
            forbidden.parent.mkdir(parents=True)
            self.init_repo(repo)
            forbidden.write_text("owned\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "owned base")
            base = git(repo, "rev-parse", "HEAD")
            allowed = repo / "proposal-evidence" / "mxfile-composition" / "owned.py"
            allowed.parent.mkdir(parents=True)
            git(repo, "mv", str(forbidden.relative_to(repo)), str(allowed.relative_to(repo)))
            git(repo, "commit", "-qm", "rename probe")
            head = git(repo, "rev-parse", "HEAD")
            paths = check_changed_paths.changed_paths(base, head, repo)
            self.assertEqual(
                paths,
                [
                    "proposal-evidence/dvm-elimination/owned.py",
                    "proposal-evidence/mxfile-composition/owned.py",
                ],
            )
            rejected = [path for path in paths if not check_changed_paths.is_allowed(path)]
            self.assertEqual(rejected, ["proposal-evidence/dvm-elimination/owned.py"])

    def test_symlink_inside_allowlist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            forbidden = repo / "proposal-evidence" / "dvm-elimination" / "owned.py"
            forbidden.parent.mkdir(parents=True)
            self.init_repo(repo)
            forbidden.write_text("owned\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "owned base")
            base = git(repo, "rev-parse", "HEAD")
            allowed = repo / "proposal-evidence" / "mxfile-composition" / "composer.py"
            allowed.parent.mkdir(parents=True)
            allowed.symlink_to("../dvm-elimination/owned.py")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "symlink probe")
            head = git(repo, "rev-parse", "HEAD")
            paths = check_changed_paths.changed_paths(base, head, repo)
            modes = check_changed_paths.head_file_modes(head, paths, repo)
            self.assertEqual(
                modes,
                {"proposal-evidence/mxfile-composition/composer.py": "120000"},
            )
            rejected = {
                path: mode
                for path, mode in modes.items()
                if mode not in check_changed_paths.REGULAR_FILE_MODES
            }
            self.assertEqual(
                rejected,
                {"proposal-evidence/mxfile-composition/composer.py": "120000"},
            )

    def test_workflow_is_read_only_and_uses_immutable_action_pins(self) -> None:
        workflow = (
            ROOT.parent.parent / ".github" / "workflows" / "mxfile-composition-proof.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("pull_request_target", workflow)
        uses = [
            line.split("uses:", 1)[1].split("#", 1)[0].strip()
            for line in workflow.splitlines()
            if "uses:" in line
        ]
        self.assertEqual(len(uses), 3)
        for action in uses:
            owner_repo, revision = action.rsplit("@", 1)
            self.assertIn(owner_repo, {"actions/checkout", "actions/upload-artifact"})
            self.assertEqual(len(revision), 40)
            self.assertTrue(all(character in "0123456789abcdef" for character in revision))

    def test_ci_receipt_binds_checked_out_sha_and_proof_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            head = self.init_repo(repo)
            proof = root / "proof"
            proof.mkdir()
            (proof / "proof-summary.json").write_text('{"status":"PASS"}\n')
            (proof / "SHA256SUMS.txt").write_text("manifest\n")
            receipt = root / "receipt.json"
            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_REPOSITORY": "roccho-dev/diagrams",
                    "GITHUB_RUN_ATTEMPT": "1",
                    "GITHUB_RUN_ID": "123",
                    "GITHUB_WORKFLOW_REF": "workflow-ref",
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECEIPT),
                    "--proof-dir",
                    str(proof),
                    "--output",
                    str(receipt),
                    "--expected-sha",
                    head,
                    "--mode",
                    "pr-exact-head",
                ],
                cwd=repo,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(result.stdout)["status"], "PASS")
            value = json.loads(receipt.read_text())
            self.assertEqual(value["checked_out_sha"], head)
            self.assertEqual(value["repository"], "roccho-dev/diagrams")
            self.assertEqual(value["mode"], "pr-exact-head")
            self.assertEqual(len(value["proof_summary_sha256"]), 64)
            self.assertEqual(len(value["manifest_sha256"]), 64)
            self.assertTrue(value["python_version"])
            self.assertTrue(value["python_implementation"])
            self.assertTrue(value["runner_os"])
            self.assertTrue(value["runner_arch"])

    def test_ci_receipt_rejects_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            self.init_repo(repo)
            proof = root / "proof"
            proof.mkdir()
            (proof / "proof-summary.json").write_text("{}\n")
            (proof / "SHA256SUMS.txt").write_text("manifest\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECEIPT),
                    "--proof-dir",
                    str(proof),
                    "--output",
                    str(root / "receipt.json"),
                    "--expected-sha",
                    "0" * 40,
                    "--mode",
                    "manual",
                ],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("checked-out SHA", result.stderr)


if __name__ == "__main__":
    unittest.main()
