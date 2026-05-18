"""Quick inspector for what landed in the local SQLite DB."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main(path: str = "data/market.sqlite") -> int:
    if not Path(path).exists():
        print(f"db not found at {path}")
        return 1
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    print("=== mutual_funds row count ===")
    print(conn.execute("SELECT COUNT(*) AS n FROM mutual_funds").fetchone()["n"])

    print("\n=== top AMCs by scheme count ===")
    for r in conn.execute(
        "SELECT amc_name, COUNT(*) AS n FROM mutual_funds "
        "WHERE amc_name IS NOT NULL GROUP BY amc_name ORDER BY n DESC LIMIT 5"
    ):
        print(f"  {(r['amc_name'] or '')[:55]:<55} {r['n']}")

    print("\n=== sample rows ===")
    for r in conn.execute(
        "SELECT scheme_code, scheme_name, nav, nav_date FROM mutual_funds LIMIT 5"
    ):
        print(f"  {r['scheme_code']:<8} | NAV {r['nav']:<10} | {r['nav_date']} | {r['scheme_name'][:60]}")

    print("\n=== categories ===")
    for r in conn.execute(
        "SELECT category, COUNT(*) AS n FROM mutual_funds "
        "WHERE category IS NOT NULL GROUP BY category ORDER BY n DESC LIMIT 5"
    ):
        print(f"  {r['category'][:55]:<55} {r['n']}")

    print("\n=== scraper_run_log ===")
    for r in conn.execute(
        "SELECT source, status, records_inserted, duration_ms FROM scraper_run_log "
        "ORDER BY started_at DESC LIMIT 5"
    ):
        ms = r["duration_ms"] or 0
        print(f"  {r['source']} | {r['status']} | inserted={r['records_inserted']} | {ms:.0f}ms")

    print("\n=== scraper_checkpoints ===")
    for r in conn.execute("SELECT source, last_run_at, last_success_at FROM scraper_checkpoints"):
        print(f"  {r['source']} | run={r['last_run_at']} | success={r['last_success_at']}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/market.sqlite"))
