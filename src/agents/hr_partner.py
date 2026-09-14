from __future__ import annotations

import json
from datetime import datetime

from spade.behaviour import CyclicBehaviour
from spade.message import Message

from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import CoopPillar, SocialNorms


class HRPartnerAgent(BaseSpecialistAgent):
    """
    Human-in-the-loop coordination agent.

    Responsibilities:
    - receive prioritized attendance alerts;
    - receive joint-intention proposals;
    - issue an HR decision;
    - return the decision to the Manager Agent.
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
            decision_authority="approve_or_reject",
            override_permission=True,
            accountability_level="high",
            audit_required=True,
            collaboration_mode="cooperative",
            conflict_resolution_style="human_review",
            human_in_the_loop=True,
            fairness_constraint="required",
            time_sensitivity="medium",
            cooldown_required=False,
        )

        super().__init__(
            jid,
            password,
            config,
            name="HRPartnerAgent",
            pillars=frozenset(
                {
                    CoopPillar.JOINT_INTENTIONS,
                    CoopPillar.RESULT_SHARING,
                    CoopPillar.SOCIAL_NORMS,
                    CoopPillar.HANDLING_INCONSISTENCY,
                }
            ),
            norms=norms,
        )

    # --------------------------------------------------------------
    # Decision rule
    # --------------------------------------------------------------

    @staticmethod
    def decide_joint_intention(
        *,
        intention_id: str,
        employee_id: str,
        goal: str,
    ) -> str:
        """
        Prototype decision rule.

        For now the HR Partner automatically agrees.
        This will later be replaced by an explicit human decision
        or another controlled HITL mechanism.
        """

        return "AGREE"

    # --------------------------------------------------------------
    # Behaviour
    # --------------------------------------------------------------

    class Inbox(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)

            if msg is None:
                return

            agent: HRPartnerAgent = self.agent

            agent.msg_in_count += 1

            message_type = msg.get_metadata("type")

            # ------------------------------------------------------
            # Joint intention proposal
            # ------------------------------------------------------

            if message_type == "joint_intention_propose":
                intention_id = (
                    msg.get_metadata("intention_id")
                    or "unknown"
                )

                employee_id = (
                    msg.get_metadata("emp_id")
                    or "unknown"
                )

                goal = (
                    msg.get_metadata("goal")
                    or "unspecified"
                )

                decision = agent.decide_joint_intention(
                    intention_id=intention_id,
                    employee_id=employee_id,
                    goal=goal,
                )

                agent._ji_final_decision[
                    intention_id
                ] = decision

                agent._audit(
                    "HR_DECISION",
                    intention_id=intention_id,
                    employee_id=employee_id,
                    goal=goal,
                    decision=decision,
                )

                # ------------------------------------------
                # Outcome event
                # ------------------------------------------

                event_msg = Message(
                    to=agent.jid_outcome
                )

                event_msg.set_metadata(
                    "type",
                    "case_event",
                )

                event_msg.set_metadata(
                    "emp_id",
                    str(employee_id),
                )

                event_msg.set_metadata(
                    "source",
                    "hr",
                )

                event_msg.set_metadata(
                    "event",
                    "HR_DECISION",
                )

                event_msg.set_metadata(
                    "result_type",
                    "METRIC",
                )

                event_msg.body = json.dumps(
                    {
                        "ts": datetime.now().isoformat(
                            timespec="seconds"
                        ),
                        "emp_id": str(employee_id),
                        "intention_id": intention_id,
                        "decision": decision,
                        "goal": goal,
                    },
                    default=str,
                )

                allowed, reason = agent.is_allowed(
                    event_msg
                )

                if allowed:
                    await agent.send(
                        event_msg
                    )

                    agent.msg_out_count += 1

                else:
                    agent._audit(
                        "MESSAGE_BLOCKED",
                        to=str(event_msg.to),
                        reason=reason,
                    )

                # ------------------------------------------
                # Reply to Manager
                # ------------------------------------------

                manager_msg = Message(
                    to=f"{agent.config.base_jid}/manager"
                )

                manager_msg.set_metadata(
                    "type",
                    "joint_intention_response",
                )

                manager_msg.set_metadata(
                    "intention_id",
                    intention_id,
                )

                manager_msg.set_metadata(
                    "intent_type",
                    decision,
                )

                manager_msg.set_metadata(
                    "goal",
                    goal,
                )

                manager_msg.set_metadata(
                    "emp_id",
                    str(employee_id),
                )

                manager_msg.body = json.dumps(
                    {
                        "intention_id": intention_id,
                        "EmployeeID": employee_id,
                        "goal": goal,
                        "decision": decision,
                    },
                    default=str,
                )

                allowed, reason = agent.is_allowed(
                    manager_msg
                )

                if not allowed:
                    agent.record_inconsistency(
                        topic="SOCIAL_LAW_BLOCK",
                        description=reason,
                        parties=frozenset(
                            {
                                str(agent.jid),
                                str(manager_msg.to),
                            }
                        ),
                        context={
                            "intention_id": intention_id,
                            "employee_id": employee_id,
                            "decision": decision,
                        },
                    )
                    return

                await agent.send(
                    manager_msg
                )

                agent.msg_out_count += 1

                return

            # ------------------------------------------------------
            # Prioritized alert
            # ------------------------------------------------------

            if message_type == "attendance_pattern_alert_prioritized":
                employee_id = msg.get_metadata(
                    "emp_id"
                )

                agent._audit(
                    "PRIORITIZED_ALERT_RECEIVED",
                    employee_id=employee_id,
                    priority=msg.get_metadata(
                        "priority"
                    ),
                )

                return

    async def setup(self):
        await super().setup()

        self.add_behaviour(
            self.Inbox()
        )