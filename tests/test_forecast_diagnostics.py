import unittest

from polymarket_backtest.forecast_diagnostics import diagnose_forecasts


class ForecastDiagnosticsTest(unittest.TestCase):
    def test_diagnose_market_echo_midpoint_rows(self) -> None:
        result = diagnose_forecasts(
            [
                {"fair_yes": 0.51, "yes_bid": 0.50, "yes_ask": 0.52, "no_bid": 0.48, "no_ask": 0.50},
                {"fair_yes": 0.31, "yes_bid": 0.30, "yes_ask": 0.32, "no_bid": 0.68, "no_ask": 0.70},
            ]
        )

        self.assertEqual(result.records, 2)
        self.assertEqual(result.market_echo_rows_1bp, 2)
        self.assertEqual(result.market_echo_share_1bp, 1.0)
        self.assertAlmostEqual(result.mean_yes_edge_to_ask, -0.01)
        self.assertAlmostEqual(result.mean_no_edge_to_ask, -0.01)
        self.assertAlmostEqual(result.mean_positive_yes_edge_to_ask, 0.0)
        self.assertIn("market_echo", result.diagnosis_flags)
        self.assertIn("no_actionable_edges", result.diagnosis_flags)
        self.assertIn("missing_resolved_outcomes", result.diagnosis_flags)

    def test_diagnose_actionable_yes_and_no_edges(self) -> None:
        result = diagnose_forecasts(
            [
                {"fair_yes": 0.70, "yes_bid": 0.50, "yes_ask": 0.55, "no_bid": 0.43, "no_ask": 0.45},
                {"fair_yes": 0.20, "yes_bid": 0.18, "yes_ask": 0.22, "no_bid": 0.68, "no_ask": 0.70},
            ],
            edge_threshold=0.08,
        )

        self.assertEqual(result.yes_edge_ge_threshold, 1)
        self.assertEqual(result.no_edge_ge_threshold, 1)
        self.assertEqual(result.actionable_rows, 2)
        self.assertNotIn("no_actionable_edges", result.diagnosis_flags)

    def test_diagnose_no_quote_symmetry_and_invalid_fair_yes_rows(self) -> None:
        result = diagnose_forecasts(
            [
                {"fair_yes": "bad", "yes_bid": 0.50, "yes_ask": 0.52, "no_bid": 0.48, "no_ask": 0.50},
                {"fair_yes": 0.50, "yes_ask": 0.52, "no_ask": 0.48},
            ]
        )

        self.assertEqual(result.invalid_fair_yes_rows, 1)
        self.assertEqual(result.rows_with_yes_quotes, 0)
        self.assertEqual(result.rows_with_no_quotes, 0)
        self.assertIn("invalid_fair_yes_rows", result.diagnosis_flags)
        self.assertIn("missing_yes_quotes", result.diagnosis_flags)
        self.assertIn("missing_no_quotes", result.diagnosis_flags)

    def test_diagnose_brier_score_from_outcome_rows(self) -> None:
        result = diagnose_forecasts(
            [
                {"market_id": "m1", "fair_yes": 0.75, "yes_bid": 0.50, "yes_ask": 0.52},
                {"market_id": "m2", "fair_yes": 0.25, "yes_bid": 0.30, "yes_ask": 0.32},
                {"market_id": "m3", "fair_yes": 0.50, "yes_bid": 0.40, "yes_ask": 0.42},
            ],
            outcome_rows=[
                {"market_id": "m1", "resolved_outcome": "YES"},
                {"market_id": "m2", "resolved_outcome": "NO"},
                {"market_id": "m3", "resolved_outcome": ""},
            ],
        )

        self.assertEqual(result.brier_resolved_rows, 2)
        self.assertEqual(result.brier_excluded_rows, 1)
        self.assertAlmostEqual(result.brier_score, 0.0625)
        self.assertGreaterEqual(len(result.calibration_bins), 1)
        self.assertNotIn("missing_resolved_outcomes", result.diagnosis_flags)


if __name__ == "__main__":
    unittest.main()
