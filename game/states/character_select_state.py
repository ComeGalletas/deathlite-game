"""CHARACTER_SELECT: pick a hero before a run (spec 4.1).

Shows each character's identity line, defining trait and starting weapon so the
choice is about playstyle, not just numbers. Under the hero cards a looping
preview plays the focused hero's idle -> walk -> attack animation; below that the
difficulty line, a **Begin** button, the game-instructions block
(`config.MENU_INSTRUCTIONS`, moved here from the start menu), then the nav hint.

Mouse (journal: "Mouse support in menus and UI"): hovering a card selects it;
the first click on a card selects *and arms* it, a second click on the same
card begins -- hovering or arrowing to another card disarms, so a slip cannot
start a run. The Begin button starts with one click; a Back target at the
bottom-left is ESC's twin. The difficulty ribbon is a switch: one click steps
Normal -> Fast -> Super Fast and wraps, the same step as Down (Up / Down
still work).
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.content import get_content
from game.state import State
from systems.animation import Animator
from ui import widgets
from ui.mouse import MouseNav
from ui.text import wrap

# The preview cycles these; idle / walk are held for a beat, attack plays once.
_PREVIEW_PHASES = ("idle", "walk", "attack")
_PREVIEW_HOLD = 1.4          # seconds a looping phase (idle / walk) is shown
_PREVIEW_PX = 130           # base preview box height
_PREVIEW_W = _PREVIEW_PX + 30   # base preview box width (sprites read wider than tall)
# Per-hero (dw, dh) tweak on the base box so each hero sits right.
_PREVIEW_ADJUST = {"nihil": (24, 0), "kestrel": (-18, 0)}
# Card body text wraps to the card width minus this inset each side, measured
# in the body font (`ui.text.wrap`), so it always clears the 9-slice frame.
_CARD_TEXT_INSET = 19       # 16 for the 9-slice frame + 3 px of breathing room
# The Begin button under the difficulty line, and the gaps around it. Drawn
# from the `wide` button sheets at the pack's native 64 px (the caps and
# bevel are authored for that height); 256 wide = four tiles.
_BEGIN_W, _BEGIN_H = 256, 64
_BEGIN_TEXT_DY = 3         # the Begin label sits this much higher than the shared lift
_BEGIN_GAP = 50              # difficulty ribbon centre -> button top (Begin tucks under the ribbon)
_INSTR_GAP = 18             # button bottom -> first instruction line centre
# The difficulty ribbon: the pack's 3-slice ribbon strip, its colour from
# `config.DIFFICULTY_RIBBON`, sized to the label plus its two forked ends.
_RIBBON_H = 64
_RIBBON_END = 64            # one cap tile each side, kept clear of the text
_RIBBON_MIN_W = 320
_RIBBON_TEXT_DY = -10        # lift the label pair off the ribbon's exact centre (optical)


class CharacterSelectState(State):
    def enter(self, **kwargs) -> None:
        self._dev = bool(kwargs.get("dev", False))   # forwarded to the run
        self.content = get_content()
        self.ids = list(self.content.characters.keys())
        self.index = 0
        # Per-run difficulty (never persisted). Up / Down cycles it.
        self.diff_index = config.DIFFICULTY_ORDER.index(config.DIFFICULTY_DEFAULT)
        self._title = fonts.heading(44)
        self._name = fonts.heading(30)          # hero names, "Difficulty:", Begin (title face)
        self._trait = fonts.heading(20)         # the trait line, title face
        self._diff_type = fonts.body(26)        # the difficulty *type*, body face
        self._body = fonts.body(20)
        self._instr = fonts.body(17)   # ~85% of the body font
        self._hint = fonts.body(16)
        # Mouse: card / button rects registered in draw(); `_armed_hero` is the
        # card the last click landed on (a second click on it begins).
        self._mouse = MouseNav()
        self._armed_hero: int | None = None

        # Hero animation preview -- one Animator, rebuilt when the pick changes.
        self._preview: Animator | None = None
        self._preview_index = -1
        self._phase_i = 0
        self._phase_t = 0.0
        self._sync_preview()

    def _sync_preview(self) -> None:
        """(Re)build the preview Animator for the focused hero, if it has a rig."""
        self._preview_index = self.index
        self._phase_i = 0
        self._phase_t = 0.0
        rig = self.content.characters[self.ids[self.index]].get("sprite")
        self._preview = Animator(self.game.assets, rig) if rig else None
        if self._preview is not None:
            self._preview.play(_PREVIEW_PHASES[0], restart=True)

    @property
    def difficulty(self) -> str:
        return config.DIFFICULTY_ORDER[self.diff_index]

    def update(self, dt: float) -> None:
        if self.index != self._preview_index:
            self._sync_preview()
        if self._preview is None:
            return
        self._preview.update(dt)
        self._phase_t += dt
        phase = _PREVIEW_PHASES[self._phase_i]
        done = self._preview.finished if phase == "attack" else self._phase_t >= _PREVIEW_HOLD
        if done:
            self._phase_i = (self._phase_i + 1) % len(_PREVIEW_PHASES)
            self._phase_t = 0.0
            self._preview.play(_PREVIEW_PHASES[self._phase_i], restart=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        act = self._mouse.event(event)
        if act is not None:
            self._mouse_action(*act)
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._select_hero((self.index - 1) % len(self.ids))
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._select_hero((self.index + 1) % len(self.ids))
        elif event.key in (pygame.K_UP, pygame.K_w):
            self._step_difficulty(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._step_difficulty(+1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._begin()
        elif event.key == pygame.K_ESCAPE:
            self._back()

    def _mouse_action(self, kind: str, key) -> None:
        if isinstance(key, tuple) and key[0] == "hero":
            i = key[1]
            if kind == "hover":
                self._select_hero(i)
            elif self._armed_hero == i:
                self._begin()                  # second click on the same card
            else:
                self._select_hero(i)
                self._armed_hero = i           # first click: select + arm
        elif kind == "click" and key == "begin":
            self._begin()
        elif kind == "click" and key == "back":
            self._back()
        elif kind == "click" and key == "difficulty":
            self._step_difficulty(+1)         # the ribbon is a switch: Down's step

    def _card_state(self, i: int) -> str:
        """Armed (first click landed) or held down -> `pressed`; the selected
        hero -> `hover` (gold); else `normal`. Hover selects, so a hovered
        card is the selected one and needs no state of its own."""
        if self._armed_hero == i or self._mouse.pressed_on == ("hero", i):
            return "pressed"
        if i == self.index:
            return "hover"
        return "normal"

    def _button_state(self, key) -> str:
        """`pressed` while the left button is held on `key`, `hover` while
        the cursor rests on it, else `normal`."""
        if self._mouse.pressed_on == key:
            return "pressed"
        if self._mouse.hover == key:
            return "hover"
        return "normal"

    def _step_difficulty(self, delta: int) -> None:
        """Cycle the difficulty, wrapping at both ends (Down / the ribbon
        click step forward, Up steps back)."""
        self.diff_index = (self.diff_index + delta) % len(config.DIFFICULTY_ORDER)

    def _select_hero(self, i: int) -> None:
        """Move the selection; leaving the armed card disarms it."""
        if i != self.index:
            self._armed_hero = None
        self.index = i

    def _begin(self) -> None:
        from game.states.loading_state import LoadingState
        self.game.state_machine.change(LoadingState(self.game),
                                       character_id=self.ids[self.index],
                                       difficulty=self.difficulty,
                                       dev=self._dev)

    def _back(self) -> None:
        from game.states.menu_state import MenuState
        self.game.state_machine.change(MenuState(self.game))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        w = surface.get_width()
        cx = w // 2

        title = self._title.render("Choose your hero", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 80)))

        hits = self._mouse.hits
        hits.clear()

        n = len(self.ids)
        card_w, gap = 340, 36
        x0 = (w - (n * card_w + (n - 1) * gap)) // 2
        y, card_h = 170, 340
        for i, cid in enumerate(self.ids):
            c = self.content.characters[cid]
            x = x0 + i * (card_w + gap)
            rect = hits.add(pygame.Rect(x, y, card_w, card_h), ("hero", i))
            # The card is a 9-slice button: gold when it is the selected
            # hero, sunk (the pressed sheet) while it is armed -- "click again
            # to begin" made visible -- or while the button is held on it.
            state = self._card_state(i)
            widgets.draw_button(surface, self.game.assets, rect, None,
                                state=state, shape="panel")
            dy = widgets.PRESSED_DY if state == "pressed" else 0

            # Text on the light card: the name and the trait line are titles
            # (title face, black); the rest is body text in the dark grey.
            name = self._name.render(c["name"], True, config.COLOR_ON_BUTTON)
            surface.blit(name, name.get_rect(midtop=(rect.centerx, y + 16 + dy)))

            trait_line = f"Trait - {c['trait_name']}"
            text_w = card_w - 2 * _CARD_TEXT_INSET      # pixel-measured wrap
            rows = wrap(self._body, c["identity"], text_w) + [
                "", trait_line,
            ] + wrap(self._body, c["trait_desc"], text_w) + [
                "", f"Starts with: {self._weapon_name(c['starting_weapon'])}",
            ]
            for j, line in enumerate(rows):
                if line == trait_line:
                    surf = self._trait.render(line, True, config.COLOR_ON_BUTTON)
                else:
                    surf = self._body.render(line, True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(surf, surf.get_rect(midtop=(rect.centerx, y + 66 + j * 24 + dy)))

        self._draw_preview(surface, cx, y + card_h + 12)

        # Difficulty on a ribbon whose colour is the difficulty. The ribbon is
        # a switch (one click steps it, like Down); Up / Down still work. Two
        # runs, centred as a pair: "Difficulty:" in the title face (black),
        # the type in the body face (dark grey).
        diff_y = y + card_h + 178
        run_a = self._name.render("Difficulty:  ", True, config.COLOR_ON_BUTTON)
        run_b = self._diff_type.render(config.DIFFICULTY_LABELS[self.difficulty], True,
                                       config.COLOR_ON_BUTTON_DIM)
        pair_w = run_a.get_width() + run_b.get_width()
        ribbon = pygame.Rect(0, 0, max(_RIBBON_MIN_W, pair_w + 2 * _RIBBON_END), _RIBBON_H)
        ribbon.center = (cx, diff_y)
        hits.add(ribbon, "difficulty")    # positioned first, then registered
        widgets.draw_ribbon(surface, self.game.assets, ribbon, None,
                            colour=config.DIFFICULTY_RIBBON[self.difficulty])
        text_y = diff_y + _RIBBON_TEXT_DY
        rect_a = run_a.get_rect(midleft=(cx - pair_w // 2, text_y))
        rect_b = run_b.get_rect(midleft=(rect_a.right, text_y))
        surface.blit(run_a, rect_a)
        surface.blit(run_b, rect_b)

        # Begin button, below the difficulty line (mouse twin of ENTER). Gold
        # while the cursor is over it, pressed while the button is held on
        # it; ENTER always fires it, so the keyboard adds no focus state.
        begin = pygame.Rect(0, 0, _BEGIN_W, _BEGIN_H)
        begin.center = (cx, diff_y + _BEGIN_GAP + _BEGIN_H // 2)
        hits.add(begin, "begin")          # register once it is in place (add copies)
        widgets.draw_button(surface, self.game.assets, begin, "Begin",
                            state=self._button_state("begin"), shape="wide",
                            font=self._name,
                            label_dy=widgets.LABEL_DY - _BEGIN_TEXT_DY)

        # Instructions sit under the button now; the hint under them.
        instr_bottom = self._draw_instructions(surface, cx, begin.bottom + _INSTR_GAP)

        hint = self._hint.render(
            "Left / Right hero    -    Up / Down or click difficulty    -    ENTER / Begin    -    ESC back",
            True, config.COLOR_TEXT_DIM)
        hint_rect = hint.get_rect(center=(cx, instr_bottom + 18))
        surface.blit(hint, hint_rect)

        # Back target, bottom-left (ESC's twin).
        back = self._hint.render("<  Back", True, config.COLOR_TEXT_DIM)
        back_rect = back.get_rect(bottomleft=(28, surface.get_height() - 16))
        surface.blit(back, back_rect)
        hits.add(back_rect.inflate(20, 12), "back")
        self._layout = {"diff_y": diff_y, "ribbon": pygame.Rect(ribbon),
                        "diff_runs": (pygame.Rect(rect_a), pygame.Rect(rect_b)),
                        "begin": pygame.Rect(begin),
                        "instr_top": begin.bottom + _INSTR_GAP, "instr_bottom": instr_bottom,
                        "hint_bottom": hint_rect.bottom}

    def _draw_preview(self, surface: pygame.Surface, cx: int, top: int) -> None:
        """The focused hero's looping animation preview, centred. Falls back to
        the hero's primitive colour disc if the rig / frame is unavailable."""
        cid = self.ids[self.index]
        c = self.content.characters[cid]
        cy = top + _PREVIEW_PX // 2
        dw, dh = _PREVIEW_ADJUST.get(cid, (0, 0))
        frame = None
        if self._preview is not None:
            frame = self._preview.frame(size=(_PREVIEW_W + dw, _PREVIEW_PX + dh))
        if frame is not None:
            surface.blit(frame, frame.get_rect(center=(cx, cy)))
        else:
            pygame.draw.circle(surface, tuple(c.get("color", config.COLOR_PLAYER)),
                               (cx, cy), _PREVIEW_PX // 3)

    def _draw_instructions(self, surface: pygame.Surface, cx: int, top: int) -> int:
        """The game-instructions block from `config.MENU_INSTRUCTIONS`, centred:
        the key bindings on one line, then the free notes. Returns the y of the
        last line so the caller can place the hint below it."""
        instr = config.MENU_INSTRUCTIONS
        line_h = self._instr.get_linesize()
        keys = "      ".join(f"{label}  {combo}" for label, combo in instr["rows"])
        y = top
        surf = self._instr.render(keys, True, config.COLOR_TEXT_DIM)
        surface.blit(surf, surf.get_rect(center=(cx, y)))
        for note in instr["notes"]:
            y += line_h
            surf = self._instr.render(note, True, config.COLOR_TEXT_DIM)
            surface.blit(surf, surf.get_rect(center=(cx, y)))
        return y

    def _weapon_name(self, wid: str) -> str:
        return self.content.weapons.get(wid, {}).get("name", wid)

