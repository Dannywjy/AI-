"""Verify the wrapper offline; the npx substitute never invokes Hyperframes."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


WRAPPER = Path(__file__).resolve().parents[1] / "scripts" / "hyperframes.sh"
FIXED_ENV = {
    "HYPERFRAMES_SKIP_SKILLS": "1",
    "HYPERFRAMES_SKILL_PKG_VERSION": "0.8.181",
    "HYPERFRAMES_PLUGIN_VERSION": "0.8.181",
    "HYPERFRAMES_NO_UPDATE_CHECK": "1",
    "HYPERFRAMES_NO_TELEMETRY": "1",
}


class HyperframesWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.capture = self.base / "npx-invocation.json"
        substitute = self.base / "npx"
        substitute.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['NPX_CAPTURE_PATH']).write_text(json.dumps({\n"
            "    'args': sys.argv[1:],\n"
            f"    'env': {{key: os.environ.get(key) for key in {list(FIXED_ENV)!r}}},\n"
            "}))\n"
        )
        substitute.chmod(0o755)
        self.environment = os.environ | {
            "PATH": str(self.base) + os.pathsep + os.environ.get("PATH", ""),
            "NPX_CAPTURE_PATH": str(self.capture),
        }

    def invoke(self, *arguments):
        return subprocess.run(["/bin/sh", str(WRAPPER), *arguments],
                              env=self.environment, capture_output=True, text=True)

    def test_init_pins_package_and_overrides_conflicting_environment(self):
        self.environment.update({key: "unreviewed" for key in FIXED_ENV})
        result = self.invoke("init", "my-video")
        self.assertEqual(result.returncode, 0, result.stderr)
        invocation = json.loads(self.capture.read_text())
        self.assertEqual(invocation["env"], FIXED_ENV)
        self.assertEqual(invocation["args"], ["--yes", "hyperframes@0.8.181", "init", "my-video"])

    def test_arguments_preserve_spaces_quotes_and_shell_characters(self):
        arguments = ["render", "folder with spaces", "--name", "a'\";*?$()", "", "中文视频"]
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.capture.read_text())["args"],
                         ["--yes", "hyperframes@0.8.181", *arguments])

    def test_disabled_commands_never_invoke_npx(self):
        for command in ("skills", "upgrade", "feedback"):
            for prefix in ([], ["--verbose"], ["--"]):
                with self.subTest(command=command, prefix=prefix):
                    result = self.invoke(*prefix, command, "additional-argument")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"Disabled command: {command}", result.stderr)
                    self.assertFalse(self.capture.exists())

    def test_no_command_and_help_are_forwarded(self):
        for arguments in ([], ["--help"], ["help", "skills"]):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.capture.read_text())["args"],
                                 ["--yes", "hyperframes@0.8.181", *arguments])


if __name__ == "__main__":
    unittest.main()
