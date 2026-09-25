"""Shared pytest fixtures.

Provides a moto-mocked DynamoDB table with the exact same schema as the real
one (partition key "id" + the StatusNextReviewIndex GSI), so the unit tests
never need real AWS credentials or a deployed table.

Note: the handlers hold the shared table object via
`from src.common.db import table`, so the fixture rebinds the `table`
reference in each module to the fresh moto-backed table.
"""
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Fake AWS credentials/environment so boto3 never looks for real ones.
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

TABLE_NAME = "cronos-capsules-test"
os.environ["CAPSULES_TABLE"] = TABLE_NAME

# Make the project root importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Same key schema, attribute definitions and GSI as the CapsulesTable
# declared in serverless.yml.
GSI_NAME = "StatusNextReviewIndex"
TABLE_DEFINITION = {
    "TableName": TABLE_NAME,
    "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
    "AttributeDefinitions": [
        {"AttributeName": "id", "AttributeType": "S"},
        {"AttributeName": "status", "AttributeType": "S"},
        {"AttributeName": "nextReview", "AttributeType": "S"},
    ],
    "GlobalSecondaryIndexes": [
        {
            "IndexName": GSI_NAME,
            "KeySchema": [
                {"AttributeName": "status", "KeyType": "HASH"},
                {"AttributeName": "nextReview", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }
    ],
    "BillingMode": "PAY_PER_REQUEST",
}


@pytest.fixture()
def capsules_table(monkeypatch):
    """A fresh, empty moto-backed DynamoDB table for each test.

    The `table` reference is rebound in both src.common.db and
    src.handlers.capsules so the handlers operate on this mocked table.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(**TABLE_DEFINITION)

        import src.common.db as db_module
        import src.handlers.capsules as capsules_module

        monkeypatch.setattr(db_module, "table", table)
        monkeypatch.setattr(capsules_module, "table", table)

        yield table
