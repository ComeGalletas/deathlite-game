"""`game/states/run_status_state.py` and `ui/run_status/`: the in-run build
screen opened with TAB.

A fake game and a hand-built run rather than a booted one, as the game-over
tests do: the screen reads a `player` (a real `Player` with real `Weapon`s
and blessings from the catalog), the run `stats`, the `levels`, the content
and the catalog -- all of which stand up without a world. What is pinned:

* every pane draws with a full build and with an empty one, inside the panel;
* the pure readouts the panes print: a weapon's `base -> now` numbers, the
  synergy pairs, an item's bonus lines;
* the keys: TAB and ESC pop, Left / Right and 1-3 switch panes, Up / Down
  and the wheel move the blessing selection and clamp;
* the mouse: a ribbon click switches panes, a row click selects a blessing;
* the pause menu's "Run status" row pushes the screen, and it finds the run
  under the pause overlay.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import Weapon
from combat.weapons.forge import apply_forge, get_forges
from entities.player import Player
from game.content import get_content
from game.states.run_status_state import PANES, RunStatusState, find_playing
from progression.blessings import apply_blessing
from progression.blessings.catalog import get_catalog
from progression.items import generate_item
from ui.run_status.build import synergy_rows, weapon_numbers
from ui.run_status.overview import item_lines


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


class _Machine:
    """Records pushes and pops; holds a stack for `find_playing`."""

    def __init__(self, stack=()):
        self._stack = list(stack)
        self.pushed = []
        self.popped = 0

    def push(self, state, **kwargs):
        self.pushed.append((state, kwargs))

    def pop(self):
        self.popped += 1


def _run(*, full: bool):
    """A hand-built run: the pieces the screen reads."""
    content = get_content()
    cdef = content.character("aegis")
    player = Player(0, 0, base_stats=cdef.get("base_stats"), trait=cdef.get("trait", ""),
                    character_id="aegis")
    catalog = get_catalog(content)
    if full:
        for wid in ("sword", "daggers", "bow", "spirit_wolf"):
            player.weapons.append(Weapon(wid, dict(content.weapon(wid))))
        for bid in ("vitality", "vitality", "sword_critical_edge",
                    "daggers_blood_in_the_water", "fleet_foot"):
            apply_blessing(player, catalog.by_id[bid])
        apply_forge(player.weapons[0], get_forges(content).get("whirlwind"))
        player.equipment = [generate_item(content, seed=4242, item_level=3, luck=1.0)]
        player.recompute()
    return SimpleNamespace(
        player=player, content=content, catalog=catalog, character_id="aegis",
        difficulty="normal", run_seed=7,
        stats={"time": 125.0, "level": 4, "kills": 31, "gold": 12, "currency": 0,
               "damage_dealt": 900.0, "dropped_items": []},
        levels=SimpleNamespace(level=4, progress_fraction=0.4))


def _state(ps, stack=()):
    game = SimpleNamespace(state_machine=_Machine(stack))
    s = RunStatusState(game)
    s.enter(playing=ps)
    return s


BACKDROP = (7, 9, 11)


def _drawn(s, size=(1600, 900)):
    surface = pygame.Surface(size)
    surface.fill(BACKDROP)
    s.draw(surface)
    return surface


def _lit(surface, rect):
    return sum(1 for x in range(rect.left, rect.right, 6)
               for y in range(rect.top, rect.bottom, 6)
               if surface.get_at((x, y))[:3] not in (BACKDROP, (0, 0, 0)))


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def test_every_pane_draws_a_full_build(self):
        s = _state(_run(full=True))
        for i in range(len(PANES)):
            s.tab = i
            with self.subTest(pane=PANES[i]):
                surface = _drawn(s)
                self.assertGreater(_lit(surface, pygame.Rect(100, 160, 1400, 600)), 200)

    def test_every_pane_draws_an_empty_build(self):
        s = _state(_run(full=False))
        for i in range(len(PANES)):
            s.tab = i
            with self.subTest(pane=PANES[i]):
                surface = _drawn(s)
                self.assertGreater(_lit(surface, pygame.Rect(100, 160, 1400, 600)), 30)

    def test_the_web_profile_size_draws_every_pane(self):
        s = _state(_run(full=True))
        for i in range(len(PANES)):
            s.tab = i
            _drawn(s, (1280, 720))

    def test_no_run_draws_a_placeholder(self):
        game = SimpleNamespace(state_machine=_Machine())
        s = RunStatusState(game)
        s.enter()                       # nothing on the stack to find
        self.assertIsNone(s.playing)
        _drawn(s)


class ReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ps = _run(full=True)

    def test_weapon_numbers_show_base_and_now_when_a_blessing_changed_them(self):
        sword = self.ps.player.weapons[0]
        rows = dict((label, (base, now)) for label, base, now in weapon_numbers(sword))
        self.assertIn("Damage", rows)
        self.assertIsNone(rows["Damage"][1], "no damage blessing was taken")
        # Critical Edge adds crit chance -> its own row.
        self.assertIn("Crit chance", rows)

    def test_weapon_numbers_report_a_changed_value(self):
        bow = Weapon("bow", dict(self.ps.content.weapon("bow")))
        bow.bonus["damage"] += 4.0
        rows = dict((label, (base, now)) for label, base, now in weapon_numbers(bow))
        base, now = rows["Damage"]
        self.assertIsNotNone(now)
        self.assertNotEqual(base, now)

    def test_synergy_rows_pair_the_weapons(self):
        names = {wid: d["name"] for wid, d in self.ps.content.weapons.items()}
        rows = synergy_rows(self.ps.player, self.ps.catalog, names)
        self.assertEqual(len(rows), 1)
        head, text = rows[0]
        self.assertIn("Daggers", head)
        self.assertIn("Sword", head)
        self.assertIn("Blood in the Water I", head)
        self.assertIn("1.5", text)

    def test_item_lines_state_the_base_and_every_affix(self):
        item = self.ps.player.equipment[0]
        lines = item_lines(item, self.ps.content)
        self.assertEqual(len(lines), 1 + len(item.affixes) + (1 if item.unique_effect else 0))
        self.assertTrue(lines[0].startswith(("+", "-", "x")), lines[0])

    def test_item_values_are_rounded_to_one_decimal(self):
        item = SimpleNamespace(base_stat="armor", base_op="flat", base_value=3.917,
                               affixes=[], unique_effect=None)
        self.assertEqual(item_lines(item), ["+3.9 Armor"])
        whole = SimpleNamespace(base_stat="max_hp", base_op="flat", base_value=20.0,
                                affixes=[], unique_effect=None)
        self.assertEqual(item_lines(whole), ["+20 Max HP"])


class KeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def test_tab_and_escape_close(self):
        for k in (pygame.K_TAB, pygame.K_ESCAPE):
            s = _state(_run(full=False))
            s.handle_event(_key(k))
            self.assertEqual(s.game.state_machine.popped, 1)

    def test_left_right_and_digits_switch_panes(self):
        s = _state(_run(full=False))
        s.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(s.tab, 1)
        s.handle_event(_key(pygame.K_LEFT))
        s.handle_event(_key(pygame.K_LEFT))
        self.assertEqual(s.tab, 2)
        s.handle_event(_key(pygame.K_1))
        self.assertEqual(s.tab, 0)
        s.handle_event(_key(pygame.K_3))
        self.assertEqual(s.tab, 2)

    def test_up_down_and_wheel_move_the_blessing_selection_and_clamp(self):
        s = _state(_run(full=True))
        s.tab = 2
        _drawn(s)                       # the pane learns its row count
        pane = s.pane
        self.assertEqual(pane.sel, 0)
        s.handle_event(_key(pygame.K_DOWN))
        self.assertEqual(pane.sel, 1)
        s.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
        self.assertEqual(pane.sel, 2)
        for _ in range(20):
            s.handle_event(_key(pygame.K_s))
        self.assertEqual(pane.sel, pane._count - 1)
        for _ in range(40):
            s.handle_event(_key(pygame.K_UP))
        self.assertEqual(pane.sel, 0)

    def test_up_down_select_a_weapon_card_on_the_build_pane(self):
        s = _state(_run(full=True))
        s.tab = 1
        _drawn(s)
        pane = s.pane
        self.assertEqual(pane.sel, 0)
        s.handle_event(_key(pygame.K_DOWN))
        s.handle_event(_key(pygame.K_DOWN))
        self.assertEqual(pane.sel, 2)
        for _ in range(10):
            s.handle_event(_key(pygame.K_DOWN))
        self.assertEqual(pane.sel, 3, "four weapons: the selection clamps at the last card")
        _drawn(s)                       # the selected card's Forging strip draws

    def test_other_keys_do_nothing(self):
        s = _state(_run(full=False))
        s.handle_event(_key(pygame.K_f))
        s.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_TAB))
        self.assertEqual(s.game.state_machine.popped, 0)
        self.assertEqual(s.tab, 0)


class MouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def _click(self, s, pos):
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))

    def test_clicking_a_ribbon_switches_panes(self):
        s = _state(_run(full=True))
        _drawn(s)
        rect = s._mouse.hits.rect_of(("tab", 2))
        self.assertIsNotNone(rect)
        self._click(s, rect.center)
        self.assertEqual(s.tab, 2)

    def test_clicking_a_weapon_card_selects_it(self):
        s = _state(_run(full=True))
        s.tab = 1
        _drawn(s)
        rect = s._mouse.hits.rect_of(("row", 3))
        self.assertIsNotNone(rect)
        self._click(s, rect.center)
        self.assertEqual(s.pane.sel, 3)

    def test_clicking_a_blessing_row_selects_it(self):
        s = _state(_run(full=True))
        s.tab = 2
        _drawn(s)
        rect = s._mouse.hits.rect_of(("row", 2))
        self.assertIsNotNone(rect)
        self._click(s, rect.center)
        self.assertEqual(s.pane.sel, 2)


class EntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def test_find_playing_looks_under_the_overlays(self):
        ps = _run(full=False)
        machine = _Machine(stack=[ps, SimpleNamespace(name="paused")])
        self.assertIs(find_playing(machine), ps)
        self.assertIsNone(find_playing(_Machine()))

    def test_the_pause_menu_row_pushes_the_screen(self):
        from game.states.paused_state import PausedState, _ROWS
        ps = _run(full=False)
        game = SimpleNamespace(state_machine=_Machine(stack=[ps]), assets=None)
        pause = PausedState(game)
        pause.enter()
        pause.sel = _ROWS.index("status")
        pause._activate()
        pushed = game.state_machine.pushed
        self.assertEqual(len(pushed), 1)
        self.assertIsInstance(pushed[0][0], RunStatusState)


if __name__ == "__main__":
    unittest.main()
