"""
Enrichment module for Capitol Connections.
Fetches legislator metadata (party, state) from the @unitedstates
project and updates existing Airtable records.
"""

import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from airtable_client import get_all_records, HEADERS, BASE_URL, RATE_LIMIT_DELAY

load_dotenv()

POLITICIANS_TABLE: str = os.getenv("AIRTABLE_TABLE_POLITICIANS", "")

# The @unitedstates project maintains both current and historical legislators
LEGISLATORS_CURRENT_URL: str = (
    "https://unitedstates.github.io/congress-legislators"
    "/legislators-current.json"
)
LEGISLATORS_HISTORICAL_URL: str = (
    "https://unitedstates.github.io/congress-legislators"
    "/legislators-historical.json"
)

def fetch_legislators() -> list[dict]:
    """
    Fetch both current and historical legislator data.
    We need both because some senators in our trade data
    may no longer be in office.
    """
    all_legislators: list[dict] = []

    for url, label in [
        (LEGISLATORS_CURRENT_URL, "current"),
        (LEGISLATORS_HISTORICAL_URL, "historical"),
    ]:
        print(f"  Fetching {label} legislators...")
        response: requests.Response = requests.get(url, timeout=30)
        response.raise_for_status()
        data: list[dict] = response.json()
        all_legislators.extend(data)
        print(f"    Found {len(data)} {label} legislators")

    return all_legislators

def build_senator_lookup(legislators: list[dict]) -> dict[str, dict]:
    """
    Build a lookup dictionary from legislator data, keyed by
    multiple name variations so we can match against the trade data.

    The trade data uses names like "Ron L Wyden" or "Thomas R Carper".
    The legislator data has structured fields: first, last, middle, nickname.

    We generate several variations for each senator and map them all
    to the same metadata dict.

    Returns:
        Dict mapping name variations to {"party": "D", "state": "OR"}.
    """
    lookup: dict[str, dict] = {}

    for legislator in legislators:
        name: dict = legislator.get("name", {})
        terms: list[dict] = legislator.get("terms", [])

        # We only care about senators
        senate_terms: list[dict] = [
            t for t in terms if t.get("type") == "sen"
        ]
        if not senate_terms:
            continue

        # Use the most recent senate term for party and state
        latest_term: dict = senate_terms[-1]
        party_full: str = latest_term.get("party", "")
        state: str = latest_term.get("state", "")

        # Map full party name to our single-letter schema
        party_map: dict[str, str] = {
            "Republican": "R",
            "Democrat": "D",
            "Independent": "I",
        }
        party: str = party_map.get(party_full, "I")

        metadata: dict[str, str] = {"party": party, "state": state}

        # Extract name components
        first: str = name.get("first", "")
        last: str = name.get("last", "")
        middle: str = name.get("middle", "")
        nickname: str = name.get("nickname", "")

        # Generate multiple name variations to maximize match chances
        # The trade data is inconsistent — sometimes middle initial,
        # sometimes full middle name, sometimes nickname
        variations: set[str] = set()

        # "Ron Wyden"
        variations.add(f"{first} {last}")

        # "Ron L Wyden" (middle initial)
        if middle:
            initial: str = middle[0]
            variations.add(f"{first} {initial} {last}")
            # "Ron Lewis Wyden" (full middle)
            variations.add(f"{first} {middle} {last}")

        # "Ronald Wyden" -> try nickname too: "Ron Wyden"
        if nickname:
            variations.add(f"{nickname} {last}")
            if middle:
                variations.add(f"{nickname} {middle[0]} {last}")
                variations.add(f"{nickname} {middle} {last}")

        # Normalize all variations: strip whitespace, collapse spaces
        # Add both raw and normalized versions of each variation
        for v in variations:
            clean: str = " ".join(v.split()).strip()
            if clean:
                lookup[clean] = metadata
                lookup[normalize_name(clean)] = metadata
    return lookup

