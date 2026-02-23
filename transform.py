"""
Transform module for Capitol Connections ETL pipeline.
Cleans raw Senate trade data and normalizes it into
Politicians, Assets, and Trades DataFrames.
"""

import pandas as pd


# Sentinel values that represent missing data in the raw source
MISSING_VALUES: set[str] = {"--", "N/A", "", "N/A "}

# Columns we want from the raw data, mapped to our schema names
COLUMN_MAP: dict[str, str] = {
    "transaction_date": "trade_date",
    "senator": "full_name",
    "ticker": "ticker",
    "asset_description": "asset_name",
    "asset_type": "asset_type",
    "type": "trade_type",
    "amount": "amount_range",
    "comment": "description",
    "ptr_link": "ptr_link",
    "owner": "owner",
}

def clean_raw_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw Senate trade data.

    Steps:
        1. Replace sentinel values with None (proper NaN).
        2. Rename columns to match our schema.
        3. Filter out rows with no usable trade type.
        4. Parse trade_date to datetime.

    Args:
        df: Raw DataFrame from the extraction step.

    Returns:
        Cleaned DataFrame ready for normalization.
    """
    cleaned: pd.DataFrame = df.copy()

    # Step 1: Replace sentinel values with None across all columns
    cleaned = cleaned.replace(MISSING_VALUES, None)

    # Step 2: Rename columns to match our Airtable schema
    cleaned = cleaned.rename(columns=COLUMN_MAP)

    # Step 3: Drop rows where trade_type is None (was "N/A")
    # These are non-actionable records we can't meaningfully load
    cleaned = cleaned.dropna(subset=["trade_type"])

    # Step 4: Parse trade_date strings into datetime objects
    cleaned["trade_date"] = pd.to_datetime(
        cleaned["trade_date"], format="%m/%d/%Y", errors="coerce"
    )

    return cleaned

def extract_politicians(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract unique politicians from the cleaned trade data.

    Returns a deduplicated DataFrame with one row per senator,
    ready for loading into the Politicians table.
    """
    politicians: pd.DataFrame = (
        cleaned_df[["full_name"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # All records in this dataset are senators
    politicians["chamber"] = "Senate"

    # Party and state are not in the raw data — leave as None
    # These will be enriched in a later phase
    politicians["party"] = None
    politicians["state"] = None
    politicians["status"] = "Active"

    return politicians


def extract_assets(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract unique assets from the cleaned trade data.

    Returns a deduplicated DataFrame with one row per asset,
    ready for loading into the Assets table.
    """
    assets: pd.DataFrame = (
        cleaned_df[["ticker", "asset_name", "asset_type"]]
        .drop_duplicates(subset=["ticker"])
        .reset_index(drop=True)
    )

    # Filter out rows with no ticker — we can't link these meaningfully
    assets = assets.dropna(subset=["ticker"])

    return assets


def prepare_trades(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the trades DataFrame for loading.

    Selects only the columns relevant to the Trades table.
    The actual linking to Politicians and Assets happens
    during the Load phase.
    """
    trade_columns: list[str] = [
        "full_name",
        "ticker",
        "trade_date",
        "trade_type",
        "amount_range",
        "description",
    ]

    trades: pd.DataFrame = (
        cleaned_df[trade_columns]
        .reset_index(drop=True)
    )

    return trades

def run_transform(raw_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Run the full transform pipeline.

    Args:
        raw_df: Raw DataFrame from extraction.

    Returns:
        Dictionary with keys 'politicians', 'assets', 'trades',
        each containing a cleaned, normalized DataFrame.
    """
    print("Cleaning raw data...")
    cleaned: pd.DataFrame = clean_raw_data(raw_df)
    print(f"  Records after cleaning: {len(cleaned)}")

    print("Extracting politicians...")
    politicians: pd.DataFrame = extract_politicians(cleaned)
    print(f"  Unique politicians: {len(politicians)}")

    print("Extracting assets...")
    assets: pd.DataFrame = extract_assets(cleaned)
    print(f"  Unique assets: {len(assets)}")

    print("Preparing trades...")
    trades: pd.DataFrame = prepare_trades(cleaned)
    print(f"  Trades to load: {len(trades)}")

    return {
        "politicians": politicians,
        "assets": assets,
        "trades": trades,
    }