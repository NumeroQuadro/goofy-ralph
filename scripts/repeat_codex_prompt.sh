#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Repeat the same prompt against local `codex exec` or `opencode run` multiple times.

Usage:
  scripts/repeat_codex_prompt.sh --prompt "Your prompt" [options] [-- <extra codex exec args>]
  scripts/repeat_codex_prompt.sh --prompt-file prompt.txt [options]
  cat prompt.txt | scripts/repeat_codex_prompt.sh [options]

Options:
  --backend BACKEND        Runner to use: codex or opencode (default: codex).
  --prompt TEXT            Prompt text to send each run.
  --prompt-file PATH       Read prompt text from file.
  --count N                Number of runs (default: 3).
  --delay SECONDS          Sleep between runs (default: 0).
  --model MODEL            Pass model to the selected backend.
  --profile PROFILE        Pass profile to codex exec (-p).
  --agent AGENT            Pass agent to opencode run (--agent).
  --cd DIR                 Run the backend inside DIR.
  --out-dir DIR            Save last message per run as run_###.txt.
  --continue-on-error      Continue remaining runs if one fails.
  --dry-run                Print commands without executing.
  -h, --help               Show this help.

Examples:
  scripts/repeat_codex_prompt.sh \
    --prompt "review this repo and list TODOs" \
    --count 5 \
    --delay 1 \
    --out-dir runs/repeat

  scripts/repeat_codex_prompt.sh \
    --prompt-file prompt.txt \
    --count 10 \
    --model gpt-5 \
    -- --json

  scripts/repeat_codex_prompt.sh \
    --backend opencode \
    --agent build \
    --prompt "review this repo and list TODOs"
EOF
}

backend="codex"
prompt=""
prompt_file=""
count=3
delay=0
model=""
profile=""
agent=""
workdir=""
out_dir=""
continue_on_error=0
dry_run=0
extra_args=()
loop_id="$(date -u +%Y%m%dT%H%M%SZ)-pid$$"
prompt_source="unspecified"

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

color_mode="${RALPH_COLOR:-auto}"
use_color=0
C_RESET=""
C_DIM=""
C_RED=""

supports_truecolor() {
  case "${COLORTERM:-}" in
    *truecolor*|*24bit*)
      return 0
      ;;
  esac

  case "${TERM:-}" in
    *-direct*)
      return 0
      ;;
  esac

  return 1
}

ansi_fg_rgb() {
  printf '\033[38;2;%s;%s;%sm' "$1" "$2" "$3"
}

ansi_fg_256() {
  printf '\033[38;5;%sm' "$1"
}

configure_colors() {
  local normalized=""

  if [[ -n "${NO_COLOR+x}" ]]; then
    use_color=0
    return
  fi

  normalized="$(to_lower "$color_mode")"
  case "$normalized" in
    auto|"")
      if [[ -t 1 && "${TERM:-}" != "dumb" ]]; then
        use_color=1
      else
        use_color=0
      fi
      ;;
    always|force|yes|true|1)
      use_color=1
      ;;
    never|no|false|0)
      use_color=0
      ;;
    *)
      use_color=0
      ;;
  esac

  if ((use_color)); then
    C_RESET=$'\033[0m'
    if supports_truecolor; then
      # Gruvbox-ish palette (truecolor).
      C_DIM="$(ansi_fg_rgb 146 131 116)" # #928374
      C_RED="$(ansi_fg_rgb 251 73 52)"   # #fb4934
    else
      # Gruvbox-ish palette (256-color fallback).
      C_DIM="$(ansi_fg_256 243)"
      C_RED="$(ansi_fg_256 167)"
    fi
  else
    C_RESET=""
    C_DIM=""
    C_RED=""
  fi
}

configure_colors

log_stdout() {
  printf '%sloop_id=%s%s %s\n' "$C_DIM" "$loop_id" "$C_RESET" "$*"
}

log_stderr() {
  printf '%sloop_id=%s %s%s\n' "$C_RED" "$loop_id" "$*" "$C_RESET" >&2
}

