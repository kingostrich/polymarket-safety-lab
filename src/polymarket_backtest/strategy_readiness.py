from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    severity: str
    observed: str
    required: str
    detail: str


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_benchmark_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    report_path = manifest.get("survival_report_path")
    if not report_path:
        return manifest
    survival_path = Path(str(report_path))
    if not survival_path.is_absolute() and not survival_path.exists():
        survival_path = path.parent / survival_path
    if not survival_path.exists():
        return manifest
    survival_report = load_json(survival_path)
    for key in [
        "open_positions",
        "positions_closed",
        "positions_opened",
        "realized_pnl",
        "event_max_drawdown",
        "timestamp_close_max_drawdown",
    ]:
        if key in survival_report:
            manifest[key] = survival_report[key]
    return manifest


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


def _has_number(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if value in ("", None):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _check(name: str, passed: bool, severity: str, observed: str, required: str, detail: str) -> ReadinessCheck:
    return ReadinessCheck(
        name=name,
        status="PASS" if passed else "FAIL",
        severity=severity,
        observed=observed,
        required=required,
        detail=detail,
    )


def assess_readiness(
    model_manifest: dict[str, Any],
    baseline_manifest: dict[str, Any],
    resolution_manifest: dict[str, Any],
    resolution_cycle_manifest: dict[str, Any],
    oracle_metrics: dict[str, Any],
    min_source_rows: int = 100,
    min_closed_trades: int = 30,
    max_drawdown_limit: float = 0.25,
) -> dict[str, Any]:
    model_equity = _float(model_manifest, "final_equity")
    baseline_equity = _float(baseline_manifest, "final_equity")
    bankroll = _float(model_manifest, "bankroll", 50.0)
    source_rows = _int(model_manifest, "source_rows")
    open_positions = _int(model_manifest, "open_positions")
    positions_closed = _int(model_manifest, "positions_closed")
    resolutions_loaded = _int(model_manifest, "resolutions_loaded")
    resolution_eligible = _int(resolution_manifest, "resolution_eligible")
    replay_ran = bool(resolution_cycle_manifest.get("replay_ran"))
    cycle_positions_closed = _int(resolution_cycle_manifest, "positions_closed")
    market_echo_share = _float(model_manifest, "market_echo_share_1bp")
    actionable_rows = _int(model_manifest, "actionable_rows")
    oracle_closed_trades = _int(oracle_metrics, "closed_trades")
    event_max_drawdown = _float(model_manifest, "event_max_drawdown")
    has_open_positions_field = _has_number(model_manifest, "open_positions")
    has_drawdown_field = _has_number(model_manifest, "event_max_drawdown")
    model_identity = " ".join(
        str(model_manifest.get(key, "")).lower()
        for key in ["benchmark_name", "provider", "model", "forecasts_file", "forecast_dir"]
    )

    checks = [
        _check(
            "sample_size",
            source_rows >= min_source_rows,
            "blocker",
            str(source_rows),
            f">= {min_source_rows} forward paper rows",
            "The current model benchmark must cover enough forward paper observations before any live-readiness claim.",
        ),
        _check(
            "beats_no_trade_baseline",
            model_equity > baseline_equity,
            "blocker",
            f"model={model_equity:.4f}, baseline={baseline_equity:.4f}",
            "model final equity > no-trade baseline final equity",
            "A losing active model should not advance toward live trading while a no-trade baseline preserves capital better.",
        ),
        _check(
            "non_negative_mark_pnl",
            model_equity >= bankroll,
            "blocker",
            f"mark_pnl={model_equity - bankroll:.4f}",
            "mark P&L >= 0 on forward paper benchmark",
            "Survival state alone is insufficient; the mark-to-market path must not be loss-making.",
        ),
        _check(
            "no_open_positions",
            has_open_positions_field and open_positions == 0,
            "blocker",
            str(open_positions) if has_open_positions_field else "missing open_positions",
            "0 open positions after replay",
            "Unsettled open exposure prevents treating the run as a completed performance sample.",
        ),
        _check(
            "official_forward_resolutions",
            resolutions_loaded > 0 or (replay_ran and cycle_positions_closed > 0),
            "blocker",
            f"resolutions_loaded={resolutions_loaded}, resolution_eligible={resolution_eligible}, replay_ran={replay_ran}",
            "at least one official closed forward resolution loaded into replay",
            "Forward paper settlement must be proven with official closed markets, not only near-binary open markets.",
        ),
        _check(
            "closed_trade_count",
            positions_closed >= min_closed_trades or cycle_positions_closed >= min_closed_trades,
            "blocker",
            f"model_closed={positions_closed}, cycle_closed={cycle_positions_closed}",
            f">= {min_closed_trades} closed non-oracle forward trades",
            "A live gate needs enough timestamp-valid closed trades to estimate realized P&L, win rate, and drawdown.",
        ),
        _check(
            "max_drawdown_under_limit",
            has_drawdown_field and event_max_drawdown <= max_drawdown_limit,
            "blocker",
            f"{event_max_drawdown:.4f}" if has_drawdown_field else "missing event_max_drawdown",
            f"event max drawdown <= {max_drawdown_limit:.2%}",
            "Final equity can hide path risk; readiness must include the worst observed equity drawdown.",
        ),
        _check(
            "not_market_echo",
            market_echo_share < 0.5 and actionable_rows > 0,
            "warning",
            f"market_echo_share_1bp={market_echo_share:.4f}, actionable_rows={actionable_rows}",
            "market echo share < 0.5 and actionable_rows > 0",
            "A model that mostly echoes the market midpoint is not providing independent signal.",
        ),
        _check(
            "oracle_smoke_is_accounting_only",
            oracle_closed_trades > 0 and "oracle" not in model_identity,
            "warning",
            f"oracle_closed_trades={oracle_closed_trades}",
            "oracle smoke exists and model identity does not contain oracle",
            "Oracle smoke uses resolved outcomes and lookahead. It validates settlement plumbing only.",
        ),
    ]
    blockers = [check for check in checks if check.status == "FAIL" and check.severity == "blocker"]
    warnings = [check for check in checks if check.status == "FAIL" and check.severity == "warning"]
    decision = "NO_LIVE_TRADING" if blockers else "PAPER_ONLY_REVIEW"
    next_actions = [
        "Continue paper logging and official resolution replay until closed forward trades exist.",
        "Do not route private keys, signing, live order placement, or asset movement through this scaffold.",
        "Only compare model variants after each produces timestamp-valid forecasts on the same forward rows.",
    ]
    if not blockers:
        next_actions.append("Run an external review and a larger non-oracle forward benchmark before considering a live-trading design review.")

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "decision": decision,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "checks": [asdict(check) for check in checks],
        "inputs": {
            "model_benchmark_name": model_manifest.get("benchmark_name", ""),
            "baseline_benchmark_name": baseline_manifest.get("benchmark_name", ""),
            "resolution_cycle_replay_ran": replay_ran,
        },
        "summary": {
            "model_final_equity": model_equity,
            "baseline_final_equity": baseline_equity,
            "model_mark_pnl": model_equity - bankroll,
            "model_open_positions": open_positions,
            "model_positions_closed": positions_closed,
            "official_resolution_eligible": resolution_eligible,
            "oracle_closed_trades": oracle_closed_trades,
            "event_max_drawdown": event_max_drawdown if has_drawdown_field else "",
        },
        "next_actions": next_actions,
        "note": "Readiness gate only. No orders were placed, signed, or submitted.",
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def write_markdown(path: Path, readiness: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Strategy Readiness Gate",
        "",
        f"Generated: {readiness['created_at']}",
        "",
        f"Decision: `{readiness['decision']}`",
        "",
        "This gate is a paper-trading safety check. It does not place orders, sign messages, or move assets.",
        "",
        "## Summary",
        "",
    ]
    for key, value in readiness["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Checks", ""])
    lines.append("| Check | Status | Severity | Observed | Required |")
    lines.append("|---|---:|---:|---|---|")
    for check in readiness["checks"]:
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {check['observed']} | {check['required']} |"
        )
    lines.extend(["", "## Blocker Details", ""])
    blockers = [check for check in readiness["checks"] if check["status"] == "FAIL" and check["severity"] == "blocker"]
    if blockers:
        for check in blockers:
            lines.append(f"- `{check['name']}`: {check['detail']}")
    else:
        lines.append("- No blocker checks failed.")
    lines.extend(["", "## Next Actions", ""])
    for action in readiness["next_actions"]:
        lines.append(f"- {action}")
    lines.append("")
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp_path, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a conservative no-live-trading readiness gate from paper benchmark artifacts.")
    parser.add_argument("--model-manifest", default="data/forecasts/next_model_blind_100/latest_benchmark_manifest.json")
    parser.add_argument("--baseline-manifest", default="data/forecasts/rule_baseline_100/latest_benchmark_manifest.json")
    parser.add_argument("--resolution-manifest", default="data/paper/resolution_status/model_bench_100/resolution_manifest.json")
    parser.add_argument("--resolution-cycle-manifest", default="data/paper/resolution_status/model_bench_100/latest_resolution_replay_cycle.json")
    parser.add_argument("--oracle-metrics", default="data/backtests/polymarket_recent_binary_10_20260531/oracle_smoke/metrics.json")
    parser.add_argument("--out-json", default="data/readiness/latest_strategy_readiness.json")
    parser.add_argument("--out-md", default="docs/strategy_readiness_gate.md")
    parser.add_argument("--min-source-rows", type=int, default=100)
    parser.add_argument("--min-closed-trades", type=int, default=30)
    parser.add_argument("--max-drawdown-limit", type=float, default=0.25)
    args = parser.parse_args()

    readiness = assess_readiness(
        model_manifest=load_benchmark_manifest(Path(args.model_manifest)),
        baseline_manifest=load_benchmark_manifest(Path(args.baseline_manifest)),
        resolution_manifest=load_json(Path(args.resolution_manifest)),
        resolution_cycle_manifest=load_json(Path(args.resolution_cycle_manifest)),
        oracle_metrics=load_json(Path(args.oracle_metrics)),
        min_source_rows=args.min_source_rows,
        min_closed_trades=args.min_closed_trades,
        max_drawdown_limit=args.max_drawdown_limit,
    )
    atomic_write_json(Path(args.out_json), readiness)
    write_markdown(Path(args.out_md), readiness)
    for key in ["decision", "blocker_count", "warning_count"]:
        print(f"{key}={readiness[key]}")
    print(f"out_json={args.out_json}")
    print(f"out_md={args.out_md}")


if __name__ == "__main__":
    main()
