# Music journal — generating a complex track for the game

## Requirement (2026-09-15)

"Review a way to generate a complex music track for the game, don't code."

This entry is the review only. Nothing was built.

## What the game has today

- Every sound is synthesised at startup from sine/square/saw/noise primitives
  in `systems/audio.py` into 16-bit mono buffers at 22050 Hz, wrapped in
  `pygame.mixer.Sound`. Eight cues exist; there is no music of any kind.
- `systems/mixer_backend.py` opens the desktop device at 22050 Hz / mono /
  24 channels, and on pygbag keeps whatever rate and channel count the
  browser hands back (96 kHz was observed), resampling buffers at load.
- `assets/CREDITS.md` states that all audio is original to the project
  (spec 15: no third-party assets). Any music approach should keep that true
  or add a clearly licensed credit.
- **numpy is deliberately excluded from the shipped game**: the PyInstaller
  spec drops it from the bundle and the pygbag journal rules it out for the
  browser build. numpy is fine in `tools/` (the asset pipeline already uses
  it). So heavy synthesis cannot run inside the game; it has to be baked
  offline, and the runtime player must be pure pygame + `array`.
- Audio is never load-bearing: the silent backend must keep working, and
  tests run with the dummy driver.
- Signals a music director could listen to already exist on the event bus:
  `ROOM_ACTIVATED` / `ROOM_DORMANT`, `ENEMY_SPAWNED`, `ENEMY_KILLED`,
  `BOSS_SPAWNED`, `BOSS_KILLED`, `PLAYER_DAMAGED`, `RUN_ENDED`, plus the
  state machine (menu, hero select, playing, paused, level-up, run status,
  game over, victory).

## What "complex" should mean here

A track that is not a four-bar loop: several instrument layers, a real
harmonic progression, a recurring hero motif that is varied rather than
repeated, distinct sections (menu, exploring, combat, boss, village), and
enough variation that a 20-minute run does not wear it out. Ideally it also
reacts to the run: the fight gets louder as the spawn master ramps up, the
boss gets its own section, the village sanctuary goes calm.

## Options reviewed

### A. Author once, stream a file (`pygame.mixer.music`)

Compose a full track offline, export OGG, stream it with `mixer.music`.
The composition can come from a tracker/DAW (LMMS, Bosca Ceoil, OpenMPT,
Furnace), from our own generator script, or from an AI service.

- Pro: trivial runtime (one call), works on pygbag and PyInstaller, tiny
  RAM (streamed), loop points are easy.
- Con: static. Sections can only change by swapping files with a crossfade
  (`mixer.music` has one stream; a second stream needs a `Sound` on a
  channel), and the track never reacts to the fight.
- Con for the AI route: MusicGen and Stable Audio Open weights are
  non-commercial; Suno/Udio grant commercial rights only on paid plans and
  the game's own "all content original" statement would need amending.
  Fast for a demo, weak as the shipped answer.

Verdict: good fallback and good enough for a jam build; not what "complex"
asks for.

### B. Real-time procedural synthesis inside the game

Extend `systems/audio.py` into a sequencer that renders bars on the fly.

- Pro: infinite variety, seeded per run, no asset files, in the spirit of
  the existing synth.
- Con: pure-Python rendering of a bar (44 100 samples × 5 layers) costs
  tens of milliseconds, far over the 16 ms frame budget, and there is no
  numpy at runtime to vectorise it. Chunking the render across frames is
  possible but fiddly, and the browser build makes it worse. The sound
  quality of a from-scratch runtime synth is also the hardest thing to get
  right and the least testable.

Verdict: rejected for the shipped game because of the no-numpy rule.
The *composer* can live offline instead (option C).

### C. Offline procedural composer + bar-bank adaptive player (recommended)

Split the work in two:

1. **`tools/music/` — an offline composer and renderer (numpy allowed).**
   A deterministic, seeded script that composes the whole score and
   renders it to short OGG clips, one per *(section, intensity, bar)*.
2. **`systems/music/` — a numpy-free runtime player.** Loads the clips as
   `Sound`s, plays them gaplessly on one dedicated channel with
   `Channel.queue()`, and at every bar boundary picks which
   (section, intensity) clip comes next from the game state. Zero DSP at
   runtime, pure pygame, works on desktop and pygbag.

This gives adaptive, layered, multi-section music while keeping the
runtime as simple as the current cue player.

#### Composer design (offline)

- **Form.** Sections: `menu`, `explore`, `combat`, `boss`, `village`,
  each 8 bars long at a fixed tempo so any bar can follow any other
  (120 BPM base, bar = 2.0 s; boss keeps the tempo but uses double-time
  drums so bars stay interchangeable). Short stings for level-up,
  game-over and victory can stay as synthesised cues.
