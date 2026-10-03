---
name: update-ffi-dlpack
description: Update or check the dlpack-ffi crate (RESTGroup/dlpack-ffi) against newer DLPack releases - fetch upstream tags, diff the vendored header, refresh header/dlpack.h, regenerate with scripts/bindgen.py, run the checker and tests, record provenance, set the crate version to the DLPack version. Use when asked to update, regenerate, or version-bump dlpack-ffi.
---

# update-ffi-dlpack: refresh the DLPack bindings

`dlpack-ffi` is a standalone generated-only crate binding [DLPack](https://github.com/dmlc/dlpack).
Its header declares C types only - no functions - so there is no symbol coverage to
check; the gate is header parity, regeneration reproducibility, and the ABI/ownership
tests under `tests/`.

**Purity rule**: never add "rstsr"/"rest" references to the dlpack-ffi repository
(content, docs, code, metadata). This skill lives in rstsr-agents and operates on the
crate from outside.

Paths are per-developer: upstream checkout `~/Git-Others/dlpack`, crate checkout
`~/rstsr_pack/dlpack-ffi` (recorded in the pack `CLAUDE.local.md`, "Resources and
Directories"). The generator never reads the upstream checkout - only the vendored
`header/dlpack.h` - so the header refresh below is mandatory.

## Check mode - is there a newer DLPack?

1. `git -C <upstream> fetch --tags --quiet`; list the newest release tags:
   `git -C <upstream> tag --sort=-v:refname | head -5`.
2. Diff the vendored header against the newest tag:
   `git -C <upstream> show <tag>:include/dlpack/dlpack.h | diff - <crate>/header/dlpack.h`.
3. Classify every hunk and report what it implies:
   - version macros - a version bump (the crate version follows the DLPack version);
   - new `DLDeviceType`/`DLDataTypeCode` values - regenerate only; the newtype style
     absorbs them, no Rust API break;
   - new/changed structs or function-pointer typedefs - regenerate; flag as a
     potential Rust API change for the human;
   - doc/comment-only hunks - regeneration noise.
4. A `DLPACK_MAJOR_VERSION` bump means an upstream ABI layout change - stop and
   report before touching anything.

## Update mode

1. **Pin the release**: check out the newest release *tag* in the upstream checkout
   (never a branch tip); record tag + commit hash + date.
2. **Pre-flight**: the crate tree must be clean (`git status`).
3. **Vendor the header**:
   `git -C <upstream> show <tag>:include/dlpack/dlpack.h > <crate>/header/dlpack.h`.
4. **Regenerate**: `cd <crate>/scripts && python3 bindgen.py`. The script copies
   `header/` into gitignored `tmp/`, runs the bindgen CLI, post-processes, writes
   `src/lib.rs`, then formats. Never edit `src/lib.rs` by hand - fix the script.
5. **Review the delta - the gate**: every hunk of `git diff src/lib.rs` must be
   explainable by the header change. Then run the checker:
   `python3 <rstsr-agents>/skills/update-ffi-dlpack/scripts/check_dlpack_bindings.py --repo <crate> --upstream <upstream> --tag <tag>`.
6. **Verify**: `cargo fmt --all -- --check`, `cargo clippy --all-targets
   --all-features -- -D warnings`, `cargo test` - all green; plus regeneration
   idempotence: re-run the generator and confirm `src/lib.rs` is unchanged.
7. **Record provenance**: readme version line (DLPack version + tag + commit) and a
   changelog entry; set `Cargo.toml` version to the DLPack version (`v1.3` -> `1.3.0`);
   refresh `Cargo.lock`.
8. **Hand off**: leave uncommitted for human review; commit only on explicit
   instruction, following skill `git-commit-coauthor`. Report: tag + commit, diff
   classification, checker/test results, and the bindgen version used.

## Pitfalls

- The vendored header is the generator input; a stale `header/dlpack.h` is the silent
  failure mode - always refresh, then rely on the checker's byte-parity check.
- Run `scripts/bindgen.py` from inside `scripts/` (it builds paths from `os.getcwd()`).
- `rustfmt.toml` contains nightly-only options (`wrap_comments`,
  `overflow_delimited_expr`); regenerate with stable rustfmt as CI does - the warnings
  are expected and the formatting stays reproducible on stable.
- Doctests are disabled in `Cargo.toml` (`[lib] doctest = false`): the generated doc
  comments embed C/C++ examples. `cargo test` runs the `tests/` suite.
- Never switch the generator back to `--default-enum-style rust`; rustified enums are
  undefined behavior for values added by newer DLPack releases.
- The crate does not follow Rust semver: its version tracks DLPack, adjustments are
  patch bumps.
- An end-to-end interop check against `numpy.from_dlpack` needs a consumer-side
  harness (e.g. pyo3 or a ctypes-loaded cdylib); it is out of scope for this
  generated-only crate and remains a manual/future check.
