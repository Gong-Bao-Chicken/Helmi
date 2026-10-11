"""Mirror tests for web/scoring.js (runs without Node)."""

import unittest


def percentile_rank(values: list[float], value: float) -> float:
    sorted_vals = sorted(v for v in values if v is not None)
    below = sum(1 for v in sorted_vals if v < value)
    equal = sum(1 for v in sorted_vals if v == value)
    return (below + equal * 0.5) / len(sorted_vals)


def compute_value_from_percentiles(safety_pct: float, raw_price_pct: float) -> tuple[float, int]:
    value_index = safety_pct - raw_price_pct
    value_score = round((value_index + 1) * 50)
    return value_index, value_score


class ScoringLogicTests(unittest.TestCase):
    def test_safe_cheap_beats_safe_expensive(self) -> None:
        prices = [50.0, 100.0, 150.0, 200.0]
        safety = 0.9
        cheap = compute_value_from_percentiles(safety, percentile_rank(prices, 50.0))
        expensive = compute_value_from_percentiles(safety, percentile_rank(prices, 200.0))
        self.assertGreater(cheap[1], expensive[1])
        self.assertGreater(cheap[0], expensive[0])


if __name__ == "__main__":
    unittest.main()
