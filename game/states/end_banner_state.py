"""END BANNER: the animated card between the run and its summary screen.

When the hero's HP reaches zero, or the boss falls, the run does not cut
straight to the résumé any more (owner, 2026-09-19; journal:
`documentation/journals/end_banner_journal.md`). This overlay is pushed on
top of the run instead, and walks three phases on a clock of its own:

* **wait** -- `config.END_BANNER_WAIT` seconds. The run underneath keeps
  animating (`update_below` is True), so the death poof and the boss burst
  play out on the scene the player was just looking at. Nothing is drawn
  over it yet.
* **banner** -- the world freezes (`update_below` flips to False), a dim
  layer settles over it, and the "GAME OVER" / "You Won!" sprite plays its
  one-shot animation through: letters fly in, hold, fly out.
* **hold** -- `config.END_BANNER_HOLD` seconds on the animation's last frame
  (the banner has left; the dimmed scene stays), then `on_done` is called.

`on_done` is the run's hand-off (`PlayingState._hand_off`): it publishes
`RUN_ENDED` and changes to the game-over or victory screen, which are
untouched by this -- they still receive the summary the run snapshotted the
moment the outcome was decided, so the time and gold they show are the
run's at that instant, not eight seconds later. A developer-mode run shows
the same intermission and then takes its usual reset.

No key or click skips it (owner). Input is swallowed here so the run
underneath does not act on it either.

The sprite is driven by `systems.animation.Animator` off the
`end_banner_loss` / `end_banner_win` rigs in `data/ui/ui_sprites.json`, so
the frame count, the 15 FPS and the one-shot come from data. With the art
missing (an empty `assets/`) the banner is the same words in the heading
face, so the timing is identical with or without pixels.
"""
from __future__ import annotations

from typing import Callable

import pygame

from game import config, fonts
from game.state import State
from systems.animation import Animator
from ui import scale

WAIT, BANNER, HOLD, DONE = "wait", "banner", "hold", "done"

RIGS = {False: "end_banner_loss", True: "end_banner_win"}
ANIM = "show"
FALLBACK_TEXT = {False: "GAME OVER", True: "YOU WON!"}
FALLBACK_COLOUR = {False: (230, 90, 90), True: (255, 214, 112)}
# The banner's centre, as a fraction of the box height: a touch above the
# middle so it reads as a title over the scene rather than a caption on it.
CENTRE_Y = 0.42


class EndBannerState(State):
    draw_below = True
    ui_box = True
    music = None            # the run's track fades the moment the outcome is decided

    def __init__(self, game) -> None:
        super().__init__(game)
        self.update_below = True        # per instance: the wait phase animates the run
        self.victory = False
        self.phase = WAIT
        self.t = 0.0                    # seconds into the current phase
        self.elapsed = 0.0              # seconds since enter
        self._on_done: Callable[[], None] | None = None
        self._anim: Animator | None = None
        self._font = None
        self._dim: pygame.Surface | None = None

    # --- lifecycle ---------------------------------------------------
    def enter(self, *, victory: bool = False, on_done: Callable[[], None] | None = None,
              **kwargs) -> None:
        self.victory = bool(victory)
        self._on_done = on_done
        self.phase = WAIT
        self.t = 0.0
        self.elapsed = 0.0
        self.update_below = True
        assets = getattr(self.game, "assets", None)
        self._anim = Animator(assets, RIGS[self.victory], start=ANIM) if assets else None

    def on_display_changed(self) -> None:
        self._font = None
        self._dim = None

    # --- timing ------------------------------------------------------
    @property
    def banner_seconds(self) -> float:
        """One play of the sprite, from the rig: frames / fps."""
        a = self._anim
        if a is None:
            return 0.0
        n = a.assets.frame_count(a.rig, a.anim)
        fps = a.assets.fps(a.rig, a.anim)
        return n / fps if n and fps else 0.0

    def update(self, dt: float) -> None:
        if self.phase == DONE:
            return
        self.elapsed += dt
        self.t += dt
        if self.phase == WAIT:
            if self.t >= config.END_BANNER_WAIT:
                self.t -= config.END_BANNER_WAIT
                self.phase = BANNER
                self.update_below = False           # the world freezes under the banner
                if self._anim is not None:
                    self._anim.play(ANIM, restart=True)
                    self._anim.update(self.t)
            return
        if self.phase == BANNER:
            if self._anim is not None:
                self._anim.update(dt)
                finished = self._anim.finished
            else:
                finished = True
            if finished:
                self.t = max(0.0, self.t - self.banner_seconds)
                self.phase = HOLD
            return
        if self.phase == HOLD and self.t >= config.END_BANNER_HOLD:
            self.phase = DONE
            if self._on_done is not None:
                self._on_done()

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        """Swallowed: nothing shortens the intermission (owner)."""

    # --- render ------------------------------------------------------
    def _dim_alpha(self) -> int:
        if self.phase == WAIT:
            return 0
        if self.phase == BANNER and config.END_BANNER_DIM_FADE > 0:
            k = min(1.0, self.t / config.END_BANNER_DIM_FADE)
            return int(config.END_BANNER_DIM_ALPHA * k)
        return config.END_BANNER_DIM_ALPHA

    def draw_backdrop(self, surface: pygame.Surface) -> None:
        # The whole render surface, side margins included on a 21:9 render --
        # the pause overlay's arrangement.
        alpha = self._dim_alpha()
        if alpha <= 0:
            return
        if self._dim is None or self._dim.get_size() != surface.get_size():
            self._dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, alpha))
        surface.blit(self._dim, (0, 0))

    def draw(self, surface: pygame.Surface) -> None:
        if self.phase != BANNER:
            return                      # nothing over the scene while waiting or holding
        centre = (surface.get_width() // 2, int(surface.get_height() * CENTRE_Y))
        frame = None
        if self._anim is not None:
            rig = self._anim.assets.rig(self._anim.rig) or {}
            fw, fh = rig.get("frame", (0, 0))
            k = scale.int_scale(config.END_BANNER_SCALE)
            size = (int(fw) * k, int(fh) * k) if fw and fh else None
            frame = self._anim.frame(size=size)
        if frame is None:
            # No art: the same words, the same clock.
            if self._font is None:
                self._font = fonts.heading(96)
            frame = self._font.render(FALLBACK_TEXT[self.victory], True,
                                      FALLBACK_COLOUR[self.victory])
        surface.blit(frame, frame.get_rect(center=centre))
