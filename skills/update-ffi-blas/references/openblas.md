# rstsr-openblas-ffi (OpenBLAS)

Upstream: [OpenBLAS](https://github.com/OpenMathLib/OpenBLAS). The crate
generates two modules, `blas` (the Fortran interface from `common_interface.h`)
and `cblas`; the `lapack` and `lapacke` modules are **not** generated here - by
design their source files are symlinks into `rstsr-lapack-ffi`.

## Upstream checkout

Per-developer, read-only. Find it in the repo-root `AGENTS.local.md` /
`CLAUDE.local.md` - a `Resources and Directories` entry (e.g. `OpenBLAS source
checkout: ~/Git-Others/OpenBLAS`). Unlike netlib LAPACK, the generator never
reads this checkout: the binding input is the crate's vendored `header/` copy,
and the checkout serves to refresh and verify it.

Keep the clone current (`git pull`, `git fetch --tags`) and target the newest
**release tag** - never a branch tip: `git tag --sort=-v:refname | head -1`,
`git checkout <tag>` (detached HEAD is fine). The crate readme's "Current FFI
version" line records what the bindings track (v0.3.34 as of 2026-10-02).

## Vendored headers

`header/` is the binding input: `cblas.h`, `common_interface.h`,
`openblas_config_template.h`. Refresh all three from the checkout at the chosen
tag, then verify (must be byte-identical, or the vendored copy is stale):

```bash
cd rstsr-openblas-ffi
for f in cblas.h common_interface.h openblas_config_template.h; do
    git -C <checkout> show <tag>:$f | diff - header/$f
done
```

A header refresh is a commit of its own in this repository ("update vendored
headers to OpenBLAS vX"); if the diff is empty, the run is a reproducibility
check rather than an upstream update.

The `lapack` / `lapacke` sources follow `rstsr-lapack-ffi` releases (netlib
LAPACK v3.12.1), not the OpenBLAS tag - OpenBLAS v0.3.34 bundles a LAPACK
reporting 3.12.0, so a minor provenance skew is expected and accepted.

## Generator

`rstsr-openblas-ffi/scripts/perform_bindgen.py`, run from its own directory
with the venv/interpreter that carries the Python deps (bindgen CLI on PATH):

```bash
cd rstsr-openblas-ffi/scripts
<python> perform_bindgen.py
```

It regenerates the files under `src/blas/` and `src/cblas/` and runs
`cargo fmt -p rstsr-openblas-ffi`. `scripts/tmp/` and `src/*/mod_template.rs`
are gitignored scratch. Generation requires a Linux host (the Linux-only
affinity API pulls in `<sched.h>`).

Toolchain: `bindgen` CLI (0.73.2 at last run; it reproduced the pre-existing
bindings byte-for-byte except the version stamp), Python with `tree_sitter` +
`tree_sitter_rust` (miniconda `torch` env), clang, and the nightly toolchain
pinned by `rust-toolchain.toml`.

Text patches assert that they fired (`replace_required` / `sub_required` /
`assert_absent`, same style as the lapack generator); if an assert fires, update
the pattern in the generator - never edit the generated files.

## Linux-only affinity API

Upstream declares `openblas_getaffinity` / `openblas_setaffinity` (and pulls
`<sched.h>` for `cpu_set_t`) under `#ifdef OPENBLAS_OS_LINUX`. The generator
defines that macro so the pair is bound, then gates the generated items with
`#[cfg(target_os = "linux")]` in all generated files (including the dyload
trio); `cpu_set_t` / `__cpu_mask` are gated too. The define must stay
*valueless* - a valued `#define OPENBLAS_OS_LINUX 1` leaks into bindgen output
as a `pub const`. When the runtime library lacks the symbols, dynamic loading
yields `None` for them.

## Verification

```bash
cd rstsr-ffi
cargo check -p rstsr-openblas-ffi --no-default-features
for f in blas cblas lapack lapacke; do
    cargo check -p rstsr-openblas-ffi --no-default-features --features "$f"
done
cargo check -p rstsr-openblas-ffi                                     # default: blas, cblas, lapack
cargo check -p rstsr-openblas-ffi --features dynamic_loading,ilp64
cargo check -p rstsr-openblas-ffi --no-default-features --features "blas,cblas,lapack,lapacke,dynamic_loading,ilp64"
cargo check -p rstsr-openblas-ffi --no-default-features --features blas,quad_precision    # and ex_precision
cargo clippy --all-targets --all-features -- -D warnings              # CI
cargo fmt --all -- --check                                            # CI
```

- `cargo check --all-features` fails on purpose: `quad_precision` +
  `ex_precision` together trip a `compile_error!` (the `clippy` cfg disables
  it, so the clippy `--all-features` line above is fine). Check the precision
  features separately.
- The crate has no test suite. For a runtime smoke, use a scratch example
  (e.g. `cblas::openblas_get_config` + a `dgemm_` product) run with
  `--features dynamic_loading` against the system OpenBLAS, then delete it.
- No automated checker yet, and the lapack checker is not applicable. Do the
  header diff above, a symbol set-diff of `src/{blas,cblas}/ffi_extern.rs`
  against the headers, and grep for leftovers (`blasint`, local `blas_int`
  alias, local `CBLAS_*` enum definitions, `CBLAS_LAYOUT`).

## Pitfalls

- **Stale vendored headers are the silent failure mode** - the generator never
  consults the checkout; always refresh + diff `header/` against the tag.
- **Load-bearing patches**: the `blasint -> blas_int` rename is what makes the
  `ilp64` feature work (a no-op would pin i32 while still compiling), and the
  `#define xdouble double -> typedef` patch keeps `quad_precision` /
  `ex_precision` meaningful. Both now assert.
- **Changelog policy**: state the upstream version and summarize only
  API-breaking changes - do not enumerate added functions. Version: a
  non-breaking update is a patch bump, a changed or removed signature bumps
  the middle number, a stamp-only regeneration needs none (`Cargo.toml` +
  readme changelog; the root readme table only tracks the upstream version).
- Versioned-SONAME dyload candidates are already handled here;
  `rstsr-lapack-ffi` still lacks them (separate change).
