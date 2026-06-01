from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import BacktestResult, ClosedTrade, MarketSnapshot, Position, Side
from .strategy import build_signal


def parse_side(value: str) -> Side | None:
    cleaned = value.strip().upper()
    if not cleaned:
        return None
    return Side(cleaned)


def load_snapshots(path: str | Path) -> list[MarketSnapshot]:
    snapshots: list[MarketSnapshot] = []
    with Path(path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            snapshots.append(
                MarketSnapshot(
                    timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                    market_id=row["market_id"],
                    question=row["question"],
                    yes_price=float(row["yes_price"]),
                    no_price=float(row["no_price"]),
                    fair_yes=float(row["fair_yes"]),
                    liquidity=float(row.get("liquidity") or 0),
                    volume_24h=float(row.get("volume_24h") or 0),
                    resolved_outcome=parse_side(row.get("resolved_outcome", "")),
                    fee_rate=float(row.get("fee_rate") or 0),
                )
            )
    return sorted(snapshots, key=lambda item: item.timestamp)


def taker_fee(shares: float, price: float, fee_rate: float) -> float:
    return shares * fee_rate * price * (1.0 - price)


def mark_position(position: Position, snapshot: MarketSnapshot) -> float:
    price = snapshot.yes_price if position.side is Side.YES else snapshot.no_price
    return position.shares * price


def max_drawdown(equity_curve: list[tuple[datetime, float]]) -> float:
    peak = 0.0
    worst = 0.0
    for _, equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, (equity - peak) / peak)
    return abs(worst)


def run_backtest(
    snapshots: list[MarketSnapshot],
    initial_bankroll: float = 100.0,
    edge_threshold: float = 0.08,
    max_fraction: float = 0.06,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    cash = initial_bankroll
    positions: dict[str, Position] = {}
    latest_by_market: dict[str, MarketSnapshot] = {}
    closed: list[ClosedTrade] = []
    equity_curve: list[tuple[datetime, float]] = []
    slippage_multiplier = 1.0 + slippage_bps / 10_000.0

    for snapshot in snapshots:
        latest_by_market[snapshot.market_id] = snapshot

        if snapshot.resolved_outcome is not None and snapshot.market_id in positions:
            position = positions.pop(snapshot.market_id)
            exit_price = 1.0 if position.side is snapshot.resolved_outcome else 0.0
            proceeds = position.shares * exit_price
            pnl = proceeds - position.cost - position.fees_paid
            cash += proceeds
            closed.append(
                ClosedTrade(
                    market_id=position.market_id,
                    side=position.side,
                    entry_time=position.entry_time,
                    exit_time=snapshot.timestamp,
                    shares=position.shares,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    pnl=pnl,
                    fees_paid=position.fees_paid,
                )
            )
        elif snapshot.market_id not in positions:
            signal = build_signal(snapshot, edge_threshold=edge_threshold, max_fraction=max_fraction)
            if signal is not None and cash > 0:
                execution_price = min(signal.price * slippage_multiplier, 0.999999)
                budget = cash * signal.fraction
                if budget > 0:
                    shares = budget / execution_price
                    fee = taker_fee(shares, execution_price, snapshot.fee_rate)
                    total_cost = budget + fee
                    if total_cost <= cash:
                        cash -= total_cost
                        positions[signal.market_id] = Position(
                            market_id=signal.market_id,
                            side=signal.side,
                            shares=shares,
                            entry_price=execution_price,
                            entry_time=snapshot.timestamp,
                            cost=budget,
                            fees_paid=fee,
                        )

        marked_value = 0.0
        for position in positions.values():
            latest = latest_by_market.get(position.market_id)
            if latest is not None:
                marked_value += mark_position(position, latest)
        equity_curve.append((snapshot.timestamp, cash + marked_value))

    final_equity = equity_curve[-1][1] if equity_curve else initial_bankroll
    wins = sum(1 for trade in closed if trade.pnl > 0)
    win_rate = wins / len(closed) if closed else 0.0
    return BacktestResult(
        initial_bankroll=initial_bankroll,
        final_equity=final_equity,
        total_return=(final_equity / initial_bankroll) - 1.0 if initial_bankroll else 0.0,
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate,
        closed_trades=tuple(closed),
        equity_curve=tuple(equity_curve),
    )
