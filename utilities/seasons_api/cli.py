"""Command-line entrypoint.

Examples:
    python -m utilities.seasons_api.cli --states NH,VT,ME --out seasons.json
    python -m utilities.seasons_api.cli --all --out seasons.csv --format csv
    python -m utilities.seasons_api.cli --list-states
"""
from __future__ import annotations

import argparse
import sys

from . import aggregator, storage
from .registry import REGISTRY


def _list_states() -> None:
    for code, entry in sorted(REGISTRY.items()):
        detail = entry.slug or entry.note or ""
        print(f"{code}\t{entry.name}\t{entry.adapter_type}\t{detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--states", help="Comma-separated USPS state codes, e.g. NH,VT,ME")
    group.add_argument("--all", action="store_true", help="Run every state in the registry")
    parser.add_argument("--list-states", action="store_true", help="Print the registry and exit")
    parser.add_argument("--out", default="seasons_output.json", help="Output file path")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument(
        "--season-start-year", type=int, default=2026,
        help="Calendar year the season begins in (e.g. 2026 for the '2026-27' season)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between HTTP requests (politeness throttle)",
    )
    args = parser.parse_args(argv)

    if args.list_states:
        _list_states()
        return 0

    if not args.states and not args.all:
        parser.error("pass --states CODE,CODE or --all")

    state_codes = None if args.all else [s.strip() for s in args.states.split(",")]

    unknown = [c for c in (state_codes or []) if c.upper() not in REGISTRY]
    if unknown:
        parser.error(f"unknown state code(s): {', '.join(unknown)}")

    results = aggregator.run(
        state_codes=state_codes,
        season_start_year=args.season_start_year,
        request_delay_seconds=args.delay,
    )

    if args.format == "json":
        storage.write_json(results, args.out)
    else:
        storage.write_csv(results, args.out)

    total_records = sum(len(r.records) for r in results)
    errors = [r for r in results if r.error]
    print(f"Wrote {total_records} season records for {len(results)} state(s) to {args.out}")
    if errors:
        print(f"{len(errors)} state(s) had no data / an error — see the 'error' field per state:")
        for r in errors:
            print(f"  {r.state_code}: {r.error}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
