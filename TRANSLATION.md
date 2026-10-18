# Catalan translation

This fork builds Paper Mario in Catalan, released as a `.bps` patch for the US ROM. The
translation itself (message files, glossary, translated images) lives in its own repository,
[papermario-cat](https://github.com/GuillemRoca/papermario-cat), checked out here as the
`translation/` submodule. This repository holds the build, the linter and CI.

Never commit a ROM, the split assets, or English or Spanish game text. `ver/us/baserom.z64`,
`assets/us/`, `reference/` and `dist/` are all gitignored.

## How the translation reaches the game

`translation/assets` is a layer in the asset stack (`ver/us/layout.yaml`), between `src/` and DX's
own assets. Any file under it replaces the base game's file at the same path:

- `translation/assets/msg/NN_Name.msg` overrides `assets/us/msg/NN_Name.msg`. Overrides are per
  message, by section and name, so a half-translated file builds, and its untranslated messages
  show in English.
- A translated image goes at the path of the one it replaces, such as
  `translation/assets/mapfs/title/logotype.png`.

Some text is C, not messages. These string tables are the only C this translation edits:

| Text | Where |
|---|---|
| File select, save and name entry | `src/filemenu/filemenu_msg.c`, the US (`#else`) tables |
| Pause menu labels | `src/pause/pause_gfx.c`, the `VERSION_US` tables |
| The plural "s" for shops, Chuck Quizmo and the minigame | `MessagePlural` in `src/engine2/msg.c` |

The tables are arrays of font codes. `tools/translation/encode.py "Text"` prints an initializer
and its width in pixels. Each string is drawn at a fixed position, so check the width against the
space it has; `translation/notes/translator-notes.md` records the tight ones. Only edit the US
tables (`#else` / `#elif VERSION_US`), never the PAL ones. They aren't portable to other ports the
way message files are, so keep their Catalan in the glossary's UI terms too.

The plural suffix stays "s" until 27_Shops and 08_Minigame are translated. Catalan needs "a" and
"es" on a stem (`moned[Var 2]`), and switching it earlier would turn the English still in place
into "1 coina".

The credits use their own fonts, which have only uppercase A–Z, digits and `' . , & ©`. Credit
headings and names are written in uppercase without accents.

## Setting up

```sh
git clone --recurse-submodules https://github.com/GuillemRoca/papermario-dx-cat
cd papermario-dx-cat
cp /path/to/papermario-us.z64 ver/us/baserom.z64   # SHA1 in ver/us/checksum.sha1
./tools/configure.sh                               # downloads the toolchain, splits the ROM
export PATH="$PWD/.dx/unix/bin:$PATH" PYTHONPATH="$PWD/.dx/unix/python"
ninja                                              # ver/us/build/papermario.z64
```

Then extract the reference text: US English, which is the source, and PAL Spanish, which is a
reference. This needs your EU ROM as a big-endian `.z64`:

```sh
tools/translation/extract_reference.sh /path/to/papermario-eu.z64
```

That fills `reference/en`, `reference/es` and `reference/en_pal`. DX can't split the PAL ROM, so
the script clones pmret/papermario into `reference/.pmret` at a pinned commit and splits only the
messages. PAL keeps every US message's name and adds some of its own, so match a Spanish message
to the English by its name, never its position. The script checks that every US name is there.

## Translating

```sh
cd translation && git switch main && cd ..   # the submodule starts detached
cp reference/en/18_GossipBoard.msg translation/assets/msg/   # then translate it in place
python3 tools/translation/lint.py            # or: lint.py 18_Gossip
ninja
```

Copying the English file is a convenient starting point. Translate every message before you
commit, or delete the ones you haven't done: English must not be committed to the translation
repository. Then commit and push in `translation/`, and commit the new submodule commit here.

`translation/README.md` lists the rules for message files, `translation/STYLE.md` the style, and
`translation/glossary.md` the names. Names are decided in the glossary before they're used.

## The linter

`tools/translation/lint.py` checks every translated file against vanilla:

| Check | Level |
|---|---|
| The file and every message ID exist in vanilla, in order, once each | error |
| Headers are written the way both DX and pmret/papermario parse them | error |
| Control codes, tags and variables match vanilla exactly, so the `[BR]`/`[Next]` structure is unchanged | error |
| Characters are in the font; `·` suggests `l.l` | error |
| No comments, CR line endings or BOM | error |
| A line is wider than its box can show | error |
| A line is near the box edge and wider than the English line | warning |
| Letters Catalan doesn't use (`ñ`, `¿`, `á` and so on) | warning |
| Messages not translated yet, or identical to English | info, `--info` lists them |

Widths use the game's own glyph table (`src/font_width/msg_data.c`) and mirror the game's
measuring code (`get_msg_properties` in `src/engine2/msg.c`). Box limits per `[Style]` are in
`STYLE_LIMITS` in `lint.py`. A `[Var n]` is counted as 60 px. Option widths in choice boxes come
from the box's `size=`.

| Option | What it does |
|---|---|
| `--complete` | Requires every file and message translated. Use it for releases. |
| `--strict` | Fails on warnings as well as errors. |
| `--compile --upstream-compiler PATH` | Also builds each file with DX's compiler and with pmret's. |
| `--json FILE` | Writes the findings as JSON. |

Messages meant to read the same as in English go in `translation/identical.txt`, so they count as
translated.

The linter's tests use invented text: `python3 -m unittest tools/translation/test_lint.py`.

## Seeing a line in game

Build, then run `ver/us/build/papermario.z64` in ares. The debug menu (`DX_DEBUG_MENU 1` in
`src/dx/config.h`; press D-Pad Left in game) warps to any map. See the
[debug menu manual page](https://docs.starhaven.dev/papermario-dx/testing/debug-menu/).

## CI

`.github/workflows/translation.yaml` runs `tools/translation/ci.sh` on every push. That script:

1. Fetches the base ROM and checks its SHA1.
2. Builds the game.
3. Runs the linter, including both compilers.
4. Writes the patch to `dist/papermario-catala-<version>.bps`.
5. Checks that the patch reproduces the ROM.

The patch and the lint report are uploaded as the run's artifact; the ROM never is. On a `v*` tag
it lints in release mode (`--complete --strict`). The script runs the same way locally.

It needs two repository secrets, under Settings → Secrets and variables → Actions:

- **`BASEROM_US_URL`**: a direct download URL for the US ROM, as a `.z64` or as a `.zip` holding
  one. The ROM can't be a secret itself, because secrets are limited to 48 KB. Host it somewhere
  private that you control and that gives a direct link, such as a private bucket with a
  long-lived signed URL. Anyone who can read the secret can download the ROM, so don't use a
  public link. The SHA1 check rejects anything that isn't the right ROM.
- **`TRANSLATION_REPO_TOKEN`**: a fine-grained personal access token with read-only Contents
  access to papermario-cat, so CI can check out the private submodule. The default
  `GITHUB_TOKEN` only reaches this repository.

With a self-hosted runner, you can instead keep the ROM on the runner and copy it to
`ver/us/baserom.z64` before `ci.sh`.

## Porting to StarHaven

The message files are portable as they are: they use only syntax that pmret/papermario's compiler
accepts, and every file is complete and in vanilla order. A port built from the vanilla decomp
can replace its `assets/us/msg/*.msg` with `translation/assets/msg/*.msg`. Because that kind of
replacement is by file, not by message, the port needs complete files. The C tables and images
need porting separately.