def normalize_name(name: str) -> str:
    """
    Normalize a name for matching by removing suffixes,
    trailing punctuation, and extra whitespace.
    """
    cleaned: str = name.strip()

    # Remove common suffixes
    suffixes: list[str] = [
        ", Jr.", ", Jr", ",Jr.", ",Jr",
        ", Iii", ", III", ",Iii", ",III",
        ", Ii", ", II",
        ", Sr.", ", Sr",
        "Jr.", "Jr", "III", "II",
    ]
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break

    # Remove trailing commas and periods
    cleaned = cleaned.rstrip(",. ")

    # Collapse multiple spaces into one
    cleaned = " ".join(cleaned.split())

    # Remove leading initials with periods like "A. " at the start
    # "A. Mitchell Mcconnell" -> "Mitchell Mcconnell"
    if len(cleaned) > 2 and cleaned[1] == "." and cleaned[2] == " ":
        cleaned = cleaned[3:]

    return cleaned


# Manual overrides for names that can't be resolved algorithmically.
# Maps the normalized trade-data name to the legislator's common name.
# This is a legitimate production pattern — document your edge cases.
MANUAL_NAME_MAP: dict[str, str] = {
    "Ladda Tammy Duckworth": "Tammy Duckworth",
    "Jacklyn S Rosen": "Jacky Rosen",
    "Daniel S Sullivan": "Dan Sullivan",
    "William Cassidy": "Bill Cassidy",
    "Timothy M Kaine": "Tim Kaine",
    "Mitchell Mcconnell": "Mitch McConnell",
    "Thomas R Tillis": "Thom Tillis",
    "Rafael E Cruz": "Ted Cruz",
    "David A Perdue": "David Perdue",
    "Ron L Wyden": "Ron Wyden",
    "Joseph Manchin": "Joe Manchin",
    "Thomas Udall": "Tom Udall",
}


def enrich_politicians() -> None:
    """
    Main enrichment function.
    Fetches existing politicians from Airtable, matches them against
    the @unitedstates legislator data, and updates records with
    party and state.
    """
    print("=== ENRICHMENT: Politicians ===\n")

    # Step 1: Fetch legislator reference data
    legislators: list[dict] = fetch_legislators()
    lookup: dict[str, dict] = build_senator_lookup(legislators)
    print(f"\n  Built lookup with {len(lookup)} name variations")

    # Step 2: Fetch our existing politicians from Airtable
    print("  Fetching existing politicians from Airtable...")
    existing: list[dict] = get_all_records(POLITICIANS_TABLE)
    print(f"  Found {len(existing)} politicians in Airtable\n")

    # Step 3: Match and update
    matched: int = 0
    unmatched: list[str] = []
    url: str = f"{BASE_URL}/{POLITICIANS_TABLE}"

    for record in existing:
        record_id: str = record["id"]
        full_name: str = record["fields"].get("Full Name", "")

        # Try exact match first, then normalized, then manual override
        normalized: str = normalize_name(full_name)
        metadata: dict[str, str] | None = (
            lookup.get(full_name)
            or lookup.get(normalized)
            or lookup.get(MANUAL_NAME_MAP.get(normalized, ""))
        )

        if not metadata:
            unmatched.append(full_name)
            continue

        # Build the update payload — only update fields that are
        # currently empty to avoid overwriting manual corrections
        updates: dict[str, str] = {}
        if not record["fields"].get("Party"):
            updates["Party"] = metadata["party"]
        if not record["fields"].get("State"):
            updates["State"] = metadata["state"]

        if not updates:
            matched += 1
            continue

        # PATCH request to update a single record
        patch_url: str = f"{url}/{record_id}"
        payload: dict = {"fields": updates}

        try:
            response: requests.Response = requests.patch(
                patch_url, headers=HEADERS, json=payload, timeout=30
            )
            response.raise_for_status()
            matched += 1
            print(f"    Updated: {full_name} -> {updates}")
        except requests.exceptions.HTTPError as e:
            print(f"    ERROR updating {full_name}: {e}")

        time.sleep(RATE_LIMIT_DELAY)

    # Report results
    print(f"\n  Matched and updated: {matched}")
    if unmatched:
        print(f"  Unmatched ({len(unmatched)}):")
        for name in unmatched:
            print(f"    - {name}")


if __name__ == "__main__":
    enrich_politicians()