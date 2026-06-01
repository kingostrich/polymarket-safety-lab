from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .strategy_readiness import load_benchmark_manifest, load_json


@dataclass(frozen=True)
class VariantRow:
    rank: int
    benchmark_name: str
    provider: str
    model: str
    source_rows: int
    initial_bankroll: float
    final_equity: float
    mark_pnl: float
    return_pct: float
    event_max_drawdown: float
    survival_state: str
    positions_opened: int
    positions_closed: int
    open_positions: int
    resolutions_loaded: int
    market_echo_share_1bp: float
    actionable_rows: int
    baseline_equity: float
    baseline_return_pct: float
    pnl_vs_baseline: float
    return_vs_baseline: float
    readiness_decision: str
    risk_flags: str
    manifest_path: str


def _float(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key, default)
    if value in ("", None):
        return default
    return float(value)


def _int(payload: dict[str, Any], key: str, default: int = 0) -> int:
    value = payload.get(key, default)
    if value in ("", None):
        return default
    return int(value)


def _str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return "" if value is None else str(value)


def discover_manifest_paths(forecast_root: Path, include_patterns: list[str] | None = None) -> list[Path]:
    paths = sorted(forecast_root.glob("*/latest_benchmark_manifest.json"))
    if not include_patterns:
        return paths
    return [
        path
        for path in paths
        if any(pattern in path.as_posix() for pattern in include_patterns)
    ]


def load_manifests(paths: list[Path]) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        rows.append((path, load_benchmark_manifest(path)))
    return rows


def is_baseline(manifest: dict[str, Any]) -> bool:
    provider = _str(manifest, "provider").lower()
    benchmark = _str(manifest, "benchmark_name").lower()
    model = _str(manifest, "model").lower()
    return provider == "rule_baseline" or benchmark.startswith("rule_baseline") or model.startswith("rule_baseline")


def return_pct(initial: float, final: float) -> float:
    if initial <= 0:
        return 0.0
    return (final - initial) / initial


def baseline_by_source_rows(manifests: list[tuple[Path, dict[str, Any]]]) -> dict[int, tuple[float, float, float]]:
    baselines: dict[int, tuple[float, float, float]] = {}
    for _, manifest in manifests:
        if not is_baseline(manifest):
            continue
        source_rows = _int(manifest, "source_rows")
        initial = _float(manifest, "bankroll", _float(manifest, "initial_bankroll"))
        final_equity = _float(manifest, "final_equity")
        baseline_return = return_pct(initial, final_equity)
        current = baselines.get(source_rows)
        if current is None or baseline_return > current[2]:
            baselines[source_rows] = (initial, final_equity, baseline_return)
    return baselines


def risk_flags(
    manifest: dict[str, Any],
    baseline_return_pct: float,
    max_drawdown_limit: float,
) -> str:
    flags: list[str] = []
    initial = _float(manifest, "bankroll", _float(manifest, "initial_bankroll"))
    final = _float(manifest, "final_equity")
    row_return = return_pct(initial, final)
    open_positions = _int(manifest, "open_positions")
    positions_opened = _int(manifest, "positions_opened")
    positions_closed = _int(manifest, "positions_closed")
    resolutions_loaded = _int(manifest, "resolutions_loaded")
    if _str(manifest, "survival_state") != "ALIVE":
        flags.append("not_alive")
    if initial > 0 and final < initial:
        flags.append("loss_vs_initial")
    if row_return < baseline_return_pct:
        flags.append("under_baseline")
    if positions_opened == 0:
        flags.append("no_trades")
    if open_positions > 0:
        flags.append("open_positions")
    if positions_closed == 0:
        flags.append("no_closed_trades")
    if positions_opened > 0 and resolutions_loaded == 0 and open_positions > 0:
        flags.append("no_official_resolutions")
    elif positions_opened > 0 and resolutions_loaded == 0:
        flags.append("no_official_resolutions_after_market_exit")
    if _float(manifest, "market_echo_share_1bp") >= 0.5:
        flags.append("market_echo")
    if _float(manifest, "event_max_drawdown") > max_drawdown_limit:
        flags.append("drawdown_over_limit")
    return ";".join(flags)


def readiness_decision_for_row(flags: str) -> str:
    blockers = {
        "not_alive",
        "loss_vs_initial",
        "under_baseline",
        "open_positions",
        "no_closed_trades",
        "no_official_resolutions",
        "drawdown_over_limit",
    }
    row_flags = set(flags.split(";")) if flags else set()
    return "NO_LIVE_TRADING" if row_flags & blockers else "PAPER_ONLY_REVIEW"


def row_sort_key(row: VariantRow) -> tuple:
    return (
        0 if row.source_rows >= 100 else 1,
        0 if row.readiness_decision == "PAPER_ONLY_REVIEW" else 1,
        -row.return_vs_baseline,
        row.event_max_drawdown,
        row.open_positions,
        row.benchmark_name,
    )


