"""The aura's shed: a trickle of motes off every primed body (RND-011).

It used to run inside the draw, one roll per drawn aura, on the run's own
random stream. That made the shed as dense as the draw was fast (about 3x
in the browser, paced at the display's 175 Hz, against the desktop's 62 fps
cap), and made gameplay's random numbers depend on how many frames had been
drawn. Here it runs once per update step instead, at a rate per second, on
a stream of its own:

* **a chance of `rate * dt`** per body per step (RND-011.D2). One roll, no
  per-body state: with a crowd this large the average is what matters, and
  a float per enemy would cost more than the particle. The whole part of
  `rate * dt` sheds for certain and only the fraction is rolled, so the
  mean is exact at any step length.
* **its own RNG**, `ElementVisuals.rng`, seeded from the run (RND-011.D1),
  so `run.rng` never sees it and the same seed sheds from the same bodies,
  as many motes, on the same steps. (Each mote's direction, speed and life
  are `ParticleSystem.burst`'s, drawn on the process-wide `random`, which
  gameplay does not use; that part was never seeded.)
* **the elemental budget**, refilled here for the step's length
  (RND-011.D3), still has the last word on how many are born.

The bodies are the ones the draw paints an aura on: in view with the draw's
pad, in `_bodies` order. An aura off screen sheds nothing, as before.
"""
from __future__ import annotations

from game.states.playing.visual.elements import layers


def update(run, dt: float) -> int:
    """Shed this step's motes. Returns how many were born."""
    visuals = getattr(run, "element_visuals", None)
    particles = getattr(run, "particles", None)
    if visuals is None or particles is None or dt <= 0.0:
        return 0
    budget, profiles, rng = visuals.budget, visuals.profiles, visuals.rng
    budget.begin_step(dt)
    now = run.stats["time"]
    born = 0
    for body in layers.in_band(run, None):
        state = getattr(body, "elemental", None)
        if state is None:
            continue
        element = state.element(now)
        if not element:
            continue
        profile = profiles[element]
        p = profile.particles
        owed = p.rate * dt
        count = int(owed)
        if rng.random() < owed - count:
            count += 1
        if count <= 0:
            continue
        granted = budget.take(element, count)
        if granted <= 0:
            continue
        # `under`: the shed is part of the aura, and the aura draws behind
        # the body wearing it (M10 rule 3). Without this the one elemental
        # visual the elements package does not draw itself would be the one
        # visual still sitting on top of the crowd.
        particles.burst(body.pos, profile.colour, count=granted, speed=p.speed,
                        life=p.life, radius=p.radius, under=True)
        born += granted
    return born
