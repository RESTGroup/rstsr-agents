# rstsr-lapack-ffi (netlib LAPACK)

Upstream: [Reference LAPACK](https://github.com/Reference-LAPACK/lapack). One
checkout generates all five modules of the crate: `blas`, `cblas`, `lapack`,
`lapacke`, `lapacke_utils`.

## Upstream checkout

Per-developer, read-only. Read the `Reference checkouts:` entry of the
repo-root `AGENTS.local.md` (or `CLAUDE.local.md`); if absent, ask the human to
add the LAPACK clone there (e.g. `Reference checkouts: ~/Git-Others`, with a
`lapack` clone inside). Pass it to the generator as `RSTSR_LAPACK_REPO=<path>`
(the script defaults to `~/Git-Others/lapack`); never write a local path into
tracked files.

Target the newest **release tag**: `git fetch --tags`,
`git tag --sort=-v:refname | head -1`, then `git checkout <tag>` (detached HEAD
is fine). Upstream `master` runs far ahead of the newest tag and is not a
binding target — bind release tags only. The crate readme's "Current FFI
version" line is the canonical record of what the bindings currently track
(v3.12.1 as of 2026-10-02; releases are rare).

## Generator

`rstsr-lapack-ffi/scripts/perform_bindgen.py`, run from its own directory with
the venv/interpreter that carries the Python deps:

```bash
cd rstsr-lapack-ffi/scripts
RSTSR_LAPACK_REPO=<checkout> <python> perform_bindgen.py
```

It copies every `.h`/`.h.in` from `CBLAS/include` + `LAPACKE/include` into
`header/` (renaming the two `*_mangling_with_flags.h.in`), regenerates the five
files under each `src/<module>/`, and runs `cargo fmt -p rstsr-lapack-ffi`.
Test and internal headers (`cblas_test.h`, `lapacke_test.h`, `*_64.h`,
`cblas_xerbla_internal.h`, ...) are vendored on purpose; do not prune them by
hand. `scripts/tmp/` and `src/*/mod_template.rs` are gitignored scratch.

Toolchain: `bindgen` CLI, Python with `tree_sitter` + `tree_sitter_rust`,
`clang`, and the nightly toolchain pinned by `rust-toolchain.toml` (for
`cargo fmt`). Setup example: `cargo install bindgen-cli --version 0.73.2`;
`uv pip install tree_sitter tree_sitter_rust`. Bindgen 0.73.2 was verified to
reproduce the committed v3.12.1 bindings byte-for-byte except the version
stamp, so a toolchain bump alone is a stamp-only diff.

## Checker

```bash
python3 <rstsr-agents>/skills/update-ffi-blas/scripts/check_lapack_bindings.py \
    --repo <rstsr-ffi> --upstream <checkout>
```

It verifies per module that every symbol declared in the vendored headers is
bound (and nothing is stale), that the four dyload files carry the same
function set as `ffi_extern.rs`, that the generated code uses the
feature-dependent `lapack_int` / `blas_int` aliases from `rstsr-cblas-base`
(no local alias definitions, no hard-coded integers, LAPACKE constants
retyped), and that every vendored header is byte-identical to the checkout.
Run it **while the checkout is still at the chosen tag** - against a different
revision the parity check will (correctly) report the upstream drift.

## Verification

```bash
cd rstsr-ffi
cargo check -p rstsr-lapack-ffi --no-default-features               # modules are feature-gated
for f in blas cblas lapack lapacke lapacke_utils; do
    cargo check -p rstsr-lapack-ffi --no-default-features --features "$f"
done
cargo check -p rstsr-lapack-ffi --all-features                       # ilp64 + lp64_as_int + dynamic_loading
cargo clippy --all-targets --all-features -- -D warnings             # CI
cargo fmt --all -- --check                                           # CI
cargo test -p rstsr-lapack-ffi --features dynamic_loading --lib      # runtime dyload smoke
```

Known pre-existing smoke failure: `blas::playground` panics at
`src/blas/dyload_compatible.rs` in the `ddotsub_` wrapper on distro BLAS builds
that ship only the function form of `ddot`/`dnrm2` (e.g. Ubuntu `libblas.so.3`
lacks `ddotsub_`). `cblas::playground` and `lapack::playground` must pass;
treat only new failures as regressions.

## Pitfalls

- **Text-patch pipeline.** `perform_bindgen.py` rewrites headers and bindgen
  output by targeted text patches (the `*_INT` type defines, the
  `*_FORTRAN_STRLEN_END` defines, the include redirects, the alias removals,
  the LAPACKE constant retypes). Patches that must fire assert that they did,
  so an upstream reformat fails the run loudly instead of silently emitting
  wrong bindings; if an assert fires, update the pattern in the generator -
  never skip the patch. The checker independently verifies the
  feature-dependent aliases (`lapack_int` / `blas_int`) actually flow into the
  generated signatures.
- **Bindgen version stamps.** Each `ffi_base.rs` records the bindgen version
  used; report the version in the hand-off. Changing it without a binding
  change is at most a patch-level concern - the openblas crate kept such a
  regeneration as its own commit.
- **Dynamic-loading candidates lack versioned SONAMEs** (`liblapack.so.3`
  etc.); on runtime-only installs without the `-dev` symlinks, loading falls
  back to `RSTSR_DYLOAD_*`. The openblas crate has the versioned-SONAME fix
  (#11); porting it to `rstsr-lapack-ffi` is a separate change.
