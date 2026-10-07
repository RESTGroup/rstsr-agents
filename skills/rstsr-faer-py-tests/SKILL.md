---
name: rstsr-faer-py-tests
description: Test rstsr-faer-py — the pyo3 package exposing rstsr's DeviceFaer backend as the array-api namespace rstsr_faer.api — against the official array-api-tests conformance suite, including build/install of its wheel, the NumPy baseline gate, conformance red maps, and diagnosis of suite runs (chunked mode, OOM/abort, hypothesis quirks). Use for any testing task on rstsr-faer-py or questions about its conformance numbers.
---

# Testing rstsr-faer-py against the array API conformance suite

`rstsr-faer-py` lives in the rstsr repository at `crates-interop/rstsr-faer-py`
(pyo3 + maturin, namespace `rstsr_faer.api`, standard 2025.12). Grading uses
the official data-apis `array-api-tests` suite pinned to `6c0b59f` (spec
submodule `5f847a3`) — the same pins as the NumPy 2.5.1 baseline, so numbers
compare directly. This skill is self-contained: its `scripts/` carry the
whole harness.

Per-developer locations (rstsr checkout, suite checkout, test interpreter)
are recorded in `AGENTS.local.md` at this repository's root; every script
also takes them as env vars (`SUITE_DIR`, `TEST_PY`). Run the scripts from
a scratch working directory — reports land in `./reports` there, never
inside a git checkout.

Recorded reference numbers at the pins (suite-default 100 examples,
derandomized; counts wobble ±2 from hypothesis DB replay):

- NumPy 2.5.1 baseline: ~1335 passed / 42 failed / 5 skipped of 1382.
- rstsr_faer.api first red map (2026-10-04): 255 / 1040 / 87 of 1382.

## 1. Build & install the wheel

The rstsr checkout pins its own nightly toolchain via `rust-toolchain.toml`.

```bash
cd <rstsr-checkout>/crates-interop/rstsr-faer-py
cargo build -p rstsr-faer-py --release                  # compile check
maturin build --release -i "$TEST_PY" -o /tmp/wheels   # maturin must run from the CRATE dir, not the workspace root
"$TEST_PY" -m pip install --force-reinstall --no-deps /tmp/wheels/rstsr_faer_py-*.whl
```

Python-side edits (`python/rstsr_faer/*.py`) need no rebuild — copy the
tree over the installed package in site-packages. Rust-side edits need the
maturin rebuild (see below for what it costs).

### Build time and opt-level (measured 2026-10-05)

A shim-crate edit costs a full release rebuild of the crate: **~6 min** at
the default opt-level since the W2 elementwise pass (before it: ~30 s). The
cost is the pair-dispatch tables (`dispatch_bin_promote!` ~270 arms +
`dispatch_bin_promote_eq!` ~170 in `any_tensor.rs`, expanded once per op
wrapper) — thousands of monomorphizations in one crate, dominated by LLVM
codegen; even opt-level 0 spends ~1m14s.

| opt-level | shim-only rebuild | full build (deps + shim) | full suite time |
| --- | --- | --- | --- |
| 0 | 1m14s | 1m26s | 60 s |
| 2 | 5m47s | 6m08s | 59 s |
| 3 | 6m05s | ≥6m19s | 59 s |

The suite is hypothesis-dominated (arrays ≤ 1024 elements), so the opt-level
is free on the test side: **use `CARGO_PROFILE_RELEASE_OPT_LEVEL=0` for dev
iterations** (~5× faster rebuilds, identical suite verdicts) and keep
opt-level 3 for the wheel whose numbers get recorded. Runtime cost of opt 0
on real compute (1e6 f64, best-of-blocks): add 0.79 ms / exp 3.2 ms vs
0.14 / 0.55 ms at opt 2/3 (numpy reference: 0.16 / 0.38 ms) — so opt 0 is
unsuitable for perf measurements. opt 2 and opt 3 are indistinguishable in
both compile and run time.

**Always `--release` (any opt-level), never the dev profile** (2026-10-07).
Dropping `--release` to get an "opt-0 wheel" silently turns on
`debug-assertions`, and integer-overflow panics then flip exactly 10 nodes
`passed → failed` (1049/251/82 instead of 1059/241/82):
`test_bitwise_{left,right}_shift[__{,i}shift__]`, `test_subtract[__sub__(x, s)]`,
`test_sum`, `test_prod`, `test_cumulative_prod`, `test_diff`,
`test_diff_append_prepend`. Those nodes pass in every stamp built with the
release profile, so a 10-node red shift is a build-profile smell, not a
regression.

**Memory**: a default `--release` (opt-level 3) cdylib link can be OOM-killed on a
loaded machine (`rustc … (signal: 9, SIGKILL)` with no rustc diagnostic, cargo
building with `nproc` jobs, swap exhausted). Memory-lean build that keeps the
verdicts identical:
`CARGO_BUILD_JOBS=2 CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_PROFILE_RELEASE_OPT_LEVEL=0 maturin build --release -i "$TEST_PY" -o /tmp/wheels`.

## 2. One-time suite setup

```bash
SUITE_DIR=… TEST_PY=… ./scripts/setup.sh
```

