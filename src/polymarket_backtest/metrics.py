from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CalibrationBin:
    lower_bound: float
    upper_bound: float
    forecasts: int
    average_forecast: float
    empirical_rate: float
    brier_score: float


@dataclass(frozen=True)
class ForecastCalibrationReport:
    brier_score: float
    resolved_rows: int
    excluded_rows: int
    calibration_bins: list[dict[str, float | int]]


def _parse_probability(value: Any, *, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite probability in [0, 1]") from exc
    if not math.isfinite(parsed) or parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{label} must be a finite probability in [0, 1]")
    return parsed


def _parse_outcome(value: Any, *, label: str) -> float:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized == "YES":
            return 1.0
        if normalized == "NO":
            return 0.0
    return _parse_probability(value, label=label)


def compute_brier_score(forecast_probs: list[Any], outcomes: list[Any]) -> float:
    if len(forecast_probs) != len(outcomes):
        raise ValueError("forecast_probs and outcomes must have the same length")
    if not forecast_probs:
        raise ValueError("at least one resolved forecast is required")
    squared_errors = []
    for index, (forecast, outcome) in enumerate(zip(forecast_probs, outcomes), start=1):
        probability = _parse_probability(forecast, label=f"forecast_probs[{index}]")
        realized = _parse_outcome(outcome, label=f"outcomes[{index}]")
        squared_errors.append((probability - realized) ** 2)
    return sum(squared_errors) / len(squared_errors)


def bin_forecasts_for_calibration(
    forecast_probs: list[Any],
    outcomes: list[Any],
    bins: int = 10,
) -> list[CalibrationBin]:
    if bins <= 0:
        raise ValueError("bins must be positive")
    if len(forecast_probs) != len(outcomes):
        raise ValueError("forecast_probs and outcomes must have the same length")
    parsed_pairs = [
        (
            _parse_probability(forecast, label=f"forecast_probs[{index}]"),
            _parse_outcome(outcome, label=f"outcomes[{index}]"),
        )
        for index, (forecast, outcome) in enumerate(zip(forecast_probs, outcomes), start=1)
    ]
    bucketed: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for probability, realized in parsed_pairs:
        bucket_index = min(int(probability * bins), bins - 1)
        bucketed[bucket_index].append((probability, realized))

    calibration_bins: list[CalibrationBin] = []
    for index, bucket in enumerate(bucketed):
        if not bucket:
            continue
        forecasts = [pair[0] for pair in bucket]
        realized_values = [pair[1] for pair in bucket]
        calibration_bins.append(
            CalibrationBin(
                lower_bound=index / bins,
                upper_bound=(index + 1) / bins,
                forecasts=len(bucket),
                average_forecast=sum(forecasts) / len(forecasts),
                empirical_rate=sum(realized_values) / len(realized_values),
                brier_score=compute_brier_score(forecasts, realized_values),
            )
        )
    return calibration_bins


def _resolved_outcome_lookup(rows: list[dict[str, Any]] | None) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    if not rows:
        return outcomes
    for row in rows:
        market_id = str(row.get("market_id") or "")
        outcome = str(row.get("resolved_outcome") or "").strip().upper()
        if market_id and outcome in {"YES", "NO"}:
            outcomes[market_id] = outcome
    return outcomes


def calibration_report_from_rows(
    forecast_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]] | None = None,
    bins: int = 10,
) -> ForecastCalibrationReport:
    outcome_by_market = _resolved_outcome_lookup(outcome_rows or forecast_rows)
    forecasts: list[float] = []
    outcomes: list[str] = []
    excluded_rows = 0

    for row in forecast_rows:
        market_id = str(row.get("market_id") or "")
        outcome = str(row.get("resolved_outcome") or "").strip().upper()
        if outcome not in {"YES", "NO"}:
            outcome = outcome_by_market.get(market_id, "")
        if outcome not in {"YES", "NO"}:
            excluded_rows += 1
            continue
        try:
            forecast = _parse_probability(row.get("fair_yes"), label="fair_yes")
        except ValueError:
            excluded_rows += 1
            continue
        forecasts.append(forecast)
        outcomes.append(outcome)

    if not forecasts:
        return ForecastCalibrationReport(
            brier_score=0.0,
            resolved_rows=0,
            excluded_rows=excluded_rows,
            calibration_bins=[],
        )
    calibration_bins = [asdict(row) for row in bin_forecasts_for_calibration(forecasts, outcomes, bins=bins)]
    return ForecastCalibrationReport(
        brier_score=compute_brier_score(forecasts, outcomes),
        resolved_rows=len(forecasts),
        excluded_rows=excluded_rows,
        calibration_bins=calibration_bins,
    )
