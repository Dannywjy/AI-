"""Offline tests use a fake official-installer interface, never upstream code."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_media_skills.py"
REF = "a" * 40
FAKE_HELPER = '''\
import argparse, json, os
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--repo")
parser.add_argument("--ref")
parser.add_argument("--path", nargs="+")
parser.add_argument("--name")
parser.add_argument("--dest", type=Path)
parser.add_argument("--method")
args = parser.parse_args()
with Path(os.environ["FAKE_LOG"]).open("a") as log:
    log.write(json.dumps(vars(args), default=str) + "\\n")
for path in args.path:
    name = args.name or Path(path).name
    target = args.dest / name
    target.mkdir()
    (target / "SKILL.md").write_text(
        "---\\nname: " + ("incorrect" if os.environ.get("FAKE_BAD_NAME") else name)
        + "\\ndescription: >-\\n  A useful multiline\\n  description.\\n---\\nInstructions.\\n")
    (target / "resource.txt").write_text("reviewed bytes")
    if name == os.environ.get("FAKE_FAILURE"):
        raise SystemExit(13)
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.helper = self.base / "fake_installer.py"
        self.helper.write_text(FAKE_HELPER)
        self.log = self.base / "helper-calls.jsonl"
        self.lock = {"schema_version": 1, "sources": [{
            "id": "example", "repo": "owner/repository", "ref": REF,
            "skills": [{"path": "skills/first", "name": "first"},
                       {"path": "skills/second", "name": "second"}],
        }]}
        self.write_lock()

    def write_lock(self):
        (self.root / "media-skills.lock.json").write_text(json.dumps(self.lock))

    def invoke(self, *arguments, environment=None, project=None, helper=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(project or self.root),
             "--installer", str(helper or self.helper), *arguments],
            env=os.environ | {"FAKE_LOG": str(self.log)} | (environment or {}),
            capture_output=True, text=True,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def installed(self, name):
        return self.root / ".agents" / "skills" / name

    def test_dry_run_is_pinned_and_does_not_create_anything(self):
        result = self.invoke("--dry-run", helper=self.base / "missing.py")
        self.assert_success(result)
        commands = [shlex.split(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(commands), 1)
        self.assertIn(REF, commands[0])
        self.assertEqual(commands[0][commands[0].index("--method") + 1], "download")
        self.assertIn("skills/first", commands[0])
        self.assertIn("skills/second", commands[0])
        self.assertFalse((self.root / ".agents").exists())
        self.assertFalse(self.log.exists())

    def test_unsafe_paths_and_unpinned_refs_are_rejected_before_download(self):
        skill = self.lock["sources"][0]["skills"][0]
        for path in ("../escape", "/tmp/escape", "x/../../escape", "x\\escape", "-bad", "x//first"):
            with self.subTest(path=path):
                skill["path"] = path
                self.write_lock()
                self.assertNotEqual(self.invoke("--dry-run").returncode, 0)
        skill["path"] = "skills/first"
        for ref in ("main", "abc123", "a" * 39, "g" * 40, "--help"):
            with self.subTest(ref=ref):
                self.lock["sources"][0]["ref"] = ref
                self.write_lock()
                self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root / ".agents").exists())

    def test_failing_download_leaves_no_partial_batch_and_can_retry(self):
        result = self.invoke(environment={"FAKE_FAILURE": "second"})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.installed("first").exists())
        self.assertFalse(self.installed("second").exists())
        self.assertEqual(list((self.root / ".agents").iterdir()), [])
        self.assert_success(self.invoke())

    def test_failure_in_later_source_leaves_earlier_source_uninstalled(self):
        second = self.lock["sources"][0]["skills"].pop()
        self.lock["sources"].append({"id": "later", "repo": "other/repository", "ref": REF,
                                     "skills": [second]})
        self.write_lock()
        self.assertNotEqual(self.invoke(environment={"FAKE_FAILURE": "second"}).returncode, 0)
        self.assertFalse(self.installed("first").exists())
        self.assertFalse(self.installed("second").exists())

    def test_repeated_install_and_check_are_offline_and_detect_tampering(self):
        self.assert_success(self.invoke())
        calls = self.log.read_text()
        self.assertEqual(len(calls.splitlines()), 1)  # one archive request for this source
        self.assert_success(self.invoke(helper=self.base / "missing.py"))
        self.assert_success(self.invoke("--check", helper=self.base / "missing.py"))
        self.assertEqual(self.log.read_text(), calls)
        (self.installed("first") / "resource.txt").write_text("local changes")
        for mode in ((), ("--check",)):
            result = self.invoke(*mode)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("modified", result.stderr)
        self.assertEqual(self.log.read_text(), calls)
        self.assertEqual((self.installed("first") / "resource.txt").read_text(), "local changes")

    def test_source_version_mismatch_never_overwrites(self):
        self.assert_success(self.invoke())
        calls = self.log.read_text()
        self.lock["sources"][0]["ref"] = "b" * 40
        self.write_lock()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source/version differs", result.stderr)
        self.assertEqual(self.log.read_text(), calls)

    def test_root_skill_and_renamed_destination_use_explicit_name(self):
        self.lock["sources"][0]["skills"] = [
            {"path": ".", "name": "root-skill"},
            {"path": "skills/zh", "name": "seedance-prompt-zh"},
        ]
        self.write_lock()
        self.assert_success(self.invoke())
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual([call["name"] for call in calls], ["root-skill", "seedance-prompt-zh"])
        self.assert_success(self.invoke("--check"))

    def test_bad_metadata_is_rejected_before_promotion(self):
        result = self.invoke(environment={"FAKE_BAD_NAME": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Frontmatter name", result.stderr)
        self.assertFalse(self.installed("first").exists())

    def test_symlink_project_and_destination_are_refused(self):
        project_link = self.base / "project-link"
        project_link.symlink_to(self.root, target_is_directory=True)
        self.assertNotEqual(self.invoke(project=project_link).returncode, 0)
        external = self.base / "external"
        external.mkdir()
        agents = self.root / ".agents"
        agents.symlink_to(external, target_is_directory=True)
        self.assertNotEqual(self.invoke().returncode, 0)
        agents.unlink()
        agents.mkdir()
        (agents / "skills").symlink_to(external, target_is_directory=True)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse(self.log.exists())

    def test_existing_unrecorded_skill_is_preserved(self):
        self.installed("first").mkdir(parents=True)
        marker = self.installed("first") / "mine.txt"
        marker.write_text("do not overwrite")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(marker.read_text(), "do not overwrite")
        self.assertFalse(self.log.exists())

    def test_check_requires_all_expected_skills(self):
        result = self.invoke("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing installed skill", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
