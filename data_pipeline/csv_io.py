import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import TextIOBase

from data_pipeline.models import Transaction


CSV_COLUMNS = (
    "transaction_datetime",
    "source_iban",
    "source_country",
    "source_bank",
    "destination_iban",
    "destination_country",
    "amount",
)


class InvalidTransactionFile(ValueError):
    """Le fichier CSV ne respecte pas le contrat d'ingestion."""


def load_transactions(csv_file: TextIOBase) -> list[Transaction]:
    reader = csv.DictReader(csv_file)
    if reader.fieldnames is None or tuple(reader.fieldnames) != CSV_COLUMNS:
        raise InvalidTransactionFile(
            f"Colonnes attendues: {', '.join(CSV_COLUMNS)}"
        )

    transactions = []
    for row_number, row in enumerate(reader, start=2):
        try:
            if any(key is None or value is None for key, value in row.items()):
                raise ValueError("nombre de colonnes invalide")
            amount = Decimal(row["amount"])
            if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
                raise ValueError("le montant doit etre positif avec au plus 2 decimales")
            transaction_datetime = datetime.fromisoformat(
                row["transaction_datetime"]
            )
            text_fields = (
                "source_iban",
                "source_country",
                "source_bank",
                "destination_iban",
                "destination_country",
            )
            if any(not row[field].strip() for field in text_fields):
                raise ValueError("un champ texte obligatoire est vide")
        except (InvalidOperation, TypeError, ValueError) as error:
            raise InvalidTransactionFile(
                f"Ligne {row_number} invalide: {error}"
            ) from error

        transactions.append(
            Transaction(
                transaction_datetime=transaction_datetime,
                source_iban=row["source_iban"].strip(),
                source_country=row["source_country"].strip(),
                source_bank=row["source_bank"].strip(),
                destination_iban=row["destination_iban"].strip(),
                destination_country=row["destination_country"].strip(),
                amount=amount,
            )
        )

    if not transactions:
        raise InvalidTransactionFile("Le fichier CSV ne contient aucune transaction.")
    return transactions
