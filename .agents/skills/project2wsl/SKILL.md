---
name: project2wsl
description: Use when the user wants to migrate, clone, copy, verify, or open a project in WSL instead of the Windows `/mnt/c` filesystem; triggers include project2wsl, WSL workspace performance warning, move project to WSL, copy project into WSL, open VS Code in WSL, create `~/projects` shortcuts, or manage multiple WSL project directories.
---

# Project to WSL

Use this skill to move project work out of Windows-mounted paths such as `/mnt/c/Users/...` and into the WSL Linux filesystem under `~/projects`, then open the result with VS Code Remote - WSL. The default deliverable is an opened VS Code window in WSL, not a long manual setup explanation.

## Defaults

- WSL distro: `Ubuntu`
- WSL project root: `~/projects`
- Existing AgentCube WSL path: `~/projects/agentcube`
- Prefer `git clone` for Git repositories whose useful work is already committed or pushed.
- Prefer `copy` only for local-only files, uncommitted experiments, non-Git projects, or large local assets.

## Script

Use the bundled script for repeatable operations:

```bash
bash .agents/skills/project2wsl/scripts/project2wsl.sh launch
bash .agents/skills/project2wsl/scripts/project2wsl.sh launch agentcube
bash .agents/skills/project2wsl/scripts/project2wsl.sh status
bash .agents/skills/project2wsl/scripts/project2wsl.sh clone https://github.com/ranxi2001/agentcube.git --name agentcube --branch intern --upstream https://github.com/volcano-sh/agentcube.git --open
bash .agents/skills/project2wsl/scripts/project2wsl.sh copy /mnt/c/Users/ranxi/Desktop/Project/my-project --name my-project --open
bash .agents/skills/project2wsl/scripts/project2wsl.sh open agentcube
bash .agents/skills/project2wsl/scripts/project2wsl.sh open agentcube --file internship-reports/如何在windows配置wsl开发环境.md
bash .agents/skills/project2wsl/scripts/project2wsl.sh shortcuts
```

The script can be launched from Windows Git Bash or from inside WSL. From Windows Git Bash, it reinvokes itself inside the target WSL distro.

For the user's normal AgentCube workflow, prefer:

```bash
bash .agents/skills/project2wsl/scripts/project2wsl.sh launch
```

This opens `~/projects/agentcube` in VS Code.

## Workflow

1. If the WSL project already exists, run `launch [name]` and stop after VS Code opens.
2. If it does not exist, choose a migration path:
   - Git repo with no important uncommitted Windows-only work: run `clone`.
   - Local-only project or uncommitted Windows files: run `copy` with a clear `--name`.
3. Verify the opened workspace:
   - `pwd` must start with `/home/<user>/projects/...`.
   - It must not start with `/mnt/c/...`.
   - VS Code lower-left indicator should show `WSL: Ubuntu`.
4. For Git projects, check `git status --short --branch` and `git remote -v`.
5. If the user wants less typing, run `shortcuts` to install `dev`, `ac`, `codeac`, `cdev`, and `mkdev` into WSL `~/.bashrc`.

## Safety Rules

- Do not delete or overwrite an existing WSL project directory unless the user explicitly asks and `--force` is supplied.
- Before using `copy` for a Git repo, check whether the Windows source has uncommitted changes. If it is clean and pushed, prefer `clone`.
- Keep official/upstream PR branches separate from local `intern` report work. For AgentCube, use `intern` for reports and local skills.
- Do not keep editing the Windows `/mnt/c/...` copy after migration, except as an archive or emergency backup.
- Do not push to upstream remotes from this skill; normal fork/upstream workflow rules still apply.

## Reference

Read `references/migration-decisions.md` when the user asks about clone vs copy tradeoffs, multiple projects, or how to recover from opening the wrong `/mnt/c` workspace.
