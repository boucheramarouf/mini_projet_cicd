import logging
import time
from hashlib import sha256

import psycopg

from data_pipeline.models import ProcessingResult


logger = logging.getLogger(__name__)

_SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS processed_files (
    object_key TEXT PRIMARY KEY,
    content_sha256 CHAR(64) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
""",
    """
CREATE TABLE IF NOT EXISTS transactions (
    object_key TEXT NOT NULL REFERENCES processed_files(object_key) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    transaction_datetime TIMESTAMPTZ NOT NULL,
    source_iban TEXT NOT NULL,
    source_country CHAR(2) NOT NULL,
    source_bank TEXT NOT NULL,
    destination_iban TEXT NOT NULL,
    destination_country CHAR(2) NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount >= 0),
    is_over_5000 BOOLEAN NOT NULL,
    PRIMARY KEY (object_key, row_number)
);
""",
    """
CREATE TABLE IF NOT EXISTS outgoing_by_iban (
    iban TEXT PRIMARY KEY,
    total_amount NUMERIC(18, 2) NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS outgoing_by_bank (
    bank TEXT PRIMARY KEY,
    total_amount NUMERIC(18, 2) NOT NULL
);
""",
    """
CREATE TABLE IF NOT EXISTS incoming_by_iban (
    iban TEXT PRIMARY KEY,
    total_amount NUMERIC(18, 2) NOT NULL
);
""",
)


class ProcessedFileConflictError(ValueError):
    """Un objet S3 deja traite a ete remplace par un contenu different."""


class SimulatedTransientError(Exception):
    """Erreur transitoire utilisee uniquement pour demontrer les retries."""


class Database:
    def __init__(
        self,
        database_url: str,
        retry_attempts: int = 3,
        retry_delay_seconds: float = 0.5,
    ):
        self.database_url = database_url
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            for statement in _SCHEMA:
                connection.execute(statement)

    def insert_processed_file(
        self,
        object_key: str,
        content: bytes,
        result: ProcessingResult,
        simulated_failures: int = 0,
    ) -> bool:
        if not result.transactions:
            raise ValueError("Impossible d'inserer un fichier sans transaction.")
        if simulated_failures < 0:
            raise ValueError("simulated_failures ne peut pas etre negatif.")

        checksum = sha256(content).hexdigest()
        remaining_simulated_failures = simulated_failures
        for attempt in range(1, self.retry_attempts + 1):
            try:
                if remaining_simulated_failures:
                    remaining_simulated_failures -= 1
                    raise SimulatedTransientError(
                        "Echec d'insertion simule pour tester le retry."
                    )
                return self._insert_once(object_key, checksum, result)
            except (psycopg.OperationalError, psycopg.InterfaceError, SimulatedTransientError):
                if attempt == self.retry_attempts:
                    logger.exception(
                        "Echec d'insertion de %s apres %s tentative(s).",
                        object_key,
                        attempt,
                    )
                    raise
                delay = self.retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Insertion de %s echouee (tentative %s/%s); nouvel essai dans %.2f s.",
                    object_key,
                    attempt,
                    self.retry_attempts,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("La boucle de retry s'est terminee de maniere inattendue.")

    def _insert_once(
        self, object_key: str, checksum: str, result: ProcessingResult
    ) -> bool:
        with psycopg.connect(self.database_url) as connection:
            inserted = connection.execute(
                """
                INSERT INTO processed_files (object_key, content_sha256)
                VALUES (%s, %s)
                ON CONFLICT (object_key) DO NOTHING
                RETURNING object_key
                """,
                (object_key, checksum),
            ).fetchone()

            if inserted is None:
                existing = connection.execute(
                    "SELECT content_sha256 FROM processed_files WHERE object_key = %s",
                    (object_key,),
                ).fetchone()
                if existing is None:
                    raise RuntimeError("Le fichier traite est introuvable apres conflit.")
                if existing[0].strip() != checksum:
                    raise ProcessedFileConflictError(
                        f"{object_key} a deja ete traite avec un contenu different; "
                        "utilisez une nouvelle cle S3."
                    )
                logger.info("Fichier deja traite, ignore: %s", object_key)
                return False

            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                INSERT INTO transactions (
                    object_key, row_number, transaction_datetime, source_iban,
                    source_country, source_bank, destination_iban,
                    destination_country, amount, is_over_5000
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    [
                        (
                            object_key,
                            row_number,
                            item.transaction.transaction_datetime,
                            item.transaction.source_iban,
                            item.transaction.source_country,
                            item.transaction.source_bank,
                            item.transaction.destination_iban,
                            item.transaction.destination_country,
                            item.transaction.amount,
                            item.is_over_5000,
                        )
                        for row_number, item in enumerate(result.transactions, start=1)
                    ],
                )

            for table, key_field, totals in (
                ("outgoing_by_iban", "iban", result.outgoing_by_iban),
                ("outgoing_by_bank", "bank", result.outgoing_by_bank),
                ("incoming_by_iban", "iban", result.incoming_by_iban),
            ):
                with connection.cursor() as cursor:
                    cursor.executemany(
                        f"""
                    INSERT INTO {table} ({key_field}, total_amount)
                    VALUES (%s, %s)
                    ON CONFLICT ({key_field}) DO UPDATE
                    SET total_amount = {table}.total_amount + EXCLUDED.total_amount
                    """,
                        list(totals.items()),
                    )

        logger.info(
            "Fichier insere: %s (%s transaction(s)).",
            object_key,
            len(result.transactions),
        )
        return True
