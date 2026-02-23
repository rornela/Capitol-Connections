"""
Capitol Connections — Streamlit Dashboard.
Interactive visualization of U.S. Senate stock trading data.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import altair as alt
from cache import refresh_cache, CACHE_PATH as CACHE_FILE



@st.cache_data
def load_data() -> pd.DataFrame:
    """Load cached data, rebuilding from Airtable if cache is missing."""
    if not CACHE_FILE.exists():
        refresh_cache()
    return pd.read_parquet(CACHE_FILE)


# --- Page config (must be the first Streamlit command) ---
st.set_page_config(
    page_title="Capitol Connections",
    page_icon="🏛️",
    layout="wide",
)

st.title("Capitol Connections")
st.caption(
    "Tracking U.S. Senate stock trades disclosed under the STOCK Act (2012–2020)  \n"
    "Data source: Senate Stock Watcher  •  Built with Python, Pandas & Airtable"
)

df: pd.DataFrame = load_data()

# --- Sidebar Filters ---
st.sidebar.header("Filters")

# Party filter
parties: list[str] = sorted(df["party"].dropna().unique().tolist())
selected_parties: list[str] = st.sidebar.multiselect(
    "Party", parties, default=parties,
)

# Trade type filter
trade_types: list[str] = sorted(df["trade_type"].dropna().unique().tolist())
selected_trade_types: list[str] = st.sidebar.multiselect(
    "Trade Type", trade_types, default=trade_types,
)

# Apply filters
filtered: pd.DataFrame = df[
    (df["party"].isin(selected_parties))
    & (df["trade_type"].isin(selected_trade_types))
]

st.sidebar.caption(f"Showing {len(filtered):,} of {len(df):,} trades")

# --- KPI Bar ---
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Trades", f"{len(filtered):,}")
col2.metric("Senators", filtered["full_name"].nunique())
col3.metric(
    "Unique Assets",
    f"{filtered['ticker'].dropna().nunique():,}",
)
if filtered.empty:
    col4.metric("Date Range", "N/A")
else:
    col4.metric(
        "Date Range",
        f"{filtered['trade_date'].min():%b %Y} — {filtered['trade_date'].max():%b %Y}",
    )

st.divider()
# --- Top Traders ---
st.subheader("Most Active Senators")

top_n: int = st.slider("Number of senators", min_value=5, max_value=25, value=10)

trade_counts: pd.DataFrame = (
    filtered.groupby(["full_name", "party"], as_index=False)
    .size()
    .rename(columns={"size": "Trades", "full_name": "Full Name", "party": "Party"})
    .sort_values("Trades", ascending=False)
    .head(top_n)
)

PARTY_COLORS: dict[str, str] = {
    "R": "#E81B23",
    "D": "#0015BC",
    "I": "#8B00FF",
}

chart: alt.Chart = (
    alt.Chart(trade_counts)
    .mark_bar()
    .encode(
        x=alt.X("Trades:Q"),
        y=alt.Y("Full Name:N", sort="-x"),
        color=alt.Color(
            "Party:N",
            scale=alt.Scale(
                domain=list(PARTY_COLORS.keys()),
                range=list(PARTY_COLORS.values()),
            ),
        ),
        tooltip=["Full Name", "Party", "Trades"],
    )
    .properties(height=400)
)

st.altair_chart(chart, use_container_width=True)

st.divider()

# --- Trade Timeline ---
st.subheader("Trading Activity Over Time")

monthly: pd.DataFrame = (
    filtered.set_index("trade_date")
    .resample("ME")
    .size()
    .reset_index(name="Trades")
    .rename(columns={"trade_date": "Month"})
)

st.line_chart(monthly, x="Month", y="Trades")

st.divider()
# --- Senator Deep Dive ---
st.subheader("Senator Deep Dive")

senators: list[str] = sorted(df["full_name"].unique().tolist())
selected: str = st.selectbox("Select a senator", senators)

senator_df: pd.DataFrame = df[df["full_name"] == selected].sort_values(
    "trade_date", ascending=False,
)

# Senator stats row
s1, s2, s3 = st.columns(3)
s1.metric("Total Trades", f"{len(senator_df):,}")
PARTY_LABELS: dict[str, str] = {
    "R": "Republican",
    "D": "Democrat",
    "I": "Independent",
}
raw_party: str | None = senator_df["party"].iloc[0]
s2.metric("Party", PARTY_LABELS.get(raw_party, "Unknown"))
s3.metric("State", senator_df["state"].iloc[0] or "Unknown")

# Trade table
st.dataframe(
    senator_df[["trade_date", "ticker", "asset_name", "trade_type", "amount_range"]]
    .rename(columns={
        "trade_date": "Trade Date",
        "ticker": "Ticker",
        "asset_name": "Asset Name",
        "trade_type": "Trade Type",
        "amount_range": "Amount Range",
    }),
    use_container_width=True,
    hide_index=True,
)