"""Generate the weapon / blessing / forge reference tables from the data JSON.

Emits Markdown (for documentation/) and a plain HTML body (for the artifact).
Run from the repo root.
"""
from __future__ import annotations

import json
import html
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
OUT_MD = Path(sys.argv[2])
OUT_HTML = Path(sys.argv[3])

sys.path.insert(0, str(ROOT))
from progression.blessings.catalog import format_value  # noqa: E402

D = ROOT / "data"
weapons = json.loads((D / "weapons/weapons.json").read_text(encoding="utf-8"))
blessings = json.loads((D / "weapons/blessings.json").read_text(encoding="utf-8"))
forges = json.loads((D / "weapons/forges.json").read_text(encoding="utf-8"))
items = json.loads((D / "weapons/items.json").read_text(encoding="utf-8"))
offering = json.loads((D / "weapons/offering.json").read_text(encoding="utf-8"))
meta = json.loads((D / "heroes/meta_upgrades.json").read_text(encoding="utf-8"))

ROMAN = ["I", "II", "III", "IV", "V"]
WEAPON_ORDER = ["sword", "hammer", "daggers", "bow", "magic_rod", "bomb",
                "ember_ring", "grave_totem", "spirit_wolf"]

# Which base field a bonus field is applied to, for the "resulting value" line.
FIELD_LABEL = {
    "damage": "damage", "area": "area", "cone_half_angle": "cone half-angle",
    "weight": "knockback weight", "cooldown_mult": "cooldown", "pierce": "pierce",
    "projectile_count": "count", "crit_chance": "crit chance",
    "stun_chance": "stun chance", "stun_duration": "stun duration",
    "blast_radius": "blast radius", "blast_radius_mult": "blast radius",
    "aim_assist_deg": "aim assist", "chain_count": "chain hops",
    "chain_range": "chain range", "summon_lifetime": "summon lifetime",
    "twin_offset_deg": "twin offset", "shockwave_radius": "shockwave radius",
    "hazard_radius": "crater radius", "hazard_duration": "crater duration",
    "cluster_count": "bomblets",
    "crit_damage": "crit damage", "reach": "reach", "orbit_radius": "orbit radius",
    "rehit_mult": "rehit interval", "orbit_speed_mult": "orbit speed",
    "attack_interval_mult": "attack interval",
    "summon_speed": "summon speed", "summon_reach": "summon leash",
}


KEY_LABEL = {
    "on_kill_heal": "HP healed per kill",
    "executioner_mult": "bonus dmg vs low HP",
    "executioner_threshold": "low-HP threshold",
    "weak_point_mult": "bonus dmg vs wounded",
    "split_count": "arrows spawned on hit",
    "split_damage_mult": "split arrow damage",
    "overcharge_mult": "overcharged bolt damage",
    "overcharge_every": "every Nth cast",
    "demolition_mult": "bonus dmg vs stunned / shoved",
    "syn_after_sword": "bonus dmg after Sword hit (1.5 s)",
    "syn_after_hammer": "bonus dmg after Hammer hit (1.5 s)",
    "syn_vs_marked": "bonus dmg vs Rod-marked",
    "crossfire_rod_bonus": "Rod bonus dmg after Bow hit (1.5 s)",
    "pull_strength": "pull toward blow (px/s)",
    "hunters_mark_per_hit": "bonus dmg per stack",
    "hunters_mark_max": "max stacks",
    "flurry_per_hit": "attack speed per stack", "flurry_max": "max stacks",
    "bleed_on_hit_frac": "bleed per tick (of the hit)", "bleed_on_hit_duration": "bleed duration",
    "burn_on_hit_frac": "burn per tick (of the hit)", "burn_on_hit_duration": "burn duration",
    "chill_on_hit_potency": "slow", "chill_on_hit_duration": "slow duration",
    "pack_tactics_mult": "bonus dmg vs enemies your weapons hit (1.5 s)",
    "sticky_damage_mult": "stuck blast bonus dmg", "sticky": "sticks to the first enemy touched",
    "keg_frac": "burst on kill (of the blast)",
}


def g(v: float) -> str:
    return f"{v:g}"


