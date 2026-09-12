"""Village NPCs for PLAYING (HI-3): built from the layout's `Village`
records, stepped each frame, and handed to the depth-sorted character
layer.

Reads from `PlayingState`: `game_map`, `camera`, `stats`, `game.assets`.
Owns `ps.npcs` (the list). Per village: a smith at the forge, a pawn or two
per house and a couple more wandering the ring, a garrison of four or five
lancers dealt round the guard posts and walking between barracks and tower,
and a few sheep in the pen. The lancers fight: an enemy that comes
within their aggro radius is charged and thrust at, then they walk back
to their post (`entities/npc.py`; `_foes` / `_hit` here are the hooks).
Colours come from a shuffled cycle per kind so no colour repeats before
every one has appeared -- never one colour per village.

Part of `journals/human_island_journal.md`.
"""
from __future__ import annotations

import random

import pygame

from combat.knockback import knock_split
from entities.npc import Npc, SheepNpc
from game import config
from game.states.playing.dps_meter import VILLAGER
from game.content import get_content


class _Cycle:
    def __init__(self, rng, items) -> None:
        self.rng, self.items, self.bag = rng, list(items), []

    def next(self):
        if not self.bag:
            self.bag = list(self.items)
            self.rng.shuffle(self.bag)
        return self.bag.pop()


