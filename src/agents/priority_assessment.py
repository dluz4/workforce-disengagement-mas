from __future__ import annotations

import asyncio
import json
import os

import pandas as pd

from openai import OpenAI
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import CoopPillar, SocialNorms


class PriorityAssessmentAgent(BaseSpecialistAgent):
    """
    Assesses the organizational priority of an attendance alert.

    Current prototype rule:
    - managerial position -> HIGH
    - non-managerial position -> NORMAL

    An LLM may generate a human-readable explanation,
    but it does not determine the priority itself.
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
            decision_authority="recommend",
            override_permission=False,
            accountability_level="high",
            audit_required=True,
            collaboration_mode="cooperative",
            conflict_resolution_style="escalation",
            human_in_the_loop=True,
            fairness_constraint="required",
            time_sensitivity="high",
            cooldown_required=False,
        )

        super().__init__(
            jid,
            password,
            config,
            name="PriorityAssessmentAgent",
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

        self._pos_map: dict[str, str] = {}

    # --------------------------------------------------------------
    # Priority rule
    # --------------------------------------------------------------

    @staticmethod
    def classify_priority(
        managerial_position: str,
    ) -> str:
        """
        Apply the deterministic priority rule.

        The LLM is not involved in this classification.
        """

        position = str(
            managerial_position
        ).strip().lower()

        if position == "gerente":
            return "HIGH"

        return "NORMAL"

    # --------------------------------------------------------------
    # Employee organizational data
    # --------------------------------------------------------------

    def load_position_map(self) -> dict[str, str]:
        """
        Read EmployeeID -> PosGerencial from the employee sheet.
        """

        df = pd.read_excel(
            self.config.excel_path,
            sheet_name=self.config.sheet_funcionarios,
        )

        required_columns = {
            "EmployeeID",
            "PosGerencial",
        }

        missing = required_columns - set(df.columns)

        if missing:
            raise ValueError(
                "Employee dataset is missing required columns: "
                + ", ".join(sorted(missing))
            )

        df = df[
            [
                "EmployeeID",
                "PosGerencial",
            ]
        ].dropna()

        df["EmployeeID"] = (
            df["EmployeeID"]
            .astype(str)
            .str.strip()
        )

        df["PosGerencial"] = (
            df["PosGerencial"]
            .astype(str)
            .str.strip()
        )

        # Preserve prototype behavior:
        # the last occurrence wins when duplicate IDs exist.
        df = df.drop_duplicates(
            subset=["EmployeeID"],
            keep="last",
        )

        return dict(
            zip(
                df["EmployeeID"],
                df["PosGerencial"],
            )
        )

    def employee_position(
        self,
        employee_id: str,
    ) -> str:
        return self._pos_map.get(
            str(employee_id),
            "NaoGerente",
        )

    # --------------------------------------------------------------
    # LLM explanation
    # --------------------------------------------------------------

    def build_llm_prompt(
        self,
        employee_id: str,
        managerial_position: str,
        priority_level: str,
        raw_alert: str,
    ) -> str:
        return (
            "You are an HR support agent.\n"
            "Transform a technical attendance alert into a short, "
            "clear and fair explanation for an HR Partner.\n\n"
            "Rules:\n"
            "- Do not accuse the employee.\n"
            "- Do not diagnose disengagement or a health condition.\n"
            "- Describe the information as a behavioral signal "
            "requiring contextual validation.\n"
            "- Recommend human review and validation.\n"
            "- If extra working hours are present, they may be "
            "described as a potential workload or wellbeing signal, "
            "not as a diagnosis.\n"
            "- Be concise.\n\n"
            f"EmployeeID={employee_id}\n"
            f"ManagerialPosition={managerial_position}\n"
            f"Priority={priority_level}\n\n"
            "TECHNICAL ALERT:\n"
            f"{raw_alert}\n\n"
            "Write the message for the HR Partner."
        )

    async def openai_enrich(
        self,
        *,
        employee_id: str,
        managerial_position: str,
        priority_level: str,
        raw_alert: str,
    ) -> str | None:

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            return None

        prompt = self.build_llm_prompt(
            employee_id=employee_id,
            managerial_position=managerial_position,
            priority_level=priority_level,
            raw_alert=raw_alert,
        )

        def call_openai() -> str:
            client = OpenAI(
                api_key=api_key
            )

            response = client.responses.create(
                model="gpt-4o-mini",
                temperature=0.7,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are an HR support agent "
                            "that writes concise and fair messages."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            return response.output_text.strip()

        try:
            return await asyncio.to_thread(
                call_openai
            )
        except Exception as exc:
            self._audit(
                "LLM_ERROR",
                error=str(exc),
            )
            return None

    # --------------------------------------------------------------
    # Message processing
    # --------------------------------------------------------------

    class Inbox(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(
                timeout=5
            )

            if msg is None:
                return

            agent: PriorityAssessmentAgent = self.agent

            if (
                msg.get_metadata("type")
                != "attendance_pattern_alert"
            ):
                return

            agent.msg_in_count += 1

            try:
                payload = json.loads(
                    msg.body
                )

                employee_id = str(
                    payload["EmployeeID"]
                )

            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
            ) as exc:

                agent.record_inconsistency(
                    topic="invalid_priority_payload",
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

            position = agent.employee_position(
                employee_id
            )

            priority = agent.classify_priority(
                position
            )

            explanation = await agent.openai_enrich(
                employee_id=employee_id,
                managerial_position=position,
                priority_level=priority,
                raw_alert=msg.body,
            )

            if explanation is None:
                explanation = (
                    "Attendance deviation detected. "
                    "Human contextual review is recommended."
                )

            # ------------------------------------------
            # Send to HR Partner
            # ------------------------------------------

            hr_msg = Message(
                to=agent.jid_hrpartner
            )

            hr_msg.set_metadata(
                "type",
                "attendance_pattern_alert_prioritized",
            )

            hr_msg.set_metadata(
                "emp_id",
                employee_id,
            )

            hr_msg.set_metadata(
                "priority",
                priority,
            )

            hr_msg.set_metadata(
                "posgerencial",
                position,
            )

            hr_msg.body = json.dumps(
                {
                    "EmployeeID": employee_id,
                    "priority": priority,
                    "posgerencial": position,
                    "explanation": explanation,
                    "source_alert": payload,
                },
                default=str,
            )

            allowed, reason = agent.is_allowed(
                hr_msg
            )

            if allowed:
                await agent.send(
                    hr_msg
                )

                agent.msg_out_count += 1

            else:
                agent.record_inconsistency(
                    topic="SOCIAL_LAW_BLOCK",
                    description=reason,
                    parties=frozenset(
                        {
                            str(agent.jid),
                            str(hr_msg.to),
                        }
                    ),
                    context={
                        "EmployeeID": employee_id,
                        "priority": priority,
                    },
                )
                return

            # ------------------------------------------
            # HIGH priority also informs Manager
            # ------------------------------------------

            if priority == "HIGH":
                manager_msg = Message(
                    to=f"{agent.config.base_jid}/manager"
                )

                manager_msg.set_metadata(
                    "type",
                    "attendance_pattern_alert_manager",
                )

                manager_msg.set_metadata(
                    "emp_id",
                    employee_id,
                )

                manager_msg.set_metadata(
                    "priority",
                    "HIGH",
                )

                manager_msg.body = json.dumps(
                    {
                        "EmployeeID": employee_id,
                        "priority": "HIGH",
                        "explanation": explanation,
                    },
                    default=str,
                )

                allowed, reason = agent.is_allowed(
                    manager_msg
                )

                if allowed:
                    await agent.send(
                        manager_msg
                    )

                    agent.msg_out_count += 1

                else:
                    agent.record_inconsistency(
                        topic="POLICY_BLOCK_ESCALATION",
                        description=reason,
                        parties=frozenset(
                            {
                                str(agent.jid),
                                str(manager_msg.to),
                            }
                        ),
                        context={
                            "EmployeeID": employee_id,
                            "priority": "HIGH",
                        },
                    )

            agent._audit(
                "PRIORITY_ASSIGNED",
                employee_id=employee_id,
                position=position,
                priority=priority,
            )

    async def setup(self):
        await super().setup()

        self._pos_map = self.load_position_map()

        self.add_behaviour(
            self.Inbox()
        )