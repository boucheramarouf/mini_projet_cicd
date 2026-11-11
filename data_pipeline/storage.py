import logging
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from data_pipeline.config import Settings


logger = logging.getLogger(__name__)


class S3Storage:
    def __init__(self, settings: Settings):
        self.bucket = settings.s3_bucket
        self.retry_attempts = settings.s3_retry_attempts
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                retries={"max_attempts": 1, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )

    def _retry(self, operation_name, operation):
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return operation()
            except (BotoCoreError, ClientError):
                if attempt == self.retry_attempts:
                    logger.exception(
                        "Echec de %s apres %s tentative(s).",
                        operation_name,
                        attempt,
                    )
                    raise
                delay = min(0.25 * (2 ** (attempt - 1)), 2)
                logger.warning(
                    "%s a echoue (tentative %s/%s); nouvel essai dans %.2f s.",
                    operation_name,
                    attempt,
                    self.retry_attempts,
                    delay,
                )
                time.sleep(delay)

    def ensure_bucket(self) -> None:
        def create_if_missing():
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as error:
                status = error.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                if status not in (403, 404):
                    raise
                self.client.create_bucket(Bucket=self.bucket)

        self._retry("verification du bucket S3", create_if_missing)

    def upload_bytes(self, key: str, content: bytes) -> None:
        self._retry(
            f"envoi S3 de {key}",
            lambda: self.client.put_object(
                Bucket=self.bucket, Key=key, Body=content
            ),
        )

    def download_bytes(self, key: str) -> bytes:
        def download():
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()

        return self._retry(f"recuperation S3 de {key}", download)

    def list_keys(self, prefix: str) -> list[str]:
        def list_objects():
            paginator = self.client.get_paginator("list_objects_v2")
            return [
                item["Key"]
                for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix)
                for item in page.get("Contents", [])
            ]

        return self._retry("liste des objets S3", list_objects)

    def delete_object(self, key: str) -> None:
        self._retry(
            f"suppression S3 de {key}",
            lambda: self.client.delete_object(Bucket=self.bucket, Key=key),
        )
