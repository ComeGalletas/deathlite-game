"""Scene composition: the world, one terrace at a time (structure review, D3).

`draw_world` is the paint order of a frame's world layer -- the sea, then
for each terrace its ground, the flat effects lying on it and the sprites
standing on it, then the ghost silhouettes. `actor_items` lists the
characters with the band each stands in; `depth_items` is the flat,
untagged view of the same list the ordering tests describe.
`PlayingState.draw` calls `draw_world` and keeps `_depth_items`,
`_actor_items`, `_draw_world` and `_draw_flat_effects` as forwarders for
the tests that call them.
"""
from __future__ import annotations

from game import config
from game.states.playing.visual import elements as element_fx
from game.states.playing.visual import cast_marker, slam_fx, slash_fx


def depth_items(ps) -> list:
    """`(depth_y, draw_fn)` for the whole sprite layer -- map scenery
    (obstacles + interior decorations) plus the characters -- sorted
    back-to-front by ground-contact Y, ignoring which terrace each stands
    on.

    `draw_world` composites band by band instead, so this is no longer the
    paint order for a world with terraces; it stays as the flat view of the
    same items, which is what the ordering tests describe and what a
    single-level world still paints exactly.
    """
    r = ps.game_map.renderer
    items = [(depth, fn) for _lvl, depth, fn in r.banded_scenery(ps.camera)]
    items += [(depth, fn) for _lvl, depth, fn in actor_items(ps)]
    items.sort(key=lambda t: t[0])
    return items


def draw_world(ps, surface) -> None:
    """The world, composited one terrace at a time: sea, then for each
    level its ground, the flat effects lying on it, and the sprites
    standing on it.

    A5. The whole world used to be painted before any sprite, so a sprite
    on a low terrace was drawn over every terrace above it -- its art
    reaches beyond its own cell, and an island bakes as one surface, so
    nothing could cover it. Banding the ground and slotting the sprites in
    is what makes a higher terrace occlude what stands below it, while the
    stone a character is standing *in front of* still sits behind them:
    a wall bands with the terrace it drops onto, not the one it holds up
    (`grid_paint.paint_room_levels`).

    Flat effects -- pickups, hazard discs, dust -- go between a band and
    its sprites, which is exactly where they were relative to the terrain
    and the characters before this existed.
    """
    r = ps.game_map.renderer
    r.begin_frame()
    r.draw_water(surface, ps.camera)
    scenery = r.banded_scenery(ps.camera)
    actors = actor_items(ps)
    levels = sorted({lvl for lvl, _d, _f in scenery}
                    | {lvl for lvl, _d, _f in actors}
                    | set(r.ground_levels()))
    for level in levels:
        r.draw_ground_band(surface, ps.camera, level)
        draw_flat_effects(ps, surface, level)
        items = [(d, f) for lvl, d, f in scenery if lvl == level]
        items += [(d, f) for lvl, d, f in actors if lvl == level]
        items.sort(key=lambda t: t[0])
        for _depth, fn in items:
            fn(surface)
    # After every band: the bodies that ended up behind obstacle art are
    # drawn again through it as translucent silhouettes.
    r.ghost_pass(surface, ps.camera)


def draw_flat_effects(ps, surface, level: int) -> None:
    """Everything that lies flat on one terrace: interactables, hazard
    discs, gems, explosion rings, dust trails and the player's own shots.

    Filtered by level rather than drawn once, because they belong under the
    characters standing on their own terrace -- which is where they were
    before the world was banded.
    """
    ren = ps.renderer
    ren.interactables(surface, level)
    ren.chests(surface, level)     # CB-9: treasure chests
    ren.hazards(surface, level)
    cast_marker.draw(surface, ps, level)          # ENT-013: where a cast will land
    slam_fx.draw_indicators(surface, ps, level)   # CR1: the pending swing
    ren.gems(surface, level)
    ren.potions(surface, level)   # CB-8: health potion drops
    ren.explosions(surface, level)
    slam_fx.draw_impacts(surface, ps, level)      # CR1: the blow
    slash_fx.draw(surface, ps, level)             # the Sword's swing sequence
    ren.trail_fx(surface, level)
    ps._draw_player_projectiles(surface, level)   # patchable: the order test hooks it
    # The elemental state of this terrace, last of the flat effects so it
    # sits directly under the sprites standing on the same band (M10 rule 3).
    element_fx.draw_under(surface, ps.run, level)


def actor_items(ps) -> list:
    """`(level, depth_y, draw_fn)` for the characters -- hero, enemies,
    boss, summons and the one-shot death poofs. The draw functions go
    through the state's `_draw_*` forwarders, which a test may patch on
    the instance."""
    run = ps.run
    lvl = ps.game_map.renderer.level_at
    top = ps.game_map.renderer.top_level_at

    def band(body) -> int:
        # A flyer is over the terrain, so it sits in the band of whatever
        # stands under it (a cliff wall included); a walker in the band
        # of the floor it stands on.
        if getattr(body, "flying", False):
            return top(body.pos.x, body.pos.y)
        return lvl(body.pos.x, body.pos.y)

    # Only what can be seen: every live body used to be listed, drawn and
    # shaded whether or not it was anywhere near the view.
    pad = config.RENDER_ACTOR_CULL_PAD
    view = run.camera.visible_rect().inflate(2 * pad, 2 * pad)
    out = [(band(e), e.pos.y,
            lambda s, e=e: ps._draw_one_enemy(s, e)) for e in run.enemies
           if view.collidepoint(e.pos.x, e.pos.y)]
    for fx in run.death_fx:
        if view.collidepoint(fx[1].x, fx[1].y):
            out.append((lvl(fx[1].x, fx[1].y), fx[1].y,
                        lambda s, fx=fx: ps._draw_death_fx(s, fx)))
    for fx in run.spawn_fx:
        body = fx[1]
        if view.collidepoint(body.pos.x, body.pos.y):
            # Just over the body it announces (+0.5), in the body's band.
            out.append((band(body), body.pos.y + 0.5,
                        lambda s, fx=fx: ps._draw_spawn_fx(s, fx)))
    boss = run.boss
    if (boss is not None and boss.alive
            and view.inflate(2 * pad, 2 * pad).collidepoint(boss.pos.x, boss.pos.y)):
        out.append((band(boss), boss.pos.y, ps._draw_boss))
    for sm in run.summons:
        if view.collidepoint(sm.pos.x, sm.pos.y):
            out.append((lvl(sm.pos.x, sm.pos.y), sm.pos.y,
                        lambda s, sm=sm: ps._draw_one_summon(s, sm)))
    out.extend(ps.npc_manager.actor_items(view, lvl))
    out.extend(ps.fish_hut_manager.actor_items(view, lvl))
    out.append((lvl(run.player.pos.x, run.player.pos.y),
                run.player.pos.y, ps._draw_player))
    return out
