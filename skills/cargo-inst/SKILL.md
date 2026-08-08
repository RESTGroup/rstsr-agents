---
description: Rust's cargo instructions for building, testing, API documentation for various cases and crates.
---

## Example

```bash
RUST_BACKTRACE=1 cargo test --package rstsr-core --test entry_row_cpu --features "backtrace row_major" --no-default-features -- core_func::manuplication::test_reshape::numpy_reshape::regression --exact --nocapture
```

## Testing rules

- Only test one crate at a time.

- The workspace pins `nightly` (`rust-toolchain.toml`) so devs get the better
  `rustfmt`/`clippy`; the library itself stays on stable (MSRV `1.82.0`) for API users.
  On a fresh machine the first `cargo` inside the workspace auto-installs nightly via
  rustup (one-time download; the example commands show no progress).

- Always add `RUST_BACKTRACE=1` (for backtrace).
- Add `RSTSR_DEV=1` **only for BLAS device crates** (`crates-device/*`); it switches
  their BLAS backend to dynamic linking for development. It is a no-op for `rstsr-core`
  and the `rstsr` facade.

- Testing cases (`--test entry_row_cpu` in example above) depends on the real testing needs.
  - Doctest: `--doc`.
  - Integration test (in dir `tests`): `--test <test_name>`, where `<test_name>` is the name of the test `.rs` file under `tests` directory.
  - All integration tests: `--tests`.
  - Unittest (in dir `src`): `--lib`.

- Cargo feature selection (for crate `rstsr-core`):
  - **Only test usual situation, unless user explicitly specifies**.
  - Usual situation (fast, Faer-free): `--features "backtrace row_major" --no-default-features`.
  - `row_major` is **required** for the `entry_*` test binaries (each has
    `required-features = ["row_major"]` in `Cargo.toml`), and `backtrace` does **not**
    imply it. With `--features backtrace --no-default-features` cargo errors:
    `target 'entry_row_cpu' requires the features: 'row_major'`.
  - With Faer (default features): drop `--no-default-features` - defaults are
    `row_major` + `aligned_alloc` + `faer` + `faer_as_default` (correct, slower build).
  - With column-major: `--features "backtrace col_major" --no-default-features`
    (`col_major` is compile-time exclusive with `row_major`).

- Cargo feature selection (for crate `rstsr`):
  - **Only test usual situation, unless user explicitly specifies**.
  - Usual situation: `--features "backtrace row_major" --no-default-features`
    (`row_major` must be explicit here too; the facade's `backtrace` does not imply it).
  - With parallel (using Faer device): ` ` (default features for users, but not for development).
  - With column-major: additionally add `col_major` after `--features` (for example, `--features "backtrace col_major"`).

- Cargo feature selection (for crates listed in `crates-device`):
  - **Only test usual situation, unless user explicitly specifies**.
  - **Additionally add `--test-threads=1` after `--exact --nocapture`** to disable parallel testing. This is more important for crates that use BLAS backends, because some BLAS backends are not thread-safe and will cause thread racing or oversubscription.
  - Usual situation: `--features "rstsr/backtrace"` with other default features.
    - Exception for crate `rstsr-openblas`'s usual case: `--features "rstsr/backtrace openmp"`
  - Currently integration test only allows row-major.

## API Document Building

```bash
RUSTDOCFLAGS="--html-in-header katex-header.html" cargo doc --no-deps
```

It is better to provide `katex-header.html`; however if that causes error, ignoring it is also fine.

Always create document at crate level, instead of workspace level.

## Linting and Formatting

```bash
cargo fmt  # Only run this before commit. This can be run at workspace level.
cargo clippy --all-targets --all-features -- -D warnings  # Run at crate level.
```
