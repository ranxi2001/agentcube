# Project to WSL Migration Decisions

## Decision Table

| Situation | Preferred action |
| --- | --- |
| Git repo, clean worktree, remote has latest work | `clone` into `~/projects/<name>` |
| Git repo, uncommitted Windows-only work | commit/push first, or `copy` to a temporary WSL name |
| Non-Git project | `copy` |
| Large project or interrupted copy | use `copy --rsync` |
| Existing WSL project should be opened | `open <name>` |
| VS Code warns about `/mnt/` filesystem | close window, run `open <name>` from this skill |

## Recommended Layout

```text
/home/ranxi/projects/
  agentcube/
  other-project/
  experiments/
```

Avoid long-term editing in:

```text
/mnt/c/Users/ranxi/Desktop/Project/
```

## Verification

Inside VS Code terminal:

```bash
pwd
git status --short --branch
```

Good:

```text
/home/ranxi/projects/agentcube
```

Bad:

```text
/mnt/c/Users/ranxi/Desktop/Project/agentcube
```

## AgentCube Defaults

```bash
bash .agents/skills/project2wsl/scripts/project2wsl.sh clone \
  https://github.com/ranxi2001/agentcube.git \
  --name agentcube \
  --branch intern \
  --upstream https://github.com/volcano-sh/agentcube.git \
  --open
```

After migration:

```bash
cd ~/projects/agentcube
git remote -v
git switch intern
```
