#!/usr/bin/env python3
"""Writes the starting glossary.md: English and PAL Spanish filled in, Catalan empty.

    python3 tools/translation/make_glossary.py translation/glossary.md

Reads the reference text (reference/en, reference/es; see TRANSLATION.md), the
item registry for item types, and the PAL C tables for menu labels. It won't
overwrite an existing glossary, since that's where the Catalan is decided;
pass --stdout to compare against a fresh copy instead.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from msgtext import CHARSET_STANDARD, ROOT, read_msg_file  # noqa: E402

REFERENCE = ROOT / "reference"

# Characters without a name message of their own. The Spanish is read from the
# PAL text: mostly the NPC tattles (1A_NpcTattles), the rest from dialogue.
CHARACTERS: List[Tuple[str, str, str]] = [
    ("Mario", "Mario", "Silent hero; others speak about him."),
    ("Luigi", "Luigi", "Mario's brother; insecure, a bit jealous of Mario's adventures."),
    ("Princess Peach", "Princesa Peach", "Gracious but resourceful and determined."),
    ("Bowser", "Bowser", "Blustering, boastful villain."),
    ("Kammy Koopa", "Kammy Koopa", "Cackling old Magikoopa, fawning over Bowser."),
    ("Jr. Troopa", "Troopa Junior", "Brash, childish bully who never gives up."),
    ("Twink", "Twink", "Sweet, naive Star Kid."),
    ("Goompa", "Goomabuelo", "Goombario's grandpa; rambling storyteller."),
    ("Gooma", "Goomabuela", "Goombario's grandma."),
    ("Goompapa", "Goompapá", "Goombario's dad."),
    ("Goomama", "Goomamá", "Goombario's mom; worrier."),
    ("Goombaria", "Goombaria", "Goombario's spoiled little sister."),
    ("Merlon", "Merlón", "Stubborn, mysterious old wizard who rambles."),
    ("Merlee", "Merlí", "Spell-casting twin."),
    ("Merluvlee", "Merluli", "Fortune-teller twin; glamorous."),
    ("Merlow", "Merlú", "Young; trades Star Pieces for Badges."),
    ("Merle", "Merlé", "Merlon's son; controls Shooting Star Summit's valley."),
    ("Kolorado", "Kolorado", "Famous, careless archaeologist; treasure-crazy."),
    ("Chuck Quizmo", "Chuck", "Quiz-show host."),
    ("Russ T.", "T. Russ", "Know-it-all Toad."),
    ("Tayce T.", "T. Tais", "Best cook around."),
    ("Minh T.", "T. Minh", "Flower lover."),
    ("Harry T.", "Harry", "Shop owner who stores items. PAL drops the 'T.'."),
    ("Fice T.", "T. Fais", "Timid guard of the path to Forever Forest."),
    ("Rip Cheato", "Rip Truco", "Shady merchant."),
    ("Chet Rippo", "Chet Rippo", "Shady point-level 'upgrader'."),
    ("The Master", "el Maestro", "Dojo master."),
    ("Chan", "Chan", "Dojo trainee."),
    ("Lee", "Lee", "Dojo trainee."),
    ("Rowf", "Rolf", "Badge seller."),
    ("Rhuff", "Ralf", "Rowf's kid."),
    ("Postmaster", "", "Serious Paratroopa. Never named in the text; 'Postmaster' is only the tattle's ID."),
    ("Pop Diva", "Cantarina", "Singer at Club 64."),
    ("Master Poet", "el Poeta", "Songwriter, in love with Pop Diva."),
    ("Fishmael", "Pezmael", "Fisherman."),
    ("Koopa Koot", "Koopa Koot", "Cranky, demanding, stingy old Koopa."),
    ("Kent C. Koopa", "Kent Koopa", "Huge, greedy toll-taker."),
    ("Whacka", "Guaka", "Gives Bumps when hit."),
    ("Sheek", "Jeque", "Dusty information trader."),
    ("Moustafa", "Mustafá", "Sheek's true identity."),
    ("Oaklie", "Okli", "Guards the entry to Forever Forest."),
    ("Bootler", "Ambrosio", "Lady Bow's butler."),
    ("Yakkey", "Yaki", "Talking magical key."),
    ("Gourmet Guy", "Tragón Guy", "Huge glutton."),
    ("Anti Guy", "AntiGuy", "Guard; deceptively weak-looking."),
    ("Village Leader", "líder del pueblo", "Dignified Yoshi elder."),
    ("Raphael the Raven", "Rafi Raven", "Guardian of the jungle."),
    ("Tolielup", "Tulipán", "Lying tulip who speaks in riddles."),
    ("Petunia", "Petunia", "Talkative, obsessed with Seeds."),
    ("Posie", "Azalea", ""),
    ("Lily", "Lili", "Easily distracted guardian of the spring."),
    ("Rosie", "Rosi", "Vain rose."),
    ("Lakilulu", "Lakilulu", "Lakilester's girlfriend; never backs down."),
    ("Mayor Penguin", "Alcalde Pingüino", "Mayor of Shiver City."),
    ("Herringway", "Herringway", "Penguin with a secret room."),
    ("Fuzzipede", "Fuzzypodo", ""),
    ("Albino Dino", "Albino Dino", "Palace guard."),
]

# Partner voice notes; the names themselves come from the game.
PARTNER_VOICE = {
    "Goombario": "Eager, curious kid; gives the tattles. Respectful of Mario.",
    "Kooper": "Earnest; dreams of being an adventurer like Kolorado.",
    "Bombette": "Energetic, bold and upbeat.",
    "Parakarry": "Overworked mail carrier; flustered and polite.",
    "Bow": "Haughty aristocratic Boo; snooty and imperious.",
    "Watt": "Cheerful, childlike Li'l Sparky.",
    "Sushie": "Bossy, motherly Cheep Cheep; nanny of the Yoshi kids.",
    "Lakilester": "Rebellious and gruff; tries to sound cool.",
}

# File select strings live in C (src/filemenu/filemenu_msg.c). The Spanish is
# decoded from the same file's PAL tables.
FILE_SELECT = [
    ("Select file to start:", "Elige fichero:"),
    ("Select file to delete:", "Elige el fichero a borrar:"),
    ("Copy which file?", "¿Qué fichero copias?"),
    ("Copy to which file?", "¿Dónde lo copias?"),
    ("NEW", "Nuevo"),
    ("Level", "Nivel"),
    ("Play Time", "Tiempo"),
    ("Delete File", "Borrar"),
    ("Cancel", "Salir"),
    ("Copy File", "Copiar"),
    ("First Play", "Primera Vez"),
    ("Yes", "Sí"),
    ("No", "No"),
    ("File name is:", "Nombre del fichero:"),
    ("OK?", "¿Vale?"),
    ("File", "Fichero"),
    ("will be deleted.", "será borrado."),
    ("OK to copy to this file?", "¿Quieres copiarlo aquí?"),
    ("Start game with", "¿Quieres este fichero?"),
    ("has been deleted.", "ha sido borrado."),
    ("Copy from", "Copia del"),
    ("to", "al"),
    ("has been created.", "ha sido creado."),
    ("Enter a file name!", "¡Introduce nombre!"),
    ("SPACE / BACK / END", ""),
]

# Battle and HUD terms that are messages.
UI_MESSAGES = [
    "Menus_Jump",
    "Menus_Hammer",
    "Menus_Items",
    "Menus_StarSpirits",
    "Menus_Strategies",
    "Menus_Abilities",
    "Menus_Defense",
    "Menus_ChangeMember",
    "Menus_RunAway",
    "Menus_DoNothing",
    "Menus_ActLater",
    "Menus_Focus",
    "Menus_EndTraining",
]


def load(name: str, lang: str) -> Dict[str, str]:
    path = REFERENCE / lang / name
    if not path.is_file():
        return {}
    return {m.key: " ".join(m.text().split()) for m in read_msg_file(path).messages}


def row(en: str, es: Optional[str], notes: str = "") -> str:
    def cell(s):
        return (s or "").replace("|", "\\|")

    return f"| {cell(en)} | {cell(es)} |  | {cell(notes)} |"


def table(title: str, intro: str, rows: List[str]) -> str:
    head = f"## {title}\n\n{intro}\n\n| English | Spanish (PAL) | Catalan | Notes |\n|---|---|---|---|\n"
    return head + "\n".join(rows) + "\n"


def by_prefix(en: Dict[str, str], es: Dict[str, str], prefix: str, notes=None) -> List[str]:
    out = []
    for key, text in en.items():
        if key.startswith(prefix):
            out.append(row(text, es.get(key), (notes or {}).get(text, "")))
    return out


def items(en: Dict[str, str], es: Dict[str, str]) -> Dict[str, List[str]]:
    registry = (ROOT / "src" / "registry" / "items.yaml").read_text(encoding="utf-8")
    groups: Dict[str, List[str]] = {"Badges": [], "Key items": [], "Items": []}
    seen = set()
    for block in re.split(r"\n- ", registry):
        name = re.search(r"nameMsg:\s*MSG_(\w+)", block)
        if not name or name.group(1) not in en:
            continue
        key = name.group(1)
        text = en[key]
        if text in seen:
            continue
        seen.add(text)
        if "ITEM_TYPE_FLAG_BADGE" in block:
            group = "Badges"
        elif "ITEM_TYPE_FLAG_KEY" in block or "ITEM_TYPE_FLAG_GEAR" in block:
            group = "Key items"
        else:
            group = "Items"
        groups[group].append(row(text, es.get(key)))
    return groups


def pause_labels(es: Dict[str, str]) -> List[str]:
    """PAL moved the pause menu's C strings into messages; the #defines name them."""
    source = (ROOT / "src" / "pause" / "pause_gfx.c").read_text(encoding="utf-8")
    out, seen = [], set()
    for key, english in re.findall(r"#define gPauseMsg_\w+ MSG_(PAL_Menu_\w+) /\* (.*?) \*/", source):
        if english in seen or english in ("[END]", "/", "."):
            continue
        seen.add(english)
        out.append(row(english, es.get(key), "Pause menu, in C"))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    if not (REFERENCE / "en").is_dir() or not (REFERENCE / "es").is_dir():
        sys.exit("error: reference/en and reference/es are missing; see TRANSLATION.md to extract them")
    if args.output.exists() and not args.stdout:
        sys.exit(f"error: {args.output} exists; it holds decisions, so it's never overwritten (try --stdout)")

    menus_en, menus_es = load("1D_Menus.msg", "en"), load("1D_Menus.msg", "es")
    tips_es = load("1F_MenuTips.msg", "es")
    names_en, names_es = load("26_ItemNames.msg", "en"), load("26_ItemNames.msg", "es")
    enemies_en, enemies_es = load("29_EnemyNames.msg", "en"), load("29_EnemyNames.msg", "es")
    moves_en = {**load("2A_PlayerMoves.msg", "en"), **load("2B_PartnerMoves.msg", "en")}
    moves_es = {**load("2A_PlayerMoves.msg", "es"), **load("2B_PartnerMoves.msg", "es")}

    sections = []
    sections.append(
        table(
            "Characters",
            "Named characters. Record each one's voice in Notes once it's settled.",
            [row(en, es, notes) for en, es, notes in CHARACTERS],
        )
    )
    sections.append(
        table(
            "Partners",
            "Menu names of the party (`Menus_Party_*`).",
            by_prefix(menus_en, menus_es, "Menus_Party_", PARTNER_VOICE),
        )
    )
    sections.append(table("Star Spirits", "`Menus_SpiritName_*`.", by_prefix(menus_en, menus_es, "Menus_SpiritName_")))
    sections.append(
        table(
            "Star powers",
            "`Menus_StarPower_*`.",
            [r for r in by_prefix(menus_en, menus_es, "Menus_StarPower_") if "Desc" not in r],
        )
    )
    groups = items(names_en, names_es)
    sections.append(table("Items", "Consumables and other items (`26_ItemNames`).", groups["Items"]))
    sections.append(table("Key items", "Key items and gear (`26_ItemNames`).", groups["Key items"]))
    sections.append(table("Badges", "Badges (`26_ItemNames`). Many share a name with a move.", groups["Badges"]))
    sections.append(
        table(
            "Moves",
            "Mario's and the partners' moves (`2A_PlayerMoves`, `2B_PartnerMoves`).",
            list(dict.fromkeys(row(v, moves_es.get(k)) for k, v in moves_en.items())),
        )
    )
    sections.append(
        table(
            "Locations",
            "Area names from the map (`Map_*_Name`).",
            [row(v, menus_es.get(k)) for k, v in menus_en.items() if k.startswith("Map_") and k.endswith("_Name")],
        )
    )
    sections.append(table("Enemies", "`29_EnemyNames`, bosses included.", [row(v, enemies_es.get(k)) for k, v in enemies_en.items()]))
    sections.append(
        table(
            "UI terms",
            "Battle menu terms are messages. Pause and file select labels are C strings "
            "(src/pause/pause_gfx.c, src/filemenu/filemenu_msg.c), so they have tight fixed widths.",
            [row(menus_en[k], menus_es.get(k), "Battle menu") for k in UI_MESSAGES if k in menus_en]
            + pause_labels(tips_es)
            + [row(en, es, "File select, in C") for en, es in FILE_SELECT],
        )
    )

    text = (
        "# Glossary\n\n"
        "The translation's names and terms. English is the source and PAL Spanish is a reference; "
        "both are filled in from the game's text. Catalan is decided by hand, then used everywhere.\n\n"
        "When a name is decided, check how much wider it is than the English: names are inserted into "
        "lines with [Var], and many menus size their boxes to the text.\n\n"
        + "\n".join(sections)
    )
    if args.stdout:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
