"""Built-in statutory holiday data.

Covers China 2025–2027 official State Council schedules (holiday periods and
weekend make-up workdays). Custom holiday ranges remain the fallback for other
years or regions.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


# China, 2026 official State Council schedule.
DEFAULT_HOLIDAY_RANGES: Dict[int, List[Tuple[str, str]]] = {
    2025: [
        ("2025-01-01", "2025-01-01"),
        ("2025-01-28", "2025-02-04"),
        ("2025-04-04", "2025-04-06"),
        ("2025-05-01", "2025-05-05"),
        ("2025-05-31", "2025-06-02"),
        ("2025-10-01", "2025-10-08"),
    ],
    2026: [
        ("2026-01-01", "2026-01-03"),
        ("2026-02-15", "2026-02-23"),
        ("2026-04-04", "2026-04-06"),
        ("2026-05-01", "2026-05-05"),
        ("2026-06-19", "2026-06-21"),
        ("2026-09-25", "2026-09-27"),
        ("2026-10-01", "2026-10-07"),
    ],
    2027: [
        ("2027-01-01", "2027-01-03"),
        ("2027-02-05", "2027-02-13"),
        ("2027-04-03", "2027-04-05"),
        ("2027-05-01", "2027-05-05"),
        ("2027-06-09", "2027-06-09"),
        ("2027-09-15", "2027-09-15"),
        ("2027-10-01", "2027-10-07"),
    ],
}

# Weekend make-up workdays in the official schedules.
DEFAULT_EXTRA_WORKDAYS: Dict[int, List[str]] = {
    2025: [
        "2025-01-26",
        "2025-02-08",
        "2025-04-27",
        "2025-09-28",
        "2025-10-11",
    ],
    2026: [
        "2026-01-04",
        "2026-02-14",
        "2026-02-28",
        "2026-05-09",
        "2026-09-20",
        "2026-10-10",
    ],
    2027: [
        "2027-01-31",
        "2027-02-14",
        "2027-05-08",
        "2027-09-26",
        "2027-10-09",
    ],
}


def default_holidays(year: int) -> List[Tuple[str, str]]:
    return list(DEFAULT_HOLIDAY_RANGES.get(year, []))


def default_extra_workdays(year: int) -> List[str]:
    return list(DEFAULT_EXTRA_WORKDAYS.get(year, []))
