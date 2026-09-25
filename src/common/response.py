"""Helper to build consistent HTTP responses."""
import json
import decimal


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB returns Decimal types; convert them to int/float for JSON."""

    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def parse_body(event: dict):
    try:
        return json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None