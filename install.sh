#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install `ralph` into a writable bin directory on this machine.

Usage:
  ./install.sh
  ./install.sh --bin-dir /custom/bin

Options:
  --bin-dir DIR  Install the `ralph` symlink into DIR.
  -h, --help     Show this help.

Defaults:
  - Uses $RALPH_BIN_DIR when set.
  - Otherwise installs into $HOME/.local/bin.
  - Creates the target directory when needed.
EOF
}

resolve_script_path() {
  local source_path="$1"
  local source_dir=""
  local target_path=""

  while [[ -L "$source_path" ]]; do
    source_dir="$(cd -P "$(dirname "$source_path")" && pwd)"
    target_path="$(readlink "$source_path")"
    if [[ "$target_path" == /* ]]; then
      source_path="$target_path"
    else
      source_path="${source_dir}/${target_path}"
    fi
  done

  source_dir="$(cd -P "$(dirname "$source_path")" && pwd)"
  printf '%s/%s\n' "$source_dir" "$(basename "$source_path")"
}

path_contains_dir() {
  local candidate="$1"

  case ":$PATH:" in
    *":$candidate:"*) return 0 ;;
    *) return 1 ;;
  esac
}

pick_default_bin_dir() {
  if [[ -n "${RALPH_BIN_DIR:-}" ]]; then
    printf '%s' "$RALPH_BIN_DIR"
    return 0
  fi

  printf '%s' "$HOME/.local/bin"
}

bin_dir=""

while (($# > 0)); do
  case "$1" in
    --bin-dir)
      [[ $# -ge 2 ]] || {
        echo "missing value for --bin-dir" >&2
        exit 2
      }
      bin_dir="$2"
      shift 2
      ;;
    --bin-dir=*)
      bin_dir="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

install_script_path="$(resolve_script_path "${BASH_SOURCE[0]}")"
repo_root="$(cd -P "$(dirname "$install_script_path")" && pwd)"
launcher_path="${repo_root}/scripts/ralph"
repeat_runner_path="${repo_root}/scripts/repeat_codex_prompt.sh"

[[ -f "$launcher_path" ]] || {
  echo "launcher not found: $launcher_path" >&2
  exit 1
}

[[ -f "$repeat_runner_path" ]] || {
  echo "helper runner not found: $repeat_runner_path" >&2
  exit 1
}

chmod +x "$launcher_path" "$repeat_runner_path"

if [[ -z "$bin_dir" ]]; then
  bin_dir="$(pick_default_bin_dir)"
fi

mkdir -p "$bin_dir"
ln -sfn "$launcher_path" "${bin_dir}/ralph"

echo "Installed ralph to ${bin_dir}/ralph"
echo "Repo root: ${repo_root}"

if ! path_contains_dir "$bin_dir"; then
  echo "Add this directory to your PATH before using ralph:"
  echo "  export PATH=\"${bin_dir}:\$PATH\""
fi

if ! command -v codex >/dev/null 2>&1 && ! command -v opencode >/dev/null 2>&1; then
  echo "warning: neither codex nor opencode is currently on PATH; install at least one backend before running ralph" >&2
fi
