from src.agents.hr_partner import HRPartnerAgent
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
    return HRPartnerAgent(
        "test@example.com/hr",
        "test-password",
        make_config(),
    )


def test_joint_intention_decision_is_agree():
    decision = HRPartnerAgent.decide_joint_intention(
        intention_id="JI-001",
        employee_id="EMP001",
        goal="Review attendance anomaly",
    )

    assert decision == "AGREE"


def test_hr_partner_has_human_in_the_loop():
    agent = make_agent()

    assert agent.norms.human_in_the_loop is True
    assert agent.norms.override_permission is True


def test_hr_partner_decision_authority():
    agent = make_agent()

    assert agent.norms.decision_authority == "approve_or_reject"