from __future__ import annotations

from datetime import datetime, time

import pandas as pd


def to_minutes(value) -> int | None:
    """
    Convert HH:MM, HH:MM:SS, datetime, time or Timestamp
    into minutes since midnight.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, datetime):
        return value.hour * 60 + value.minute

    if isinstance(value, time):
        return value.hour * 60 + value.minute

    s = str(value).strip()

    if not s or s.lower() == "nan":
        return None

    if " " in s:
        s = s.split()[-1]

    parts = s.split(":")

    if len(parts) < 2:
        return None

    h = int(parts[0])
    m = int(parts[1])

    return h * 60 + m


def format_hhmm(minutes: int | float | None) -> str:
    if minutes is None:
        return "-"

    minutes = int(round(minutes))

    h = minutes // 60
    m = minutes % 60

    return f"{h:02d}:{m:02d}"


def work_minutes(
    clock_in_min: int | None,
    clock_out_min: int | None,
) -> int | None:
    """
    Calculate worked minutes.
    Supports overnight shifts.
    """
    if clock_in_min is None or clock_out_min is None:
        return None

    delta = clock_out_min - clock_in_min

    if delta < 0:
        delta += 24 * 60

    return delta


def format_hours(minutes: float | int | None) -> str:
    if minutes is None:
        return "-"

    m = int(round(minutes))
    h = m // 60
    mm = m % 60

    return f"{h:02d}:{mm:02d}"


def format_signed_hours(minutes: float | int | None) -> str:
    if minutes is None:
        return "-"

    sign = "+" if minutes >= 0 else "-"

    m = abs(int(round(minutes)))
    h = m // 60
    mm = m % 60

    return f"{sign}{h:02d}:{mm:02d}"


def _median(values: list[int]) -> float:
    values = sorted(values)

    n = len(values)
    mid = n // 2

    if n % 2 == 1:
        return values[mid]

    return (values[mid - 1] + values[mid]) / 2


def compute_baseline_and_anomalies(
    records: list[dict],
    baseline_days: int,
    alert_minutes: int,
):
    """
    Compute an individual attendance baseline and detect deviations.

    Baseline:
        median clock-in and clock-out time from the first
        `baseline_days` observations.

    Anomaly:
        an observation after the baseline period where either
        clock-in or clock-out deviates by more than `alert_minutes`.
    """

    records_sorted = sorted(
        records,
        key=lambda r: str(r.get("Data", "")),
    )

    if len(records_sorted) < baseline_days:
        return None, []

    baseline_records = records_sorted[:baseline_days]
    post_baseline_records = records_sorted[baseline_days:]

    clock_in_values = [
        to_minutes(r.get("Entrada"))
        for r in baseline_records
    ]

    clock_out_values = [
        to_minutes(r.get("Saida"))
        for r in baseline_records
    ]

    clock_in_values = [
        value for value in clock_in_values
        if value is not None
    ]

    clock_out_values = [
        value for value in clock_out_values
        if value is not None
    ]

    if not clock_in_values or not clock_out_values:
        return None, []

    baseline = {
        "entrada": {
            "median": _median(clock_in_values),
            "min": min(clock_in_values),
            "max": max(clock_in_values),
        },
        "saida": {
            "median": _median(clock_out_values),
            "min": min(clock_out_values),
            "max": max(clock_out_values),
        },
    }

    baseline["entrada"]["range"] = (
        baseline["entrada"]["max"]
        - baseline["entrada"]["min"]
    )

    baseline["saida"]["range"] = (
        baseline["saida"]["max"]
        - baseline["saida"]["min"]
    )

    anomalies = []

    for record in post_baseline_records:
        clock_in = to_minutes(record.get("Entrada"))
        clock_out = to_minutes(record.get("Saida"))

        if clock_in is None or clock_out is None:
            continue

        delta_in = (
            clock_in
            - baseline["entrada"]["median"]
        )

        delta_out = (
            clock_out
            - baseline["saida"]["median"]
        )

        if (
            abs(delta_in) > alert_minutes
            or abs(delta_out) > alert_minutes
        ):
            anomalies.append(
                {
                    "Data": str(record.get("Data", "")),
                    "Entrada": str(record.get("Entrada", "")),
                    "Saida": str(record.get("Saida", "")),
                    "DeltaEntradaMin": int(delta_in),
                    "DeltaSaidaMin": int(delta_out),
                }
            )

    return baseline, anomalies