"""
Connection test script for Airtable API.
Validates credentials and confirms table schema access.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_PAT: str = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")

def test_airtable_connection() -> None:
    """Fetch base schema to validate API credentials and access."""

    if not AIRTABLE_PAT or not AIRTABLE_BASE_ID:
        print("ERROR: Missing AIRTABLE_PAT or AIRTABLE_BASE_ID in .env file.")
        return

    url: str = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"

    headers: dict[str, str] = {
        "Authorization": f"Bearer {AIRTABLE_PAT}",
        "Content-Type": "application/json",
    }

    try:
        response: requests.Response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        tables: list[dict] = response.json().get("tables", [])

        print(f"Connection successful! Found {len(tables)} tables:\n")
        for table in tables:
            print(f"  Table: {table['name']} (ID: {table['id']})")
            fields: list[dict] = table.get("fields", [])
            for field in fields:
                print(f"    - {field['name']} ({field['type']})")
            print()

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 401:
            print("Your API token is invalid or expired. Regenerate it at airtable.com/create/tokens")
        elif response.status_code == 403:
            print("Your token doesn't have permission for this base. Check your token's access settings.")
    except requests.exceptions.ConnectionError:
        print("Connection failed. Check your internet connection.")
    except requests.exceptions.Timeout:
        print("Request timed out after 10 seconds.")

if __name__ == "__main__":
    test_airtable_connection()