def base_of(weapon_id: str, field: str, forge_id: str | None):
    """The value a bonus field starts from: the weapon definition, with the
    forge's overrides/effects merged when the blessing is post-forge."""
    d = dict(weapons[weapon_id])
    fx = {}
    if forge_id:
        d.update(forges[forge_id]["overrides"])
        fx = forges[forge_id]["effects"]
    if field == "cooldown_mult":
        return float(d["cooldown"]), "s"
    if field == "blast_radius_mult":
        return float(d["blast_radius"]), ""
    if field == "rehit_mult":
        return float(d["rehit_interval"]), "s"
    if field == "orbit_speed_mult":
        return float(d["orbit_speed"]), ""
    if field == "attack_interval_mult":
        return float(d["summon_attack_interval"]), "s"
    if field in d and isinstance(d[field], (int, float)):
        return float(d[field]), ""
    if field in fx:
        return float(fx[field]), ""
    return None, ""


def resulting(weapon_id: str, e: dict, forge_id: str | None) -> str | None:
    """'base -> v1 / v2 / ...' for a weapon_bonus whose base is known."""
    base, unit = base_of(weapon_id, e["field"], forge_id)
    if base is None:
        return None
    vals = []
    for lv in e["levels"]:
        if e["mode"] == "mult":
            vals.append(base * lv)
        else:
            vals.append(base + lv)
    if e["field"] in ("crit_chance", "stun_chance"):
        fmt = lambda x: f"{x*100:.0f}%"
    else:
        fmt = lambda x: f"{round(x, 2):g}{unit}"
    return f"{FIELD_LABEL.get(e['field'], e['field'])} {fmt(base)} → " + " / ".join(fmt(v) for v in vals)


def effect_row(bid: str, b: dict, e: dict) -> tuple[str, str, list[str], str]:
    """(what, unit-note, per-level cells, resulting line)."""
    if e["type"] == "weapon_bonus":
        what = FIELD_LABEL.get(e["field"], e["field"])
        if e["mode"] == "mult":
            what += " ×"
        else:
            what += " +"
    else:
        what = KEY_LABEL.get(e["key"], e["key"])
    cells = [format_value(v, e["display"]) if e["display"] != "hidden" else f"×{v:g}"
             for v in e["levels"]]
    res = resulting(b["weapon"], e, b.get("requires", {}).get("forge")) if e["type"] == "weapon_bonus" else None
    return what, cells, res


def weapon_summary(wid: str) -> str:
    w = weapons[wid]
    parts = [f"class {w['class']}", f"category {w['category']}", f"damage {w['damage']}",
             f"cooldown {w['cooldown']}s"]
    if w.get("projectile_count", 1) != 1:
        parts.append(f"count {w['projectile_count']}")
    parts.append(f"area {w['area']}")
    if w.get("reach"):
        parts.append(f"reach {w['reach']}")
    if w.get("cone_half_angle"):
        parts.append(f"cone ±{w['cone_half_angle']}°")
    if w.get("pierce") not in (None, 999):
        parts.append(f"pierce {w['pierce']}")
    parts.append(f"weight {w['weight']}")
    for k in ("stun_chance", "stun_duration", "blast_radius", "fuse", "orbit_radius",
              "orbit_speed", "rehit_interval", "summon_lifetime", "summon_replant_delay",
              "summon_attack_interval", "summon_attack_range", "aim_assist_deg"):
        if k in w:
            parts.append(f"{k.replace('_', ' ')} {w[k]}")
    if w.get("special_effect"):
        parts.append(f"special {w['special_effect']}")
    parts.append(element_cadence(w))
    return ", ".join(parts)


def element_cadence(w: dict) -> str:
    """How often this weapon inflicts the element infused into it.

    Every weapon carries `element_application` (the owner's rule: summons
    are infusable too, so every one of them needs the metadata), in one of
    two modes -- an attack counter, or a time window. Without this column
    the reference tables describe the weapons as if infusion did not exist,
    and the cadence is the whole reason one weapon is a better home for an
    element than another.
    """
    spec = w["element_application"]
    if spec["mode"] == "time":
        return f"element every {spec['window']}s"
    skipped = int(spec["interval"])
    if skipped == 0:
        return "element every attack"
    nth = skipped + 1
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(nth if nth < 20 else nth % 10, "th")
    return f"element every {nth}{suffix} attack"


# --------------------------------------------------------------------------
md: list[str] = []
hb: list[str] = []          # html body


