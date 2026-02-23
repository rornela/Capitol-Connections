"""
Airtable API client for Capitol Connections.
Handles authentication, batch operations, and rate limiting.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_PAT: str = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")

BASE_URL: str = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"

HEADERS: dict[str, str] = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json",
}

# Airtable limits
MAX_BATCH_SIZE: int = 10
RATE_LIMIT_DELAY: float = 0.22  # ~4.5 requests/sec, safely under the 5/sec limit

def create_records(
    table_id: str,
    records: list[dict],
) -> list[dict]:
    """
    Create records in an Airtable table with automatic batching
    and rate limiting.

    Args:
        table_id: The Airtable table ID (starts with 'tbl').
        records: List of record dicts, each with a 'fields' key.
            Example: [{"fields": {"Full Name": "Ron L Wyden"}}]

    Returns:
        List of created record dicts from Airtable's response,
        each containing 'id' and 'fields'.

    Raises:
        requests.exceptions.HTTPError: If any API request fails.
    """
    url: str = f"{BASE_URL}/{table_id}"
    all_created: list[dict] = []

    # Split records into batches of MAX_BATCH_SIZE
    for i in range(0, len(records), MAX_BATCH_SIZE):
        batch: list[dict] = records[i : i + MAX_BATCH_SIZE]

        payload: dict = {"records": batch}

        try:
            response: requests.Response = requests.post(
                url, headers=HEADERS, json=payload, timeout=30
            )
            response.raise_for_status()

            created: list[dict] = response.json().get("records", [])
            all_created.extend(created)

            batch_num: int = (i // MAX_BATCH_SIZE) + 1
            total_batches: int = (len(records) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
            print(f"    Batch {batch_num}/{total_batches}: "
                  f"created {len(created)} records")

        except requests.exceptions.HTTPError as e:
            print(f"    ERROR on batch starting at index {i}: {e}")
            print(f"    Response: {response.text}")
            raise

        # Rate limiting — pause between requests
        time.sleep(RATE_LIMIT_DELAY)

    return all_created

def get_all_records(table_id: str) -> list[dict]:
    """
    Fetch all records from an Airtable table, handling pagination.

    Airtable returns max 100 records per page. If there are more,
    it includes an 'offset' token to fetch the next page.

    Args:
        table_id: The Airtable table ID.

    Returns:
        List of all record dicts in the table.
    """
    url: str = f"{BASE_URL}/{table_id}"
    all_records: list[dict] = []
    offset: str | None = None

    while True:
        params: dict[str, str] = {}
        if offset:
            params["offset"] = offset

        try:
            response: requests.Response = requests.get(
                url, headers=HEADERS, params=params, timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"    ERROR fetching records: {e}")
            raise

        data: dict = response.json()
        records: list[dict] = data.get("records", [])
        all_records.extend(records)

        # Check for pagination
        offset = data.get("offset")
        if not offset:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return all_records