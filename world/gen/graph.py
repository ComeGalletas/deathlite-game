"""The island graph: adjacency, BFS distances, and which island is what --
its kind (what happens there) and its topography (what shape it is)."""
from __future__ import annotations

from collections import deque

from world.layout import Room
from world.gen.settings import settings_or_config
from world.gen.tuning import SPECIAL_KINDS


def _adjacency(rooms, edges) -> dict:
    adj = {r.id: [] for r in rooms}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    for rid in adj:
        adj[rid].sort()
    return adj


def _rooted_tree(rooms, edges, root):
    """`(parent, children)` for the room tree rooted at `root`. `edges` is
    already `(parent_in_growth, child)` but generation may root elsewhere, so
    re-root from `root` explicitly."""
    adj = _adjacency(rooms, edges)
    parent = {root: -1}
    kids = {r.id: [] for r in rooms}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in parent:
                parent[v] = u
                kids[u].append(v)
                q.append(v)
    return parent, kids


def _grow_subtree(seed: int, kids: dict, size: int, blocked: set) -> list:
    """Deterministic BFS over the seed's **descendants only** (down `kids`), up
    to `size` rooms, skipping any subtree rooted at a `blocked` room. The result
    is always a connected subtree whose single boundary edge is `seed`'s edge to
    its parent -- so a raised region grown this way needs exactly one stair."""
    out: list = []
    q = deque([seed])
    while q and len(out) < size:
        cur = q.popleft()
        if cur in blocked:
            continue
        out.append(cur)
        for k in kids[cur]:
            q.append(k)
    return out



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
        else:
            room.topography = rng.choices(names, weights=weights, k=1)[0]


def _assign_kinds(rooms, rng, start_id, boss_id, dist) -> None:
    rooms[start_id].kind = "start"
    rooms[boss_id].kind = "boss"
    others = [r.id for r in rooms if r.id not in (start_id, boss_id)]
    rng.shuffle(others)
    # One of each special where room budget allows; the rest stay "combat".
    for kind, rid in zip(SPECIAL_KINDS, others):
        rooms[rid].kind = kind
