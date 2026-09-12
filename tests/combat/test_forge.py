"""Six-weapon system P3: Forging (design §7, §8, §13, §18). The twelve
Forgings as data, the merge onto a weapon, exclusivity and eligibility, and
every Forge behaviour that needs code: twin cones, the Earthshaker
shockwave, the Meteor Hammer crater (a hero-owned hazard), cluster
bomblets, mines, and the changed fire mechanisms (Fan of Blades, Arcane
Storm)."""
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from combat.weapons.forge import (EFFECT_KEYS, OVERRIDABLE, Forges, apply_forge,
                                  blessing_levels, forge_eligible, get_forges)
from game.content import get_content
from game.states.playing.combat import CombatResolver
from tests.combat.fakes import FakeEnemy, fake_ps

C = get_content()
F = get_forges(C)
SIX = ("sword", "hammer", "daggers", "bow", "magic_rod", "bomb")


def weapon(wid, forge=None):
    w = Weapon(wid, C.weapon(wid))
    if forge:
        apply_forge(w, F.get(forge))
    w._cd = 0.0
    return w


class _Shot:
    def __init__(self, **kw):
        self.active = True
        self.__dict__.update(kw)


def ctx(enemies, sink, **over):
    base = dict(origin=pygame.Vector2(), enemies=list(enemies),
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0),
                spawn_projectile=lambda **kw: (sink.append(_Shot(**kw)), sink[-1])[1],
                anchor=pygame.Vector2())
    base.update(over)
    return FireContext(**base)


def fire(w, enemies=(FakeEnemy(25, 0),), **over):     # inside every melee reach
    """One attack's spawns. A slam (the Hammer, CR1) swings first, so the
    weapon is ticked until its blow lands."""
    sink = []
    w._cd = 0.0
    w.update(1 / 60, ctx(enemies, sink, **over))
    if w.special == "slam":
        for _ in range(90):
            if sink or w._swing_dir is None:
                break
            w.update(1 / 60, ctx(enemies, sink, **over))
    return sink


class DataTests(unittest.TestCase):
    def test_twelve_forgings_two_per_weapon_none_for_summons(self):
        self.assertEqual(len(F.by_id), 12)
        for wid in SIX:
            self.assertEqual(len(F.for_weapon(wid)), 2, wid)
        for wid in ("ember_ring", "grave_totem", "spirit_wolf"):
            self.assertEqual(F.for_weapon(wid), [], wid)

    def test_the_designs_twelve_names(self):
        self.assertEqual(set(F.by_id), {
            "whirlwind", "greatsword", "earthshaker", "meteor_hammer", "twin_daggers",
            "fan_of_blades", "multishot", "ballista", "arcane_storm", "arcane_lance",
            "cluster_bomb", "minefield"})

    def test_every_forging_renames_the_weapon_and_has_an_identity(self):
        for f in F.by_id.values():
            self.assertEqual(f.overrides.get("name"), f.name, f.id)
            self.assertTrue(f.identity, f.id)
            self.assertTrue(f.description, f.id)

    def test_overrides_and_effects_are_known_keys(self):
        for f in F.by_id.values():
            self.assertTrue(set(f.overrides) <= OVERRIDABLE, f.id)
            self.assertTrue(set(f.effects) <= EFFECT_KEYS, f.id)

    def test_bad_data_raises(self):
        base = {"name": "X", "weapon": "sword", "identity": "i", "description": "d",
                "overrides": {}, "effects": {}}
        with self.assertRaises(ValueError):
            Forges({"x": {**base, "weapon": "spirit_wolf"}}, C.weapons)
        with self.assertRaises(ValueError):
            Forges({"x": {**base, "overrides": {"class": "ranged"}}}, C.weapons)
        with self.assertRaises(ValueError):
            Forges({"x": {**base, "effects": {"homing": 1}}}, C.weapons)
        with self.assertRaises(ValueError):
            Forges({"x": {**base, "overrides": {"special_effect": "laser"}}}, C.weapons)