def slug(t: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def h(level: int, text: str) -> None:
    md.append(f"{'#' * level} {text}\n")
    attr = f' id="{slug(text)}"' if level <= 3 else ""
    hb.append(f'<h{level}{attr}>{html.escape(text)}</h{level}>')


def p(text: str) -> None:
    md.append(text + "\n")
    # very small inline markup: `code` and **bold**
    t = html.escape(text)
    import re
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    hb.append(f"<p>{t}</p>")


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> None:
    md.append("| " + " | ".join(headers) + " |")
    md.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        md.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    md.append("")
    hb.append(f'<div class="tw"><table class="{cls}"><thead><tr>'
              + "".join(f"<th>{html.escape(x)}</th>" for x in headers)
              + "</tr></thead><tbody>")
    chip_cols = {i for i, x in enumerate(headers) if x in ("Rarity", "Category")}
    level_cols = {i for i, x in enumerate(headers) if x in ROMAN or x in RAR}
    for r in rows:
        cont = ' class="cont"' if str(r[0]) == "" else ""
        cells = []
        for i, c in enumerate(r):
            c = str(c)
            if i in chip_cols and c:
                cells.append(f'<td><span class="chip {c}">{html.escape(c)}</span></td>')
            elif i in level_cols:
                cells.append(f'<td class="num">{html.escape(c)}</td>')
            else:
                cells.append(f"<td>{html.escape(c)}</td>")
        hb.append(f"<tr{cont}>" + "".join(cells) + "</tr>")
    hb.append("</tbody></table></div>")


RAR = ["common", "uncommon", "rare", "epic", "legendary"]


def bullets(lines: list[str]) -> None:
    for l in lines:
        md.append(f"- {l}")
    md.append("")
    import re
    hb.append("<ul>" + "".join(
        "<li>" + re.sub(r"`([^`]+)`", r"<code>\1</code>",
                        re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html.escape(l)))
        + "</li>" for l in lines) + "</ul>")


# --------------------------------------------------------------------------
h(1, "Weapon blessings, Forgings and upgrades")
p("Generated by `tools/gen_weapon_tables.py` from `data/weapons/*.json` and `data/heroes/meta_upgrades.json` on 2026-09-19; rerun it after a tuning pass. "
  "Blessing values are the **cumulative total at that level** (the catalog stores totals; "
  "applying level N adds the difference to N-1). Every blessing has five levels. "
  "The `→` lines show the weapon's own number before and after each level, "
  "using the base weapon (or the forged weapon for a post-Forge blessing).")

h(2, "Review findings")
p("What stood out while building the tables. Numbers come from the data files; "
  "balance and consistency notes; the open defect the 2026-09-12 review found is fixed.")
