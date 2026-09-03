"""Rules shared by generation, baking and the runtime.

A layer, not a dumping ground. Everything here reads the data model
(`world.layout`) and the terrain data, and nothing else in `world/`:
generation, the terrain painters, the collider and the navigation grid all
import *from* here and are never imported *by* it.
`tests/world/test_layering.py` enforces the direction.

    frontier   where a prop may stand relative to a level change
    inset      how far inside its own terrace a point stands (the field)
    floor      is a world point on floor, and on which island
    steps      may a body step from one tile to the next
    biome      what a tileset is: its biome, its surf, its scatter mix
"""
