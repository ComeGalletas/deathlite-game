"""The loading screen: a dark screen, "Loading...", and the chosen hero
running in place while the world is built.

Building a run takes four to five seconds -- generation, the elevation index,
the terrain bake and the navigation field -- and `PlayingState.enter` used
to do all of it in one call, so the frame froze after ENTER on the hero
select and the browser tab hung with it. The loop is single-threaded and the
browser build has no threads (pygame surfaces have to be baked on the main
thread anyway), so the only way to keep drawing is to do the work in slices:
`generate_world_steps` and `bake_steps` yield between islands, and this
state advances them for a few milliseconds a frame.

When the last step is done the run starts with the world it built
(`PlayingState.enter(prebuilt=...)`), under the same seed, hero, difficulty
and developer flag it was entered with.
"""
from __future__ import annotations

import random
import time
from collections import namedtuple

import pygame

from game import config, fonts
from game.content import get_content
from game.state import State
from systems.animation import Animator
from world.gen import generate_world_steps
from world.map import GameMap
from world.pathfinding import NavField
from world.terrain.bake import bake_steps

PrebuiltWorld = namedtuple("PrebuiltWorld", "game_map nav")

_BG = (10, 10, 14)
_FG = (235, 235, 240)
# How long to keep stepping inside one frame before drawing again. A step is
# 50-350 ms on its own, so most frames run one; the budget only matters for
# the many small ones.
_BUDGET_S = 0.030


class LoadingState(State):
    def enter(self, *, seed: int | None = None, character_id: str | None = None,
              dev: bool = False, difficulty: str | None = None, **kwargs) -> None:
        # The seed is decided here, not in the run, so the world built here
        # is the run's world.
        self.run_seed = seed if seed is not None else random.randrange(1 << 30)
        content = get_content()
        self.character_id = character_id or next(iter(content.characters))
        self._run_kwargs = dict(seed=self.run_seed, character_id=self.character_id,
                                dev=dev, difficulty=difficulty)

        cdef = content.character(self.character_id)
        rig = cdef.get("sprite")
        assets = self.game.assets
        self._anim = None
        if rig and assets.frame_count(rig, "walk") > 0:
            self._anim = Animator(assets, rig, "walk")
        self._hero_color = tuple(cdef.get("color", config.COLOR_PLAYER))

        self._font = fonts.heading(48)
        self._label = "Loading..."
        self._steps = self._work()
        self._prebuilt: PrebuiltWorld | None = None

    # --- the work, one slice at a time -------------------------------
    def _work(self):
        """Every step of building a run, as a generator. Sets `_prebuilt`
        when it is exhausted."""
        steps = generate_world_steps(self.run_seed)
        while True:
            try:
                yield next(steps)
            except StopIteration as done:
                layout = done.value
                break
        gm = GameMap(seed=self.run_seed, layout=layout)
        yield "elevation"
        steps = bake_steps(layout)
        while True:
            try:
                yield next(steps)
            except StopIteration as done:
                gm.terrain = done.value
                break
        nav = None
        if config.ENEMY_PATHFINDING:
            nav = NavField(layout, layout.obstacles)
            yield "navigation"
        self._prebuilt = PrebuiltWorld(gm, nav)

    def update(self, dt: float) -> None:
        if self._anim is not None:
            self._anim.update(dt)
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < _BUDGET_S:
            try:
                next(self._steps)
            except StopIteration:
                self._start_run()
                return

    def _start_run(self) -> None:
        from game.states.playing_state import PlayingState
        self.game.state_machine.change(PlayingState(self.game),
                                       prebuilt=self._prebuilt, **self._run_kwargs)

    # --- the screen ----------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx, cy = surface.get_width() // 2, surface.get_height() // 2
        text = self._font.render(self._label, True, _FG)
        surface.blit(text, text.get_rect(center=(cx, cy - 40)))
        self._draw_hero(surface, cx, cy + 60)

    def _draw_hero(self, surface, cx: int, ground_y: int) -> None:
        """The hero as the run draws it -- same rig, same size, same anchor
        -- standing on `ground_y`, running in place."""
        assets = self.game.assets
        z = config.CAMERA_ZOOM
        if self._anim is None:
            r = round(16 * z)
            pygame.draw.circle(surface, self._hero_color, (cx, ground_y), r)
            pygame.draw.circle(surface, config.COLOR_PLAYER_OUTLINE, (cx, ground_y),
                               r, width=2)
            return
        rig = self._anim.rig
        bw, bh = assets.scale_for(rig)
        frame = self._anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))))
        ax, ay = assets.anchor(rig)
        surface.blit(frame, (cx - ax * z, ground_y - ay * z))
