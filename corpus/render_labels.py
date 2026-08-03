#!/usr/bin/env python3
"""Render exact-text test labels for the verification corpus.

Programmatic rendering (instead of AI image generation) is used for the
strict-text cases so the corpus controls every character on the label.
Messy real-photo cases (glare, angle) are added separately.
"""
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ttb.rules import CANONICAL_WARNING  # noqa: E402

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
REGULAR = str(FONT_DIR / "DejaVuSans.ttf")
BOLD = str(FONT_DIR / "DejaVuSans-Bold.ttf")

OUT = Path(__file__).parent / "images"
W, H = 1000, 1400
INK = "#1a1a1a"
PAPER = "#f5efe0"

NAME_ADDRESS = "Bottled by Ridge & Rye Distilling Co., Bardstown, KY"


def wrap(draw, text, font, max_w):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_label(
    filename,
    *,
    brand,
    class_type=None,
    abv_line=None,
    net_contents=None,
    name_address=NAME_ADDRESS,
    country=None,
    warning=CANONICAL_WARNING,
    warning_bold_prefix=True,
):
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, H - 30], outline="#333333", width=4)

    y = 130
    brand_font = ImageFont.truetype(BOLD, 72)
    for line in wrap(d, brand, brand_font, W - 160):
        d.text(((W - d.textlength(line, font=brand_font)) / 2, y), line,
               font=brand_font, fill=INK)
        y += 90
    y += 30
    body_font = ImageFont.truetype(REGULAR, 44)
    for text in (class_type, abv_line, net_contents):
        if not text:
            continue
        d.text(((W - d.textlength(text, font=body_font)) / 2, y), text,
               font=body_font, fill=INK)
        y += 70

    y = H - 440
    small_font = ImageFont.truetype(REGULAR, 30)
    for text in (name_address, country):
        if not text:
            continue
        d.text(((W - d.textlength(text, font=small_font)) / 2, y), text,
               font=small_font, fill=INK)
        y += 44

    if warning:
        # Warning sits in a white panel with a border so it reads as legible
        # on a contrasting background, separate and apart (27 CFR 16.22).
        d.rectangle([55, H - 345, W - 55, H - 55], fill="#ffffff", outline="#333333", width=3)
        wfont = ImageFont.truetype(REGULAR, 26)
        wbold = ImageFont.truetype(BOLD, 26)
        head, sep, rest = warning.partition(":")
        if sep:
            head_font = wbold if warning_bold_prefix else wfont
            tokens = [(t, head_font) for t in (head + ":").split()]
            tokens += [(t, wfont) for t in rest.split()]
        else:
            tokens = [(t, wfont) for t in warning.split()]
        x, yy = 80, H - 310
        space = d.textlength(" ", font=wfont)
        for token, font in tokens:
            tw = d.textlength(token, font=font)
            if x + tw > W - 80:
                x = 80
                yy += 38
            d.text((x, yy), token, font=font, fill=INK)
            x += tw + space

    OUT.mkdir(exist_ok=True)
    img.save(OUT / filename)


LABELS = [
    {
        "filename": "clean_bourbon.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="pass",
            tests_what="Happy path, everything matches",
        ),
    },
    {
        "filename": "stones_throw.png",
        "render": dict(
            brand="STONE'S THROW",
            class_type="Straight Rye Whiskey",
            abv_line="46% Alc./Vol. (92 Proof)",
            net_contents="750 mL",
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="Stone's Throw",
            expected_class_type="Straight Rye Whiskey",
            expected_abv="46", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="review",
            tests_what="Fuzzy brand judgment: caps difference is REVIEW, not FAIL",
        ),
    },
    {
        "filename": "warning_title_case.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            warning=CANONICAL_WARNING.replace(
                "GOVERNMENT WARNING:", "Government Warning:"
            ),
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="fail",
            tests_what="Warning capitalization: title case must fail",
        ),
    },
    {
        "filename": "warning_reworded.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            warning=CANONICAL_WARNING.replace("birth defects", "health issues"),
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="fail",
            tests_what="Warning wording: reworded statement must fail",
        ),
    },
    {
        "filename": "warning_missing.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            warning=None,
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="fail",
            tests_what="Missing warning statement entirely",
        ),
    },
    {
        "filename": "abv_mismatch.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="40% Alc./Vol. (80 Proof)",
            net_contents="750 mL",
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="fail",
            tests_what="Label ABV 40 vs application 45",
        ),
    },
    {
        "filename": "net_contents_700.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="45% Alc./Vol. (90 Proof)",
            net_contents="700 mL",
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="fail",
            tests_what="Net contents 700 mL vs application 750 mL",
        ),
    },
    {
        "filename": "table_wine.png",
        "render": dict(
            brand="MEADOWLARK CELLARS",
            class_type="Red Table Wine",
            abv_line=None,
            net_contents="750 mL",
            name_address="Produced and bottled by Meadowlark Cellars, Walla Walla, WA",
        ),
        "manifest": dict(
            beverage_type="wine", expected_brand="MEADOWLARK CELLARS",
            expected_class_type="Red Table Wine",
            expected_abv="12", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="pass",
            tests_what="Table wine ABV exception: no numeric ABV is compliant",
        ),
    },
    {
        "filename": "proof_inconsistent.png",
        "render": dict(
            brand="RIDGE & RYE",
            class_type="Kentucky Straight Bourbon Whiskey",
            abv_line="45% Alc./Vol. (80 Proof)",
            net_contents="750 mL",
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="RIDGE & RYE",
            expected_class_type="Kentucky Straight Bourbon Whiskey",
            expected_abv="45", expected_net_ml="750", is_import="false",
            expected_country="", expected_verdict="review",
            tests_what="Proof does not equal 2 x ABV, internal consistency check",
        ),
    },
    {
        "filename": "import_no_country.png",
        "render": dict(
            brand="GLEN MORRIG",
            class_type="Single Malt Scotch Whisky",
            abv_line="43% Alc./Vol. (86 Proof)",
            net_contents="750 mL",
            name_address="Imported by Caledonia Imports LLC, New York, NY",
            country=None,
        ),
        "manifest": dict(
            beverage_type="distilled_spirits", expected_brand="GLEN MORRIG",
            expected_class_type="Single Malt Scotch Whisky",
            expected_abv="43", expected_net_ml="750", is_import="true",
            expected_country="Scotland", expected_verdict="fail",
            tests_what="Imported spirit missing country of origin",
        ),
    },
]

MANIFEST_COLUMNS = [
    "filename", "beverage_type", "expected_brand", "expected_class_type",
    "expected_abv", "expected_net_ml", "is_import", "expected_country",
    "expected_verdict", "tests_what",
]


def main():
    for spec in LABELS:
        render_label(spec["filename"], **spec["render"])
        print(f"rendered {spec['filename']}")
    manifest_path = Path(__file__).parent / "manifest.csv"
    with open(manifest_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for spec in LABELS:
            writer.writerow({"filename": spec["filename"], **spec["manifest"]})
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
