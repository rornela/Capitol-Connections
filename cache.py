"""
Fetch all three Airtable tables and flatten into a single
denormalized Parquet file for the Streamlit dashboard.
"""

from pathlib import Path
import pandas as pd
from airtable_client import get_all_records
import os
from dotenv import load_dotenv

load_dotenv()

POLITICIANS_TABLE: str = os.getenv("AIRTABLE_TABLE_POLITICIANS", "")
ASSETS_TABLE: str = os.getenv("AIRTABLE_TABLE_ASSETS", "")
TRADES_TABLE: str = os.getenv("AIRTABLE_TABLE_TRADES", "")

CACHE_PATH: Path = Path(__file__).parent / "data" / "trades_enriched.parquet"

def fetch_table(table_id: str, label: str) -> list[dict]:
    """Fetch all records from one Airtable table with progress feedback."""
    print(f"  Fetching {label}...")
    records: list[dict] = get_all_records(table_id)
    print(f"  Got {len(records)} {label} records.")
    return records

def build_lookup(
    records: list[dict],
    field_map: dict[str, str],
) -> dict[str, dict[str, str | None]]:
    """
    Build a lookup dict: Airtable record ID → selected fields.

    Args:
        records: Raw Airtable records from get_all_records().
        field_map: Maps Airtable field names to our output keys.
            Example: {"Full Name": "full_name", "Party": "party"}

    Returns:
        Dict keyed by record ID.
            Example: {"recABC": {"full_name": "Ron Wyden", "party": "D"}}
    """
    lookup: dict[str, dict[str, str | None]] = {}

    for record in records:
        record_id: str = record["id"]
        fields: dict = record.get("fields", {})

        lookup[record_id] = {
            output_key: fields.get(airtable_field)
            for airtable_field, output_key in field_map.items()
        }

    return lookup


def build_flat_dataframe(
    trade_records: list[dict],
    politician_lookup: dict[str, dict[str, str | None]],
    asset_lookup: dict[str, dict[str, str | None]],
) -> pd.DataFrame:
    """
    Denormalize trades by resolving linked Politician and Asset records
    into a single flat DataFrame.

    Args:
        trade_records: Raw Airtable trade records.
        politician_lookup: Record ID → politician metadata.
        asset_lookup: Record ID → asset metadata.

    Returns:
        Flat DataFrame with one row per trade, all fields resolved.
    """
    rows: list[dict] = []

    for record in trade_records:
        fields: dict = record.get("fields", {})

        # --- Resolve linked Politician ---
        politician_ids: list[str] = fields.get("Politician", [])
        if politician_ids:
            politician: dict[str, str | None] = politician_lookup.get(
                politician_ids[0], {}
            )
        else:
            politician = {}

        # --- Resolve linked Asset ---
        asset_ids: list[str] = fields.get("Asset", [])
        if asset_ids:
            asset: dict[str, str | None] = asset_lookup.get(
                asset_ids[0], {}
            )
        else:
            asset = {}

        row: dict = {
            "trade_date": fields.get("Trade Date"),
            "disclosure_date": fields.get("Disclosure Date"),
            "trade_type": fields.get("Trade Type"),
            "amount_range": fields.get("Amount Range"),
            "description": fields.get("Description"),
            # Flattened from Politician lookup
            "full_name": politician.get("full_name"),
            "party": politician.get("party"),
            "state": politician.get("state"),
            # Flattened from Asset lookup
            "ticker": asset.get("ticker"),
            "asset_name": asset.get("asset_name"),
            "asset_type": asset.get("asset_type"),
        }

        rows.append(row)

    df: pd.DataFrame = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df["disclosure_date"] = pd.to_datetime(df["disclosure_date"], errors="coerce")

    return df

def refresh_cache() -> pd.DataFrame:
    """
    Full cache refresh: fetch all tables, denormalize, save to Parquet.

    Returns:
        The flattened DataFrame (also saved to disk).
    """
    # --- Fetch all three tables ---
    politician_records: list[dict] = fetch_table(POLITICIANS_TABLE, "Politicians")
    asset_records: list[dict] = fetch_table(ASSETS_TABLE, "Assets")
    trade_records: list[dict] = fetch_table(TRADES_TABLE, "Trades")

    # --- Build lookups for parent tables ---
    politician_lookup: dict[str, dict[str, str | None]] = build_lookup(
        politician_records,
        {"Full Name": "full_name", "Party": "party", "State": "state"},
    )
    asset_lookup: dict[str, dict[str, str | None]] = build_lookup(
        asset_records,
        {"Ticker": "ticker", "Asset Name": "asset_name", "Asset Type": "asset_type"},
    )

    # --- Denormalize into flat DataFrame ---
    print("  Building flat DataFrame...")
    df: pd.DataFrame = build_flat_dataframe(
        trade_records, politician_lookup, asset_lookup,
    )
    print(f"  Result: {len(df)} rows, {len(df.columns)} columns.")

    # --- Save to Parquet ---
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_PATH, index=False)
    print(f"  Saved cache to {CACHE_PATH}")

    return df

if __name__ == "__main__":
    print("Refreshing cache...")
    refresh_cache()
    print("Done.")