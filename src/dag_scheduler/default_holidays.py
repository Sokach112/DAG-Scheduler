"""Versioned statutory holiday datasets.

Data lives in ``data/holidays/<region>/<year>.json`` so new years can be added
without touching scheduler code. Only officially published years are included.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Dict, List, Tuple


@lru_cache(maxsize=1)
def all_default_datasets() -> Tuple[Dict, ...]:
    """Load and validate all bundled CN holiday datasets."""
    try:
        root = files("dag_scheduler.data.holidays.cn")
    except (ModuleNotFoundError, FileNotFoundError):
        return ()

    datasets: List[Dict] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".json"):
            continue
        data = json.loads(entry.read_text(encoding="utf-8"))
        if data.get("schema") != 1 or data.get("region") != "CN":
            raise ValueError(f"invalid holiday dataset: {entry.name}")
        year = data.get("year")
        if not isinstance(year, int):
            raise ValueError(f"holiday dataset missing year: {entry.name}")
        datasets.append(data)
    return tuple(datasets)


def holiday_coverage() -> Dict:
    """Public metadata used by the API/UI to warn about uncovered years."""
    datasets = all_default_datasets()
    years = sorted({item["year"] for item in datasets})
    latest = max(
        (item.get("published_at", "") for item in datasets), default="")
    return {
        "region": "CN",
        "name": "China statutory holidays",
        "years": years,
        "updated_at": latest,
        "sources": {
            str(item["year"]): item.get("source", "")
            for item in datasets
        },
    }


def default_holidays(year: int) -> List[Tuple[str, str]]:
    for item in all_default_datasets():
        if item["year"] == year:
            return [
                (h["start"], h["end"]) for h in item.get("holidays", [])
            ]
    return []


def default_extra_workdays(year: int) -> List[str]:
    for item in all_default_datasets():
        if item["year"] == year:
            return list(item.get("makeup_workdays", []))
    return []
