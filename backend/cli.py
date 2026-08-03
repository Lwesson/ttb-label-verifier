#!/usr/bin/env python3
"""Verify one label image against application data from the command line.

Examples:
  python cli.py ../corpus/images/clean_bourbon.png --type distilled_spirits \
      --brand "RIDGE & RYE" --class-type "Kentucky Straight Bourbon Whiskey" \
      --abv 45 --net "750 mL"
  python cli.py label.png --type wine --brand X --extractor mock --mock-json fx.json
"""
import argparse
import mimetypes
import time
from pathlib import Path

from ttb.models import BeverageType, ExpectedValues, ExtractedLabel
from ttb.normalize import parse_net_contents
from ttb.verdict import FIELD_LABELS, verify
from ttb.vision.mock import MockExtractor


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Verify an alcohol label image against its application data"
    )
    p.add_argument("image", help="path to the label image")
    p.add_argument("--type", required=True, dest="beverage_type",
                   choices=[t.value for t in BeverageType])
    p.add_argument("--brand", required=True)
    p.add_argument("--class-type")
    p.add_argument("--abv", type=float, help="expected ABV percent, e.g. 45")
    p.add_argument("--net", help='expected net contents, e.g. "750 mL"')
    p.add_argument("--name-address")
    p.add_argument("--country")
    p.add_argument("--imported", action="store_true")
    p.add_argument("--extractor", choices=["claude", "mock"], default="claude")
    p.add_argument("--mock-json", help="ExtractedLabel JSON file for --extractor mock")
    return p


def build_expected(args: argparse.Namespace) -> ExpectedValues:
    return ExpectedValues(
        beverage_type=BeverageType(args.beverage_type),
        brand_name=args.brand,
        class_type=args.class_type,
        abv_percent=args.abv,
        net_contents_ml=parse_net_contents(args.net),
        name_address=args.name_address,
        country_of_origin=args.country,
        is_import=args.imported,
    )


def run(argv=None):
    args = build_parser().parse_args(argv)
    image = Path(args.image)
    image_bytes = image.read_bytes()
    media_type = mimetypes.guess_type(image.name)[0] or "image/png"
    expected = build_expected(args)

    if args.extractor == "mock":
        fixture = ExtractedLabel.model_validate_json(Path(args.mock_json).read_text())
        extractor = MockExtractor(fixture)
    else:
        from ttb.vision.claude import ClaudeVisionExtractor
        extractor = ClaudeVisionExtractor()

    start = time.perf_counter()
    extraction = extractor.extract(image_bytes, media_type, expected.beverage_type)
    result = verify(expected, extraction)
    result.elapsed_seconds = round(time.perf_counter() - start, 2)

    print(f"\n{result.verdict.value.upper()}: {result.headline}  ({result.elapsed_seconds}s)")
    for reason in result.reasons:
        print(f"  - {reason}")
    print("\nFields:")
    for m in result.field_matches:
        label = FIELD_LABELS.get(m.field, m.field)
        print(f"  {label:18} {m.status.value:14} {m.reason}")
    print("\nWarning checks:")
    for c in result.warning.checks:
        print(f"  {c.name:14} {c.status.value:8} {c.detail}")
    return result


if __name__ == "__main__":
    run()
