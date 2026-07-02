#!/usr/bin/env bash
set -euo pipefail

DEFAULT_DISTRO="Ubuntu"
DEFAULT_PROJECTS_DIR="$HOME/projects"

usage() {
  cat <<'EOF'
Usage:
  project2wsl.sh launch [name] [--file RELATIVE_FILE]
  project2wsl.sh status [--distro Ubuntu] [--projects-dir ~/projects]
  project2wsl.sh clone <repo-url> [--name NAME] [--branch BRANCH] [--upstream URL] [--open]
  project2wsl.sh copy <source-path> [--name NAME] [--rsync] [--force] [--open]
  project2wsl.sh open <name> [--file RELATIVE_FILE]
  project2wsl.sh shortcuts

Examples:
  project2wsl.sh launch
  project2wsl.sh launch agentcube
  project2wsl.sh status
  project2wsl.sh clone https://github.com/ranxi2001/agentcube.git --name agentcube --branch intern --upstream https://github.com/volcano-sh/agentcube.git --open
  project2wsl.sh copy /mnt/c/Users/ranxi/Desktop/Project/my-project --name my-project --open
  project2wsl.sh open agentcube --file internship-reports/如何在windows配置wsl开发环境.md
EOF
}

is_wsl() {
  grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null
}

host_abs_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$(pwd)" "$path"
  fi
}

