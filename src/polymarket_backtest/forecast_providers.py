from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .strategy import clamp_probability


def normalize_timestamp_key(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


@dataclass(frozen=True)
class Forecast:
    fair_yes: float
    model: str
    cost: float
    reasoning: str


class ForecastProvider(Protocol):
    name: str

    def forecast(self, row: dict[str, str]) -> Forecast:
        """Return a timestamped paper forecast for a logged market row."""


class RecordedForecastProvider:
    name = "recorded_neutral_market_implied"

    def __init__(self, cost_per_forecast: float = 0.0) -> None:
        self.cost_per_forecast = cost_per_forecast

    def forecast(self, row: dict[str, str]) -> Forecast:
        return Forecast(
            fair_yes=clamp_probability(float(row["fair_yes"])),
            model=self.name,
            cost=self.cost_per_forecast,
            reasoning="Uses the fair_yes already recorded in the forward logger row.",
        )


class RuleBaselineForecastProvider:
    name = "rule_baseline_midpoint"

    def __init__(self, cost_per_forecast: float = 0.0) -> None:
        self.cost_per_forecast = cost_per_forecast

    @staticmethod
    def _midpoint(row: dict[str, str]) -> float | None:
        yes_bid = float(row.get("yes_bid") or 0.0)
        yes_ask = float(row.get("yes_ask") or 0.0)
        if yes_bid > 0 and yes_ask > 0:
            return (yes_bid + yes_ask) / 2.0
        return None

    def forecast(self, row: dict[str, str]) -> Forecast:
        midpoint = self._midpoint(row)
        fair_yes = midpoint if midpoint is not None else float(row["fair_yes"])
        return Forecast(
            fair_yes=clamp_probability(fair_yes),
            model=self.name,
            cost=self.cost_per_forecast,
            reasoning="Zero-cost baseline using YES order-book midpoint; falls back to recorded fair_yes.",
        )


class SyntheticEdgeForecastProvider:
    name = "synthetic_edge_test_only"

    def __init__(self, edge: float = 0.12, side: str = "YES", cost_per_forecast: float = 0.0) -> None:
        self.edge = edge
        self.side = side.upper()
        self.cost_per_forecast = cost_per_forecast

    def forecast(self, row: dict[str, str]) -> Forecast:
        yes_ask = float(row["yes_ask"])
        no_ask = float(row["no_ask"])
        if self.side == "NO":
            fair_yes = 1.0 - (no_ask + self.edge)
        else:
            fair_yes = yes_ask + self.edge
        return Forecast(
            fair_yes=clamp_probability(fair_yes),
            model=f"{self.name}:{self.side}:{self.edge:.4f}",
            cost=self.cost_per_forecast,
            reasoning="Synthetic forecast used only to test paper survival mechanics.",
        )


class ForecastFileProvider:
    name = "forecast_file"

    def __init__(self, path: Path, allow_missing: bool = False) -> None:
        self.path = path
        self.allow_missing = allow_missing
        self._forecasts = self._load(path)

    @staticmethod
    def _key(row: dict[str, str]) -> tuple[str, str]:
        return (normalize_timestamp_key(row["logged_at"]), row["market_id"])

    @classmethod
    def _load(cls, path: Path) -> dict[tuple[str, str], Forecast]:
        forecasts: dict[tuple[str, str], Forecast] = {}
        if path.suffix.lower() == ".jsonl":
            with path.open() as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    forecasts[(normalize_timestamp_key(row["logged_at"]), row["market_id"])] = Forecast(
                        fair_yes=clamp_probability(float(row["fair_yes"])),
                        model=row.get("model") or row.get("provider") or cls.name,
                        cost=float(row.get("cost") or 0.0),
                        reasoning=row.get("reasoning") or "Forecast loaded from file.",
                    )
            return forecasts
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                forecasts[(normalize_timestamp_key(row["logged_at"]), row["market_id"])] = Forecast(
                    fair_yes=clamp_probability(float(row["fair_yes"])),
                    model=row.get("model") or row.get("provider") or cls.name,
                    cost=float(row.get("cost") or 0.0),
                    reasoning=row.get("reasoning") or "Forecast loaded from file.",
                )
        return forecasts

    def forecast(self, row: dict[str, str]) -> Forecast:
        key = self._key(row)
        forecast = self._forecasts.get(key)
        if forecast is not None:
            return forecast
        if self.allow_missing:
            return Forecast(
                fair_yes=clamp_probability(float(row["fair_yes"])),
                model=f"{self.name}:missing_fallback",
                cost=0.0,
                reasoning="Missing forecast row; fell back to recorded fair_yes.",
            )
        raise KeyError(f"missing forecast for logged_at={key[0]} market_id={key[1]}")


def create_forecast_provider(
    mode: str,
    cost_per_forecast: float = 0.0,
    synthetic_edge: float = 0.12,
    synthetic_side: str = "YES",
) -> ForecastProvider:
    if mode == "recorded":
        return RecordedForecastProvider(cost_per_forecast=cost_per_forecast)
    if mode == "rule_baseline":
        return RuleBaselineForecastProvider(cost_per_forecast=cost_per_forecast)
    if mode == "synthetic_edge":
        return SyntheticEdgeForecastProvider(
            edge=synthetic_edge,
            side=synthetic_side,
            cost_per_forecast=cost_per_forecast,
        )
    raise ValueError(f"unknown forecast mode: {mode}")
