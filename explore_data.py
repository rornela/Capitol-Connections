"""
Data exploration script.
Fetches raw Senate stock trade data and prints diagnostic info.
This is a throwaway script — its purpose is to inform our ETL design.
"""

import requests
import pandas as pd

SENATE_URL: str = (
    "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data"
    "/master/aggregate/all_transactions.json"
)


def explore_senate_data() -> None:
    """Fetch and inspect raw Senate trading data."""

    print("Fetching Senate trade data...")

    try:
        response: requests.Response = requests.get(SENATE_URL, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data: {e}")
        return

    raw_data: list[dict] = response.json()
    print(f"Total raw records: {len(raw_data)}\n")

    # Data is already flat — one record per transaction
    df: pd.DataFrame = pd.DataFrame(raw_data)

    # --- Diagnostic 1: What columns exist? ---
    print("=== COLUMNS ===")
    print(df.columns.tolist())
    print()

    # --- Diagnostic 2: First few rows ---
    print("=== FIRST 3 ROWS ===")
    print(df.head(3).to_string())
    print()

    # --- Diagnostic 3: Data types and null counts ---
    print("=== DATA TYPES & NULLS ===")
    print(df.info())
    print()

    # --- Diagnostic 4: Unique values in key columns ---
    print("=== UNIQUE VALUE COUNTS ===")
    for col in df.columns:
        unique_count: int = df[col].nunique()
        print(f"  {col}: {unique_count} unique values")
    print()

    # --- Diagnostic 5: Sample values for important columns ---
    print("=== SAMPLE VALUES ===")
    for col in ["type", "amount", "asset_type", "owner", "ticker"]:
        if col in df.columns:
            print(f"  {col}: {df[col].unique()[:15]}")
    print()


if __name__ == "__main__":
    explore_senate_data()