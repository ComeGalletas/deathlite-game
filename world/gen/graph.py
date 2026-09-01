"""Connectivity graph, floor assignment, room-kind assignment, BFS distances
(W1 split of world/procedural.py)."""
from __future__ import annotations

from collections import deque

from world.layout import Room
from game import config
from world.gen.tuning import (
    SPECIAL_KINDS, special_kinds, _VERT_REGIONS, _VERT_REGION_ROOMS, _VERT_F2_CHANCE,
    _VERT_F3_CHANCE,
)


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


def _assign_floors(rooms, edges, rng, start_id, boss_id) -> None:
    """Raise a couple of plateaus onto the room tree. Each is a **subtree** so it
    has exactly one edge to lower ground -> one stair -> a clean pinch (LD-1
    decision: open areas joined by small pathways). Floors 0..3; floor 3 is a
    tiny tail of a floor-2 area; a final settle pass keeps every tree edge within
    a 2-floor gap."""
    parent, kids = _rooted_tree(rooms, edges, start_id)
    # candidate subtree roots: not start, not a child of start (keep the opening
    # on the ground), and with enough descendants to be a real plateau.
    def _descendants(n):
        c = 0
        stack = list(kids[n])
        while stack:
            c += 1
            stack.extend(kids[stack.pop()])
        return c

    cand = [r.id for r in rooms
            if r.id != start_id and parent[r.id] != start_id
            and _descendants(r.id) + 1 >= _VERT_REGION_ROOMS[0]]
    rng.shuffle(cand)
    raised: set = set()

    for _ in range(rng.randint(*_VERT_REGIONS)):
        seed = next((c for c in cand
                     if c not in raised and parent[c] not in raised), None)
        if seed is None:
            break
        blob = _grow_subtree(seed, kids, rng.randint(*_VERT_REGION_ROOMS), raised)
        blob_set = set(blob)
        for rid in blob:
            rooms[rid].floor = 1
            raised.add(rid)
        # escalate the deep tail of the subtree to floor 2 (still one boundary
        # edge -> one 1->2 stair, plus one 2->1 stair only if it stops short).
        if len(blob) >= 3 and rng.random() < _VERT_F2_CHANCE:
            # deepest room of the subtree that still has a child inside the blob
            inner = [n for n in blob if any(k in blob_set for k in kids[n])]
            f2_seed = min(inner or blob, key=_descendants)
            f2 = [n for n in _grow_subtree(f2_seed, kids, len(blob), set())
                  if n in blob_set]
            for rid in f2:
                rooms[rid].floor = 2
            # tiny floor-3 tail: a leaf of the floor-2 area (parent already f2).
            if len(f2) >= 2 and rng.random() < _VERT_F3_CHANCE:
                leaves = [n for n in f2 if not any(k in blob_set for k in kids[n])]
                f3_seed = min(leaves, key=_descendants) if leaves else None
                if f3_seed is not None and rooms[parent[f3_seed]].floor >= 2:
                    rooms[f3_seed].floor = 3       # interior to the floor-2 area

    rooms[start_id].floor = 0
    changed = True
    while changed:
        changed = False
        for a, b in edges:
            hi = a if rooms[a].floor >= rooms[b].floor else b
            lo = b if hi == a else a
            if rooms[hi].floor - rooms[lo].floor > 2:
                rooms[hi].floor -= 1
                changed = True


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


def assign_topography(rooms, rng, boss_id) -> None:
    """Give every island its shape type.

    Separate from `_assign_kinds` because the two are orthogonal: kind says what
    happens on an island, topography says what shape it is, and a shrine can sit
    on a small one. The boss island is the single fixed assignment -- big and
    relatively flat is what the brief asks of it -- and the rest are drawn by
    weight from `config.HEIGHTMAP_TOPOGRAPHIES`.

    The start island is deliberately *not* pinned. It gets whatever it draws,
    the same as any other, so the opening of a run is not always the same shape.
    """
    if not config.HEIGHTMAP_ROOMS:
        return
    table = config.HEIGHTMAP_TOPOGRAPHIES
    pool = [(name, spec["weight"]) for name, spec in table.items()
            if spec.get("weight", 0) > 0]
    names = [n for n, _w in pool]
    weights = [w for _n, w in pool]
    for room in rooms:
        if room.id == boss_id:
            room.topography = config.HEIGHTMAP_BOSS_TOPOGRAPHY
        else:
            room.topography = rng.choices(names, weights=weights, k=1)[0]


def _assign_kinds(rooms, rng, start_id, boss_id, dist) -> None:
    rooms[start_id].kind = "start"
    rooms[boss_id].kind = "boss"
    others = [r.id for r in rooms if r.id not in (start_id, boss_id)]
    rng.shuffle(others)
    # One of each special where room budget allows; the rest stay "combat".
    for kind, rid in zip(special_kinds(config.HEIGHTMAP_ROOMS), others):
        rooms[rid].kind = kind
