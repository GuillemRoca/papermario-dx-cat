#!/usr/bin/env bash
# Extracts the reference text into reference/ (gitignored, never committed):
#   reference/en      US English, the source text (copied from DX's own split)
#   reference/es      PAL Spanish, for meaning and register
#   reference/en_pal  PAL English, to match PAL-only lines
#
#   tools/translation/extract_reference.sh path/to/papermario-eu.z64
#
# DX only splits the US ROM, so the PAL text comes from pmret/papermario,
# cloned into reference/.pmret at a pinned commit. Only the message segments
# are split. The PAL checksum isn't enforced: dumps of the EU cartridge
# differ, and the messages are checked by decoding them instead.
set -euo pipefail

PMRET_COMMIT=1104f1f71b824042a5fa1f958f2d861b603320fd

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="$ROOT/reference"
PAL_ROM="${1:?usage: $0 path/to/papermario-eu.z64}"

if [ ! -d "$ROOT/assets/us/msg" ]; then
  echo "error: assets/us/msg is missing; run ./tools/configure.sh once with ver/us/baserom.z64 in place" >&2
  exit 1
fi
if [ "$(head -c 4 "$PAL_ROM" | od -An -tx1 | tr -d ' \n')" != "80371240" ]; then
  echo "error: $PAL_ROM isn't a big-endian .z64 ROM; byteswap it first" >&2
  exit 1
fi

mkdir -p "$REF"
PMRET="$REF/.pmret"
if [ ! -d "$PMRET/.git" ]; then
  git clone --filter=blob:none https://github.com/pmret/papermario "$PMRET"
fi
git -C "$PMRET" fetch --quiet origin "$PMRET_COMMIT" || true
git -C "$PMRET" checkout --quiet "$PMRET_COMMIT"

if [ ! -x "$REF/.venv/bin/python" ]; then
  python3 -m venv "$REF/.venv"
  "$REF/.venv/bin/pip" install --quiet -r "$PMRET/tools/configure/requirements.txt"
fi

cp "$PAL_ROM" "$PMRET/ver/pal/baserom.z64"
sed '/^sha1:/d' "$PMRET/ver/pal/splat.yaml" > "$PMRET/ver/pal/splat_msg.yaml"
(
  cd "$PMRET"
  PYTHONPATH=tools/build:tools "$REF/.venv/bin/python" -m splat split ver/pal/splat_msg.yaml --modes pm_msg
)
rm -f "$PMRET/ver/pal/baserom.z64"

for dir in en es en_pal; do
  rm -rf "${REF:?}/$dir"
  mkdir -p "$REF/$dir"
done
cp "$ROOT"/assets/us/msg/*.msg "$REF/en/"
cp "$PMRET"/assets/pal/msg_pal_es/*.msg "$REF/es/"
cp "$PMRET"/assets/pal/msg_pal_en/*.msg "$REF/en_pal/"

# PAL keeps every US message name and adds PAL_* ones, so the two can be
# matched by section and name. Check that before anyone relies on it.
python3 - "$REF" <<'EOF'
import re, sys
from pathlib import Path

ref = Path(sys.argv[1])
header = re.compile(r"^#message:([0-9A-F]{2}):\(([^)]+)\)", re.M)
for us in sorted((ref / "en").glob("*.msg")):
    es = ref / "es" / us.name
    us_names = set(header.findall(us.read_text(encoding="utf-8")))
    es_names = set(header.findall(es.read_text(encoding="utf-8")))
    missing = us_names - es_names
    if missing:
        sys.exit(f"error: {es.name} lacks {len(missing)} US messages, e.g. {sorted(missing)[:3]}")
print(f"reference/: {len(list((ref / 'es').glob('*.msg')))} Spanish files, every US message matched by name")
EOF
