"""SYS-008: the same seed plays the same run in any process.

Four child processes run `tools/verification/run_digest.py`'s script on
seed 123 -- the seed that used to drift -- side by side, under different
`PYTHONHASHSEED` values, and must produce the same digest.

Side by side on purpose: the drift this guards against came from the
flow-field fill being sliced by wall-clock time, which only showed under
load, and processes started together are load. The digest covers the
hero, the stats, every enemy, the pools, the ledger, the run RNG's state and
the camera after 720 frames with debug spawns and a level-up; the old drift
began after frame 600, so the whole script is kept.

Integration tier: four booted runs at once, a few seconds. It compares the two runs
with each other, not with the pin in `run_digests.json`, so a gameplay
change that moves the run does not break it -- only a run that no longer
repeats does.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = 123
_CHILD = ("from tools.verification.run_digest import run_digest; "
          f"print('DIGEST', run_digest({SEED}))")


def _start(hash_seed: str) -> subprocess.Popen:
    env = dict(os.environ, PYTHONHASHSEED=hash_seed,
               SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    return subprocess.Popen([sys.executable, "-c", _CHILD], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)


def _digest(proc: subprocess.Popen) -> str:
    out, _ = proc.communicate(timeout=600)
    lines = [ln for ln in out.splitlines() if ln.startswith("DIGEST ")]
    if proc.returncode != 0 or not lines:
        raise AssertionError(f"the child run failed (exit {proc.returncode}):\n{out[-2000:]}")
    return lines[-1].split()[1]


class RunDeterminismTests(unittest.TestCase):
    def test_one_seed_plays_one_run_across_processes_and_hash_seeds(self):
        """Four at once, not two: the drift showed in about one run in four
        under load, so more processes side by side is both more load and
        more draws. Each child is a few seconds (the worlds come from the
        disk cache)."""
        procs = [_start(h) for h in ("1", "2", "3", "4")]
        digests = [_digest(p) for p in procs]
        self.assertEqual(len(set(digests)), 1,
                         f"seed {SEED} played {len(set(digests))} different runs "
                         f"in {len(digests)} processes: {digests}")


if __name__ == "__main__":
    unittest.main()
