import argparse
import logging

from data_pipeline.config import Settings
from data_pipeline.generate import generate_csv_files
from data_pipeline.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generation, traitement et stockage S3/PostgreSQL des transactions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("generate", help="generer les fichiers CSV deterministes")

    run_parser = subparsers.add_parser(
        "run", help="traiter les fichiers deja presents sur S3"
    )
    run_parser.add_argument(
        "--simulate-processing-failure",
        action="store_true",
        help="declencher volontairement une erreur de traitement (demonstration)",
    )
    run_all_parser = subparsers.add_parser(
        "run-all", help="generer, envoyer sur S3 et traiter les fichiers"
    )
    run_all_parser.add_argument(
        "--simulate-processing-failure",
        action="store_true",
        help="declencher volontairement une erreur de traitement (demonstration)",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings.from_env()
    if arguments.command == "generate":
        files = generate_csv_files(settings.data_directory)
        for path in files:
            print(path)
        return

    run_pipeline(
        settings,
        generate=arguments.command == "run-all",
        simulate_processing_failure=getattr(
            arguments, "simulate_processing_failure", False
        ),
    )


if __name__ == "__main__":
    main()
