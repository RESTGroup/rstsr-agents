---
name: update-ffi-blas
description: Update an rstsr-ffi binding crate from a newer upstream BLAS/LAPACK release - update the upstream, pin the revision, vendor headers, regenerate the bindgen output, verify coverage, record provenance. Read references/lapack.md for rstsr-lapack-ffi, references/openblas.md for rstsr-openblas-ffi, references/mkl.md for rstsr-mkl-ffi and references/aocl.md for rstsr-aocl-ffi; the other distributions have no reference yet. Use when asked to update, regenerate, or version-bump an rstsr-ffi binding crate.
---

# update-ffi-blas: regenerate rstsr-ffi bindings

The `rstsr-ffi` repository binds several BLAS/LAPACK distributions. The update
procedure is the same for each; the concrete commands, paths, toolchain and
pitfalls differ per distribution and live in a per-library reference:

| crate | reference |
|---|---|
| `rstsr-lapack-ffi` | `references/lapack.md` |
| `rstsr-openblas-ffi` | `references/openblas.md` |
| `rstsr-mkl-ffi` | `references/mkl.md` |
| `rstsr-aocl-ffi` | `references/aocl.md` |
| `rstsr-blis-ffi`, `rstsr-kml-ffi` | not written yet - stop and say so |
| `rstsr-cblas-base` | enum base crate, not bindgen-able; no procedure |

## Procedure

1. **Read the target crate's reference** (table above) before anything else.
   It names the upstream checkout, the generator, the checker, and the
   verification commands. Completion: you know which upstream library and
   which crate files the run will touch.
2. **Update the upstream, then pin the revision.** Source checkout: `git pull`
   so the clone is current, `git fetch --tags`, then check out the newest
   release *tag* - never a branch tip (`git tag --sort=-v:refname | head -1`;
   detached HEAD is fine). Binary distribution (MKL): the reference names the
   installer step instead, and the "revision" is the installed version.
   Completion: the pinned revision is identified - `git describe --tags` prints
   the chosen tag, `git status -s` is clean, commit hash + date recorded - or,
   for a binary distribution, the installed version and its path are recorded.
3. **Pre-flight the rstsr-ffi working tree.** `git status` clean: regeneration
   rewrites tracked files in place, and a dirty tree makes the API diff
   unreviewable. Completion: clean tree, or only changes belonging to this
   update.
4. **Regenerate** with the crate's generator (command in the reference).
   Completion: exit 0; `git status` shows only the paths the reference
   expects (generator scratch is gitignored).
5. **Review the API delta - the gate.** Run the crate's binding checker
   (reference) and classify **every** hunk of `git diff` as upstream-caused
   (correct) or generator artifact (a bug - fix the generator, never the
   generated file). A missing or renamed symbol still compiles, so the
   checker, not the compiler, is what catches coverage loss. Changed or
   removed signatures are potential API breakage; list them for the human.
   Completion: checker passes and every hunk has an explanation.
6. **Verify the build** with the reference's command list. Completion: all
   green; note pre-existing failures instead of hiding them.
7. **Record provenance** in the same change: the crate readme's version line
   and the root `readme.md` table row (the reference states the exact shape);
   bump the crate version when the bindings changed - patch by default, bump
   the middle number only for a user-visible break (changed or removed
   signatures); no bump for a stamp-only regeneration. Changelog policy: state
   the upstream version and summarize **only API-breaking changes** - do not
   enumerate added functions. Completion: the readme, `Cargo.toml` and root
   table agree on the upstream tag and version.
8. **Hand off.** Leave the change uncommitted for human review; commit only on
   explicit instruction, following skill `git-commit-coauthor`. Report:
   upstream tag + commit, per-module symbol delta, breaking changes, and the
   generator toolchain versions used.
