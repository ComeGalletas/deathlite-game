"""A fingerprint of a headless run: the same seed, the same frames, the
same numbers -- or the refactor moved something.

    python -m tools.verification.run_digest            # print the digests
    python -m tools.verification.run_digest --write    # pin them
    python -m tools.verification.run_digest --check    # compare to the pin

Boots a `Game` on the dummy SDL drivers with a throwaway save, drives the
menu into a run on each pinned seed (`tests/boot.start_run`), steps it
`FRAMES` frames of 1/60 s with a few debug spawns thrown in so combat, XP,
drops and the ledger all run, and hashes what the run holds afterwards: the
hero, the stats, every live enemy, the pools, the ledger, and the run RNG's
state. The A/B for the `PlayingState` split (structure review, D): the
digest before the split is the digest after it, frame for frame.

Not a test: it costs a boot and two world builds. Run it by hand around a
change to the run's wiring.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# No workarounds (SYS-008). This used to re-run itself under a pinned
# `PYTHONHASHSEED` and flatten the spawn watchdog's stagger, because one
# seed did not always play the same run. The causes were the flow-field
# fill's wall-clock slice and the watchdog's `id()`-based stagger; both are
# fixed, and a run is now the same in any process, under any hash seed and
# any load -- `tests/flows/test_run_determinism.py` holds it there.

SEEDS = (7, 123)
FRAMES = 720                     # 12 s of run
PIN = Path(__file__).with_name("run_digests.json")


def _num(v):
    return round(float(v), 4)


def _vec(v):
    return [_num(v.x), _num(v.y)]


def run_digest(seed: int) -> str:
    import pygame
    from game.game import Game
    from tests.boot import start_run

    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(_menu(game))
    ps = start_run(game, seed=seed)
    dt = 1 / 60
    for frame in range(FRAMES):
        if frame in (30, 90, 150):
            ps._spawn_enemy("skull", owner="dev")
        if frame == 200:
            ps.levels.add_xp(40)
        game.state_machine.update(dt)
        # A level-up overlay freezes the run; take the first card.
        cur = game.state_machine.current
        if cur is not ps and hasattr(cur, "_pick") and getattr(cur, "choices", None):
            cur._pick(0)
        if frame % 60 == 0:
            game._render()
    snap = {
        "player": {"pos": _vec(ps.player.pos), "hp": _num(ps.player.hp),
                   "level": ps.levels.level, "xp": ps.levels.total_xp,
                   "weapons": [w.weapon_id for w in ps.player.weapons],
                   "blessings": dict(ps.player.blessings)},
        "stats": {k: (_num(v) if isinstance(v, float) else v)
                  for k, v in ps.stats.items() if k != "dropped_items"},
        "enemies": sorted([e.enemy_id, _vec(e.pos), _num(e.hp)] for e in ps.enemies),
        "boss": None if ps.boss is None else [_vec(ps.boss.pos), _num(ps.boss.hp)],
        "pools": {"projectiles": len(ps.projectiles), "hostiles": len(ps.hostiles),
                  "gems": len(ps.gems), "potions": len(ps.potions),
                  "summons": len(ps.summons), "hazards": len(ps.hazards)},
        "ledger": {k: _num(v) for k, v in sorted(ps.ledger.damage.items())},
        "rng": hashlib.sha1(repr(ps.rng.getstate()).encode()).hexdigest()[:16],
        "camera": _vec(ps.camera.pos),
    }
    pygame.quit()
    if "--dump" in sys.argv:
        print(json.dumps(snap, sort_keys=True, indent=1))
    return hashlib.sha1(json.dumps(snap, sort_keys=True).encode()).hexdigest()[:20]


def _menu(game):
    from game.states.menu_state import MenuState
    game.running = True
    return MenuState(game)


def main(argv) -> int:
    got = {str(s): run_digest(s) for s in SEEDS}
    if "--write" in argv:
        PIN.write_text(json.dumps(got, indent=2) + "\n", encoding="utf-8")
        print("pinned", got)
        return 0
    if "--check" in argv:
        want = json.loads(PIN.read_text(encoding="utf-8"))
        bad = {s: (want.get(s), d) for s, d in got.items() if want.get(s) != d}
        print("match" if not bad else f"MOVED: {bad}")
        return 1 if bad else 0
    print(json.dumps(got, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
