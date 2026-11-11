import logging
from io import StringIO
from pathlib import Path

from data_pipeline.config import Settings
from data_pipeline.csv_io import load_transactions
from data_pipeline.database import Database
from data_pipeline.generate import generate_csv_files
from data_pipeline.storage import S3Storage
from data_pipeline.transform import process_transactions


logger = logging.getLogger(__name__)


def process_object(
    key: str,
    storage: S3Storage,
    database: Database,
    simulated_failures: int = 0,
    simulate_processing_failure: bool = False,
) -> bool:
    content = storage.download_bytes(key)
    transactions = load_transactions(StringIO(content.decode("utf-8-sig")))
    result = process_transactions(transactions)
    if simulate_processing_failure:
        raise RuntimeError("Echec de traitement volontaire (demo).")
    return database.insert_processed_file(
        key,
        content,
        result,
        simulated_failures=simulated_failures,
    )


def run_pipeline(
    settings: Settings,
    generate: bool = False,
    simulate_processing_failure: bool = False,
) -> None:
    storage = S3Storage(settings)
    database = Database(
        settings.database_url,
        retry_attempts=settings.db_retry_attempts,
        retry_delay_seconds=settings.db_retry_delay_seconds,
    )
    storage.ensure_bucket()
    database.create_schema()

    if generate:
        generated_files = generate_csv_files(settings.data_directory)
        for path in generated_files:
            storage.upload_bytes(
                f"{settings.s3_prefix}{path.name}",
                path.read_bytes(),
            )
        logger.info("%s fichier(s) genere(s) puis envoye(s) sur S3.", len(generated_files))

    keys = storage.list_keys(settings.s3_prefix)
    if not keys:
        raise FileNotFoundError(
            f"Aucun fichier CSV trouve sur S3 sous le prefixe {settings.s3_prefix!r}."
        )

    for index, key in enumerate(keys):
        process_object(
            key,
            storage,
            database,
            simulated_failures=(
                settings.simulated_insert_failures if index == 0 else 0
            ),
            simulate_processing_failure=(
                simulate_processing_failure and index == 0
            ),
        )
    logger.info("Pipeline terminee: %s objet(s) examine(s).", len(keys))
