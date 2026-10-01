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
  `/assets/sound_effects` (three WAV cues, 0.46 MB). The synthesised cues
  (`config.SOUND_EFFECTS` with no file) are built in memory and need no
  asset.

## Decisions

- **BLD-004.D1 — a config switch, `AUDIO_ENABLED`** (builder). True on the
  desktop; `apply_web_profile()` sets it False. `AudioManager` then asks
  for the silent backend instead of probing a device, so neither the cue
  library nor the music stream is built, and the expected silence logs as
  information, not a warning.
- **BLD-004.D2 — the audio folders leave the bundle**
  (`/assets/music`, `/assets/sound_effects` in `pygbag.ini`'s
  `ignoreDirs`). With no MP3 in the bundle pygbag's format check passes,
  so `build.sh` and `serve.sh` work again unchanged.
- **BLD-004.D3 — the Options screen's audio rows stay** (builder, flagged
  to the owner). In the browser the master, effects and music volume rows
  and the M mute key change values that drive nothing. Hiding them is a UI
  change across the Options layout, its fit tests and both languages; it
  is left for the owner to ask for.

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
- [ ] BLD-004.3 — real build without the flag, docs, critic, close
