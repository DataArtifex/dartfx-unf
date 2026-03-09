import json
from pathlib import Path

import pytest

from dartfx.unf.core import unf_file

BASE_DIR = Path(__file__).parent / "101"

# Discover all supported file formats
DATA_FILES = [
    f
    for f in BASE_DIR.glob("*.*")
    if f.suffix in {".csv", ".dta", ".sav", ".xpt", ".parquet"}
]


@pytest.mark.parametrize("data_file", DATA_FILES, ids=lambda x: x.name)
def test_101_files(data_file):
    # Determine corresponding JSON file containing expected results
    if data_file.suffix == ".parquet":
        json_file = data_file.with_suffix(".unf6-parquet.json")
    else:
        # All other files should match the CSV results
        json_file = data_file.with_suffix(".unf6.json")

    if not json_file.exists():
        pytest.skip(f"No JSON expected results found for {data_file.name}")

    with open(json_file) as f:
        expected = json.load(f)

    expected_unf = expected["result"]["unf"]
    expected_columns = {
        col["name"]: col["unf"] for col in expected["result"]["columns"]
    }

    # Calculate UNF
    report = unf_file(data_file)
    result = report.result

    # Assert file UNF
    assert result.unf == expected_unf, f"File UNF mismatch for {data_file.name}"

    # Assert column UNFs
    for col in result.columns:
        if col.name in expected_columns:
            assert col.unf == expected_columns[col.name], (
                f"Column {col.name} UNF mismatch in {data_file.name}"
            )
