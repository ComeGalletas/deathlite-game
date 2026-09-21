"""Fish huts and their seahorse boats for PLAYING (journals/fish_hut_journal.md):
built from the layout's `FishHut` records, stepped each frame, and handed to
the depth-sorted character layer.

Reads from `PlayingState`: `game_map`, `camera`, `game.assets`, and
`npc_manager.draw_one` for the blit. Owns `ps.fish_huts` (the huts, static
props that bob) and `ps.boats` (the `WaterNpc`s, two to four per hut).

The hut is drawn through the character layer rather than the flat water
scenery under the islands so that a boat drifting north of it is hidden by it
and one south of it draws over it. Both sit in band 0 -- the sea has no
terrace -- at their own depth.

A boat's home is dealt `boat_ring` tiles out from its hut at a seeded angle,
on open water; the boat then drifts within its leash of that home. Nothing
here fights, blocks, or is targeted: the riders some sheets draw are art.
"""
from __future__ import annotations

import random

import pygame

from entities.npc import WaterNpc
from game import config
from game.content import get_content
from systems.animation import Animator

HUT = "fish_hut"
BOAT = "seahorse_boat"
# How many angles a boat tries for a home on open water before it gives up
# and is not built: a hut whose water is that crowded has fewer boats.
_HOME_TRIES = 8


class FishHutProp:
    """A moored hut: what `Npcs.draw_one` needs of an NPC, standing still.
    `radius` 0 keeps the render drop off, so the anchor is the waterline."""
    __slots__ = ("kind", "rig", "pos", "anim", "facing", "radius")

    def __init__(self, rig: str, x: float, y: float, assets) -> None:
        self.kind = HUT
        self.rig = rig
        self.pos = pygame.Vector2(x, y)
        self.anim = Animator(assets, rig, start="idle") if assets.rig(rig) else None
        self.facing = 1
        self.radius = 0.0


class FishHuts:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self.data = get_content().npcs
        self.rng = random.Random()

    # --- build ---------------------------------------------------------
    def build(self) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        run.fish_huts = []
        run.boats = []
        layout = run.game_map.layout
        records = getattr(layout, "fish_huts", None) if layout is not None else None
        if not records:
            return
        px = config.TILE_PX
        assets = ps.game.assets
        spec = self.data["kinds"][BOAT]
        place = self.data["placement"]
        rigs = list(spec["rigs"])
        lo, hi = place["boats"]
        ring = place["boat_ring"]
        # Seeded by the world, like the villagers: a seed's boats are the
        # same boats every run.
        self.rng = random.Random(f"{layout.seed}:fish_huts")
        rng = self.rng
        for rec in records:
            run.fish_huts.append(FishHutProp(f"npc_{HUT}", rec.x, rec.y, assets))
            for _ in range(rng.randint(lo, hi)):
                rig = rng.choice(rigs)
                for _ in range(_HOME_TRIES):
                    ang = rng.uniform(0.0, 6.283185307)
                    d = rng.uniform(*ring) * px
                    home = pygame.Vector2(rec.x, rec.y) + pygame.Vector2(d, 0).rotate_rad(ang)
                    if run.game_map.is_open_water(home.x, home.y):
                        run.boats.append(WaterNpc(BOAT, rig, home.x, home.y, spec,
                                                 assets, leash_px=spec["leash"] * px))
                        break

    # --- step ----------------------------------------------------------
    def update(self, dt: float) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        huts = getattr(ps, "fish_huts", None)
        boats = getattr(ps, "boats", None)
        if not huts and not boats:
            return
        idle = self.data["kinds"][BOAT]["idle"]
        pad = config.RENDER_ACTOR_CULL_PAD * 3
        view = run.camera.visible_rect().inflate(2 * pad, 2 * pad)
        world = run.game_map
        for h in huts or ():
            if h.anim is not None and view.collidepoint(h.pos.x, h.pos.y):
                h.anim.update(dt)
        for b in boats or ():
            if view.collidepoint(b.pos.x, b.pos.y):
                b.update(dt, self.rng, world, idle)

    # --- draw ----------------------------------------------------------
    def actor_items(self, view, lvl) -> list:
        """`(level, depth_y, draw_fn)` for the visible huts and boats."""
        ps = self.ps
        run = getattr(self, "run", ps)
        draw = ps.npc_manager.draw_one
        out = []
        for n in list(getattr(ps, "fish_huts", ())) + list(getattr(ps, "boats", ())):
            if view.collidepoint(n.pos.x, n.pos.y):
                out.append((lvl(n.pos.x, n.pos.y), n.pos.y,
                            lambda s, n=n: draw(s, n)))
        return out
