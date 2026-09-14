from __future__ import annotations

from spade.message import Message


KNOWN_ROLES = {
    "timekeeper",
    "behavioral",
    "priority",
    "hr",
    "manager",
    "outcome",
    "rh",
}


SOCIAL_LAW = {
    "timekeeper": {
        "behavioral": {
            "emp_times",
            "attendance_batch_ready",
        },
        "outcome": {
            "inconsistency_record",
            "metric_snapshot",
            "case_event",
        },
    },

    "behavioral": {
        "priority": {
            "attendance_pattern_alert",
        },
        "timekeeper": {
            "attendance_batch_ack",
        },
        "outcome": {
            "inconsistency_record",
            "metric_snapshot",
            "case_event",
        },
    },

    "priority": {
        "hr": {
            "attendance_pattern_alert_prioritized",
        },
        "manager": {
            "attendance_pattern_alert_manager",
        },
        "outcome": {
            "inconsistency_record",
            "metric_snapshot",
            "case_event",
        },
    },

    "hr": {
        "manager": {
            "joint_intention_response",
        },
        "outcome": {
            "inconsistency_record",
            "metric_snapshot",
            "case_event",
        },
    },

    "manager": {    
        "hr": {
            "joint_intention_propose",
        },
        "outcome": {
            "inconsistency_record",
            "metric_snapshot",
            "case_event",
        },
    },
}



def role_from_jid(jid: str) -> str:
    """
    Extract the organizational role from the XMPP JID resource.

    Example:
        user@example.com/behavioral -> behavioral
    """
    value = str(jid)

    if "/" not in value:
        return "unknown"

    return value.split("/", 1)[1].strip().lower()


def message_type(msg: Message) -> str:
    try:
        return (msg.get_metadata("type") or "").strip()
    except Exception:
        return ""


def is_allowed_send(
    *,
    sender_jid: str,
    receiver_jid: str,
    msg: Message,
) -> tuple[bool, str]:
    """
    Enforce Social Law constraints.

    Rules:
    - the sender/receiver route must exist;
    - the message type must be explicitly permitted;
    - Priority -> Manager is allowed only for HIGH priority alerts.
    """

    sender_role = role_from_jid(sender_jid)
    receiver_role = role_from_jid(receiver_jid)
    msg_type = message_type(msg)

    allowed_types = SOCIAL_LAW.get(
        sender_role,
        {},
    ).get(
        receiver_role,
        set(),
    )

    if not allowed_types:
        return (
            False,
            f"Route blocked: {sender_role} -> "
            f"{receiver_role} (type={msg_type})",
        )

    if msg_type not in allowed_types:
        return (
            False,
            f"Message type blocked on route "
            f"{sender_role}->{receiver_role}: "
            f"type={msg_type}",
        )

    if (
        sender_role == "priority"
        and receiver_role == "manager"
    ):
        priority = (
            msg.get_metadata("priority") or ""
        ).strip().upper()

        if priority != "HIGH":
            return (
                False,
                "Manager receives only HIGH priority alerts. "
                f"priority={priority or 'EMPTY'}",
            )

    return True, "OK"