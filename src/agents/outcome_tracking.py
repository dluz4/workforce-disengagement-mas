from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from spade.behaviour import CyclicBehaviour
from spade.message import Message

from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import CoopPillar, SocialNorms


@dataclass
class OutcomeHistory:
    emp_id: str

    baseline_in_median: float | None = None
    baseline_out_median: float | None = None
    baseline_avg_work_min: float | None = None

    window_anomalies_count: int = 0
    last_priority: str | None = None
    last_posgerencial: str | None = None

    hr_decision: str | None = None
    action_executed: bool | None = None

    post_avg_work_min: float | None = None
    post_avg_delta_work_min: float | None = None
    post_anomalies_count: int | None = None

    normalized: bool | None = None

    last_update_ts: str | None = None

    audit_events: list[dict[str, Any]] = field(
        default_factory=list
    )


class OutcomeTrackingAgent(BaseSpecialistAgent):
    """
    Tracks the lifecycle of an employee-related case.

    It records:
    - behavioral metrics;
    - assigned priority;
    - HR decision;
    - manager action;
    - post-action outcomes.
    """

    def __init__(
        self,
        jid: str,
        password: str,
        config: Config,
    ):
        norms = SocialNorms(
            confidentiality="restricted",
            hierarchy_respect=True,
            autonomy_level="medium",
            communication_scope="mediated",
            communication_frequency="periodic",
            decision_authority="recommend",
            override_permission=False,
            accountability_level="shared",
            audit_required=True,
            collaboration_mode="cooperative",
            conflict_resolution_style="escalate",
            human_in_the_loop=True,
            fairness_constraint="basic",
            time_sensitivity="low",
            cooldown_required=True,
        )

        super().__init__(
            jid,
            password,
            config,
            name="OutcomeTrackingAgent",
            pillars=frozenset(
                {
                    CoopPillar.RESULT_SHARING,
                    CoopPillar.TASK_SHARING,
                    CoopPillar.SOCIAL_NORMS,
                }
            ),
            norms=norms,
        )

        self._hist: dict[str, OutcomeHistory] = {}

    @staticmethod
    def append_jsonl(
        path: str,
        record: dict,
    ) -> None:
        file_path = Path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with file_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )

    def get_history(
        self,
        emp_id: str,
    ) -> OutcomeHistory:
        if emp_id not in self._hist:
            self._hist[emp_id] = OutcomeHistory(
                emp_id=emp_id
            )

        return self._hist[emp_id]

    @staticmethod
    def compute_normalized(
        history: OutcomeHistory,
    ) -> bool | None:
        """
        Minimal prototype normalization rule.

        A case is considered normalized when:
        - no post-action anomalies remain; and
        - average work-time deviation is within ±10 minutes.
        """

        if (
            history.post_anomalies_count is None
            or history.post_avg_delta_work_min is None
        ):
            return None

        return (
            history.post_anomalies_count == 0
            and abs(
                history.post_avg_delta_work_min
            ) <= 10
        )

    @staticmethod
    def update_timestamp(
        history: OutcomeHistory,
    ) -> None:
        history.last_update_ts = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

    def process_metric_snapshot(
        self,
        *,
        emp_id: str,
        payload: dict,
    ) -> OutcomeHistory:

        history = self.get_history(emp_id)

        history.baseline_in_median = payload.get(
            "baseline_in_median",
            history.baseline_in_median,
        )

        history.baseline_out_median = payload.get(
            "baseline_out_median",
            history.baseline_out_median,
        )

        history.baseline_avg_work_min = payload.get(
            "avg_base_work_min",
            history.baseline_avg_work_min,
        )

        history.window_anomalies_count = payload.get(
            "window_anomalies_count",
            history.window_anomalies_count,
        )

        history.post_avg_work_min = payload.get(
            "avg_after_work_min",
            history.post_avg_work_min,
        )

        history.post_avg_delta_work_min = payload.get(
            "avg_delta_work_min",
            history.post_avg_delta_work_min,
        )

        history.post_anomalies_count = payload.get(
            "window_anomalies_count",
            history.post_anomalies_count,
        )

        history.audit_events.append(
            {
                "ts": payload.get("ts"),
                "type": "metric_snapshot",
                "source": payload.get("source"),
            }
        )

        self.update_timestamp(history)

        history.normalized = (
            self.compute_normalized(history)
        )

        return history

    def process_case_event(
        self,
        *,
        emp_id: str,
        event: str,
        payload: dict,
    ) -> OutcomeHistory:

        history = self.get_history(emp_id)

        event = (event or "").strip()

        if event == "PRIORITY_ASSIGNED":
            history.last_priority = payload.get(
                "priority",
                history.last_priority,
            )

            history.last_posgerencial = payload.get(
                "posgerencial",
                history.last_posgerencial,
            )

        elif event == "HR_DECISION":
            history.hr_decision = payload.get(
                "decision",
                history.hr_decision,
            )

        elif event == "ACTION_EXECUTED":
            history.action_executed = bool(
                payload.get(
                    "action_executed",
                    True,
                )
            )

        history.audit_events.append(
            {
                "ts": payload.get("ts"),
                "type": "case_event",
                "event": event,
                "source": payload.get("source"),
            }
        )

        self.update_timestamp(history)

        history.normalized = (
            self.compute_normalized(history)
        )

        return history

    class Inbox(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)

            if msg is None:
                return

            agent: OutcomeTrackingAgent = self.agent

            agent.msg_in_count += 1

            message_type = msg.get_metadata("type")

            employee_id = (
                msg.get_metadata("emp_id")
                or ""
            ).strip()

            if message_type == "inconsistency_record":
                agent._audit(
                    "INCONSISTENCY_RECEIVED",
                    body=msg.body,
                )
                return

            if message_type not in (
                "metric_snapshot",
                "case_event",
            ):
                return

            if not employee_id:
                agent._audit(
                    "OUTCOME_MESSAGE_IGNORED",
                    reason="Missing emp_id",
                    message_type=message_type,
                )
                return

            try:
                payload = (
                    json.loads(msg.body)
                    if msg.body
                    else {}
                )
            except Exception:
                payload = {
                    "raw": msg.body
                }

            event_record = {
                "ts": payload.get("ts")
                or datetime.now().isoformat(
                    timespec="seconds"
                ),
                "emp_id": employee_id,
                "mtype": message_type,
                "meta": dict(msg.metadata),
                "payload": payload,
            }

            agent.append_jsonl(
                "reports/outcome_events.jsonl",
                event_record,
            )

            if message_type == "metric_snapshot":
                agent.process_metric_snapshot(
                    emp_id=employee_id,
                    payload=payload,
                )
                return

            if message_type == "case_event":
                event = (
                    msg.get_metadata("event")
                    or payload.get("event")
                    or ""
                )

                agent.process_case_event(
                    emp_id=employee_id,
                    event=event,
                    payload=payload,
                )
                return

    async def setup(self):
        await super().setup()

        self.add_behaviour(
            self.Inbox()
        )