"""Behaviour templates: `data/enemies/behaviors.json` into machines (ENT-017).

`registry.build_behavior(name, cfg)` resolves `name` here first. A template's
numbers merge shared `defaults` -> the template's `defaults` -> the enemy's
own block (`merged`), and its `shape` builds the machine:

* `move` -- one state (`state`, default `move`) holding the named `move`
  stacks, in order.
* `telegraph_cycle` -- chase -> telegraph -> attack -> recover
  (`behaviors/_telegraph.py`) from the template's `chase` stack, `trigger`,
  `timings` keys, `on_windup_start` / `on_windup_end` / `on_recover_start`
  actions and `attack` component, all by name (`entities/ai/actions.py`).
* anything else -- a code-built shape registered with `@behavior`
  (`brute`, `kite_shoot`, `path_chase_sweep`, `boss_patterns`), handed the
  merged block.
"""
from __future__ import annotations

from entities.ai import actions
from entities.ai.behaviors._telegraph import telegraph_cycle
from entities.ai.machine import Behavior

SHAPES: dict = {}


def _shape(name: str):
    def deco(fn):
        SHAPES[name] = fn
        return fn
    return deco


def _data() -> dict:
    from game.content import get_content
    return get_content().behaviors


def template(name: str) -> dict | None:
    return _data()["behaviors"].get(name)


def names() -> list[str]:
    return sorted(k for k in _data()["behaviors"] if not k.startswith("_"))


def merged(tpl: dict | None, cfg: dict) -> dict:
    """Shared defaults, then the template's, then the enemy's own keys.
    `_comment` keys are documentation, not numbers."""
    out = {k: v for k, v in _data()["defaults"].items() if not k.startswith("_")}
    if tpl is not None:
        out.update(tpl.get("defaults", {}))
    out.update(cfg)
    return out


def _stacks(names_, cfg) -> list:
    comps = []
    for n in names_:
        comps.extend(actions.STACKS[n](cfg))
    return comps


@_shape("move")
def _move(tpl: dict, cfg: dict) -> Behavior:
    return Behavior({tpl.get("state", "move"): _stacks(tpl["move"], cfg)})


@_shape("telegraph_cycle")
def _cycle(tpl: dict, cfg: dict) -> Behavior:
    trig = tpl["trigger"]
    if trig is None:
        trigger_range = None                       # swing on the timer alone
    elif trig in actions.TRIGGERS:
        trigger_range = actions.TRIGGERS[trig](cfg)
    else:
        trigger_range = cfg[trig]
    t = tpl["timings"]
    hooks = {k: actions.ACTIONS[tpl[k]](cfg)
             for k in ("on_windup_start", "on_windup_end", "on_recover_start")
             if tpl.get(k)}
    return telegraph_cycle(
        chase=_stacks([tpl["chase"]], cfg),
        trigger_range=trigger_range,
        telegraph=cfg[t["telegraph"]],
        active=cfg[t["active"]],
        recover=cfg[t["recover"]],
        cooldown=cfg[t["cooldown"]],
        attack=actions.ATTACKS[tpl["attack"]](cfg) if tpl.get("attack") else None,
        recover_weight=cfg["recover_weight"],
        **hooks,
    )


def problems(name: str, tpl: dict, code_shapes) -> list[str]:
    """What is wrong with one template (empty when it builds)."""
    out = []
    shape = tpl.get("shape")
    if shape not in SHAPES and shape not in code_shapes:
        out.append(f"{name}: unknown shape {shape!r}")
    for s in tpl.get("move", ()):
        if s not in actions.STACKS:
            out.append(f"{name}: unknown stack {s!r}")
    if tpl.get("chase") and tpl["chase"] not in actions.STACKS:
        out.append(f"{name}: unknown chase stack {tpl['chase']!r}")
    for k in ("on_windup_start", "on_windup_end", "on_recover_start"):
        if tpl.get(k) and tpl[k] not in actions.ACTIONS:
            out.append(f"{name}: unknown action {tpl[k]!r}")
    if tpl.get("attack") and tpl["attack"] not in actions.ATTACKS:
        out.append(f"{name}: unknown attack {tpl['attack']!r}")
    return out
