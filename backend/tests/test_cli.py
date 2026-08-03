from ttb.models import Verdict

from .fixtures import make_extraction


def test_cli_end_to_end_with_mock(tmp_path, capsys):
    import cli

    image = tmp_path / "label.png"
    image.write_bytes(b"fake image bytes")
    fixture = tmp_path / "extraction.json"
    fixture.write_text(make_extraction().model_dump_json())

    result = cli.run([
        str(image),
        "--type", "distilled_spirits",
        "--brand", "RIDGE & RYE",
        "--class-type", "Kentucky Straight Bourbon Whiskey",
        "--abv", "45",
        "--net", "750 mL",
        "--extractor", "mock",
        "--mock-json", str(fixture),
    ])
    assert result.verdict == Verdict.PASS
    out = capsys.readouterr().out
    assert "Looks good" in out
    assert "brand_name" in out or "Brand name" in out
