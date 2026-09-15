from src.analytics import (
    compute_baseline_and_anomalies,
    to_minutes,
    work_minutes,
)


def test_to_minutes():
    assert to_minutes("08:30") == 510
    assert to_minutes("17:15:00") == 1035


def test_work_minutes():
    assert work_minutes(480, 1020) == 540
    assert work_minutes(1380, 60) == 120


def test_baseline_and_anomaly_detection():
    records = []

    for day in range(1, 31):
        records.append(
            {
                "Data": f"2026-01-{day:02d}",
                "Entrada": "08:00",
                "Saida": "17:00",
            }
        )

    records.append(
        {
            "Data": "2026-02-01",
            "Entrada": "09:00",
            "Saida": "17:00",
        }
    )

    baseline, anomalies = compute_baseline_and_anomalies(
        records,
        baseline_days=30,
        alert_minutes=30,
    )

    assert baseline is not None
    assert baseline["entrada"]["mean"] == 480
    assert baseline["saida"]["mean"] == 1020

    assert len(anomalies) == 1
    assert anomalies[0]["DeltaEntradaMin"] == 60