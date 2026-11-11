import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    s3_endpoint_url: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    s3_prefix: str
    data_directory: str
    s3_retry_attempts: int
    db_retry_attempts: int
    db_retry_delay_seconds: float
    simulated_insert_failures: int

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://pipeline:pipeline@localhost:5432/transactions",
            ),
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"),
            s3_bucket=os.getenv("S3_BUCKET", "transactions"),
            s3_access_key=os.getenv("S3_ACCESS_KEY", "test"),
            s3_secret_key=os.getenv("S3_SECRET_KEY", "test"),
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            s3_prefix=os.getenv("S3_PREFIX", "transactions/"),
            data_directory=os.getenv("DATA_DIRECTORY", "data/generated"),
            s3_retry_attempts=int(os.getenv("S3_RETRY_ATTEMPTS", "4")),
            db_retry_attempts=int(os.getenv("DB_RETRY_ATTEMPTS", "3")),
            db_retry_delay_seconds=float(os.getenv("DB_RETRY_DELAY_SECONDS", "0.5")),
            simulated_insert_failures=int(
                os.getenv("SIMULATE_INSERT_FAILURES", "0")
            ),
        )
        if settings.s3_retry_attempts < 1 or settings.db_retry_attempts < 1:
            raise ValueError("Le nombre de tentatives doit etre superieur ou egal a 1.")
        if settings.simulated_insert_failures < 0:
            raise ValueError("SIMULATE_INSERT_FAILURES ne peut pas etre negatif.")
        return settings