describe_cmd() {
  local rendered=()
  local part=""

  for part in "$@"; do
    rendered+=("$(printf '%q' "$part")")
  done

  printf '%s' "${rendered[*]}"
}

require_value() {
  local flag="$1"

  [[ $# -ge 2 ]] || {
    log_stderr "error missing value for ${flag}"
    exit 2
  }
}

while (($# > 0)); do
  case "$1" in
    --backend=*)
      backend="${1#*=}"
      shift
      ;;
    --backend)
      require_value "$1" "$@"
      backend="$2"
      shift 2
      ;;
    --prompt=*)
      prompt="${1#*=}"
      prompt_source="flag"
      shift
      ;;
    --prompt)
      require_value "$1" "$@"
      prompt="$2"
      prompt_source="flag"
      shift 2
      ;;
    --prompt-file=*)
      prompt_file="${1#*=}"
      prompt_source="file:${prompt_file}"
      shift
      ;;
    --prompt-file)
      require_value "$1" "$@"
      prompt_file="$2"
      prompt_source="file:${prompt_file}"
      shift 2
      ;;
    --count=*)
      count="${1#*=}"
      shift
      ;;
    --count)
      require_value "$1" "$@"
      count="$2"
      shift 2
      ;;
    --delay=*)
      delay="${1#*=}"
      shift
      ;;
    --delay)
      require_value "$1" "$@"
      delay="$2"
      shift 2
      ;;
    --model=*)
      model="${1#*=}"
      shift
      ;;
    --model)
      require_value "$1" "$@"
      model="$2"
      shift 2
      ;;
    --profile=*)
      profile="${1#*=}"
      shift
      ;;
    --profile)
      require_value "$1" "$@"
      profile="$2"
      shift 2
      ;;
    --agent=*)
      agent="${1#*=}"
      shift
      ;;
    --agent)
      require_value "$1" "$@"
      agent="$2"
      shift 2
      ;;
    --cd=*)
      workdir="${1#*=}"
      shift
      ;;
    --cd)
      require_value "$1" "$@"
      workdir="$2"
      shift 2
      ;;
    --out-dir=*)
      out_dir="${1#*=}"
      shift
      ;;
    --out-dir)
      require_value "$1" "$@"
      out_dir="$2"
      shift 2
      ;;
    --continue-on-error)
      continue_on_error=1
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      extra_args=("$@")
      break
      ;;
    *)
      log_stderr "error unknown argument: $1"
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "$prompt" && -n "$prompt_file" ]]; then
  log_stderr "error use either --prompt or --prompt-file, not both"
  exit 2
fi

if ! [[ "$count" =~ ^[1-9][0-9]*$ ]]; then
  log_stderr "error --count must be an integer >= 1"
  exit 2
fi

case "$backend" in
  codex|opencode)
    ;;
  *)
    log_stderr "error --backend must be codex or opencode"
    exit 2
    ;;
esac

if ((dry_run == 0)) && ! command -v "$backend" >/dev/null 2>&1; then
  log_stderr "error backend command not found on PATH: $backend"
  exit 127
fi

if [[ "$backend" == "codex" && -n "$agent" ]]; then
  log_stderr "error --agent is only supported with --backend opencode"
  exit 2
fi

if [[ "$backend" == "opencode" && -n "$profile" ]]; then
  log_stderr "error --profile is only supported with --backend codex"
  exit 2
fi

prompt_text=""
if [[ -n "$prompt_file" ]]; then
  if [[ ! -f "$prompt_file" ]]; then
    log_stderr "error prompt file not found: $prompt_file"
    exit 2
  fi
  prompt_text="$(cat "$prompt_file")"
  if [[ ! "$prompt_text" =~ [^[:space:]] ]]; then
    log_stderr "warning: prompt file is empty"
    exit 2
  fi
elif [[ -n "$prompt" ]]; then
  prompt_text="$prompt"
elif [[ ! -t 0 ]]; then
  prompt_text="$(cat)"
  prompt_source="stdin"
