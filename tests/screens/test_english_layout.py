"""English, where every text lands: the TAB panes, the run summary (three
and four columns, and an empty one) and the Sanctuary's upgrade panel, at
1600x900 (UI-014.9).

Moving the screens' text into the locale files was meant to leave English
exactly as it was drawn. `english_layout.json` pins each drawn text with its
rect, captured from the code before the move (UI-014.8's tree); this test
draws the same states and compares. It catches a changed word, a value read
from the wrong stat, a moved row or a changed layout constant -- where the
text is, not how its pixels are antialiased. The widths come from the
bundled faces through pygame's FreeType, and the Sanctuary's from the
system's Consolas (`fonts.mono`), so a new pygame or another machine's fonts
can move them: re-pin with --write after checking the change is the fonts'.

The rows D18/D19 changed on purpose are not in the fixture: the Sanctuary's
equipped-slot lines are left out. A sanctioned change to these screens
re-pins the fixture:

    python -m tests.screens.test_english_layout --write
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ElementId
from game import fonts, locale
from game.content import get_content
from progression.items import generate_item

FIXTURE = Path(__file__).with_name("english_layout.json")
SIZE = (1600, 900)


def capture() -> list[list]:
    """`[screen, text, x, y, w, h]` for every text drawn, in English."""
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()
    locale.set_language("en")
    texts, keep, rows = {}, [], []

    class Tag:
        def __init__(self, font):
            self.font = font

        def render(self, text, *a, **k):
            out = self.font.render(text, *a, **k)
            texts[id(out)] = str(text)
            keep.append(out)                      # alive, so no id is reused
            return out

        def __getattr__(self, name):
            return getattr(self.font, name)

    def surface_for(screen):
        class Surface(pygame.Surface):
            def blit(self, src, dest, *a, **k):
                if id(src) in texts:
                    r = (pygame.Rect(dest) if isinstance(dest, pygame.Rect)
                         else pygame.Rect(dest, src.get_size()))
                    rows.append([screen, texts[id(src)], r.x, r.y, r.w, r.h])
                return super().blit(src, dest, *a, **k)
        return Surface(SIZE)

    real_load = fonts._load
    with mock.patch.object(fonts, "_load", lambda *a, **k: Tag(real_load(*a, **k))):
        from game.states.run_status_state import PANES
        from tests.screens.test_run_status import _run, _state
        ps = _run(full=True)
        ps.player.weapons[2].element = ElementId.FIRE
        ps.stats.update(potions=3, potion_healing=41.6, currency=25)
        s = _state(ps)
        for i, pane in enumerate(PANES):
            s.tab = i
            s.draw(surface_for(f"tab_{pane}"))
        s = _state(_run(full=False))
        for i, pane in enumerate(PANES):
            s.tab = i
            s.draw(surface_for(f"tab_empty_{pane}"))

        from ui.run_summary import COLUMNS, VICTORY_COLUMNS, RunSummaryPanel
        C = get_content()
        items = [generate_item(C, seed=n, item_level=5).to_dict() for n in range(3)]
        stats = {
            "time": 412.0, "level": 9, "kills": 57, "gold_earned": 120, "potions": 2,
            "potion_healing": 30.4, "chests": 1, "unlocked_elements": ["fire", "wind"],
            "dropped_items": items, "new_records": ["time", "damage_dealt"],
            "kill_rows": [("Skitter", 50), ("Imp", 7)],
            "weapon_rows": [{"name": "Sword", "level": 5, "damage": 900.0, "share": 0.98,
                             "dps": 2.2}],
            "other_rows": [{"name": "Burn", "damage": 20.0, "share": 0.02, "dps": 0.1}],
            "damage_dealt": 920.0, "blessing_rows": [("Vitality", 2)],
            "character": "Aegis", "trait_name": "Bulwark",
            "hero_stats": {"max_hp": 160.0, "crit_chance": 0.1}, "equipment": items[:1],
            "first_clear": True, "victory": True}
        for name, cols, st in (("summary_four", VICTORY_COLUMNS, stats),
                               ("summary_three", COLUMNS, dict(stats, victory=False)),
                               ("summary_empty", COLUMNS, {"time": 30.0})):
            RunSummaryPanel(st).draw(surface_for(name), None, 178, 762, columns=cols)

        from game.game import Game
        from game.states.meta_state import MetaState
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        locale.set_language("en")
        game.save.currency = 55
        game.save.meta = {"constitution": 10, "fortune": 2}
        m = MetaState(game)
        m.enter()
        before = len(rows)
        m.draw(surface_for("sanctuary"))
        # The stash panel's slot lines changed on purpose (UI-014.D19).
        rows[before:] = [r for r in rows[before:] if r[2] < 800]
    return rows


class EnglishLayoutTests(unittest.TestCase):
    def test_english_lands_where_it_did(self):
        want = json.loads(FIXTURE.read_text(encoding="utf-8"))
        got = capture()
        self.assertGreater(len(want), 300)
        missing = [r for r in want if r not in got]
        extra = [r for r in got if r not in want]
        self.assertEqual((missing[:10], extra[:10]), ([], []))
        self.assertEqual(got, want)                         # and in the same order


if __name__ == "__main__":
    if "--write" in sys.argv:
        rows = capture()
        FIXTURE.write_text("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                           + "\n]\n", encoding="utf-8", newline="\n")
        print(f"{len(rows)} rows written to {FIXTURE}")
    else:
        unittest.main()
