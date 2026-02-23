"""Unit tests for the transform module."""

import pandas as pd
import pytest

from transform import clean_raw_data, extract_politicians, extract_assets


def make_raw_row(**overrides) -> dict:
    """
    Build a single raw data row with sensible defaults.
    Override any field by passing keyword arguments.
    """
    base: dict = {
        "transaction_date": "01/15/2021",
        "senator": "Jane Smith",
        "ticker": "AAPL",
        "asset_description": "Apple Inc",
        "asset_type": "Stock",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "comment": "Some comment",
        "ptr_link": "https://example.com",
        "owner": "Self",
    }
    base.update(overrides)
    return base


class TestCleanRawData:
    """Tests for clean_raw_data()."""

    def test_sentinels_replaced_with_none(self):
        """Sentinel values ('--', 'N/A', '') should become None."""
        raw: pd.DataFrame = pd.DataFrame([
            make_raw_row(ticker="--"),
            make_raw_row(ticker="N/A"),
            make_raw_row(ticker=""),
            make_raw_row(ticker="AAPL"),
        ])

        result: pd.DataFrame = clean_raw_data(raw)

        tickers = result["ticker"].tolist()
        assert tickers.count(None) == 3
        assert "AAPL" in tickers

    def test_columns_renamed(self):
        """Raw column names should be mapped to schema names."""
        raw: pd.DataFrame = pd.DataFrame([make_raw_row()])

        result: pd.DataFrame = clean_raw_data(raw)

        assert "full_name" in result.columns
        assert "trade_date" in result.columns
        assert "trade_type" in result.columns
        # Original names should be gone
        assert "senator" not in result.columns
        assert "transaction_date" not in result.columns
    
    def test_null_trade_type_rows_dropped(self):
        """Rows where trade_type is a sentinel value should be removed."""
        raw: pd.DataFrame = pd.DataFrame([
            make_raw_row(type="Purchase"),
            make_raw_row(type="N/A"),
            make_raw_row(type="--"),
        ])

        result: pd.DataFrame = clean_raw_data(raw)

        assert len(result) == 1
        assert result["trade_type"].iloc[0] == "Purchase"

    def test_dates_parsed(self):
        """trade_date should be parsed from string to datetime."""
        raw: pd.DataFrame = pd.DataFrame([
            make_raw_row(transaction_date="03/15/2021"),
        ])

        result: pd.DataFrame = clean_raw_data(raw)

        assert pd.api.types.is_datetime64_any_dtype(result["trade_date"])
        assert result["trade_date"].iloc[0] == pd.Timestamp("2021-03-15")


class TestExtractPoliticians:
    """Tests for extract_politicians()."""

    def test_deduplicates_by_name(self):
        """Senators appearing in multiple trades should produce one row."""
        raw: pd.DataFrame = pd.DataFrame([
            make_raw_row(senator="Jane Smith"),
            make_raw_row(senator="Jane Smith"),
            make_raw_row(senator="Bob Jones"),
        ])
        cleaned: pd.DataFrame = clean_raw_data(raw)

        result: pd.DataFrame = extract_politicians(cleaned)

        assert len(result) == 2
        names: list[str] = result["full_name"].tolist()
        assert "Jane Smith" in names
        assert "Bob Jones" in names

    def test_default_columns_added(self):
        """Each politician should get chamber, party, state, and status defaults."""
        raw: pd.DataFrame = pd.DataFrame([make_raw_row()])
        cleaned: pd.DataFrame = clean_raw_data(raw)

        result: pd.DataFrame = extract_politicians(cleaned)

        row = result.iloc[0]
        assert row["chamber"] == "Senate"
        assert row["party"] is None
        assert row["state"] is None
        assert row["status"] == "Active"


class TestExtractAssets:
    """Tests for extract_assets()."""

    def test_deduplicates_by_ticker(self):
        """Same ticker appearing multiple times should produce one row."""
        raw: pd.DataFrame = pd.DataFrame([
            make_raw_row(ticker="AAPL", asset_description="Apple Inc"),
            make_raw_row(ticker="AAPL", asset_description="Apple Inc"),
            make_raw_row(ticker="MSFT", asset_description="Microsoft Corp"),
        ])
        cleaned: pd.DataFrame = clean_raw_data(raw)

        result: pd.DataFrame = extract_assets(cleaned)

        assert len(result) == 2
        tickers: list[str] = result["ticker"].tolist()
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_null_tickers_dropped(self):
        """Assets with no ticker should be excluded."""
        raw: pd.DataFrame = pd.DataFrame([
            make_raw_row(ticker="AAPL"),
            make_raw_row(ticker="--"),
        ])
        cleaned: pd.DataFrame = clean_raw_data(raw)

        result: pd.DataFrame = extract_assets(cleaned)

        assert len(result) == 1
        assert result["ticker"].iloc[0] == "AAPL"