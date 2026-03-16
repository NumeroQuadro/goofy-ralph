from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
BOOTSTRAP_SCRIPT = REPO_ROOT / "bootstrap.sh"
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

    def test_bootstrap_clones_repo_snapshot_and_installs_ralph(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fixture_repo = tmp_path / "fixture-repo"
            clone_dir = tmp_path / "cloned-repo"
            bin_dir = tmp_path / "bin"

            shutil.copytree(
                REPO_ROOT,
                fixture_repo,
                ignore=shutil.ignore_patterns(".git", ".ralph", "__pycache__", ".pytest_cache"),
            )
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=str(fixture_repo),
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=str(fixture_repo),
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=str(fixture_repo),
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=str(fixture_repo),
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=str(fixture_repo),
                check=True,
                capture_output=True,
                text=True,
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["RALPH_REPO_URL"] = str(fixture_repo)

            result = subprocess.run(
                [
                    "bash",
                    str(BOOTSTRAP_SCRIPT),
                    "--repo-dir",
                    str(clone_dir),
                    "--bin-dir",
                    str(bin_dir),
                ],
                cwd=str(REPO_ROOT),
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((clone_dir / ".git").is_dir())
            self.assertTrue((bin_dir / "ralph").is_symlink())

            help_result = subprocess.run(
                [str(bin_dir / "ralph"), "--help"],
                cwd=str(tmp_path),
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("ralph [mode]", help_result.stdout)
