# goofy-ralph

`ralph` is a small CLI wrapper around `codex exec` for running the same prompt repeatedly from the directory where you launch it.

It is designed to work from a clone located anywhere on Linux or macOS, including macOS machines that still use the system Bash 3.2.

## Requirements

- `codex` available on `PATH`
- `bash`

## Install

Clone the repo anywhere and run the installer:

```bash
git clone git@github.com:NumeroQuadro/goofy-ralph.git
cd goofy-ralph
./install.sh
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

The helper runner lives at `scripts/repeat_codex_prompt.sh`.

## Tests

```bash
python3 -m unittest tests.test_install tests.test_ralph tests.test_repeat_codex_prompt
```
