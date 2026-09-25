"""Shared DynamoDB client, reused across Lambda invocations."""
import os
import boto3

TABLE_NAME = os.environ.get("CAPSULES_TABLE")

# Optional endpoint override for local development (DynamoDB Local).
# If DYNAMODB_ENDPOINT_URL is not set, boto3 targets real AWS as usual.
_resource_kwargs = {}
if os.environ.get("DYNAMODB_ENDPOINT_URL"):
    _resource_kwargs["endpoint_url"] = os.environ["DYNAMODB_ENDPOINT_URL"]

_dynamodb = boto3.resource("dynamodb", **_resource_kwargs)
table = _dynamodb.Table(TABLE_NAME)