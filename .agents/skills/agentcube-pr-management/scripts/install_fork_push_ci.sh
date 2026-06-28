#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
if [[ -z "${branch}" ]]; then
  echo "error: detached HEAD is not supported" >&2
  exit 1
fi

case "${branch}" in
  main|intern)
    echo "error: do not install fork push CI on ${branch}; create a ci/<topic> validation branch first" >&2
    exit 1
    ;;
esac

case "${branch}" in
  ci/*|test/*|feat/*|fix/*|chore/*|docs/*)
    ;;
  *)
    echo "warning: branch ${branch} is not matched by the fork push CI branch filters" >&2
    echo "warning: use ci/<topic>, test/<topic>, feat/<topic>, fix/<topic>, chore/<topic>, or docs/<topic>" >&2
    ;;
esac

repo_root="$(git rev-parse --show-toplevel)"
template_rel=".agents/skills/agentcube-pr-management/templates/fork-push-validation.yml"
template="${repo_root}/${template_rel}"
target="${repo_root}/.github/workflows/fork-push-validation.yml"

mkdir -p "$(dirname "${target}")"
if [[ -f "${template}" ]]; then
  cp "${template}" "${target}"
elif git cat-file -e "intern:${template_rel}" 2>/dev/null; then
  git show "intern:${template_rel}" > "${target}"
else
  echo "error: cannot find ${template_rel} in the worktree or local intern branch" >&2
  echo "hint: fetch/switch the intern branch first, or copy the workflow template manually" >&2
  exit 1
fi

git add "${target}"
if git diff --cached --quiet -- "${target}"; then
  echo "fork push CI workflow is already installed on ${branch}"
  exit 0
fi

git commit -s -m "ci: add fork push validation workflow"

echo "installed fork push CI workflow on ${branch}"
echo "next: git push origin ${branch}:${branch}"
