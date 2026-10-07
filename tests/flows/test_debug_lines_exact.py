"""RND-010.5: computing the F1 overlay's lines changes nothing in the run.

Since RND-010.5 `report_debug` runs only while the overlay is shown. That
skipping it is exact rests on it changing no run state: every call it makes
reads (`active_auras`, the counters, `vis.report()`, the DPS summary). This
holds that for good, so a side effect added to it later is caught: seed 123
is played twice by `tools/verification/run_digest.py`, once with the
overlay hidden and once shown, and the two runs' digests (the hero, the
stats, every enemy, the pools, the ledger, the run RNG and the camera after
720 frames with debug spawns and a level-up) are the same.

Two child processes side by side, as `test_run_determinism` runs them, so
each run gets a fresh interpreter. Integration tier.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = 123


def _start(overlay: bool) -> subprocess.Popen:
    child = ("from tools.verification.run_digest import run_digest; "
             f"print('DIGEST', run_digest({SEED}, overlay={overlay}))")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    return subprocess.Popen([sys.executable, "-c", child], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _digest(proc: subprocess.Popen) -> str:
    out, _ = proc.communicate(timeout=600)
    lines = [ln for ln in out.splitlines() if ln.startswith("DIGEST ")]
    if proc.returncode != 0 or not lines:
        raise AssertionError(f"the child run failed (exit {proc.returncode}):\n{out[-2000:]}")
    return lines[-1].split()[1]


class DebugLinesExactTests(unittest.TestCase):
    def test_the_run_is_the_same_with_the_overlay_hidden_or_shown(self):
        hidden, shown = _start(False), _start(True)
        self.assertEqual(_digest(hidden), _digest(shown))


if __name__ == "__main__":
    unittest.main()
