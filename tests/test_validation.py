"""Unit tests for src.common.validation.validate_capsule_payload."""
from src.common.validation import MAX_MESSAGE_LENGTH, validate_capsule_payload


def _valid_payload():
    return {
        "message": "See you in the future",
        "recipientEmail": "recipient@example.com",
        "ownerEmail": "owner@example.com",
        "checkInIntervalHours": 24,
    }


def test_valid_payload_returns_none():
    assert validate_capsule_payload(_valid_payload()) is None


def test_none_body_is_rejected():
    error = validate_capsule_payload(None)
    assert error is not None
    assert "JSON" in error


def test_missing_message_is_rejected():
    payload = _valid_payload()
    del payload["message"]
    assert '"message"' in validate_capsule_payload(payload)


def test_blank_message_is_rejected():
    payload = _valid_payload()
    payload["message"] = "   "
    assert validate_capsule_payload(payload) is not None


def test_too_long_message_is_rejected():
    payload = _valid_payload()
    payload["message"] = "x" * (MAX_MESSAGE_LENGTH + 1)
    error = validate_capsule_payload(payload)
    assert str(MAX_MESSAGE_LENGTH) in error


def test_invalid_recipient_email_is_rejected():
    payload = _valid_payload()
    payload["recipientEmail"] = "not-an-email"
    assert "recipientEmail" in validate_capsule_payload(payload)


def test_invalid_owner_email_is_rejected():
    payload = _valid_payload()
    payload["ownerEmail"] = "owner-without-at-sign"
    assert "ownerEmail" in validate_capsule_payload(payload)


def test_zero_and_negative_interval_are_rejected():
    for invalid_interval in (0, -5):
        payload = _valid_payload()
        payload["checkInIntervalHours"] = invalid_interval
        assert "checkInIntervalHours" in validate_capsule_payload(payload)


def test_non_numeric_interval_is_rejected():
    payload = _valid_payload()
    payload["checkInIntervalHours"] = "24"
    assert validate_capsule_payload(payload) is not None


def test_boolean_interval_is_rejected():
    """bool is a subclass of int in Python (True == 1); it must not be
    accepted as a valid checkInIntervalHours."""
    for invalid_interval in (True, False):
        payload = _valid_payload()
        payload["checkInIntervalHours"] = invalid_interval
        assert "checkInIntervalHours" in validate_capsule_payload(payload)
