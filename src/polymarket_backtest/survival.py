from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .forecast_providers import ForecastFileProvider, ForecastProvider, create_forecast_provider
from .models import MarketSnapshot, Position, Side
from .strategy import build_signal

EPSILON = 1e-12


@dataclass(frozen=True)
class SurvivalEvent:
    timestamp: str
    event_type: str
    market_id: str
    side: str
    cash: float
    equity: float
    detail: str


@dataclass(frozen=True)
class SurvivalResult:
    state: str
    death_reason: str
    initial_bankroll: float
    final_cash: float
    final_equity: float
    rows_processed: int
    forecast_calls: int
    forecast_cost_total: float
    signals_seen: int
    positions_opened: int
    positions_closed: int
    liquidity_skips: int
    partial_entries: int
    unfilled_entry_notional: float
    exit_liquidity_skips: int
    partial_exits: int
    unfilled_exit_notional: float
    slippage_cost_total: float
    realized_pnl: float
    open_positions: int
    max_drawdown: float
    event_max_drawdown: float
    timestamp_close_max_drawdown: float
    drawdown_policy: str
    forecast_model: str


@dataclass(frozen=True)
class Resolution:
    market_id: str
    resolved_at: datetime
    outcome: Side | None


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def safe_float(value: str | float | int | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    os.replace(tmp_path, path)


def load_paper_rows(input_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(glob.glob(str(input_dir / "paper_signals_*.csv"))):
        with Path(path).open(newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return sorted(rows, key=lambda row: (parse_timestamp(row["logged_at"]), row["market_id"]))


def order_rows_for_timestamp_policy(rows: list[dict[str, str]], timestamp_order_policy: str) -> list[dict[str, str]]:
    if timestamp_order_policy == "sequential":
        return rows
    if timestamp_order_policy != "history_first":
        raise ValueError(f"unknown timestamp order policy: {timestamp_order_policy}")

    ordered: list[dict[str, str]] = []
    seen_markets: set[str] = set()
    index = 0
    while index < len(rows):
        row_time = parse_timestamp(rows[index]["logged_at"])
        batch: list[dict[str, str]] = []
        while index < len(rows) and parse_timestamp(rows[index]["logged_at"]) == row_time:
            batch.append(rows[index])
            index += 1
        ordered.extend(sorted(batch, key=lambda row: (0 if row["market_id"] in seen_markets else 1, row["market_id"])))
        seen_markets.update(row["market_id"] for row in batch)
    return ordered


def timestamp_batches(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    index = 0
    while index < len(rows):
        row_time = parse_timestamp(rows[index]["logged_at"])
        batch: list[dict[str, str]] = []
        while index < len(rows) and parse_timestamp(rows[index]["logged_at"]) == row_time:
            batch.append(rows[index])
            index += 1
        batches.append(batch)
    return batches


def load_resolutions(path: Path | None) -> dict[str, Resolution]:
    if path is None:
        return {}
    resolutions: dict[str, Resolution] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            market_id = row["market_id"]
            outcome_text = (row.get("resolved_outcome") or "").upper()
            outcome = Side(outcome_text) if outcome_text in {Side.YES.value, Side.NO.value} else None
            resolutions[market_id] = Resolution(
                market_id=market_id,
                resolved_at=parse_timestamp(row["resolved_at"]),
                outcome=outcome,
            )
    return resolutions


def row_bid_price(row: dict[str, str], side: Side) -> float | None:
    value = row.get("yes_bid") if side == Side.YES else row.get("no_bid")
    if value in (None, ""):
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def update_last_valid_bids(
    last_valid_bids: dict[str, dict[Side, float]],
    market_id: str,
    row: dict[str, str],
) -> None:
    for side in (Side.YES, Side.NO):
        price = row_bid_price(row, side)
        if price is not None:
            last_valid_bids.setdefault(market_id, {})[side] = price


def effective_bid_price(
    row: dict[str, str],
    side: Side,
    last_valid_bids: dict[str, dict[Side, float]] | None = None,
    missing_quote_policy: str = "zero",
) -> float:
    price = row_bid_price(row, side)
    if price is None and missing_quote_policy == "last_valid_bid" and last_valid_bids is not None:
        price = last_valid_bids.get(row["market_id"], {}).get(side)
    if price is None:
        return 0.0
    return max(0.0, price)


def mark_positions(
    positions: dict[str, Position],
    latest_rows: dict[str, dict[str, str]],
    last_valid_bids: dict[str, dict[Side, float]] | None = None,
    missing_quote_policy: str = "zero",
) -> float:
    if missing_quote_policy not in {"zero", "last_valid_bid"}:
        raise ValueError(f"unknown missing quote policy: {missing_quote_policy}")
    value = 0.0
    for market_id, position in positions.items():
        row = latest_rows.get(market_id)
        if row is None:
            value += position.cost
            continue
        price = effective_bid_price(row, position.side, last_valid_bids, missing_quote_policy)
        value += position.shares * price
    return value


def max_drawdown(equity_curve: list[float]) -> float:
    peak = 0.0
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, (equity - peak) / peak)
    return abs(worst)


def drawdown_curve_for_policy(
    initial_bankroll: float,
    final_equity: float,
    event_equity_curve: list[float],
    timestamp_equity_marks: list[tuple[datetime, float]],
    drawdown_policy: str,
) -> list[float]:
    if drawdown_policy == "event":
        return event_equity_curve
    if drawdown_policy != "timestamp_close":
        raise ValueError(f"unknown drawdown policy: {drawdown_policy}")

    curve = [initial_bankroll]
    if timestamp_equity_marks:
        ordered_marks = [
            mark for _, mark in sorted(enumerate(timestamp_equity_marks), key=lambda item: (item[1][0], item[0]))
        ]
        last_timestamp, last_equity = ordered_marks[0]
        for timestamp, equity in ordered_marks[1:]:
            if timestamp != last_timestamp:
                curve.append(last_equity)
                last_timestamp = timestamp
            last_equity = equity
        curve.append(last_equity)
    if abs(curve[-1] - final_equity) > EPSILON:
        curve.append(final_equity)
    return curve


def settle_position(position: Position, resolution: Resolution, timestamp: str) -> tuple[float, SurvivalEvent]:
    if resolution.outcome is None:
        proceeds = position.cost
        payout_label = "REFUND_COST"
    else:
        payout_price = 1.0 if position.side == resolution.outcome else 0.0
        proceeds = position.shares * payout_price
        payout_label = f"{payout_price:.6f}"
    pnl = proceeds - position.cost
    return proceeds, SurvivalEvent(
        timestamp=timestamp,
        event_type="SETTLE_POSITION",
        market_id=position.market_id,
        side=position.side.value,
        cash=0.0,
        equity=0.0,
        detail=f"outcome={resolution.outcome.value if resolution.outcome else 'UNKNOWN'};payout={payout_label};pnl={pnl:.6f}",
    )


def exit_position(
    position: Position,
    row: dict[str, str],
    fair_yes: float,
    last_valid_bids: dict[str, dict[Side, float]] | None = None,
    missing_quote_policy: str = "zero",
) -> tuple[float, SurvivalEvent]:
    bid = effective_bid_price(row, position.side, last_valid_bids, missing_quote_policy)
    proceeds = position.shares * bid
    pnl = proceeds - position.cost
    hold_edge = fair_yes - bid if position.side == Side.YES else (1.0 - fair_yes) - bid
    return proceeds, SurvivalEvent(
        timestamp=row["logged_at"],
        event_type="EXIT_POSITION",
        market_id=position.market_id,
        side=position.side.value,
        cash=0.0,
        equity=0.0,
        detail=f"bid={bid:.6f};hold_edge={hold_edge:.6f};pnl={pnl:.6f}",
    )


def exit_bid_depth_shares(row: dict[str, str], side: Side) -> float:
    if side == Side.YES:
        return safe_float(row.get("yes_bid_depth_top3"))
    return safe_float(row.get("no_bid_depth_top3"))


def slippage_adjusted_price(
    price: float,
    requested_notional: float,
    available_notional: float,
    slippage_model: str,
    max_slippage_bps: float,
    direction: str,
) -> tuple[float, float, float]:
    if slippage_model == "none" or available_notional <= EPSILON or requested_notional <= EPSILON:
        return price, 0.0, 0.0
    if slippage_model != "depth_utilization":
        raise ValueError(f"unknown slippage model: {slippage_model}")
    if direction not in {"buy", "sell"}:
        raise ValueError(f"unknown slippage direction: {direction}")

    utilization = min(1.0, max(0.0, requested_notional / available_notional))
    penalty = max(0.0, max_slippage_bps) / 10_000.0 * utilization
    if direction == "buy":
        adjusted_price = min(1.0, price * (1.0 + penalty))
    else:
        adjusted_price = max(0.0, price * (1.0 - penalty))
    return adjusted_price, abs(adjusted_price - price), utilization


def execute_exit(
    position: Position,
    row: dict[str, str],
    fair_yes: float,
    exit_liquidity_model: str,
    max_exit_depth_fraction: float,
    slippage_model: str,
    max_slippage_bps: float,
    last_valid_bids: dict[str, dict[Side, float]] | None = None,
    missing_quote_policy: str = "zero",
) -> tuple[float, float, bool, float, float, SurvivalEvent]:
    if exit_liquidity_model == "none":
        proceeds, event = exit_position(position, row, fair_yes, last_valid_bids, missing_quote_policy)
        return proceeds, proceeds - position.cost, True, 0.0, 0.0, event
    if exit_liquidity_model != "top3_bid":
        raise ValueError(f"unknown exit liquidity model: {exit_liquidity_model}")

    bid = effective_bid_price(row, position.side, last_valid_bids, missing_quote_policy)
    available_shares = exit_bid_depth_shares(row, position.side) * max(0.0, max_exit_depth_fraction)
    if bid <= 0 or available_shares <= 0:
        unfilled_notional = position.shares * max(0.0, bid)
        return 0.0, 0.0, False, unfilled_notional, 0.0, SurvivalEvent(
            timestamp=row["logged_at"],
            event_type="SKIP_EXIT_LIQUIDITY_DEPTH",
            market_id=position.market_id,
            side=position.side.value,
            cash=0.0,
            equity=0.0,
            detail=f"bid={bid:.6f};available_shares={available_shares:.6f};unfilled_notional={unfilled_notional:.6f}",
        )

    shares_to_exit = min(position.shares, available_shares)
    exit_ratio = shares_to_exit / position.shares
    closed_cost = position.cost * exit_ratio
    available_notional = available_shares * bid
    requested_notional = shares_to_exit * bid
    exec_bid, _, depth_utilization = slippage_adjusted_price(
        bid,
        requested_notional,
        available_notional,
        slippage_model,
        max_slippage_bps,
        "sell",
    )
    proceeds = shares_to_exit * exec_bid
    slippage_cost = shares_to_exit * max(0.0, bid - exec_bid)
    pnl = proceeds - closed_cost
    hold_edge = fair_yes - bid if position.side == Side.YES else (1.0 - fair_yes) - bid

    if shares_to_exit >= position.shares - EPSILON:
        return proceeds, pnl, True, 0.0, slippage_cost, SurvivalEvent(
            timestamp=row["logged_at"],
            event_type="EXIT_POSITION",
            market_id=position.market_id,
            side=position.side.value,
            cash=0.0,
            equity=0.0,
            detail=(
                f"bid={bid:.6f};exec_bid={exec_bid:.6f};hold_edge={hold_edge:.6f};pnl={pnl:.6f};"
                f"available_shares={available_shares:.6f};depth_utilization={depth_utilization:.6f};"
                f"slippage_cost={slippage_cost:.6f}"
            ),
        )

    position.shares -= shares_to_exit
    position.cost -= closed_cost
    unfilled_notional = position.shares * bid
    return proceeds, pnl, False, unfilled_notional, slippage_cost, SurvivalEvent(
        timestamp=row["logged_at"],
        event_type="PARTIAL_EXIT_POSITION",
        market_id=position.market_id,
        side=position.side.value,
        cash=0.0,
        equity=0.0,
        detail=(
            f"bid={bid:.6f};exec_bid={exec_bid:.6f};hold_edge={hold_edge:.6f};shares_exited={shares_to_exit:.6f};"
            f"shares_remaining={position.shares:.6f};pnl={pnl:.6f};unfilled_notional={unfilled_notional:.6f};"
            f"depth_utilization={depth_utilization:.6f};slippage_cost={slippage_cost:.6f}"
        ),
    )


def should_exit_position(
    position: Position,
    row: dict[str, str],
    fair_yes: float,
    exit_policy: str,
    exit_edge_threshold: float,
    last_valid_bids: dict[str, dict[Side, float]] | None = None,
    missing_quote_policy: str = "zero",
) -> bool:
    if exit_policy == "none":
        return False
    bid = effective_bid_price(row, position.side, last_valid_bids, missing_quote_policy)
    hold_edge = fair_yes - bid if position.side == Side.YES else (1.0 - fair_yes) - bid
    if exit_policy == "edge_below":
        return hold_edge <= exit_edge_threshold + EPSILON
    raise ValueError(f"unknown exit policy: {exit_policy}")


def settle_due_positions(
    positions: dict[str, Position],
    resolutions: dict[str, Resolution],
    timestamp: str,
    row_time: datetime,
    cash: float,
    latest_rows: dict[str, dict[str, str]],
    last_valid_bids: dict[str, dict[Side, float]] | None = None,
    missing_quote_policy: str = "zero",
) -> tuple[float, int, float, list[SurvivalEvent]]:
    closed = 0
    realized_pnl = 0.0
    events: list[SurvivalEvent] = []
    for market_id, position in list(positions.items()):
        resolution = resolutions.get(market_id)
        if resolution is None:
            continue
        if not resolution_due(row_time, resolution):
            continue
        positions.pop(market_id)
        proceeds, event = settle_position(position, resolution, timestamp)
        cash += proceeds
        closed += 1
        realized_pnl += proceeds - position.cost
        equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
        events.append(
            SurvivalEvent(
                event.timestamp,
                event.event_type,
                event.market_id,
                event.side,
                cash,
                equity,
                event.detail,
            )
        )
    return cash, closed, realized_pnl, events


def resolution_due(row_time: datetime, resolution: Resolution) -> bool:
    resolved_at = resolution.resolved_at
    if resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=UTC)
    return row_time >= resolved_at


def entry_depth_notional(row: dict[str, str], side: Side, price: float) -> float:
    if price <= 0:
        return 0.0
    if side == Side.YES:
        depth_shares = safe_float(row.get("yes_ask_depth_top3"))
        if depth_shares <= 0:
            depth_shares = safe_float(row.get("yes_depth_top3"))
    else:
        depth_shares = safe_float(row.get("no_ask_depth_top3"))
        if depth_shares <= 0:
            depth_shares = safe_float(row.get("no_depth_top3"))
    return max(0.0, depth_shares) * price


def entry_budget_for_fill_policy(
    row: dict[str, str],
    side: Side,
    price: float,
    budget: float,
    liquidity_model: str,
    max_depth_fraction: float,
    entry_fill_policy: str,
) -> tuple[float, bool, float, float, str]:
    if entry_fill_policy not in {"all_or_none", "partial"}:
        raise ValueError(f"unknown entry fill policy: {entry_fill_policy}")
    if liquidity_model == "none":
        return budget, False, 0.0, 0.0, ""
    if liquidity_model != "top3_ask":
        raise ValueError(f"unknown liquidity model: {liquidity_model}")
    available_notional = entry_depth_notional(row, side, price) * max(0.0, max_depth_fraction)
    if budget <= available_notional + EPSILON:
        return budget, False, 0.0, available_notional, f"available_notional={available_notional:.6f}"
    if entry_fill_policy == "all_or_none" or available_notional <= EPSILON:
        return 0.0, False, budget, available_notional, f"budget={budget:.6f};available_notional={available_notional:.6f}"
    filled_budget = min(budget, available_notional)
    unfilled_notional = budget - filled_budget
    return filled_budget, True, unfilled_notional, available_notional, (
        f"requested_budget={budget:.6f};filled_budget={filled_budget:.6f};"
        f"available_notional={available_notional:.6f};unfilled_notional={unfilled_notional:.6f}"
    )


def simulate_survival(
    rows: list[dict[str, str]],
    provider: ForecastProvider,
    resolutions: dict[str, Resolution] | None = None,
    initial_bankroll: float = 50.0,
    edge_threshold: float = 0.08,
    max_fraction: float = 0.06,
    max_positions: int = 10,
    death_threshold: float = 0.0,
    exit_policy: str = "none",
    exit_edge_threshold: float = 0.0,
    liquidity_model: str = "none",
    max_depth_fraction: float = 0.25,
    entry_fill_policy: str = "all_or_none",
    exit_liquidity_model: str = "none",
    max_exit_depth_fraction: float = 0.25,
    slippage_model: str = "none",
    max_slippage_bps: float = 50.0,
    missing_quote_policy: str = "zero",
    forecast_call_policy: str = "always",
    timestamp_order_policy: str = "sequential",
    drawdown_policy: str = "event",
) -> tuple[SurvivalResult, list[SurvivalEvent]]:
    if missing_quote_policy not in {"zero", "last_valid_bid"}:
        raise ValueError(f"unknown missing quote policy: {missing_quote_policy}")
    if forecast_call_policy not in {"always", "actionable"}:
        raise ValueError(f"unknown forecast call policy: {forecast_call_policy}")
    if timestamp_order_policy not in {"sequential", "history_first", "position_first"}:
        raise ValueError(f"unknown timestamp order policy: {timestamp_order_policy}")
    if drawdown_policy not in {"event", "timestamp_close"}:
        raise ValueError(f"unknown drawdown policy: {drawdown_policy}")
    if missing_quote_policy == "last_valid_bid" and exit_policy != "none" and exit_liquidity_model == "none":
        raise ValueError("last_valid_bid exits require top3_bid exit liquidity model")
    if slippage_model != "none" and liquidity_model == "none" and exit_liquidity_model == "none":
        raise ValueError("depth_utilization slippage requires top3_ask or top3_bid liquidity depth")
    resolutions = resolutions or {}
    cash = initial_bankroll
    state = "ALIVE"
    death_reason = ""
    forecast_calls = 0
    forecast_cost_total = 0.0
    signals_seen = 0
    positions_opened = 0
    positions_closed = 0
    liquidity_skips = 0
    partial_entries = 0
    unfilled_entry_notional = 0.0
    exit_liquidity_skips = 0
    partial_exits = 0
    slippage_cost_total = 0.0
    realized_pnl = 0.0
    processed_count = 0
    positions: dict[str, Position] = {}
    latest_rows: dict[str, dict[str, str]] = {}
    last_valid_bids: dict[str, dict[Side, float]] = {}
    exit_skip_markets: set[str] = set()
    unfilled_exit_notional_by_market: dict[str, float] = {}
    events: list[SurvivalEvent] = []
    event_equity_curve: list[float] = [initial_bankroll]
    timestamp_equity_marks: list[tuple[datetime, float]] = []
    forecast_model = provider.name
    ordered_rows = [] if timestamp_order_policy == "position_first" else order_rows_for_timestamp_policy(rows, timestamp_order_policy)

    def record_equity(equity: float, timestamp: str) -> None:
        event_equity_curve.append(equity)
        timestamp_equity_marks.append((parse_timestamp(timestamp), equity))

    def iter_ordered_rows():
        if timestamp_order_policy != "position_first":
            yield from ordered_rows
            return
        for batch in timestamp_batches(rows):
            for row in batch:
                latest_rows[row["market_id"]] = row
                update_last_valid_bids(last_valid_bids, row["market_id"], row)
            yield from sorted(batch, key=lambda row: (0 if row["market_id"] in positions else 1, row["market_id"]))

    for row in iter_ordered_rows():
        if state == "DEAD":
            break
        processed_count += 1
        if timestamp_order_policy != "position_first":
            latest_rows[row["market_id"]] = row
            update_last_valid_bids(last_valid_bids, row["market_id"], row)
        row_time = parse_timestamp(row["logged_at"])

        cash, closed, pnl, settlement_events = settle_due_positions(
            positions,
            resolutions,
            row["logged_at"],
            row_time,
            cash,
            latest_rows,
            last_valid_bids,
            missing_quote_policy,
        )
        if settlement_events:
            positions_closed += closed
            realized_pnl += pnl
            for event in settlement_events:
                unfilled_exit_notional_by_market.pop(event.market_id, None)
                exit_skip_markets.discard(event.market_id)
            events.extend(settlement_events)
            equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
            record_equity(equity, row["logged_at"])
            if equity <= death_threshold:
                state = "DEAD"
                death_reason = "equity_below_death_threshold"
                events.append(
                    SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], "", cash, equity, death_reason)
                )
                break
        if state == "DEAD":
            break
        if row["market_id"] in resolutions and resolution_due(row_time, resolutions[row["market_id"]]):
            continue

        if forecast_call_policy == "actionable":
            if row["market_id"] in positions and exit_policy == "none":
                equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
                events.append(
                    SurvivalEvent(
                        row["logged_at"],
                        "SKIP_FORECAST_HELD_NO_EXIT",
                        row["market_id"],
                        positions[row["market_id"]].side.value,
                        cash,
                        equity,
                        "forecast_skipped=true",
                    )
                )
                record_equity(equity, row["logged_at"])
                if equity <= death_threshold:
                    state = "DEAD"
                    death_reason = "equity_below_death_threshold"
                    events.append(
                        SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], "", cash, equity, death_reason)
                    )
                    break
                continue
            if row["market_id"] not in positions and len(positions) >= max_positions:
                equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
                events.append(
                    SurvivalEvent(
                        row["logged_at"],
                        "SKIP_FORECAST_MAX_POSITIONS",
                        row["market_id"],
                        "",
                        cash,
                        equity,
                        "forecast_skipped=true",
                    )
                )
                record_equity(equity, row["logged_at"])
                if equity <= death_threshold:
                    state = "DEAD"
                    death_reason = "equity_below_death_threshold"
                    events.append(
                        SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], "", cash, equity, death_reason)
                    )
                    break
                continue

        forecast = provider.forecast(row)
        forecast_calls += 1
        forecast_model = forecast.model
        if forecast.cost > 0 and forecast.cost > cash:
            forecast_cost_total += cash
            cash = 0.0
            equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
            record_equity(equity, row["logged_at"])
            state = "DEAD"
            death_reason = "cash_depleted_by_forecast_cost"
            events.append(
                SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], "", cash, equity, death_reason)
            )
            break
        cash -= forecast.cost
        forecast_cost_total += forecast.cost

        equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
        record_equity(equity, row["logged_at"])
        if equity <= death_threshold:
            state = "DEAD"
            death_reason = "equity_below_death_threshold"
            events.append(
                SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], "", cash, equity, death_reason)
            )
            break

        if row["market_id"] in positions and should_exit_position(
            positions[row["market_id"]],
            row,
            forecast.fair_yes,
            exit_policy,
            exit_edge_threshold,
            last_valid_bids,
            missing_quote_policy,
        ):
            position = positions[row["market_id"]]
            proceeds, pnl, closed, unfilled_notional, slippage_cost, event = execute_exit(
                position,
                row,
                forecast.fair_yes,
                exit_liquidity_model,
                max_exit_depth_fraction,
                slippage_model,
                max_slippage_bps,
                last_valid_bids,
                missing_quote_policy,
            )
            if event.event_type == "SKIP_EXIT_LIQUIDITY_DEPTH":
                if position.market_id not in exit_skip_markets:
                    exit_liquidity_skips += 1
                    exit_skip_markets.add(position.market_id)
                unfilled_exit_notional_by_market[position.market_id] = unfilled_notional
                events.append(
                    SurvivalEvent(
                        event.timestamp,
                        event.event_type,
                        event.market_id,
                        event.side,
                        cash,
                        equity,
                        event.detail,
                    )
                )
                continue
            if closed:
                positions.pop(row["market_id"])
                positions_closed += 1
                unfilled_exit_notional_by_market.pop(row["market_id"], None)
                exit_skip_markets.discard(row["market_id"])
            else:
                partial_exits += 1
                unfilled_exit_notional_by_market[position.market_id] = unfilled_notional
            cash += proceeds
            realized_pnl += pnl
            slippage_cost_total += slippage_cost
            equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
            events.append(
                SurvivalEvent(
                    event.timestamp,
                    event.event_type,
                    event.market_id,
                    event.side,
                    cash,
                    equity,
                    event.detail,
                )
            )
            record_equity(equity, row["logged_at"])
            if equity <= death_threshold:
                state = "DEAD"
                death_reason = "equity_below_death_threshold"
                events.append(
                    SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], event.side, cash, equity, death_reason)
                )
                break
            continue
        unfilled_exit_notional_by_market.pop(row["market_id"], None)
        exit_skip_markets.discard(row["market_id"])

        snapshot = MarketSnapshot(
            timestamp=parse_timestamp(row["logged_at"]),
            market_id=row["market_id"],
            question=row["question"],
            yes_price=safe_float(row.get("yes_ask")),
            no_price=safe_float(row.get("no_ask")),
            fair_yes=forecast.fair_yes,
            liquidity=safe_float(row.get("liquidity")),
            volume_24h=safe_float(row.get("volume_24h")),
        )
        signal = build_signal(snapshot, edge_threshold=edge_threshold, max_fraction=max_fraction)
        if signal is None:
            continue
        signals_seen += 1
        if row["market_id"] in positions:
            events.append(
                SurvivalEvent(row["logged_at"], "SKIP_EXISTING_POSITION", row["market_id"], signal.side.value, cash, equity, "")
            )
            continue
        if len(positions) >= max_positions:
            events.append(
                SurvivalEvent(row["logged_at"], "SKIP_MAX_POSITIONS", row["market_id"], signal.side.value, cash, equity, "")
            )
            continue

        budget = cash * signal.fraction
        if budget <= 0 or budget > cash:
            events.append(
                SurvivalEvent(row["logged_at"], "SKIP_NO_CASH", row["market_id"], signal.side.value, cash, equity, "")
            )
            continue
        filled_budget, partial_entry, entry_unfilled_notional, available_notional, liquidity_detail = entry_budget_for_fill_policy(
            row,
            signal.side,
            signal.price,
            budget,
            liquidity_model,
            max_depth_fraction,
            entry_fill_policy,
        )
        if filled_budget <= EPSILON:
            liquidity_skips += 1
            unfilled_entry_notional += entry_unfilled_notional
            events.append(
                SurvivalEvent(
                    row["logged_at"],
                    "SKIP_LIQUIDITY_DEPTH",
                    row["market_id"],
                    signal.side.value,
                    cash,
                    equity,
                    liquidity_detail,
                )
            )
            continue
        if partial_entry:
            partial_entries += 1
            unfilled_entry_notional += entry_unfilled_notional
        exec_price, _, depth_utilization = slippage_adjusted_price(
            signal.price,
            filled_budget,
            available_notional,
            slippage_model,
            max_slippage_bps,
            "buy",
        )
        if exec_price <= EPSILON:
            events.append(
                SurvivalEvent(row["logged_at"], "SKIP_NO_EXEC_PRICE", row["market_id"], signal.side.value, cash, equity, "")
            )
            continue
        shares = filled_budget / exec_price
        entry_slippage_cost = filled_budget - (shares * signal.price)
        slippage_cost_total += max(0.0, entry_slippage_cost)
        cash -= filled_budget
        positions[row["market_id"]] = Position(
            market_id=row["market_id"],
            side=signal.side,
            shares=shares,
            entry_price=exec_price,
            entry_time=parse_timestamp(row["logged_at"]),
            cost=filled_budget,
        )
        positions_opened += 1
        equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
        record_equity(equity, row["logged_at"])
        events.append(
            SurvivalEvent(
                timestamp=row["logged_at"],
                event_type="OPEN_POSITION",
                market_id=row["market_id"],
                side=signal.side.value,
                cash=cash,
                equity=equity,
                detail=(
                    f"edge={signal.edge:.6f};fraction={signal.fraction:.6f};cost={filled_budget:.6f};"
                    f"requested_cost={budget:.6f};quoted_price={signal.price:.6f};entry_price={exec_price:.6f};"
                    f"partial_entry={str(partial_entry).lower()};depth_utilization={depth_utilization:.6f};"
                    f"slippage_cost={entry_slippage_cost:.6f};{liquidity_detail}"
                ),
            )
        )
        if equity <= death_threshold:
            state = "DEAD"
            death_reason = "equity_depleted_after_position"
            events.append(
                SurvivalEvent(row["logged_at"], "DEAD", row["market_id"], signal.side.value, cash, equity, death_reason)
            )
            break

    final_equity = cash + mark_positions(positions, latest_rows, last_valid_bids, missing_quote_policy)
    event_drawdown_curve = drawdown_curve_for_policy(
        initial_bankroll,
        final_equity,
        event_equity_curve,
        timestamp_equity_marks,
        "event",
    )
    timestamp_close_drawdown_curve = drawdown_curve_for_policy(
        initial_bankroll,
        final_equity,
        event_equity_curve,
        timestamp_equity_marks,
        "timestamp_close",
    )
    drawdown_curve = drawdown_curve_for_policy(
        initial_bankroll,
        final_equity,
        event_equity_curve,
        timestamp_equity_marks,
        drawdown_policy,
    )
    event_drawdown = max_drawdown(event_drawdown_curve)
    timestamp_close_drawdown = max_drawdown(timestamp_close_drawdown_curve)
    result = SurvivalResult(
        state=state,
        death_reason=death_reason,
        initial_bankroll=initial_bankroll,
        final_cash=cash,
        final_equity=final_equity,
        rows_processed=processed_count,
        forecast_calls=forecast_calls,
        forecast_cost_total=forecast_cost_total,
        signals_seen=signals_seen,
        positions_opened=positions_opened,
        positions_closed=positions_closed,
        liquidity_skips=liquidity_skips,
        partial_entries=partial_entries,
        unfilled_entry_notional=unfilled_entry_notional,
        exit_liquidity_skips=exit_liquidity_skips,
        partial_exits=partial_exits,
        unfilled_exit_notional=sum(unfilled_exit_notional_by_market.values()),
        slippage_cost_total=slippage_cost_total,
        realized_pnl=realized_pnl,
        open_positions=len(positions),
        max_drawdown=max_drawdown(drawdown_curve),
        event_max_drawdown=event_drawdown,
        timestamp_close_max_drawdown=timestamp_close_drawdown,
        drawdown_policy=drawdown_policy,
        forecast_model=forecast_model,
    )
    return result, events


