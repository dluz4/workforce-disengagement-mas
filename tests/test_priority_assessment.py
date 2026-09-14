from src.agents.priority_assessment import PriorityAssessmentAgent
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
    return PriorityAssessmentAgent(
        "test@example.com/priority",
        "test-password",
        make_config(),
    )


def test_manager_is_high_priority():
    priority = PriorityAssessmentAgent.classify_priority(
        "Gerente"
    )

    assert priority == "HIGH"


def test_non_manager_is_normal_priority():
    priority = PriorityAssessmentAgent.classify_priority(
        "NaoGerente"
    )

    assert priority == "NORMAL"


def test_priority_rule_is_case_insensitive():
    priority = PriorityAssessmentAgent.classify_priority(
        "  gerente  "
    )

    assert priority == "HIGH"


def test_employee_position_from_map():
    agent = make_agent()

    agent._pos_map = {
        "EMP001": "Gerente",
        "EMP002": "NaoGerente",
    }

    assert agent.employee_position("EMP001") == "Gerente"
    assert agent.employee_position("EMP002") == "NaoGerente"
    assert agent.employee_position("EMP999") == "NaoGerente"


def test_llm_prompt_requires_human_review():
    agent = make_agent()

    prompt = agent.build_llm_prompt(
        employee_id="EMP001",
        managerial_position="Gerente",
        priority_level="HIGH",
        raw_alert="Employee arrived 60 minutes later than baseline.",
    )

    assert "Do not diagnose disengagement" in prompt
    assert "human review" in prompt
    assert "behavioral signal" in prompt

def test_load_position_map(monkeypatch):
    import pandas as pd

    fake_df = pd.DataFrame(
        [
            {
                "EmployeeID": "EMP001",
                "PosGerencial": "Gerente",
            },
            {
                "EmployeeID": "EMP002",
                "PosGerencial": "NaoGerente",
            },
            {
                "EmployeeID": "EMP001",
                "PosGerencial": "NaoGerente",
            },
        ]
    )

    def fake_read_excel(*args, **kwargs):
        return fake_df

    monkeypatch.setattr(
        pd,
        "read_excel",
        fake_read_excel,
    )

    agent = make_agent()

    position_map = agent.load_position_map()

    assert position_map == {
        "EMP001": "NaoGerente",
        "EMP002": "NaoGerente",
    }