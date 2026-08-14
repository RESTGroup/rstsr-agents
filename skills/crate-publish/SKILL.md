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

- Flow: dispatch **Release-plz-PR** workflow (`release-plz-pr.yml`) → it opens a PR
  with the version bump and changelog → human sets the final version and merges →
  dispatch **Release-plz** workflow (`release-plz.yml`) → CI publishes all crates to
  crates.io and tags `rstsr-vX.Y.Z`.
- The release CI **runs no tests**. Green CI on `master` HEAD (checked in
  pre-flight) is the quality gate; do not add local test runs unless asked.
- crates.io publishing and git tags are **irreversible**.

## Gates (strict)

Only on **explicit user instruction in the session**, never assumed from permissions:

- dispatching either workflow (`gh workflow run`),
- merging or pushing commits to the release PR,
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

## Release PR

1. Dispatch (gated): `gh workflow run release-plz-pr.yml -R RESTGroup/rstsr --ref master`,
   then `gh run watch` and `gh pr list -R RESTGroup/rstsr --state open`.
2. Review the PR. release-plz proposes a patch bump unless commit titles follow
   conventional format; check against the semver report before agreeing.
3. **Changelog entries must be rephrased, never copied from PR titles.** Gather
   material with `gh pr list -R RESTGroup/rstsr --state merged --limit N` and write
   entries in the style of `rstsr/CHANGELOG.md`:
   - heading `## vX.Y.Z -- YYYY-MM-DD`;
   - freeform category lines (`Bug Fix`, `Enhancement`,
     `Enhancement (also behavior change)`, `Behavior change`,
     `API breaking changes`), `- ` items, PR link as `(RESTGroup/rstsr#NN)` when a
     PR exists, indented prose for elaboration.
4. Changelog location is a **symlink**: `rstsr/CHANGELOG.md` → `../CHANGELOG.md`,
   so release-plz's package changelog lands in the root `CHANGELOG.md` directly -
   there is no second copy to keep in sync. Verify the symlink is intact
   (`ls -l rstsr/CHANGELOG.md`).
5. Human sets the final version (edit the PR if the proposed one is wrong) and
   merges (gated).

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
