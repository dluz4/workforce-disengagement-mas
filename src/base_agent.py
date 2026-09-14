from __future__ import annotations

import time as pytime
import uuid
import json

from collections import defaultdict
from datetime import datetime
from typing import FrozenSet, Optional

from spade.agent import Agent
from spade.message import Message

from src.config import Config
from src.governance import (
    CoopPillar,
    InconsistencyRecord,
    IntentType,
    JointIntention,
    SocialNorms,
)
from src.social_laws import is_allowed_send


class BaseSpecialistAgent(Agent):
    """
    Base class shared by all specialist agents.

    Responsibilities:
    - telemetry
    - audit trail
    - inconsistency registry
    - joint intention registry
    - communication policy
    - cooldown and daily alert limits
    - Social Law enforcement
    """

    def __init__(
        self,
        jid: str,
        password: str,
        config: Config,
        *,
        name: str,
        pillars: FrozenSet[CoopPillar],
        norms: Optional[SocialNorms] = None,
    ):
        super().__init__(jid, password)

        self.config = config
        self.agent_name = name
        self.norms = norms
        self.pillars = pillars

        # Telemetry
        self.started_at: float | None = None
        self.msg_in_count = 0
        self.msg_out_count = 0
        self.last_msg_in_at: float | None = None
        self.last_msg_out_at: float | None = None

        self.semantic_status = "INIT"

        # Known agent addresses
        self.jid_rh = config.jid_rh
        self.jid_timekeeper = config.jid_timekeeper
        self.jid_behavioral = config.jid_behavioral
        self.jid_hrpartner = config.jid_hrpartner
        self.jid_outcome = config.jid_outcome

        # Governance registries
        self._joint_intentions: dict[str, JointIntention] = {}
        self._ji_final_decision: dict[str, str] = {}
        self._inconsistencies: dict[str, InconsistencyRecord] = {}

        # Audit trail
        self._audit_log: list[dict] = []

        # Alert policy state
        self._last_alert_at: dict[str, float] = {}
        self._daily_alert_counts = defaultdict(int)
        self._daily_key_date: str | None = None

    async def setup(self):
        await super().setup()

        self.started_at = pytime.time()
        self.semantic_status = "IDLE"

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _audit(self, event: str, **data):
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "agent": self.agent_name,
            "jid": str(self.jid),
            "event": event,
            **data,
        }

        self._audit_log.append(record)

    # ------------------------------------------------------------------
    # Social Law
    # ------------------------------------------------------------------

    def is_allowed(self, msg: Message) -> tuple[bool, str]:
        return is_allowed_send(
            sender_jid=str(self.jid),
            receiver_jid=str(msg.to),
            msg=msg,
        )

    # ------------------------------------------------------------------
    # Inconsistency management
    # ------------------------------------------------------------------

    def _new_inconsistency_id(self) -> str:
        return f"INC-{uuid.uuid4().hex[:10]}"

    def record_inconsistency(
        self,
        *,
        topic: str,
        description: str,
        parties: FrozenSet[str],
        context: Optional[dict] = None,
    ) -> InconsistencyRecord:

        inconsistency_id = self._new_inconsistency_id()

        record = InconsistencyRecord(
            inconsistency_id=inconsistency_id,
            detected_by=str(self.jid),
            topic=topic,
            description=description,
            parties=parties,
        )

        self._inconsistencies[inconsistency_id] = record

        self._audit(
            "INCONSISTENCY_RECORDED",
            inconsistency_id=inconsistency_id,
            topic=topic,
            description=description,
            parties=sorted(parties),
            context=context or {},
        )

        return record

    # ------------------------------------------------------------------
    # Joint intentions
    # ------------------------------------------------------------------

    def create_joint_intention(
        self,
        *,
        intent_type: IntentType,
        goal: str,
        owner: str,
        participants: FrozenSet[str],
        emp_id: str | None = None,
    ) -> JointIntention:

        intention_id = f"JI-{uuid.uuid4().hex[:10]}"

        intention = JointIntention(
            intention_id=intention_id,
            intent_type=intent_type,
            goal=goal,
            owner=owner,
            participants=participants,
        )

        self._joint_intentions[intention_id] = intention

        self._audit(
            "JI_CREATED",
            intention_id=intention_id,
            intent_type=intent_type.name,
            goal=goal,
            owner=owner,
            participants=sorted(participants),
            emp_id=emp_id,
        )

        return intention

    def get_joint_intention(
        self,
        intention_id: str,
    ) -> Optional[JointIntention]:

        return self._joint_intentions.get(intention_id)

    # ------------------------------------------------------------------
    # Alert policy
    # ------------------------------------------------------------------

    def _today_key(self) -> str:
        return datetime.now().date().isoformat()

    def _reset_daily_if_needed(self):
        today = self._today_key()

        if self._daily_key_date != today:
            self._daily_key_date = today
            self._daily_alert_counts.clear()

    def _cooldown_seconds_from_norms(self) -> int:
        if self.norms is None:
            return 0

        sensitivity = (
            self.norms.time_sensitivity or "medium"
        ).lower()

        if sensitivity == "high":
            return 10 * 60

        if sensitivity == "medium":
            return 60 * 60

        return 6 * 60 * 60

    def _policy_allow_alert(
        self,
        *,
        emp_id: str,
        alert_type: str,
        anomalies_count: int,
        daily_limit: int = 3,
    ) -> tuple[bool, str, str]:

        key = f"{emp_id}:{alert_type}"

        if self.norms is None:
            return True, "OK", key

        if (
            self.norms.communication_frequency.lower()
            == "event_driven"
            and anomalies_count <= 0
        ):
            return False, "No anomaly event.", key

        self._reset_daily_if_needed()

        daily_key = f"{self._today_key()}:{key}"

        if self._daily_alert_counts[daily_key] >= daily_limit:
            return (
                False,
                f"Daily alert limit reached ({daily_limit}) for {key}.",
                key,
            )

        if self.norms.cooldown_required:
            cooldown_seconds = self._cooldown_seconds_from_norms()

            last_alert = self._last_alert_at.get(key)

            now = pytime.time()

            if (
                last_alert is not None
                and now - last_alert < cooldown_seconds
            ):
                return (
                    False,
                    f"Cooldown active ({cooldown_seconds}s) for {key}.",
                    key,
                )

        self._daily_alert_counts[daily_key] += 1
        self._last_alert_at[key] = pytime.time()

        return True, "OK", key

    async def escalate_inconsistency(
        self,
        inconsistency_id: str,
    ) -> None:
        """
        Escalates a previously recorded inconsistency
        to the Outcome Tracking Agent.
        """

        record = self._inconsistency_registry.get(
            inconsistency_id
        )

        if record is None:
            self._audit(
                "INCONSISTENCY_ESCALATION_FAILED",
                inconsistency_id=inconsistency_id,
                reason="Unknown inconsistency_id",
            )
            return

        msg = Message(
            to=self.jid_outcome
        )

        msg.set_metadata(
            "performative",
            "inform",
        )

        msg.set_metadata(
            "type",
            "inconsistency_record",
        )

        msg.set_metadata(
            "source",
            self.name,
        )

        msg.body = json.dumps(
            {
                "inconsistency_id": (
                    record.inconsistency_id
                ),
                "detected_by": (
                    record.detected_by
                ),
                "topic": (
                    record.topic
                ),
                "description": (
                    record.description
                ),
                "parties": sorted(
                    record.parties
                ),
            },
            default=str,
        )

        allowed, reason = self.is_allowed(
            msg
        )

        if not allowed:
            self._audit(
                "INCONSISTENCY_ESCALATION_BLOCKED",
                inconsistency_id=inconsistency_id,
                reason=reason,
            )
            return

        await self.send(
            msg
        )

        self.msg_out_count += 1

        self._audit(
            "INCONSISTENCY_ESCALATED",
            inconsistency_id=inconsistency_id,
            to=str(msg.to),
        )