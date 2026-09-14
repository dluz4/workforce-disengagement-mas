from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_jid: str
    password: str

    jid_rh: str
    jid_behavioral: str
    jid_timekeeper: str
    jid_hrpartner: str
    jid_outcome: str

    excel_path: str
    excel_sheet: str = "Registros"
    sheet_funcionarios: str = "Funcionarios"

    max_funcionarios: int = 10
    max_runtime_sec: int = 45
    baseline_days: int = 30
    variation_alert: int = 30


def load_config() -> Config:
    env = os.environ

    required = (
        "XMPP_BASE_JID",
        "XMPP_PASSWORD",
        "EXCEL_PATH",
        "OPENAI_API_KEY",
    )

    for key in required:
        if not env.get(key):
            raise RuntimeError(f"{key} not defined.")

    base = env["XMPP_BASE_JID"]

    return Config(
        base_jid=base,
        password=env["XMPP_PASSWORD"],
        jid_rh=f"{base}/rh",
        jid_behavioral=f"{base}/behavioral",
        jid_timekeeper=f"{base}/timekeeper",
        jid_hrpartner=f"{base}/hr",
        jid_outcome=f"{base}/outcome",
        excel_path=env["EXCEL_PATH"],
        excel_sheet=env.get("EXCEL_SHEET", "Registros"),
        sheet_funcionarios=env.get("SHEET_FUNCIONARIOS", "Funcionarios"),
        max_funcionarios=int(env.get("MAX_FUNCIONARIOS", 10)),
        max_runtime_sec=int(env.get("MAX_RUNTIME_SEC", 45)),
        baseline_days=int(env.get("BASELINE_DAYS", 30)),
        variation_alert=int(env.get("VARIATION_ALERT", 30)),
    )