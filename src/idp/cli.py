"""Command line interface.

Examples
--------
Show the resolved configuration and the health of each engine::

    python -m idp info

Process a whole folder with the local backend::

    python -m idp process ./scans --output ./out --provider ollama
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from idp.config import PROVIDERS, Settings, get_settings
from idp.errors import IdpError
from idp.logging_utils import get_logger, setup_logging
from idp.pipeline import Pipeline
from idp.schemas import DocumentType

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idp",
        description="Intelligent Document Processing - extraction structuree multimodale.",
    )
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="Affiche la configuration et l'etat des moteurs")

    process = subparsers.add_parser("process", help="Traite un fichier ou un dossier")
    process.add_argument("input", help="Fichier image/PDF ou dossier a parcourir")
    process.add_argument("-o", "--output", default=None, help="Dossier de sortie des JSON")
    process.add_argument("-p", "--provider", choices=PROVIDERS, default=None)
    process.add_argument(
        "-t",
        "--doc-type",
        choices=DocumentType.values(),
        default=None,
        help="Force le type de document (sinon detection automatique)",
    )
    process.add_argument("--no-cache", action="store_true", help="Ignore le cache OCR/extraction")
    process.add_argument("--print", dest="print_json", action="store_true", help="Affiche le JSON produit")

    return parser


def _cmd_info(settings: Settings) -> int:
    print("Configuration effective")
    print("-" * 60)
    for key, value in settings.describe().items():
        print(f"  {key:<20} : {value}")

    print()
    print("Etat des moteurs")
    print("-" * 60)
    for provider in PROVIDERS:
        try:
            health = Pipeline(provider=provider, settings=settings).health()
        except Exception as exc:  # noqa: BLE001 - diagnostic command
            print(f"  {provider:<8} : indisponible ({exc})")
            continue
        ocr = health["ocr"]
        extractor = health["extractor"]
        print(f"  {provider:<8} : OCR {'OK' if ocr['ok'] else 'KO'} ({ocr['detail']})")
        print(f"  {'':<8}   Extraction {'OK' if extractor['ok'] else 'KO'} ({extractor['detail']})")
    return 0


def _collect_inputs(raw_input: str) -> list[Path]:
    target = Path(raw_input)
    if target.is_file():
        return [target]
    if target.is_dir():
        from idp.pdf import is_supported

        return sorted(path for path in target.rglob("*") if path.is_file() and is_supported(path))
    raise IdpError(f"Chemin introuvable : {target}")


def _cmd_process(args: argparse.Namespace, settings: Settings) -> int:
    from idp.pdf import is_supported

    files = _collect_inputs(args.input)
    if not files:
        print("Aucun fichier supporte trouve.", file=sys.stderr)
        return 1

    files = [path for path in files if is_supported(path)]
    pipeline = Pipeline(provider=args.provider, settings=settings, use_cache=not args.no_cache)

    health = pipeline.health()
    if not health["ocr"]["ok"]:
        print(f"OCR indisponible : {health['ocr']['detail']}", file=sys.stderr)
        return 2
    if not health["extractor"]["ok"]:
        print(f"Extraction indisponible : {health['extractor']['detail']}", file=sys.stderr)
        return 2

    failures = 0
    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path.name}")
        try:
            outputs = pipeline.process_and_save_all(path, out_dir=args.output)
            for output in outputs:
                print(f"    -> {output}")
            if args.print_json:
                print(json.dumps(pipeline.process(path).to_dict(), indent=2, ensure_ascii=False))
        except IdpError as exc:
            failures += 1
            print(f"    !! echec : {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - never abort the whole batch
            failures += 1
            logger.exception("Erreur inattendue sur %s", path)
            print(f"    !! erreur inattendue : {exc}", file=sys.stderr)

    print()
    print(f"Termine : {len(files) - failures} succes, {failures} echec(s).")
    return 0 if failures == 0 else 3


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level, force=True)
    settings = get_settings()

    try:
        if args.command == "info":
            return _cmd_info(settings)
        if args.command == "process":
            return _cmd_process(args, settings)
    except IdpError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    return 1
