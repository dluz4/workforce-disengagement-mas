from src.agents.manager import ManagerAgent
from src.config import Config
from src.governance import IntentType


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
    return ManagerAgent(
        "test@example.com/manager",
        "test-password",
        make_config(),
    )


def test_manager_executes_only_after_agree():
    assert ManagerAgent.should_execute_action("AGREE") is True


def test_manager_does_not_execute_after_reject():
    assert ManagerAgent.should_execute_action("REJECT") is False


def test_manager_decision_is_case_insensitive():
    assert ManagerAgent.should_execute_action(" agree ") is True


def test_manager_has_human_in_the_loop():
    agent = make_agent()

    assert agent.norms.human_in_the_loop is True
    assert agent.norms.collaboration_mode == "joint_intention"


def test_manager_cannot_override_hr():
    agent = make_agent()

    assert agent.norms.override_permission is False

def test_manager_creates_joint_intention():
    agent = make_agent()

    joint_intention = agent.create_joint_intention(
        intent_type=IntentType.PROPOSE,
        goal="Human review before employee-facing action",
        owner=str(agent.jid),
        participants=frozenset(
            {
                str(agent.jid),
                agent.jid_hrpartner,
            }
        ),
        emp_id="EMP001",
    )

    assert joint_intention.intention_id.startswith("JI-")
    assert joint_intention.intent_type == IntentType.PROPOSE
    assert joint_intention.goal == (
        "Human review before employee-facing action"
    )
    assert str(agent.jid) in joint_intention.participants
    assert agent.jid_hrpartner in joint_intention.participants

    stored = agent.get_joint_intention(
        joint_intention.intention_id
    )

    assert stored == joint_intention