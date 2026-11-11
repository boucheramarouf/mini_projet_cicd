from io import BytesIO

from botocore.exceptions import EndpointConnectionError
import psycopg

from data_pipeline.database import Database
from data_pipeline.storage import S3Storage


def test_database_retries_a_transient_insert(monkeypatch):
    database = Database("unused", retry_attempts=3, retry_delay_seconds=0)
    calls = []

    def insert_once(*_args):
        calls.append(True)
        return True

    monkeypatch.setattr(database, "_insert_once", insert_once)
    assert database.insert_processed_file(
        "file.csv", b"content", object_with_transaction(), simulated_failures=1
    ) is True
    assert len(calls) == 1


def test_database_retries_after_database_error(monkeypatch):
    database = Database("unused", retry_attempts=3, retry_delay_seconds=0)
    calls = []

    def insert_once(*_args):
        calls.append(True)
        if len(calls) == 1:
            raise psycopg.OperationalError("temporary")
        return True

    monkeypatch.setattr(database, "_insert_once", insert_once)
    assert database.insert_processed_file(
        "file.csv", b"content", object_with_transaction()
    ) is True
    assert len(calls) == 2


def test_s3_retries_download(monkeypatch):
    storage = S3Storage.__new__(S3Storage)
    storage.bucket = "test"
    storage.retry_attempts = 3

    class Client:
        calls = 0

        def get_object(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise EndpointConnectionError(endpoint_url="http://s3")
            return {"Body": BytesIO(b"csv-content")}

    client = Client()
    storage.client = client
    monkeypatch.setattr("data_pipeline.storage.time.sleep", lambda _seconds: None)
    assert storage.download_bytes("file.csv") == b"csv-content"
    assert client.calls == 2


def object_with_transaction():
    from datetime import datetime, timezone
    from decimal import Decimal

    from data_pipeline.models import (
        ProcessedTransaction,
        ProcessingResult,
        Transaction,
    )

    transaction = Transaction(
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        "FR1",
        "FR",
        "Banque A",
        "DE1",
        "DE",
        Decimal("1.00"),
    )
    return ProcessingResult(
        (ProcessedTransaction(transaction, False),),
        {"FR1": Decimal("1.00")},
        {"Banque A": Decimal("1.00")},
        {"DE1": Decimal("1.00")},
    )
