"""The in-run status screen's panes (journal:
`documentation/journals/run_status_journal.md`).

One module per pane -- `overview`, `build`, `blessings` -- and `common` for
what they share: the dim layer, the ribbon tabs, the row primitives and the
stat formatting. `RunStatusState` (`game/states/run_status_state.py`) owns
the input and asks the active pane to draw.
"""
from ui.run_status.blessings import BlessingsPane
from ui.run_status.build import BuildPane
from ui.run_status.overview import OverviewPane

__all__ = ["OverviewPane", "BuildPane", "BlessingsPane"]
