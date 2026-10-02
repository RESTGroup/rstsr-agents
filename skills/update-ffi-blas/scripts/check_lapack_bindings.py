#!/usr/bin/env python3
"""Coverage and header-parity checks for the rstsr-lapack-ffi bindings.

Run after `rstsr-lapack-ffi/scripts/perform_bindgen.py` regenerates the
bindings. A missing or renamed symbol still compiles, so this script is the
binding gate that `cargo check` cannot provide.

Checks:
  1. every function declared in the vendored headers of each module has a
     binding in `src/<module>/ffi_extern.rs` (and no stale binding remains);
  2. the four dyload files of each module carry exactly the same function set;
  3. the generated code uses the feature-dependent `lapack_int` / `blas_int`
     aliases from `rstsr-cblas-base` rather than local definitions or
     hard-coded integers (a silent generator no-op otherwise disables
     `ilp64` / `lp64_as_int`);
  4. with `--upstream`, the vendored `header/` files match the upstream
     CBLAS/LAPACKE include directories byte-for-byte (the two
     `*_mangling_with_flags.h.in` files are vendored under their final name).

Exit code 0 = all checks pass. Written for the LAPACK v3.12.1 header format
(also verified against upstream master 74d4d637); a parse that suddenly loses
most of its symbols is reported as a checker failure rather than a pass.
"""

import argparse
import os
import re
import sys

# module -> vendored header declaring its symbols
MODULES = {
    "blas": "cblas_f77.h",
    "cblas": "cblas.h",
    "lapack": "lapack.h",
    "lapacke": "lapacke.h",
    "lapacke_utils": "lapacke_utils.h",
}

# a parse yielding fewer symbols than this means the header format changed
# under the checker; fail loudly instead of reporting a false pass
MIN_EXPECTED = {"blas": 100, "cblas": 100, "lapack": 1000, "lapacke": 2000, "lapacke_utils": 100}

MANGLE_RENAME = {
    "cblas_mangling_with_flags.h.in": "cblas_mangling.h",
    "lapacke_mangling_with_flags.h.in": "lapacke_mangling.h",
}

# local definitions of these names shadow the glob-imported aliases from
# rstsr-cblas-base and silently disable the ilp64 / lp64_as_int features
LOCAL_ALIAS = re.compile(r"pub type\s+(lapack_int|blas_int|F77_INT|CBLAS_INT)\s*=")
LOCAL_CBLAS_ENUM = re.compile(r"pub (enum|struct|type)\s+CBLAS_(LAYOUT|TRANSPOSE|UPLO|DIAG|SIDE|ORDER)\b")

# module -> (alias, minimum uses in ffi_extern.rs); hard-coded integers
# instead of the alias drive the count far below these floors
ALIAS_USAGE = {
    "blas": ("blas_int", 100),
    "cblas": ("blas_int", 100),
    "lapack": ("lapack_int", 1000),
    "lapacke": ("lapack_int", 1000),
    "lapacke_utils": ("lapack_int", 100),
}

# LAPACKE constants the generator retypes: matrix layout is always c_int,
# error codes follow lapack_int
LAPACKE_BASE_CONSTANTS = (
    "pub const LAPACK_ROW_MAJOR: c_int",
    "pub const LAPACK_WORK_MEMORY_ERROR: lapack_int",
)


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def strip_directives(text):
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def expected_symbols(module, header_text):
    text = strip_comments(header_text)
    if module == "blas":
        # #define F77_dnrm2_sub_base F77_GLOBAL_SUFFIX(dnrm2sub,DNRM2SUB) -> dnrm2sub_
        suffixes = re.findall(
            r"^#define\s+F77_[A-Za-z0-9_]+?_base\s+F77_GLOBAL_SUFFIX\s*\(\s*([A-Za-z0-9_]+)",
            text,
            re.M,
        )
        symbols = {name + "_" for name in suffixes}
        # generator synthesizes value-returning `x_` from subroutine `xsub_`
        symbols |= {name[:-4] + "_" for name in symbols if name.endswith("sub_")}
        return symbols
    if module == "lapack":
        names = re.findall(r"^#define\s+LAPACK_([A-Za-z0-9_]+?)(?:_base)?\s+LAPACK_GLOBAL", text, re.M)
        return {name + "_" for name in names}
    if module == "cblas":
        return set(re.findall(r"\b(cblas_[a-z0-9_]+)\s*\(", text))
    if module == "lapacke":
        names = set(re.findall(r"\b(LAPACKE_[A-Za-z0-9_]+)\s*\(", strip_directives(text)))
        # the two `lapack_make_complex_*` helpers are declared without the LAPACKE_ prefix
        names |= set(re.findall(r"\b(lapack_make_complex_[a-z0-9_]+)\s*\(", strip_directives(text)))
        return names
    if module == "lapacke_utils":
        names = set(re.findall(r"API_SUFFIX\s*\(\s*(LAPACKE_[A-Za-z0-9_]+)\s*\)\s*\(", text))
        names |= set(re.findall(r"\b(LAPACKE_[A-Za-z0-9_]+)\s*\(", strip_directives(text)))
        return names
    raise AssertionError(module)


