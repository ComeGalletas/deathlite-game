"""`telegraph_cycle` -- the shared chase -> telegraph -> attack -> recover shape
(the old `_fsm_common`), assembled from R4 pieces.

The attack's one-shot fires on the `telegraph -> attack` transition (exact
timing, matching the old `on_attack_start`); a continuous attack (a dash) puts a
per-frame component in the `attack` state instead. `recover` drifts toward the
player at `recover_weight * speed`. The `Cooldown` sits in `always=[...]` so it
counts down in every phase, and is reloaded on `recover -> chase`.
"""
from __future__ import annotations

from entities.ai.components import Cooldown, SeekTarget, after, all_of, in_range
from entities.ai.machine import Behavior, Transition


def telegraph_cycle(*, chase, trigger_range, telegraph, active, recover, cooldown,
                    attack=None, on_windup_start=None, on_windup_end=None,
                    recover_via="nav", recover_weight=0.3) -> Behavior:
    cd = Cooldown(seconds=cooldown, start_ready=False)

    def enter_attack(actor, per, cmb):
        if hasattr(actor, "contact_cd"):
            actor.contact_cd = 0.0          # old _fsm_enter("attack")
        if on_windup_end is not None:
            on_windup_end(actor, per, cmb)

    return Behavior(
        always=[cd],
        states={
            "chase": list(chase),
            "telegraph": [],
            "attack": list(attack or []),
            "recover": [SeekTarget(via=recover_via, slew=0.0, weight=recover_weight)],
        },
        transitions=[
            Transition("chase", "telegraph",
                       when=all_of(in_range(trigger_range), _ready(cd)),
                       on=on_windup_start),
            Transition("telegraph", "attack", when=after(telegraph), on=enter_attack),
            Transition("attack", "recover", when=after(active)),
            Transition("recover", "chase", when=after(recover),
                       on=lambda a, p, c: cd.trigger(a)),
        ],
        initial="chase",
    )


def _ready(cd: Cooldown):
    return lambda actor, per: cd.ready(actor)