class ApplyTests(unittest.TestCase):
    def test_merge_keeps_the_base_and_takes_the_overrides(self):
        w = weapon("sword", "greatsword")
        self.assertEqual(w.forge, "greatsword")
        self.assertEqual(w.name, "Greatsword")
        self.assertEqual(w.definition["damage"], 42)
        self.assertEqual(w.definition["class"], "melee")             # untouched
        self.assertEqual(w.definition["special_effect"], "cone")     # untouched
        self.assertEqual(w.visual_id, "greatsword")

    def test_exclusive(self):
        w = weapon("sword", "whirlwind")
        with self.assertRaises(ValueError):
            apply_forge(w, F.get("greatsword"))
        self.assertEqual(w.forge, "whirlwind")

    def test_a_forging_only_fits_its_weapon(self):
        with self.assertRaises(ValueError):
            apply_forge(weapon("bow"), F.get("whirlwind"))

    def test_eligibility_needs_two_blessing_levels_and_no_forge(self):
        w = weapon("sword")
        self.assertEqual(blessing_levels(w), 0)
        self.assertFalse(forge_eligible(w, 2))
        w.level = 3                                        # two weapon blessings
        self.assertTrue(forge_eligible(w, 2))
        apply_forge(w, F.get("whirlwind"))
        self.assertFalse(forge_eligible(w, 2))
        wolf = weapon("spirit_wolf")
        wolf.level = 9
        self.assertFalse(forge_eligible(wolf, 2), "summons are never forged")

    def test_blessing_bonuses_survive_the_forge(self):
        w = weapon("sword")
        w.bonus["damage"] += 9
        apply_forge(w, F.get("greatsword"))
        self.assertAlmostEqual(w._damage(), 42 + 9)


class MeleeForgeTests(unittest.TestCase):
    def test_whirlwind_is_a_fast_full_circle(self):
        w = weapon("sword", "whirlwind")
        s = fire(w, [FakeEnemy(30, 40)])
        self.assertEqual(len(s), 1)
        self.assertAlmostEqual(s[0].cone_half_angle, math.pi)
        self.assertLess(w._cooldown(1.0), C.weapon("sword")["cooldown"] / 3)
        self.assertLess(s[0].damage, C.weapon("sword")["damage"])

    def test_greatsword_is_slow_huge_and_heavy(self):
        w = weapon("sword", "greatsword")
        s = fire(w)[0]
        self.assertGreater(s.damage, 2 * C.weapon("sword")["damage"])
        self.assertGreater(s.radius, C.weapon("sword")["area"])
        self.assertGreater(s.src_weight, C.weapon("sword")["weight"])
        self.assertGreater(w._cooldown(1.0), C.weapon("sword")["cooldown"])

    def test_twin_daggers_swing_two_fanned_cones(self):
        w = weapon("daggers", "twin_daggers")
        s = fire(w, [FakeEnemy(30, 0)])                   # inside the shorter reach
        self.assertEqual(len(s), 2)
        angles = sorted(math.degrees(math.atan2(c.cone_dir.y, c.cone_dir.x)) for c in s)
        self.assertAlmostEqual(angles[0], -22, places=3)
        self.assertAlmostEqual(angles[1], 22, places=3)
        self.assertLess(s[0].damage, C.weapon("daggers")["damage"])   # the split

    def test_cross_cut_widens_the_twin_fan(self):
        w = weapon("daggers", "twin_daggers")
        w.bonus["twin_offset_deg"] = 8
        angles = sorted(math.degrees(math.atan2(c.cone_dir.y, c.cone_dir.x))
                        for c in fire(w, [FakeEnemy(30, 0)]))
        self.assertAlmostEqual(angles[1], 30, places=3)

    def test_earthshaker_adds_a_shockwave_blast_at_the_impact(self):
        w = weapon("hammer", "earthshaker")
        s = fire(w)
        blows = [x for x in s if getattr(x, "style", "") == "hidden"]   # CR1: the slam's circle
        blasts = [x for x in s if getattr(x, "style", "") == "blast"]
        self.assertEqual((len(blows), len(blasts)), (1, 1))
        b = blasts[0]
        self.assertAlmostEqual(b.radius, 90)
        self.assertIn("shockwave", b.source_tags)
        self.assertAlmostEqual(b.damage, blows[0].damage * 0.5)
        self.assertAlmostEqual(b.pos.x, 40.0)             # the circle's centre
        self.assertTrue(b.no_block)

    def test_aftershock_widens_the_shockwave(self):
        w = weapon("hammer", "earthshaker")
        w.bonus["shockwave_radius"] = 24
        b = [x for x in fire(w) if getattr(x, "style", "") == "blast"][0]
        self.assertAlmostEqual(b.radius, 114)

    def test_meteor_hammer_leaves_a_crater_through_the_context(self):
        w = weapon("hammer", "meteor_hammer")
        craters = []
        fire(w, spawn_hazard=lambda **kw: craters.append(kw))
        self.assertEqual(len(craters), 1)
        c = craters[0]
        self.assertAlmostEqual(c["radius"], 64)
        self.assertAlmostEqual(c["duration"], 2.5)
        self.assertAlmostEqual(c["dps"], 27 * 0.35)
        self.assertAlmostEqual(c["pos"].x, 40.0)          # CR1: at the circle's centre
        self.assertEqual(c["weapon_id"], "hammer")
        self.assertIn("crater", c["source_tags"])

    def test_no_hazard_callback_means_no_crater_and_no_crash(self):
        w = weapon("hammer", "meteor_hammer")
        self.assertEqual(len(fire(w)), 1)


