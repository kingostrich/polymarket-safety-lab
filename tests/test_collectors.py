import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from polymarket_backtest.collectors import (
    CollectedMarket,
    PricePoint,
    collect_historical_dataset,
    resolved_outcome,
    validate_collected_dataset,
)


def market(market_id: str = "m1") -> CollectedMarket:
    return CollectedMarket(
        id=market_id,
        question="Will it happen?",
        closed_time="2026-01-01T00:00:00Z",
        resolved_outcome="YES",
        yes_token_id="yes-token",
        no_token_id="no-token",
        final_yes_price=1.0,
        final_no_price=0.0,
        volume=100.0,
        liquidity=50.0,
        fee_type="",
        fees_enabled=False,
        order_min_size=5.0,
        order_tick_size=0.01,
    )


class CollectorsTest(unittest.TestCase):
    def test_resolved_outcome_requires_conservative_binary_prices(self) -> None:
        self.assertEqual(resolved_outcome([0.999, 0.001]), "YES")
        self.assertEqual(resolved_outcome([0.001, 0.999]), "NO")
        self.assertIsNone(resolved_outcome([0.998, 0.002]))
        self.assertIsNone(resolved_outcome([0.5, 0.5]))
        self.assertIsNone(resolved_outcome([1.0]))
        self.assertIsNone(resolved_outcome([None, 1.0]))
        self.assertIsNone(resolved_outcome(None))

    def test_validate_collected_dataset_rejects_non_neutral_rows(self) -> None:
        errors = validate_collected_dataset(
            [market()],
            [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "market_id": "m1",
                    "yes_price": "0.500000",
                    "fair_yes": "0.600000",
                    "resolved_outcome": "MAYBE",
                }
            ],
        )

        self.assertTrue(any("fair_yes must equal yes_price" in error for error in errors))
        self.assertTrue(any("resolved_outcome must be YES or NO" in error for error in errors))

    def test_validate_collected_dataset_compares_neutral_prices_numerically(self) -> None:
        errors = validate_collected_dataset(
            [market()],
            [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "market_id": "m1",
                    "yes_price": "0.5",
                    "fair_yes": "0.500000",
                    "resolved_outcome": "YES",
                }
            ],
        )

        self.assertEqual(errors, [])

    def test_collect_historical_rejects_invalid_generated_dataset(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_market = market()
            points = [
                PricePoint(
                    market_id="m1",
                    token_id="yes-token",
                    side="YES",
                    timestamp=1_700_000_000,
                    price=0.50,
                )
            ]

            with (
                patch("polymarket_backtest.collectors.collect_closed_binary_markets", return_value=[bad_market]),
                patch("polymarket_backtest.collectors.collect_price_history", return_value=points),
                patch(
                    "polymarket_backtest.collectors.build_neutral_snapshots",
                    return_value=[
                        {
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "market_id": "m1",
                            "yes_price": "0.500000",
                            "fair_yes": "0.600000",
                            "resolved_outcome": "YES",
                        }
                    ],
                ),
            ):
                with self.assertRaisesRegex(ValueError, "validation failed"):
                    collect_historical_dataset(root, markets_count=1, max_pages=1)

            self.assertFalse((root / "manifest.json").exists())

    def test_collect_historical_manifest_distinguishes_neutral_from_oracle_smoke(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample_market = market()
            points = [
                PricePoint(
                    market_id="m1",
                    token_id="yes-token",
                    side="YES",
                    timestamp=1_700_000_000,
                    price=0.50,
                ),
                PricePoint(
                    market_id="m1",
                    token_id="no-token",
                    side="NO",
                    timestamp=1_700_000_000,
                    price=0.50,
                ),
            ]

            with (
                patch("polymarket_backtest.collectors.collect_closed_binary_markets", return_value=[sample_market]),
                patch("polymarket_backtest.collectors.collect_price_history", return_value=points),
            ):
                manifest = collect_historical_dataset(root, markets_count=1, max_pages=1)

            written_manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["validation_status"], "PASS")
            self.assertEqual(written_manifest["dataset_modes"]["snapshots_neutral"]["kind"], "neutral_plumbing")
            self.assertEqual(written_manifest["dataset_modes"]["oracle_smoke"]["kind"], "oracle_settlement_smoke")
            self.assertEqual(written_manifest["dataset_modes"]["oracle_smoke"]["path"], "")
            self.assertIn("Gamma /markets", written_manifest["collection_path"]["market_metadata"])
            self.assertEqual(written_manifest["generated_files"]["neutral_snapshots"], "snapshots_neutral.csv")
            self.assertIn("data/normalized", written_manifest["git_tracking_note"])


if __name__ == "__main__":
    unittest.main()
