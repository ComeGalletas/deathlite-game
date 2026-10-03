# Web release: no audio

**ID:** BLD-004 · **Systems:** BLD (+ AUD) · **Type:** feature ·
**Branch:** `ComeGalletas/web-no-audio-5be9212c` (session worktree
`.claude/worktrees/web-hands-on-test`, from `origin/main` at `8c42196`) ·
**Started:** 2026-09-30

## Requirement (owner, 2026-09-30)

- **Objective:** ship the web (pygbag) release with no audio at all, and
  make the web build work again without special flags.
- **Details:**
  - Found while preparing a hands-on web build (BLD-003.6): pygbag refuses
    the MP3 music ("Use OGG format instead"), so `dist/web/build.sh` and
    `serve.sh` have failed since the music landed (2026-09-16). The
    hands-on builds passed `--disable-sound-format-error` by hand.
    *(Critic round 5: pygbag refuses WAV and AIFF too, not only MP3; the
    error names the first file it meets, which was the music. The WAV cues
    would have failed the build as well. See D2.)*
  - The owner decided no audio will be considered for the web release:
    no music and no sound effects in the browser.
- **Constraint:**
  - The desktop build keeps its music (the delivered MP3s, owner
    2026-09-16) and its sound effects, unchanged.
  - The audio files are not shipped in the web bundle rather than shipped
    unplayed; no format flag hides the problem.
  - `main.py --web` (the browser profile on the desktop, for testing)
    behaves as the browser does: silent.

## Confirmed reading

- **One switch reaches both players.** `AudioManager` opens the mixer
  backend (`systems/mixer_backend.py` `make_mixer_backend`) and
  `MusicPlayer` takes that backend and is enabled only when it is ready
  (`systems/music.py:57`). The `SilentMixer` backend is never ready, and
  both players already short-circuit every call on it (the headless test
  path). Nothing else in the game touches `pygame.mixer`.
- **What ships today.** `dist/web/pygbag.ini` excludes
  `/assets/sound_effects/unused` but not `/assets/music` (two MP3s) or
  `/assets/sound_effects` (three WAV cues, 0.48 MB). The synthesised cues
  (`config.SOUND_EFFECTS` with no file) are built in memory and need no
  asset.

## Decisions

- **BLD-004.D1 — a config switch, `AUDIO_ENABLED`** (builder). True on the
  desktop; `apply_web_profile()` sets it False. `Game` then brings pygame
  up with no mixer device (`mixer_backend.init_pygame(audio=False)`, after
  critic round 1), and `AudioManager` asks for the silent backend instead
  of probing a device, so neither the cue library nor the music stream is
  built, and the expected silence logs as information, not a warning.
- **BLD-004.D2 — the audio folders leave the bundle**
  (`/assets/music`, `/assets/sound_effects` in `pygbag.ini`'s
  `ignoreDirs`). pygbag 0.9.3 refuses MP3, WAV and AIFF files with no OGG
  sibling (`pygbag/pack.py`), so excluding **both** folders is what clears
  its format check (corrected in critic round 5; the first version of this
  line said "no MP3"). `build.sh` and `serve.sh` work again unchanged.
- **BLD-004.D3 — the Options screen's audio rows stay** (builder, flagged
  to the owner). In the browser the master, effects and music volume rows,
  the mute row and the M mute key change values that drive nothing. Hiding them is a UI
  change across the Options layout, its fit tests and both languages; it
  is left for the owner to ask for. **Decided by the owner, 2026-10-02:
  keep them for now; as long as they break nothing they remain** (recorded
  under BLD-006.1).
- **BLD-004.D4 — the five nested `unused/` folders leave the bundle too**
  (builder, after critic round 1). Rewriting the `pygbag.ini` comment
  removed its only nested example and left it describing a rule no line
  followed; BLD-003.6 had already found these folders shipping. The
  desktop spec skips `unused/` at any depth, so the game is known to run
  without them; the web now matches, and a test keeps it matching.

## Plan

1. Journal and index (this file).
2. `config.AUDIO_ENABLED`, set False by the web profile; `AudioManager`
   takes the silent backend when it is off; `pygbag.ini` excludes the two
   audio folders. Tests: the web profile is silent and the desktop is not;
   with audio off no cue, file or track is loaded and every call is a
   no-op; every audio file the game names lives under an excluded folder.
