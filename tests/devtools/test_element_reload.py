"""CMB-009.3: F9 re-reads the element data into a live developer run.

Pure: a real `ElementRegistry` on a stand-in run, and the files handed in
through the loader hook, so no data file is ever written. The numbers
changed are read from the shipped data and moved relative to it, never
restated.
"""
import copy
import unittest
from types import SimpleNamespace

from combat.elements.ids import ElementId
from combat.elements.registry import ElementRegistry
from game import config
from game.content import get_content
from game.states.playing.devtools.dev_flags import DevFlags
from game.states.playing.devtools.element_reload import (
    ELEMENTS_FILE, REACTIONS_FILE, reload_element_data)

FIRE = ElementId.FIRE


def _run(dev_mode=True):
    c = get_content()
    content = SimpleNamespace(elements=copy.deepcopy(c.elements),
                              reactions=copy.deepcopy(c.reactions))
    registry = ElementRegistry(content.elements, content.reactions)
    notices = []
    return SimpleNamespace(
        elements=SimpleNamespace(registry=registry), content=content,
        dev_mode=dev_mode, notices=notices,
        notice=lambda text, seconds=2.5: notices.append((text, seconds)))


def _loader(elements, reactions):
    files = {ELEMENTS_FILE: elements, REACTIONS_FILE: reactions}
    return lambda name: copy.deepcopy(files[name])


def _edited(**changes):
    """The shipped files with `changes` applied: `fire_aura` moves Fire's
    aura duration, `cap` the reactions-per-frame cap, by the given delta."""
    c = get_content()
    elements, reactions = copy.deepcopy(c.elements), copy.deepcopy(c.reactions)
    if "fire_aura" in changes:
        elements["elements"]["fire"]["aura"]["duration"] += changes["fire_aura"]
    if "cap" in changes:
        elements["global"]["max_reactions_per_frame"] += changes["cap"]
    return elements, reactions


class ReloadTests(unittest.TestCase):
    def test_a_changed_value_reaches_the_live_registry(self):
        run = _run()
        before = run.elements.registry.config(FIRE).aura.duration
        cap = run.elements.registry.global_cfg.max_reactions_per_frame
        ok, _msg = reload_element_data(run, _loader(*_edited(fire_aura=1.5, cap=2)))
        self.assertTrue(ok)
        self.assertAlmostEqual(run.elements.registry.config(FIRE).aura.duration,
                               before + 1.5)
        self.assertEqual(run.elements.registry.global_cfg.max_reactions_per_frame,
                         cap + 2)

    def test_the_runs_content_follows(self):
        run = _run()
        elements, reactions = _edited(fire_aura=1.5)
        reload_element_data(run, _loader(elements, reactions))
        self.assertEqual(run.content.elements, elements)

    def test_the_runs_modifiers_survive_and_apply_to_the_new_data(self):
        """A buff or blessing the run holds is not the data's to undo."""
        run = _run()
        base = run.elements.registry.config(FIRE).aura.duration
        run.elements.registry.modifiers(FIRE).add("aura.duration", source="test",
                                                  flat=2.0)
        reload_element_data(run, _loader(*_edited(fire_aura=1.0)))
        self.assertAlmostEqual(run.elements.registry.config(FIRE).aura.duration,
                               base + 1.0 + 2.0)

    def test_bad_data_keeps_the_old_values(self):
        run = _run()
        before = run.elements.registry.config(FIRE).aura.duration
        before_content = copy.deepcopy(run.content.elements)
        elements, reactions = _edited(fire_aura=1.0)
        del elements["global"]                       # fails validation
        ok, message = reload_element_data(run, _loader(elements, reactions))
        self.assertFalse(ok)
        self.assertIn("failed", message)
        self.assertEqual(run.elements.registry.config(FIRE).aura.duration, before)
        self.assertEqual(run.content.elements, before_content)

    def test_an_unreadable_file_keeps_the_old_values(self):
        from game.content import ContentError

        def broken(name):
            raise ContentError(f"invalid JSON in {name}")

        run = _run()
        before = run.elements.registry.config(FIRE).aura.duration
        ok, _msg = reload_element_data(run, broken)
        self.assertFalse(ok)
        self.assertEqual(run.elements.registry.config(FIRE).aura.duration, before)


class F9Tests(unittest.TestCase):
    KEY = config.DEBUG_KEYS["reload_elements"]

    def test_f9_is_its_own_key(self):
        others = [v for k, v in config.DEBUG_KEYS.items() if k != "reload_elements"]
        self.assertNotIn(self.KEY, others)

    def test_f9_reloads_in_a_developer_run_and_says_so(self):
        run = _run(dev_mode=True)
        self.assertTrue(DevFlags().handle_debug_key(SimpleNamespace(run=run), self.KEY))
        self.assertEqual(len(run.notices), 1)
        self.assertIn("reloaded", run.notices[0][0])

    def test_f9_does_nothing_outside_a_developer_run(self):
        run = _run(dev_mode=False)
        self.assertFalse(DevFlags().handle_debug_key(SimpleNamespace(run=run), self.KEY))
        self.assertEqual(run.notices, [])


if __name__ == "__main__":
    unittest.main()
