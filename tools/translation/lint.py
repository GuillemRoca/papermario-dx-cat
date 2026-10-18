#!/usr/bin/env python3
"""Lints translated .msg files against the vanilla ones.

    python3 tools/translation/lint.py                 # lint translation/assets/msg
    python3 tools/translation/lint.py --complete      # also require every message (release)
    python3 tools/translation/lint.py --compile --upstream-compiler PATH

Checks, per translated file:
  - the file and every message ID exist in vanilla, in vanilla order, once each;
  - headers use the syntax both the DX and the pmret/papermario compilers accept;
  - every control code, tag and variable matches the vanilla message exactly,
    so line and page structure are unchanged;
  - every character is in the font (no middle dot: write l.l), and flags
    letters that aren't Catalan, which usually means Spanish slipped in;
  - each line's pixel width, from the game's own width table, against the box
    it's drawn in and against the vanilla line;
  - how much of each file is translated.

Exit status is 1 if there are errors (or warnings, with --strict).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from msgtext import (  # noqa: E402
    ROOT,
    FontMetrics,
    Message,
    charset_problems,
    count_words,
    measure_lines,
    read_msg_file,
    style_of,
)

# Text area per message style, in pixels. "hard" is where the game clips or
# the box stops growing (src/engine2/msg_draw.c, msg.c); "comfort" is about
# the 99th percentile of vanilla lines in that style. A line over "hard" is an
# error. A line over "comfort" that is also wider than the vanilla line it
# replaces is a warning.
STYLE_LIMITS = {
    "right": (252, 240),  # speech bubble: text from x=48, clipped at x=300
    "left": (252, 240),
    "center": (252, 240),
    "tattle": (256, 240),  # box width is clamped to 256
    "inspect": (256, 240),
    "narrate": (256, 240),
    "sign": (245, 238),  # text from x=38, clipped at x=283
    "lamppost": (245, 238),
    "epilogue": (200, 192),  # fixed 200x50 box
    "popup": (288, 240),  # box is the text width + 32, on a 320 px screen
    None: (252, 240),  # no [Style]: the caller picks the box; assume a speech bubble
}
DX_COMPILER = ROOT / "tools" / "build" / "msg" / "parse_compile.py"

# [Var n] contents aren't known here; this is about a typical item name.
VAR_ALLOWANCE = 60

# Letters the font has that Catalan doesn't use.
NON_CATALAN = set("áìùñâêîôûäëößÁÌÙÑÂÊÎÔÛÄËÖ¿¡ª")


@dataclass
class Finding:
    level: str  # "error", "warning" or "info"
    file: str
    line: int
    key: str
    text: str

    def format(self) -> str:
        where = f"{self.file}:{self.line}" if self.line else self.file
        key = f" [{self.key}]" if self.key else ""
        return f"{where}: {self.level}{key}: {self.text}"


@dataclass
class FileStats:
    name: str
    total: int
    present: int = 0
    translated: int = 0
    words_total: int = 0
    words_translated: int = 0
    errors: int = 0
    warnings: int = 0


@dataclass
class Linter:
    vanilla_dir: Path
    translation_dir: Path
    complete: bool = False
    allow_identical: set = field(default_factory=set)
    findings: List[Finding] = field(default_factory=list)
    stats: Dict[str, FileStats] = field(default_factory=dict)

    def __post_init__(self):
        self.metrics = FontMetrics.load()

    def add(self, level: str, file: str, line: int, key: str, text: str):
        self.findings.append(Finding(level, file, line, key, text))
        if file in self.stats:
            if level == "error":
                self.stats[file].errors += 1
            elif level == "warning":
                self.stats[file].warnings += 1

    def run(self, only: Optional[List[str]] = None):
        vanilla_files = {p.name: p for p in sorted(self.vanilla_dir.glob("*.msg"))}
        if not vanilla_files:
            sys.exit(f"error: no vanilla .msg files in {self.vanilla_dir}; build once or extract the reference first")
        translated_files = (
            {p.name: p for p in sorted(self.translation_dir.glob("*.msg"))} if self.translation_dir.is_dir() else {}
        )

        for name in translated_files:
            if name not in vanilla_files:
                self.add("error", name, 0, "", "no vanilla file has this name; files override one-for-one")

        for name, vanilla_path in vanilla_files.items():
            if only and not any(o in name for o in only):
                continue
            vanilla = read_msg_file(vanilla_path)
            stats = FileStats(name, len(vanilla.messages))
            stats.words_total = sum(count_words(m.text()) for m in vanilla.messages)
            self.stats[name] = stats
            if name in translated_files:
                self.lint_file(name, vanilla.messages, translated_files[name])
            elif self.complete:
                self.add("error", name, 0, "", "file not translated yet")

    def lint_file(self, name: str, vanilla: List[Message], path: Path):
        stats = self.stats[name]
        parsed = read_msg_file(path)
        for p in parsed.problems:
            self.add("error", name, p.line, "", p.message)

        section = vanilla[0].section if vanilla else None
        by_key = {m.key: (i, m) for i, m in enumerate(vanilla)}
        seen = set()
        last_index = -1
        for msg in parsed.messages:
            if msg.section != section:
                self.add("error", name, msg.line, msg.key, f"section {msg.section:02X} doesn't match the file's {section:02X}")
                continue
            if msg.key not in by_key:
                self.add(
                    "error",
                    name,
                    msg.line,
                    msg.key,
                    "no vanilla message has this ID; the build would silently add it as a new message",
                )
                continue
            if msg.key in seen:
                self.add("error", name, msg.line, msg.key, "message appears twice")
                continue
            seen.add(msg.key)
            index, original = by_key[msg.key]
            if index < last_index:
                self.add("error", name, msg.line, msg.key, "out of vanilla order")
            last_index = max(last_index, index)
            if msg.header != original.header:
                self.add("error", name, msg.line, msg.key, f"header should be '{original.header}'")
            stats.present += 1
            self.lint_message(name, original, msg)

        missing = [m.key for m in vanilla if m.key not in seen]
        if missing:
            level = "error" if self.complete else "info"
            shown = ", ".join(missing[:8]) + (f" and {len(missing) - 8} more" if len(missing) > 8 else "")
            self.add(level, name, 0, "", f"{len(missing)} messages not translated yet (they show in English): {shown}")

    def lint_message(self, name: str, original: Message, msg: Message):
        stats = self.stats[name]
        ok = True

        # every command must match, in order
        want = [t.signature() for t in original.commands()]
        got = [t.signature() for t in msg.commands()]
        if want != got:
            ok = False
            i = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
            expected = f"[{want[i]}]" if i < len(want) else "nothing more"
            found = f"[{got[i]}]" if i < len(got) else "nothing more"
            line = msg.commands()[i].line if i < len(got) else msg.line
            self.add(
                "error",
                name,
                line,
                msg.key,
                f"control codes differ from vanilla at code #{i + 1}: expected {expected}, found {found}",
            )

        for p in charset_problems(msg):
            ok = False
            self.add("error", name, p.line, msg.key, p.message)

        for t in msg.tokens:
            if t.kind == "text" and t.value in NON_CATALAN:
                self.add("warning", name, t.line, msg.key, f"'{t.value}' isn't used in Catalan (Spanish left over?)")

        if ok:
            self.check_widths(name, original, msg)

        text = msg.text()
        identical = text == original.text()
        has_letters = any(c.isalpha() for c in text)
        if identical and has_letters and msg.key not in self.allow_identical:
            self.add("info", name, msg.line, msg.key, "identical to English; not counted as translated")
        elif ok:  # a message that wouldn't build right doesn't count
            stats.translated += 1
            stats.words_translated += count_words(original.text())

    def check_widths(self, name: str, original: Message, msg: Message):
        style, named, _ = style_of(original)
        old_lines = measure_lines(original, self.metrics)
        new_lines = measure_lines(msg, self.metrics)
        if len(old_lines) != len(new_lines):
            return  # reported as a control code mismatch

        if style in ("choice", "upgrade") and isinstance(named.get("size"), list):
            box = named["size"][0]
            hard, comfort = box - 16, box - 40
        else:
            hard, comfort = STYLE_LIMITS.get(style, STYLE_LIMITS[None])

        for i, (old, new) in enumerate(zip(old_lines, new_lines)):
            width = new.width + (VAR_ALLOWANCE if new.has_var else 0)
            line_no = next((t.line for t in new.tokens if t.kind == "text"), msg.line)
            label = f"line {i + 1} is {new.width} px" + (f" + [Var] (~{VAR_ALLOWANCE})" if new.has_var else "")
            shown = "".join(t.value if t.kind == "text" else t.raw for t in new.tokens).strip()
            if width > hard and new.width > old.width:
                self.add(
                    "error",
                    name,
                    line_no,
                    msg.key,
                    f"{label}, over the {hard} px {style or 'default'} box (vanilla {old.width} px): {shown}",
                )
            elif width > comfort and new.width > old.width:
                self.add(
                    "warning",
                    name,
                    line_no,
                    msg.key,
                    f"{label}, near the {hard} px {style or 'default'} box edge (vanilla {old.width} px): {shown}",
                )

    def compile_check(self, compilers: List[Path]):
        """Runs real compilers on each translated file."""
        for path in sorted(self.translation_dir.glob("*.msg")):
            for compiler in compilers:
                with tempfile.TemporaryDirectory() as tmp:
                    result = subprocess.run(
                        [sys.executable, str(compiler), "us", str(path), str(Path(tmp) / "out.bin")],
                        capture_output=True,
                        text=True,
                    )
                output = (result.stdout + result.stderr).strip()
                if result.returncode != 0 or output:
                    level = "error" if result.returncode != 0 else "warning"
                    detail = output.splitlines()[-1] if output else f"exit status {result.returncode}"
                    label = "DX" if compiler.resolve() == DX_COMPILER.resolve() else str(compiler)
                    self.add(level, path.name, 0, "", f"{label} compiler: {detail}")


def print_report(linter: Linter, show_info: bool):
    order = {"error": 0, "warning": 1, "info": 2}
    for f in sorted(linter.findings, key=lambda f: (f.file, f.line, order[f.level])):
        if f.level != "info" or show_info:
            print(f.format())

    print()
    print(f"{'file':26} {'msgs':>5} {'done':>5} {'%':>6} {'words':>7} {'%words':>7} {'err':>4} {'warn':>4}")
    total = FileStats("TOTAL", 0)
    for s in linter.stats.values():
        pct = 100 * s.translated / s.total if s.total else 0
        wpct = 100 * s.words_translated / s.words_total if s.words_total else 0
        print(
            f"{s.name:26} {s.total:5} {s.translated:5} {pct:5.1f}% {s.words_total:7} {wpct:6.1f}% {s.errors:4} {s.warnings:4}"
        )
        for attr in ("total", "translated", "words_total", "words_translated", "errors", "warnings"):
            setattr(total, attr, getattr(total, attr) + getattr(s, attr))
    pct = 100 * total.translated / total.total if total.total else 0
    wpct = 100 * total.words_translated / total.words_total if total.words_total else 0
    unassigned = sum(1 for f in linter.findings if f.file not in linter.stats and f.level == "error")
    print(
        f"{'TOTAL':26} {total.total:5} {total.translated:5} {pct:5.1f}% {total.words_total:7} {wpct:6.1f}% "
        f"{total.errors + unassigned:4} {total.warnings:4}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--translation", type=Path, default=ROOT / "translation" / "assets" / "msg")
    parser.add_argument(
        "--vanilla",
        type=Path,
        default=None,
        help="vanilla .msg files (default: assets/us/msg, else reference/en)",
    )
    parser.add_argument(
        "--allow-identical",
        type=Path,
        default=ROOT / "translation" / "identical.txt",
        help="message IDs that are meant to stay as in English, one per line",
    )
    parser.add_argument("--complete", action="store_true", help="every file and message must be translated")
    parser.add_argument("--strict", action="store_true", help="fail on warnings too")
    parser.add_argument("--compile", action="store_true", help="also run the DX message compiler on each file")
    parser.add_argument(
        "--upstream-compiler",
        type=Path,
        action="append",
        default=[],
        help="path to pmret/papermario's tools/build/msg/parse_compile.py, to check the files build there too",
    )
    parser.add_argument("--info", action="store_true", help="also list untranslated and identical messages")
    parser.add_argument("--json", type=Path, help="write findings and stats as JSON")
    parser.add_argument("files", nargs="*", help="only lint files whose name contains one of these")
    args = parser.parse_args()

    vanilla = args.vanilla
    if vanilla is None:
        vanilla = ROOT / "assets" / "us" / "msg"
        if not vanilla.is_dir():
            vanilla = ROOT / "reference" / "en"

    allow = set()
    if args.allow_identical.is_file():
        for line in args.allow_identical.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                allow.add(line)

    linter = Linter(vanilla, args.translation, complete=args.complete, allow_identical=allow)
    linter.run(args.files)
    compilers = ([DX_COMPILER] if args.compile else []) + args.upstream_compiler
    if compilers:
        linter.compile_check(compilers)
    print_report(linter, args.info)

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "findings": [f.__dict__ for f in linter.findings],
                    "stats": [s.__dict__ for s in linter.stats.values()],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )

    levels = {f.level for f in linter.findings}
    if "error" in levels or (args.strict and "warning" in levels):
        sys.exit(1)


if __name__ == "__main__":
    main()
