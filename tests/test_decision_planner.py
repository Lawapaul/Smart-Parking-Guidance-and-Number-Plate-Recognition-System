"""Basic tests for the slot recommendation logic."""

import unittest

from src.decision.planner import recommend_slot


class DecisionPlannerTests(unittest.TestCase):
    """Verify the recommendation helper returns a stable result."""

    def test_recommend_slot_returns_best_candidate(self) -> None:
        slots = [
            {"label": "P1-S1", "x": 0, "y": 0, "w": 50, "h": 100, "is_occupied": False},
            {"label": "P1-S2", "x": 60, "y": 0, "w": 50, "h": 100, "is_occupied": False},
        ]
        recommendation = recommend_slot(slots)
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation["slot"]["label"], "P1-S1")


if __name__ == "__main__":
    unittest.main()
