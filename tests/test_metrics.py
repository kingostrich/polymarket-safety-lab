import unittest

from polymarket_backtest.metrics import (
    bin_forecasts_for_calibration,
    calibration_report_from_rows,
    compute_brier_score,
)


class MetricsTest(unittest.TestCase):
    def test_perfect_forecast_brier_is_zero(self) -> None:
        self.assertEqual(compute_brier_score([1.0, 0.0], ["YES", "NO"]), 0.0)

    def test_half_probability_forecast_brier_is_quarter(self) -> None:
        self.assertEqual(compute_brier_score([0.5, 0.5], ["YES", "NO"]), 0.25)

    def test_invalid_probability_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "probability"):
            compute_brier_score([1.2], ["YES"])

    def test_unresolved_rows_are_excluded_and_counted(self) -> None:
        report = calibration_report_from_rows(
            [
                {"market_id": "m1", "fair_yes": "0.75"},
                {"market_id": "m2", "fair_yes": "0.25"},
                {"market_id": "m3", "fair_yes": "0.50"},
            ],
            outcome_rows=[
                {"market_id": "m1", "resolved_outcome": "YES"},
                {"market_id": "m2", "resolved_outcome": "NO"},
                {"market_id": "m3", "resolved_outcome": ""},
            ],
        )

        self.assertEqual(report.resolved_rows, 2)
        self.assertEqual(report.excluded_rows, 1)
        self.assertAlmostEqual(report.brier_score, 0.0625)

    def test_calibration_bins_include_empirical_rate(self) -> None:
        bins = bin_forecasts_for_calibration([0.05, 0.15, 0.95], ["NO", "YES", "YES"], bins=2)

        self.assertEqual(len(bins), 2)
        self.assertEqual(bins[0].forecasts, 2)
        self.assertAlmostEqual(bins[0].average_forecast, 0.10)
        self.assertAlmostEqual(bins[0].empirical_rate, 0.50)
        self.assertEqual(bins[1].forecasts, 1)
        self.assertAlmostEqual(bins[1].empirical_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
