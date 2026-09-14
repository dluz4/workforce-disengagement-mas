from src.agents.behaviour_monitor import BehaviourMonitorAgent
from src.config import Config


def make_config():
    return Config(
        base_jid="test@example.com",
        password="test-password",
        jid_rh="test@example.com/manager",
        jid_behavioral="test@example.com/behavioral",
        jid_timekeeper="test@example.com/timekeeper",
        jid_hrpartner="test@example.com/hr",
        jid_outcome="test@example.com/outcome",
        excel_path="dummy.xlsx",
        baseline_days=30,
        variation_alert=30,
    )


def make_agent():
    return BehaviourMonitorAgent(
        "test@example.com/behavioral",
        "test-password",
        make_config(),
    )


def test_analyze_records_detects_one_anomaly():
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

    agent = make_agent()

    result = agent.analyze_records(records)

    assert result["baseline"] is not None
    assert result["anomalies_count"] == 1
    assert len(result["anomalies"]) == 1

    anomaly = result["anomalies"][0]

    assert anomaly["DeltaEntradaMin"] == 60
    assert anomaly["DeltaSaidaMin"] == 0


def test_analyze_records_without_anomaly():
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
            "Entrada": "08:20",
            "Saida": "17:10",
        }
    )

    agent = make_agent()

    result = agent.analyze_records(records)

    assert result["baseline"] is not None
    assert result["anomalies_count"] == 0
    assert result["anomalies"] == []