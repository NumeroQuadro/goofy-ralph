# goofy-ralph

`ralph` is a small CLI wrapper around `codex exec` for running the same prompt repeatedly from the directory where you launch it.

## Install

Clone the repo and point `/usr/local/bin/ralph` at the launcher:

```bash
ln -sfn /path/to/goofy-ralph/scripts/ralph /usr/local/bin/ralph
chmod +x /path/to/goofy-ralph/scripts/ralph /path/to/goofy-ralph/scripts/repeat_codex_prompt.sh
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
python3 -m unittest tests.test_ralph tests.test_repeat_codex_prompt
```