class CraterTests(unittest.TestCase):
    """A hero-owned hazard hurts enemies through the resolver, not the hero."""

    def _crater(self, ps, dps=10.0):
        ps.fx.spawn_hazard(pygame.Vector2(0, 0), 60, dps, 2.0, owner="player",
                           weapon_id="hammer", source_tags=("melee", "crater"))
        return ps.hazards[0]

    def test_ticks_bite_enemies_inside_and_not_the_hero(self):
        inside, outside = FakeEnemy(20, 0), FakeEnemy(200, 0)
        ps = fake_ps([inside, outside])
        ps.player.pos.update(0, 0)
        hurt = []
        ps.player.take_damage = lambda amt: hurt.append(amt)
        hz = self._crater(ps)
        for _ in range(int(hz.tick_interval * 60) + 1):     # one whole interval
            ps.fx.update_hazards(1 / 60)
            CombatResolver(ps).projectile_hits()
            ps.fx.update_projectiles(1 / 60)
        self.assertAlmostEqual(inside.hp, 100 - 10 * hz.tick_interval, delta=0.01)
        self.assertEqual(outside.hp, 100.0)
        self.assertEqual(hurt, [])

    def test_the_bite_is_a_hidden_one_frame_projectile(self):
        ps = fake_ps([])
        hz = self._crater(ps)
        ps.fx.update_hazards(hz.tick_interval + 0.001)
        live = [p for p in ps.projectiles if p.active]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0].style, "hidden")
        self.assertTrue(live[0].no_block)
        self.assertEqual(live[0].src_weight, 0.0)

    def test_an_enemy_hazard_still_only_hurts_the_hero(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        ps.player.pos.update(0, 0)
        hurt = []
        ps.player.take_damage = lambda amt: hurt.append(amt) or amt
        ps.game.events = ps.game.events
        ps.fx.spawn_hazard(pygame.Vector2(0, 0), 60, 10, 2.0)   # owner "enemy"
        for _ in range(40):
            ps.fx.update_hazards(1 / 60)
        self.assertTrue(hurt)
        self.assertEqual(e.hp, 100.0)


class RangedForgeTests(unittest.TestCase):
    def test_fan_of_blades_throws_four(self):
        w = weapon("daggers", "fan_of_blades")
        s = fire(w, [FakeEnemy(150, 0)])
        self.assertEqual(len(s), 4)
        self.assertTrue(all(x.vel.length() > 0 for x in s))
        self.assertTrue(all(getattr(x, "cone_half_angle", 0.0) == 0.0 for x in s))
        self.assertEqual(w.category, "projectile")
        self.assertEqual(w.weapon_class, "melee")         # still the melee slot

    def test_multishot_and_ballista(self):
        m = fire(weapon("bow", "multishot"), [FakeEnemy(200, 0)])
        self.assertEqual(len(m), 3)
        self.assertEqual(len({round(x.vel.y) for x in m}), 3)
        b = fire(weapon("bow", "ballista"), [FakeEnemy(200, 0)])
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0].pierce, 8)
        self.assertGreater(b[0].damage, 3 * C.weapon("bow")["damage"])

    def test_arcane_storm_orbits_instead_of_firing(self):
        w = weapon("magic_rod", "arcane_storm")
        sink = []
        self.assertFalse(w.update(1 / 60, ctx([FakeEnemy(60, 0)], sink)))
        live = [o for o in sink if o.active]
        self.assertEqual(len(live), 4)
        self.assertTrue(all(o.orbit_speed != 0 for o in live))

    def test_arcane_lance_pierces_a_line(self):
        s = fire(weapon("magic_rod", "arcane_lance"), [FakeEnemy(200, 0)])
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0].pierce, 6)
        self.assertGreater(s[0].damage, 3 * C.weapon("magic_rod")["damage"])


