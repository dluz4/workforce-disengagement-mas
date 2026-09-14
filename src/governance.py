from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import FrozenSet


class CoopPillar(Enum):
    TASK_SHARING = auto()
    RESULT_SHARING = auto()
    JOINT_INTENTIONS = auto()
    SOCIAL_NORMS = auto()
    HANDLING_INCONSISTENCY = auto()


class IntentType(Enum):
    REQUEST = auto()
    INFORM = auto()
    PROPOSE = auto()
    AGREE = auto()
    REJECT = auto()
    ESCALATE = auto()


class ResultType(Enum):
    METRIC = auto()
    ALERT = auto()
    DECISION = auto()
    ACTION_STATUS = auto()


@dataclass(frozen=True)
class SocialNorms:
    """Social and organizational governance profile assigned to an agent."""

    # Basic norms
    confidentiality: str
    hierarchy_respect: bool
    autonomy_level: str

    # Communication norms
    communication_scope: str
    communication_frequency: str

    # Decision and authority norms
    decision_authority: str
    override_permission: bool

    # Accountability norms
    accountability_level: str
    audit_required: bool

    # Cooperation norms
    collaboration_mode: str
    conflict_resolution_style: str

    # Ethical and human-centered norms
    human_in_the_loop: bool
    fairness_constraint: str

    # Temporal norms
    time_sensitivity: str
    cooldown_required: bool


@dataclass(frozen=True)
class JointIntention:
    intention_id: str
    intent_type: IntentType
    goal: str
    owner: str
    participants: FrozenSet[str]


@dataclass(frozen=True)
class SharedResult:
    result_id: str
    result_type: ResultType
    produced_by: str
    payload_ref: str


@dataclass(frozen=True)
class InconsistencyRecord:
    inconsistency_id: str
    detected_by: str
    topic: str
    description: str
    parties: FrozenSet[str]