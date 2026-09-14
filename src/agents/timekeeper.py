from __future__ import annotations
import json
import pandas as pd

from spade.behaviour import OneShotBehaviour
from spade.message import Message

from src.base_agent import BaseSpecialistAgent
from src.config import Config
from src.governance import CoopPillar, SocialNorms


class TimekeeperAgent(BaseSpecialistAgent):
    """
    Reads attendance records and sends employee time data
    to the Behaviour Monitor Agent.

    This first modular version keeps data extraction isolated
    from the remaining MAS workflow.
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
            autonomy_level="low",
            communication_scope="restricted",
            communication_frequency="event_driven",
            decision_authority="inform",
            override_permission=False,
            accountability_level="high",
            audit_required=True,
            collaboration_mode="cooperative",
            conflict_resolution_style="escalation",
            human_in_the_loop=False,
            fairness_constraint="required",
            time_sensitivity="medium",
            cooldown_required=False,
        )

        super().__init__(
            jid,
            password,
            config,
            name="TimekeeperAgent",
            pillars=frozenset(
                {
                    CoopPillar.TASK_SHARING,
                    CoopPillar.RESULT_SHARING,
                    CoopPillar.SOCIAL_NORMS,
                }
            ),
            norms=norms,
        )

    def load_attendance_data(self) -> pd.DataFrame:
        """
        Load attendance records from the configured Excel sheet.
        """

        df = pd.read_excel(
            self.config.excel_path,
            sheet_name=self.config.excel_sheet,
        )

        required_columns = {
            "EmployeeID",
            "Data",
            "Entrada",
            "Saida",
        }

        missing = required_columns - set(df.columns)

        if missing:
            raise ValueError(
                "Attendance dataset is missing required columns: "
                + ", ".join(sorted(missing))
            )

        return df

    def employee_records(
        self,
        df: pd.DataFrame,
        employee_id,
    ) -> list[dict]:
        """
        Return attendance records for one employee.
        """

        subset = df[
            df["EmployeeID"].astype(str)
            == str(employee_id)
        ].copy()

        subset = subset.sort_values("Data")

        return subset[
            [
                "EmployeeID",
                "Data",
                "Entrada",
                "Saida",
            ]
        ].to_dict(
            orient="records"
        )

    class SendAttendanceBehaviour(OneShotBehaviour):
        async def run(self):
            agent: TimekeeperAgent = self.agent

            df = agent.load_attendance_data()

            employee_ids = (
                df["EmployeeID"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            employee_ids = employee_ids[
                : agent.config.max_funcionarios
            ]

            for employee_id in employee_ids:
                records = agent.employee_records(
                    df,
                    employee_id,
                )

                msg = Message(
                    to=agent.jid_behavioral
                )

                msg.set_metadata(
                    "type",
                    "emp_times",
                )

                msg.body = json.dumps(
                    {
                        "EmployeeID": employee_id,
                        "records": records,
                    },
                    default=str,
                )

                allowed, reason = agent.is_allowed(
                    msg
                )

                if not allowed:
                    agent._audit(
                        "MESSAGE_BLOCKED",
                        to=str(msg.to),
                        reason=reason,
                    )
                    continue

                await agent.send(msg)

                agent.msg_out_count += 1

                agent._audit(
                    "ATTENDANCE_SENT",
                    employee_id=employee_id,
                    records=len(records),
                )

    async def setup(self):
        await super().setup()

        self.add_behaviour(
            self.SendAttendanceBehaviour()
        )