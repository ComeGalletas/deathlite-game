"""The spawn master (`documentation/spawn_master_design.md`).

Owns where enemies may appear, how many exist at once and in what mix, and
which of them are simulated this frame. Built up phase by phase
(`documentation/spawn_master_todo.md`): S1 the point records and their
index (`points`), S2 the schedule tables (`tables`) and the budget director
(`budget`), S3 the `Host` protocol (`host`), placement (`placement`) and
the `SpawnMaster` facade (`master`), S4 the active zone (`locality`) and
the live / dormant registry (`population`), S5 the watchdog (`watchdog`),
S6 the pacing signal (`pacing`). Nothing under this package imports `entities` or `game.states`:
the run reaches it through one narrow adapter.
"""
from spawn.points import PointIndex, ResourcePoint, SpawnPoint
from spawn.tables import SpawnTables, TableError
from spawn.host import Host
from spawn.placement import Placement, SpawnRequest
from spawn.locality import Locality
from spawn.population import DormantEnemy, Population
from spawn.watchdog import Verdict, Watchdog
from spawn.pacing import Pacing
from spawn.master import (ENEMY_RECYCLED, ENEMY_SPAWNED, ROOM_ACTIVATED, ROOM_DORMANT,
                          SpawnMaster)

__all__ = ["PointIndex", "ResourcePoint", "SpawnPoint", "SpawnTables", "TableError",
           "Host", "Placement", "SpawnRequest", "SpawnMaster", "ENEMY_SPAWNED",
           "Locality", "DormantEnemy", "Population", "ROOM_ACTIVATED", "ROOM_DORMANT",
           "Watchdog", "Verdict", "ENEMY_RECYCLED", "Pacing"]
