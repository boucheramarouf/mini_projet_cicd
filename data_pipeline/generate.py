import csv
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.csv_io import CSV_COLUMNS


_DATASETS = (
    (
        ("FR7630006000011234567890189", "FR", "Banque Atlas", "DE89370400440532013000", "DE", "1200.00"),
        ("FR7630006000011234567890189", "FR", "Banque Atlas", "ES9121000418450200051332", "ES", "6200.00"),
        ("DE89370400440532013000", "DE", "Rhein Bank", "FR7630006000011234567890189", "FR", "750.50"),
        ("GB29NWBK60161331926819", "GB", "North Bank", "DE89370400440532013000", "DE", "5000.00"),
        ("FR7630006000011234567890189", "FR", "Banque Atlas", "GB29NWBK60161331926819", "GB", "350.25"),
    ),
    (
        ("FR7630006000011234567890189", "FR", "Banque Atlas", "DE89370400440532013000", "DE", "900.00"),
        ("DE89370400440532013000", "DE", "Rhein Bank", "ES9121000418450200051332", "ES", "5100.01"),
        ("GB29NWBK60161331926819", "GB", "North Bank", "FR7630006000011234567890189", "FR", "1250.00"),
        ("ES9121000418450200051332", "ES", "Iberia Finance", "DE89370400440532013000", "DE", "80.00"),
        ("FR7630006000011234567890189", "FR", "Banque Atlas", "ES9121000418450200051332", "ES", "2200.00"),
    ),
)


def generate_csv_files(output_directory: str | Path) -> list[Path]:
    """Genere deux fichiers stables de cinq transactions chacun."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for file_index, rows in enumerate(_DATASETS, start=1):
        path = directory / f"transactions_{file_index:03d}.csv"
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_COLUMNS)
            for row_index, row in enumerate(rows, start=1):
                transaction_datetime = datetime(
                    2025, 1, file_index, 8 + row_index, 30, tzinfo=timezone.utc
                )
                writer.writerow(
                    [transaction_datetime.isoformat(), *row]
                )
        paths.append(path)
    return paths