def write_survival_outputs(result: SurvivalResult, events: list[SurvivalEvent], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = out_dir / f"survival_report_{stamp}.json"
    events_path = out_dir / f"survival_events_{stamp}.csv"
    atomic_write_text(report_path, json.dumps(asdict(result), indent=2, ensure_ascii=False))
    if events:
        tmp_path = events_path.with_suffix(events_path.suffix + ".tmp")
        with tmp_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(events[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(event) for event in events)
        os.replace(tmp_path, events_path)
    else:
        atomic_write_text(events_path, "timestamp,event_type,market_id,side,cash,equity,detail\n")
    for source, destination in (
        (report_path, out_dir / "latest_survival_report.json"),
        (events_path, out_dir / "latest_survival_events.csv"),
    ):
        tmp_path = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copyfile(source, tmp_path)
        os.replace(tmp_path, destination)
    return {"report_path": str(report_path), "events_path": str(events_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paper survival accounting over forward logger snapshots.")
    parser.add_argument("--input-dir", default="data/paper/live_snapshots")
    parser.add_argument("--out-dir", default="data/paper/survival")
    parser.add_argument("--bankroll", type=float, default=50.0)
    parser.add_argument("--edge-threshold", type=float, default=0.08)
    parser.add_argument("--max-fraction", type=float, default=0.06)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--death-threshold", type=float, default=0.0)
    parser.add_argument("--resolutions-csv")
    parser.add_argument("--exit-policy", default="none", choices=["none", "edge_below"])
    parser.add_argument("--exit-edge-threshold", type=float, default=0.0)
    parser.add_argument("--liquidity-model", default="none", choices=["none", "top3_ask"])
    parser.add_argument("--max-depth-fraction", type=float, default=0.25)
    parser.add_argument("--entry-fill-policy", default="all_or_none", choices=["all_or_none", "partial"])
    parser.add_argument("--exit-liquidity-model", default="none", choices=["none", "top3_bid"])
    parser.add_argument("--max-exit-depth-fraction", type=float, default=0.25)
    parser.add_argument("--slippage-model", default="none", choices=["none", "depth_utilization"])
    parser.add_argument("--max-slippage-bps", type=float, default=50.0)
    parser.add_argument("--missing-quote-policy", default="zero", choices=["zero", "last_valid_bid"])
    parser.add_argument("--forecast-call-policy", default="always", choices=["always", "actionable"])
    parser.add_argument("--timestamp-order-policy", default="sequential", choices=["sequential", "history_first", "position_first"])
    parser.add_argument("--drawdown-policy", default="event", choices=["event", "timestamp_close"])
    parser.add_argument("--forecast-mode", default="recorded", choices=["recorded", "rule_baseline", "synthetic_edge"])
    parser.add_argument("--forecasts-file", help="Optional CSV or JSONL forecasts file keyed by logged_at and market_id.")
    parser.add_argument("--allow-missing-forecasts", action="store_true")
    parser.add_argument("--forecast-cost", type=float, default=0.0)
    parser.add_argument("--synthetic-edge", type=float, default=0.12)
    parser.add_argument("--synthetic-side", default="YES", choices=["YES", "NO"])
    args = parser.parse_args()

    rows = load_paper_rows(Path(args.input_dir))
    if args.forecasts_file:
        provider = ForecastFileProvider(Path(args.forecasts_file), allow_missing=args.allow_missing_forecasts)
    else:
        provider = create_forecast_provider(
            args.forecast_mode,
            cost_per_forecast=args.forecast_cost,
            synthetic_edge=args.synthetic_edge,
            synthetic_side=args.synthetic_side,
        )
    resolutions = load_resolutions(Path(args.resolutions_csv)) if args.resolutions_csv else {}
    result, events = simulate_survival(
        rows,
        provider=provider,
        resolutions=resolutions,
        initial_bankroll=args.bankroll,
        edge_threshold=args.edge_threshold,
        max_fraction=args.max_fraction,
        max_positions=args.max_positions,
        death_threshold=args.death_threshold,
        exit_policy=args.exit_policy,
        exit_edge_threshold=args.exit_edge_threshold,
        liquidity_model=args.liquidity_model,
        max_depth_fraction=args.max_depth_fraction,
        entry_fill_policy=args.entry_fill_policy,
        exit_liquidity_model=args.exit_liquidity_model,
        max_exit_depth_fraction=args.max_exit_depth_fraction,
        slippage_model=args.slippage_model,
        max_slippage_bps=args.max_slippage_bps,
        missing_quote_policy=args.missing_quote_policy,
        forecast_call_policy=args.forecast_call_policy,
        timestamp_order_policy=args.timestamp_order_policy,
        drawdown_policy=args.drawdown_policy,
    )
    paths = write_survival_outputs(result, events, Path(args.out_dir))
    for key, value in asdict(result).items():
        print(f"{key}={value}")
    for key, value in paths.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
