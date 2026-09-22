# Sound effects journal — the recorded cues

**Legacy ID:** AUD-003 · **Systems:** AUD · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## Requirement (owner, 2026-09-16)

- **Objective:** Wire up the recorded sound effects.
- **Details:** Check the sounds first — the biggest file only carries its
  audio at the start of the track and needs cutting — and rename the files
  for proper management.
- **Constraint:** Credit the two sources by name; the effects come from
  freesound.org.

Delivered into `assets/sound_effects/`. Companion to
`music_journal.md` — that entry covers the two streamed Pixabay tracks; this
one covers the recorded cues, which are a different mechanism (short
`pygame.mixer.Sound` buffers on the cue channels, not a stream).

## The sources, measured

Three Freesound downloads, 5.6 MB in total. The owner's diagnosis of the big
one was right, and it turned out to be true of all three in different degrees.

| file | length | rate | peak | the problem |
|------|--------|------|------|-------------|
| `386678__laurenmg95__grass_footstep_hard_4.wav` | 1.46 s | 44.1 kHz | −9.7 dBFS | the step lands at **0.230 s**; 0.20 s of handling noise before it and 1.13 s of silence after |
| `386686__laurenmg95__grass_footstep_soft_4.wav` | 1.31 s | 44.1 kHz | −12.3 dBFS | the step lands at **0.090 s**; 1.01 s of silence after |
| `869056__signaturesoundsorg__monster_growls_grunts_10.wav` | 14.08 s | **96 kHz** | −21.6 dBFS | the growl is over by ~2.2 s; the remaining **11.9 s** is a −84 dBFS noise floor. Also the wrong sample rate, and far quieter than the footsteps |

Two findings beyond "it needs cutting":

- **Leading silence is worse than trailing silence.** `Sound.play()` starts at
  frame 0, so 0.23 s of quiet run-up on the hard footstep is not texture — it
  is latency, heard as a lag between the key and the step. Trimming on a
  −40 dB silence floor alone did *not* remove it, because the run-up sits above
  that floor. Finding the *start* needs a stricter threshold than finding the
  end; see `attack_rel` below.
- **The growl's level is not comparable to the footsteps'.** At −21.6 dBFS
  peak against −9.7, it would have been inaudible under them without
  normalisation.

## What was done to the files