- **Harmony.** One mode per island family (meadow → Dorian, forest →
  Aeolian, village → Lydian/major, boss → Phrygian). A small functional
  grammar (tonic → pre-dominant → dominant → tonic, with weighted
  substitutions such as bVII or iv) generates an 8-bar progression per
  section, seeded so the same seed yields the same progression.
- **Motif.** A fixed 8-note hero theme. Every section restates it through
  variation operators: transposition into the current chord, inversion,
  retrograde fragment, rhythmic displacement, octave shift. Chord tones on
  strong beats, passing tones on weak ones. This is what makes the track
  read as *one piece* rather than a playlist.
- **Layers** (this is also the intensity ladder, cumulative):
  0. pad — detuned saws through a one-pole low-pass, slow attack;
  1. arpeggio — 16th-note chord arps, gently filtered;
  2. bass — root/fifth ostinato following the progression;
  3. drums — kick (sine pitch drop), snare (noise + tone), hats
     (high-passed noise), patterns from Euclidean rhythms with seeded
     fills every 4th bar;
  4. lead — the motif variations;
  5. boss overlay — low-octave ostinato and toms, only in `boss`.
- **Synthesis.** Subtractive voices (sine / triangle / saw), ADSR
  envelopes, one-pole filters, a feedback delay and a small Schroeder
  reverb (combs + allpasses), soft-clip limiter on the master. All of
  this is a few hundred lines of numpy.
- **Rendering detail that matters.** Render each (section, intensity) as
  one continuous 8-bar stream *then* slice it into bars, so note and
  reverb tails cross bar boundaries naturally inside a mix. Switching
  intensity at a bar boundary cuts a tail; drums on the beat mask it, and
  pads get a short release to keep the seam clean.
- **Output.** 5 sections × up to 6 intensity levels × 8 bars ≈ 200 clips
  of 2 s. Roughly 6–8 MB of OGG on disk, about 10 MB decoded in RAM at
  22050 Hz mono (double for stereo 44.1 kHz). Acceptable for both builds.
  Plus one full-length static mix per section as the option-A fallback.
- **Determinism.** Same seed → byte-identical clips. Tests can render at a
  reduced rate and check bar lengths match across layers, peak level stays
  under clipping, and a digest is stable, in the style of the world tests.

#### Player design (runtime, no numpy)

- `MusicPlayer`: owns one reserved mixer channel, loads the bank lazily
  from `assets/music/`, plays bar N and immediately `queue()`s bar N+1;
  `Channel.set_endevent` or a per-frame `get_queue()` check tells it when
  to queue the next one. Silent backend → no-op, exactly like cues.
- `MusicDirector`: turns game state into (section, target intensity) at
  bar granularity. Menu/hero select → `menu`; village sanctuary → `village`;
  playing with no active room → `explore` at intensity 1–2; enemies alive
  (from `ENEMY_SPAWNED` / `ENEMY_KILLED` / room activation) ramp intensity
  up by one per bar toward a level set by live enemy count; low HP adds
  one; `BOSS_SPAWNED` → `boss`, `BOSS_KILLED` → back to `explore` with a
  drop to intensity 1; `RUN_ENDED` fades out. Intensity moves one step per
  bar so changes feel musical, never abrupt.
- Volume: a separate music volume next to the existing master, persisted
  in the same settings dict; pause dips it.
- Mixer: consider opening the desktop device at 44100 Hz stereo; the
  backend already knows how to resample and up-mix the mono cues, so the
  eight existing sounds keep working and the music gains stereo width.

#### Costs

| Piece | Effort |
|-------|--------|
| Offline composer + renderer (tools/music/) | 2–3 days to a good-sounding first bank; timbre iteration is open-ended |
| Runtime player + director | about 1 day |
| Tests and packaging (spec datas, pygbag bundle) | about half a day |

The biggest risk is taste, not engineering: a rule-based composer can sound
mechanical. The mitigations are the fixed hero motif, humanised velocity
and micro-timing in the renderer, and an offline listening loop where the
seed and grammar weights are tuned by ear before the bank is baked.

## Recommendation

Option C. It keeps the game's "all audio is original" promise, respects the
no-numpy runtime, works on both desktop and browser builds, and is the only
option that reacts to the run. Option A's static mix falls out of the same
generator for free as a fallback.

## Open decisions for the user

- Stereo 44.1 kHz device (better music) vs keeping the current mono 22050
  cue path untouched.
- Whether the bank is baked per world seed (progression varies by seed in
  the offline tool) or one fixed bank ships. One fixed bank is the sane
  first step.
- Whether an AI-generated track is acceptable as a *placeholder* while the
  composer is built, given the licensing note above.

## Progress

- [x] Review written (this entry). No code.
