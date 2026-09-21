"""The breadth-first jump tree, shared by Thunder and Superconduct.

Both spread the same way -- the closest `per_jump` enemies within
`max_range`, one jump level at a time, never the same enemy twice, stopping
at `max_targets` -- and differ only in what they do when they arrive. So the
walk lives here and the arriving is a callback.

`max_targets` is not optional: the worst case grows as
`per_jump + per_jump^2 + ... + per_jump^jumps`.

A node that died to the jump that reached it still arcs onward (the death
rule, 2026-09-21): the walk needs only where it was standing. Nothing is
ever *targeted* on a corpse, because `world.nearest` returns the living.
"""
from __future__ import annotations


def breadth_first(world, origin, *, jumps: int, per_jump: int, max_range: float,
                  max_targets: int, visit, arc=None) -> int:
    """Walk the tree from `origin`; return how many enemies it reached.

    `visit(target, level)` is called once per enemy reached, with `level`
    counting from 1, and returns whether the tree may continue from that
    enemy. `arc(from_pos, to_pos)` is an optional hook for the visual.
    """
    if jumps <= 0 or per_jump <= 0 or max_targets <= 0:
        return 0
    visited = {id(origin)}
    frontier = [origin]
    taken = 0

    for level in range(jumps):
        following = []
        for node in frontier:
            if taken >= max_targets:
                break
            room = min(per_jump, max_targets - taken)
            for hit in world.nearest(node.pos, room, max_range, exclude=visited):
                visited.add(id(hit))
                taken += 1
                if arc is not None:
                    arc(node.pos, hit.pos)
                if visit(hit, level + 1):
                    following.append(hit)
        frontier = following
        if not frontier or taken >= max_targets:
            break
    return taken
