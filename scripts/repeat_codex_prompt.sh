#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Repeat the same prompt against local `codex exec` multiple times.

Usage:
  scripts/repeat_codex_prompt.sh --prompt "Your prompt" [options] [-- <extra codex exec args>]
  scripts/repeat_codex_prompt.sh --prompt-file prompt.txt [options]
  cat prompt.txt | scripts/repeat_codex_prompt.sh [options]

Options:
  --prompt TEXT            Prompt text to send each run.
  --prompt-file PATH       Read prompt text from file.
  --count N                Number of runs (default: 3).
  --delay SECONDS          Sleep between runs (default: 0).
  --model MODEL            Pass model to codex exec (-m).
  --profile PROFILE        Pass profile to codex exec (-p).
  --cd DIR                 Pass working directory to codex exec (-C).
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
EOF
}

prompt=""
prompt_file=""
count=3
delay=0
model=""
profile=""
workdir=""
out_dir=""
continue_on_error=0
dry_run=0
extra_args=()
loop_id="$(date -u +%Y%m%dT%H%M%SZ)-pid$$"
prompt_source="unspecified"

log_stdout() {
  printf 'loop_id=%s %s\n' "$loop_id" "$*"
}

log_stderr() {
  printf 'loop_id=%s %s\n' "$loop_id" "$*" >&2
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
  "loop_start total_runs=${count} prompt_source=${prompt_source} prompt_chars=${#prompt_text} continue_on_error=${continue_on_error} dry_run=${dry_run}"

for ((i = 1; i <= count; i++)); do
  iteration="${i}/${count}"
  log_stdout "iteration_start iteration=${iteration} current=${i} total=${count}"

  cmd=(codex exec)
  [[ -n "$model" ]] && cmd+=(-m "$model")
  [[ -n "$profile" ]] && cmd+=(-p "$profile")
  [[ -n "$workdir" ]] && cmd+=(-C "$workdir")
  cmd+=("${extra_args[@]}")

  run_output=""
  if [[ -n "$out_dir" ]]; then
    printf -v run_num "%03d" "$i"
    run_output="${out_dir}/run_${run_num}.txt"
    cmd+=(-o "$run_output")
  fi
  cmd+=(-)

  log_stdout "workdir=${workdir:-<inherit>} out_dir=${out_dir:-<none>} run_output=${run_output:-<none>}"
  log_stdout "codex_command $(describe_cmd "${cmd[@]}")"

  if ((dry_run)); then
    log_stdout "iteration_dry_run iteration=${iteration} current=${i} total=${count}"
  else
    set +e
    printf '%s\n' "$prompt_text" | "${cmd[@]}"
    status=$?
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
