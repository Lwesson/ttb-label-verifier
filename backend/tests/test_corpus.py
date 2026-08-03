import csv
import subprocess
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[2] / "corpus"


def test_render_labels_produces_corpus_and_manifest():
    result = subprocess.run(
        [sys.executable, str(CORPUS / "render_labels.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    with open(CORPUS / "manifest.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 10
    verdicts = {r["expected_verdict"] for r in rows}
    assert verdicts == {"pass", "review", "fail"}
    for row in rows:
        image = CORPUS / "images" / row["filename"]
        assert image.exists(), f"missing {row['filename']}"
        assert image.stat().st_size > 5000
