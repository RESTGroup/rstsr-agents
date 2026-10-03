# rstsr-mkl-ffi (Intel oneAPI MKL)

Upstream: [Intel oneAPI MKL](https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl-download.html)
(Math Kernel Library). A binary-only distribution - there is no source
checkout. The crate generates the modules `blas`, `cblas`, `lapack`, `lapacke`
and `service`, plus the shared `mkl_types`.

## Upstream distribution

The upstream "checkout" is the **install tree**: `~/intel/oneapi/mkl/<version>`
(per-developer; find it in the repo-root `AGENTS.local.md` /
`CLAUDE.local.md` - a `Resources and Directories` entry). The non-root default
of the offline installer is `$HOME/intel/oneapi`; installs must not use `sudo`
(root installs go to `/opt/intel/oneapi`, a different tree than the one the
crate's dyload search and the recorded path assume).

Get a newer version from the download page's Linux "offline installer" link
(direct `registrationcenter-download.intel.com` URL, no registration), then:

```bash
cd ~/Downloads
wget <intel-onemkl-<version>_offline.sh URL>
sh ./intel-onemkl-<version>_offline.sh -a --silent --eula accept \
    --install-dir="$HOME/intel/oneapi"
```

The version to record is in `mkl/<ver>/include/mkl_version.h`
(`INTEL_MKL_VERSION`, e.g. `20260100` = 2026.1; `__INTEL_MKL_BUILD_DATE` is the
release build date). PyPI `mkl-include` / `mkl` wheels are an alternative
header/lib source but not the tracked install.

## Vendored headers

`header/` is the binding input: the classic C headers copied verbatim from
`mkl/<ver>/include` (48 headers as of 2026.1). The install's
`*_omp_offload.h` / `*_omp_variant.h` headers are **not** vendored - the crate
binds the classic interface only. Refresh each already-vendored file from the
new install and byte-verify (any difference beyond the ones upstream really
changed is a sign of a hand edit or a stale copy).

Until 2026-10 the crate also vendored `header/symbol_table.txt` (a 2.5 MB
`nm -D` dump of `libmkl_rt.so`) that `gen_lapack.py` asserted against. It was
removed as repository noise; the library-coverage check now lives in this
procedure (see Verification) instead of in the generator.

## Generator

Six jupytext-style scripts under `rstsr-mkl-ffi/scripts/`, run as plain Python
from that directory (cwd matters - paths are built from `os.getcwd()`), with
the Python that carries `tree_sitter` + `tree_sitter_rust` and the `bindgen`
CLI on PATH:

```bash
cd rstsr-mkl-ffi/scripts
python gen_types.py && python gen_blas.py && python gen_cblas.py \
    && python gen_lapack.py && python gen_lapacke.py && python gen_service.py
```

- `gen_types.py` **must run first**: it writes `scripts/tmp/mkl_types_rstsr.h`
  by rewriting object-like `#define`s in `mkl_types.h` into `typedef`s, and
  every other preprocessed header includes it. It is the only script that does
  not touch `src/`.
- Each other script: copy `header/` -> `scripts/tmp/`, write
  `tmp/<X>_rstsr.h`, run bindgen, post-process (tree-sitter name normalization;
  `gen_lapack` folds `*_64` onto the canonical name and asserts symbol-table
  coverage), split with `util_dyload.dyload_main`, copy the six generated files
  into `src/<dir>/`, then `cargo fmt -p rstsr-mkl-ffi`. `src/lib.rs` and each
  `src/<dir>/mod.rs` are hand-written and never overwritten.
- `src/mkl_types.rs` is half hand-written and its generated part must be
  merged by hand after `gen_types.py`: keep the preamble (imports,
  cfg-selected `MKL_INT`/`MKL_UINT`/`MKL_LONG`, fixed-width aliases) and append
  the regenerated part, dropping the `_MKL_Complex8/16` structs and the
  generated `MKL_INT*`/`MKL_UINT*`/`MKL_LONG`/`MKL_F16`/`MKL_BF16`/`MKL_E5M2`/
  `MKL_E4M3` aliases (the preamble defines them), and stripping `::core::ffi::`
  prefixes. A merge-only change is invisible to the other scripts, so it is
  easy to forget - diff `src/mkl_types.rs` explicitly.
- **Recheck the hand-merge every run.** Diff the raw bindgen output
  (`scripts/tmp/mkl_types.rs`) against the committed `src/mkl_types.rs`: every
  difference must be either an upstream change or one of the adaptations listed
  above. Bindgen or upstream can add, rename or retype items such that an
  adaptation no longer fits; when that happens, edit `src/mkl_types.rs`
  accordingly - and update this reference, so the next run inherits the
  knowledge.

No generator asserts a text patch (the old `gen_lapack.py` symbol-coverage
assert went with the vendored table), so review the diff - not the exit status -
for every module.

## Verification

```bash
cd rstsr-ffi
cargo check -p rstsr-mkl-ffi --no-default-features
for f in blas cblas lapack lapacke; do
    cargo check -p rstsr-mkl-ffi --no-default-features --features "$f"
done
cargo check -p rstsr-mkl-ffi                                     # default: blas, cblas, lapack
cargo check -p rstsr-mkl-ffi --features dynamic_loading
cargo check -p rstsr-mkl-ffi --features ilp64                     # and lp64_as_int
cargo check -p rstsr-mkl-ffi --no-default-features --features "blas,cblas,lapack,lapacke,dynamic_loading,ilp64"
cargo clippy -p rstsr-mkl-ffi --all-targets --all-features -- -D warnings
cargo fmt --all -- --check
```

- The crate has no test suite. For a runtime smoke, use a scratch example
  (`--features dynamic_loading`) that prints `service::MKL_Get_Version` and
  runs a `cblas_dgemm`. `$HOME/intel/oneapi/mkl/latest/lib` is already one of
  the dyload candidates, so the user install is found without setting
  `RSTSR_DYLOAD_MKL`; delete the example afterwards. A threaded routine may
  first fail with `undefined symbol: omp_get_num_procs` - see the pitfalls.
- **Library-coverage audit** (this is what the removed vendored symbol table
  used to enforce): every lapack name the generator binds must be exported by
  the runtime library, as both `<name>` and `<name>_`. With the install at hand:

  ```bash
  nm -D ~/intel/oneapi/mkl/<ver>/lib/libmkl_rt.so | awk '{print $NF}' | LC_ALL=C sort -u > /tmp/mkl_exports.txt
  grep -oE '^void[[:space:]]+[A-Za-z_][A-Za-z0-9_]*' rstsr-mkl-ffi/header/mkl_lapack.h \
      | awk '{print tolower($2)}' | sed -e 's/_64$//' -e 's/_$//' | LC_ALL=C sort -u > /tmp/mkl_names.txt
  { sed 's/$/_/' /tmp/mkl_names.txt; cat /tmp/mkl_names.txt; } | LC_ALL=C sort -u \
      | LC_ALL=C comm -23 - /tmp/mkl_exports.txt     # must print nothing
  ```

  Keep the `LC_ALL=C` sorts: `comm`'s collation differs from plain `sort`'s
  locale order, and mixing the two silently reports phantom missing symbols.
  (`_64` declarations are folded onto the canonical name by the generator; the
  uppercase spelling is a Rust-level alias, so it needs no extra symbol.)
- No automated checker beyond that. Diff review: the post-update diff should be
  limited to the headers that changed upstream, `src/mkl_types.rs`, and the
  modules whose headers changed.

## Pitfalls

- **Ordering**: `gen_types.py` must run first - it produces
  `scripts/tmp/mkl_types_rstsr.h`, which every other preprocessed header
  includes.
- **OpenMP runtime**: `dynamic_loading` users can hit
  `libmkl_intel_thread.so.3: undefined symbol: omp_get_num_procs` on the first
  threaded call - a plain Rust binary loads no OpenMP runtime, and MKL's
  threading layers deliberately leave the `omp_*` symbols for the application
  to provide. Working setups: `MKL_THREADING_LAYER=SEQUENTIAL`/`GNU`, or
  `LD_PRELOAD=$HOME/intel/oneapi/compiler/latest/lib/libiomp5.so`. Do not
  "fix" this by having the crate dlopen libiomp5 itself: loading an OpenMP
  runtime is the host application's decision (mixing libiomp5 with libgomp in
  one process is the classic failure it avoids).
- **Stale vendored headers are silent**: the generator never reads the MKL
  install, only `header/`.
- **`src/mkl_types.rs` is hand-merged** - the one file a script cannot update
  for you.
- **Upstream drops constants**: MKL removes dead CPU-target values as it retires
  them (2026.1 dropped the Knights-Landing/old-AVX `MKL_CBWR_*` and
  `MKL_ENABLE_*` values). Removed Rust items are user-visible breakage: list
  them under API Breaking in the changelog.
- **Version policy**: same as the other references - patch by default, bump the
  middle number for a user-visible break (here: the constant removals made
  0.2.1 -> 0.3.0), no bump for a stamp-only regeneration. Update the crate
  readme's version line + changelog, `Cargo.toml`, and the root `readme.md`
  table row.
- The `libmkl_rt.so` **SONAME** bumps between major series (`.so.2` -> `.so.3`
  at 2026.0). Dynamic loading by filename is unaffected; it matters only for
  programs linking `-lmkl_rt`.
