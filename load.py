"""
Load module for Capitol Connections ETL pipeline.
Pushes transformed DataFrames into Airtable with proper
record linking between tables.
"""

import os
import pandas as pd
from dotenv import load_dotenv
from airtable_client import create_records, get_all_records

load_dotenv()

# Table IDs from your .env
POLITICIANS_TABLE: str = os.getenv("AIRTABLE_TABLE_POLITICIANS", "")
ASSETS_TABLE: str = os.getenv("AIRTABLE_TABLE_ASSETS", "")
TRADES_TABLE: str = os.getenv("AIRTABLE_TABLE_TRADES", "")

def load_politicians(politicians_df: pd.DataFrame) -> dict[str, str]:
    """
    Load politicians into Airtable and return a name-to-record-ID mapping.

    Args:
        politicians_df: DataFrame with columns: full_name, chamber,
            party, state, status.

    Returns:
        Dict mapping full_name to Airtable record ID.
        Example: {"Ron L Wyden": "recABC123"}
    """
    print("\nLoading Politicians...")

    records: list[dict] = []
    for _, row in politicians_df.iterrows():
        fields: dict = {"Full Name": row["full_name"]}

        # Only include non-null fields — Airtable rejects null
        # values for single select fields
        if pd.notna(row.get("chamber")):
            fields["Chamber"] = row["chamber"]
        if pd.notna(row.get("party")):
            fields["Party"] = row["party"]
        if pd.notna(row.get("state")):
            fields["State"] = row["state"]
        if pd.notna(row.get("status")):
            fields["Status"] = row["status"]

        records.append({"fields": fields})

    created: list[dict] = create_records(POLITICIANS_TABLE, records)

    # Build the lookup mapping: full_name -> record_id
    name_to_id: dict[str, str] = {}
    for record in created:
        name: str = record["fields"]["Full Name"]
        record_id: str = record["id"]
        name_to_id[name] = record_id

    print(f"  Loaded {len(name_to_id)} politicians")
    return name_to_id

def load_assets(assets_df: pd.DataFrame) -> dict[str, str]:
    """
    Load assets into Airtable and return a ticker-to-record-ID mapping.

    Args:
        assets_df: DataFrame with columns: ticker, asset_name, asset_type.

    Returns:
        Dict mapping ticker to Airtable record ID.
        Example: {"AAPL": "recXYZ789"}
    """
    print("\nLoading Assets...")

    records: list[dict] = []
    for _, row in assets_df.iterrows():
        fields: dict = {"Ticker": row["ticker"]}

        if pd.notna(row.get("asset_name")):
            fields["Asset Name"] = row["asset_name"]
        if pd.notna(row.get("asset_type")):
            fields["Asset Type"] = row["asset_type"]

        records.append({"fields": fields})

    created: list[dict] = create_records(ASSETS_TABLE, records)

    ticker_to_id: dict[str, str] = {}
    for record in created:
        ticker: str = record["fields"]["Ticker"]
        record_id: str = record["id"]
        ticker_to_id[ticker] = record_id

    print(f"  Loaded {len(ticker_to_id)} assets")
    return ticker_to_id

def load_trades(
    trades_df: pd.DataFrame,
    politician_map: dict[str, str],
    asset_map: dict[str, str],
) -> int:
    """
    Load trades into Airtable with links to Politicians and Assets.

    For each trade, looks up the politician's record ID by full_name
    and the asset's record ID by ticker, then creates the trade with
    those linked record references.

    Args:
        trades_df: DataFrame with columns: full_name, ticker,
            trade_date, trade_type, amount_range, description.
        politician_map: Dict mapping full_name -> Airtable record ID.
        asset_map: Dict mapping ticker -> Airtable record ID.

    Returns:
        Count of successfully loaded trades.
    """
    print("\nLoading Trades...")

    records: list[dict] = []
    skipped: int = 0

    for _, row in trades_df.iterrows():
        # Look up the linked record IDs
        politician_id: str | None = politician_map.get(row["full_name"])
        asset_id: str | None = asset_map.get(row["ticker"]) if pd.notna(row.get("ticker")) else None

        # Skip trades where we can't establish the politician link
        # (the trade is meaningless without knowing who made it)
        if not politician_id:
            skipped += 1
            continue

        fields: dict = {
            "Politician": [politician_id],
            "Trade Type": row["trade_type"],
        }

        # Link to asset if we have a matching record
        if asset_id:
            fields["Asset"] = [asset_id]

        # Format date as ISO string — Airtable expects "YYYY-MM-DD"
        if pd.notna(row.get("trade_date")):
            fields["Trade Date"] = row["trade_date"].strftime("%Y-%m-%d")

        if pd.notna(row.get("amount_range")):
            fields["Amount Range"] = row["amount_range"]

        if pd.notna(row.get("description")):
            fields["Description"] = str(row["description"])

        records.append({"fields": fields})

    print(f"  Prepared {len(records)} trades ({skipped} skipped - no politician match)")

    created: list[dict] = create_records(TRADES_TABLE, records)

    print(f"  Successfully loaded {len(created)} trades")
    return len(created)

def run_load(transformed_data: dict[str, pd.DataFrame]) -> None:
    """
    Execute the full load pipeline in the correct order.

    Order matters:
        1. Politicians first (parents)
        2. Assets second (parents)
        3. Trades last (children that reference parents)

    Args:
        transformed_data: Dict with keys 'politicians', 'assets', 'trades',
            each containing a DataFrame from the transform step.
    """
    # Validate configuration
    if not all([POLITICIANS_TABLE, ASSETS_TABLE, TRADES_TABLE]):
        print("ERROR: Missing table IDs in .env file.")
        print("Ensure AIRTABLE_TABLE_POLITICIANS, AIRTABLE_TABLE_ASSETS,")
        print("and AIRTABLE_TABLE_TRADES are set.")
        return

    # Step 1: Load parent tables and capture ID mappings
    politician_map: dict[str, str] = load_politicians(
        transformed_data["politicians"]
    )

    asset_map: dict[str, str] = load_assets(
        transformed_data["assets"]
    )

    # Step 2: Load child table with links to parents
    trades_loaded: int = load_trades(
        transformed_data["trades"],
        politician_map,
        asset_map,
    )

    print("\n=== LOAD COMPLETE ===")
    print(f"  Politicians: {len(politician_map)}")
    print(f"  Assets: {len(asset_map)}")
    print(f"  Trades: {trades_loaded}")