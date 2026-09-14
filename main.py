from __future__ import annotations

import asyncio

from src.config import load_config

from src.agents.timekeeper import TimekeeperAgent
from src.agents.behaviour_monitor import BehaviourMonitorAgent
from src.agents.priority_assessment import PriorityAssessmentAgent
from src.agents.hr_partner import HRPartnerAgent
from src.agents.manager import ManagerAgent
from src.agents.outcome_tracking import OutcomeTrackingAgent


async def main():
    config = load_config()

    timekeeper = TimekeeperAgent(
        config.jid_timekeeper,
        config.password,
        config,
    )

    behavioural = BehaviourMonitorAgent(
        config.jid_behavioral,
        config.password,
        config,
    )

    priority = PriorityAssessmentAgent(
        f"{config.base_jid}/priority",
        config.password,
        config,
    )

    hr_partner = HRPartnerAgent(
        config.jid_hrpartner,
        config.password,
        config,
    )

    manager = ManagerAgent(
        config.jid_rh,
        config.password,
        config,
    )

    outcome = OutcomeTrackingAgent(
        config.jid_outcome,
        config.password,
        config,
    )

    agents = [
        outcome,
        hr_partner,
        manager,
        priority,
        behavioural,
        timekeeper,
    ]

    try:
        for agent in agents:
            print(
                f"Starting {agent.name} "
                f"({agent.jid})..."
            )

            await agent.start(
                auto_register=True
            )

        print(
            "\nAll agents started."
        )

        print(
            f"System running for "
            f"{config.max_runtime_sec} seconds...\n"
        )

        await asyncio.sleep(
            config.max_runtime_sec
        )

    finally:
        print(
            "\nStopping agents..."
        )

        for agent in reversed(agents):
            try:
                await agent.stop()

                print(
                    f"Stopped {agent.name}"
                )

            except Exception as exc:
                print(
                    f"Error stopping "
                    f"{agent.name}: {exc}"
                )

        print(
            "\nSystem stopped."
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )