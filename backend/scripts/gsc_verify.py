#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-api-python-client>=2.0",
#   "google-auth>=2.0",
# ]
# ///
"""Export last-7-days GSC metrics to three CSVs: by page, by query, and by page+query."""

import csv
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SITE_URL = "sc-domain:tempo.co"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SCRIPTS_DIR = Path(__file__).parent

FIELDS = ["clicks", "impressions", "ctr", "position"]


def get_credentials(key_path: Path) -> service_account.Credentials:
    return service_account.Credentials.from_service_account_file(
        str(key_path), scopes=SCOPES
    )


def fetch(service, start_date: str, end_date: str, dimensions: list[str]) -> list[dict]:
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": 5000,
    }
    try:
        response = (
            service.searchanalytics()
            .query(siteUrl=SITE_URL, body=body)
            .execute()
        )
    except HttpError as e:
        label = "+".join(dimensions)
        print(f"GSC API error ({label}): {e.status_code} — {e.reason}", file=sys.stderr)
        if e.status_code == 403:
            print(
                "Check that the service account has been granted access in GSC "
                "(Settings → Users and permissions).",
                file=sys.stderr,
            )
        sys.exit(1)
    return response.get("rows", [])


def write_csv(rows: list[dict], key_names: list[str], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=key_names + FIELDS)
        writer.writeheader()
        for row in rows:
            keys = row.get("keys", [])
            record = {name: keys[i] if i < len(keys) else "" for i, name in enumerate(key_names)}
            record.update(
                {
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": round(row.get("ctr", 0.0) * 100, 4),
                    "position": round(row.get("position", 0.0), 2),
                }
            )
            writer.writerow(record)


def resolve_credentials() -> Path:
    backend_root = Path(__file__).parent.parent
    env_val = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if env_val:
        key_path = Path(env_val)
        if not key_path.is_absolute():
            key_path = backend_root / key_path
        if key_path.exists():
            return key_path

    candidates = list(backend_root.glob("teco-analytics-*.json"))
    if not candidates:
        print(
            "No service account JSON found. Set GOOGLE_APPLICATION_CREDENTIALS "
            "or place teco-analytics-*.json in backend/.",
            file=sys.stderr,
        )
        sys.exit(1)
    return candidates[0]


def main() -> None:
    key_path = resolve_credentials()
    print(f"Using credentials: {key_path.name}")

    creds = get_credentials(key_path)
    service = build("searchconsole", "v1", credentials=creds)

    print("\nListing accessible sites…")
    site_entries = service.sites().list().execute().get("siteEntry", [])
    if not site_entries:
        print("No sites accessible. Check GSC permissions.", file=sys.stderr)
        sys.exit(1)
    for s in site_entries:
        print(f"  {s['siteUrl']}  (permission: {s.get('permissionLevel', '?')})")
    print()

    end = date.today() - timedelta(days=1)  # GSC lags ~1 day
    start = end - timedelta(days=6)
    start_str, end_str = start.isoformat(), end.isoformat()
    print(f"Date range: {start_str} → {end_str}\n")

    for dimensions, key_names, filename in [
        (["page"],          ["page"],         "gsc_pages_7d.csv"),
        (["query"],         ["query"],        "gsc_queries_7d.csv"),
        (["page", "query"], ["page", "query"], "gsc_page_queries_7d.csv"),
    ]:
        label = "+".join(dimensions)
        print(f"Fetching by {label}…")
        rows = fetch(service, start_str, end_str, dimensions)
        if not rows:
            print(f"  No data returned for {label}.")
            continue
        output_path = SCRIPTS_DIR / filename
        write_csv(rows, key_names, output_path)
        print(f"  {len(rows)} rows → {output_path.name}")


if __name__ == "__main__":
    main()
