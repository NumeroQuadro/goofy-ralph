from __future__ import annotations

import os
import pty
import select
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ralph"


class RalphCliTests(unittest.TestCase):
    def run_cli(
        self,
        *args: str,
        cwd: Path | None = None,
        script: Path | None = None,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(script or SCRIPT), *args],
            cwd=str(cwd or REPO_ROOT),
            check=False,
            text=True,
            capture_output=True,
            input=input_text,
            env=env,
        )

    def run_cli_tty(
        self,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        interactions: list[tuple[bytes, bytes]] | None = None,
        timeout: float = 10.0,
    ) -> tuple[int, str]:
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            ["bash", str(SCRIPT), *args],
            cwd=str(cwd or REPO_ROOT),
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            close_fds=True,
        )
        os.close(slave_fd)

        interactions = interactions or []
        interaction_index = 0
        chunks: list[bytes] = []
        deadline = time.monotonic() + timeout

        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.2)
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                    output = b"".join(chunks)
                    while interaction_index < len(interactions):
                        expected, response = interactions[interaction_index]
                        if expected not in output:
                            break
                        os.write(master_fd, response)
                        interaction_index += 1
                elif proc.poll() is not None:
                    break
            else:
                proc.terminate()
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass

        if proc.poll() is None:
            proc.kill()
        returncode = proc.wait(timeout=5)
        output_text = b"".join(chunks).decode("utf-8", errors="replace")
        return returncode, output_text

    def test_help_mentions_inherited_reasoning_effort(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("ralph [mode]", result.stdout)
        self.assertIn("--backend BACKEND", result.stdout)
        self.assertIn("opencode run", result.stdout)
        self.assertIn("plain `codex` would use", result.stdout)
        self.assertIn("custom model override manually", result.stdout)
        self.assertIn("default         Use the explicit Codex preset", result.stdout)
        self.assertIn("Number of runs (default: 5)", result.stdout)
        self.assertIn("use `RALPH.md`", result.stdout)
        self.assertIn("inherit", result.stdout)
        self.assertNotIn("ralph-loop [mode]", result.stdout)

    def test_dry_run_inherit_mode_does_not_inject_mode_flags(self) -> None:
        result = self.run_cli("--dry-run", "review this repo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex_command codex exec", result.stdout)
        self.assertIn("iteration_start iteration=1/5 current=1 total=5", result.stdout)
        self.assertIn(f"workdir={REPO_ROOT}", result.stdout)
        self.assertIn(f"out_dir={REPO_ROOT}/.ralph/", result.stdout)
        self.assertIn("--skip-git-repo-check", result.stdout)
        self.assertIn(f"-C {REPO_ROOT}", result.stdout)
        self.assertIn(f"{REPO_ROOT}/.ralph/", result.stdout)
        self.assertNotIn("--full-auto", result.stdout)
        self.assertNotIn("--sandbox", result.stdout)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", result.stdout)
        self.assertNotIn("model_reasoning_effort", result.stdout)

    def test_dry_run_full_auto_injects_mode_flag(self) -> None:
        result = self.run_cli("--dry-run", "--mode", "full-auto", "review this repo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--full-auto", result.stdout)

    def test_dry_run_workspace_write_mode_injects_sandbox(self) -> None:
        result = self.run_cli("--dry-run", "--mode", "workspace-write", "review this repo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--sandbox", result.stdout)
        self.assertIn("workspace-write", result.stdout)

    def test_forwards_raw_codex_exec_args_after_separator(self) -> None:
        result = self.run_cli(
            "--dry-run",
            "--mode",
            "read-only",
            "review this repo",
            "--",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--sandbox", result.stdout)
        self.assertIn("read-only", result.stdout)
        self.assertIn("--json", result.stdout)

    def test_positional_default_mode_and_prompt_file_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "text.md"
            prompt_path.write_text("hello from file", encoding="utf-8")

            result = self.run_cli("--dry-run", "default", "-n", "2", f"--prompt={prompt_path}")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("loop_start backend=codex total_runs=2", result.stdout)
        self.assertIn("iteration_start iteration=1/2 current=1 total=2", result.stdout)
        self.assertIn("prompt_chars=15", result.stdout)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", result.stdout)
        self.assertIn("--skip-git-repo-check", result.stdout)
        self.assertNotIn(" -m ", result.stdout)
        self.assertNotIn("model_reasoning_effort", result.stdout)

    def test_defaults_to_ralph_md_when_prompt_not_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            prompt_path = tmp_path / "RALPH.md"
            prompt_path.write_text("default prompt file", encoding="utf-8")

            result = self.run_cli("--dry-run", "default", cwd=tmp_path)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("loop_start backend=codex total_runs=5", result.stdout)
        self.assertIn("prompt_source=file:RALPH.md", result.stdout)
        self.assertIn("prompt_chars=19", result.stdout)

    def test_positional_mode_before_prompt_text_works(self) -> None:
        result = self.run_cli("--dry-run", "full-auto", "review this repo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--full-auto", result.stdout)

    def test_default_mode_respects_explicit_model_override(self) -> None:
        result = self.run_cli(
            "--dry-run",
            "default",
            "--model",
            "gpt-5.1-codex-mini",
            "review this repo",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-m gpt-5.1-codex-mini", result.stdout)
        self.assertNotIn("model_reasoning_effort", result.stdout)

    def test_direct_mode_keeps_explicit_model_override_verbatim(self) -> None:
        result = self.run_cli("--dry-run", "--model", "gpt-5.4", "review this repo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-m gpt-5.4", result.stdout)

    def test_opencode_backend_inherits_current_defaults_when_not_overridden(self) -> None:
        result = self.run_cli("--dry-run", "--backend", "opencode", "review this repo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("loop_start backend=opencode", result.stdout)
        self.assertIn("opencode_command opencode run", result.stdout)
        self.assertIn("PROMPT_TEXT", result.stdout)
        self.assertNotIn("--model", result.stdout)
        self.assertNotIn("--agent", result.stdout)
        self.assertNotIn("--skip-git-repo-check", result.stdout)
        self.assertNotIn("codex exec", result.stdout)

    def test_auto_selects_opencode_when_codex_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            utility_dir = tmp_path / "utils"
            bin_dir.mkdir()
            utility_dir.mkdir()
            fake_opencode = bin_dir / "opencode"
            fake_opencode.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_opencode.chmod(0o755)

            for command_name in ("bash", "sed", "dirname", "readlink", "basename", "date", "tr", "mkdir", "sleep"):
                target = shutil.which(command_name, path="/usr/bin:/bin")
                self.assertIsNotNone(target, command_name)
                (utility_dir / command_name).symlink_to(target)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{utility_dir}"

            result = self.run_cli("--dry-run", "review this repo", env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("loop_start backend=opencode", result.stdout)
        self.assertIn("opencode_command opencode run", result.stdout)
        self.assertNotIn("codex exec", result.stdout)

    def test_opencode_backend_forwards_agent_model_and_extra_args(self) -> None:
        result = self.run_cli(
            "--dry-run",
            "--backend",
            "opencode",
            "--agent",
            "build",
            "--model",
            "anthropic/claude-sonnet-4",
            "review this repo",
            "--",
            "--format",
            "json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("opencode_command opencode run", result.stdout)
        self.assertIn("--agent build", result.stdout)
        self.assertIn("--model anthropic/claude-sonnet-4", result.stdout)
        self.assertIn("--format json", result.stdout)

    def test_opencode_backend_rejects_codex_only_profile_flag(self) -> None:
        result = self.run_cli(
            "--dry-run",
            "--backend",
            "opencode",
            "--profile",
            "default",
            "review this repo",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--profile is only supported with --backend codex", result.stderr)

    def test_symlink_invocation_resolves_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            shim = tmp_path / "ralph"
            shim.symlink_to(SCRIPT)
            run_dir = tmp_path / "workspace"
            run_dir.mkdir()

            result = self.run_cli("--dry-run", "review this repo", cwd=run_dir, script=shim)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex_command codex exec", result.stdout)
        self.assertIn(f"workdir={run_dir}", result.stdout)
        self.assertIn(f"out_dir={run_dir}/.ralph/", result.stdout)

    def test_runs_from_caller_directory_with_relative_prompt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            prompt_path = tmp_path / "prompt.txt"
            prompt_path.write_text("review this repo", encoding="utf-8")

            result = self.run_cli(
                "--dry-run",
                "default",
                "-n",
                "2",
                "--prompt",
                "prompt.txt",
                cwd=tmp_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"workdir={tmp_path}", result.stdout)
        self.assertIn(f"out_dir={tmp_path}/.ralph/", result.stdout)
        self.assertIn(f"prompt_source=file:prompt.txt", result.stdout)
        self.assertNotIn(" -m ", result.stdout)

    def test_rejects_conflicting_prompt_sources(self) -> None:
        result = self.run_cli("--dry-run", "--prompt", "one", "two")

        self.assertEqual(result.returncode, 2)
        self.assertIn("use either positional prompt", result.stderr)

    def test_rejects_duplicate_mode_sources(self) -> None:
        result = self.run_cli("--dry-run", "--mode", "full-auto", "default", "--prompt", "hello")

        self.assertEqual(result.returncode, 2)
        self.assertIn("mode specified more than once", result.stderr)

    def test_explicit_cd_and_out_dir_override_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            custom_workdir = tmp_path / "project"
            custom_out_dir = tmp_path / "results"
            custom_workdir.mkdir()

            result = self.run_cli(
                "--dry-run",
                "--cd",
                str(custom_workdir),
                "--out-dir",
                str(custom_out_dir),
                "review this repo",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"workdir={custom_workdir}", result.stdout)
        self.assertIn(f"out_dir={custom_out_dir}", result.stdout)
        self.assertIn(f"-C {custom_workdir}", result.stdout)
        self.assertIn(f"{custom_out_dir}/run_001.txt", result.stdout)

    def test_explicit_cd_without_out_dir_uses_target_directory_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            custom_workdir = tmp_path / "project"
            custom_workdir.mkdir()
            prompt_path = custom_workdir / "prompt.txt"
            prompt_path.write_text("audit target directory", encoding="utf-8")

            result = self.run_cli(
                "--dry-run",
                "--cd",
                str(custom_workdir),
                "--prompt",
                "prompt.txt",
                cwd=tmp_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"workdir={custom_workdir}", result.stdout)
        self.assertIn(f"out_dir={custom_workdir}/.ralph/", result.stdout)
        self.assertIn(f"-C {custom_workdir}", result.stdout)
        self.assertIn(f"prompt_source=file:{custom_workdir}/prompt.txt", result.stdout)

    def test_interactive_menu_can_launch_default_mode_with_prompt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("audit this repo", encoding="utf-8")

            result = self.run_cli(
                "--interactive",
                input_text="\n".join(
                    [
                        "",
                        "2",
                        "",
                        "",
                        "2",
                        "0",
                        "2",
                        str(prompt_path),
                        "n",
                        "y",
                        "",
                    ]
                )
                + "\n",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ralph interactive setup", result.stdout)
        self.assertIn("mode=default", result.stdout)
        self.assertIn("loop_start backend=codex total_runs=2", result.stdout)
        self.assertIn("prompt_source=file:", result.stdout)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", result.stdout)
        self.assertNotIn(" -m ", result.stdout)
        self.assertNotIn("model_reasoning_effort", result.stdout)

    def test_interactive_menu_can_launch_opencode_backend_with_agent_override(self) -> None:
        result = self.run_cli(
            "--interactive",
            "--backend",
            "opencode",
            input_text="\n".join(
                [
                    "",
                    "",
                    "build",
                    "2",
                    "0",
                    "3",
                    "review this repo",
                    "n",
                    "y",
                    "",
                ]
            )
            + "\n",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("backend=opencode", result.stdout)
        self.assertIn("agent=build", result.stdout)
        self.assertIn("opencode_command opencode run", result.stdout)

    def test_interactive_tty_skips_custom_count_selector_and_keeps_delay_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            prompt_path = tmp_path / "RALPH.md"
            prompt_path.write_text("interactive tty prompt", encoding="utf-8")
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            opencode_path = bin_dir / "opencode"
            opencode_path.write_text(
                "#!/usr/bin/env bash\n"
                "echo \"stub opencode $*\"\n",
                encoding="utf-8",
            )
            opencode_path.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"

            returncode, output = self.run_cli_tty(
                "--backend",
                "opencode",
                "-n",
                "15",
                cwd=tmp_path,
                env=env,
                interactions=[
                    (b"Backend: < opencode >", b"\n"),
                    (b"Model: < backend default >", b"\n"),
                    (b"Agent override (blank keeps current opencode agent):", b"\n"),
                    (b"How many runs [15]:", b"1\n"),
                    (b"Delay: < 0 >", b"\r"),
                    (b"Prompt: < RALPH.md >", b"\n"),
                    (b"Continue on error: < no >", b"\n"),
                    (b"Dry run: < no >", b"\n"),
                    (b"Launch now: < yes >", b"\n"),
                ],
            )

        self.assertEqual(returncode, 0, output)
        self.assertNotIn("Run count: < custom >", output)
        self.assertIn("How many runs [15]: 1", output)
        self.assertIn("Delay: 0", output)
        self.assertNotIn("Delay: custom", output)
        self.assertIn("loop_start backend=opencode total_runs=1", output)

    def test_interactive_menu_prefills_ralph_md_as_default_prompt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            prompt_path = tmp_path / "RALPH.md"
            prompt_path.write_text("interactive default prompt", encoding="utf-8")

            result = self.run_cli(
                "--interactive",
                cwd=tmp_path,
                input_text="\n".join(
                    [
                        "",
                        "1",
                        "",
                        "",
                        "1",
                        "0",
                        "1",
                        "n",
                        "y",
                        "",
                    ]
                )
                + "\n",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prompt_source=file:RALPH.md", result.stdout)
        self.assertIn("prompt_file=RALPH.md", result.stdout)
        self.assertIn("prompt_chars=26", result.stdout)

    def test_interactive_menu_can_launch_read_only_mode_with_inline_prompt(self) -> None:
        result = self.run_cli(
            "--interactive",
            input_text="\n".join(
                [
                    "",
                    "3",
                    "gpt-5.5-codex",
                    "",
                    "1",
                    "0",
                    "3",
                    "review account docs",
                    "n",
                    "y",
                    "",
                ]
            )
            + "\n",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=read-only", result.stdout)
        self.assertIn("prompt_source=flag", result.stdout)
        self.assertIn("prompt_chars=19", result.stdout)
        self.assertIn("--sandbox read-only", result.stdout)
        self.assertIn("-m gpt-5.5-codex", result.stdout)

    def test_interactive_menu_targets_custom_directory_for_prompt_and_output_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            target_dir = tmp_path / "target"
            target_dir.mkdir()
            prompt_path = target_dir / "prompt.txt"
            prompt_path.write_text("inspect target directory", encoding="utf-8")

            result = self.run_cli(
                "--interactive",
                "--cd",
                str(target_dir),
                cwd=tmp_path,
                input_text="\n".join(
                    [
                        "",
                        "1",
                        "",
                        "",
                        "1",
                        "0",
                        "2",
                        "prompt.txt",
                        "n",
                        "y",
                        "",
                    ]
                )
                + "\n",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"launch_dir={tmp_path}", result.stdout)
        self.assertIn(f"workdir={target_dir}", result.stdout)
        self.assertIn(f"out_dir={target_dir}/.ralph/", result.stdout)
        self.assertIn(f"prompt_source=file:{target_dir}/prompt.txt", result.stdout)
        self.assertIn(f"-C {target_dir}", result.stdout)


if __name__ == "__main__":
    unittest.main()
