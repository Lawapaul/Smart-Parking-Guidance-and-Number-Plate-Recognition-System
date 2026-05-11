"""Basic tests for demo explanation text."""

import unittest

from src.reasoning.explainer import explain_snapshot


class ReasoningTests(unittest.TestCase):
    """Verify the user-facing summary remains informative."""

    def test_explainer_mentions_recommendation(self) -> None:
        snapshot = {
            "parking": {"total": 6, "available": 2, "occupied": 4, "efficiency": 66.67},
            "recommendation": {"slot": {"label": "P2-S3"}},
            "latest_vehicle": {"plate_text": "DEMO-001"},
        }
        summary = explain_snapshot(snapshot)
        self.assertIn("P2-S3", summary)
        self.assertIn("DEMO-001", summary)


if __name__ == "__main__":
    unittest.main()
