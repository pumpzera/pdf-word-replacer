from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .core import ReplacementRule, replace_text_in_pdf


def _parse_rule(raw: str) -> ReplacementRule:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"Invalid replacement '{raw}'. Use SOURCE=TARGET format."
        )
    source, target = raw.split("=", 1)
    if not source:
        raise argparse.ArgumentTypeError("Replacement source cannot be empty.")
    return ReplacementRule(source=source, target=target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-word-replacer",
        description="Replace visible text in a text-based PDF.",
    )
    parser.add_argument("input_pdf", help="Path to the source PDF")
    parser.add_argument("output_pdf", help="Path for the edited PDF")
    parser.add_argument(
        "--replace",
        dest="replacements",
        action="append",
        type=_parse_rule,
        required=True,
        help="Replacement rule in SOURCE=TARGET format. Repeat for multiple replacements.",
    )
    parser.add_argument(
        "--ignore-case",
        action="store_true",
        help="Enable case-insensitive matching for single-word replacements.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_pdf = Path(args.input_pdf)
    output_pdf = Path(args.output_pdf)

    try:
        results = replace_text_in_pdf(
            input_pdf,
            output_pdf,
            args.replacements,
            ignore_case=args.ignore_case,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    total = sum(results.values())
    print(f"Saved: {output_pdf}")
    print(f"Total replacements: {total}")
    for source, count in results.items():
        print(f"- {source}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
