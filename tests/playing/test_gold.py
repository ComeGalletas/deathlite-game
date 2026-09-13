"""The run's gold accounting: a spendable balance and a run total, together.

The end screens report the gold **earned** over a run, not what is left after
the Merchant (owner, 2026-09-12): pick up 200, spend 50, and the summary says
200. `stats["gold"]` alone cannot answer that -- it is the balance, and the
merchant subtracts from it -- so `PlayingState` keeps both in one pair of
methods rather than asking every income site to remember a second counter.

`add_gold` / `spend_gold` touch nothing but `self.stats`, so they are exercised
against a stand-in rather than a booted run; `tests/playing/test_interactables.py`
covers the merchant end to end.
"""
import unittest
from types import SimpleNamespace

from game.states.playing.core.state import PlayingState


def _ps(gold=0, earned=0):
    return SimpleNamespace(stats={"gold": gold, "gold_earned": earned})


def add(ps, n):
    return PlayingState.add_gold(ps, n)


def spend(ps, n):
    return PlayingState.spend_gold(ps, n)


class AddTests(unittest.TestCase):
    def test_earning_moves_the_balance_and_the_total_together(self):
        ps = _ps()
        self.assertEqual(add(ps, 200), 200)
        self.assertEqual(ps.stats["gold"], 200)
        self.assertEqual(ps.stats["gold_earned"], 200)

    def test_earnings_accumulate(self):
        ps = _ps()
        for n in (10, 25, 5):
            add(ps, n)
        self.assertEqual(ps.stats["gold_earned"], 40)

    def test_zero_and_negative_amounts_are_ignored(self):
        ps = _ps(100, 100)
        for n in (0, -5, -100):
            self.assertEqual(add(ps, n), 0)
        self.assertEqual((ps.stats["gold"], ps.stats["gold_earned"]), (100, 100))

    def test_a_summary_without_the_total_yet_still_adds(self):
        # A run built before `gold_earned` existed (or a stand-in that omits
        # it) must not raise on the first coin.
        ps = SimpleNamespace(stats={"gold": 0})
        add(ps, 7)
        self.assertEqual(ps.stats["gold_earned"], 7)


class SpendTests(unittest.TestCase):
    def test_spending_is_not_un_earning(self):
        """The owner's example, exactly: earn 200, spend 50, report 200."""
        ps = _ps()
        add(ps, 200)
        self.assertTrue(spend(ps, 50))
        self.assertEqual(ps.stats["gold"], 150)
        self.assertEqual(ps.stats["gold_earned"], 200)

    def test_it_refuses_what_the_balance_cannot_cover(self):
        ps = _ps(40, 40)
        self.assertFalse(spend(ps, 41))
        self.assertEqual(ps.stats["gold"], 40, "a refused purchase took gold")

    def test_it_can_spend_the_balance_exactly(self):
        ps = _ps(40, 40)
        self.assertTrue(spend(ps, 40))
        self.assertEqual(ps.stats["gold"], 0)
        self.assertEqual(ps.stats["gold_earned"], 40)

    def test_zero_and_negative_amounts_buy_nothing(self):
        ps = _ps(40, 40)
        for n in (0, -5):
            self.assertFalse(spend(ps, n))
        self.assertEqual(ps.stats["gold"], 40)

    def test_the_balance_can_never_go_negative(self):
        ps = _ps(100, 100)
        for _ in range(20):
            spend(ps, 30)
        self.assertGreaterEqual(ps.stats["gold"], 0)
        self.assertEqual(ps.stats["gold_earned"], 100)



if __name__ == "__main__":
    unittest.main()
