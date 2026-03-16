#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Bootstrap goofy-ralph from GitHub and install the `ralph` command.

Usage:
  ./bootstrap.sh
  ./bootstrap.sh --repo-dir /custom/path --bin-dir /custom/bin

Environment:
  RALPH_REPO_URL   Clone source (default: https://github.com/NumeroQuadro/goofy-ralph.git)
  RALPH_REPO_DIR   Install checkout directory (default: $HOME/.local/share/goofy-ralph)
  RALPH_BIN_DIR    Default bin directory passed through to install.sh
EOF
}

repo_url="${RALPH_REPO_URL:-https://github.com/NumeroQuadro/goofy-ralph.git}"
repo_dir="${RALPH_REPO_DIR:-$HOME/.local/share/goofy-ralph}"
bin_dir="${RALPH_BIN_DIR:-}"

while (($# > 0)); do
  case "$1" in
    --repo-dir)
      [[ $# -ge 2 ]] || {
        echo "missing value for --repo-dir" >&2
        exit 2
      }
      repo_dir="$2"
      shift 2
      ;;
    --repo-dir=*)
      repo_dir="${1#*=}"
      shift
      ;;
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

command -v git >/dev/null 2>&1 || {
  echo "git is required to bootstrap goofy-ralph" >&2
  exit 1
}

mkdir -p "$(dirname "$repo_dir")"

if [[ -d "${repo_dir}/.git" ]]; then
  git -C "$repo_dir" pull --ff-only
elif [[ -e "$repo_dir" ]]; then
  echo "target path exists and is not a git checkout: $repo_dir" >&2
  exit 1
else
  git clone "$repo_url" "$repo_dir"
fi

install_cmd=("$repo_dir/install.sh")
if [[ -n "$bin_dir" ]]; then
  install_cmd+=(--bin-dir "$bin_dir")
fi

"${install_cmd[@]}"
