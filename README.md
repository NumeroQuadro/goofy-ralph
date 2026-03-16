# goofy-ralph

`ralph` is a small CLI wrapper around `codex exec` for running the same prompt repeatedly from the directory where you launch it.

It is designed to work from a clone located anywhere on Linux or macOS, including macOS machines that still use the system Bash 3.2.

## Requirements

- `bash`
- `codex` on `PATH` if you want the default backend
- `opencode` on `PATH` if you want `--backend opencode`

## Install

Clone the repo anywhere and run the installer:

```bash
git clone git@github.com:NumeroQuadro/goofy-ralph.git
cd goofy-ralph
./install.sh
```

For a curl-style bootstrap install:

```bash
curl -fsSL https://raw.githubusercontent.com/NumeroQuadro/goofy-ralph/main/bootstrap.sh | bash
```

To force a specific bin directory with the curl bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/NumeroQuadro/goofy-ralph/main/bootstrap.sh | bash -s -- --bin-dir /usr/local/bin
```

`install.sh` installs `ralph` into:

- `$RALPH_BIN_DIR` when you set it
- otherwise `$HOME/.local/bin`

You can also install into a specific directory:

```bash
./install.sh --bin-dir "/usr/local/bin"
```

If the installer prints a PATH hint, add that directory to your shell startup file.

Manual install is still possible:

```bash
ln -sfn "/path/to/goofy-ralph/scripts/ralph" "$HOME/.local/bin/ralph"
```

## Usage

Direct mode:

```bash
ralph default -n 10 --prompt prompt.txt
```

OpenCode backend:

```bash
ralph --backend opencode --agent build -n 3 --prompt prompt.txt
```

Inline prompt:

```bash
ralph full-auto -n 3 "review this repo and list TODOs"
```

Interactive mode:

```bash
ralph
```

Defaults:

- prompt file: `RALPH.md` from the effective working directory, when present
- run count: `5`
- output directory: `<effective-workdir>/.ralph/<timestamp-pid>/`
- backend: `codex` unless you pass `--backend opencode`

Backend notes:

- `codex` keeps the existing `ralph` mode behavior (`default`, `read-only`, `full-auto`, and so on)
- `opencode` inherits the current opencode model/agent setup unless you override `--model` or `--agent`

The helper runner lives at `scripts/repeat_codex_prompt.sh` and now supports both backends.

## Tests

```bash
python3 -m unittest tests.test_install tests.test_ralph tests.test_repeat_codex_prompt
```
