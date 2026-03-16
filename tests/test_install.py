from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
LAUNCHER_SCRIPT = REPO_ROOT / "scripts" / "ralph"


class InstallScriptTests(unittest.TestCase):
    def test_install_into_requested_bin_dir_creates_working_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(INSTALL_SCRIPT), "--bin-dir", str(bin_dir)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Installed ralph to", result.stdout)

            installed_link = bin_dir / "ralph"
            self.assertTrue(installed_link.is_symlink())
            self.assertEqual(installed_link.resolve(), LAUNCHER_SCRIPT.resolve())

            help_result = subprocess.run(
                [str(installed_link), "--help"],
                cwd=str(tmp_path),
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("ralph [mode]", help_result.stdout)

    def test_install_defaults_to_home_local_bin_when_no_writable_candidate_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            home_dir = tmp_path / "home"
            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["PATH"] = "/usr/bin:/bin"

            result = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Installed ralph to {home_dir}/.local/bin/ralph", result.stdout)
            self.assertIn(f'export PATH="{home_dir}/.local/bin:$PATH"', result.stdout)
            self.assertTrue((home_dir / ".local" / "bin" / "ralph").is_symlink())
