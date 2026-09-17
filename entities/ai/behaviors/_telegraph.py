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
from entities.ai.machine import ATTACK_SLOT, time_in_state
from entities.ai.machine import Behavior, Transition


def telegraph_cycle(*, chase, trigger_range, telegraph, active, recover, cooldown,
                    attack=None, on_windup_start=None, on_windup_end=None,
                    on_recover_start=None, recover_via="nav",
                    recover_weight=0.3) -> Behavior:
    """`trigger_range=None` drops the distance gate: the wind-up then starts
    on the cooldown alone, wherever the actor is standing. That is what the
    Beekeeper wants -- it swings on a timer and the bees are the point, so
    waiting until it is touching the player would hold the summon hostage to a
    melee range it has no reason to reach (owner, 2026-09-17). Aggro still
    gates the whole behaviour, so it does not swing at a player it has not
    noticed.
    """
    cd = Cooldown(seconds=cooldown, start_ready=False)
    ready = _ready(cd)
    # `telegraph` may be a callable(actor) -> seconds, for an enemy whose
    # wind-up depends on which swing it picked (the Whirlspear's heavy whirl
    # is read for longer than its fast sweep).
    windup = (after(telegraph) if not callable(telegraph)
              else (lambda actor, per: time_in_state(actor) >= telegraph(actor)))
    start = ready if trigger_range is None else all_of(in_range(trigger_range), ready)

    def enter_attack(actor, per, cmb):
        if hasattr(actor, "contact_cd"):
            actor.contact_cd = 0.0          # old _fsm_enter("attack")
        if on_windup_end is not None:
            on_windup_end(actor, per, cmb)

    def leave_attack(actor, per, cmb):
        if on_recover_start is not None:
            on_recover_start(actor, per, cmb)

    def end_cycle(actor, per, cmb):
        # Whatever strip the swing named stops applying once the cycle is
        # over, or a multi-strip enemy would keep playing its last attack
        # frame while it walks (`Enemy._anim_name`). Only `anim` is cleared:
        # the slot also carries a swing counter that must survive.
        actor.bb.slot(ATTACK_SLOT).pop("anim", None)
        cd.trigger(actor)

    return Behavior(
        always=[cd],
        states={
            "chase": list(chase),
            "telegraph": [],
            "attack": list(attack or []),
            "recover": [SeekTarget(via=recover_via, slew=0.0, weight=recover_weight)],
        },
        transitions=[
            Transition("chase", "telegraph", when=start, on=on_windup_start),
            Transition("telegraph", "attack", when=windup, on=enter_attack),
            Transition("attack", "recover", when=after(active), on=leave_attack),
            Transition("recover", "chase", when=after(recover), on=end_cycle),
        ],
        initial="chase",
    )


def _ready(cd: Cooldown):
    return lambda actor, per: cd.ready(actor)