host_path_to_wsl_path() {
  local path="$1"
  if [[ "$path" =~ ^/([A-Za-z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    printf '/mnt/%s/%s\n' "$drive" "${BASH_REMATCH[2]}"
  elif [[ "$path" =~ ^/cygdrive/([A-Za-z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    printf '/mnt/%s/%s\n' "$drive" "${BASH_REMATCH[2]}"
  elif [[ "$path" =~ ^([A-Za-z]):[\\/](.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    local rest="${BASH_REMATCH[2]//\\//}"
    printf '/mnt/%s/%s\n' "$drive" "$rest"
  else
    echo "error: cannot convert host path to WSL path: $path" >&2
    exit 1
  fi
}

reinvoke_in_wsl_if_needed() {
  if is_wsl; then
    return 0
  fi
  if ! command -v wsl.exe >/dev/null 2>&1; then
    echo "error: this script must run inside WSL or from Windows with wsl.exe on PATH" >&2
    exit 1
  fi

  local distro="$DEFAULT_DISTRO"
  local original_args=("$@")
  local arg
  while [[ $# -gt 0 ]]; do
    arg="$1"
    case "$arg" in
      --distro) distro="${2:-$DEFAULT_DISTRO}"; shift 2 ;;
      --distro=*) distro="${arg#--distro=}"; shift ;;
      *) shift ;;
    esac
  done

  local script_host script_win script_wsl
  script_host="$(host_abs_path "$0")"
  script_wsl="$(host_path_to_wsl_path "$script_host")"

  MSYS_NO_PATHCONV=1 wsl.exe -d "$distro" -- bash "$script_wsl" "${original_args[@]}"
  exit $?
}

expand_home() {
  local path="$1"
  if [[ "$path" == "~" ]]; then
    printf '%s\n' "$HOME"
  elif [[ "$path" == "~/"* ]]; then
    printf '%s/%s\n' "$HOME" "${path#~/}"
  else
    printf '%s\n' "$path"
  fi
}

to_wsl_path() {
  local path="$1"
  if [[ "$path" =~ ^[A-Za-z]:[\\/] ]]; then
    wslpath -u "$path"
  elif [[ "$path" =~ ^/([A-Za-z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    printf '/mnt/%s/%s\n' "$drive" "${BASH_REMATCH[2]}"
  else
    printf '%s\n' "$path"
  fi
}

project_name_from_repo() {
  local repo="$1"
  repo="${repo%.git}"
  repo="${repo%/}"
  printf '%s\n' "${repo##*/}"
}

safe_destination() {
  local projects_dir="$1"
  local name="$2"
  if [[ -z "$name" || "$name" == "." || "$name" == ".." || "$name" == */* ]]; then
    echo "error: invalid project name: $name" >&2
    exit 1
  fi
  printf '%s/%s\n' "$projects_dir" "$name"
}

assert_under_projects() {
  local projects_dir="$1"
  local dest="$2"
  local projects_real dest_parent
  mkdir -p "$projects_dir"
  projects_real="$(realpath "$projects_dir")"
  dest_parent="$(realpath "$(dirname "$dest")")"
  if [[ "$dest_parent" != "$projects_real" ]]; then
    echo "error: destination must be directly under $projects_real" >&2
    exit 1
  fi
}

run_status() {
  local projects_dir="$1"
  echo "wsl_user=$(whoami)"
  echo "home=$HOME"
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "os=$PRETTY_NAME"
  fi
  echo "projects_dir=$projects_dir"
  mkdir -p "$projects_dir"
  for tool in git code wslpath rsync; do
    if command -v "$tool" >/dev/null 2>&1; then
      printf '%s=%s\n' "$tool" "$(command -v "$tool")"
    else
      printf '%s=missing\n' "$tool"
    fi
  done
  echo "projects:"
  find "$projects_dir" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' 2>/dev/null | sort || true
}

run_clone() {
  local repo="$1" projects_dir="$2" name="$3" branch="$4" upstream="$5" open_after="$6"
  if [[ -z "$name" ]]; then
    name="$(project_name_from_repo "$repo")"
  fi
  local dest
  dest="$(safe_destination "$projects_dir" "$name")"
  mkdir -p "$projects_dir"
  assert_under_projects "$projects_dir" "$dest"

  if [[ -d "$dest/.git" ]]; then
    echo "repo already exists: $dest"
  elif [[ -e "$dest" ]]; then
    echo "error: destination exists and is not a Git repo: $dest" >&2
    exit 1
  else
    git clone "$repo" "$dest"
  fi

  cd "$dest"
  if [[ -n "$upstream" ]] && ! git remote get-url upstream >/dev/null 2>&1; then
    git remote add upstream "$upstream"
  fi
  git fetch --all --prune
  if [[ -n "$branch" ]]; then
    git switch "$branch" 2>/dev/null || git switch -c "$branch" "origin/$branch"
  fi
  git status --short --branch
  if [[ "$open_after" == "1" ]]; then
    code .
  fi
}

run_copy() {
  local source="$1" projects_dir="$2" name="$3" use_rsync="$4" force="$5" open_after="$6"
  local source_wsl
  source_wsl="$(to_wsl_path "$source")"
  if [[ ! -e "$source_wsl" ]]; then
    echo "error: source does not exist in WSL: $source_wsl" >&2
    exit 1
  fi
  if [[ -z "$name" ]]; then
    name="$(basename "$source_wsl")"
  fi
  local dest
  dest="$(safe_destination "$projects_dir" "$name")"
  mkdir -p "$projects_dir"
  assert_under_projects "$projects_dir" "$dest"

  if [[ -e "$dest" ]]; then
    if [[ "$force" != "1" ]]; then
      echo "error: destination exists: $dest" >&2
      echo "Use --name for a new directory or --force to replace it." >&2
      exit 1
    fi
    rm -rf "$dest"
  fi

  if [[ "$use_rsync" == "1" ]]; then
    if ! command -v rsync >/dev/null 2>&1; then
      echo "error: rsync is not installed in WSL" >&2
      echo "Install with: sudo apt-get update && sudo apt-get install -y rsync" >&2
      exit 1
    fi
    mkdir -p "$dest"
    rsync -a --info=progress2 "${source_wsl%/}/" "$dest/"
  else
    cp -a "$source_wsl" "$dest"
  fi

  cd "$dest"
  pwd
  if [[ -d .git ]]; then
    git status --short --branch || true
  fi
  if [[ "$open_after" == "1" ]]; then
    code .
  fi
}

run_open() {
  local projects_dir="$1" name="$2" file="$3"
  local dest
  dest="$(safe_destination "$projects_dir" "$name")"
  if [[ ! -d "$dest" ]]; then
    echo "error: project not found: $dest" >&2
    exit 1
  fi
  cd "$dest"
  if [[ -n "$file" ]]; then
    code "$file"
  else
    code .
  fi
}

run_launch() {
  local projects_dir="$1" name="$2" file="$3"
  if [[ -z "$name" ]]; then
    name="$(basename "$(pwd)")"
  fi
  if [[ "$name" == "scripts" || "$name" == "project2wsl" || "$name" == ".agents" ]]; then
    name="agentcube"
  fi
  run_open "$projects_dir" "$name" "$file"
}

run_shortcuts() {
  local marker="# project2wsl shortcuts"
  if grep -q "$marker" "$HOME/.bashrc" 2>/dev/null; then
    echo "shortcuts already installed in ~/.bashrc"
    return 0
  fi
  cat >> "$HOME/.bashrc" <<'EOF'

# project2wsl shortcuts
alias dev='cd ~/projects'
alias ac='cd ~/projects/agentcube'
alias codeac='cd ~/projects/agentcube && code .'

cdev() {
  if [ -z "${1:-}" ]; then
    echo "usage: cdev <project-dir-under-~/projects>" >&2
    return 2
  fi
  cd "$HOME/projects/$1" && code .
}

mkdev() {
  if [ -z "${1:-}" ]; then
    echo "usage: mkdev <project-dir-under-~/projects>" >&2
    return 2
  fi
  mkdir -p "$HOME/projects/$1"
  cd "$HOME/projects/$1"
}
EOF
  echo "installed shortcuts into ~/.bashrc"
  echo "run: source ~/.bashrc"
}

main() {
  local cmd="${1:-}"
  if [[ -z "$cmd" || "$cmd" == "-h" || "$cmd" == "--help" ]]; then
    usage
    exit 0
  fi

  reinvoke_in_wsl_if_needed "$@"

  shift || true

  local distro="$DEFAULT_DISTRO"
  local projects_dir="$DEFAULT_PROJECTS_DIR"
  local branch="" upstream="" name="" file=""
  local open_after="0" force="0" use_rsync="0"

  case "$cmd" in
    status)
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --distro) distro="$2"; shift 2 ;;
          --distro=*) distro="${1#--distro=}"; shift ;;
          --projects-dir) projects_dir="$2"; shift 2 ;;
          --projects-dir=*) projects_dir="${1#--projects-dir=}"; shift ;;
          *) echo "error: unknown argument for status: $1" >&2; exit 1 ;;
        esac
      done
      projects_dir="$(expand_home "$projects_dir")"
      run_status "$projects_dir"
      ;;
    launch)
      if [[ $# -gt 0 && "$1" != --* ]]; then
        name="$1"
        shift
      else
        name="$(basename "$(pwd)")"
      fi
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --file) file="$2"; shift 2 ;;
          --file=*) file="${1#--file=}"; shift ;;
          --projects-dir) projects_dir="$2"; shift 2 ;;
          --projects-dir=*) projects_dir="${1#--projects-dir=}"; shift ;;
          --distro) shift 2 ;;
          --distro=*) shift ;;
          *) echo "error: unknown argument for launch: $1" >&2; exit 1 ;;
        esac
      done
      projects_dir="$(expand_home "$projects_dir")"
      run_launch "$projects_dir" "$name" "$file"
      ;;
    clone)
      if [[ $# -lt 1 ]]; then usage; exit 1; fi
      local repo="$1"
      shift
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --name) name="$2"; shift 2 ;;
          --name=*) name="${1#--name=}"; shift ;;
          --branch) branch="$2"; shift 2 ;;
          --branch=*) branch="${1#--branch=}"; shift ;;
          --upstream) upstream="$2"; shift 2 ;;
          --upstream=*) upstream="${1#--upstream=}"; shift ;;
          --open) open_after="1"; shift ;;
          --projects-dir) projects_dir="$2"; shift 2 ;;
          --projects-dir=*) projects_dir="${1#--projects-dir=}"; shift ;;
          --distro) shift 2 ;;
          --distro=*) shift ;;
          *) echo "error: unknown argument for clone: $1" >&2; exit 1 ;;
        esac
      done
      projects_dir="$(expand_home "$projects_dir")"
      run_clone "$repo" "$projects_dir" "$name" "$branch" "$upstream" "$open_after"
      ;;
    copy)
      if [[ $# -lt 1 ]]; then usage; exit 1; fi
      local source="$1"
      shift
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --name) name="$2"; shift 2 ;;
          --name=*) name="${1#--name=}"; shift ;;
          --rsync) use_rsync="1"; shift ;;
          --force) force="1"; shift ;;
          --open) open_after="1"; shift ;;
          --projects-dir) projects_dir="$2"; shift 2 ;;
          --projects-dir=*) projects_dir="${1#--projects-dir=}"; shift ;;
          --distro) shift 2 ;;
          --distro=*) shift ;;
          *) echo "error: unknown argument for copy: $1" >&2; exit 1 ;;
        esac
      done
      projects_dir="$(expand_home "$projects_dir")"
      run_copy "$source" "$projects_dir" "$name" "$use_rsync" "$force" "$open_after"
      ;;
    open)
      if [[ $# -lt 1 ]]; then usage; exit 1; fi
      name="$1"
      shift
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --file) file="$2"; shift 2 ;;
          --file=*) file="${1#--file=}"; shift ;;
          --projects-dir) projects_dir="$2"; shift 2 ;;
          --projects-dir=*) projects_dir="${1#--projects-dir=}"; shift ;;
          --distro) shift 2 ;;
          --distro=*) shift ;;
          *) echo "error: unknown argument for open: $1" >&2; exit 1 ;;
        esac
      done
      projects_dir="$(expand_home "$projects_dir")"
      run_open "$projects_dir" "$name" "$file"
      ;;
    shortcuts)
      run_shortcuts
      ;;
    *)
      echo "error: unknown command: $cmd" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
