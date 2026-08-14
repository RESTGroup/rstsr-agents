---
name: crate-publish
description: Publish a new version of the rstsr workspace crates via the release-plz GitHub workflows, orchestrated from the agent CLI with gh. Use when the user asks to release, publish, or cut a new rstsr version. Strict human gates on dispatch and merge; the human developer always sets the final version number.
---

# crate-publish: rstsr version publish

Releases the `rstsr` repo (RESTGroup/rstsr). All workspace crates share one version
(`version.workspace = true`) and move in lockstep; only the `rstsr` crate gets the
git tag `rstsr-vX.Y.Z` and a GitHub Release. Publishing itself happens in CI
(**release-plz**); this skill orchestrates it from the CLI with `gh`.

**Scope**: `rstsr` repo only. Releases of `rstsr-ffi` and `tblis-rs` are **not**
covered by this skill.

## Model

- Flow (manual bump): human sets the version; agent prepares the release commit
  (`Update to vX.Y.Z`: workspace `Cargo.toml` versions + root `CHANGELOG.md`) →
  human approves commit and push → dispatch **Release-plz** workflow
  (`release-plz.yml`) → CI publishes all crates to crates.io and tags
  `rstsr-vX.Y.Z`.
- The `release-plz-pr.yml` workflow (bot version-bump PR) is currently **broken**:
  repo settings forbid Actions-created PRs (403 "GitHub Actions is not permitted
  to create or approve pull requests"; observed 2026-06-25 and 2026-08-14). Do
  not dispatch it unless that setting is re-enabled.
- The release CI **runs no tests**. Green CI on `master` HEAD (checked in
  pre-flight) is the quality gate; do not add local test runs unless asked.
- crates.io publishing and git tags are **irreversible**.

## Gates (strict)

Only on **explicit user instruction in the session**, never assumed from permissions:

- dispatching either workflow (`gh workflow run`),
- merging, or pushing the release commit to `master`,
- anything touching crates.io, including `cargo yank`.

Free: local reads, `gh run list/watch`, `gh pr list/view`, `cargo semver-checks`,
preparing edits and commands. Any commit (e.g. changelog sync on the PR branch)
follows skill `git-commit-coauthor`.

## Pre-flight

```bash
cd rstsr
git fetch origin && git status -sb                 # clean, in sync with origin/master
grep -n publish rstsr-test-manifest/Cargo.toml    # MUST show publish = false
gh run list -R RESTGroup/rstsr --branch master -L 10   # clippy + test workflows green on HEAD sha
git log --oneline rstsr-v<last>..HEAD             # enumerate release content
```

Semver evidence (**advisory only** - the human decides the final version):

```bash
cargo install cargo-semver-checks --locked        # one-time; not on brew, compiles from source
cargo semver-checks check-release -p rstsr-common -p rstsr-core --default-features --features backtrace,row_major
for p in rstsr-dtype-traits rstsr-blas-traits rstsr-linalg-traits rstsr-sci-traits rstsr-native-impl rstsr-openblas rstsr-mkl rstsr-blis rstsr-aocl rstsr-kml rstsr-tblis rstsr; do
  cargo semver-checks check-release -p "$p" --default-features
done
```

**Always pass `--default-features`**: the tool's default all-features mode fails
in this workspace - `col_major` + `row_major` are mutually exclusive
(`compile_error!`), and published `rstsr-native-impl` baselines have a doc-only
break under the `rayon` feature. Baselines = latest crates.io versions, automatic.
Non-zero exit with `--- failure <lint> ---` blocks means breaking changes were
found. Report findings and a proposed version (patch by default, since plain
commit titles carry no semver signal); the human decides the final version.

## Release commit (manual bump)

1. Workspace `Cargo.toml`: bump `[workspace.package] version` and the 14 `rstsr*`
   entries under `[workspace.dependencies]` (replace the exact old version string;
   **do not touch** cross-repo ffi/tblis reqs like `0.5`/`0.2`).
2. Root `CHANGELOG.md` (the crate-level `rstsr/CHANGELOG.md` is a symlink to it -
   verify with `ls -l`): new `## vX.Y.Z -- YYYY-MM-DD` section. **Entries must be
   rephrased, never copied from PR titles**; gather material with `gh pr list -R
   RESTGroup/rstsr --state merged --limit N`. Style: freeform category lines
   (`Bug Fix`, `Enhancement`, `Behavior change`,
   `API breaking changes (user should not feel that)`), `- ` items, PR link as
   `(RESTGroup/rstsr#NN)`, indented prose for elaboration. No entries for
   test-only or meta commits.
3. Commit subject `Update to vX.Y.Z` (historical shape: exactly `Cargo.toml` +
   `CHANGELOG.md`; no `Cargo.lock`); push to `master` (gated).
4. Cross-check: a `release-plz-pr.yml` dispatch log prints `next version is X.Y.Z`
   per crate (patch by default for plain commit titles) - advisory only, the human
   sets the real version in step 1.

## Publish and verify

1. Dispatch (gated): `gh workflow run release-plz.yml -R RESTGroup/rstsr --ref master`;
   `gh run watch`.
2. Verify (free):

```bash
curl -s -A crate-publish https://crates.io/api/v1/crates/rstsr | jq -r .crate.max_stable_version
gh release view -R RESTGroup/rstsr        # rstsr-vX.Y.Z with notes
git fetch --tags origin && git tag -l 'rstsr-v*'
```

3. Report: published versions (all workspace crates), tag, release link, failures.

## Mistakes

- Bad published version: `cargo yank rstsr@X.Y.Z` only on explicit instruction;
  yanking is damage control, not deletion; **never reuse a version number** - fix
  forward with a patch bump.
- Release workflow failed midway (some crates published, some not): fix the cause,
  re-dispatch; release-plz skips versions already on crates.io.
