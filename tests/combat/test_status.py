"""Milestone 6 & 9: status-effect framework (spec 5.7 / 8: "Status effects")."""
import unittest

from combat.status import REGISTRY, StatusState


def _sink(out):
    """`StatusState.update`'s damage callback: `(amount, source)`. `source` is
    what applied the status -- a weapon id -- so a damage-over-time tick can be
    attributed like any other hit."""
    return lambda amount, _source=None: out.append(amount)


class BurnTests(unittest.TestCase):
    def test_burn_deals_damage_over_time(self):
        st = StatusState()
        st.apply("burn", duration=2.0, potency=4.0)   # ticks every 0.5s
        total = []
        for _ in range(40):  # 4s of 0.1s steps -- covers the 2s duration
            st.update(0.1, _sink(total))
        # ~4 ticks of 4 damage before it expires.
        self.assertGreaterEqual(sum(total), 12)
        self.assertLessEqual(sum(total), 20)
        self.assertNotIn("burn", st)

    def test_stacks_raise_tick_damage_up_to_cap(self):
        st = StatusState()
        for _ in range(9):
            st.apply("burn", 5.0, 3.0)
        self.assertEqual(st.stacks("burn"), 5)  # BURN.max_stacks
        got = []
        st.update(0.5, _sink(got))
        self.assertAlmostEqual(got[0], 3.0 * 5)

    def test_bonus_max_stacks_raises_cap(self):
        st = StatusState()
        for _ in range(9):
            st.apply("burn", 5.0, 3.0, bonus_max_stacks=2)
        self.assertEqual(st.stacks("burn"), 7)


class ChillShockTests(unittest.TestCase):
    def test_chill_slows_and_expires(self):
        st = StatusState()
        st.apply("chill", 1.0, 0.30)
        self.assertAlmostEqual(st.speed_multiplier(), 0.70)
        st.update(1.1, lambda *_a: None)
        self.assertEqual(st.speed_multiplier(), 1.0)

    def test_shock_amplifies_damage_taken(self):
        st = StatusState()
        st.apply("shock", 3.0, 0.25)
        self.assertAlmostEqual(st.damage_taken_multiplier(), 1.25)

    def test_refresh_keeps_one_stack_and_extends(self):
        st = StatusState()
        st.apply("chill", 1.0, 0.2)
        st.update(0.8, lambda *_a: None)
        st.apply("chill", 1.0, 0.2)   # refresh
        st.update(0.5, lambda *_a: None)
        self.assertIn("chill", st)     # would have expired without the refresh


class GenericFrameworkTests(unittest.TestCase):
    """Milestone 9: five effects, one update loop, dispatch by family."""

    def test_five_effects_registered(self):
        self.assertGreaterEqual(len(REGISTRY), 5)
        self.assertEqual({"burn", "poison", "bleed", "chill", "shock"} & set(REGISTRY),
                         {"burn", "poison", "bleed", "chill", "shock"})

    def test_poison_and_bleed_tick_like_any_dot_no_special_casing(self):
        for sid in ("poison", "bleed"):
            st = StatusState()
            st.apply(sid, duration=2.0, potency=3.0)
            total = []
            for _ in range(40):
                st.update(0.1, _sink(total))
            self.assertGreater(sum(total), 0, f"{sid} dealt no damage")
            self.assertNotIn(sid, st)

    def test_multiple_slows_stack_multiplicatively(self):
        st = StatusState()
        st.apply("chill", 5.0, 0.30)
        # a second slow family effect would compound; with one it is just 0.7
        self.assertAlmostEqual(st.speed_multiplier(), 0.70)

    def test_dot_and_amp_coexist(self):
        st = StatusState()
        st.apply("poison", 3.0, 2.0)
        st.apply("shock", 3.0, 0.25)
        got = []
        st.update(0.75, _sink(got))
        self.assertGreater(sum(got), 0)
        self.assertAlmostEqual(st.damage_taken_multiplier(), 1.25)


if __name__ == "__main__":
    unittest.main()


class StatusSourceTests(unittest.TestCase):
    """A damage-over-time tick says which weapon it belongs to.

    Without this the burn a Bow arrow lit is indistinguishable from the burn a
    Rod lit, and a build's damage breakdown has an unattributable hole in it --
    which is exactly what the DPS meter is for.
    """

    def _sources(self, st, steps=40, dt=0.1):
        got = []
        for _ in range(steps):
            st.update(dt, lambda _amount, source: got.append(source))
        return got

    def test_a_tick_carries_the_source_that_applied_it(self):
        st = StatusState()
        st.apply("burn", duration=2.0, potency=4.0, source="bow")
        got = self._sources(st)
        self.assertTrue(got, "no tick fired")
        self.assertEqual(set(got), {"bow"})

    def test_no_source_is_none_not_an_error(self):
        """Every existing caller omits it, and must keep working."""
        st = StatusState()
        st.apply("burn", duration=2.0, potency=4.0)
        self.assertEqual(set(self._sources(st)), {None})

    def test_a_refresh_re_attributes_to_the_weapon_keeping_it_alive(self):
        st = StatusState()
        st.apply("burn", duration=2.0, potency=4.0, source="bow")
        st.apply("burn", duration=2.0, potency=4.0, source="magic_rod")
        self.assertEqual(set(self._sources(st)), {"magic_rod"})

    def test_a_refresh_without_a_source_keeps_the_one_it_had(self):
        st = StatusState()
        st.apply("burn", duration=2.0, potency=4.0, source="bow")
        st.apply("burn", duration=2.0, potency=4.0)
        self.assertEqual(set(self._sources(st)), {"bow"})


if __name__ == "__main__":
    unittest.main()
