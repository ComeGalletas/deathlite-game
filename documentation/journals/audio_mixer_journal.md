# Audio mixer journal — a sound-effects level of its own

**Legacy ID:** AUD-002 · **Systems:** AUD, UI · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## Requirement (owner, 2026-09-16)

- **Objective:** Add a separate volume option for the sound effects.
- **Details:** The new level governs both the current synthesized sounds and
  the recorded voice clips for the growls.
- **Constraint:** Confirm the reading before implementing.

## Confirmed reading

Options has two volume rows today, **Master volume** and **Music volume**.
"Master volume" is a misnomer: it is not a master over anything, it is the
cue level — `AudioManager.volume`, applied per play in `systems/audio.py` and
touching nothing else. The music stream is entirely separate
(`MusicPlayer.volume`), so the two rows are siblings, not a parent and a
child.

The request adds a third level, **Sound effects**, and says what it governs:
*everything `AudioManager` plays*. That is both kinds of cue, which today are
already one library:

- the **eight synthesised cues** built at startup from sine / square / noise
  primitives — `shoot`, `hit`, `enemy_death`, `xp`, `level_up`,
  `player_hurt`, `boss_spawn`, `boss_death`;
- the **recorded clips** in `config.SOUND_EFFECTS`, loaded from
  `assets/sound_effects/` — the two grass footsteps and `monster_growl.wav`,
  the "voice clip" the requirement names. The growl plays twice over: at full
  level on a boss entrance (`BOSS_SPAWNED`, where the recording overwrote the
  synthesised saw sweep) and at `config.GROWL_ROOM_GAIN` when a populated
  room wakes.

`AudioManager.play` already folds a per-cue `gain` under the level, so the
footstep's 0.30 and the room growl's 0.45 keep their relative balance
whatever the new row is set to. Nothing about which cue is synthesised and
which is recorded needs to reach the Options screen — one row covers both,
which is what "naturally add" asks for.

Once Sound effects owns the cues, **Master volume has nothing left of its
own**, so it either becomes a true master over music *and* effects, or it
goes. That is the one decision the request leaves open; see below.

### What this touches

| file | change |
|------|--------|
| `game/config.py` | a default for the new level |
| `systems/audio.py` | the cue level folds in the master |
| `systems/music.py` | `_apply_volume` folds in the same master |
| `game/game.py` | load / persist the new setting |
| `game/save.py` | the new default in `settings` |
| `game/states/options_state.py` | a third slider row, and the layout moved up to fit nine rows above the hint |

## Proposal

**Three levels, one multiplication.** A cue plays at `master × sfx × gain`
and the music stream at `master × music`, with mute and the pause duck on top
exactly as now. Each owner keeps its own number: `AudioManager` gains
`set_master`, `MusicPlayer` gains `set_master`, and `Game.set_master_volume`
writes both and persists — no new module, no shared mutable global.

**Defaults, chosen so nothing the owner has already tuned moves.** Master
starts at **1.0**, Sound effects at **0.7** (today's cue level) and Music
stays at `config.MUSIC_VOLUME_DEFAULT` = 0.5. A fresh install therefore
sounds byte-identical to the current build.

**Migration is free.** `settings["volume"]` already *is* the effects level, so
it keeps its meaning and is simply read into the new row; the new
`settings["master_volume"]` defaults to 1.0 when a save predates it. A
returning player's mix is unchanged, and no migration code is needed. (The
key keeps the name `volume` rather than churning saves for a rename; the
Options row is what the player reads, and `save.py` documents the mapping.)

**The rows** become Master volume · Music volume · Sound effects · Mute · Key
layout · Display mode · Resolution · Sanctuary · Back — nine, up from eight.
At `y0 = 240` and a 74 px step the ninth row would land on the hint line, so
`_ROW_TOP` moves to 200, putting the last row at 792 with the hint at 860.
The in-run set (no Sanctuary) is eight rows.

**Feedback.** The `xp` blip moves with the meaning: the Sound effects row
blips as it steps, and so does Master (it changes how loud cues are). Music
stays silent — the track is its own feedback. The mouse drag added earlier
today works on the third bar with no new code, since `_SLIDER_ROWS` drives it.

**Tests.** `tests/systems/test_audio.py` / `test_music.py` for the
multiplication and the clamps; `tests/screens/test_options.py` for the new
row, its persistence, its independence from the other two, its drag, and the
old-save migration.

## Decision (owner, 2026-09-16)

**A — Master volume becomes a real master.** Three rows: Master over Music
and Sound effects, a cue at `master × sfx × gain` and the stream at
`master × music`. The alternative on the table was dropping Master and
leaving Music beside Sound effects; the owner chose the mixer.

## Todo

- [x] `game/config.py`: `MASTER_VOLUME_DEFAULT = 1.0`, `SFX_VOLUME_DEFAULT =
      0.7` (the level the cues already played at), beside
      `MUSIC_VOLUME_DEFAULT`; the `VOLUME_STEP` comment now covers all three.
- [x] `systems/audio.py`: `self.master`, `set_master(v)`, and `play()` at
      `master * volume * gain`. The per-cue gains are untouched, so the
      footstep's 0.30 and the room growl's 0.45 keep their balance.
- [x] `systems/music.py`: `self.master`, `set_master(v)`, `_apply_volume`
      folding it in under the mute and the duck.
- [x] `game/game.py`: `set_master_volume(v, persist=...)` sets both players
      from one place so their copies cannot drift; boot loads
      `settings["master_volume"]` through it with `persist=False`, and
      `persist()` writes all three levels.
- [x] `game/save.py`: `"master_volume": 1.0` in the default settings, with the
      mapping of the three keys documented where they are declared.
- [x] `game/states/options_state.py`: the `sfx` row, `_LABELS`,
      `_SLIDER_ROWS`, `_level_of` and a new `_apply_level` (the one place that
      knows which object owns which row, shared by the keyboard nudge and the
      mouse drag), and `_ROW_TOP` 240 -> 200 so nine rows clear the hint. The
      blip now follows the meaning: master and sound effects blip, music does
      not.
- [x] Tests: `tests/systems/test_audio.py` `MixerLevelTests` (+7, an injected
      cue pins `master * sfx * gain` with or without a device: the defaults
      reproducing today's 0.7, each level scaling, the gain folding under
      both, the clamp at both ends, `set_master` clamping and rounding, mute
      still winning); `tests/systems/test_music.py` `AppliedLevelTests` (+5)
      and two more in `LevelTests` (what reaches `mixer.music.set_volume`,
      the duck multiplying on top, mute and a silent master winning);
      `tests/screens/test_options.py` `MasterVolumeTests` (+9) and
      `MixerMigrationTests` (+3), with the old `VolumeTests` re-pointed at the
      `sfx` row it has always described. The file went 52 -> 64.
- [x] `README.md`: the controls table, the Options paragraph and the feature
      list.
- [x] Full suite green and a screenshot of the three bars.

## Verification (2026-09-16)

- `tests/screens/test_options.py`: 52 -> **64 passed**.
- `tests/screens/test_options.py` + `tests/systems`: **227 passed**.
- Full default suite: **2430 passed, 8 deselected, 487 subtests**, exit 0
  (16:23), up from 2387 before this entry.
- Screenshot: the nine-row screen at 1600x900 -- Master 100 %, Music 50 %,
  Sound effects mid-drag at 65 % -- with Back at y 793 clearing the hint at
  860.
- Not verifiable headless: how the three levels *sound* against each other.
  The arithmetic is pinned instead, and the defaults were chosen so the
  shipped mix is unchanged until the player moves a slider.
