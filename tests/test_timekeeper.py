import pandas as pd

from src.agents.timekeeper import TimekeeperAgent
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
    )


def make_agent():
    return TimekeeperAgent(
        "test@example.com/timekeeper",
        "test-password",
        make_config(),
    )


def test_employee_records_filters_one_employee():
    df = pd.DataFrame(
        [
            {
                "EmployeeID": "EMP001",
                "Data": "2026-01-02",
                "Entrada": "08:10",
                "Saida": "17:00",
            },
            {
                "EmployeeID": "EMP002",
                "Data": "2026-01-01",
                "Entrada": "09:00",
                "Saida": "18:00",
            },
            {
                "EmployeeID": "EMP001",
                "Data": "2026-01-01",
                "Entrada": "08:00",
                "Saida": "17:00",
            },
        ]
    )

    agent = make_agent()

    records = agent.employee_records(
        df,
        "EMP001",
    )

    assert len(records) == 2

    assert all(
        str(record["EmployeeID"]) == "EMP001"
        for record in records
    )

    assert str(records[0]["Data"]) == "2026-01-01"
    assert str(records[1]["Data"]) == "2026-01-02"


def test_employee_records_unknown_employee():
    df = pd.DataFrame(
        [
            {
                "EmployeeID": "EMP001",
                "Data": "2026-01-01",
                "Entrada": "08:00",
                "Saida": "17:00",
            }
        ]
    )

    agent = make_agent()

    records = agent.employee_records(
        df,
        "EMP999",
    )

    assert records == []