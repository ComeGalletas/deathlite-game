"""Item names built from their parts when shown (UI-014.6, UI-014.D9).

An item's stored `name` is its English identity (built at generation,
saved). What the player reads is `item_name`: the base, the rarity word and
the first affix in the current language, in the word order of the locale's
`item.name` / `item.name_affix` templates. Spanish puts the rarity adjective
after the base and agrees it with the base's `gender_es`.
"""
import unittest
from unittest import mock

from game import locale
from game.content import get_content
from progression.items import (RARITIES, AffixRoll, Item, generate_item, item_label,
                               item_name, stored_name)

C = get_content()
SEEDS = range(1500)


def items():
    return [generate_item(C, seed=s, item_level=1 + s % 7) for s in SEEDS]


def old_save(item):
    """The dict an item saved before UI-014.6 has: no `base_id`."""
    d = item.to_dict()
    del d["base_id"]
    return Item.from_dict(d)


class NameTests(unittest.TestCase):
    def setUp(self):
        locale.set_language("en")

    def tearDown(self):
        locale.set_language(locale.DEFAULT)

    def test_generation_records_the_base_and_the_save_keeps_it(self):
        it = generate_item(C, seed=7)
        self.assertIn(it.base_id, {b["id"] for b in C.items["bases"][it.slot]})
        back = Item.from_dict(it.to_dict())
        self.assertEqual(back.base_id, it.base_id)
        self.assertEqual(back, it)

    def test_english_builds_exactly_the_stored_name_for_every_combination(self):
        # Exhaustive, not sampled: every slot x base x rarity x possible
        # first affix (or none), for a new item and for one saved before
        # `base_id` existed. The template path (`item_name`) against the
        # generation path (`stored_name`).
        data = C.items
        checked = 0
        for slot, bases in data["bases"].items():
            eligible = [aid for aid, a in data["affixes"].items() if slot in a["slots"]]
            for base in bases:
                firsts = [None] + [aid for aid in eligible
                                   if (data["affixes"][aid].get("stat")
                                       or data["affixes"][aid].get("tag")) != base["stat"]]
                for rarity in RARITIES:
                    for aid in firsts:
                        if (aid is None) != (rarity == "common"):
                            continue                # common rolls none, the rest one or more
                        affixes = [] if aid is None else [AffixRoll(
                            aid, data["affixes"][aid]["name"], "stat", None, None, None, 1.0)]
                        name = stored_name(data, base, rarity,
                                           affixes[0].name if affixes else None)
                        it = Item(f"{slot}-x-{rarity}", slot, name, rarity, 1,
                                  base["stat"], base["op"], 1.0, affixes, None, base["id"])
                        self.assertEqual(item_name(it, C), name)
                        self.assertEqual(item_name(old_save(it), C), name)
                        checked += 1
        self.assertGreaterEqual(checked, 150)

    def test_generation_names_through_stored_name(self):
        for it in items()[:200]:
            base = next(b for b in C.items["bases"][it.slot] if b["id"] == it.base_id)
            first = it.affixes[0].name if it.affixes else None
            self.assertEqual(it.name, stored_name(C.items, base, it.rarity, first))

    def test_base_stats_are_unique_per_slot(self):
        # An old save (no `base_id`) finds its base by slot + stat; two bases
        # of one slot sharing a stat would leave those items unnamed in
        # Spanish, silently. This keeps the recovery exact.
        for slot, bases in C.items["bases"].items():
            stats = [b["stat"] for b in bases]
            self.assertEqual(len(stats), len(set(stats)), slot)

    def test_spanish_word_order_and_gender(self):
        locale.set_language("es")
        data = C.items
        for it in items():
            base = next(b for b in data["bases"][it.slot] if b["id"] == it.base_id)
            prefix = data["prefixes_es"][it.rarity][base["gender_es"]]
            want = f"{base['name_es']} {prefix}"
            if it.affixes:
                want += f" {data['affixes'][it.affixes[0].affix_id]['name_es']}"
            self.assertEqual(item_name(it, C), want, it.item_id)
            self.assertEqual(item_name(old_save(it), C), want, it.item_id)

    def test_known_names(self):
        locale.set_language("es")
        self.assertEqual(item_name(generate_item(C, seed=5, item_level=3), C),
                         "Amuleto de urraca refinado de presteza")
        self.assertEqual(item_name(generate_item(C, seed=33, item_level=3), C),
                         "Pulsera de viaje refinada de vitalidad")

    def test_the_same_item_follows_a_language_switch(self):
        it = generate_item(C, seed=5, item_level=3)
        english = item_name(it, C)
        locale.set_language("es")
        self.assertNotEqual(item_name(it, C), english)
        locale.set_language("en")
        self.assertEqual(item_name(it, C), english)
        self.assertEqual(it.name, english)             # the identity never moved

    def test_an_unknown_or_ambiguous_base_shows_the_stored_name(self):
        locale.set_language("es")
        it = generate_item(C, seed=5)
        it.base_id = "no_such_base"
        self.assertEqual(item_name(it, C), it.name)
        legacy = old_save(generate_item(C, seed=5))
        legacy.base_stat = "no_such_stat"
        self.assertEqual(item_name(legacy, C), legacy.name)
        # Two bases of the slot sharing the stat: no guess.
        twin = dict(C.items["bases"][legacy.slot][0], id="twin")
        stat_twin = old_save(generate_item(C, seed=5))
        bases = C.items["bases"][stat_twin.slot]
        stat_twin.base_stat = bases[0]["stat"]
        with mock.patch.dict(C.items["bases"], {stat_twin.slot: bases + [twin]}):
            self.assertEqual(item_name(stat_twin, C), stat_twin.name)

    def test_a_missing_spanish_part_falls_back_to_english(self):
        locale.set_language("es")
        it = next(i for i in items() if i.affixes)
        affix = C.items["affixes"][it.affixes[0].affix_id]
        forms = C.items["prefixes_es"][it.rarity]
        with mock.patch.dict(affix, {"name_es": ""}), \
                mock.patch.dict(forms, {"m": "", "f": ""}):
            name = item_name(it, C)
        self.assertIn(C.items["prefixes"][it.rarity], name)       # English word
        self.assertTrue(name.endswith(affix["name"]), name)        # English affix

    def test_the_label_puts_the_rarity_tag_before_the_name(self):
        locale.set_language("es")
        it = generate_item(C, seed=5, item_level=3)
        self.assertEqual(item_label(it, C), f"[{it.rarity[0].upper()}] {item_name(it, C)}")

    def test_the_summary_builds_names_and_keeps_a_legacy_dict(self):
        from ui.run_summary import _item_name
        locale.set_language("es")
        it = generate_item(C, seed=33, item_level=3)
        self.assertEqual(_item_name(it.to_dict())[0],
                         "[U] Pulsera de viaje refinada de vitalidad")
        # A summary written before items carried their parts.
        legacy = {"name": "Fine Traveller Band of Vitality", "rarity": "uncommon",
                  "slot": "accessory", "level": 3}
        self.assertEqual(_item_name(legacy)[0], "[U] Fine Traveller Band of Vitality")
        self.assertEqual(_item_name("Bare string")[0], "Bare string")
        # A whole item saved before `base_id` existed is still built.
        old = it.to_dict()
        del old["base_id"]
        self.assertEqual(_item_name(old)[0], "[U] Pulsera de viaje refinada de vitalidad")

    def test_the_summary_does_not_hide_a_naming_error(self):
        # Only the whole-item check falls back; a bug inside `item_name`
        # raises here as it does on the TAB screen and in the Sanctuary.
        from ui import run_summary
        it = generate_item(C, seed=33, item_level=3)
        with mock.patch.object(run_summary, "item_name", side_effect=KeyError("boom")):
            with self.assertRaises(KeyError):
                run_summary._item_name(it.to_dict())


if __name__ == "__main__":
    unittest.main()
