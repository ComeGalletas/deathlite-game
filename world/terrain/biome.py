"""Re-export shim: the palette rule lives in `world/gen/biomes.py` now.

It moved because the island's palette became generation output rather than a
rendering decision -- the obstacle scatter reads the biome too, and two modules
deriving the same answer from the same seed is how they come to disagree. This
module stays so `world.terrain.biome.floor_palette` keeps resolving; nothing
new should import it.
"""
from world.gen.biomes import floor_palette

__all__ = ["floor_palette"]
