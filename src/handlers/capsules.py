"""CRUD handlers for the Capsule entity."""
import uuid
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from src.common.db import table
from src.common.response import build_response, parse_body
from src.common.validation import validate_capsule_payload

STATUS_ACTIVE = "ACTIVE"
STATUS_DELIVERED = "DELIVERED"
STATUS_CANCELLED = "CANCELLED"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_review(interval_hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=interval_hours)).isoformat()


# CREATE - POST /capsules
def create(event, context):
    data = parse_body(event)
    error = validate_capsule_payload(data)
    if error:
        return build_response(400, {"error": error})

    now = _now_iso()
    item = {
        "id": str(uuid.uuid4()),
        "ownerEmail": data["ownerEmail"],
        "recipientEmail": data["recipientEmail"],
        "message": data["message"],
        "checkInIntervalHours": data["checkInIntervalHours"],
        "lastCheckIn": now,
        "nextReview": _next_review(data["checkInIntervalHours"]),
        "status": STATUS_ACTIVE,
        "createdAt": now,
        "deliveredAt": None,
    }

    try:
        table.put_item(Item=item)
        return build_response(201, item)
    except ClientError as err:
        print(f"ERROR creating capsule: {err}")
        return build_response(500, {"error": "Could not create the capsule"})


# READ (all) - GET /capsules
def list_capsules(event, context):
    query_params = (event.get("queryStringParameters") or {})
    limit = int(query_params.get("limit", 20))

    scan_kwargs = {"Limit": limit}

    last_key = query_params.get("lastKey")
    if last_key:
        scan_kwargs["ExclusiveStartKey"] = {"id": last_key}

    try:
        result = table.scan(**scan_kwargs)
        response_body = {
            "items": result.get("Items", []),
            "lastKey": result.get("LastEvaluatedKey", {}).get("id"),
        }
        return build_response(200, response_body)
    except ClientError as err:
        print(f"ERROR listing capsules: {err}")
        return build_response(500, {"error": "Could not list capsules"})


# READ (one) - GET /capsules/{id}
def get_capsule(event, context):
    capsule_id = event["pathParameters"]["id"]

    try:
        result = table.get_item(Key={"id": capsule_id})
        item = result.get("Item")
        if not item:
            return build_response(404, {"error": "Capsule not found"})
        return build_response(200, item)
    except ClientError as err:
        print(f"ERROR getting capsule: {err}")
        return build_response(500, {"error": "Could not retrieve the capsule"})


# UPDATE - PUT /capsules/{id}
def update_capsule(event, context):
    capsule_id = event["pathParameters"]["id"]
    data = parse_body(event)
    error = validate_capsule_payload(data)
    if error:
        return build_response(400, {"error": error})

    try:
        result = table.update_item(
            Key={"id": capsule_id},
            UpdateExpression=(
                "SET message = :message, "
                "recipientEmail = :recipientEmail, "
                "checkInIntervalHours = :interval"
            ),
            ConditionExpression="attribute_exists(id) AND #st = :active",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":message": data["message"],
                ":recipientEmail": data["recipientEmail"],
                ":interval": data["checkInIntervalHours"],
                ":active": STATUS_ACTIVE,
            },
            ReturnValues="ALL_NEW",
        )
        return build_response(200, result["Attributes"])
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return build_response(404, {"error": "Capsule not found or not active"})
        print(f"ERROR updating capsule: {err}")
        return build_response(500, {"error": "Could not update the capsule"})


# DELETE - DELETE /capsules/{id}
def delete_capsule(event, context):
    capsule_id = event["pathParameters"]["id"]

    try:
        table.delete_item(
            Key={"id": capsule_id},
            ConditionExpression="attribute_exists(id)",
        )
        return build_response(200, {"message": "Capsule deleted successfully"})
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return build_response(404, {"error": "Capsule not found"})
        print(f"ERROR deleting capsule: {err}")
        return build_response(500, {"error": "Could not delete the capsule"})


# EXTRA - PATCH /capsules/{id}/checkin
def check_in(event, context):
    capsule_id = event["pathParameters"]["id"]

    try:
        result = table.get_item(Key={"id": capsule_id})
        item = result.get("Item")
        if not item:
            return build_response(404, {"error": "Capsule not found"})

        interval_hours = item["checkInIntervalHours"]
        now = _now_iso()

        table.update_item(
            Key={"id": capsule_id},
            UpdateExpression="SET lastCheckIn = :now, nextReview = :next",
            ConditionExpression="attribute_exists(id) AND #st = :active",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":now": now,
                ":next": _next_review(float(interval_hours)),
                ":active": STATUS_ACTIVE,
            },
        )
        return build_response(200, {"message": "Check-in registered", "nextReview": _next_review(float(interval_hours))})
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return build_response(404, {"error": "Capsule not found or not active"})
        print(f"ERROR during check-in: {err}")
        return build_response(500, {"error": "Could not register check-in"})