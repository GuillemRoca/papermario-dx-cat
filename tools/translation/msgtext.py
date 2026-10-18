"""Reads .msg files the way tools/build/msg/parse_compile.py does, and measures
lines the way the game does.

The charsets, the command parser and the comment stripper are imported from
the compiler itself, so this module can't drift from what actually builds.
Glyph widths are read from src/font_width/msg_data.c and src/enums.h.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build" / "msg"))

try:
    import msgpack  # noqa: F401
except ImportError:
    # the compiler imports msgpack for its output only; the linter needs just the standard library
    import types

    sys.modules["msgpack"] = types.ModuleType("msgpack")

import parse_compile  # noqa: E402

CHARSET_STANDARD = parse_compile.CHARSET_STANDARD
CHARSET_CREDITS = parse_compile.CHARSET_CREDITS

# A header both the DX and the pmret/papermario compilers accept: upstream reads
# the directive up to the first space, DX up to the brace.
PORTABLE_HEADER = re.compile(r"^#message:([0-9A-F]{2}):(\(([A-Za-z0-9_]+)\)|([0-9A-F]{3})) \{$")

# Commands without arguments that print one glyph of the standard font.
GLYPH_COMMANDS = {
    "note": 0x00,
    "heart": 0x90,
    "star": 0x91,
    "up": 0x92,
    "down": 0x93,
    "left": 0x94,
    "right": 0x95,
    "circle": 0x96,
    "cross": 0x97,
    "a": 0x98,
    "b": 0x99,
    "l": 0x9A,
    "r": 0x9B,
    "z": 0x9C,
    "start": 0xA1,
}
C_BUTTON_GLYPHS = {"up": 0x9D, "down": 0x9E, "left": 0x9F, "right": 0xA0}

# Commands that end a line or a page. A line is measured between these.
LINE_BREAKS = {"br", "next", "end"}

FONT_IDS = {"standard": 0, "menu": 1, "menu2": 2, "title": 3, "subtitle": 4}


@dataclass
class Token:
    kind: str  # "text" or "cmd"
    value: str  # the character, or the lowercased command name
    raw: str  # source text, e.g. "[Style right]"
    line: int
    args: list = field(default_factory=list)
    named: dict = field(default_factory=dict)

    def signature(self) -> str:
        """What must match the vanilla message: the command and its arguments."""
        inner = self.raw[1:-1].split(" ")
        return " ".join([inner[0].lower()] + [a.lower() for a in inner[1:] if a])


@dataclass
class Message:
    section: int
    name: Optional[str]
    index: Optional[int]
    header: str
    line: int
    tokens: List[Token]

    @property
    def key(self) -> str:
        return self.name if self.name is not None else f"{self.index:03X}"

    def text(self) -> str:
        return "".join(t.value for t in self.tokens if t.kind == "text")

    def commands(self) -> List[Token]:
        return [t for t in self.tokens if t.kind == "cmd"]


@dataclass
class Problem:
    line: int
    message: str


@dataclass
class MsgFile:
    path: Path
    messages: List[Message]
    problems: List[Problem]  # syntax problems found while reading


def read_msg_file(path: Path) -> MsgFile:
    raw = path.read_bytes()
    problems: List[Problem] = []
    if b"\r" in raw:
        problems.append(Problem(1, "file has CR line endings; use LF only (upstream pmret mis-parses CR)"))
    source = raw.decode("utf-8")
    if source.startswith("﻿"):
        problems.append(Problem(1, "file starts with a UTF-8 BOM; remove it"))
        source = source[1:]

    for lineno, text in enumerate(source.split("\n"), 1):
        if "//" in text or "/*" in text:
            problems.append(
                Problem(
                    lineno,
                    "comment in a .msg file: the compilers treat '...' spans as C strings, so with apostrophes a "
                    "comment can end up compiled as text. Put notes in notes/ instead",
                )
            )

    stripped = parse_compile.strip_c_comments(source).replace("\r", "")
    messages: List[Message] = []
    i = 0
    lineno = 1
    n = len(stripped)
    while i < n:
        c = stripped[i]
        if c == "\n":
            lineno += 1
            i += 1
            continue
        if c in " \t":
            i += 1
            continue
        # a header runs to the opening brace
        start_line = lineno
        brace = stripped.find("{", i)
        if brace == -1:
            problems.append(Problem(lineno, "text outside a message"))
            break
        header_text = stripped[i : brace + 1]
        lineno += header_text.count("\n")
        header_line = header_text.strip()
        i = brace + 1
        m = PORTABLE_HEADER.match(header_line)
        if not m:
            problems.append(
                Problem(
                    start_line,
                    f"header '{header_line}' isn't portable; write '#message:SS:(Name) {{' on one line, "
                    "with one space before the brace",
                )
            )
            loose = re.match(r"#message:([0-9A-Fa-f]+):\s*(\(([^)]*)\)|([0-9A-Fa-f]+))", header_line.replace(" ", ""))
            if not loose:
                break
            section = int(loose.group(1), 16)
            name = loose.group(3)
            index = int(loose.group(4), 16) if loose.group(4) else None
        else:
            section = int(m.group(1), 16)
            name = m.group(3)
            index = int(m.group(4), 16) if m.group(4) else None

        tokens: List[Token] = []
        closed = False
        while i < n:
            c = stripped[i]
            if c == "\t":
                i += 1
                continue
            if c == "\n":
                lineno += 1
                i += 1
                continue
            if c == "[":
                end = stripped.find("]", i)
                newline = stripped.find("\n", i)
                if end != -1 and (newline == -1 or end < newline):
                    raw_cmd = stripped[i : end + 1]
                    command, args, named, _ = parse_compile.parse_command(raw_cmd + " ")
                    tokens.append(Token("cmd", command, raw_cmd, lineno, args, named))
                    i = end + 1
                    continue
            if c == "}":
                closed = True
                i += 1
                break
            if c == "\\" and i + 1 < n:
                i += 1
                c = stripped[i]
            tokens.append(Token("text", c, c, lineno))
            i += 1
        if not closed:
            problems.append(Problem(start_line, "message is missing its closing brace"))
        messages.append(Message(section, name, index, header_line, start_line, tokens))

    return MsgFile(path, messages, problems)


def charset_problems(msg: Message) -> List[Problem]:
    """Characters the compiler would reject, given the font switches."""
    problems = []
    charset = CHARSET_STANDARD
    for t in msg.tokens:
        if t.kind == "cmd" and t.value == "font" and t.args:
            charset = CHARSET_CREDITS if t.args[0] in ("title", "subtitle") else CHARSET_STANDARD
        elif t.kind == "text" and t.value not in charset:
            hint = ""
            if t.value == "·":
                hint = " (no middle dot in the font: write l.l)"
            elif charset is CHARSET_CREDITS:
                hint = " (credits font: uppercase A-Z, digits, ' . , & © only)"
            problems.append(Problem(t.line, f"character '{t.value}' U+{ord(t.value):04X} is not in the font{hint}"))
    return problems


# --- glyph widths -----------------------------------------------------------------------------


@dataclass
class FontMetrics:
    normal: Dict[int, int]  # charset code -> width, standard and menu fonts
    title: List[int]
    subtitle: List[int]
    monospace: Dict[int, int]  # font id -> monospace width, used for spaces

    @classmethod
    def load(cls, root: Path = ROOT) -> "FontMetrics":
        enums = (root / "src" / "enums.h").read_text(encoding="utf-8")
        # the non-JP character enum starts at MSG_CHAR_NOTE = 0x00
        start = enums.index(re.search(r"MSG_CHAR_NOTE\s*=\s*0x00", enums).group(0))
        end = enums.index("#endif", start)
        codes = {k: int(v, 16) for k, v in re.findall(r"(MSG_CHAR_\w+)\s*=\s*(0x[0-9A-Fa-f]+)", enums[start:end])}

        data = (root / "src" / "font_width" / "msg_data.c").read_text(encoding="utf-8")
        block = data[data.index("u8 MsgCharWidthNormal[]", data.index("#else")) :]
        block = block[: block.index("};")]
        # take the #else side of the iQue-only override
        block = re.sub(r"#if VERSION_IQUE.*?#else(.*?)#endif", r"\1", block, flags=re.S)
        normal = {codes[name]: int(w) for name, w in re.findall(r"\[(MSG_CHAR_\w+)\]\s*(\d+)", block)}

        def table(name: str) -> List[int]:
            body = data[data.index(f"u8 {name}[]") :]
            body = body[body.index("{") + 1 : body.index("};")]
            return [int(x) for x in re.findall(r"\d+", body)]

        us_data = data[data.index("u8 MsgCharWidthNormal[]", data.index("#else")) :]

        def mono(name: str, default: int) -> int:
            # the US definitions follow the US width table; the JP ones come before it
            m = re.search(rf"{name}\[\]\s*=\s*\{{.*?monospaceWidth\s*=\s*(\d+)", us_data, re.S)
            return int(m.group(1)) if m else default

        monospace = {
            0: mono("MsgCharDataNormal", 10),
            1: mono("MsgCharDataMenu", 9),
            2: mono("MsgCharDataMenu", 9),
            3: mono("MsgCharDataTitle", 12),
            4: mono("MsgCharDataSubtitle", 12),
        }
        return cls(normal, table("MsgCharWidthTitle"), table("MsgCharWidthSubtitle"), monospace)

    def glyph(self, code: int, font: int, scale: float) -> int:
        # msg_get_print_char_width truncates each glyph's scaled width to an int
        if font == 3:
            width = self.title[code] if code < len(self.title) else self.monospace[3]
        elif font == 4:
            width = self.subtitle[code] if code < len(self.subtitle) else self.monospace[4]
        else:
            width = self.normal.get(code, self.monospace.get(font, 10))
        return int(width * scale)

    def space(self, font: int, scale: float) -> int:
        return int(self.monospace.get(font, 10) * scale * 0.6)


@dataclass
class Line:
    text: str  # the line with commands shown, for reports
    width: int  # pixels, not counting [Var] contents
    has_var: bool
    tokens: List[Token]


def measure_lines(msg: Message, metrics: FontMetrics) -> List[Line]:
    """Split a message at [BR], [Next] and [End] and measure each line.

    Mirrors get_msg_properties (src/engine2/msg.c): each glyph adds its table
    width times the [Size] scale, truncated; spaces use 0.6 of the font's
    monospace width; [Var n] adds the variable's width, which isn't known
    here, so the line is marked instead. [SetPosX n] and [Right n] move the
    pen when drawing, so they're applied as well.
    """
    lines: List[Line] = []
    width = 0
    font = 0
    scale = 1.0
    has_var = False
    current: List[Token] = []

    def flush():
        nonlocal width, has_var, current
        text = "".join(t.raw for t in current)
        lines.append(Line(text, width, has_var, current))
        width = 0
        has_var = False
        current = []

    for t in msg.tokens:
        if t.kind == "cmd" and t.value in LINE_BREAKS:
            flush()
            continue
        current.append(t)
        if t.kind == "text":
            charset = CHARSET_CREDITS if font in (3, 4) else CHARSET_STANDARD
            code = charset.get(t.value)
            if code is None:
                continue
            if code == 0xF7:
                width += metrics.space(font, scale)
            elif isinstance(code, int):
                width += metrics.glyph(code, font, scale)
            continue
        name, args = t.value, t.args
        if name in GLYPH_COMMANDS and not args:
            width += metrics.glyph(GLYPH_COMMANDS[name], font, scale)
        elif name == "c" and args and args[0] in C_BUTTON_GLYPHS:
            width += metrics.glyph(C_BUTTON_GLYPHS[args[0]], font, scale)
        elif name == "font" and args:
            font = FONT_IDS.get(args[0], font)
        elif name == "size" and args:
            sizes = args[0] if isinstance(args[0], list) else [args[0]]
            scale = (sizes[-1] if len(sizes) > 1 else sizes[0]) / 16.0
        elif name == "sizereset":
            scale = 1.0
        elif name == "var":
            has_var = True
        elif name == "setposx" and args and isinstance(args[0], int):
            width = args[0]
        elif name == "right" and args and isinstance(args[0], int):
            width += args[0]
    if current:
        flush()
    return lines


def style_of(msg: Message) -> Tuple[Optional[str], dict, list]:
    for t in msg.tokens:
        if t.kind == "cmd" and t.value == "style":
            return (str(t.args[0]) if t.args else None), t.named, t.args[1:]
    return None, {}, []


WORD = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:['’][A-Za-zÀ-ÿ0-9]+)*")


def count_words(text: str) -> int:
    return len(WORD.findall(text))
