from __future__ import annotations

import json
from datetime import datetime

from spade.behaviour import CyclicBehaviour
from spade.message import Message

from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import (
    CoopPillar,
    IntentType,
    SocialNorms,
)


class ManagerAgent(BaseSpecialistAgent):
    """
    Manager Agent.

    Responsibilities:
    - receive HIGH-priority alerts;
    - create a Joint Intention;
    - request HR validation;
    - execute an action only after HR returns AGREE;
    - report the executed action to Outcome Tracking.
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
            autonomy_level="high",
            communication_scope="mediated",
            communication_frequency="on_demand",
            decision_authority="approve",
            override_permission=False,
            accountability_level="shared",
            audit_required=True,
            collaboration_mode="joint_intention",
            conflict_resolution_style="negotiate",
            human_in_the_loop=True,
            fairness_constraint="strict",
            time_sensitivity="medium",
            cooldown_required=True,
        )

        super().__init__(
            jid,
            password,
            config,
            name="ManagerAgent",
            pillars=frozenset(
                {
                    CoopPillar.JOINT_INTENTIONS,
                    CoopPillar.HANDLING_INCONSISTENCY,
                    CoopPillar.SOCIAL_NORMS,
                    CoopPillar.RESULT_SHARING,
                }
            ),
            norms=norms,
        )

    # --------------------------------------------------------------
    # Decision rule
    # --------------------------------------------------------------

    @staticmethod
    def should_execute_action(decision: str) -> bool:
        """
        Sensitive actions are executed only after explicit HR approval.
        """
        return (decision or "").strip().upper() == "AGREE"

    # --------------------------------------------------------------
    # Behaviour
    # --------------------------------------------------------------

    class Inbox(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)

            if msg is None:
                return

            agent: ManagerAgent = self.agent

            agent.msg_in_count += 1

            message_type = msg.get_metadata("type")

            # ------------------------------------------------------
            # HIGH-priority alert from Priority Assessment
            # ------------------------------------------------------

            if message_type == "attendance_pattern_alert_manager":
                priority = (
                    msg.get_metadata("priority") or ""
                ).strip().upper()

                employee_id = (
                    msg.get_metadata("emp_id")
                    or "unknown"
                )

                if priority != "HIGH":
                    agent._audit(
                        "MANAGER_ALERT_REJECTED",
                        employee_id=employee_id,
                        reason="Manager accepts only HIGH priority alerts.",
                        priority=priority,
                    )
                    return

                goal = (
                    "Human review of the behavioral attendance "
                    "signal before any employee-facing action"
                )

                joint_intention = agent.create_joint_intention(
                    intent_type=IntentType.PROPOSE,
                    goal=goal,
                    owner=str(agent.jid),
                    participants=frozenset(
                        {
                            str(agent.jid),
                            agent.jid_hrpartner,
                        }
                    ),
                    emp_id=str(employee_id),
                )

                proposal = Message(
                    to=agent.jid_hrpartner
                )

                proposal.set_metadata(
                    "performative",
                    "propose",
                )

                proposal.set_metadata(
                    "type",
                    "joint_intention_propose",
                )

                proposal.set_metadata(
                    "intention_id",
                    joint_intention.intention_id,
                )

                proposal.set_metadata(
                    "emp_id",
                    str(employee_id),
                )

                proposal.set_metadata(
                    "goal",
                    goal,
                )

                proposal.body = json.dumps(
                    {
                        "intention_id": joint_intention.intention_id,
                        "EmployeeID": employee_id,
                        "goal": goal,
                        "priority": priority,
                    },
                    default=str,
                )

                allowed, reason = agent.is_allowed(
                    proposal
                )

                if not allowed:
                    agent.record_inconsistency(
                        topic="SOCIAL_LAW_BLOCK",
                        description=reason,
                        parties=frozenset(
                            {
                                str(agent.jid),
                                str(proposal.to),
                            }
                        ),
                        context={
                            "employee_id": employee_id,
                            "intention_id": (
                                joint_intention.intention_id
                            ),
                        },
                    )
                    return

                await agent.send(
                    proposal
                )

                agent.msg_out_count += 1

                agent._audit(
                    "JOINT_INTENTION_PROPOSED",
                    employee_id=employee_id,
                    intention_id=joint_intention.intention_id,
                    goal=goal,
                )

                return

            # ------------------------------------------------------
            # HR response to Joint Intention
            # ------------------------------------------------------

            if message_type == "joint_intention_response":
                decision = (
                    msg.get_metadata("intent_type")
                    or ""
                ).strip().upper()

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

                agent._ji_final_decision[
                    intention_id
                ] = decision

                agent._audit(
                    "JOINT_INTENTION_RESPONSE_RECEIVED",
                    intention_id=intention_id,
                    employee_id=employee_id,
                    decision=decision,
                )

                if not agent.should_execute_action(
                    decision
                ):
                    agent._audit(
                        "ACTION_NOT_EXECUTED",
                        intention_id=intention_id,
                        employee_id=employee_id,
                        decision=decision,
                    )
                    return

                # Human-authorized action
                agent._audit(
                    "ACTION_EXECUTED",
                    intention_id=intention_id,
                    employee_id=employee_id,
                    goal=goal,
                )

                event_msg = Message(
                    to=agent.jid_outcome
                )

                event_msg.set_metadata(
                    "performative",
                    "inform",
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
                    "manager",
                )

                event_msg.set_metadata(
                    "event",
                    "ACTION_EXECUTED",
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
                        "goal": goal,
                        "action_executed": True,
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

                return

    async def setup(self):
        await super().setup()

        self.add_behaviour(
            self.Inbox()
        )