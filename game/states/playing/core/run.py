"""`Run`: the state of one run, shared by the sub-systems.

`PlayingState` used to be both the coordinator -- the frame pipeline, the
draw order, the event routing -- and the bag every sub-system reached into
for the pools, the services and the run's facts (`ps.enemies`, `ps.rng`,
`ps.stats`, ...). The earlier split (`journals/playing_state_refactor.md`)
extracted the sub-systems but left them holding the whole state; this is
the `RunContext` that split deferred (structure review, D).

A `Run` holds what the sub-systems read and write: the run's facts, the
world and the hero, the entity pools, the feedback services, the transient
effect lists, the screen feedback timers and the input state. It knows
nothing about states, screens or the frame order; the few rules that
belong to the run as a whole -- the gold counters, the targetable bodies,
the world margin, a notice -- are methods here.

`PlayingState` builds one in `enter` and keeps every name the tests and
the older call sites read (`ps.enemies`, `ps._explosions`, `ps.rng`, ...)
as properties forwarding to it (`FIELDS` / `ALIASES`), so nothing outside
the package has to know the run moved.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame


@dataclass
class Run:
    # --- facts --------------------------------------------------------
    seed: int
    rng: object                       # random.Random, seeded by `seed`
    difficulty: str
    dev_mode: bool
    content: object                   # `game.content.Content`
    game: object                      # the `Game`: assets, events, audio, save
    character_id: str = ""
    # --- world and hero (set during `enter`) ----------------------------
    game_map: object = None
    player: object = None
    boss: object = None
    camera: object = None
    # --- entity pools ---------------------------------------------------
    enemies: list = field(default_factory=list)
    projectiles: object = None        # Pool[Projectile]
    hostiles: object = None           # Pool[Projectile]
    gems: object = None               # Pool[XPGem]
    potions: object = None            # Pool[HealthPotion]
    summons: object = None            # Pool[Summon]
    hazards: list = field(default_factory=list)
    melee_hitboxes: list = field(default_factory=list)
    interactables: list = field(default_factory=list)
    chests: list = field(default_factory=list)
    npcs: list = field(default_factory=list)
    boats: list = field(default_factory=list)
    fish_huts: list = field(default_factory=list)
    # --- services -------------------------------------------------------
    grid: object = None               # SpatialGrid over the enemies, per frame
    particles: object = None
    damage_numbers: object = None
    shake: object = None
    levels: object = None             # LevelTracker
    ledger: object = None             # RunLedger
    stats: dict = field(default_factory=dict)
    # --- transient effects ----------------------------------------------
    explosions: list = field(default_factory=list)   # blast visuals
    impacts: list = field(default_factory=list)      # CR1: the Hammer's impact sheets
    slashes: list = field(default_factory=list)      # the Sword's two-strip swing
    death_fx: list = field(default_factory=list)     # [Animator("dead"), pos, facing, ...]
    trail_fx: list = field(default_factory=list)     # projectile dust bursts
    spawn_fx: list = field(default_factory=list)     # [Animator("enemy_spawn"), body]
    # --- screen feedback --------------------------------------------------
    hurt_flash_t: float = 0.0
    boss_warning_t: float = 0.0
    boss_name: str = ""
    notice_t: float = 0.0
    notice_text: str = ""
    # --- input --------------------------------------------------------------
    auto_attack: bool = True
    aim: object = None                # this frame's `AimInput`
    tap_pending: bool = False         # a queued click-attack
    mouse_armed: bool = True          # ignored while an overlay's click is still held
    last_move_dir: pygame.Vector2 = field(default_factory=lambda: pygame.Vector2(1, 0))
    frame: int = 0                    # update count; the tick LOD's phase

    # --- rules of the run as a whole -----------------------------------
    def notice(self, text: str, seconds: float = 2.5) -> None:
        """Show `text` at the bottom of the screen for a moment (P3)."""
        self.notice_text = text
        self.notice_t = float(seconds)

    # The balance and the run total move together here rather than at each
    # income site, because the end screens report the gold *earned* over the
    # run, not what is left after the Merchant (owner, 2026-09-12): a run that
    # picks up 200 and spends 50 reports 200. Two counters kept in step by
    # convention would drift the first time an income source forgot one.
    def add_gold(self, amount: int) -> int:
        """Bank `amount` gold. Returns what was actually added."""
        amount = int(amount)
        if amount <= 0:
            return 0
        self.stats["gold"] += amount
        self.stats["gold_earned"] = self.stats.get("gold_earned", 0) + amount
        return amount

    def spend_gold(self, amount: int) -> bool:
        """Take `amount` off the balance if it is there; False when it is not.
        The run total is untouched -- spending is not un-earning."""
        amount = int(amount)
        if amount <= 0 or self.stats["gold"] < amount:
            return False
        self.stats["gold"] -= amount
        return True

    def targetables(self) -> list:
        """What the hero's weapons and summons may hit: the enemies, and the
        boss while it lives."""
        if self.boss is not None and self.boss.alive:
            return self.enemies + [self.boss]
        return self.enemies

    def in_world_margin(self, pos: pygame.Vector2, margin: float) -> bool:
        return (-margin <= pos.x <= self.game_map.width + margin
                and -margin <= pos.y <= self.game_map.height + margin)


# The `Run` fields `PlayingState` forwards under their own names, and the
# underscore-prefixed names it forwards for the callers and tests that grew
# up with them (`ps._explosions` is `run.explosions`, `ps.run_seed` is
# `run.seed`). Kept as data so the state's forwarding is one loop.
FIELDS = tuple(Run.__dataclass_fields__)
ALIASES = {
    "run_seed": "seed",
    "_explosions": "explosions", "_impacts": "impacts", "_slashes": "slashes",
    "_death_fx": "death_fx", "_trail_fx": "trail_fx", "_spawn_fx": "spawn_fx",
    "_hurt_flash_t": "hurt_flash_t", "_boss_warning_t": "boss_warning_t",
    "_boss_name": "boss_name", "_notice_t": "notice_t", "_notice_text": "notice_text",
    "_aim": "aim", "_tap_pending": "tap_pending", "_mouse_armed": "mouse_armed",
    "_last_move_dir": "last_move_dir", "_frame": "frame",
}


# The aliases as properties on `Run` itself, so a sub-system may read the
# fx lists and timers under the names the tests' fakes set (`_explosions`,
# `_hurt_flash_t`, ...) whether it was handed a `Run` or a bare namespace.
for _alias, _name in ALIASES.items():
    setattr(Run, _alias, property(
        lambda self, n=_name: getattr(self, n),
        lambda self, v, n=_name: setattr(self, n, v)))
del _alias, _name
