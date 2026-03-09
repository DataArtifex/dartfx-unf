import json
from pathlib import Path

from dartfx.unf.cli import main


def test_cli_default_parse_dates(tmp_path: Path) -> None:
    """Test that by default the CLI does not parse dates (changed default)."""
    csv_file = tmp_path / "dates.csv"
    csv_file.write_text("date_col\n2020-01-01\n")

    output_file = tmp_path / "output.json"

    # Run CLI
    main([str(csv_file), "--output", str(output_file)])

    # Read output
    report = json.loads(output_file.read_text())

    # If parse_dates was true, type would be "date".
    # Since the default is False, it should remain "string".
    assert report["result"]["columns"][0]["type"] == "string"


def test_cli_parse_date_flag(tmp_path: Path) -> None:
    """Test that --parse-date enables date parsing."""
    csv_file = tmp_path / "dates.csv"
    csv_file.write_text("date_col\n2020-01-01\n")

    output_file = tmp_path / "output.json"

    # Run CLI
    main([str(csv_file), "--parse-date", "--output", str(output_file)])

    # Read output
    report = json.loads(output_file.read_text())

    # With --parse-date, the type should be "date".
    assert report["result"]["columns"][0]["type"] == "date"


def test_cli_leading_zeros(tmp_path: Path) -> None:
    """Test that --leading-zeros preserves leading zeros as strings."""
    csv_file = tmp_path / "lz.csv"
    csv_file.write_text("code\n0123\n0456\n")

    output_file = tmp_path / "output.json"

    # Run CLI without flag - should infer numeric (integer)
    main([str(csv_file), "--output", str(output_file)])
    report = json.loads(output_file.read_text())
    assert report["result"]["columns"][0]["type"] == "numeric"

    # Run CLI with --leading-zeros flag - should preserve string
    main([str(csv_file), "--leading-zeros", "--output", str(output_file)])
    report = json.loads(output_file.read_text())
    assert report["result"]["columns"][0]["type"] == "string"


def test_cli_no_leading_zeros(tmp_path: Path) -> None:
    """Test that --no-leading-zeros overrides explicit leading-zeros if needed."""
    csv_file = tmp_path / "lz.csv"
    csv_file.write_text("code\n0123\n0456\n")

    output_file = tmp_path / "output.json"

    main([str(csv_file), "--no-leading-zeros", "--output", str(output_file)])
    report = json.loads(output_file.read_text())
    assert report["result"]["columns"][0]["type"] == "numeric"
