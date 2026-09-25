"""Scheduled automation: detects capsules with an expired check-in window
and marks them as delivered, notifying the recipient."""
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from src.common.db import table

STATUS_ACTIVE = "ACTIVE"
STATUS_DELIVERED = "DELIVERED"

ses_client = boto3.client("ses")
SENDER = os.environ.get("NOTIFICATION_SENDER")


def _send_delivery_email(capsule: dict) -> None:
    if not SENDER:
        print(f"NOTIFICATION (no SES sender configured): capsule {capsule['id']} delivered "
              f"to {capsule['recipientEmail']}")
        return

    try:
        ses_client.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [capsule["recipientEmail"]]},
            Message={
                "Subject": {"Data": "A time capsule has been delivered to you"},
                "Body": {
                    "Text": {
                        "Data": (
                            f"A message from {capsule['ownerEmail']} has been "
                            f"delivered automatically:\n\n{capsule['message']}"
                        )
                    }
                },
            },
        )
    except ClientError as err:
        print(f"ERROR sending notification email: {err}")


def review_expirations(event, context):
    """Triggered by EventBridge on a schedule (rate(15 minutes))."""
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        result = table.query(
            IndexName="StatusNextReviewIndex",
            KeyConditionExpression="#st = :active AND nextReview <= :now",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":active": STATUS_ACTIVE, ":now": now_iso},
        )
    except ClientError as err:
        print(f"ERROR querying expired capsules: {err}")
        return

    expired_capsules = result.get("Items", [])
    print(f"Found {len(expired_capsules)} expired capsule(s) to deliver")

    for capsule in expired_capsules:
        try:
            table.update_item(
                Key={"id": capsule["id"]},
                UpdateExpression="SET #st = :delivered, deliveredAt = :now",
                ConditionExpression="#st = :active",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":delivered": STATUS_DELIVERED,
                    ":active": STATUS_ACTIVE,
                    ":now": now_iso,
                },
            )
            _send_delivery_email(capsule)
            print(f"Capsule {capsule['id']} delivered successfully")
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # already processed by another concurrent execution, skip
                continue
            print(f"ERROR delivering capsule {capsule['id']}: {err}")