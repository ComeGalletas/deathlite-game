"""How a run ends (structure review, D3; journal: end_banner_journal.md).

Three steps. `begin` is what the hero's death and the boss kill call: it
snapshots the summary *now* -- the time and gold the screens show are the
run's at the moment the outcome was decided -- and pushes the end banner
over the run, which calls `hand_off` when its sprite has played. `end` is
the two back to back with no banner, for callers that want the summary
screen at once (tests, mostly). `ending_sequence` is what the run does
under the banner: no input, no combat, only what is in flight plays out.

`PlayingState` keeps `_begin_end`, `_end_run`, `_snapshot_summary`,
`_restart_dev_run` and the `_ending` flag as forwarders here.
"""
from __future__ import annotations

from game.events import Events


class RunEnd:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        # Set the frame the outcome is decided (HP at zero, or the boss down):
        # the run stops taking input and fighting, keeps animating its effects
        # under the end banner, and hands off when the banner is done.
        self.ending = False

    def begin(self, *, victory: bool) -> None:
        if self.ending:
            return
        self.ending = True
        summary = self.snapshot_summary(victory)
        from game.states.end_banner_state import EndBannerState
        game = self.run.game
        game.state_machine.push(EndBannerState(game), victory=victory,
                                on_done=lambda: self.hand_off(summary, victory))

    def end(self, *, victory: bool) -> None:
        self.ending = True
        self.hand_off(self.snapshot_summary(victory), victory)

    def ending_sequence(self, dt: float) -> None:
        """The run under the end banner's wait phase: no input, no combat, no
        enemy motion and no clock -- only what is already in flight plays
        out (the hero's last animation, the death poof, the boss burst,
        particles, damage numbers, the shake). The banner overlay stops
        calling this once its sprite starts, and ends the run itself."""
        ps, run = self.ps, self.run
        ps.hero.update(dt)
        ps.fx.update_death_fx(dt)
        ps.fx.update_trail_fx(dt)
        ps.fx.update_spawn_fx(dt)
        run.camera.update(dt, run.player.pos)
        run.particles.update(dt)
        run.damage_numbers.update(dt)
        run.shake.update(dt)

    def snapshot_summary(self, victory: bool) -> dict:
        ps, run = self.ps, self.run
        player, content = run.player, run.content
        summary = dict(run.stats)
        summary["weapons"] = [(w.name, w.level) for w in player.weapons]
        summary["seed"] = run.seed
        summary["difficulty"] = run.difficulty
        summary["character"] = content.character(run.character_id)["name"]
        summary["character_id"] = run.character_id
        summary["blessings"] = dict(player.blessings)
        # The game-over readout (`ui/run_summary.py`): the per-weapon damage
        # split with DPS over the held span, the proc rows, kills per type,
        # blessings by name. Nothing above is renamed -- the save, the
        # rankings and the victory screen read the keys they always did.
        end = run.stats["time"]
        held = [w.weapon_id for w in player.weapons]
        names = {wid: d.get("name", wid) for wid, d in content.weapons.items()}
        lib = ps.blessing_lib
        names.update({bid: b.name for bid, b in lib.by_id.items()})
        summary["weapon_rows"] = run.ledger.weapon_rows(player.weapons, end)
        summary["other_rows"] = run.ledger.other_rows(held, names, end)
        summary["kill_rows"] = run.ledger.kill_rows()
        summary["blessing_rows"] = [
            (lib.by_id[bid].name if bid in lib.by_id else bid, lvl)
            for bid, lvl in player.blessings.items()]
        summary["damage_by_source"] = dict(run.ledger.damage)
        # The end screens are one piece of code (`ui/end_screen.py`), so what
        # makes a win a win travels in the dict rather than in two renderers.
        summary["victory"] = victory
        boss = ps.rewards.boss_defeated
        if boss is not None:
            summary["boss_id"], summary["boss"] = boss
        # Read *before* the RUN_ENDED publish below: `Game._on_run_ended` calls
        # `save.mark_cleared`, so asking afterwards always answers "already
        # cleared" and the first-clear reward could never be announced.
        save = run.game.save
        summary["first_clear"] = bool(
            victory and not save.hero_cleared(run.character_id))
        # Same ordering trap, same reason: `record_best` in that handler
        # overwrites the values this compares against, so afterwards no run
        # has ever beaten anything. A dev run banks nothing, so it sets no
        # records and must not claim any.
        summary["new_records"] = ([] if run.dev_mode else
                                  save.beaten_records(summary, run.difficulty))
        # The hero's resolved build. The run-status screen reads `player.stats`
        # live; a screen shown after the run is over cannot, so it is snapshot.
        # `player.stats` is already the resolved plain dict (the `StatSet`
        # itself is `player.statset`), so this is a copy, not a recompute.
        summary["trait"] = getattr(player, "trait", "")
        summary["hero_stats"] = dict(getattr(player, "stats", None) or {})
        summary["equipment"] = [
            {"name": it.name, "rarity": it.rarity, "slot": it.slot, "level": it.level}
            for it in getattr(player, "equipment", ())]
        return summary

    def hand_off(self, summary: dict, victory: bool) -> None:
        run = self.run
        game = run.game
        game.events.publish(Events.RUN_ENDED, stats=summary, victory=victory,
                            dev=run.dev_mode)
        if run.dev_mode:
            # A dev run never shows a summary or banks anything -- it just wipes
            # back to a clean level-1 state on the same world (the "Reset run"
            # behaviour, also triggered on death).
            self.restart_dev_run()
            return
        if victory:
            from game.states.victory_state import VictoryState
            game.state_machine.change(VictoryState(game), stats=summary)
        else:
            from game.states.game_over_state import GameOverState
            game.state_machine.change(GameOverState(game), stats=summary)

    def restart_dev_run(self) -> None:
        """Reload the developer run from scratch: same world seed, fresh hero,
        level 1, no blessings / items / upgrades, enemies cleared."""
        from game.states.loading_state import LoadingState
        run = self.run
        run.game.state_machine.change(
            LoadingState(run.game), character_id=run.character_id,
            seed=run.seed, dev=True)
