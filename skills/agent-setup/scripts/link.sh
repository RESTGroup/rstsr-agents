#!/usr/bin/env bash
# Create the AI-agent symlinks for the RSTSR workflow (rstsr-agents convention).
#
# Creates, idempotently, relative to the target directory:
#   .claude   -> rstsr-agents            (Claude Code: skills + settings)
#   .agents   -> rstsr-agents            (agent-agnostic convention)
#   CLAUDE.md -> rstsr-agents/AGENTS.md  (Claude Code instruction entry)
#   AGENTS.md -> rstsr-agents/AGENTS.md  (Codex/OpenCode instruction entry)
#
# Usage:
#   link.sh [--target DIR] [--source DIR] [--check] [--force]
#
#   --target DIR   directory to place links in (default: current directory)
#   --source DIR   path to the rstsr-agents checkout. Default: `rstsr-agents`
#                  in the target directory, else `../rstsr-agents` (standard
#                  pack layout), else error.
#   --check        report what would be done, change nothing
#   --force        if a link name is taken by a REAL file/directory (e.g. the
#                  developer's own CLAUDE.md), move it to `<name>.agents-backup`
#                  and create the symlink. Without --force, real files abort.
#                  Existing symlinks are always re-pointed (with a report).
#
# Exit codes: 0 ok (or dry-run plan), 1 aborted, 2 bad usage.
set -euo pipefail

target="$PWD"
source_dir=""
check=0
force=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="${2:?}"; shift 2 ;;
    --source) source_dir="${2:?}"; shift 2 ;;
    --check)  check=1; shift ;;
    --force)  force=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "link.sh: unknown argument: $1 (see -h)" >&2; exit 2 ;;
  esac
done

if [[ ! -d "$target" ]]; then
  echo "link.sh: target directory does not exist: $target" >&2
  exit 2
fi
target="$(cd "$target" && pwd)"

# Resolve the rstsr-agents source.
if [[ -z "$source_dir" ]]; then
  if [[ -d "$target/rstsr-agents" ]]; then
    source_dir="$target/rstsr-agents"
  elif [[ -d "$target/../rstsr-agents" ]]; then
    source_dir="$target/../rstsr-agents"
  else
    echo "link.sh: cannot find rstsr-agents in '$target' or its parent;" \
         "pass --source /path/to/rstsr-agents" >&2
    exit 2
  fi
fi
source_dir="$(cd "$source_dir" && pwd)"
if [[ ! -f "$source_dir/AGENTS.md" ]]; then
  echo "link.sh: '$source_dir' does not look like rstsr-agents (no AGENTS.md)" >&2
  exit 2
fi

# Link target as a relative path from the target dir (keeps pack dirs movable).
# GNU realpath computes it directly; BSD realpath (macOS) has no --relative-to,
# so fall back to computing it in bash, then to the absolute path.
relpath() {
  # relpath FROM TO -> path of TO relative to FROM (both absolute, no trailing /)
  local -a f t
  local i n common=0 out=""
  IFS='/' read -r -a f <<<"${1#/}"
  IFS='/' read -r -a t <<<"${2#/}"
  n=$(( ${#f[@]} < ${#t[@]} ? ${#f[@]} : ${#t[@]} ))
  for ((i = 0; i < n; i++)); do
    [[ "${f[i]}" == "${t[i]}" ]] || break
    common=$((common + 1))
  done
  for ((i = common; i < ${#f[@]}; i++)); do out+="../"; done
  local IFS='/'
  printf '%s' "${out}${t[*]:common}"
}

if ! rel="$(realpath --relative-to="$target" "$source_dir" 2>/dev/null)"; then
  rel="$(relpath "$target" "$source_dir")"
  [[ -n "$rel" ]] || rel="$source_dir"  # identical dirs: absolute fallback
fi

want_for() {
  # Link name -> symlink target (relative to the target directory).
  case "$1" in
    .claude|.agents)      echo "$rel" ;;
    CLAUDE.md|AGENTS.md)  echo "$rel/AGENTS.md" ;;
  esac
}

aborted=0
for name in .claude .agents CLAUDE.md AGENTS.md; do
  want="$(want_for "$name")"
  path="$target/$name"
  if [[ -L "$path" ]]; then
    have="$(readlink "$path")"
    if [[ "$have" == "$want" ]]; then
      echo "  = $name -> $want (already correct)"
    else
      echo "  ~ $name: repointing symlink '$have' -> '$want'"
      (( check )) || ln -sfn "$want" "$path"
    fi
  elif [[ -e "$path" ]]; then
    if (( force )); then
      echo "  ! $name: real file exists; moving to $name.agents-backup"
      (( check )) || mv "$path" "$path.agents-backup"
      (( check )) || ln -s "$want" "$path"
    else
      echo "  x $name: exists and is not a symlink; refusing (use --force to" \
           "move it to $name.agents-backup, or resolve manually)" >&2
      aborted=1
    fi
  else
    echo "  + $name -> $want"
    (( check )) || ln -s "$want" "$path"
  fi
done

if (( aborted )); then
  echo "link.sh: aborted - some link names are taken by real files." >&2
  exit 1
fi
echo "link.sh: done ($( [[ $check -eq 1 ]] && echo 'dry run' || echo 'links updated' )) in $target"