def build_variant_rows(
    manifests: list[tuple[Path, dict[str, Any]]],
    source_rows_filter: int = 0,
    max_drawdown_limit: float = 0.25,
) -> list[VariantRow]:
    baselines = baseline_by_source_rows(manifests)
    rows: list[VariantRow] = []
    for manifest_path, manifest in manifests:
        source_rows = _int(manifest, "source_rows")
        if source_rows_filter > 0 and source_rows != source_rows_filter:
            continue
        initial = _float(manifest, "bankroll", _float(manifest, "initial_bankroll"))
        final = _float(manifest, "final_equity")
        row_return = return_pct(initial, final)
        _, baseline_equity, baseline_return = baselines.get(source_rows, (initial, initial, 0.0))
        flags = risk_flags(
            manifest,
            baseline_return_pct=baseline_return,
            max_drawdown_limit=max_drawdown_limit,
        )
        rows.append(
            VariantRow(
                rank=0,
                benchmark_name=_str(manifest, "benchmark_name") or manifest_path.parent.name,
                provider=_str(manifest, "provider"),
                model=_str(manifest, "model"),
                source_rows=source_rows,
                initial_bankroll=initial,
                final_equity=final,
                mark_pnl=final - initial,
                return_pct=row_return,
                event_max_drawdown=_float(manifest, "event_max_drawdown"),
                survival_state=_str(manifest, "survival_state"),
                positions_opened=_int(manifest, "positions_opened"),
                positions_closed=_int(manifest, "positions_closed"),
                open_positions=_int(manifest, "open_positions"),
                resolutions_loaded=_int(manifest, "resolutions_loaded"),
                market_echo_share_1bp=_float(manifest, "market_echo_share_1bp"),
                actionable_rows=_int(manifest, "actionable_rows"),
                baseline_equity=baseline_equity,
                baseline_return_pct=baseline_return,
                pnl_vs_baseline=final - baseline_equity,
                return_vs_baseline=row_return - baseline_return,
                readiness_decision=readiness_decision_for_row(flags),
                risk_flags=flags,
                manifest_path=str(manifest_path),
            )
        )
    ranked = sorted(rows, key=row_sort_key)
    return [
        VariantRow(**{**asdict(row), "rank": index + 1})
        for index, row in enumerate(ranked)
    ]


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def write_csv(rows: list[VariantRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(VariantRow.__dataclass_fields__.keys())
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    os.replace(tmp_path, path)


def write_markdown(rows: list[VariantRow], path: Path, readiness: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Model Variant Comparison",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "This report compares paper-only benchmark manifests. It is not a live-trading approval.",
        "",
    ]
    if readiness:
        lines.extend(
            [
                "## Current Gate",
                "",
                f"- Strategy readiness decision: `{readiness.get('decision', '')}`",
                f"- Blockers: `{readiness.get('blocker_count', '')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Variants",
            "",
            "| rank | benchmark | rows | provider | mark equity | return | vs baseline | MDD | opened | closed | open | echo <=1bp | decision | risk flags |",
            "|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row.rank} | `{row.benchmark_name}` | {row.source_rows} | {row.provider} | "
            f"{row.final_equity:.4f} | {row.return_pct:.2%} | {row.return_vs_baseline:.2%} | "
            f"{row.event_max_drawdown:.2%} | {row.positions_opened} | {row.positions_closed} | "
            f"{row.open_positions} | {row.market_echo_share_1bp:.2%} | `{row.readiness_decision}` | `{row.risk_flags}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A no-trade or market-echo baseline can rank above an active model if the active model loses money.",
            "- `NO_LIVE_TRADING` on any row means that variant still fails one or more paper-safety conditions.",
            "- Oracle settlement smoke is intentionally excluded from this model-variant table because it uses resolved outcomes.",
            "",
        ]
    )
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp_path, path)


def build_report(
    forecast_root: Path,
    output_csv: Path,
    output_json: Path,
    output_md: Path,
    source_rows_filter: int = 0,
    readiness_json: Path | None = None,
    include_patterns: list[str] | None = None,
    max_drawdown_limit: float = 0.25,
) -> dict[str, Any]:
    manifests = load_manifests(discover_manifest_paths(forecast_root, include_patterns=include_patterns))
    rows = build_variant_rows(
        manifests,
        source_rows_filter=source_rows_filter,
        max_drawdown_limit=max_drawdown_limit,
    )
    readiness = load_json(readiness_json) if readiness_json and readiness_json.exists() else None
    write_csv(rows, output_csv)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "forecast_root": str(forecast_root),
        "source_rows_filter": source_rows_filter,
        "variant_count": len(rows),
        "rows": [asdict(row) for row in rows],
        "note": "Paper comparison only. No orders were placed, signed, or submitted.",
    }
    atomic_write_json(output_json, payload)
    write_markdown(rows, output_md, readiness=readiness)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare model benchmark variants using paper-only manifests.")
    parser.add_argument("--forecast-root", default="data/forecasts")
    parser.add_argument("--output-csv", default="data/forecasts/model_variant_comparison.csv")
    parser.add_argument("--output-json", default="data/forecasts/model_variant_comparison.json")
    parser.add_argument("--output-md", default="docs/model_variant_comparison.md")
    parser.add_argument("--source-rows", type=int, default=0)
    parser.add_argument("--readiness-json", default="data/readiness/latest_strategy_readiness.json")
    parser.add_argument("--include-pattern", action="append", default=[])
    parser.add_argument("--max-drawdown-limit", type=float, default=0.25)
    args = parser.parse_args()

    payload = build_report(
        forecast_root=Path(args.forecast_root),
        output_csv=Path(args.output_csv),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        source_rows_filter=args.source_rows,
        readiness_json=Path(args.readiness_json) if args.readiness_json else None,
        include_patterns=args.include_pattern or None,
        max_drawdown_limit=args.max_drawdown_limit,
    )
    print(f"variant_count={payload['variant_count']}")
    print(f"output_csv={args.output_csv}")
    print(f"output_json={args.output_json}")
    print(f"output_md={args.output_md}")


if __name__ == "__main__":
    main()
