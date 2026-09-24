# Music journal — shipping the two delivered tracks

**Legacy ID:** AUD-001 (continued) · **Systems:** AUD · split out of `music_journal.md` by DOC-005 on 2026-09-24, as the owner decided (this entry's own open question 8). Its text is unchanged apart from the notes DOC-005 added.

## Requirement (owner, 2026-09-16)

- **Objective:** Review the two music tracks delivered into `assets\music`
  and propose a way to add them to the main menu and the gameplay stage.

This entry is the review and the proposal. Nothing has been built yet; the
plan below is waiting on the confirmations at the end.

Note on this file: a `music_journal.md` already existed (the 2026-09-15 review
above, which recommended an offline procedural composer, option C). The owner
asked for a new music journal; rather than overwrite that review it is
kept as the entry above, because it is the direct context for this one. This
request is effectively **option A** of that review — author once, stream a
file — now that real tracks exist. Option C is not cancelled by this; it can
still land later and reuse the same runtime player.

## The tracks, measured

Decoded through `pygame.mixer` and measured sample-by-sample (RMS of the
mono sum, expressed as a fraction of full scale):

| | `main-menu.mp3` | `gameplay-1.mp3` |
|---|---|---|
| Length | 147.41 s (2:27) | 130.63 s (2:11) |
| On disk | 4.50 MB | 3.99 MB |
| Format | MPEG-1 Layer III, 320 kbps, 44.1 kHz, stereo | MPEG-1 Layer III, 320 kbps, 48 kHz, stereo |
| Level, first 0.5 s | 0.086 — starts at full level | 0.006 — **fades in** over ~1.5 s |
| Level, mid-track | 0.126 | 0.116 |
| Level, last 3 s | 0.066 | 0.101 |
| Level, last 1 s | 0.007 | 0.013 |
| Level, last 0.2 s | 0.00008 — **true digital silence** | 0.009 — a low tail, not silence |

Both decode cleanly through this SDL_mixer build, so MP3 on the desktop is
not in question.

### What that means for looping

Neither track is a seamless loop; both are authored as standalone pieces
with an ending.

- **`main-menu.mp3`** starts at full level and fades to *actual silence* over
  the last two seconds. `mixer.music.play(-1)` therefore gives a ~1.5 s
  dropout followed by an abrupt return to full level, once every 2:27. That
  is a recognised and tolerable loop shape, but it is audible.
- **`gameplay-1.mp3`** fades in *and* out, so its loop seam is a graceful
  dip through low level rather than a hole — the better behaved of the two,
  once every 2:11.

A follow-up `tools/music/` pass could trim the head and tail and crossfade
the join into a genuinely seamless loop. That is a separate, optional job;
the proposal below loops the files as delivered.

### Format mismatch with the current device

This is the one finding that touches existing code. `systems/mixer_backend.py`
opens the desktop device at **22050 Hz, mono** (`DesktopMixer.prepare`),
because that is the rate `systems/audio.py` renders its eight synthesised
cues at. Streamed through that device, both tracks are downmixed to mono and
resampled down from 44.1/48 kHz — a 320 kbps stereo master played back at
roughly telephone bandwidth in one channel. The measured stereo width of the
two tracks (L−R RMS about 0.05–0.06) is modest but real, and it would be
thrown away entirely.

`MixerBackend.make_sound` already resamples from `SYNTH_RATE` and interleaves
to the device's channel count, so **opening the desktop device at 44100 Hz
stereo keeps every cue at the pitch and length it was rendered at**. It is
not entirely free — the cues used to skip the resample — but the whole
library is 2.4 seconds of audio and the cost was measured at 85 ms, once, at
startup. This is exactly the open decision the 2026-09-15 entry left for the
owner, and the tracks make the answer obvious.

### Size

320 kbps is far above what this game needs. Re-encoded to OGG Vorbis at
about 112–128 kbps the pair drops from 8.5 MB to roughly 2.3 MB, is better
supported by SDL_mixer and pygbag than MP3, and is indistinguishable at
game volume. If that is done, the delivered MP3s are archived in
`assets/music/unused/` under the project's existing convention for spent
source files, and the PyInstaller spec already skips `unused` at any depth.

## Proposal

### 1. `systems/music.py` — a streaming player

A new module beside `systems/audio.py`, roughly 120 lines. It is a thin,
defensive wrapper over `pygame.mixer.music`:

- **Streams, never loads.** `mixer.music.load()` plus `play(-1)`. The tracks
  decode to about 26 MB each at 44.1 kHz stereo; loading them as `Sound`
  objects would be 50 MB of resident RAM for no benefit.
- **A separate stream.** `mixer.music` does not consume one of the eight cue
  channels, so nothing competes with the existing SFX.
- **Idempotent `play(track_id)`.** Asking for the track that is already
  playing is a no-op. This is the important property: it is what keeps the
  menu track running unbroken across MENU to CHARACTER SELECT to OPTIONS to
  RANKINGS to SANCTUARY instead of restarting it on every screen change.
- **Crossfades** via `fadeout(ms)` then `play(fade_ms=...)`; `mixer.music`
  has a single stream, so this is a gap-fade, not a true crossfade. At the
  menu-to-run transition it lands under the loading screen, where it reads as
  intentional.
- **Never load-bearing.** A silent backend (the dummy driver in tests and
  CI) makes every method a no-op, exactly like `AudioManager`. A missing or
  unreadable file logs a warning and leaves the game silent — the same
  degrade-don't-raise rule `game/assets.py` uses for missing sprites.
- API: `play(track_id, fade_ms=0)`, `stop(fade_ms=0)`, `set_volume(v)`,
  `set_muted(b)`, `set_ducked(b)`, `current`.

Track ids resolve through `game/config.py`, matching how every other asset
path is declared there (`MENU_BACKGROUND_IMAGE` and friends):

```python
MUSIC_TRACKS = {
    "menu":     "music/main-menu.mp3",
    "gameplay": "music/gameplay-1.mp3",
}
```

Paths are relative to `assets.ASSETS_DIR`, so adding `gameplay-2.mp3` later
is a one-line data change. `systems/music.py` can grow into a
`systems/music/` sub-package if an adaptive director is ever added (option C
above); it does not need to be one for two tracks.

### 2. Wiring: a declarative `music` attribute on `State`

`game/state.py` already carries `draw_below`, `update_below`, `ui_box` and
`backdrop` as class attributes that the machine and the main loop honour, and
its stated design goal is that "adding a new state must not require editing
the main loop". Music should follow that idiom rather than scattering
`game.music.play(...)` calls through eleven `enter()` methods.

So: add one class attribute to `State`, and have `StateMachine` apply
`self.current.music` after every `push` / `pop` / `change`. Three values:

- `MUSIC_INHERIT` (the default) — leave whatever is playing alone.
- `"menu"` / `"gameplay"` — a track id from `config.MUSIC_TRACKS`.
- `None` — fade out to silence.

`MUSIC_INHERIT` as the default is what makes the overlays free: PAUSED,
LEVEL_UP, RUN STATUS and the dev menu declare nothing, so the gameplay track
keeps playing underneath them without a single line in those files.

| State | `music` | Why |
|---|---|---|
| `MenuState` | `"menu"` | |
| `CharacterSelectState` | `"menu"` | unbroken — idempotent `play` |
| `OptionsState` | `"menu"` | you need to hear it to set the slider |
| `RankingsState` | `"menu"` | |
| `MetaState` (Sanctuary) | `"menu"` | |
| `LoadingState` | inherit | menu track carries the 4–5 s build |
| `PlayingState` | `"gameplay"` | crossfade lands as the world appears |
| `PausedState` | inherit (ducked) | |
| `LevelUpState` | inherit | |
| `RunStatusState` | inherit | |
| `DevMenuState` | inherit | |
| `GameOverState` | `None` | the music stopping *is* the run ending |
| `VictoryState` | `None` | ditto; owner's call, see below |

`LoadingState` inheriting means the menu track plays through world
generation and the swap to the gameplay track happens the moment the world
appears — a musical cue for "the run has started". The alternative is to
start the gameplay track on the loading screen so the run opens mid-swing;
that is a taste call and is listed below.

The loading screen is worth one note: it does 50–350 ms of work per slice.
`mixer.music` streams on SDL's own audio thread, so it will not stutter
while the main thread is blocked inside a generation step.

### 3. Volume, mute and ducking

- A second Options row, **"Music volume"**, beside the existing "Master
  volume", stepping on the same volume-step grid.
- Persisted as `save.settings["music_volume"]`, default **0.5** — music
  should sit under the cues, not next to them. Added to the `save.py`
  defaults dict and written in `Game.persist()` alongside `muted` and
  `volume`.
- `AudioManager.volume` keeps its current meaning: the SFX master. The two
  are independent.
- **Mute** (the `M` key and the Mute row) silences both. `Game` sets
  `music.set_muted(...)` wherever it already toggles `audio.muted`.
- **PAUSED ducks** the music to about 40% via `set_ducked(True)` and restores
  on exit. Ducking is separate from the stored volume so the Options value is
  never overwritten.

### 4. Device format

Change `DesktopMixer.prepare` to `pygame.mixer.init(frequency=44100,
size=-16, channels=2)` and keep `set_num_channels(24)`. `make_sound` already
handles the resample and the up-mix, so the eight cues play at the pitch they
were rendered at; only their startup conversion cost changes, and they total
2.4 seconds of audio (measured: 119 ms to build all eight before, 204 ms
after — 85 ms once, at startup). `BrowserMixer` is untouched — it already
accepts whatever rate and channel count the browser hands back.

### 5. Packaging

- **PyInstaller** (`dist/desktop/DeathliteGame.spec`): add `"music"` to
  `ASSET_DIRS`. The allow-list is per-file through `_tree`, so nothing else
  changes; the bundle grows by 8.5 MB (or about 2.3 MB if re-encoded to OGG).
- **pygbag** (`dist/web/pygbag.ini`): this is a deny-list, so
  `assets/music/` would ship automatically. 8.5 MB is a lot to push into a
  browser bundle, and MP3 decoding under emscripten SDL_mixer is not
  guaranteed the way it is on desktop. Recommendation for now: add
  `/assets/music` to `ignoreDirs` and have `config.apply_web_profile()` set
  `MUSIC_ENABLED = False`, then revisit once the tracks are OGG. Note that
  `ignoreDirs` lists `/assets/unused` but *not* `/assets/music/unused`, so an
  archived source MP3 would ship to the web unless that is added too.

### 6. Credits

`assets/CREDITS.md` currently states, as its opening sentence, that all game
content including "the procedurally synthesised audio in `systems/audio.py`"
is original to this project, and the spec-15 rule is "no third-party assets".
Two delivered MP3s make that sentence untrue as written. It needs a Music
section with the author, source, licence and whether attribution is required
— which needs the provenance from the owner (see below).

### 7. Tests

- `tests/systems/test_music.py` — the silent backend no-ops; every `State`
  subclass's `music` value is `MUSIC_INHERIT`, `None`, or a key that exists
  in `config.MUSIC_TRACKS`; every file named in `MUSIC_TRACKS` exists on
  disk; a repeated `play` of the current track does not restart it.
- `tests/screens/test_options.py` — existing, needs updating for the new row
  and the changed row count.

## Cost

| Piece | Effort |
|---|---|
| `systems/music.py` plus config entries | about half a day |
| `State.music`, the `StateMachine` hook and the eleven declarations | about 1 hour |
| Options row, save key, mute and duck wiring | about 1 hour |
| Device format change and re-checking the eight cues | about 1 hour |
| Packaging (spec, pygbag, CREDITS) | about 1 hour |
| Tests | about 1 hour |

## Open decisions for the owner

*(DOC-005, 2026-09-24: 1–7 were **confirmed** on 2026-09-16 (below). 8 — whether this entry should be its own file — was **answered by the owner on 2026-09-24**: split, done by DOC-005)*

1. **Provenance of the two tracks** — self-composed, AI-generated, or from a
   licensed pack? This determines what goes in `CREDITS.md` and whether the
   "all content original" sentence is amended or kept. Blocking for the
   credits edit only, not for the code.
2. **Desktop device at 44100 Hz stereo?** Recommended. Without it the music
   plays mono at 22 kHz.
3. **Re-encode to OGG at about 128 kbps?** Recommended: 8.5 MB down to about
   2.3 MB, better pygbag support, no audible difference at game volume. The
   MP3s would be archived in `assets/music/unused/`.
4. **Web build: ship music or disable it for now?** Recommended: disable
   until the tracks are OGG.
5. **End screens** — fade to silence on GAME OVER and VICTORY (proposed), or
   let the menu track come back in?
6. **Loading screen** — keep the menu track through world generation
   (proposed), or start the gameplay track there so the run opens mid-swing?
7. **Seamless loops?** The menu track drops to true silence for about 1.5 s
   at every loop. Accept it for now, or schedule a `tools/music/` trim-and-
   crossfade pass?
8. **This journal** — kept as a second entry in `music_journal.md`
   (proposed, since the 2026-09-15 review is its direct context), or split
   into its own file?

## Confirmed decisions (2026-09-16)

The owner answered the open questions above. Recording them here as the
settled shape of the work; the questions they resolve are struck through by
this section, not edited out.

### Provenance and licence — settled

Both tracks come from **Pixabay**:

| Slot | Track | Author | Pixabay id |
|---|---|---|---|
| Main menu | Shakuhachi Sunrise (Full Version) | kaazoom | 553468 |
| Gameplay | Happy Adventure Quest | jorisvermeer | 572050 |

They are covered by the **Pixabay Content License**
(https://pixabay.com/service/license-summary/), verified 2026-09-16. It
allows free use, commercial use included, **without attribution required**
(credit is "appreciated" but optional), and allows modification. The
relevant prohibition is that Content may not be sold or distributed **on a
standalone basis** — that is, in substantially the form it has on the site,
with no creative effort applied. Bundling the tracks into the game as its
score is not a standalone distribution, so shipping them in the desktop and
web builds is within the licence. Selling the two MP3s as files, or shipping
a soundtrack release of them, would not be.

Consequence for `assets/CREDITS.md`: the opening sentence currently claims
all game content, audio included, is original to this project. That becomes
untrue and must be amended to carve out the music. A new **Music** section
is added in the same table format the Tiny Swords and effects-pack entries
already use, giving track, author, Pixabay id, licence and
"Attribution required? No (credit is optional but appreciated)". Crediting
them anyway is the courteous move and costs nothing, so the section does
credit them by name.

### Audio format — settled

- **Desktop device moves to 44100 Hz stereo.** `DesktopMixer.prepare` opens
  `pygame.mixer.init(frequency=44100, size=-16, channels=2)`. The eight
  synthesised cues are unaffected: `MixerBackend.make_sound` already
  resamples from `SYNTH_RATE` and interleaves to the device's channel count.
- **The tracks ship as the delivered 320 kbps MP3s.** No OGG re-encode, and
  no `assets/music/unused/` archive — there is no spent source to archive.
- **The web build ships the music too.** `dist/web/pygbag.ini` is left alone;
  `assets/music/` rides along on the deny-list as it already would.

Two consequences of that last pair are accepted going in, and are written
here so they are not rediscovered as surprises: the pygbag bundle grows by
8.5 MB, and MP3 decoding under emscripten SDL_mixer is not verified the way
it is on desktop. Because `systems/music.py` degrades to silence on any load
failure, the worst case in the browser is a silent game, not a broken one.
If the web bundle size or a browser decode failure becomes a real problem,
the OGG re-encode and the `MUSIC_ENABLED = False` web-profile switch
described above are still the answer, and neither is invalidated by
shipping MP3 first.

### Transitions — settled

- **The menu track carries the loading screen.** `LoadingState` inherits, so
  the menu music plays through world generation and the swap to the gameplay
  track lands the moment the world appears.
- **Both end screens fade to silence.** `GameOverState.music = None` and
  `VictoryState.music = None`. The music stopping is itself the signal that
  the run is over, and it leaves the boss-death and victory cues room.

The rest of the state table in the proposal above stands as written.

### Looping — settled

Both tracks loop as delivered with `play(-1)`. The menu track's ~1.5 s drop
to silence every 2:27 is accepted for now. No `tools/music/` trim pass is
scheduled; it stays available if the seam turns out to grate in play.

### Still open

*(DOC-005, 2026-09-24: **closed** — the split asked here was made by DOC-005 on 2026-09-24)*

Nothing blocking. The only question from the list above that was not put to
the owner is whether this entry should be split out of `music_journal.md`
into a file of its own; it stays here until they say otherwise.

## Built (2026-09-16)

Implemented as proposed. What landed, and the three places reality differed
from the plan:

### New

- **`systems/music.py`** — `MusicPlayer`, a streaming wrapper over
  `pygame.mixer.music`. `play()` is idempotent, a silent backend or a missing
  file leaves the game silent instead of raising, and `current` tracks intent
  even with no device so the state machine behaves the same headless.
- **`tests/systems/test_music.py`** — 20 tests: every declared track file
  exists, every state declares a usable value, the inherit/silence rules, the
  clamps, and the stack behaviours below.

### Changed

- **`game/state.py`** — `MUSIC_INHERIT` sentinel, the `State.music` class
  attribute, a `State.music_player` accessor, and `StateMachine._apply_music`
  called from `push` / `pop` / `change`.
- **`game/states/*`** — one `music` declaration each, per the table above.
  `PausedState` also ducks on enter and restores on exit.
- **`game/game.py`** — builds the player, restores its volume and mute from
  the save, ticks `music.update(dt)` once a frame, and extends the `M` key
  and `persist()` to cover it.
- **`game/config.py`** — `MUSIC_TRACKS`, `MUSIC_VOLUME_DEFAULT`,
  `MUSIC_FADE_MS`, `MUSIC_DUCK`.
- **`game/save.py`** — `music_volume` default.
- **`systems/audio.py`** — an `AudioManager.backend` property, so the music
  player can see whether a device came up without reaching into a private.
- **`systems/mixer_backend.py`** — `DESKTOP_RATE` / `DESKTOP_CHANNELS`,
  now 44100 / 2.
- **`game/states/options_state.py`** — the Music volume row and a
  `_draw_slider` helper shared with the master row.
- **`dist/desktop/DeathliteGame.spec`** — `"music"` in `ASSET_DIRS`.
- **`assets/CREDITS.md`** — the opening claim narrowed to the synthesised
  *sound effects*, plus a Music section for the two Pixabay tracks.

### Three things the plan got wrong

1. **The fade could not use `mixer.music.fadeout()`.** It blocks the calling
   thread until the fade completes, which would hitch the frame on every
   state change. `MusicPlayer` walks its own gain ramp from `update(dt)`
   instead, so nothing blocks and the switch is still a fade-out followed by
   a fade-in.
2. **"Nobody declares a track" had to mean "leave it alone", not "silence".**
   `change()` clears the stack, so the loading screen — which inherits — is
   briefly the only state on it. Falling back to silence there would have
   killed the menu track at exactly the moment the plan said to keep it.
   There is a test pinning this.
3. **Options is two different things.** Reached from the menu it is a menu
   screen and declares `"menu"`; pushed from the pause menu over a live run
   (`in_run=True`) it is an overlay, and declaring `"menu"` there would have
   interrupted the run's music. `enter` now sets `MUSIC_INHERIT` per instance
   in that case, which works because `StateMachine` reads the declaration
   after `enter` has run.

A fourth, smaller correction: the device change is not free the way this
entry first claimed. See the measurement in the device section above.

### Verified

- Full suite green.
- Driven end to end against a *real* audio device (not the dummy driver):
  the menu track starts and fades in to the configured level; hero select and
  the loading screen keep it playing without restarting it; the run switches
  to the gameplay track; pause ducks 0.500 to 0.195 (0.5 x `MUSIC_DUCK`) and
  unpausing restores it.
- All eight synthesised cues still report their exact rendered durations
  through the new 44100 Hz device.
- The Options screen renders the new row and still fits the 1600x900 box.

### Not done, still available if wanted

*(DOC-005, 2026-09-24: **closed by the owner** — the OGG re-encode, the pygbag `MUSIC_ENABLED` switch and the loop trim are web-only changes, and the web build is not yet considered finished; they belong to that work when it resumes)*

The OGG re-encode, the pygbag `MUSIC_ENABLED` switch and the seamless-loop
trim pass were all declined for now and are described above where they were
proposed.

## Progress

- [x] Tracks reviewed and measured; proposal written. No code.
- [x] Decisions confirmed by the owner and recorded.
- [x] `systems/music.py`, the `State.music` hook and the state declarations.
- [x] Options row, save key, mute and duck wiring.
- [x] Desktop device to 44100 Hz stereo; the eight cues re-checked.
- [x] PyInstaller `ASSET_DIRS`; `assets/CREDITS.md` Music section.
- [x] Tests.
