"""Registered behaviour builders. Importing this package runs the `@behavior`
decorators; `entities/ai/__init__` imports it so `build_behavior` just works.
"""
from entities.ai.behaviors import boss, melee, ranged, simple  # noqa: F401  -- @behavior registration
