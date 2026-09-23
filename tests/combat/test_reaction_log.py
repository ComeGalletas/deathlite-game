"""CMB-009.4: the reaction log the dev overlay reads.

Unit tier: the real resolver and registry over hand-built enemies and a
recording world, with a stand-in reaction runner so what each reaction
deals is chosen here. No run and no Game.
"""
import copy
import unittest
from types import SimpleNamespace

from combat.elements.ids import ElementId
from combat.elements.reaction_log import LoggedReaction, ReactionLog
from combat.elements.registry import ElementRegistry
from combat.elements.resolve import ElementalResolver, Outcome
from combat.elements.world import NullWorld
from game.content import get_content
from game.states.playing.devtools.overlays import reaction_log_lines
from tests.combat.fakes import FakeEnemy

C = get_content()
FIRE, ICE, THUNDER = ElementId.FIRE, ElementId.ICE, ElementId.THUNDER


def build(enemies, runner, *, cap=None):
    data = copy.deepcopy(C.elements)
    if cap is not None:
        data["global"]["max_reactions_per_frame"] = cap
    registry = ElementRegistry(data, C.reactions)
    resolver = ElementalResolver(registry, world=NullWorld(enemies),
                                 reaction_runner=runner)
    resolver.log = ReactionLog(16)
    return resolver


def deal(amount):
    """A runner that deals `amount` to the carrier, as a reaction would."""
    return lambda target, variant, config, ctx: ctx.deal(target, amount, "test")


def react(resolver, enemy, now=0.0):
    """Fire on `enemy`, then Ice onto it: one reaction."""
    resolver.apply(enemy, FIRE, weapon_id="sword", hit_damage=10.0, now=now)
    return resolver.apply(enemy, ICE, weapon_id="bow", hit_damage=10.0, now=now)


class ReactionLogTests(unittest.TestCase):
    def test_a_reaction_is_logged_with_its_pair_and_its_damage(self):
        e = FakeEnemy(0, 0)
        r = build([e], deal(25.0))
        self.assertEqual(react(r, e, now=2.0), Outcome.REACTION)
        (entry,) = r.log.newest()
        variant = r.registry.reaction(FIRE, ICE)
        self.assertEqual(entry.reaction, variant.reaction.key)
        self.assertEqual((entry.aura, entry.trigger), ("fire", "ice"))
        self.assertAlmostEqual(entry.damage, 25.0)
        self.assertEqual((entry.depth, entry.deferred), (0, False))
        self.assertEqual(entry.serial, 1)
        self.assertEqual(entry.time, 2.0)

    def test_a_reaction_set_off_inside_another_is_a_cascade(self):
        """The second enemy holds Thunder; the first reaction lays Fire on
        it through `spread_aura`, which is how a tornado or Superconduct
        starts the next one."""
        a, b = FakeEnemy(0, 0), FakeEnemy(40, 0)

        def runner(target, variant, config, ctx):
            ctx.deal(target, 10.0, "test")
            if target is a:
                ctx.resolver.spread_aura(b, FIRE, weapon_id="bow",
                                         hit_damage=5.0, now=ctx.now)

        r = build([a, b], runner)
        r.apply(b, THUNDER, weapon_id="rod", hit_damage=10.0, now=0.0)
        react(r, a)
        newest, oldest = r.log.newest()
        self.assertEqual(newest.depth, 0, "the outer reaction finishes last")
        self.assertEqual(oldest.depth, 1)
        self.assertEqual((oldest.aura, oldest.trigger), ("thunder", "fire"))

    def test_the_damage_is_the_reactions_own_not_its_cascades(self):
        a, b = FakeEnemy(0, 0), FakeEnemy(40, 0)

        def runner(target, variant, config, ctx):
            ctx.deal(target, 10.0 if target is a else 99.0, "test")
            if target is a:
                ctx.resolver.spread_aura(b, FIRE, weapon_id="bow",
                                         hit_damage=5.0, now=ctx.now)

        r = build([a, b], runner)
        r.apply(b, THUNDER, weapon_id="rod", hit_damage=10.0, now=0.0)
        react(r, a)
        outer = next(e for e in r.log.newest() if e.depth == 0)
        self.assertAlmostEqual(outer.damage, 10.0)

    def test_a_reaction_the_budget_held_is_logged_when_it_runs(self):
        a, b = FakeEnemy(0, 0), FakeEnemy(40, 0)
        r = build([a, b], deal(5.0), cap=1)
        react(r, a)
        self.assertEqual(react(r, b), Outcome.DEFERRED)
        self.assertEqual(len(r.log), 1, "a held reaction has not run yet")
        r.begin_frame(0.1)
        newest = r.log.newest()[0]
        self.assertTrue(newest.deferred)
        self.assertEqual(newest.serial, 2)

    def test_the_log_keeps_only_its_capacity(self):
        log = ReactionLog(3)
        for i in range(5):
            log.record(LoggedReaction(i + 1, float(i), "overload", "fire",
                                      "thunder", 1.0, 0, False))
        self.assertEqual(len(log), 3)
        self.assertEqual([e.serial for e in log.newest()], [5, 4, 3])
        self.assertEqual([e.serial for e in log.newest(2)], [5, 4])

    def test_clearing_the_resolver_clears_the_log(self):
        e = FakeEnemy(0, 0)
        r = build([e], deal(1.0))
        react(r, e)
        r.clear()
        self.assertEqual(len(r.log), 0)

    def test_no_log_means_nothing_is_recorded(self):
        e = FakeEnemy(0, 0)
        r = build([e], deal(1.0))
        r.log = None
        self.assertEqual(react(r, e), Outcome.REACTION)


class OverlayLineTests(unittest.TestCase):
    def test_a_line_names_the_reaction_and_flags_a_cascade_and_a_hold(self):
        log = ReactionLog(4)
        log.record(LoggedReaction(1, 1.0, "melt", "fire", "ice", 12.5, 0, False))
        log.record(LoggedReaction(2, 1.2, "overload", "thunder", "fire", 30.0, 2, True))
        (newest, _c1), (oldest, _c2) = reaction_log_lines(log, 10)
        self.assertIn("overload", newest)
        self.assertIn("thunder>fire", newest)
        self.assertIn("cascade 2", newest)
        self.assertIn("held", newest)
        self.assertNotIn("cascade", oldest)
        self.assertNotIn("held", oldest)

    def test_the_overlay_is_a_dev_menu_row(self):
        from game.states import dev_menu_state
        self.assertIn("reaction_log", dev_menu_state._ROOT_ROWS)
        self.assertIn("reaction_log", dev_menu_state._LABELS)

    def test_the_overlay_draws_nothing_outside_a_dev_run(self):
        import pygame
        from game.states.playing.devtools.overlays import reaction_log_overlay
        surf = pygame.Surface((200, 200))
        ps = SimpleNamespace(dev_mode=False, _dev_show_reaction_log=True)
        reaction_log_overlay(surf, ps)                   # returns before any read
        self.assertEqual(surf.get_at((100, 100))[:3], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
