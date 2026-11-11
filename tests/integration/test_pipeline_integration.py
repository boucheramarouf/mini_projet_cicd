from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest

from data_pipeline.config import Settings
from data_pipeline.database import Database, ProcessedFileConflictError
from data_pipeline.pipeline import process_object
from data_pipeline.storage import S3Storage


def test_s3_to_postgres_ingestion_is_correct_and_idempotent():
    settings = Settings.from_env()
    storage = S3Storage(settings)
    database = Database(settings.database_url, retry_delay_seconds=0)
    storage.ensure_bucket()
    database.create_schema()

    test_id = str(uuid4())
    key = f"integration/{test_id}.csv"
    source_iban = f"FR-TEST-{test_id}"
    destination_iban = f"DE-TEST-{test_id}"
    source_bank = f"Banque Test {test_id}"
    content = (
        "transaction_datetime,source_iban,source_country,source_bank,"
        "destination_iban,destination_country,amount\n"
        f"2025-01-01T10:00:00+00:00,{source_iban},FR,{source_bank},"
        f"{destination_iban},DE,6000.00\n"
        f"2025-01-01T11:00:00+00:00,{source_iban},FR,{source_bank},"
        f"{destination_iban},DE,25.50\n"
    ).encode("utf-8")
    storage.upload_bytes(key, content)

    try:
        assert process_object(key, storage, database) is True
        assert process_object(key, storage, database) is False
        storage.upload_bytes(key, content + b"\n")
        with pytest.raises(ProcessedFileConflictError, match="contenu different"):
            process_object(key, storage, database)
        with psycopg.connect(settings.database_url) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM transactions WHERE object_key = %s", (key,)
            ).fetchone()[0] == 2
            assert connection.execute(
                "SELECT amount, is_over_5000 FROM transactions "
                "WHERE object_key = %s ORDER BY row_number",
                (key,),
            ).fetchall() == [
                (Decimal("6000.00"), True),
                (Decimal("25.50"), False),
            ]
            assert connection.execute(
                "SELECT total_amount FROM outgoing_by_iban WHERE iban = %s",
                (source_iban,),
            ).fetchone()[0] == Decimal("6025.50")
            assert connection.execute(
                "SELECT total_amount FROM outgoing_by_bank WHERE bank = %s",
                (source_bank,),
            ).fetchone()[0] == Decimal("6025.50")
            assert connection.execute(
                "SELECT total_amount FROM incoming_by_iban WHERE iban = %s",
                (destination_iban,),
            ).fetchone()[0] == Decimal("6025.50")
    finally:
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("DELETE FROM processed_files WHERE object_key = %s", (key,))
            connection.execute("DELETE FROM outgoing_by_iban WHERE iban = %s", (source_iban,))
            connection.execute("DELETE FROM outgoing_by_bank WHERE bank = %s", (source_bank,))
            connection.execute("DELETE FROM incoming_by_iban WHERE iban = %s", (destination_iban,))
        storage.delete_object(key)