class Npcs:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.data = get_content().npcs
        self.rng = random.Random()

    # --- build ---------------------------------------------------------
    def build(self) -> None:
        ps = self.ps
        ps.npcs = []
        layout = ps.game_map.layout
        if layout is None or not getattr(layout, "villages", None):
            return
        px = config.TILE_PX
        assets = ps.game.assets
        kinds = self.data["kinds"]
        place = self.data["placement"]
        # Seeded by the world, so a run's villagers are the same people each
        # time and a test can pin them.
        self.rng = random.Random(f"{layout.seed}:npcs")
        rng = self.rng
        colours = _Cycle(rng, self.data["colours"])

        def rig(kind):
            return kinds[kind]["rigs"].format(colour=colours.next())

        def spot_near(x, y, tiles, radius):
            """A walkable point within `tiles` of `(x, y)`, or `None`."""
            for _ in range(12):
                ang = rng.uniform(0.0, 6.283185307)
                d = rng.uniform(0.6, 1.0) * tiles * px
                cand = pygame.Vector2(x, y) + pygame.Vector2(d, 0).rotate_rad(ang)
                if ps.game_map.is_walkable(cand, radius):
                    return cand
            return None

        for v in layout.villages:
            # The smith, at the forge's front.
            spec = kinds["smith"]
            home = spot_near(v.forge.x, v.forge.y + 1.2 * px, 0.8, spec["radius"])
            if home is not None:
                ps.npcs.append(Npc("smith", rig("smith"), home.x, home.y, spec,
                                   assets, leash_px=spec["leash"] * px))
            # Pawns: some at the houses, a few more about the ring.
            spec = kinds["pawn"]
            homes = [(x, y) for kind, x, y in v.buildings if kind == "house"]
            wants = [(x, y) for x, y in homes
                     for _ in range(rng.randint(*place["pawns_per_house"]))]
            wants += [(v.forge.x, v.forge.y)
                      for _ in range(rng.randint(*place["extra_pawns"]))]
            for x, y in wants:
                home = spot_near(x, y, 2.5, spec["radius"])
                if home is not None:
                    ps.npcs.append(Npc("pawn", rig("pawn"), home.x, home.y, spec,
                                       assets, leash_px=spec["leash"] * px))
            # The garrison: `lancers` of them per village, dealt round the
            # guard posts in turn. Each patrols between its post's two
            # buildings (or stands by the one, if only one of the pair fit),
            # starting from a different end than the last so a shared post's
            # pair do not march in step. A village whose military row did
            # not fit at all musters its lancers round the forge instead.
            spec = kinds["lancer"]
            patrols = []
            for pair in v.posts:
                stops = []
                for x, y in pair:
                    s = spot_near(x, y + 0.9 * px, 1.2, spec["radius"])
                    if s is not None:
                        stops.append(s)
                if stops:
                    patrols.append(stops)
            if not patrols:
                patrols.append([pygame.Vector2(v.forge.x, v.forge.y + 1.8 * px)])
            for i in range(rng.randint(*place["lancers"])):
                stops = patrols[i % len(patrols)]
                turn = (i // len(patrols)) % len(stops)
                stops = stops[turn:] + stops[:turn]
                home = spot_near(stops[0].x, stops[0].y, 0.9, spec["radius"]) or stops[0]
                ps.npcs.append(Npc("lancer", rig("lancer"), home.x, home.y, spec,
                                   assets, leash_px=spec["leash"] * px,
                                   posts=stops if len(stops) > 1 else None,
                                   aggro_px=spec["aggro"] * px,
                                   chase_px=spec["chase"] * px))
            # The sheep, in the pen: 2-4, each on its own spot, stirring
            # within its leash of it.
            if v.pen is not None:
                spec = kinds["sheep"]
                pad = spec["radius"] + 4
                if v.pen.width > 2 * pad and v.pen.height > 2 * pad:
                    for _ in range(rng.randint(*place["sheep"])):
                        x = rng.uniform(v.pen.left + pad, v.pen.right - pad)
                        y = rng.uniform(v.pen.top + pad, v.pen.bottom - pad)
                        ps.npcs.append(SheepNpc(spec["rigs"], x, y, spec, assets, v.pen,
                                                spec["leash"] * px))

    # --- step ----------------------------------------------------------
    def update(self, dt: float) -> None:
        ps = self.ps
        npcs = getattr(ps, "npcs", None)
        if not npcs:
            return
        kinds = self.data["kinds"]
        # Only the villagers anywhere near the view move; the rest stand
        # where they are, which nobody can see.
        pad = config.RENDER_ACTOR_CULL_PAD * 3
        view = ps.camera.visible_rect().inflate(2 * pad, 2 * pad)
        world = ps.game_map
        foes, on_hit = self._foes, self._hit
        for n in npcs:
            if view.collidepoint(n.pos.x, n.pos.y):
                n.update(dt, self.rng, world, kinds[n.kind]["idle"],
                         foes=foes if n.aggro > 0.0 else None, on_hit=on_hit)

    def _foes(self, x: float, y: float, r: float) -> list:
        """The live enemies near a point, off the frame's spatial grid
        (last frame's cells: a frame stale, which a charge does not mind).
        The boss is not a villager's business."""
        ps = self.ps
        grid = getattr(ps, "grid", None)
        near = grid.query_circle(x, y, r) if grid is not None else ps.enemies
        return [e for e in near if e.alive]

    def _hit(self, npc, foe) -> None:
        """A lancer's thrust lands: the foe's own `take_damage` (so it
        provokes and hit-flashes like any hit), a damage number, a few
        sparks and a push through the same weight split as a bump."""
        ps = self.ps
        spec = self.data["kinds"][npc.kind]
        # `VILLAGER` so the DPS meter can drop it: a lancer that wanders over
        # and stabs the training dummy is not the hero's damage.
        dealt = foe.take_damage(npc.damage, source=VILLAGER)
        ps.damage_numbers.add(foe.pos, dealt, False)
        ps.particles.burst(foe.pos, (236, 226, 200), count=4, speed=90,
                           life=0.22, radius=2)
        if spec.get("knock"):
            _, push = knock_split(float(spec["weight"]), foe.weight, float(spec["knock"]))
            foe.apply_knockback(foe.pos - npc.pos, push)

    # --- draw ----------------------------------------------------------
    def actor_items(self, view, lvl) -> list:
        """`(level, depth_y, draw_fn)` for the visible villagers, for the
        character layer."""
        npcs = getattr(self.ps, "npcs", None)
        if not npcs:
            return []
        return [(lvl(n.pos.x, n.pos.y), n.pos.y,
                 lambda s, n=n: self.draw_one(s, n))
                for n in npcs if view.collidepoint(n.pos.x, n.pos.y)]

    def draw_one(self, surface, n) -> None:
        ps = self.ps
        r = ps.renderer
        z = ps.camera.zoom
        sx, sy = ps.camera.world_to_screen(n.pos)
        assets = ps.game.assets
        frame = None
        if n.anim is not None:
            bw, bh = assets.scale_for(n.rig) or (32, 32)
            flip = n.facing < 0 and assets.face(n.rig) == "right"
            frame = n.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                                 flip=flip)
        if frame is None:
            pygame.draw.circle(surface, (230, 220, 200), (int(sx), int(sy)),
                               round(n.radius * z))
            return
        ax, ay = assets.anchor(n.rig)
        if flip:
            # The lancer's crop is wide to the east for the lance's thrust,
            # so a mirrored frame mirrors its anchor too and the feet stay put.
            ax = bw - ax
        r._blit_character(surface, frame,
                          (sx - ax * z, sy - ay * z + r.sprite_drop(n.radius)),
                          n.pos.y)
