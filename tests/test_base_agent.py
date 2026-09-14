from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import (
    CoopPillar,
    IntentType,
    SocialNorms,
)


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


def make_norms():
    return SocialNorms(
        confidentiality="high",
        hierarchy_respect=True,
        autonomy_level="medium",
        communication_scope="restricted",
        communication_frequency="event_driven",
        decision_authority="recommend",
        override_permission=False,
        accountability_level="high",
        audit_required=True,
        collaboration_mode="cooperative",
        conflict_resolution_style="escalation",
        human_in_the_loop=True,
        fairness_constraint="required",
        time_sensitivity="medium",
        cooldown_required=True,
    )


def make_agent():
    return BaseSpecialistAgent(
        "test@example.com/testagent",
        "test-password",
        make_config(),
        name="TestAgent",
        pillars=frozenset(
            {
                CoopPillar.SOCIAL_NORMS,
                CoopPillar.JOINT_INTENTIONS,
            }
        ),
        norms=make_norms(),
    )


def test_create_joint_intention():
    agent = make_agent()

    intention = agent.create_joint_intention(
        intent_type=IntentType.PROPOSE,
        goal="Review attendance anomaly",
        owner="test@example.com/testagent",
        participants=frozenset(
            {
                "test@example.com/hr",
                "test@example.com/manager",
            }
        ),
        emp_id="EMP001",
    )

    assert intention.intent_type == IntentType.PROPOSE
    assert intention.goal == "Review attendance anomaly"
    assert intention.intention_id.startswith("JI-")

    stored = agent.get_joint_intention(
        intention.intention_id
    )

    assert stored == intention


def test_medium_cooldown():
    agent = make_agent()

    assert agent._cooldown_seconds_from_norms() == 3600


def test_event_driven_policy_blocks_without_anomaly():
    agent = make_agent()

    allowed, reason, _ = agent._policy_allow_alert(
        emp_id="EMP001",
        alert_type="attendance",
        anomalies_count=0,
    )

    assert allowed is False
    assert reason == "No anomaly event."