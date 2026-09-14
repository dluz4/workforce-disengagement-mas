from src.agents.outcome_tracking import (
    OutcomeHistory,
    OutcomeTrackingAgent,
)
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
    return OutcomeTrackingAgent(
        "test@example.com/outcome",
        "test-password",
        make_config(),
    )


def test_get_history_creates_employee_history():
    agent = make_agent()

    history = agent.get_history("EMP001")

    assert history.emp_id == "EMP001"
    assert agent.get_history("EMP001") is history


def test_normalized_true_when_no_anomalies_and_small_deviation():
    history = OutcomeHistory(
        emp_id="EMP001",
        post_anomalies_count=0,
        post_avg_delta_work_min=8,
    )

    assert (
        OutcomeTrackingAgent.compute_normalized(
            history
        )
        is True
    )


def test_normalized_false_when_anomalies_remain():
    history = OutcomeHistory(
        emp_id="EMP001",
        post_anomalies_count=1,
        post_avg_delta_work_min=5,
    )

    assert (
        OutcomeTrackingAgent.compute_normalized(
            history
        )
        is False
    )


def test_normalized_false_when_deviation_is_too_large():
    history = OutcomeHistory(
        emp_id="EMP001",
        post_anomalies_count=0,
        post_avg_delta_work_min=15,
    )

    assert (
        OutcomeTrackingAgent.compute_normalized(
            history
        )
        is False
    )


def test_normalized_none_without_post_action_data():
    history = OutcomeHistory(
        emp_id="EMP001"
    )

    assert (
        OutcomeTrackingAgent.compute_normalized(
            history
        )
        is None
    )


def test_process_hr_decision():
    agent = make_agent()

    history = agent.process_case_event(
        emp_id="EMP001",
        event="HR_DECISION",
        payload={
            "decision": "AGREE",
            "source": "hr",
        },
    )

    assert history.hr_decision == "AGREE"


def test_process_action_executed():
    agent = make_agent()

    history = agent.process_case_event(
        emp_id="EMP001",
        event="ACTION_EXECUTED",
        payload={
            "action_executed": True,
            "source": "manager",
        },
    )

    assert history.action_executed is True


def test_process_priority_assigned():
    agent = make_agent()

    history = agent.process_case_event(
        emp_id="EMP001",
        event="PRIORITY_ASSIGNED",
        payload={
            "priority": "HIGH",
            "posgerencial": "Gerente",
            "source": "priority",
        },
    )

    assert history.last_priority == "HIGH"
    assert history.last_posgerencial == "Gerente"