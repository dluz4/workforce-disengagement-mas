from __future__ import annotations

import json

from spade.behaviour import CyclicBehaviour

from src.analytics import compute_baseline_and_anomalies
from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import CoopPillar, SocialNorms
from spade.behaviour import CyclicBehaviour
from spade.message import Message

class BehaviourMonitorAgent(BaseSpecialistAgent):
    """
    Receives attendance records from the Timekeeper Agent
    and evaluates deviations from the employee baseline.
    """

    def __init__(
        self,
        jid: str,
        password: str,
        config: Config,
    ):
        norms = SocialNorms(
            confidentiality="high",
            hierarchy_respect=True,
            autonomy_level="medium",
            communication_scope="restricted",
            communication_frequency="event_driven",
            decision_authority="analyze",
            override_permission=False,
            accountability_level="high",
            audit_required=True,
            collaboration_mode="cooperative",
            conflict_resolution_style="escalation",
            human_in_the_loop=False,
            fairness_constraint="required",
            time_sensitivity="medium",
            cooldown_required=True,
        )

        super().__init__(
            jid,
            password,
            config,
            name="BehaviourMonitorAgent",
            pillars=frozenset(
                {
                    CoopPillar.TASK_SHARING,
                    CoopPillar.RESULT_SHARING,
                    CoopPillar.SOCIAL_NORMS,
                    CoopPillar.HANDLING_INCONSISTENCY,
                }
            ),
            norms=norms,
        )

    def analyze_records(
        self,
        records: list[dict],
    ) -> dict:
        baseline, anomalies = compute_baseline_and_anomalies(
            records,
            baseline_days=self.config.baseline_days,
            alert_minutes=self.config.variation_alert,
        )

        return {
            "baseline": baseline,
            "anomalies": anomalies,
            "anomalies_count": len(anomalies),
        }

    class ReceiveAttendanceBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)

            if msg is None:
                return

            agent: BehaviourMonitorAgent = self.agent

            agent.msg_in_count += 1

            try:
                payload = json.loads(msg.body)

                employee_id = payload["EmployeeID"]
                records = payload["records"]

            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                agent.record_inconsistency(
                    topic="invalid_attendance_payload",
                    description=str(exc),
                    parties=frozenset(
                        {
                            str(msg.sender),
                            str(agent.jid),
                        }
                    ),
                    context={
                        "raw_body": msg.body,
                    },
                )
                return

            result = agent.analyze_records(records)

            agent._audit(
                "ATTENDANCE_ANALYZED",
                employee_id=employee_id,
                anomalies_count=result["anomalies_count"],
            )




            if result["anomalies_count"] <= 0:
                return

            allowed_alert, policy_reason, _ = agent._policy_allow_alert(
                emp_id=str(employee_id),
                alert_type="attendance_pattern_alert",
                anomalies_count=result["anomalies_count"],
            )

            if not allowed_alert:
                agent._audit(
                    "ALERT_SUPPRESSED",
                    employee_id=employee_id,
                    reason=policy_reason,
                )
                return

            alert_msg = Message(
                to=f"{agent.config.base_jid}/priority"
            )

            alert_msg.set_metadata(
                "type",
                "attendance_pattern_alert",
            )

            alert_msg.body = json.dumps(
                {
                    "EmployeeID": employee_id,
                    "baseline": result["baseline"],
                    "anomalies": result["anomalies"],
                    "anomalies_count": result["anomalies_count"],
                },
                default=str,
            )

            allowed_send, reason = agent.is_allowed(alert_msg)

            if not allowed_send:
                agent._audit(
                    "MESSAGE_BLOCKED",
                    to=str(alert_msg.to),
                    reason=reason,
                )
                return

            await agent.send(alert_msg)

            agent.msg_out_count += 1

            agent._audit(
                "ATTENDANCE_ALERT_SENT",
                employee_id=employee_id,
                anomalies_count=result["anomalies_count"],
            )








    async def setup(self):
        await super().setup()

        self.add_behaviour(
            self.ReceiveAttendanceBehaviour()
        )