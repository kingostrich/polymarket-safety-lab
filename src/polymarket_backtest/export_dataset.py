from __future__ import annotations

import argparse
from pathlib import Path


def export_dataset(input_dir: Path, output_dir: Path) -> None:
    import duckdb

    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "polymarket_recent_binary.duckdb"
    connection = duckdb.connect(str(database_path))
    schemas = {
        "markets_closed_binary": """
            id VARCHAR,
            question VARCHAR,
            closed_time TIMESTAMPTZ,
            resolved_outcome VARCHAR,
            yes_token_id VARCHAR,
            no_token_id VARCHAR,
            final_yes_price DOUBLE,
            final_no_price DOUBLE,
            volume DOUBLE,
            liquidity DOUBLE,
            fee_type VARCHAR,
            fees_enabled BOOLEAN,
            order_min_size DOUBLE,
            order_tick_size DOUBLE
        """,
        "token_price_history": """
            market_id VARCHAR,
            token_id VARCHAR,
            side VARCHAR,
            timestamp BIGINT,
            price DOUBLE
        """,
        "snapshots_neutral": """
            timestamp TIMESTAMPTZ,
            market_id VARCHAR,
            question VARCHAR,
            yes_price DOUBLE,
            no_price DOUBLE,
            fair_yes DOUBLE,
            liquidity DOUBLE,
            volume_24h DOUBLE,
            resolved_outcome VARCHAR,
            fee_rate DOUBLE
        """,
    }
    csv_paths = {
        "markets_closed_binary": input_dir / "markets_closed_binary.csv",
        "token_price_history": input_dir / "token_price_history.csv",
        "snapshots_neutral": input_dir / "snapshots_neutral.csv",
    }
    for table, schema in schemas.items():
        csv_path = csv_paths[table]
        parquet_path = output_dir / f"{table}.parquet"
        connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute(f"CREATE TABLE {table} ({schema})")
        connection.execute(f"COPY {table} FROM ? (HEADER, DELIMITER ',')", [str(csv_path)])
        connection.execute(f"COPY {table} TO ? (FORMAT PARQUET)", [str(parquet_path)])
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export collected CSV data to DuckDB and Parquet.")
    parser.add_argument("--input-dir", default="data/normalized/polymarket_recent_binary")
    parser.add_argument("--output-dir", default="data/normalized/polymarket_recent_binary/export")
    args = parser.parse_args()
    export_dataset(Path(args.input_dir), Path(args.output_dir))
    print(f"exported={args.output_dir}")


if __name__ == "__main__":
    main()