bullets([
    "**The three Forge cards that say the blow is lighter now are (2026-09-19).** "
    "The 2026-09-12 tuning pass moved Bomb damage 28 → 23 and Hammer 25 → 27 without revisiting "
    "`data/weapons/forges.json`, so Meteor Hammer (27), Cluster Bomb (24) and Minefield (26) all "
    "hit as hard as or harder than the base while their cards said lighter. The overrides are "
    "re-based on the current weapons: Meteor Hammer 23 (0.85 of the Hammer's 27; the crater's "
    "0.35 dps × 2.5 s is worth most of a blow), Cluster Bomb 20 and Minefield 21 (0.86 and 0.93 "
    "of the Bomb's 23, the ratios the Forgings shipped with).",
    "**Six own blessings per weapon (2026-09-19).** Every weapon, summons included, carries one "
    "damage blessing, one speed / frequency blessing, one or two coverage blessings and the rest "
    "special effects; the six cross-weapon synergies and the post-Forge blessings sit on top and "
    "stay gated. Damage blessings follow `base × (1.15^n − 1)` so level V doubles the weapon and "
    "every step is 10-20 % over the previous level; speed blessings are ×0.87 / 0.76 / 0.66 / 0.57 "
    "/ 0.50; the trade cards (Heavy Blade, Heavy Draw) are sized so the net output still climbs "
    "×1.15 a level. Coverage grows about +20-25 % hit area a level. Blast Amplifier is gone. "
    "See `journals/six_blessings_journal.md`.",
    "**Two coverage cards multiply hits and sit above the yardstick.** Arcane Missiles (+3 bolts "
    "at V) and More Embers (+5 embers at V) scale output close to linearly against a single "
    "target. Both are identity cards from the design and were kept as they were.",
    "**Cooldown penalties are flat.** Heavy Blade and Heavy Draw multiply cooldown by ×1.15 at "
    "every level (the level-to-level delta is ×1.0), so the penalty is paid in full at level I "
    "and the later levels are pure gain. Intended, but worth knowing when reading the tables.",
    "**Stacking that reaches the floor.** Quick Hands V halves the Daggers cooldown to 0.2 s; "
    "with Haste V (÷1.32) that is 0.15 s and with Flurry V at five stacks (÷1.6) 0.095 s, still "
    "above the 0.05 s floor. Rapid Draw V with Heavy Draw gives the Bow 1.2 × 0.5 × 1.15 = 0.69 s. "
    "Dense Field V on Minefield lays a mine every 0.65 s with a 25 s lifetime, so up to about "
    "38 live mines at once.",
    "**Constant effect rows.** Executioner's threshold (35% HP), Hunter's Mark's and Flurry's caps "
    "(5 stacks), Overcharge's cadence (every 4th cast), Chain's range (200 px), Sticky Bomb's flag "
    "and the on-hit status durations are stored as five equal levels. They print correctly and "
    "never change; the tables show them once.",
    "**Name collisions between systems.** Fortune and Scholar exist as both a meta upgrade and a "
    "blessing, Swiftness is a meta upgrade and an item affix, and Vitality / Haste / Fortune are "
    "both blessings and affixes. Nothing breaks, but the run-status screen lists them side by side.",
    "**All effect keys are wired.** Every `weapon_effect` key and Forge effect key in the data is "
    "read by code (combat.py, synergy.py, core.py, slam.py, bomb.py, effects.py, state.py), and "
    "the item affix tags `area` and `elite` are honoured by the tag-damage aggregate. The on-hit "
    "status keys are read by suffix (`_on_hit_frac`, `_on_hit_potency`, `_on_hit_duration`).",
])

rules = offering
h(2, "Offering rules")
table(["Rule", "Value"], [
    ["Cards per level-up", rules["choices"]],
    ["Kind weights (stat / weapon / grant / forge)",
     f"{rules['kind_weights']['stat']} / {rules['kind_weights']['weapon']} / "
     f"{rules['kind_weights']['grant']} / {rules['kind_weights']['forge']}"],
    ["Rarity weights (common / uncommon / rare / forge)",
     f"{rules['rarity_weights']['common']} / {rules['rarity_weights']['uncommon']} / "
     f"{rules['rarity_weights']['rare']} / {rules['rarity_weights']['forge']}"],
    ["Level falloff (weight × at level I..V)", " / ".join(g(x) for x in rules["level_falloff"])],
    ["Summon grant weight factor", rules["summon_factor"]],
    ["Blessing levels a weapon needs before it can be forged", rules["forge_requires_levels"]],
    ["Weapon slots (melee + ranged) / summon slots", "3 / 1"],
    ["Forgings per weapon", "1 of 2, exclusive and permanent"],
])

# --- per-weapon -------------------------------------------------------------
h(2, "Per-weapon tables")
for wid in WEAPON_ORDER:
    w = weapons[wid]
    h(3, w["name"])
    p(f"*{w['description']}*  ")
    p("Base: " + weapon_summary(wid))

    base_bless = [(bid, b) for bid, b in blessings.items()
                  if b["kind"] == "weapon" and b["weapon"] == wid and "forge" not in b.get("requires", {})]
    rows = []
    for bid, b in base_bless:
        req = b.get("requires", {})
        note = ""
        if "weapons" in req:
            note = "needs " + ", ".join(weapons[x]["name"] for x in req["weapons"])
        for i, e in enumerate(b["effects"]):
            what, cells, res = effect_row(bid, b, e)
            rows.append([
                b["name"] if i == 0 else "",
                b["category"] if i == 0 else "",
                b["rarity"] if i == 0 else "",
                what, *cells,
                res or "",
                note if i == 0 else "",
            ])
    h(4, "Blessings")
    table(["Blessing", "Category", "Rarity", "Effect", *ROMAN, "Resulting value", "Requires"], rows, "bless")

    my_forges = [(fid, f) for fid, f in forges.items() if f["weapon"] == wid]
    if not my_forges:
        p("No Forgings: summons cannot be forged.")
        continue
    h(4, "Forgings")
    frows = []
    for fid, f in my_forges:
        ov = []
        for k, v in f["overrides"].items():
            if k in ("name",):
                continue
            old = w.get(k)
            if old is None:
                ov.append(f"{k} = {v}")
            elif old != v:
                ov.append(f"{k} {old} → {v}")
        fx = ", ".join(f"{k} {v}" for k, v in f["effects"].items()) or "—"
        frows.append([f["name"], f["identity"], "; ".join(ov), fx, f["description"]])
    table(["Forging", "Identity", "Overrides (base → forged)", "Forge effects", "Card text"], frows, "forge")

    post = [(bid, b) for bid, b in blessings.items()
            if b["kind"] == "weapon" and b["weapon"] == wid and "forge" in b.get("requires", {})]
    prow = []
    for bid, b in post:
        fname = forges[b["requires"]["forge"]]["name"]
        for i, e in enumerate(b["effects"]):
            what, cells, res = effect_row(bid, b, e)
            prow.append([fname if i == 0 else "", b["name"] if i == 0 else "",
                         b["category"] if i == 0 else "", b["rarity"] if i == 0 else "",
                         what, *cells, res or ""])
    h(4, "Post-Forge blessings")
    table(["After forging", "Blessing", "Category", "Rarity", "Effect", *ROMAN, "Resulting value"], prow, "bless")

