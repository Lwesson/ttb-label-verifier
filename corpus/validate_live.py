#!/usr/bin/env python3
"""Run the whole corpus through the LIVE vision pipeline and score the verdicts.

Each manifest row lists accepted verdicts (pipe-separated) because degraded
photos legitimately land in more than one correct outcome. Costs real API
calls: fractions of a cent per label on Haiku.

Usage:
  python validate_live.py
  python validate_live.py --model claude-sonnet-5 --write-md ../docs/corpus-results-sonnet.md
"""
import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from ttb.models import BeverageType, ExpectedValues  # noqa: E402
from ttb.verdict import verify  # noqa: E402
from ttb.vision.claude import ClaudeVisionExtractor  # noqa: E402

CORPUS = Path(__file__).parent


def expected_from_row(row: dict) -> ExpectedValues:
    return ExpectedValues(
        beverage_type=BeverageType(row["beverage_type"]),
        brand_name=row["expected_brand"],
        class_type=row["expected_class_type"] or None,
        abv_percent=float(row["expected_abv"]) if row["expected_abv"] else None,
        net_contents_ml=float(row["expected_net_ml"]) if row["expected_net_ml"] else None,
        country_of_origin=row["expected_country"] or None,
        is_import=row["is_import"] == "true",
    )


def main():
    parser = argparse.ArgumentParser(description="Validate the corpus against the live pipeline")
    parser.add_argument("--model", default=None, help="vision model id (default: env/TTB default)")
    parser.add_argument("--write-md", default=None, help="write a markdown results table here")
    parser.add_argument("--only", default=None, help="comma-separated filenames to run alone")
    args = parser.parse_args()

    extractor = ClaudeVisionExtractor(model=args.model)
    rows = list(csv.DictReader(open(CORPUS / "manifest.csv", newline="")))
    if args.only:
        wanted = set(args.only.split(","))
        rows = [r for r in rows if r["filename"] in wanted]
    records = []
    ok_count = 0
    print(f"model: {extractor.model}")
    print(f"{'label':26} {'accepted':22} {'got':11} ok  {'s':>5}")
    print("-" * 78)
    for row in rows:
        accepted = set(row["expected_verdict"].split("|"))
        image = CORPUS / "images" / row["filename"]
        expected = expected_from_row(row)
        start = time.perf_counter()
        extraction = extractor.extract(image.read_bytes(), "image/png", expected.beverage_type)
        result = verify(expected, extraction)
        elapsed = time.perf_counter() - start
        ok = result.verdict.value in accepted
        ok_count += ok
        records.append((row, result, elapsed, ok))
        print(
            f"{row['filename']:26} {row['expected_verdict']:22} "
            f"{result.verdict.value:11} {'Y' if ok else 'N':3} {elapsed:5.1f}"
        )
    print("-" * 78)
    print(f"{ok_count}/{len(rows)} in accepted verdicts")
    times = sorted(e for _, _, e, _ in records)
    print(f"latency: min {times[0]:.1f}s, median {times[len(times) // 2]:.1f}s, max {times[-1]:.1f}s")

    if args.write_md:
        out = Path(args.write_md)
        lines = [
            "# Corpus results",
            "",
            f"Model: `{extractor.model}`. {ok_count}/{len(rows)} labels landed in an accepted verdict.",
            f"Latency: min {times[0]:.1f}s, median {times[len(times) // 2]:.1f}s, max {times[-1]:.1f}s.",
            "",
            "| Label | Tests | Accepted | Result | Seconds |",
            "|---|---|---|---|---|",
        ]
        for row, result, elapsed, ok in records:
            mark = "" if ok else " (MISS)"
            lines.append(
                f"| {row['filename']} | {row['tests_what']} | {row['expected_verdict']} "
                f"| {result.verdict.value}{mark} | {elapsed:.1f} |"
            )
        out.write_text("\n".join(lines) + "\n")
        print(f"wrote {out}")

    sys.exit(0 if ok_count == len(rows) else 1)


if __name__ == "__main__":
    main()
