from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Transaction:
    transaction_datetime: datetime
    source_iban: str
    source_country: str
    source_bank: str
    destination_iban: str
    destination_country: str
    amount: Decimal


@dataclass(frozen=True)
class ProcessedTransaction:
    transaction: Transaction
    is_over_5000: bool


@dataclass(frozen=True)
class ProcessingResult:
    transactions: tuple[ProcessedTransaction, ...]
    outgoing_by_iban: dict[str, Decimal]
    outgoing_by_bank: dict[str, Decimal]
    incoming_by_iban: dict[str, Decimal]
