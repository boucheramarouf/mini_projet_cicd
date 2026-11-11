from decimal import Decimal

from data_pipeline.models import (
    ProcessedTransaction,
    ProcessingResult,
    Transaction,
)


def process_transactions(
    transactions: list[Transaction],
) -> ProcessingResult:
    """Calcule les indicateurs sans modifier les transactions en entree."""
    outgoing_by_iban: dict[str, Decimal] = {}
    outgoing_by_bank: dict[str, Decimal] = {}
    incoming_by_iban: dict[str, Decimal] = {}
    processed = []

    for transaction in transactions:
        outgoing_by_iban[transaction.source_iban] = (
            outgoing_by_iban.get(transaction.source_iban, Decimal("0"))
            + transaction.amount
        )
        outgoing_by_bank[transaction.source_bank] = (
            outgoing_by_bank.get(transaction.source_bank, Decimal("0"))
            + transaction.amount
        )
        incoming_by_iban[transaction.destination_iban] = (
            incoming_by_iban.get(transaction.destination_iban, Decimal("0"))
            + transaction.amount
        )
        processed.append(
            ProcessedTransaction(
                transaction=transaction,
                is_over_5000=transaction.amount > Decimal("5000"),
            )
        )

    return ProcessingResult(
        transactions=tuple(processed),
        outgoing_by_iban=outgoing_by_iban,
        outgoing_by_bank=outgoing_by_bank,
        incoming_by_iban=incoming_by_iban,
    )
