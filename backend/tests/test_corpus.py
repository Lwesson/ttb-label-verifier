import csv
import subprocess
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
VALID_VERDICTS = {"pass", "review", "fail", "unreadable"}


def test_render_labels_produces_corpus_and_manifest():
    result = subprocess.run(
        [sys.executable, str(CORPUS / "render_labels.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    with open(CORPUS / "manifest.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 15
    for row in rows:
        accepted = set(row["expected_verdict"].split("|"))
        assert accepted <= VALID_VERDICTS and accepted
        image = CORPUS / "images" / row["filename"]
        assert image.exists(), f"missing {row['filename']}"
        assert image.stat().st_size > 5000
    names = {r["filename"] for r in rows}
    for expected_name in (
        "blurry_bourbon.png", "glare_bourbon.png", "angled_bourbon.png",
        "dim_bourbon.png", "warning_not_bold.png",
    ):
        assert expected_name in names


def test_batch_manifest_emitted_for_demo():
    with open(CORPUS / "batch_manifest.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 15
    assert set(rows[0].keys()) == {
        "filename", "beverage_type", "brand_name", "class_type", "abv_percent",
        "net_contents", "name_address", "country_of_origin", "is_import",
    }
