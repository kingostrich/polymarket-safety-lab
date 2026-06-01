import csv
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from polymarket_backtest.report_summary import SurvivalReportSummary
from polymarket_backtest.strategy_compare import (
    build_comparisons,
    filter_rows_by_scenario_prefix,
    load_summary_rows,
    write_comparison_csv,
)


def summary_row(**overrides) -> dict[str, str]:
    base = SurvivalReportSummary(
        scenario="case",
        report_path="data/paper/case/survival_report_20260101T000000Z.json",
        run_timestamp="20260101T000000Z",
        state="ALIVE",
        death_reason="",
        initial_bankroll=50.0,
        final_equity=50.0,
        final_cash=50.0,
        return_on_investment=0.0,
        max_drawdown=0.0,
        event_max_drawdown=0.0,
        timestamp_close_max_drawdown=0.0,
        drawdown_policy="event",
        rows_processed=10,
        signals_seen=0,
        forecast_calls=0,
        forecast_cost_total=0.0,
        positions_opened=0,
        positions_closed=0,
        open_positions=0,
        liquidity_skips=0,
        partial_entries=0,
        unfilled_entry_notional=0.0,
        exit_liquidity_skips=0,
        partial_exits=0,
        unfilled_exit_notional=0.0,
        slippage_cost_total=0.0,
        realized_pnl=0.0,
        forecast_model="recorded",
        legacy_mdd_fields=False,
        missing_fields="",
    )
    row = {key: str(value) for key, value in asdict(base).items()}
    row.update({key: str(value) for key, value in overrides.items()})
    return row


class StrategyCompareTest(unittest.TestCase):
    def test_build_comparisons_uses_latest_run_per_scenario_and_flags_mixed_history(self) -> None:
        rows = [
            summary_row(scenario="case", run_timestamp="20260101T000000Z", forecast_model="recorded"),
            summary_row(
                scenario="case",
                run_timestamp="20260102T000000Z",
                forecast_model="synthetic",
                return_on_investment="-0.10",
                liquidity_skips="2",
                partial_entries="1",
                open_positions="3",
                exit_liquidity_skips="1",
                partial_exits="1",
                unfilled_exit_notional="2.5",
                slippage_cost_total="0.1",
            ),
            summary_row(
                scenario="clean",
                run_timestamp="20260101T000000Z",
                return_on_investment="0.01",
                event_max_drawdown="0.02",
            ),
        ]

        comparisons = build_comparisons(rows)

        self.assertEqual(len(comparisons), 2)
        case = next(row for row in comparisons if row.scenario == "case")
        self.assertEqual(case.run_timestamp, "20260102T000000Z")
        self.assertTrue(case.mixed_history)
        self.assertIn("mixed_history", case.risk_flags)
        self.assertIn("entry_liquidity", case.risk_flags)
        self.assertIn("partial_entry", case.risk_flags)
        self.assertIn("open_positions", case.risk_flags)
        self.assertIn("exit_liquidity", case.risk_flags)
        self.assertIn("partial_exit", case.risk_flags)
        self.assertIn("unfilled_exit", case.risk_flags)
        self.assertIn("slippage_cost", case.risk_flags)

    def test_screening_rank_prefers_alive_active_higher_roi_then_lower_mdd(self) -> None:
        rows = [
            summary_row(scenario="legacy", legacy_mdd_fields="True", return_on_investment="0.50", positions_opened="2"),
            summary_row(scenario="dead", state="DEAD", return_on_investment="1.00"),
            summary_row(scenario="no_trade", return_on_investment="0.00", positions_opened="0"),
            summary_row(scenario="candidate", return_on_investment="0.01", event_max_drawdown="0.01", positions_opened="2"),
        ]

        comparisons = build_comparisons(rows)

        self.assertEqual(comparisons[0].scenario, "legacy")
        self.assertEqual(comparisons[1].scenario, "candidate")
        self.assertEqual(comparisons[2].scenario, "no_trade")
        self.assertEqual(comparisons[3].scenario, "dead")
        self.assertEqual([row.screening_rank for row in comparisons], [1, 2, 3, 4])
        self.assertIn("no_trades", comparisons[2].risk_flags)

    def test_performance_rank_prefers_higher_roi_even_for_no_trade_baseline(self) -> None:
        rows = [
            summary_row(scenario="active_loss", positions_opened="2", return_on_investment="-0.10"),
            summary_row(scenario="no_trade", positions_opened="0", return_on_investment="0.00"),
        ]

        comparisons = build_comparisons(rows, rank_mode="performance")

        self.assertEqual(comparisons[0].scenario, "no_trade")
        self.assertEqual(comparisons[1].scenario, "active_loss")

    def test_invalid_rank_mode_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown rank mode"):
            build_comparisons([summary_row()], rank_mode="bad")

    def test_write_comparison_csv_round_trips(self) -> None:
        comparisons = build_comparisons([summary_row(scenario="case")])
        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "comparison.csv"

            write_comparison_csv(comparisons, output_path)
            with output_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["scenario"], "case")
        self.assertEqual(rows[0]["screening_rank"], "1")

    def test_filter_rows_by_scenario_prefix(self) -> None:
        rows = [
            summary_row(scenario="standardized/case"),
            summary_row(scenario="legacy/case"),
        ]

        filtered = filter_rows_by_scenario_prefix(rows, "standardized/")

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["scenario"], "standardized/case")

    def test_load_summary_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(summary_row().keys()))
                writer.writeheader()
                writer.writerow(summary_row(scenario="case"))

            rows = load_summary_rows(path)

        self.assertEqual(rows[0]["scenario"], "case")