else
  log_stderr "error provide --prompt or --prompt-file (or pipe prompt via stdin)"
  exit 2
fi

if [[ -n "$out_dir" ]]; then
  mkdir -p "$out_dir"
fi

log_stdout \
  "loop_start backend=${backend} total_runs=${count} prompt_source=${prompt_source} prompt_chars=${#prompt_text} continue_on_error=${continue_on_error} dry_run=${dry_run}"

for ((i = 1; i <= count; i++)); do
  iteration="${i}/${count}"
  log_stdout "iteration_start iteration=${iteration} current=${i} total=${count}"

  cmd=()
  cmd_for_log=()
  command_log_name="${backend}_command"
  execution_workdir="${workdir:-$(pwd)}"
  use_stdout_capture=0

  case "$backend" in
    codex)
      cmd=(codex exec)
      cmd_for_log=(codex exec)
      [[ -n "$model" ]] && {
        cmd+=(-m "$model")
        cmd_for_log+=(-m "$model")
      }
      [[ -n "$profile" ]] && {
        cmd+=(-p "$profile")
        cmd_for_log+=(-p "$profile")
      }
      [[ -n "$workdir" ]] && {
        cmd+=(-C "$workdir")
        cmd_for_log+=(-C "$workdir")
      }
      if ((${#extra_args[@]} > 0)); then
        cmd+=("${extra_args[@]}")
        cmd_for_log+=("${extra_args[@]}")
      fi
      ;;
    opencode)
      cmd=(opencode run)
      cmd_for_log=(opencode run)
      [[ -n "$model" ]] && {
        cmd+=(--model "$model")
        cmd_for_log+=(--model "$model")
      }
      [[ -n "$agent" ]] && {
        cmd+=(--agent "$agent")
        cmd_for_log+=(--agent "$agent")
      }
      if ((${#extra_args[@]} > 0)); then
        cmd+=("${extra_args[@]}")
        cmd_for_log+=("${extra_args[@]}")
      fi
      cmd+=("$prompt_text")
      cmd_for_log+=("PROMPT_TEXT")
      use_stdout_capture=1
      ;;
  esac

  run_output=""
  if [[ -n "$out_dir" ]]; then
    printf -v run_num "%03d" "$i"
    run_output="${out_dir}/run_${run_num}.txt"
    if [[ "$backend" == "codex" ]]; then
      cmd+=(-o "$run_output")
      cmd_for_log+=(-o "$run_output")
    fi
  fi
  if [[ "$backend" == "codex" ]]; then
    cmd+=(-)
    cmd_for_log+=(-)
  fi

  log_stdout "workdir=${execution_workdir} out_dir=${out_dir:-<none>} run_output=${run_output:-<none>}"
  log_stdout "${command_log_name} $(describe_cmd "${cmd_for_log[@]}")"

  if ((dry_run)); then
    log_stdout "iteration_dry_run iteration=${iteration} current=${i} total=${count}"
  else
    set +e
    case "$backend" in
      codex)
        printf '%s\n' "$prompt_text" | "${cmd[@]}"
        status=$?
        ;;
      opencode)
        if ((use_stdout_capture)) && [[ -n "$run_output" ]]; then
          (
            cd "$execution_workdir"
            "${cmd[@]}"
          ) | tee "$run_output"
          status=$?
        else
          (
            cd "$execution_workdir"
            "${cmd[@]}"
          )
          status=$?
        fi
        ;;
    esac
    set -e

    if ((status != 0)); then
      log_stderr "iteration_failed iteration=${iteration} current=${i} total=${count} exit_status=${status}"
      if ((continue_on_error == 0)); then
        exit "$status"
      fi
    else
      log_stdout "iteration_done iteration=${iteration} current=${i} total=${count}"
    fi
  fi

  if ((i < count)); then
    log_stdout "next_iteration=$((i + 1))/${count} delay_seconds=${delay}"
    sleep "$delay"
  fi
done

log_stdout "loop_done total_runs=${count}"
