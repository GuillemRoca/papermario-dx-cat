#!/usr/bin/env bash
# Builds the Catalan ROM, lints the translation and makes the .bps patch.
# CI runs this (.github/workflows/translation.yaml); it runs the same locally.
#
# The US base ROM comes from ver/us/baserom.z64 if it's there, otherwise from
# the URL in BASEROM_US_URL (a .z64, or a .zip holding one). Either way its
# SHA1 must match ver/us/checksum.sha1. See TRANSLATION.md.
#
# Outputs, in dist/: papermario-catala-<version>.bps and lint.txt / lint.json.
# The ROM itself is never copied out of the build directory.
#
# RELEASE=1 lints in release mode: every message translated, no warnings.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PMRET_COMMIT=1104f1f71b824042a5fa1f958f2d861b603320fd
FLIPS_COMMIT=ff216a75df0987047a67d7923567dc4482ce07ac
CI_DIR="$ROOT/.ci"
mkdir -p "$CI_DIR" dist

step() { echo "::group::$*" 2>/dev/null || true; echo "== $*"; }
endstep() { echo "::endgroup::" 2>/dev/null || true; }

step "Base ROM"
BASEROM=ver/us/baserom.z64
EXPECTED_SHA1=$(cut -d' ' -f1 ver/us/checksum.sha1)
if [ ! -f "$BASEROM" ]; then
  if [ -z "${BASEROM_US_URL:-}" ]; then
    echo "error: no base ROM. Put it at $BASEROM, or set BASEROM_US_URL (see TRANSLATION.md)." >&2
    exit 1
  fi
  curl -fsSL -o "$CI_DIR/baserom.download" "$BASEROM_US_URL"
  if [ "$(head -c 2 "$CI_DIR/baserom.download")" = "PK" ]; then
    python3 - "$CI_DIR/baserom.download" "$BASEROM" <<'EOF'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    names = [n for n in z.namelist() if n.lower().endswith(".z64")]
    if len(names) != 1:
        sys.exit(f"error: expected one .z64 in the zip, found {names}")
    with open(sys.argv[2], "wb") as out:
        out.write(z.read(names[0]))
EOF
  else
    mv "$CI_DIR/baserom.download" "$BASEROM"
  fi
  rm -f "$CI_DIR/baserom.download"
fi
ACTUAL_SHA1=$(sha1sum "$BASEROM" | cut -d' ' -f1)
if [ "$ACTUAL_SHA1" != "$EXPECTED_SHA1" ]; then
  echo "error: base ROM SHA1 is $ACTUAL_SHA1, expected $EXPECTED_SHA1 (the US ROM, big-endian .z64)" >&2
  exit 1
fi
echo "base ROM ok ($ACTUAL_SHA1)"
endstep

step "Tools"
if ! command -v flips >/dev/null 2>&1; then
  if [ ! -x "$CI_DIR/flips/flips" ]; then
    rm -rf "$CI_DIR/flips"
    git clone --quiet https://github.com/Alcaro/Flips.git "$CI_DIR/flips"
    git -C "$CI_DIR/flips" checkout --quiet "$FLIPS_COMMIT"
    make -C "$CI_DIR/flips" TARGET=cli >/dev/null
  fi
  export PATH="$CI_DIR/flips:$PATH"
fi
UPSTREAM_COMPILER="$CI_DIR/pmret-parse_compile.py"
if [ ! -f "$UPSTREAM_COMPILER" ]; then
  curl -fsSL -o "$UPSTREAM_COMPILER" \
    "https://raw.githubusercontent.com/pmret/papermario/$PMRET_COMMIT/tools/build/msg/parse_compile.py"
fi
endstep

step "Configure"
./tools/configure.sh
export PATH="$ROOT/.dx/unix/bin:$PATH" PYTHONPATH="$ROOT/.dx/unix/python"
endstep

step "Lint"
LINT_ARGS=(--compile --upstream-compiler "$UPSTREAM_COMPILER" --json dist/lint.json)
if [ "${RELEASE:-0}" = "1" ]; then
  LINT_ARGS+=(--complete --strict)
fi
set +e
python3 tools/translation/lint.py "${LINT_ARGS[@]}" | tee dist/lint.txt
LINT_STATUS=${PIPESTATUS[0]}
set -e
endstep

step "Build"
ninja
endstep

step "Patch"
ninja ver/us/build/papermario.bps
VERSION=$(git describe --tags --always --dirty)
cp ver/us/build/papermario.bps "dist/papermario-catala-$VERSION.bps"
flips --apply "dist/papermario-catala-$VERSION.bps" "$BASEROM" "$CI_DIR/check.z64" >/dev/null
if ! cmp -s "$CI_DIR/check.z64" ver/us/build/papermario.z64; then
  echo "error: the patch doesn't reproduce the built ROM" >&2
  exit 1
fi
rm -f "$CI_DIR/check.z64"
echo "dist/papermario-catala-$VERSION.bps ($(wc -c < "dist/papermario-catala-$VERSION.bps") bytes), checked against the build"
endstep

if [ "$LINT_STATUS" != "0" ]; then
  echo "error: the linter found problems (see dist/lint.txt)" >&2
  exit "$LINT_STATUS"
fi
