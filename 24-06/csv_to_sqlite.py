#!/usr/bin/env python3
"""csv_to_sqlite.py

Read a CSV file and write it into a SQLite database table.

Usage:
  python csv_to_sqlite.py --csv sample.csv --db creditrisk.db --table loan_data

If `--csv` is not provided it will try `sample.csv` then
`demo_data/clean_portfolio.csv`.
"""
from pathlib import Path
import argparse
import sys
import pandas as pd
from sqlalchemy import create_engine


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write CSV to SQLite table")
    parser.add_argument("--csv", help="Path to input CSV file", default=None)
    parser.add_argument("--db", help="SQLite database path", default="creditrisk.db")
    parser.add_argument("--table", help="Table name to write", default="loan_data")
    args = parser.parse_args(argv)

    csv_path = args.csv
    if csv_path is None:
        # prefer a top-level sample.csv, then demo data
        cand1 = Path("sample.csv")
        cand2 = Path("demo_data") / "clean_portfolio.csv"
        if cand1.exists():
            csv_path = str(cand1)
        elif cand2.exists():
            csv_path = str(cand2)
        else:
            print("No CSV provided and neither sample.csv nor demo_data/clean_portfolio.csv were found.")
            return 2

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"CSV file not found: {csv_file}")
        return 2

    db_path = Path(args.db)
    table_name = args.table

    print(f"Reading CSV: {csv_file}")
    try:
        df = pd.read_csv(csv_file, keep_default_na=True)
    except Exception as exc:
        print(f"Failed to read CSV: {exc}")
        return 3

    engine_url = f"sqlite:///{db_path.as_posix()}"
    print(f"Writing to SQLite DB: {db_path} (table: {table_name})")
    try:
        engine = create_engine(engine_url, future=True)
        df.to_sql(table_name, con=engine, if_exists="replace", index=False)
        engine.dispose()
    except Exception as exc:
        print(f"Failed to write to SQLite DB: {exc}")
        return 4

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
