"""Milestone 2: object pool acquire / sweep / cap / reuse / clear."""
import unittest

from systems.object_pool import Pool


class Dummy:
    def __init__(self):
        self.active = False


class PoolTests(unittest.TestCase):
    def test_acquire_marks_active_and_tracks(self):
        pool = Pool(Dummy, max_size=4)
        a = pool.acquire()
        self.assertTrue(a.active)
        self.assertEqual(len(pool), 1)

    def test_cap_returns_none_not_crash(self):
        pool = Pool(Dummy, max_size=2)
        pool.acquire()
        pool.acquire()
        self.assertIsNone(pool.acquire())
        self.assertEqual(len(pool), 2)

    def test_sweep_reclaims_inactive_and_reuses_instance(self):
        pool = Pool(Dummy, max_size=4)
        a = pool.acquire()
        a.active = False
        reclaimed = pool.sweep()
        self.assertEqual(reclaimed, 1)
        self.assertEqual(len(pool), 0)
        b = pool.acquire()
        self.assertIs(b, a)  # recycled, not newly allocated

    def test_clear_deactivates_all(self):
        pool = Pool(Dummy, max_size=4)
        x, y = pool.acquire(), pool.acquire()
        pool.clear()
        self.assertEqual(len(pool), 0)
        self.assertFalse(x.active)
        self.assertFalse(y.active)


if __name__ == "__main__":
    unittest.main()
