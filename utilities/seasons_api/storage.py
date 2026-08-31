"""Write StateResult lists out as JSON or flattened CSV."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import StateResult

CSV_FIELDS = [
    "state_code", "state_name", "species", "season_label", "zone", "method",
    "date_text", "start_date", "end_date", "date_parsed", "source_url", "retrieved_at",
]


def write_json(results: list[StateResult], path: str | Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state_count": len(results),
        "states": [r.to_dict() for r in results],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(results: list[StateResult], path: str | Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for state_result in results:
            for record in state_result.records:
                row = record.to_dict()
                writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
