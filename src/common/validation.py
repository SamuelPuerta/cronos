"""Common validation logic for capsule payloads."""

MIN_INTERVAL_HOURS = 1
MAX_MESSAGE_LENGTH = 2000


def validate_capsule_payload(data: dict) -> str | None:
    if not data:
        return "Request body must be valid JSON"

    if not isinstance(data.get("message"), str) or not data["message"].strip():
        return '"message" is required and must be text'

    if len(data["message"]) > MAX_MESSAGE_LENGTH:
        return f'"message" must be at most {MAX_MESSAGE_LENGTH} characters'

    if not isinstance(data.get("recipientEmail"), str) or "@" not in data["recipientEmail"]:
        return '"recipientEmail" is required and must be a valid email'

    if not isinstance(data.get("ownerEmail"), str) or "@" not in data["ownerEmail"]:
        return '"ownerEmail" is required and must be a valid email'

    interval = data.get("checkInIntervalHours")
    if not isinstance(interval, (int, float)) or interval < MIN_INTERVAL_HOURS:
        return f'"checkInIntervalHours" must be a number >= {MIN_INTERVAL_HOURS}'

    return None