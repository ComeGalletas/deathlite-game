"""Code-built behaviour shapes. Importing this package runs the `@behavior`
decorators; `entities/ai/__init__` imports it so `build_behavior` just works.

Most behaviours are templates in `data/enemies/behaviors.json` (ENT-017)
built by `entities/ai/templates.py`; these are the shapes a template can name
that are not a plain `move` or `telegraph_cycle`.
"""
from entities.ai.behaviors import boss, melee, ranged  # noqa: F401  -- @behavior registration
