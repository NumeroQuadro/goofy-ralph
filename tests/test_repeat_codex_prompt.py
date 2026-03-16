from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "repeat_codex_prompt.sh"


class RepeatCodexPromptTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            capture_output=True,
        )

    def test_dry_run_prints_loop_and_iteration_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("review this repo", encoding="utf-8")

            result = self.run_script("--dry-run", "--count", "2", "--prompt-file", str(prompt_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        loop_ids = re.findall(r"loop_id=([^\s]+)", result.stdout)
        self.assertTrue(loop_ids)
        self.assertEqual(len(set(loop_ids)), 1)
        self.assertIn("loop_start backend=codex total_runs=2", result.stdout)
        self.assertIn("prompt_source=file:", result.stdout)
        self.assertIn("iteration=1/2", result.stdout)
        self.assertIn("iteration_start iteration=1/2 current=1 total=2", result.stdout)
        self.assertIn("iteration_dry_run iteration=1/2 current=1 total=2", result.stdout)
        self.assertIn("loop_id=", result.stdout)
        self.assertIn("codex_command codex exec", result.stdout)
        self.assertIn("next_iteration=2/2", result.stdout)
        self.assertIn("loop_done total_runs=2", result.stdout)

    def test_opencode_backend_dry_run_builds_backend_specific_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            prompt_path = tmp_path / "prompt.txt"
            out_dir = tmp_path / "runs"
            prompt_path.write_text("review this repo", encoding="utf-8")

            result = self.run_script(
                "--dry-run",
                "--backend",
                "opencode",
                "--agent",
                "build",
                "--model",
                "anthropic/claude-sonnet-4",
                "--cd",
                str(tmp_path),
                "--out-dir",
                str(out_dir),
                "--prompt-file",
                str(prompt_path),
                "--",
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("loop_start backend=opencode", result.stdout)
        self.assertIn("opencode_command opencode run", result.stdout)
        self.assertIn("--agent build", result.stdout)
        self.assertIn("--model anthropic/claude-sonnet-4", result.stdout)
        self.assertIn("--format json", result.stdout)
        self.assertIn("PROMPT_TEXT", result.stdout)
        self.assertIn(f"workdir={tmp_path}", result.stdout)
        self.assertIn(f"run_output={out_dir}/run_001.txt", result.stdout)
        self.assertNotIn("codex exec", result.stdout)

    def test_opencode_backend_dry_run_without_extra_args_is_supported(self) -> None:
        result = self.run_script(
            "--dry-run",
            "--backend",
            "opencode",
            "--prompt",
            "hello from opencode",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("loop_start backend=opencode", result.stdout)
        self.assertIn("opencode_command opencode run PROMPT_TEXT", result.stdout)
        self.assertNotIn("error backend command not found", result.stderr)

    def test_opencode_backend_rejects_codex_profile_flag(self) -> None:
        result = self.run_script(
            "--dry-run",
            "--backend",
            "opencode",
            "--profile",
            "default",
            "--prompt",
            "hello",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--profile is only supported with --backend codex", result.stderr)

    def test_empty_prompt_file_warns_and_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "empty.txt"
            prompt_path.write_text("", encoding="utf-8")

            result = self.run_script("--dry-run", "--prompt-file", str(prompt_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("loop_id=", result.stderr)
        self.assertIn("warning: prompt file is empty", result.stderr)

    def test_whitespace_only_prompt_file_warns_and_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "blank.txt"
            prompt_path.write_text(" \n\t\r\n", encoding="utf-8")

            result = self.run_script("--dry-run", "--prompt-file", str(prompt_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("loop_id=", result.stderr)
        self.assertIn("warning: prompt file is empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
