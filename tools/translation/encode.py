#!/usr/bin/env python3
"""Encodes text as a MSG_BIN initializer, for the C string tables.

    python3 tools/translation/encode.py "Tria un joc:"
    { 0x34, 0x52, 0x49, 0x41, 0xF7, ... 0xFD }  // 85 px

Used for the strings that are C arrays rather than messages (TRANSLATION.md).
The width is what the game measures, to compare with the space the menu gives.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from msgtext import CHARSET_STANDARD, FontMetrics  # noqa: E402


def encode(text: str) -> list:
    codes = []
    for c in text:
        if c not in CHARSET_STANDARD or not isinstance(CHARSET_STANDARD[c], int):
            sys.exit(f"error: '{c}' is not in the font")
        codes.append(CHARSET_STANDARD[c])
    return codes + [0xFD]


def width(codes: list, metrics: FontMetrics) -> int:
    return sum(metrics.space(0, 1.0) if c == 0xF7 else metrics.glyph(c, 0, 1.0) for c in codes[:-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="+")
    args = parser.parse_args()
    metrics = FontMetrics.load()
    for text in args.text:
        codes = encode(text)
        body = ", ".join(f"0x{c:02X}" for c in codes)
        print(f"{{ {body} }}  // {text!r}, {width(codes, metrics)} px")


if __name__ == "__main__":
    main()
