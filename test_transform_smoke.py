"""Quick test to verify the transform pipeline."""

import requests
import pandas as pd
from transform import run_transform

SENATE_URL: str = (
    "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data"
    "/master/aggregate/all_transactions.json"
)

response: requests.Response = requests.get(SENATE_URL, timeout=30)
response.raise_for_status()

raw_df: pd.DataFrame = pd.DataFrame(response.json())
result: dict[str, pd.DataFrame] = run_transform(raw_df)

print("\n=== POLITICIANS SAMPLE ===")
print(result["politicians"].head().to_string())

print("\n=== ASSETS SAMPLE ===")
print(result["assets"].head().to_string())

print("\n=== TRADES SAMPLE ===")
print(result["trades"].head().to_string())