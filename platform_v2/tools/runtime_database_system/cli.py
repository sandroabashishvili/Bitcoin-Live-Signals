"""CLI for the SQLite runtime mirror lifecycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import export_all_documents, import_all_json, parity_report, status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage SmartSignalHub trading, market-data, and content databases.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--import-json", action="store_true", help="Import trading, market-data, and news JSON into SQLite.")
    action.add_argument("--check-parity", action="store_true", help="Compare all compatibility JSON with the three SQLite databases.")
    action.add_argument("--export-root", type=Path, help="Export all three SQLite databases as JSON under this directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.import_json:
        result = import_all_json()
    elif args.check_parity:
        result = parity_report()
    elif args.export_root:
        result = export_all_documents(target_root=args.export_root.expanduser().resolve())
    else:
        result = status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