3. Build the web bundle with `dist/web/build.sh` as it stands (no flag)
   and check the bundle holds no audio; docs; cold critic pass; close.

## Critic rubric (frozen before building)

1. Under the web profile (browser runtime or `main.py --web`) no mixer
   device is opened, no sound or music file is loaded, and every audio call
   is a no-op; on the desktop audio is exactly as before. Tests show both.
2. The web bundle carries no audio file: every path in
   `config.SOUND_EFFECTS` and `config.MUSIC_TRACKS` is under a
   `pygbag.ini` exclusion (tested), and an actual build lists none.
3. `dist/web/build.sh` builds as it stands, with no sound-format flag
   (run, not reasoned about).
4. Every doc that describes the web build's audio or the MP3 problem
   agrees with the code.

## Tasks

- [x] BLD-004.1 — journal, index entry
- [x] BLD-004.2 — `AUDIO_ENABLED`, silent web profile, audio out of the bundle, tests
- [x] BLD-004.3 — real build without the flag, docs, critic, close

## Progress

### BLD-004.2 — the switch, the bundle, the tests (2026-09-30)

- `game/config.py`: `AUDIO_ENABLED: bool = True`, beside the mixer
  defaults; `apply_web_profile()` sets it False (docstring bullet added).
- *(Superseded by critic round 1, below: `Game` now brings pygame up with
  no device through `mixer_backend.init_pygame`, and the close in
  `AudioManager` is only a guarded backstop.)* `systems/audio.py`
  `AudioManager.__init__`: with the switch off it closes
  the device `pygame.init()` has already opened (measured: after
  `pygame.init()` on SDL's dummy driver, `pygame.mixer.get_init()` is
  `(44100, -16, 2)`, so without the close `main.py --web` would hold a
  device), takes `make_mixer_backend("silent")`, logs at info and returns
  before the cue library, the file loads and the event subscriptions.
  `MusicPlayer` built on that backend is disabled, so every music call
  only keeps its bookkeeping (`current`), as it does headless.
- `dist/web/pygbag.ini`: `/assets/music` and `/assets/sound_effects`
  replace `/assets/sound_effects/unused` in `ignoreDirs` (the whole folder
  covers its `unused/` originals).
- `tests/systems/test_web_audio.py`, 19 tests:
  - the switch: on for the desktop, off under the profile, restored after;
  - the silent manager: no device left open, the silent backend, no cue
    built or file loaded (`_build_library` / `_load_files` /
    `pygame.mixer.Sound` / `music.load` / `music.play` patched to fail), no
    event subscription, info not warning, every call a no-op; the music
    player on it disabled; the desktop control unchanged;
  - `SilentGameTests` (integration, in `tests/conftest.py`): a real `Game`
    booted under the profile and stepped on the menu, which asks for
    "menu", with every cue event published: no device, nothing opened;
  - the bundle: both folders excluded, every `SOUND_EFFECTS` and
    `MUSIC_TRACKS` path under an exclusion, and no audio file anywhere in
    `assets/` outside one (with a control that the walk finds audio).
- Mutation check, each must fail the module: the manager ignoring the
  switch (6 failed, 4 errors), the device left open (5), the music folder
  shipped (3), the old `sound_effects/unused`-only line (3), the profile
  leaving audio on (7 failed, 4 errors). Restored: 19 passed.
- Touched suites: `tests/systems`, `tests/display`, `test_web_crowd`,
  `test_frame_pacing`, `test_smoke`, `test_options`, the tier audit:
  410 passed.

### BLD-004.3 — the real build, docs (2026-09-30)