class BombForgeTests(unittest.TestCase):
    def _bomb_projectile(self, ps, wid_forge, **extra):
        w = Weapon("bomb", C.weapon("bomb"))
        apply_forge(w, F.get(wid_forge))
        ps.player.weapons.append(w)
        return ps._spawn_projectile(
            pos=(0, 0), vel=(0, 0), damage=24, radius=8, lifetime=0.05, inert=True,
            blast_radius=72, blast_lifetime=0.12, src_weight=22, weapon_id="bomb",
            source_tags=("ranged", "area"), **extra), w

    def test_cluster_bomb_scatters_bomblets_once(self):
        ps = fake_ps([])
        bomb, w = self._bomb_projectile(ps, "cluster_bomb")
        ps.fx.update_projectiles(0.1)                      # fuse out -> blast + bomblets
        kids = [p for p in ps.projectiles if p.active and "cluster" in p.source_tags]
        self.assertEqual(len(kids), 3)
        for k in kids:
            self.assertTrue(k.inert)
            self.assertAlmostEqual(k.damage, 24 * 0.4)
            self.assertAlmostEqual(k.blast_radius, 72 * 0.6)
            self.assertGreater(k.vel.length(), 0)
        for _ in range(60):                                # bomblets go off
            ps.fx.update_projectiles(1 / 60)
        self.assertEqual(len(ps._explosions), 4)          # 1 + 3, no grandchildren

    def test_bomblets_blessing_adds_more(self):
        ps = fake_ps([])
        bomb, w = self._bomb_projectile(ps, "cluster_bomb")
        w.bonus["cluster_count"] = 2
        ps.fx.update_projectiles(0.1)
        self.assertEqual(len([p for p in ps.projectiles if p.active and "cluster" in p.source_tags]), 5)

    def test_minefield_throws_armed_mines(self):
        w = weapon("bomb", "minefield")
        s = fire(w, [FakeEnemy(150, 0)])
        self.assertEqual(len(s), 1)
        self.assertTrue(s[0].mine)
        self.assertAlmostEqual(s[0].arm_delay, 0.6)
        self.assertAlmostEqual(s[0].lifetime, 25)
        self.assertTrue(s[0].inert)

    def test_a_mine_waits_until_armed_then_trips_on_contact(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        ps.player.weapons.append(weapon("bomb", "minefield"))
        mine = ps._spawn_projectile(
            pos=(0, 0), vel=(0, 0), damage=26, radius=8, lifetime=25, inert=True,
            blast_radius=62, blast_lifetime=0.12, src_weight=22, weapon_id="bomb",
            source_tags=("ranged", "area"), mine=True, arm_delay=0.6)
        CombatResolver(ps).projectile_hits()
        self.assertTrue(mine.active)
        self.assertEqual(e.hp, 100.0)                      # not armed yet
        mine.age = 0.7
        CombatResolver(ps).projectile_hits()
        self.assertFalse(mine.active)
        self.assertTrue(mine.detonated)
        blast = [p for p in ps.projectiles if p.active and p.style == "blast"]
        self.assertEqual(len(blast), 1)
        CombatResolver(ps).projectile_hits()
        self.assertEqual(e.hp, 74.0)

    def test_an_armed_mine_with_no_one_on_it_keeps_waiting(self):
        ps = fake_ps([FakeEnemy(300, 0)])
        ps.player.weapons.append(weapon("bomb", "minefield"))
        mine = ps._spawn_projectile(
            pos=(0, 0), vel=(0, 0), damage=26, radius=8, lifetime=25, inert=True,
            blast_radius=62, blast_lifetime=0.12, src_weight=22, weapon_id="bomb",
            source_tags=("ranged", "area"), mine=True, arm_delay=0.6)
        mine.age = 5.0
        CombatResolver(ps).projectile_hits()
        self.assertTrue(mine.active)
        self.assertFalse(mine.detonated)


class VisualTests(unittest.TestCase):
    def test_a_forged_weapon_names_its_forge_look_and_falls_back(self):
        from types import SimpleNamespace
        from game.states.playing.state import PlayingState
        fake = SimpleNamespace(content=C)
        kw = {"weapon_id": "daggers", "visual": "fan_of_blades"}
        PlayingState._resolve_visual(fake, kw)
        self.assertEqual(kw["style"], "thrown")             # the Forge's own entry
        self.assertNotIn("visual", kw)
        kw = {"weapon_id": "sword", "visual": "greatsword"}
        PlayingState._resolve_visual(fake, kw)
        self.assertEqual(kw["style"], "cone")               # no entry: the Sword's

    def test_the_fire_path_forwards_the_visual_id(self):
        s = fire(weapon("daggers", "fan_of_blades"), [FakeEnemy(150, 0)])
        self.assertEqual(s[0].visual, "fan_of_blades")
        s = fire(weapon("sword"))
        self.assertEqual(s[0].visual, "sword")


class ForgeWeaponPickerTests(unittest.TestCase):
    """Change request 6, end to end: the village Forge lets the player pick.

    The case that matters is the one that was impossible before -- two weapons
    qualify and the player reforges the **second**. `use_forge` took
    `eligible[0]`, so the second was unreachable however the player approached
    the anvil.

    Driven on the bench's empty arena (`game.dps_bench`) rather than a
    generated world: this is about the overlay, and a world would cost seconds
    per test to prove nothing.
    """

    def _run_with(self, wids, blessings):
        from combat.weapons import Weapon
        from game import dps_bench
        from progression.blessings import apply_blessing
        # Called through the module, not stashed on the class: a plain function
        # assigned to a class attribute becomes a bound method, and `self`
        # would arrive as the `hero` argument.
        game, ps = dps_bench._start_dev_run()
        ps.player.weapons.clear()
        for wid in wids:
            ps.player.weapons.append(Weapon(wid, ps.content.weapon(wid)))
        for bid in blessings:
            apply_blessing(ps.player, ps.blessing_lib.by_id[bid])
        return game, ps

    def _open_forge(self, ps):
        from entities.interactable import Interactable
        ps.locations.use_forge(Interactable("forge", pygame.Vector2(ps.player.pos), 30))

    def test_the_second_eligible_weapon_can_be_reforged(self):
        from game.states.level_up_state import LevelUpState
        game, ps = self._run_with(
            ("sword", "bow"),
            ("sword_bloodletting", "sword_crowd_cleaner",
             "bow_split_arrow", "bow_rapid_draw"))
        self._open_forge(ps)
        st = game.state_machine.current
        self.assertIsInstance(st, LevelUpState)
        self.assertEqual([r[0].weapon_id for r in st.weapon_rows], ["sword", "bow"])
        self.assertTrue(all(r[1] for r in st.weapon_rows))

        st.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        self.assertEqual(st.weapon_rows[st.weapon_sel][0].weapon_id, "bow")
        st.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))

        bow = ps.player.weapon_by_id("bow")
        sword = ps.player.weapon_by_id("sword")
        self.assertIsNotNone(bow.forge, "the Bow was not reforged")
        self.assertIsNone(sword.forge, "the Sword was reforged instead")

    def test_the_cards_belong_to_the_selected_weapon(self):
        game, ps = self._run_with(
            ("sword", "bow"),
            ("sword_bloodletting", "sword_crowd_cleaner",
             "bow_split_arrow", "bow_rapid_draw"))
        self._open_forge(ps)
        st = game.state_machine.current
        self.assertTrue(all(c.weapon == "sword" for c in st.choices))
        st.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        self.assertTrue(all(c.weapon == "bow" for c in st.choices))

    def test_a_weapon_short_of_the_requirement_is_listed_but_not_selectable(self):
        game, ps = self._run_with(
            ("sword", "hammer"),
            ("sword_bloodletting", "sword_crowd_cleaner", "hammer_heavy_impact"))
        self._open_forge(ps)
        st = game.state_machine.current
        rows = {r[0].weapon_id: r for r in st.weapon_rows}
        self.assertTrue(rows["sword"][1])
        self.assertFalse(rows["hammer"][1])
        self.assertIn("needs 1 more", rows["hammer"][2])
        st.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        self.assertEqual(st.weapon_rows[st.weapon_sel][0].weapon_id, "sword")

    def test_nothing_eligible_still_just_says_what_is_missing(self):
        from game.states.playing_state import PlayingState
        game, ps = self._run_with(("sword", "bow"), ("sword_bloodletting",))
        self._open_forge(ps)
        self.assertIsInstance(game.state_machine.current, PlayingState)


if __name__ == "__main__":
    unittest.main()