# --- hero stat blessings ----------------------------------------------------
h(2, "Hero stat blessings (any weapon)")
rows = []
for bid, b in blessings.items():
    if b["kind"] != "stat":
        continue
    for i, e in enumerate(b["effects"]):
        cells = [format_value(v, e["display"]) for v in e["levels"]]
        rows.append([b["name"] if i == 0 else "", b["category"], b["rarity"],
                     f"{e['stat']} ({e['op']})", *cells,
                     b["description"].format(*["X"] * len(b["effects"]))])
table(["Blessing", "Category", "Rarity", "Stat (op)", *ROMAN, "Card text"], rows, "bless")

# --- meta upgrades ----------------------------------------------------------
h(2, "Meta upgrades (Salvage shop, persistent)")
rows = []
for mid, m in meta.items():
    lv = m["max_level"]
    costs = [m["cost_base"] + m["cost_step"] * i for i in range(lv)]
    per = m["per_level"]
    tot = per * lv
    fmt = (lambda x: f"{x*100:g}%") if m["op"] == "pct" or per < 1 else (lambda x: f"{x:g}")
    rows.append([m["name"], f"{m['stat']} ({m['op']})", f"+{fmt(per)}", lv, f"+{fmt(tot)}",
                 f"{costs[0]} … {costs[-1]} (total {sum(costs)})"])
table(["Upgrade", "Stat (op)", "Per level", "Max level", "At max", "Cost per level (Salvage)"], rows)

# --- items ------------------------------------------------------------------
h(2, "Equipment (random items)")
p("An item is one base stat plus 0/1/2/3/4 affixes for common/uncommon/rare/epic/legendary, "
  "plus the slot's unique effect at legendary. Values scale by `1 + 0.05 × (item level − 1)`. "
  "Rarity weights 60/25/10/4/1, shifted toward the top by luck. Prefixes: "
  + ", ".join(f"{k} = {v}" for k, v in items["prefixes"].items()) + ".")
rows = []
for slot, bases in items["bases"].items():
    for b in bases:
        rows.append([slot, b["name"], f"{b['stat']} ({b['op']})", f"{g(b['min'])} – {g(b['max'])}"])
table(["Slot", "Base", "Stat (op)", "Roll range"], rows)
rows = []
RAR = ["common", "uncommon", "rare", "epic", "legendary"]
for aid, a in items["affixes"].items():
    target = f"{a['stat']} ({a['op']})" if a["kind"] == "stat" else f"+dmg vs tag '{a['tag']}'"
    rows.append([a["name"], ", ".join(a["slots"]), target, *[g(a["values"][r]) for r in RAR]])
table(["Affix", "Slots", "Target", *RAR], rows)
rows = [[slot, u["name"], u["desc"]] for slot, u in items["unique_effects"].items()]
table(["Slot", "Legendary unique", "Effect"], rows)

OUT_MD.write_text("\n".join(md), encoding="utf-8")
OUT_HTML.write_text("\n".join(hb), encoding="utf-8")
print("wrote", OUT_MD, OUT_HTML, "\nblessings:", len(blessings), "forges:", len(forges))
