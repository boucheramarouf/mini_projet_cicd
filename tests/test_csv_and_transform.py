from decimal import Decimal
from io import StringIO

import pytest

from data_pipeline.csv_io import InvalidTransactionFile, load_transactions
from data_pipeline.generate import generate_csv_files
from data_pipeline.transform import process_transactions


def test_generated_csv_files_are_deterministic_and_loadable(tmp_path):
    first_run = generate_csv_files(tmp_path)
    first_contents = [path.read_bytes() for path in first_run]
    second_run = generate_csv_files(tmp_path)

    assert [path.name for path in second_run] == [
        "transactions_001.csv",
        "transactions_002.csv",
    ]
    assert [path.read_bytes() for path in second_run] == first_contents
    assert [
        len(load_transactions(StringIO(path.read_text(encoding="utf-8"))))
        for path in second_run
    ] == [5, 5]


def test_processing_sums_and_flags_without_mutating_input():
    transactions = load_transactions(
        StringIO(
            "transaction_datetime,source_iban,source_country,source_bank,"
            "destination_iban,destination_country,amount\n"
            "2025-01-01T10:00:00+00:00,FR1,FR,Banque A,DE1,DE,5000.00\n"
            "2025-01-01T11:00:00+00:00,FR1,FR,Banque A,DE2,DE,5000.01\n"
            "2025-01-01T12:00:00+00:00,FR2,FR,Banque B,DE1,DE,2.50\n"
        )
    )

    result = process_transactions(transactions)

    assert result.outgoing_by_iban == {"FR1": Decimal("10000.01"), "FR2": Decimal("2.50")}
    assert result.outgoing_by_bank == {"Banque A": Decimal("10000.01"), "Banque B": Decimal("2.50")}
    assert result.incoming_by_iban == {"DE1": Decimal("5002.50"), "DE2": Decimal("5000.01")}
    assert [item.is_over_5000 for item in result.transactions] == [False, True, False]
    assert transactions[1].amount == Decimal("5000.01")


@pytest.mark.parametrize(
    "row",
    [
        "2025-01-01,FR1,FR,Banque A,DE1,DE,NaN",
        "2025-01-01,FR1,FR,Banque A,DE1,DE,-1.00",
        "2025-01-01,FR1,FR,Banque A,DE1,DE,1.001",
        "invalid-date,FR1,FR,Banque A,DE1,DE,1.00",
        "2025-01-01,FR1,FR,Banque A",
    ],
)
def test_loader_rejects_invalid_rows(row):
    csv_content = (
        "transaction_datetime,source_iban,source_country,source_bank,"
        "destination_iban,destination_country,amount\n"
        + row
        + "\n"
    )
    with pytest.raises(InvalidTransactionFile, match="Ligne 2"):
        load_transactions(StringIO(csv_content))


def test_loader_rejects_wrong_columns():
    with pytest.raises(InvalidTransactionFile, match="Colonnes attendues"):
        load_transactions(StringIO("transaction_datetime,amount\n"))
