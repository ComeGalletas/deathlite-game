"""`game/states/victory_state.py`: the run résumé shown after the boss dies.

The screen was a stub -- nine centred lines, keyboard only -- while the
game-over screen it shares a stats dict with had grown a full résumé, buttons
and mouse support. What is pinned here is that it now draws the same frame and
answers the same input, so the two cannot drift apart again unnoticed.

A fake game rather than a booted one, as in `test_game_over.py`: the state only
needs somewhere to record the transition.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.states.character_select_state import CharacterSelectState
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState
from game.states.victory_state import BACKDROP, VictoryState
from ui import end_screen, run_summary

LEDGER_STATS = {
    "character": "Aegis", "difficulty": "fast", "seed": 35,
    "time": 612.4, "level": 21, "kills": 734, "gold": 1180, "currency": 265,
    "damage_dealt": 486_200.0, "potions": 9, "potion_healing": 640.0,
    "weapons": [("Sword", 6), ("Bow", 4)],
    "blessings": {"sword_keen_edge": 3},
    "dropped_items": [{"name": "Ashen Signet", "rarity": "rare"}],
    "weapon_rows": [
        {"name": "Sword", "level": 6, "damage": 212_400.0, "share": 0.44, "dps": 402.1},
        {"name": "Bow", "level": 4, "damage": 158_900.0, "share": 0.33, "dps": 301.0},
    ],
    "other_rows": [{"name": "Keen Edge", "damage": 28_400.0, "share": 0.06, "dps": 53.8}],
    "kill_rows": [("Skull", 210), ("Spider", 164), ("The Tusked Lance", 1)],
    "blessing_rows": [("Keen Edge", 3)],
}


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


class _Recorder:
    def __init__(self):
        self.changed_to = None

    def change(self, state, **kwargs):
        self.changed_to = state


def _state(stats=None):
    s = VictoryState(SimpleNamespace(state_machine=_Recorder()))
    s.enter(stats=stats)
    return s


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()


class ExitTests(_Base):
    def _pressed(self, key, stats=None):
        s = _state(stats)
        s.handle_event(_key(key))
        return s.game.state_machine.changed_to

    def test_enter_starts_another_run(self):
        self.assertIsInstance(self._pressed(pygame.K_RETURN), CharacterSelectState)

    def test_space_starts_another_run(self):
        self.assertIsInstance(self._pressed(pygame.K_SPACE), CharacterSelectState)

    def test_s_opens_the_sanctuary(self):
        self.assertIsInstance(self._pressed(pygame.K_s), MetaState)

    def test_escape_goes_back_to_the_menu(self):
        self.assertIsInstance(self._pressed(pygame.K_ESCAPE), MenuState)

    def test_any_other_key_stays_on_the_summary(self):
        self.assertIsNone(self._pressed(pygame.K_f))

    def test_a_key_release_is_not_a_press(self):
        s = _state()
        s.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN))
        self.assertIsNone(s.game.state_machine.changed_to)

    def test_the_cursor_moves_and_confirms(self):
        s = _state()
        s.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(s.sel, 1)
        s.handle_event(_key(pygame.K_RETURN))
        self.assertIsInstance(s.game.state_machine.changed_to, MetaState)


class MouseTests(_Base):
    """The screen had no mouse targets at all before this."""

    def _ready(self):
        s = _state(LEDGER_STATS)
        s.draw(pygame.Surface((1600, 900)))
        return s

    def _click(self, s, i):
        pos = s._mouse.hits.rect_of(i).center
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        return s.game.state_machine.changed_to

    def test_three_buttons_are_registered(self):
        s = self._ready()
        self.assertEqual(len(s._mouse.hits), 3)

    def test_hover_selects(self):
        s = self._ready()
        pos = s._mouse.hits.rect_of(2).center
        s.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        self.assertEqual(s.sel, 2)
        self.assertIsNone(s.game.state_machine.changed_to)

    def test_clicking_new_run(self):
        self.assertIsInstance(self._click(self._ready(), 0), CharacterSelectState)

    def test_clicking_sanctuary(self):
        self.assertIsInstance(self._click(self._ready(), 1), MetaState)

    def test_clicking_main_menu(self):
        self.assertIsInstance(self._click(self._ready(), 2), MenuState)


class SummaryTests(_Base):
    """The résumé the screen used to throw away."""

    def _drawn(self, stats):
        s = _state(stats)
        surface = pygame.Surface((1600, 900))
        s.draw(surface)
        return s, surface

    def _lit(self, surface, rect):
        return sum(1 for y in range(rect.top, rect.bottom, 3)
                   for x in range(rect.left, rect.right, 3)
                   if surface.get_at((x, y))[:3] != BACKDROP)

    def test_all_three_columns_are_drawn(self):
        _s, surface = self._drawn(LEDGER_STATS)
        band_h = end_screen.PANEL_BOTTOM - end_screen.PANEL_TOP
        for i in range(3):
            col = pygame.Rect(60 + i * 500, end_screen.PANEL_TOP, 460, band_h)
            self.assertGreater(self._lit(surface, col), 200,
                               f"column {i} is empty")

    def test_no_stats_at_all_still_draws(self):
        _s, surface = self._drawn(None)
        self.assertGreater(self._lit(surface, pygame.Rect(0, 0, 1600, 900)), 0)

    def test_the_stats_are_kept_as_given(self):
        s = _state(LEDGER_STATS)
        self.assertEqual(s.stats, LEDGER_STATS)

    def test_the_title_and_the_subtitle_are_drawn(self):
        _s, surface = self._drawn(LEDGER_STATS)
        self.assertGreater(self._lit(surface, pygame.Rect(600, 40, 400, 60)), 0)
        self.assertGreater(self._lit(surface, pygame.Rect(500, 104, 600, 32)), 0)



def _drawn_text(stats, columns=None):
    """Every label and line the panel renders, by spying on its two text
    primitives -- what the column *says*, with no geometry involved."""
    panel = run_summary.RunSummaryPanel(stats)
    seen = []
    real_kv, real_line = panel._kv, panel._line

    def kv(surface, area, y, label, value, **kw):
        seen.extend((str(label), str(value)))
        if kw.get("flag"):
            seen.append(f"{label}:{kw['flag']}")
        return real_kv(surface, area, y, label, value, **kw)

    def line(surface, area, y, text, **kw):
        seen.append(str(text))
        return real_line(surface, area, y, text, **kw)

    panel._kv, panel._line = kv, line
    panel.draw(pygame.Surface((1600, 900)), None,
               end_screen.PANEL_TOP, end_screen.PANEL_BOTTOM,
               columns=columns or run_summary.VICTORY_COLUMNS)
    return seen



def _ribbon_colours(columns):
    """The ribbon colour each column asks `_column` for, in order."""
    panel = run_summary.RunSummaryPanel(dict(LEDGER_STATS))
    seen = []
    real = panel._column

    def spy(surface, assets, rect, title, colour):
        seen.append(colour)
        return real(surface, assets, rect, title, colour)

    panel._column = spy
    panel.draw(pygame.Surface((1600, 900)), None,
               end_screen.PANEL_TOP, end_screen.PANEL_BOTTOM, columns=columns)
    return seen


class ColumnWidthTests(unittest.TestCase):
    """`run_summary.column_widths`: the rule that lets a fourth column exist.

    Pure arithmetic, so it is asserted directly rather than inferred from
    pixels -- the failure it guards against (a weapon's name printed through
    its own damage figure) is invisible to a "did anything draw" check.
    """

    def test_no_minimum_means_an_even_split(self):
        self.assertEqual(run_summary.column_widths(300, [0, 0, 0]), [100, 100, 100])

    def test_the_row_always_ends_flush(self):
        for space in (299, 300, 301, 1420, 1421):
            for mins in ([0, 0, 0], [0, 0, 498, 0], [498, 0]):
                self.assertEqual(sum(run_summary.column_widths(space, mins)), space,
                                 f"{space} px over {mins} did not add up")

    def test_a_column_over_the_equal_share_takes_its_minimum(self):
        widths = run_summary.column_widths(1420, [0, 0, 498, 0])
        self.assertEqual(widths[2], 498)
        others = [widths[0], widths[1], widths[3]]
        # Even but for the rounding the last column absorbs.
        self.assertLessEqual(max(others) - min(others), 1)

    def test_a_minimum_under_the_equal_share_is_ignored(self):
        self.assertEqual(run_summary.column_widths(1420, [0, 0, 100]),
                         run_summary.column_widths(1420, [0, 0, 0]))

    def test_the_weapons_minimum_applies_at_three_columns_as_well(self):
        """Not a four-column-only rule.

        The three-column equal share is 480 px, which leaves 424 px of content
        for a weapon row that can want 430 -- so the game-over screen could
        already print a long weapon name through a seven-figure damage. The
        minimum widens that column rather than leaving the overlap latent.
        """
        space = 1600 - 2 * 60 - 2 * 20
        self.assertLess(space // 3, 498, "the premise of this test has moved")
        self.assertEqual(run_summary.column_widths(space, [0, 0, 498])[2], 498)

    def test_the_shipped_victory_set_clears_the_weapons_minimum(self):
        mins = [m for _d, m in
                (run_summary._COLUMNS[c] for c in run_summary.VICTORY_COLUMNS)]
        space = 1600 - 2 * 60 - (len(mins) - 1) * 20
        widths = run_summary.column_widths(space, mins)
        for want, got in zip(mins, widths, strict=True):
            self.assertGreaterEqual(got, want)


class HeroColumnTests(_Base):
    """The fourth column, and the victory-only facts in it."""

    def _hero_area(self, stats):
        surface = pygame.Surface((1600, 900))
        _state(stats).draw(surface)
        # The rightmost column, inside its padding.
        return surface, pygame.Rect(1240, end_screen.PANEL_TOP + 40, 300, 420)

    def _lit(self, surface, rect):
        return sum(1 for y in range(rect.top, rect.bottom, 2)
                   for x in range(rect.left, rect.right, 2)
                   if surface.get_at((x, y))[:3] != BACKDROP)

    def test_victory_draws_four_columns_and_game_over_draws_three(self):
        self.assertEqual(len(run_summary.VICTORY_COLUMNS), 4)
        self.assertEqual(len(run_summary.COLUMNS), 3)
        self.assertEqual(run_summary.VICTORY_COLUMNS[:3], run_summary.COLUMNS)

    def test_the_hero_column_paints(self):
        surface, area = self._hero_area(LEDGER_STATS)
        self.assertGreater(self._lit(surface, area), 200)

    def test_the_unlock_line_only_shows_on_a_first_clear(self):
        """Asserted on the text, not on lit pixels: the stat list shrinks to
        fit whatever room is left, so the column paints the same amount either
        way and a pixel count cannot tell the two apart."""
        for first_clear, expected in ((True, True), (False, False)):
            drawn = _drawn_text({**LEDGER_STATS, "first_clear": first_clear})
            self.assertEqual(any("unlocked" in t for t in drawn), expected,
                             f"first_clear={first_clear} drew the wrong lines")

    def test_a_win_says_cleared_in_and_a_death_says_survived(self):
        for victory, want in ((True, "Cleared in"), (False, "Survived")):
            self.assertIn(want, _drawn_text({**LEDGER_STATS, "victory": victory}))

    def test_a_summary_with_no_hero_block_still_draws_the_column(self):
        bare = {k: v for k, v in LEDGER_STATS.items()
                if k not in ("hero_stats", "equipment", "trait")}
        surface, area = self._hero_area(bare)
        self.assertGreater(self._lit(surface, area), 0)


class GoldTests(_Base):
    """Gold is reported gross, and salvage is not reported at all."""

    def test_the_run_column_shows_the_total_earned_not_the_balance(self):
        drawn = _drawn_text({**LEDGER_STATS, "gold": 150, "gold_earned": 200})
        self.assertIn("Gold earned", drawn)
        self.assertIn("200", drawn)
        self.assertNotIn("150", drawn, "the leftover balance is on the screen")

    def test_an_older_summary_falls_back_to_the_balance(self):
        # Written before the run kept a total: the balance is an undercount but
        # it is the best answer available, and must not read as zero.
        older = {k: v for k, v in LEDGER_STATS.items() if k != "gold_earned"}
        drawn = _drawn_text({**older, "gold": 1180})
        self.assertIn("1180", drawn)

    def test_salvage_is_not_shown(self):
        drawn = _drawn_text({**LEDGER_STATS, "currency": 265})
        self.assertFalse([t for t in drawn if "alvage" in t],
                         "the salvage row printed the raw currency, which is "
                         "not what Game._on_run_ended actually banks")


class PaletteTests(unittest.TestCase):
    """Step 5: the same ribbons, everything else saying 'win'."""

    def test_the_backdrop_is_warmer_than_the_game_over_screens(self):
        from game.states.game_over_state import BACKDROP as DEATH
        self.assertNotEqual(BACKDROP, DEATH)
        # Warm: more red+green than blue, and brighter overall than defeat.
        self.assertGreater(BACKDROP[0], BACKDROP[2])
        self.assertGreater(sum(BACKDROP), sum(DEATH))

    def test_no_button_leads_a_win_with_the_danger_art(self):
        from game.states.game_over_state import BUTTONS as DEATH_BUTTONS
        from game.states.victory_state import BUTTONS
        self.assertEqual([b.variant for b in BUTTONS], ["primary"] * len(BUTTONS))
        # The game-over screen keeps its red Main menu, so this is a real
        # difference rather than a shared change.
        self.assertIn("danger", [b.variant for b in DEATH_BUTTONS])

    def test_the_two_screens_offer_the_same_destinations(self):
        from game.states.game_over_state import BUTTONS as DEATH_BUTTONS
        from game.states.victory_state import BUTTONS
        self.assertEqual([b.bid for b in BUTTONS],
                         [b.bid for b in DEATH_BUTTONS])

    def test_the_ribbon_colours_are_reused_not_recoloured(self):
        """The owner asked for the same ribbons and a different everything
        else, so the columns must not have grown a victory palette of their
        own -- asserted on the colours the panel actually asks for."""
        self.assertEqual(_ribbon_colours(run_summary.COLUMNS),
                         _ribbon_colours(run_summary.VICTORY_COLUMNS)[:3])
        self.assertTrue(all(_ribbon_colours(run_summary.VICTORY_COLUMNS)))


class RecordMarkerTests(_Base):
    """Step 6: rows that set a record for the difficulty carry a marker."""

    def test_a_record_row_is_marked_and_the_others_are_not(self):
        drawn = _drawn_text({**LEDGER_STATS, "new_records": ["kills"]})
        self.assertIn(f"Kills:{run_summary.BEST_FLAG}", drawn)
        self.assertNotIn(f"Level:{run_summary.BEST_FLAG}", drawn)

    def test_the_clock_row_is_marked_under_whichever_label_it_wears(self):
        for victory, label in ((True, "Cleared in"), (False, "Survived")):
            drawn = _drawn_text({**LEDGER_STATS, "victory": victory,
                                 "new_records": ["time"]})
            self.assertIn(f"{label}:{run_summary.BEST_FLAG}", drawn)

    def test_a_run_that_broke_nothing_is_marked_nowhere(self):
        drawn = _drawn_text({**LEDGER_STATS, "new_records": []})
        self.assertFalse([t for t in drawn if t.endswith(run_summary.BEST_FLAG)])

    def test_a_summary_with_no_record_list_draws_no_markers(self):
        older = {k: v for k, v in LEDGER_STATS.items() if k != "new_records"}
        drawn = _drawn_text(older)
        self.assertFalse([t for t in drawn if t.endswith(run_summary.BEST_FLAG)])


if __name__ == "__main__":
    unittest.main()
