"""
Capitol Connections ETL Pipeline.
Extracts Senate stock trade data, transforms it, and loads it into Airtable.
"""

import requests
import pandas as pd
from transform import run_transform
from load import run_load

SENATE_URL: str = (
    "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data"
    "/master/aggregate/all_transactions.json"
)


def extract() -> pd.DataFrame:
    """Fetch raw Senate trade data and return as a DataFrame."""
    print("=== EXTRACT ===")
    print("Fetching Senate trade data...")

    response: requests.Response = requests.get(SENATE_URL, timeout=30)
    response.raise_for_status()

    raw_data: list[dict] = response.json()
    print(f"  Extracted {len(raw_data)} raw records")

    return pd.DataFrame(raw_data)


def main() -> None:
    """Run the full ETL pipeline."""
    print("=" * 50)
    print("CAPITOL CONNECTIONS ETL PIPELINE")
    print("=" * 50)

    # Extract
    raw_df: pd.DataFrame = extract()

    # Transform
    print("\n=== TRANSFORM ===")
    transformed: dict[str, pd.DataFrame] = run_transform(raw_df)

    # Load
    print("\n=== LOAD ===")
    run_load(transformed)

    print("\n" + "=" * 50)
    print("PIPELINE COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()