`tools/asset_pipeline/cut_sound_effects.py`, in the style of the existing
`cut_*.py` scripts and pure stdlib (`wave` + `array`, no numpy, so it runs in
the game's own venv). Per file: find the content bounds, trim, resample to the
device rate, fade the new end, normalise.

Two decisions inside it are worth keeping:

- **`attack_rel`** — the start of the content is where the level first crosses
  a fraction of the file's *peak*, not of the silence floor. The footsteps use
  5 %, which lands on the step itself; the growl keeps the default 1 %, because
  it is already at 19 % of its peak in the first 20 ms and a stricter threshold
  would clip its onset. A 15 ms pre-roll puts the attack's leading edge back.
- **Normalisation is per group, not per file.** The two footsteps are a matched
  pair — "hard" is meant to be louder than "soft" — so they share one gain
  factor and keep their 2.6 dB contrast. The growl is normalised alone.

Result:

| cue | from | to | size |
|-----|------|----|------|
| `footstep_grass_hard.wav` | 1.46 s, −9.7 dBFS | **0.109 s**, −2.9 dBFS | 252 KB → 19 KB |
| `footstep_grass_soft.wav` | 1.31 s, −12.3 dBFS | **0.221 s**, −5.5 dBFS | 226 KB → 38 KB |
| `monster_growl.wav` | 14.08 s @ 96 kHz, −21.6 dBFS | **2.400 s** @ 44.1 kHz, −2.9 dBFS | 5281 KB → 413 KB |

**5.6 MB → 0.46 MB**, and all three reach half their peak within 30–50 ms, so
they sound the instant they are played.

The originals are archived unmodified in `assets/sound_effects/unused/` under
their Freesound filenames — which carry the ID and the author, and are what the
CC BY credit points at. Re-cut with:

```
python -m tools.asset_pipeline.cut_sound_effects
```

## Licensing

Checked per file on freesound.org, because **Freesound sets the licence per
upload** and these are not all the same:

| file | author | ID | licence |
|------|--------|----|---------|
| grass_footstep_hard_4 | laurenmg95 | 386678 | **CC BY 4.0 — attribution required** |
| grass_footstep_soft_4 | laurenmg95 | 386686 | **CC BY 4.0 — attribution required** |
| Monster_Growls_Grunts_10 | SignatureSoundsOrg | 869056 | CC0 — attribution not required |

CC BY 4.0 also requires that modifications be **indicated**, and all three files
were modified (trimmed, resampled, normalised, faded). `assets/CREDITS.md` now
carries a Sound effects section with the authors, IDs, source links, licences, a
"Changes made" subsection and ready-made attribution text, and its opening
paragraph flags that this is the one credit block that must not be dropped from
a shipped build.

## Wiring

### One library, two kinds of cue

`systems/audio.py` was "every effect is synthesised, no files". It now builds
the eight synth cues and then loads the recorded ones from
`config.SOUND_EFFECTS` **on top**, into the same dict. `play()` does not know
or care which a cue is. A recorded name that collides with a synthesised one
simply replaces it — which is how the boss growl took over `boss_spawn`.

The files are pre-cut at the device's 44.1 kHz, so `pygame.mixer.Sound(path)`
converts nothing. A missing or undecodable file is skipped with a warning and
the cue is absent, so `play()` no-ops — the same degradation the synth path
already had.

### Per-play gain

`play(name, gain=1.0)`. This is what lets one recording serve two moments at
two levels without a second copy of the file. The level is set on the
**channel** the play returns, not on the `Sound`: a `Sound`'s volume is shared
by every play of it, so the boss growl and the room growl would otherwise fight
over it.

### The growl: boss entrance and room wake (owner's choice)

- `BOSS_SPAWNED` → full level. This replaces the synthesised saw sweep, which
  was the weakest of the eight cues.
- `ROOM_ACTIVATED` → `config.GROWL_ROOM_GAIN` (0.45), with a
  `GROWL_ROOM_MIN_GAP_MS` (6 s) floor so walking across several islands does
  not chain growls.

**The gate on that second one was wrong at first and is worth recording.** The
obvious reading of the payload is "growl when `woke` is truthy". But
`SpawnMaster` publishes `woke=` the count of *previously hibernating* enemies
re-queued, and `seeded=` the count of residents a room gets on **first** entry —
so a first visit reports `woke=0, seeded=N`. Gating on `woke` alone would have
been exactly backwards: silent the first time into an island, growling only on
the way back through. The condition is `woke or seeded`, and a room that
activates genuinely empty stays silent. Confirmed against a real run: the
payloads were `(0, 0, 0), (1, 0, 0), (2, 0, 2), (3, 0, 1), (4, 0, 1)` — the two
empty islands silent, the populated ones eligible, and the 6 s floor holding
five activations to one growl.

### Footsteps: alternating takes, speed-scaled cadence (owner's choice)

A `_Footsteps` helper in `systems/audio.py`; the run calls
`audio.tick_footsteps(dt, moving, speed)` from `_phase_update` in one line.

- **A stride, not an interval.** One step per `FOOTSTEP_STRIDE_PX` (64 px, one
  tile) of ground covered. That makes the cadence scale with the hero's move
  speed on its own, with no base-speed constant here to drift out of sync with
  `data/heroes/characters.json`. At the heroes' 140–170 px/s it lands at
  0.38–0.46 s, an ordinary walking pace; the derived interval is then clamped
  to 0.16–0.85 s so a stacked speed build is not a machine gun.
- **Distance is accumulated, not sampled**, so the remainder carries across
  frames and a slow frame does not drop a step.
- **The takes alternate**, which reads as a gait; one sample on repeat does not.
- Footsteps follow the *input* direction, not the resolved motion, so a
  knockback shove or walking into a wall produces no phantom steps.
- `FOOTSTEP_GAIN` 0.30 — they are constant, so they sit well under everything.

## Packaging

- **PyInstaller**: `"sound_effects"` added to `ASSET_DIRS`. The spec skips
  `unused/` at any depth, so only the 0.46 MB of cues ship.
- **pygbag**: this one needed a fix. Its `ignoreDirs` is a deny-list matching
  **whole paths**, and it listed `/assets/unused` but nothing nested — so the
  5.6 MB of Freesound originals would have shipped to the browser alongside the
  0.46 MB of cues. `/assets/sound_effects/unused` is now listed, with a comment
  explaining that each nested `unused/` has to be added by hand.

## Verified

- 149 tests in `tests/systems/` green, including the new
  `tests/systems/test_sound_effects.py`.
- Driven against a **real** audio device: 10 cues load (7 synth + 3 recorded),
  `boss_spawn` is the 2.4 s growl rather than the 0.7 s sweep, and a real run
  produced 7 alternating footsteps in 3 s of walking at gain 0.30 — a 0.43 s
  cadence at Aegis's 150 px/s.
- Cadence measured across speeds: 0.457 s at 140 px/s, 0.377 s at 170, clamped
  to 0.160 s at 400 and 0.850 s at 60.

## Open

- The growl is one recording used for two different moments. If it starts to
  read as repetitive, the Freesound pack it came from has more takes and
  `config.SOUND_EFFECTS` would take them as extra names.
- Footsteps are grass-only, which every island currently is. Bridges and the
  village's stone would want their own takes if that stops being true.

## Progress

- [x] Sources reviewed and measured; the dead air quantified.
- [x] `tools/asset_pipeline/cut_sound_effects.py`; files cut, resampled,
      normalised, renamed, originals archived.
- [x] Licences checked per file; `assets/CREDITS.md` Sound effects section.
- [x] `systems/audio.py`: file cues, per-play gain, footstep cadence.
- [x] Growl on boss spawn and on a room waking.
- [x] Footsteps wired into the run.
- [x] PyInstaller `ASSET_DIRS`; pygbag nested-`unused` exclusion.
- [x] `tests/systems/test_sound_effects.py`.
