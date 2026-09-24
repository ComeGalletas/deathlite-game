"""Rules of the height-map world checked on hand-built grids.

Worldgen R4 (`documentation/journals/worldgen_modularity_todo.md`): a test
that only needs *a* grid -- a predicate, a composition identity, a case the
rule must catch -- is written here on a grid small enough to read, and runs
in the `unit` tier (`tests/conftest.py` lists this package before the
`tests/world/` prefix). The generated-world sweeps that stay in
`tests/world/` are the ones only a generated world can make: that an
invariant survives a layout nobody drew by hand.
"""
