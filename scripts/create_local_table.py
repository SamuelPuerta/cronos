"""Creates the CapsulesTable (with its GSI) in a local DynamoDB instance.

Usage:
    docker compose up -d                   # start DynamoDB Local (port 8000)
    python scripts/create_local_table.py   # create the table locally

Environment variables (all optional):
    DYNAMODB_ENDPOINT_URL  Local endpoint. Default: http://localhost:8000
    CAPSULES_TABLE         Table name. Default: cronos-capsules-dev
                           (matches the value serverless.yml injects in dev)
    AWS_DEFAULT_REGION     Any region string. Default: us-east-1
"""
import os
import sys

import boto3
from botocore.exceptions import ClientError

ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")
TABLE_NAME = os.environ.get("CAPSULES_TABLE", "cronos-capsules-dev")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def main() -> None:
    dynamodb = boto3.resource("dynamodb", region_name=REGION, endpoint_url=ENDPOINT_URL)

    try:
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "nextReview", "AttributeType": "S"},
            ],
            # Same GSI as the one declared in serverless.yml.
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "StatusNextReviewIndex",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "nextReview", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        print(f"Table '{TABLE_NAME}' created successfully on {ENDPOINT_URL}")
    except ClientError as err:
        if err.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table '{TABLE_NAME}' already exists on {ENDPOINT_URL}, nothing to do")
            sys.exit(0)
        raise

    print(f"GSI 'StatusNextReviewIndex' ready.")
    print("Tip: export DYNAMODB_ENDPOINT_URL=http://localhost:8000 before running")
    print("`serverless offline` so the handlers use this local table.")


if __name__ == "__main__":
    main()
