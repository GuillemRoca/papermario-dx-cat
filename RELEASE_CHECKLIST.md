# Release checklist

For each release of the Catalan patch. See TRANSLATION.md for how the build works.

## Translation

- [ ] `translation/` is on the commit you mean to release, and that commit is pushed.
- [ ] `python3 tools/translation/lint.py --complete --strict` passes: every message translated, no
      warnings.
- [ ] Each file you meant to finish is at 100% in the linter's table.
- [ ] The glossary has no empty Catalan cells for names the text uses.
- [ ] The C string tables match the glossary: `src/filemenu/filemenu_msg.c`,
      `src/pause/pause_gfx.c`, and `MessagePlural` in `src/engine2/msg.c`.
- [ ] `translation/notes/translator-notes.md` has no open questions.

## `src/dx/config.h`

Set these for the release build. They're for development and testing, and change gameplay or show
debug features.

- [ ] `DX_DEBUG_MENU 0`
- [ ] `DX_DEBUG_EVT_TESTS 0`
- [ ] `DX_DEBUG_OVERLAY_LOADS 0`
- [ ] `USE_PROFILER 0`
- [ ] `DX_SKIP_LOGOS 0`
- [ ] `DX_SKIP_STORY 0`
- [ ] `DX_SKIP_DEMO 0`
- [ ] `NEW_GAME_MAP_ID "kmr_20"`, `NEW_GAME_ENTRY_ID kmr_20_ENTRY_0`,
      `NEW_GAME_STORY_PROGRESS STORY_INTRO`. These are the defaults; change them back if you used
      them to test.
- [ ] `DX_PAUSE_LAG_FIX`: decide and record the choice here. `1` skips the blur filter behind the
      pause menu (`src/background_gfx.c`), which lags on some emulators; `0` keeps the original
      blur, as on real hardware. DX defaults to `1`.
- [ ] `DX_MOD_NAME`: at most 27 characters, ASCII only. The file select draws it with an
      ASCII-only converter, so it can't contain accents. Choose it once and never change it: saves
      are signed with it, and a save made under another name shows in red on the file select,
      without its summary, and loads as a vanilla save.
      Suggestion: `"Paper Mario en catala"` (21 characters).
- [ ] Version: bump `DX_MOD_VER_MAJOR`, `DX_MOD_VER_MINOR` and `DX_MOD_VER_PATCH`. Keep `MAJOR`
      unless the save format changes, which a translation shouldn't do. Use `MINOR` for new
      translated content and `PATCH` for fixes.

## Build and test

- [ ] `tools/translation/ci.sh` passes locally with `RELEASE=1`.
- [ ] Apply `dist/papermario-catala-<version>.bps` to a clean US ROM (SHA1 in
      `ver/us/checksum.sha1`) with Flips or Rom Patcher JS. Check that it boots in ares, and on
      hardware if possible.
- [ ] Start a new game with the logos, story and demo enabled. Check the title screen, the file
      select (name entry, copy, delete), the pause menu and a save and load.
- [ ] Check any translated images in game.

## Publish

- [ ] Tag `vX.Y.Z` on this repository. CI lints in release mode and uploads the patch.
- [ ] Publish the `.bps` only, never a ROM. Give the base ROM's SHA1 and say it must be the US
      version in `.z64` format.
- [ ] Put `src/dx/config.h` back to development settings on `main` if you want the debug menu
      again.

## Release log

### v1.0.0

- `DX_MOD_NAME "Paper Mario en catala"`, version 1.0.0.
- `DX_PAUSE_LAG_FIX 1`: kept DX's default. Most players use emulators, where the blur lags; on
  hardware the pause menu just shows no blur behind it.
- Debug menu, EVT tests, overlay logging and profiler off; logos, story and demo on; new game at
  `kmr_20` with `STORY_INTRO`.
- `lint.py --complete --strict --compile` with the pmret compiler too: 8009/8009 messages, 0
  errors, 0 warnings. `ci.sh` passes with `RELEASE=1`.
- The `.bps` applied to the US ROM (SHA1 `3837f44cda784b466c9a2d99df70d77c322b97a0`) gives a ROM
  identical to the build.
- Checked in n64js (headless, `/root/emu/shoot.py`): logos, storybook, title, file select, name
  entry, new game, the castle party, the prologue in the Goomba region, the pause menu tabs.
- Not checked in game: copy and delete on the file select, saving and loading, and most
  translated images (battle, level up, chapter cards). See `translation/notes/translator-notes.md`,
  "Things to check in game or decide".
