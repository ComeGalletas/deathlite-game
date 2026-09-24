"""ENT-017: behaviour templates in `data/enemies/behaviors.json`.

Pure: the real data, no world. Parity with the builders the templates
replaced was proved by golden traces (every enemy, 1500 frames, identical;
`journals/enemy_ai_journal.md`); these pin the contract that keeps it so.
"""
import copy
import unittest

from entities.ai import build_behavior, registered
from entities.ai import templates
from entities.ai.components import Charge, SeekTarget
from entities.ai.registry import code_shapes
from game.content import get_content


def _defs(table):
    return {k: v for k, v in table.items() if isinstance(v, dict)}


class TemplateCoverageTests(unittest.TestCase):
    def test_every_enemy_and_boss_behaviour_is_a_template(self):
        c = get_content()
        for kind, table in (("enemy", c.enemies), ("boss", c.bosses)):
            for eid, cfg in _defs(table).items():
                with self.subTest(**{kind: eid}):
                    self.assertIsNotNone(templates.template(cfg["behavior"]),
                                         f"{eid}: no template {cfg['behavior']!r}")

    def test_every_template_names_only_registered_things(self):
        for name in templates.names():
            with self.subTest(template=name):
                self.assertEqual(
                    templates.problems(name, templates.template(name), code_shapes()), [])

    def test_every_enemy_and_boss_builds(self):
        c = get_content()
        for table in (c.enemies, c.bosses):
            for eid, cfg in _defs(table).items():
                with self.subTest(enemy=eid):
                    build_behavior(cfg["behavior"], cfg)

    def test_registered_lists_the_templates(self):
        self.assertLessEqual(set(templates.names()), set(registered()))


class MergeTests(unittest.TestCase):
    def test_the_enemy_overrides_the_template_which_overrides_the_shared(self):
        shared = get_content().behaviors["defaults"]
        tpl = templates.template("fsm_charger")
        m = templates.merged(tpl, {"charge_speed": 999, "nav_slew": 1.0})
        self.assertEqual(m["charge_speed"], 999)                        # enemy
        self.assertEqual(m["charge_damage"], tpl["defaults"]["charge_damage"])  # template
        self.assertEqual(m["nav_slew"], 1.0)                             # enemy over shared
        self.assertEqual(m["seek_weight"], shared["seek_weight"])        # shared

    def test_an_enemys_number_reaches_the_component(self):
        cfg = {"charge_speed": 777, "charge_damage": 5}
        b = build_behavior("fsm_charger", cfg)
        dash = next(c for c in b.states["attack"] if isinstance(c, Charge))
        self.assertEqual((dash.speed, dash.damage), (777, 5))

    def test_without_an_override_the_template_number_is_used(self):
        tpl = templates.template("fsm_charger")["defaults"]
        b = build_behavior("fsm_charger", {})
        dash = next(c for c in b.states["attack"] if isinstance(c, Charge))
        self.assertEqual((dash.speed, dash.damage),
                         (tpl["charge_speed"], tpl["charge_damage"]))

    def test_comments_are_not_merged_as_numbers(self):
        m = templates.merged(templates.template("summoner"), {})
        self.assertFalse([k for k in m if k.startswith("_")])


class NoCodeFallbackTests(unittest.TestCase):
    """The builders read the data and nothing else: a number removed from
    the data is an error, not a silent default."""

    def test_a_template_number_removed_from_the_data_is_missed(self):
        data = get_content().behaviors
        saved = copy.deepcopy(data)
        try:
            del data["behaviors"]["fsm_charger"]["defaults"]["charge_speed"]
            with self.assertRaises(KeyError):
                build_behavior("fsm_charger", {})
        finally:
            data.clear()
            data.update(saved)

    def test_a_shared_number_removed_from_the_data_is_missed(self):
        data = get_content().behaviors
        saved = copy.deepcopy(data)
        try:
            del data["defaults"]["nav_slew"]
            with self.assertRaises(KeyError):
                build_behavior("path_chase", {"radius": 10})
        finally:
            data.clear()
            data.update(saved)


class ShapeTests(unittest.TestCase):
    def test_a_move_template_is_one_state_of_its_stacks(self):
        b = build_behavior("chase", {})
        self.assertEqual(list(b.states), ["move"])
        (seek,) = b.states["move"]
        self.assertIsInstance(seek, SeekTarget)
        self.assertEqual(seek.via, "straight")

    def test_the_dummy_names_its_single_state(self):
        self.assertEqual(list(build_behavior("dummy", {}).states), ["idle"])

    def test_a_cycle_template_has_the_four_states(self):
        b = build_behavior("fsm_warlock", {})
        self.assertLessEqual({"chase", "telegraph", "attack", "recover"}, set(b.states))


if __name__ == "__main__":
    unittest.main()
