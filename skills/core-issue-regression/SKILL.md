---
name: core-issue-regression
description: Write a regression test for a reported rstsr-core issue, in tests/test_issues/. Mirrors NumPy's test_regression.py pattern - one test per ticket, citing the issue number.
---

# core-issue-regression: tests for reported issues

Add a regression test when a bug is reported against rstsr-core, so it cannot silently
return. Mirrors NumPy's `test_regression.py` convention: one test per ticket, the
ticket number in the test name/comment, grouped in one place.

## Location & structure

- One file per issue: `rstsr-core/tests/test_issues/issue_<n>.rs`, declared in
  `test_issues/mod.rs`.
- A test module per issue, included by every entry binary via `mod test_issues;`
  (see `test-conventions` §1-2).

```rust
// issue_77.rs
use crate::test_utils::*;
use rstsr::prelude::*;
use crate::TESTCFG;

#[cfg(test)]
mod issue_77 {
    use super::*;
    static FUNC: &str = "issue_77";

    #[test]
    fn regression() {
        // Issue #77: <one-line summary>
        crate::specify_test!("regression");

        let mut device = TESTCFG.device.clone();
        device.set_default_order(RowMajor);
        // ... minimal reproducer + assert
    }
}
```

## Rules

- **Minimal reproducer.** Cut the report down to the smallest input that triggers the
  bug. No sprawling fixtures.
- **Cite the issue number** in the module name (`issue_<n>`), `FUNC`, and a leading
  comment.
- **Run on the device matrix** (`entry_row_cpu`, `entry_row_faer`) - a regression that
  only manifests on one device is still a regression.
- If the issue is layout/order-specific, note it; otherwise the test should be
  order-agnostic (it runs in the row-major entries; col-major gets its own if needed).
- Do **not** mark `not-applicable` NumPy rows for these - issue tests are rstsr-internal
  regressions, not NumPy parity. They are tracked separately from
  `numpy_coverage.csv`.
