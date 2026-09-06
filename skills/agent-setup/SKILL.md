---
name: agent-setup
description: Bootstrap or repair the rstsr agent symlinks (.claude, .agents, CLAUDE.md, AGENTS.md -> rstsr-agents) in a repository checkout or pack root. Use when setting up a new checkout, when skills or instructions are not discovered, or when links dangle after moving or renaming directories.
---

# agent-setup: symlink bootstrap for the rstsr agent workflow

Every rstsr repository carries four gitignored symlinks pointing at the sibling
`rstsr-agents` repository; this skill creates and repairs them with its script.

| Symlink | Points to | Consumer |
| --- | --- | --- |
| `.claude` | `rstsr-agents` | Claude Code: skill discovery, `settings.json` |
| `.agents` | `rstsr-agents` | agent-agnostic convention |
| `CLAUDE.md` | `rstsr-agents/AGENTS.md` | Claude Code instruction entry |
| `AGENTS.md` | `rstsr-agents/AGENTS.md` | Codex, OpenCode, other AGENTS.md-aware tools |

Relative links keep the pack directory movable as a whole. Full rationale and
troubleshooting: `README.md` of rstsr-agents.

## Usage

```bash
# in a repository of the standard pack layout (rstsr-agents as a sibling):
../rstsr-agents/skills/agent-setup/scripts/link.sh

# at the pack root (auto-detects ./rstsr-agents):
rstsr-agents/skills/agent-setup/scripts/link.sh

# standalone checkout (rstsr-agents cloned anywhere):
bash /path/to/rstsr-agents/skills/agent-setup/scripts/link.sh --source /path/to/rstsr-agents
```

Run it once per repository, and once at the pack root if sessions are opened
there. It is idempotent: correct links are skipped, foreign symlinks are
re-pointed with a report, `--check` dry-runs.

## Safety rules

- A **real file** occupying a link name (e.g. the developer's own `CLAUDE.md`)
  is **refused** - never overwrite it. With `--force` it is moved to
  `<name>.agents-backup` first. Say what you are about to replace and why.
- Symlink creation needs no special confirmation; report what was created.

## When things look broken

- Skills or instructions not discovered: `ls .claude/skills/` through the
  symlink; if it fails, re-run this script (it repoints dangling links), then
  restart the agent session.
- After moving or renaming the pack directory: re-run this script per
  repository with `--check` first.
