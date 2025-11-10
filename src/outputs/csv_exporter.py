import csv
from pathlib import Path
from typing import List, Dict, Any

def write_csv(records: List[Dict[str, Any]], path: Path) -> None:
    if not records:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            f.write("")  # create empty file if no records
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for r in records for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: _stringify(v) for k, v in r.items()})

def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        return "; ".join(map(str, v))
    return str(v)