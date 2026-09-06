# rstsr-agents

Shared AI code-agent workflow for the RSTSR ecosystem: one repository holding the
agent instructions (`AGENTS.md`), operational skills (`skills/`), and reference
rules (`rules/`), consumed by every rstsr repository through symlinks.

Rationale: see ADR-0001 in `rstsr-book/dev/adr/` (symlink to a single source
instead of per-repo copies that drift).

## Repository layout

```
rstsr-agents/
├── AGENTS.md                  # shared instruction entry (read first by agents)
├── README.md                  # this file (human-facing setup, not for agents)
├── settings.json              # committed Claude Code baseline (permissions)
├── rules/                     # reference material agents read on demand
│   └── code-concepts.md       #   rstsr-core types & naming conventions
└── skills/                    # task-dependent instructions (SKILL.md each)
    ├── agent-setup/           #   bootstrap the symlinks (scripts/link.sh) - see "Setup"
    ├── cargo-inst/            #   build / test / doc / fmt / clippy commands
    ├── test-conventions/      #   rstsr-core test conventions (read before core-test)
    ├── core-test/             #   author parity test + doc test + docstring
    ├── core-issue-regression/ #   regression test for a reported issue
    ├── core-numpy-sync/       #   NumPy test-surface drift detection
    ├── core-col-major-transfer/ # (stub, deferred)
    ├── crate-publish/         #   rstsr release via release-plz
    └── git-commit-coauthor/   #   commit trailers + PR template (+ coauthor.sh)
```

## How agents consume this repository

All rstsr repositories carry the same four gitignored symlinks:

| Symlink | Points to | Consumer |
| --- | --- | --- |
| `.claude` | `rstsr-agents` | Claude Code: skill discovery (`.claude/skills/`), `settings.json` |
| `.agents` | `rstsr-agents` | agent-agnostic convention |
| `CLAUDE.md` | `rstsr-agents/AGENTS.md` | Claude Code instruction entry |
| `AGENTS.md` | `rstsr-agents/AGENTS.md` | Codex, OpenCode, and other AGENTS.md-aware tools |

Relative links (`../rstsr-agents` from a repo, `rstsr-agents` from the pack root)
keep the pack directory movable as a whole. Claude Code additionally discovers
`settings.json` / `settings.local.json` through the `.claude` symlink.

## Setup

### Pack layout (recommended)

Put the repositories as siblings in one folder:

```
rstsr-pack/
├── rstsr/
├── rstsr-ffi/
├── rstsr-book/
├── rstsr-agents/
└── (your notes, workspace file, ...)
```

Then, once per repository **and** once at the pack root. The bootstrap is
packaged as the `agent-setup` skill - Claude Code users can simply invoke that
skill; the script lives at `skills/agent-setup/scripts/link.sh`:

```bash
link=../rstsr-agents/skills/agent-setup/scripts/link.sh
cd rstsr-pack/rstsr      && $link
cd rstsr-pack/rstsr-book && $link
cd rstsr-pack/rstsr-ffi  && $link
cd rstsr-pack && rstsr-agents/skills/agent-setup/scripts/link.sh   # pack root
```

The script is idempotent: existing correct links are skipped, foreign symlinks are
re-pointed with a report, and a **real file** occupying a link name (e.g. your own
`CLAUDE.md`) is refused unless `--force` (which moves it to `<name>.agents-backup`).
`--check` dry-runs. `--source /path/to/rstsr-agents` overrides auto-detection.

### Standalone checkout

A single repository (e.g. only `rstsr`) works too - clone `rstsr-agents` anywhere
and point the links at it:

```bash
git clone https://github.com/RESTGroup/rstsr-agents.git ../somewhere/rstsr-agents
../somewhere/rstsr-agents/skills/agent-setup/scripts/link.sh --target .
```

Note for standalone use: cross-repo references shrink. `../rstsr-book/` paths
assume the pack layout and will not resolve standalone. Reference-checkout
locations (NumPy/SciPy/array-api clones, used by the test skills) are
per-developer in any layout: record yours in `AGENTS.local.md` (e.g.
`Reference checkouts: /path/to/dir`).

## Local configuration: the `*.local` convention

Every rstsr repository (and this one) gitignores the catch-all pattern `*.local*`.
Anything suffixed `.local` is yours alone - safe to create in any repo directory,
never committed. Two uses in this workflow:

- `settings.local.json` - personal Claude Code settings. Drop it **here**, in
  `rstsr-agents/`; through the `.claude` symlink Claude Code reads it as
  `.claude/settings.local.json`, and the catch-all keeps it uncommitted. The
  committed `settings.json` is the team-wide baseline (a conservative allowlist);
  extend it locally, not globally:

  ```json
  {
    "permissions": {
      "allow": [
        "Bash(npm run build:*)",
        "Bash(gh run list:*)"
      ]
    }
  }
  ```
- `AGENTS.local.md` - per-developer supplement/override at a repository root.
  `AGENTS.md` instructs agents to read it when present.

Anything else personal (notes, scratch configs) follows the same rule: suffix
`.local`.

## Adding a skill

1. New directory `skills/<name>/` with a `SKILL.md` starting from frontmatter:
   ```yaml
   ---
   name: <name>
   description: <one line; this is all other sessions see when deciding to load it>
   ---
   ```
2. Keep skills single-purpose and reference each other (`test-conventions` is the
   shared reference for the `core-*` skills) instead of duplicating.
3. If the skill ships a script that encodes a registry (e.g. `coauthor.sh`), keep
   the SKILL.md table in sync with the script - the script is authoritative.

Skill changes take effect in already-open agent sessions only after a restart.

## Troubleshooting

- **Skills not discovered** (Claude Code): check your `.claude` symlink resolves -
  `ls .claude/skills/` - and restart the session.
- **Dangling links after moving/renaming the pack**: relative links survive renames
  of the pack root but not of `rstsr-agents` itself; re-run the `agent-setup`
  script with `--check` per repository.
- **Agent session wrote scratch files into this repository**: `tmp*` and `*.local*`
  are gitignored here on purpose; move anything worth keeping to your notes
  directory.

## Provenance

Most of this repository is maintained with heavy AI assistance; files substantially
generated by AI note the model per the RSTSR convention (see `AGENTS.md`). The
emails in `skills/git-commit-coauthor/` are conventional attribution addresses, not
contact points.