def binding_symbols(path):
    text = open(path).read()
    return set(re.findall(r"pub (?:unsafe )?fn ([A-Za-z0-9_]+)\s*\(", text))


def check_module(repo, module):
    header_path = os.path.join(repo, "rstsr-lapack-ffi", "header", MODULES[module])
    module_dir = os.path.join(repo, "rstsr-lapack-ffi", "src", module)
    expected = expected_symbols(module, open(header_path).read())
    if len(expected) < MIN_EXPECTED[module]:
        return [f"{module}: parsed only {len(expected)} symbols from {MODULES[module]} - "
                f"header format changed, update check_lapack_bindings.py"]
    problems = []
    found = binding_symbols(os.path.join(module_dir, "ffi_extern.rs"))
    missing, extra = sorted(expected - found), sorted(found - expected)
    if missing:
        problems.append(f"{module}: {len(missing)} declared symbol(s) missing from ffi_extern.rs: {missing[:8]}")
    if extra:
        problems.append(f"{module}: {len(extra)} stale binding(s) not declared in header: {extra[:8]}")
    for variant in ("dyload_struct.rs", "dyload_initializer.rs", "dyload_compatible.rs"):
        path = os.path.join(module_dir, variant)
        text = open(path).read()
        if variant == "dyload_struct.rs":
            names = set(re.findall(r"pub ([A-Za-z0-9_]+):\s*\n?\s*Option<", text))
        elif variant == "dyload_initializer.rs":
            names = set(re.findall(r"([A-Za-z0-9_]+): get_symbol\(", text))
        else:
            names = binding_symbols(path)
        if names != found:
            problems.append(f"{module}: {variant} carries a different function set than ffi_extern.rs")
    print(f"  {module}: {len(expected)} declared, {len(found)} bound - "
          + ("OK" if not problems else "FAIL"))
    return problems


def check_type_plumbing(repo):
    problems = []
    base_dir = os.path.join(repo, "rstsr-lapack-ffi", "src")
    for module in MODULES:
        base = open(os.path.join(base_dir, module, "ffi_base.rs")).read()
        for match in LOCAL_ALIAS.finditer(base):
            problems.append(f"{module}: ffi_base.rs defines a local {match.group(1)} alias "
                            f"(must come from rstsr-cblas-base, or ilp64/lp64_as_int are ignored)")
        for match in LOCAL_CBLAS_ENUM.finditer(base):
            problems.append(f"{module}: ffi_base.rs defines a local {match.group(0)!r} "
                            f"(must come from rstsr-cblas-base)")
    for module, (alias, minimum) in ALIAS_USAGE.items():
        text = open(os.path.join(base_dir, module, "ffi_extern.rs")).read()
        uses = len(re.findall(rf"\b{alias}\b", text))
        if uses < minimum:
            problems.append(f"{module}: only {uses} uses of {alias} in ffi_extern.rs "
                            f"(expected >= {minimum}) - signatures may hard-code integers")
    lapacke_base = open(os.path.join(base_dir, "lapacke", "ffi_base.rs")).read()
    for needle in LAPACKE_BASE_CONSTANTS:
        if needle not in lapacke_base:
            problems.append(f"lapacke: ffi_base.rs is missing {needle!r} (generator retype missed?)")
    print("  type plumbing: " + ("OK" if not problems else "FAIL"))
    return problems


def check_header_parity(repo, upstream):
    problems = []
    vendored_dir = os.path.join(repo, "rstsr-lapack-ffi", "header")
    for subdir in ("CBLAS/include", "LAPACKE/include"):
        src_dir = os.path.join(upstream, subdir)
        for name in sorted(os.listdir(src_dir)):
            if not (name.endswith(".h") or name.endswith(".h.in")):
                continue
            vendored = MANGLE_RENAME.get(name, name)
            a, b = os.path.join(src_dir, name), os.path.join(vendored_dir, vendored)
            if not os.path.exists(b):
                problems.append(f"header: {vendored} is missing (upstream has {subdir}/{name})")
            elif open(a, "rb").read() != open(b, "rb").read():
                problems.append(f"header: {vendored} differs from {subdir}/{name}")
    if not problems:
        print("  header parity: all vendored headers match the upstream checkout - OK")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="path to the rstsr-ffi repository")
    parser.add_argument("--upstream", help="path to the LAPACK checkout for header-parity checking")
    args = parser.parse_args()

    problems = []
    print("binding coverage (vendored header -> src/<module>/ffi_extern.rs):")
    for module in MODULES:
        problems += check_module(args.repo, module)
    print("type plumbing (feature-dependent aliases must come from rstsr-cblas-base):")
    problems += check_type_plumbing(args.repo)
    if args.upstream:
        print(f"header parity (vendored header/ vs {args.upstream}):")
        problems += check_header_parity(args.repo, args.upstream)

    if problems:
        print("\nFAILURES:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
