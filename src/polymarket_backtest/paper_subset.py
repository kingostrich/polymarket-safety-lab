from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .survival import load_paper_rows, parse_timestamp


SUBSET_FILE_RE = re.compile(r"^paper_signals_subset_\d{8}T\d{6}Z\.(csv|jsonl)$")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    os.replace(tmp_path, path)


def cleanup_generated_subset_files(out_dir: Path, keep: set[Path] | None = None) -> None:
    keep = {path.resolve() for path in keep or set()}
    for path in out_dir.iterdir():
        if path.resolve() in keep:
            continue
        if SUBSET_FILE_RE.match(path.name):
            path.unlink()


def cleanup_tmp_files(out_dir: Path) -> None:
    for path in out_dir.iterdir():
        if path.name.endswith(".tmp"):
            path.unlink()


def remove_paths(paths: list[Path]) -> None:
    for path in paths:
        if path.exists():
            path.unlink()


def snapshot_files(paths: list[Path]) -> dict[Path, str | None]:
    return {path: path.read_text() if path.exists() else None for path in paths}


def restore_files(snapshot: dict[Path, str | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            if path.exists():
                path.unlink()
            continue
        atomic_write_text(path, content)


def write_subset_rows(
    rows: list[dict[str, str]],
    out_dir: Path,
    input_dir: Path,
    start_index: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    if start_index < 0:
        raise ValueError("start_index must be non-negative")
    if limit <= 0:
        raise ValueError("limit must be positive")

    selected = rows[start_index : start_index + limit]
    if not selected:
        raise ValueError("no source rows selected")

    out_dir.mkdir(parents=True, exist_ok=True)
    cleanup_tmp_files(out_dir)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = out_dir / f"paper_signals_subset_{stamp}.csv"
    jsonl_path = out_dir / f"paper_signals_subset_{stamp}.jsonl"
    latest_csv_path = out_dir / "latest_paper_signals.csv"
    latest_jsonl_path = out_dir / "latest_paper_signals.jsonl"
    latest_manifest_path = out_dir / "latest_manifest.json"
    latest_snapshot = snapshot_files([latest_csv_path, latest_jsonl_path, latest_manifest_path])
    fieldnames = list(selected[0].keys())

    tmp_csv_path = csv_path.with_suffix(csv_path.suffix + ".tmp")
    try:
        with tmp_csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(selected)
        os.replace(tmp_csv_path, csv_path)

        jsonl_content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected)
        atomic_write_text(jsonl_path, jsonl_content)

        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "input_dir": str(input_dir),
            "out_dir": str(out_dir),
            "source_records": len(rows),
            "records": len(selected),
            "start_index": start_index,
            "limit": limit,
            "signals": sum(1 for row in selected if row.get("action") == "paper_signal"),
            "skips": sum(1 for row in selected if row.get("action") == "skip"),
            "csv_path": str(csv_path),
            "jsonl_path": str(jsonl_path),
            "note": "Subset for model forecast benchmarking only. No orders were placed.",
        }
        atomic_write_text(latest_csv_path, csv_path.read_text())
        atomic_write_text(latest_jsonl_path, jsonl_path.read_text())
        atomic_write_text(latest_manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False))
    except BaseException:
        remove_paths([tmp_csv_path, csv_path, jsonl_path])
        restore_files(latest_snapshot)
        cleanup_tmp_files(out_dir)
        raise

    cleanup_generated_subset_files(out_dir, keep={csv_path, jsonl_path})
    return manifest


def run_subset(input_dir: Path, out_dir: Path, start_index: int = 0, limit: int = 20) -> dict[str, Any]:
    source_rows = sorted(load_paper_rows(input_dir), key=lambda row: (parse_timestamp(row["logged_at"]), row["market_id"]))
    if not source_rows:
        raise ValueError(f"no paper rows found in {input_dir}")
    return write_subset_rows(
        source_rows,
        out_dir=out_dir,
        input_dir=input_dir,
        start_index=start_index,
        limit=limit,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a small paper-signal subset for model forecast benchmarking.")
    parser.add_argument("--input-dir", default="data/paper/live_snapshots")
    parser.add_argument("--out-dir", default="data/paper/model_bench_20")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    manifest = run_subset(
        input_dir=Path(args.input_dir),
        out_dir=Path(args.out_dir),
        start_index=args.start_index,
        limit=args.limit,
    )
    for key, value in manifest.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