Clones/checks out the suite at the pin, initializes the spec submodule
(offline from `SPEC_LOCAL` when given; SSH fallback when HTTPS fails), and
installs test deps (pytest, pytest-json-report, hypothesis, ndindex) into
`TEST_PY`'s environment — no overlay venv, numpy untouched (only the
`MODULE=numpy` baseline needs numpy).

## 3. Run

| command | purpose |
| --- | --- |
| `MODULE=numpy ./scripts/run.sh` | NumPy baseline gate (reproduces the reference numbers) |
| `MODULE=rstsr_faer.api CHUNKED=1 ./scripts/run.sh` | subject under test — **always `CHUNKED=1` on red runs** |
| `./scripts/run.sh array_api_tests/test_creation_functions.py` | single file (MODULE still applies) |
| `FRESH=1 …` | delete the `.hypothesis` example DB for canonical counts |
| `MAX_EXAMPLES=20 …` | quick smoke |
| `NO_EXPLAIN=1 …` | skip hypothesis's explain phase — red-map speedup (≈15× on failure-heavy files; the "Draw N" repro blob is dropped, counts unchanged) |
| `SKIPS_FILE=… XFAILS_FILE=… …` | gap machinery (suite-native flags; the files live with the grading task, never upstream) |

Anything after the script name is passed straight to pytest. Other knobs:
`SUITE_DIR`, `TEST_PY`, `REPORTS`, `API_VERSION`, `NO_EXPLAIN`.

## 4. Reading the results

- Whole-suite report `reports/<module>-<stamp>.json` plus a `.meta.json`
  sidecar (module version, suite commit, max-examples); run.sh prints
  `summarize_report.py`'s breakdown for whole-suite runs — failures grouped
  by *spec function* (the suite attaches `array_api_function_name` per
  test), not by node id.
- `CHUNKED=1` writes one report per suite file
  (`<module>-chunk-<file>-<stamp>.json`) and merges the totals.
- Derandomization is on by default, so runs compare across modules and
  days; `FRESH=1` for canonical numbers.

## 5. Chunked mode is mandatory for red runs

`CHUNKED=1` runs one pytest process per suite file: a runaway or aborting
test then costs one file's process, not the whole run. `run.sh` treats a
chunk that dies without a report as a HARD ERROR — a silent merge once
dropped a whole file from the totals (2026-10-04: collection read 1366
instead of 1382, unnoticed until re-checked). After any chunked run,
confirm chunk count == number of `array_api_tests/test_*.py` files (19 at
pin `6c0b59f`).

On a red module, wall time is dominated by hypothesis's *explain* phase (the
post-failure "Draw N ..." minimal-explanation blob) — measured 2026-10-04:
34.2s of a 36.8s failure-heavy file, while generate/shrink were 1.3s/0.8s;
~1000 failures × per-failure explain is the whole run. `NO_EXPLAIN=1` drops
the phase (bundled `no_explain.py`; loads a child of the suite's hypothesis
profile in `pytest_configure` — a later load does not take effect). Keep it
unset when one failure's explanation blob is the evidence you need.

With `NO_EXPLAIN=1` and a warm `.hypothesis` DB the whole 19-file chunked
suite runs in **~60 s** (measured 2026-10-05), and the wall time did not move
between wheel opt-levels 0/2/3 — the suite measures conformance, not Rust
speed, so never read suite time as a performance signal (see §1 for that
measurement).

## 6. Debugging a balloon or abort

- Suite inputs are bounded (arrays ≤ 1024 elements, `MAX_ARRAY_SIZE`); if
  RSS explodes, the bug is in the module under test, not the suite. Sample
  `ps -o rss= -p $PID` against pytest `-v` progress to find the test.
- A Rust allocation failure aborts the process — hypothesis never reaches
  "Falsifying example". Wrap the shim with a call logger writing to
  `sys.__stderr__` (plain `print` is swallowed by pytest's fd-level capture;
  run pytest with `-s` as well): the last logged call is the culprit.
- `ulimit -v <kb>` bounds a repro's blast radius; `journalctl -k | grep -i
  'out of memory'` gives the RSS at kernel kill time.
- Historical hazard, fixed 2026-10-04 rust-side: `rt::arange` used to loop
  forever on a step pointing away from the stop (`arange(0, 4.15e9,
  step=-1.3e8)` OOM'd the machine). The lesson stands: a Rust-side runaway
  aborts the process, so suite red runs stay CHUNKED and repros stay under
  `ulimit` until the culprit is fixed and verified.

## 7. Discipline (rstsr project rules)

- The grading task owns its gap register: every divergence of
  `rstsr_faer.api` from the standard gets an entry, categorized
  `rust-side` / `shim-side` / `suite`. Rust-side problems are never fixed
  agent-side: register them and wait for the maintainer.
- Zero rstsr-core/rstsr-native-impl edits from the testing side without
  owner permission; the shim (`crates-interop/rstsr-faer-py`) is a pure
  **wrapper**: marshalling, validation, and rstsr calls only — no
  algorithms in either its Rust or Python layer. A missing capability is a
  register entry and a rust-side fix request; a shim-side algorithm needs
  the owner's explicit per-case permission, and each workaround must be
  backed by a register entry.
- Never publish the wheel; it is a local validation instrument only.
