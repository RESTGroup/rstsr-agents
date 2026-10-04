#!/usr/bin/env bash
#
# One-time setup for grading rstsr-faer-py against the Array API conformance
# suite — see ../SKILL.md.
#
# Knobs:
#   SUITE_DIR     suite checkout location   (default ~/array-api-tests)
#   TEST_PY       test interpreter          (default python3 on PATH)
#   SUITE_COMMIT  suite pin                 (default 6c0b59f)
#   SPEC_LOCAL    optional sibling array-api clone for offline submodule init
#
# Produces:
#   - suite checkout @ SUITE_COMMIT with spec submodule @ 5f847a3
#   - test deps (pytest, pytest-json-report, hypothesis, ndindex) installed
#     into TEST_PY's environment — no overlay venv; numpy itself untouched
#
set -euo pipefail

TEST_PY="${TEST_PY:-$(command -v python3)}"
SUITE_DIR="${SUITE_DIR:-$HOME/array-api-tests}"
SUITE_COMMIT="${SUITE_COMMIT:-6c0b59f9ecd654f0c356614f2e421c9993f676d2}"
SPEC_COMMIT="5f847a3858875c682ae901aa22b0413bf24be9da"

# ------------------------------------------------- 1. the suite checkout ----
echo "==> conformance suite ($SUITE_DIR)"
if [ ! -d "$SUITE_DIR/.git" ]; then
    git clone --quiet https://github.com/data-apis/array-api-tests.git "$SUITE_DIR" \
        || {  # HTTPS to github is unreliable on some networks; retry via SSH
            rm -rf "$SUITE_DIR"
            git clone --quiet git@github.com:data-apis/array-api-tests.git "$SUITE_DIR"
        }
fi
git -C "$SUITE_DIR" checkout --quiet "$SUITE_COMMIT"

# The spec repo is executable test data (stubs.py imports it; test_special_cases
# parses its docstrings) — the suite asserts its presence at import time.
# Offline-first when SPEC_LOCAL points at a clone holding the pin (local-path
# submodule clones need -c protocol.file.allow=always); SSH fallback otherwise.
if ! git -C "$SUITE_DIR" submodule status 2>/dev/null | grep -q '^ '; then
    if [ -n "${SPEC_LOCAL:-}" ] && [ -d "$SPEC_LOCAL/.git" ] \
            && git -C "$SPEC_LOCAL" cat-file -e "$SPEC_COMMIT" 2>/dev/null; then
        echo "    submodule: initializing offline from $SPEC_LOCAL"
        SUBMOD_NAME="$(git -C "$SUITE_DIR" config -f .gitmodules --get-regexp '\.path=' \
            | awk -F'= ' -v p="array-api" '$2==p {k=$1; sub(/\.path$/, "", k); sub(/^submodule\./, "", k); print k}')"
        git -C "$SUITE_DIR" config "submodule.$SUBMOD_NAME.url" "$SPEC_LOCAL"
        git -C "$SUITE_DIR" -c protocol.file.allow=always submodule update --init --quiet
    elif ! git -C "$SUITE_DIR" submodule update --init --quiet 2>/dev/null; then
        echo "    submodule: default fetch failed; retrying via ssh"
        git -C "$SUITE_DIR" config url."git@github.com:".insteadOf "https://github.com/"
        git -C "$SUITE_DIR" submodule update --init --quiet
    fi
else
    git -C "$SUITE_DIR" submodule update --init --quiet
fi
echo "    suite : $(git -C "$SUITE_DIR" rev-parse --short HEAD)"
echo "    spec  : $(git -C "$SUITE_DIR/array-api" rev-parse --short HEAD)"

# ------------------------------------------------- 2. test deps -------------
echo "==> test deps -> $("$TEST_PY" -c 'import sys; print(sys.executable)')"
# The suite's requirements.txt lists only pytest, pytest-json-report,
# hypothesis, ndindex. numpy is untouched (only the MODULE=numpy baseline
# needs it).
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$TEST_PY" --quiet -r "$SUITE_DIR/requirements.txt"
else
    "$TEST_PY" -m pip install --quiet -r "$SUITE_DIR/requirements.txt"
fi

# ------------------------------------------------- 3. prove it --------------
echo "==> check: interpreter + deps"
"$TEST_PY" - <<'PY'
import sys
import pytest, hypothesis, ndindex
print(f"    python    : {sys.executable}")
print(f"    pytest    : {pytest.__version__}")
print(f"    hypothesis: {hypothesis.__version__}")
print(f"    ndindex   : {ndindex.__version__}")
PY

echo
echo "Done.  Next (see ../SKILL.md):"
echo "    MODULE=numpy ./run.sh                      # baseline gate"
echo "    MODULE=rstsr_faer.api CHUNKED=1 ./run.sh   # subject under test"