- `dist/web/build.sh` run as it stands (only `PYTHON` pointed at the
  repo's venv, which the script reads): it built. The log's ignore list
  shows both folders; no sound-format error.
- First build: the apk (`out/web-hands-on-test.apk`, named after the
  worktree folder) was 10,368,246 bytes, 831 entries, **0 audio files**.
  The audio that used to ship was 9,384,279 bytes (music 8,902,687, cues
  481,592).

**Critic round 1 (cold, rubric only): FAIL.** Rubric 2 and 3 passed;
1 and 4 failed. Findings and what was done:

1. *A device was opened under the web profile and then closed*:
   `pygame.init()` opens the default device, and the first fix only
   released it in `AudioManager`. Fixed at the source:
   `systems/mixer_backend.py` `init_pygame(audio)` runs `pygame.init()`
   with `SDL_AUDIODRIVER` set, for that one call, to a driver name no SDL
   build has, so the mixer's share of the init fails cleanly and nothing
   opens; every other module comes up as before (measured on pygame 2.5.2
   and 2.6.1: `(4, 1)` instead of `(5, 0)`; clock, timers, events and a
   later desktop `mixer.init` unchanged). The caller's variable is put
   back in a `finally`. `Game.__init__` calls it with
   `config.AUDIO_ENABLED`. The rejected alternative, initialising display,
   font and joystick by hand, leaves `pygame.get_init()` False and has to
   track pygame's own module list per version, including the pygame-ce
   build the browser runs, which cannot be checked here.
2. *Docs said "no device is opened"*: true now, by finding 1.
3. *The release in `AudioManager` was unguarded*: it is kept as a
   backstop for a device opened before the game, and now goes through
   `MixerBackend.shutdown()`, which catches `pygame.error`.
4. to 6. *Stale journal lines*: annotated in `music_tracks_journal.md`
   ("Audio format, settled"), `sound_effects_journal.md` (the
   `sound_effects/unused` entry), `web_frame_time_journal.md` (the nested
   `unused/` bullet) and `pygbag.md` (the browser mixer's resampling).
7. *Mixed units*: sizes now from a script, in decimal MB: 9.4 MB of audio.
8. *The `pygbag.ini` comment described a rule no line followed*: D4.
9. *`mixer_backend.py` still described `BrowserMixer` as the web path*:
   its docstring now has an "Audio off" entry.
10. *Dead Options controls in the browser*: D3, the owner's call.

Tests after round 1: `tests/systems/test_web_audio.py` has 29.
`InitWithoutMixerTests` covers the helper: the plain-init control, no
device with the rest up, the variable restored (set, unset, and when the
init raises), and a later desktop bring-up. `SilentGameTests` spies on
`AudioManager.__init__` and asserts the mixer is already `None` when it
runs, inside a `Game` booted from a closed mixer: never opened, not opened
and released. The backstop's guard is tested. A new bundle test fails on
any `unused/` folder under `assets/` that is not excluded. Mutation check,
nine breaks, each fails the module: the manager ignoring the switch, the
backstop removed, the music folder shipped, the old
`sound_effects/unused`-only line, the profile leaving audio on, `Game` back
on plain `pygame.init()`, the variable not restored, the helper ignoring
`audio=False`, a nested `unused/` folder shipped. Touched suites:
`tests/systems tests/flows tests/display tests/screens tests/devtools`,
1,458 passed, 0 failed.

- Second build, same command: no sound-format error; the apk was
  9,566,776 bytes (an intermediate tree, not reproducible from a commit), 791 entries, 0 audio files, 0 files under `unused/`.
  (Its `game/config.py` was not the final one: a comment there was edited
  after the build, which critic round 2 caught.)

**Critic round 2 (cold, rubric only): FAIL on item 4 only.** Items 1 to 3
passed, item 1 with the critic's own fresh-process probe on pygame 2.5.2
and 2.6.1, with `SDL_AUDIODRIVER` unset so the real Windows driver was in
play: at nine points from import to 30 frames in, `mixer.get_init()`,
`SDL_WasInit(SDL_INIT_AUDIO)` and the current driver all read none, with
no `mixer.init`, `pre_init`, `Sound` or `music.load` call. The desktop
control opened wasapi and loaded music. Ten mutations of its own all
failed the module. Findings and what was done:

1. *The README's sizes read as "10.2 MB dropped, apk 0.8 MB smaller"*:
   rewritten with each step measured. The bundle with the audio was
   19.6 MB (BLD-003.6, `web_frame_time_journal.md`), 10.4 MB without it,
   and 9.5 MB now.
2. *`systems/audio.py` docstring said the synth runs in the browser*:
   it now says the web release has audio off and `BrowserMixer` is unused.
3. *The "byte-identical" claim was false for `game/config.py`*: rebuilt
   after the last edit; see the third build below.
4. *0.46 MB is MiB*: 0.48 MB.
5. *The `web_plan.md` §6 row said "build with the MP3 music" and named
   unchanged files*: reworded, with the files that changed.
6. *The BLD-004.2 entry did not say it was superseded*: marked.
7. *If the variable trick ever stops holding (SDL3 renames it
   `SDL_AUDIO_DRIVER`), the backstop would close a device silently*: a
   device found open with audio off now logs a **warning** naming it, so a
   browser console shows it. Tested both ways (no device: info only; a
   device open: the warning).
8. *Outside the rubric, taken because each was minutes*: `CLAUDE.md` and
   `FUNCTIONAL_README.md` added to `ignoreFiles`; `SilentGameTests` uses a
   `TemporaryDirectory` instead of leaving a `mkdtemp` behind; the
   `web_plan.md` header notes its 45 MB figure is the 2026-09-03 reading.
   Left as is: D3 (the Options audio rows), the owner's call.

- Third build, same command: no sound-format error; the
  apk was 9,538,822 bytes (an intermediate tree: `main.py` changed after it), 789 entries, **0 audio files, 0 files under
  `unused/`, neither doc file**, and all 305 of its `.py` files are
  byte-identical to the tree.

**Critic round 3 (cold, rubric only): items 1 to 3 PASS, item 4 one
number.** Beyond the rubric it **booted the bundle in Chrome** (pygame-ce
2.5.7, SDL 2.28.4, through pygbag's dev server on a scratch copy): the menu
came up, the console showed only "audio off by configuration" (the
"device was open" warning never fired), `Module.SDL2` held no
`audioContext`, and a spy on `AudioContext` counted 0 constructions. That
settles the "not checked in a browser" gap below. Its desktop probe on
the pre-BLD-004 tree (`8c42196`) gave the same call sequence and cues as
this tree. Twelve mutations of its own all failed the module; a control
build with `/assets/music` put back failed on the MP3 as before.

1. *"9.4 MB of audio on disk"*: the two folders hold 15.3 MB on disk
   (with the 5.9 MB of `sound_effects/unused/` originals, already
   excluded); 9.4 MB is what used to ship. Reworded.
- Taken from its notes: `main.py`'s `--web` comment now says "no audio";
  the music journal's "two consequences" paragraph is marked superseded
  for the web. Left as notes: `pygame.get_error()` keeps the "Audio target
  ... not available" text after the init (harmless); `SilentGameTests`
  leaves its display up, as the other booting tests do; `assets/CREDITS.md`
  ships to the web and still credits the music (a credit file, accurate
  for the desktop).

- Fourth build: 9,538,827 bytes (reproduced to the byte by critic
  round 4, which rebuilt it from a copy of the tree).

**Critic round 4 (cold, rubric only): items 1 to 3 PASS, item 4 one
line.** Its fresh-process probe booted a run (seed 1234, 120 frames) under
the profile with every `pygame.mixer` and `mixer.music` callable and
`open` wrapped: one `mixer.get_init` call, nothing else, no audio file
opened. The desktop control matched the `8c42196` tree call for call. It
rebuilt `bd7a80d` with the flag (19,609,140 bytes) and `1149b75`
(10,368,246 bytes, 831 entries), confirming both figures, and its own nine
mutations all failed the module. Suites: 1,459 passed.

1. *`pygbag.md`'s TODO note still called the bundle trim pending, against
   the item marked moot below it*: annotated.
2. *The second and third build sizes cannot be reproduced*: marked as
   intermediate trees.
- Taken from its notes: the README states its MB are decimal; the
  `sound_effects_journal.md` annotation gives its MiB figures in decimal;
  the `mixer_backend.py` and `audio.py` docstrings no longer claim the
  dummy driver (or a CI) means no device; the `web_plan.md` row for
  `assets/unordered-effects/` is marked moot (the folder is gone). Left
  as a note for the owner: this machine's desktop device opens at
  `(44100, -16, 8)` although `DesktopMixer` asks for 2 channels, the same
  before and after BLD-004.

- Fifth build: 9,538,872 bytes (reviewed by critic round 5, which found
  every entry identical to the tree then).

**Critic round 5 (cold, rubric only): items 1 to 3 PASS, item 4 one
wrong claim.**

1. *The docs said pygbag refuses MP3; it refuses MP3, WAV and AIFF with
   no OGG sibling* (`pygbag/pack.py`, 0.9.3, read and confirmed; the
   critic also ran pygbag's `pack.archive()` on a lone WAV cue and got
   the same error). The WAV cues would have failed the build too; the
   error names only the first file, the music. Corrected in
   `dist/web/README.md`, the `pygbag.ini` comment, D2 and the requirement
   above, `web_plan.md` (§2 and the §6 row) and `pending_plans.md` §7.
   `WebBundleTests` now counts `.aiff` / `.aif` as audio too.
2. *`assets/CREDITS.md` said the web build ships the tracks*: it now says
   the desktop build does and the web build ships no audio.

- Sixth build: 9,538,905 bytes (reviewed by critic round 6).

**Critic round 6 (cold, rubric only): items 1 to 3 PASS, item 4 one
sentence.** It ran pygbag 0.9.3's own `gather` and `filter` against the
tree and `pygbag.ini`: they select exactly the 789 bundled paths, none of
which trips the format check; with the `8c42196` ini they reach the two
MP3s and the three WAVs, music first.

1. *`mixer_backend.py`'s docstring said `AudioManager` never calls
   `pygame.mixer` directly*: with audio off it reads `get_init()`. Fixed.
- Taken from its notes: the README now says the refusal is the Windows
  and macOS behaviour, and that on Linux pygbag first transcodes with
  ffmpeg or stops on an MP3 with another message (read in
  `pygbag/optimizing.py`); `assets/CREDITS.md` no longer calls the music
  the only recorded audio; the music journal's "8.5 MB" is marked as MiB;
  the README paragraph is split in three. Left as a note for later web
  work: the GitHub Actions sketch in `pygbag.md` (W9, parked) describes
  pygbag's ignore rules wrongly and uses old paths.

- **Final build**, same command, after the last edit to a bundled file:
  no sound-format error; the apk is **9,538,932 bytes**, 789 entries,
  0 audio files, 0 under `unused/`, and all 789 files are identical to the
  tree (line endings normalised).
- Docs: `dist/web/README.md` (the MP3 paragraph and the "scripts fail"
  note replaced by the no-audio paragraph; the exclusions row),
  `FUNCTIONAL_README.md` (web section), `plans/web_plan.md` (§2 and §6
  row), `plans/pending_plans.md` (§7: two blockers left),
  `journals/pygbag.md` (status, goal item 2, the bundle-trim todo moot),
  `journals/web_frame_time_journal.md` (the BLD-003.6 MP3 bullet closed),
  `journals/music_tracks_journal.md` (the proposed `MUSIC_ENABLED` switch
  landed wider, as `AUDIO_ENABLED`; "Audio format, settled" marked
  superseded for the web), `journals/sound_effects_journal.md`, the
  `systems/mixer_backend.py` and `systems/audio.py` docstrings, `main.py`'s
  `--web` comment.
- ~~Not checked in a browser~~: settled by critic round 3, which booted
  the bundle in Chrome and saw no audio context created.

**Critic round 7 (cold, rubric only): PASS on all four items.** It read
every prose hunk of the diff against the code and pygbag 0.9.3's
`pack.py`, `optimizing.py`, `filtering.py` and `gathering.py`, measured
every size by script, and ran pygbag's own `gather` and `filter`: they
select exactly the apk's 789 paths, none refused by the format check. The
apk (9,538,932 bytes) equals the tree. Its one rubric-relevant note, that
the README left out the Options mute row among the dead controls, is
fixed (the README does not ship in the bundle, so no rebuild).

Left for later, outside BLD-004: the README's Files table names the apk
`deathlite-game.apk`, which is right in the shared checkout and not in a
worktree (pygbag names it after the folder); on Linux pygbag's optimizer
copies `.py` files that name `.mp3` / `.wav` paths and runs `black` over
them, not run here; the `pygbag.md` W9 Actions sketch (parked) misstates
pygbag's ignore rules.

## Close (2026-09-30)

BLD-004 is done. The web profile turns audio off with
`config.AUDIO_ENABLED`; pygame comes up with no mixer device
(`mixer_backend.init_pygame`), no cue or track loads, and the desktop is
call-for-call what it was at `8c42196`. The audio folders and the nested
`unused/` folders are out of the bundle, `dist/web/build.sh` and
`serve.sh` build with no flag, and the apk went from 19.6 MB (with audio)
to 9.5 MB. Seven cold critic rounds; the last passed. Open for the owner:
D3, the Options audio rows and M key that do nothing in the browser.
*(D3 decided 2026-10-02: they stay while they break nothing.)*
