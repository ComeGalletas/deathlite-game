"""The island graph: BFS distances over the islands' links, and which island
is what -- its kind (what happens there) and its topography (what shape it
is). (WLD-013 removed the retired generator's plateau helpers, `_adjacency`,
`_rooted_tree` and `_grow_subtree`, which `_assign_floors` used.)"""
from __future__ import annotations

from collections import deque

from world.layout import Room
from world.gen.settings import settings_or_config
from world.gen.tuning import SPECIAL_KINDS, VILLAGE_KIND


def _distances(rooms: list[Room], source: int) -> dict[int, int]:
    dist = {source: 0}
    q = deque([source])
    while q:
        cur = q.popleft()
        for nb in rooms[cur].neighbors:
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                q.append(nb)
    return dist


def assign_topography(rooms, rng, boss_id, settings=None) -> None:
    """Give every island its shape type.

    Separate from `_assign_kinds` because the two are orthogonal: kind says what
    happens on an island, topography says what shape it is, and a shrine can sit
    on a small one. The boss island is the single fixed assignment -- big and
    relatively flat is what the brief asks of it -- and the rest are drawn by
    weight from the settings' topography table.

    The start island is deliberately *not* pinned. It gets whatever it draws,
    the same as any other, so the opening of a run is not always the same shape.
    """
    settings = settings_or_config(settings)
    table = settings.topographies
    pool = [(name, spec["weight"]) for name, spec in table.items()
            if spec.get("weight", 0) > 0]
    names = [n for n, _w in pool]
    weights = [w for _n, w in pool]
    for room in rooms:
        if room.id == boss_id:
            room.topography = settings.boss_topography
        elif room.kind == VILLAGE_KIND:
            # The other fixed assignment (HI-1): a village is flat and small
            # whatever it would have drawn, and it draws nothing.
            room.topography = settings.village_topography
        else:
            room.topography = rng.choices(names, weights=weights, k=1)[0]


def _pick_villages(rooms, rng, start_id, boss_id, dist, settings=None) -> list:
    """Which islands are villages (HI-1): between `settings.villages[0]` and
    `[1]` of them, drawn from the islands at a tree distance from the start
    inside `settings.village_distance`, never the boss.

    A hard floor of one: the forge has to exist somewhere. With three or
    more islands the start always has a non-boss neighbour -- the boss is
    the farthest island, so it can only be adjacent to the start when nothing
    else is -- but should the band ever come up empty the draw falls back to
    any island that is neither start nor boss rather than to none."""
    s = settings_or_config(settings)
    lo, hi = s.village_distance
    cands = sorted(r.id for r in rooms
                   if r.id not in (start_id, boss_id)
                   and lo <= dist.get(r.id, -1) <= hi)
    if not cands:
        cands = sorted(r.id for r in rooms if r.id not in (start_id, boss_id))
    n = min(rng.randint(*s.villages), len(cands))
    return sorted(rng.sample(cands, n))


def _assign_kinds(rooms, rng, start_id, boss_id, dist, settings=None) -> None:
    rooms[start_id].kind = "start"
    rooms[boss_id].kind = "boss"
    villages = _pick_villages(rooms, rng, start_id, boss_id, dist, settings)
    for rid in villages:
        rooms[rid].kind = VILLAGE_KIND
    others = [r.id for r in rooms
              if r.id not in (start_id, boss_id) and r.id not in villages]
    rng.shuffle(others)
    # One of each special where room budget allows; the rest stay "combat".
    #
    # `SPECIAL_KINDS` is empty today (owner, 2026-09-20 --
    # `journals/special_facilities_journal.md`), so this assigns nothing and
    # every island here stays "combat". Kept as the working template: naming
    # a kind in that tuple is all it takes to place one again. The shuffle
    # runs either way so parking the specials does not move the world RNG
    # stream for an unrelated reason.
    for kind, rid in zip(SPECIAL_KINDS, others):
        rooms[rid].kind = kind
