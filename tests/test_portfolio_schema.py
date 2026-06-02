from __future__ import annotations

import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from polymarket_backtest.models import Side
from polymarket_backtest.portfolio_schema import (
    load_exposures,
    main,
    parse_portfolio_spec,
    validate_portfolio_spec,
)


def sample_payload() -> dict[str, object]:
    return {
        "portfolio_id": "research_hedge_v1",
        "groups": [
            {
                "group_id": "overlapping_election_markets",
                "description": "Paper-only hedge candidate across related prediction markets.",
                "max_joint_notional": 25,
                "max_correlation": 0.9,
                "legs": [
                    {
                        "market_id": "market-candidate-a-wins",
                        "side": "YES",
                        "max_notional": 10,
                        "hedge_role": "primary",
                        "correlation": 0.8,
                    },
                    {
                        "market_id": "market-candidate-b-wins",
                        "side": "NO",
                        "max_notional": 12,
                        "hedge_role": "hedge",
                        "correlation": -0.7,
                    },
                ],
            }
        ],
    }


class PortfolioSchemaTest(unittest.TestCase):
    def test_parse_valid_multi_leg_spec(self) -> None:
        spec = parse_portfolio_spec(sample_payload())

        self.assertEqual(spec.portfolio_id, "research_hedge_v1")
        self.assertEqual(len(spec.groups), 1)
        self.assertEqual(spec.groups[0].legs[0].side, Side.YES)
        self.assertEqual(spec.groups[0].legs[1].side, Side.NO)

    def test_rejects_duplicate_market_ids_within_group(self) -> None:
        payload = sample_payload()
        group = payload["groups"][0]  # type: ignore[index]
        group["legs"][1]["market_id"] = "market-candidate-a-wins"  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "duplicate market_id"):
            parse_portfolio_spec(payload)

    def test_rejects_invalid_side(self) -> None:
        payload = sample_payload()
        group = payload["groups"][0]  # type: ignore[index]
        group["legs"][0]["side"] = "MAYBE"  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "side must be YES or NO"):
            parse_portfolio_spec(payload)

    def test_validate_passes_when_caps_and_exposures_are_under_joint_limit(self) -> None:
        spec = parse_portfolio_spec(sample_payload())
        report = validate_portfolio_spec(
            spec,
            {
                "market-candidate-a-wins": 8,
                "market-candidate-b-wins": 7,
            },
        )

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.violations, ())
        self.assertFalse(report.production_safe)
        self.assertEqual(report.readiness_decision, "PAPER_ONLY_REVIEW")

    def test_validate_allows_leg_caps_to_exceed_joint_limit_until_exposure_is_active(self) -> None:
        payload = sample_payload()
        group = payload["groups"][0]  # type: ignore[index]
        group["legs"][0]["max_notional"] = 20  # type: ignore[index]
        group["legs"][1]["max_notional"] = 20  # type: ignore[index]
        spec = parse_portfolio_spec(payload)

        report = validate_portfolio_spec(spec)

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.violations, ())

    def test_validate_blocks_active_exposure_above_joint_limit(self) -> None:
        spec = parse_portfolio_spec(sample_payload())
        report = validate_portfolio_spec(
            spec,
            {
                "market-candidate-a-wins": 14,
                "market-candidate-b-wins": 12,
            },
        )

        self.assertEqual(report.status, "FAIL")
        self.assertIn("active exposure", report.violations[0])

    def test_validate_blocks_active_exposure_above_leg_limit(self) -> None:
        spec = parse_portfolio_spec(sample_payload())
        report = validate_portfolio_spec(
            spec,
            {
                "market-candidate-a-wins": 11,
                "market-candidate-b-wins": 4,
            },
        )

        self.assertEqual(report.status, "FAIL")
        self.assertIn("exceeds leg cap", report.violations[0])

    def test_validate_treats_negative_exposure_as_absolute_risk(self) -> None:
        spec = parse_portfolio_spec(sample_payload())
        report = validate_portfolio_spec(
            spec,
            {
                "market-candidate-a-wins": -11,
                "market-candidate-b-wins": 4,
            },
        )

        self.assertEqual(report.status, "FAIL")
        self.assertIn("exceeds leg cap", report.violations[0])

    def test_rejects_absolute_correlation_above_group_cap(self) -> None:
        payload = sample_payload()
        group = payload["groups"][0]  # type: ignore[index]
        group["legs"][1]["correlation"] = -0.95  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "absolute correlation exceeds"):
            parse_portfolio_spec(payload)

    def test_load_exposures_accepts_nested_market_exposures_object(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "exposures.json"
            path.write_text('{"market_exposures": {"market-a": 3.5}}', encoding="utf-8")

            exposures = load_exposures(path)

        self.assertEqual(exposures, {"market-a": 3.5})

    def test_cli_writes_fail_report_for_invalid_spec(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "portfolio.json"
            out_path = root / "report.json"
            spec_path.write_text('{"portfolio_id": "x", "groups": []}', encoding="utf-8")

            with self.assertRaises(SystemExit) as exc, patch(
                "sys.argv",
                ["portfolio_schema", "--spec", str(spec_path), "--out-json", str(out_path)],
            ):
                main()

            self.assertEqual(exc.exception.code, 1)
            self.assertIn('"status": "FAIL"', out_path.read_text(encoding="utf-8"))

    def test_report_serializes_to_json_safe_shape(self) -> None:
        spec = parse_portfolio_spec(sample_payload())
        report = validate_portfolio_spec(spec)

        self.assertEqual(asdict(report)["groups_checked"], 1)


if __name__ == "__main__":
    unittest.main()
