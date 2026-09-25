"""Unit tests for the capsule handlers (src/handlers/capsules.py).

All tests run against a moto-mocked DynamoDB table (see conftest.py),
so no real AWS credentials or deployed resources are needed.
"""
import json
from datetime import datetime, timedelta, timezone

from src.handlers import capsules


def _body(response: dict) -> dict:
    return json.loads(response["body"])


def _valid_payload():
    return {
        "message": "Open when I am gone",
        "recipientEmail": "recipient@example.com",
        "ownerEmail": "owner@example.com",
        "checkInIntervalHours": 24,
    }


def _create_capsule():
    """Create a capsule through the real handler and return (response, id)."""
    response = capsules.create({"body": json.dumps(_valid_payload())}, None)
    return response, _body(response)["id"]


# CREATE ------------------------------------------------------------------


def test_create_with_valid_payload_returns_201(capsules_table):
    response, capsule_id = _create_capsule()

    assert response["statusCode"] == 201
    body = _body(response)
    assert body["id"] == capsule_id
    assert body["status"] == "ACTIVE"
    assert body["message"] == _valid_payload()["message"]
    assert body["nextReview"] > body["lastCheckIn"]


def test_create_with_invalid_payload_returns_400(capsules_table):
    payload = _valid_payload()
    del payload["message"]

    response = capsules.create({"body": json.dumps(payload)}, None)

    assert response["statusCode"] == 400
    assert "error" in _body(response)


def test_create_with_empty_body_returns_400(capsules_table):
    response = capsules.create({"body": None}, None)

    assert response["statusCode"] == 400
    assert "error" in _body(response)


# READ --------------------------------------------------------------------


def test_get_capsule_returns_created_item(capsules_table):
    _, capsule_id = _create_capsule()

    response = capsules.get_capsule({"pathParameters": {"id": capsule_id}}, None)

    assert response["statusCode"] == 200
    assert _body(response)["id"] == capsule_id


def test_get_capsule_with_unknown_id_returns_404(capsules_table):
    response = capsules.get_capsule(
        {"pathParameters": {"id": "non-existent-id"}}, None
    )

    assert response["statusCode"] == 404
    assert _body(response)["error"] == "Capsule not found"


def test_list_capsules_returns_created_items(capsules_table):
    _create_capsule()

    response = capsules.list_capsules({"queryStringParameters": None}, None)

    assert response["statusCode"] == 200
    assert len(_body(response)["items"]) == 1


def test_list_capsules_with_invalid_limit_returns_400(capsules_table):
    for bad_limit in ("abc", "-3", "2.5.1"):
        response = capsules.list_capsules(
            {"queryStringParameters": {"limit": bad_limit}}, None
        )
        assert response["statusCode"] == 400
        assert "limit" in _body(response)["error"]


# UPDATE ------------------------------------------------------------------


def test_update_existing_capsule_returns_200(capsules_table):
    _, capsule_id = _create_capsule()
    payload = _valid_payload()
    payload["message"] = "updated message"

    response = capsules.update_capsule(
        {"pathParameters": {"id": capsule_id}, "body": json.dumps(payload)}, None
    )

    assert response["statusCode"] == 200
    assert _body(response)["message"] == "updated message"


def test_update_nonexistent_capsule_returns_404(capsules_table):
    response = capsules.update_capsule(
        {
            "pathParameters": {"id": "non-existent-id"},
            "body": json.dumps(_valid_payload()),
        },
        None,
    )

    assert response["statusCode"] == 404
    assert "error" in _body(response)


# DELETE ------------------------------------------------------------------


def test_delete_existing_capsule_returns_200(capsules_table):
    _, capsule_id = _create_capsule()

    response = capsules.delete_capsule({"pathParameters": {"id": capsule_id}}, None)

    assert response["statusCode"] == 200
    # The item is actually gone from the table.
    assert capsules_table.get_item(Key={"id": capsule_id}).get("Item") is None


def test_delete_nonexistent_capsule_returns_404(capsules_table):
    """The ConditionExpression attribute_exists(id) turns a delete of a
    missing item into a ConditionalCheckFailedException -> 404."""
    response = capsules.delete_capsule(
        {"pathParameters": {"id": "non-existent-id"}}, None
    )

    assert response["statusCode"] == 404
    assert _body(response)["error"] == "Capsule not found"


# CHECK-IN ----------------------------------------------------------------


def test_check_in_updates_last_check_in_and_next_review(capsules_table):
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    capsule_id = "capsule-for-check-in"
    capsules_table.put_item(
        Item={
            "id": capsule_id,
            "ownerEmail": "owner@example.com",
            "recipientEmail": "recipient@example.com",
            "message": "hello future",
            "checkInIntervalHours": 24,
            "lastCheckIn": three_days_ago.isoformat(),
            "nextReview": three_days_ago.isoformat(),
            "status": "ACTIVE",
            "createdAt": three_days_ago.isoformat(),
            "deliveredAt": None,
        }
    )
    previous = capsules_table.get_item(Key={"id": capsule_id})["Item"]

    response = capsules.check_in({"pathParameters": {"id": capsule_id}}, None)

    assert response["statusCode"] == 200
    body = _body(response)
    assert body["message"] == "Check-in registered"

    updated = capsules_table.get_item(Key={"id": capsule_id})["Item"]
    assert updated["lastCheckIn"] != previous["lastCheckIn"]
    assert updated["nextReview"] != previous["nextReview"]
    # nextReview must now be roughly checkInIntervalHours in the future.
    next_review = datetime.fromisoformat(updated["nextReview"])
    assert next_review > datetime.now(timezone.utc) + timedelta(hours=23)


def test_check_in_with_unknown_id_returns_404(capsules_table):
    response = capsules.check_in(
        {"pathParameters": {"id": "non-existent-id"}}, None
    )

    assert response["statusCode"] == 404
    assert _body(response)["error"] == "Capsule not found"


# SEARCH ------------------------------------------------------------------


def test_search_by_status_returns_only_matching_capsules(capsules_table):
    _, capsule_id = _create_capsule()

    response = capsules.search_capsules(
        {"queryStringParameters": {"status": "ACTIVE"}}, None
    )

    assert response["statusCode"] == 200
    body = _body(response)
    assert body["count"] == 1
    assert body["items"][0]["id"] == capsule_id

    response = capsules.search_capsules(
        {"queryStringParameters": {"status": "DELIVERED"}}, None
    )
    assert _body(response)["count"] == 0


def test_search_without_status_returns_400(capsules_table):
    for event in ({"queryStringParameters": {}}, {"queryStringParameters": None}, {}):
        response = capsules.search_capsules(event, None)
        assert response["statusCode"] == 400
        assert "status" in _body(response)["error"]


def test_search_with_invalid_status_returns_400(capsules_table):
    response = capsules.search_capsules(
        {"queryStringParameters": {"status": "WHATEVER"}}, None
    )

    assert response["statusCode"] == 400
    assert "error" in _body(response)


# DEFENSIVE PATH PARAMETER HANDLING ---------------------------------------


def test_missing_path_parameter_returns_400_in_all_id_handlers(capsules_table):
    for handler in (
        capsules.get_capsule,
        capsules.update_capsule,
        capsules.delete_capsule,
        capsules.check_in,
    ):
        response = handler({"pathParameters": None}, None)
        assert response["statusCode"] == 400
        assert _body(response)["error"] == "Missing path parameter: id"
