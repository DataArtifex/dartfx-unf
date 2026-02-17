# Usage Guide

`dartfx-unf` provides multiple ways to calculate UNF fingerprints depending on your data source.

## Command Line Interface (CLI)

The CLI is the easiest way to hash files directly from the terminal.

```bash
uv run dartfx-unf [FILES] [OPTIONS]
```

### Basic Usage

Calculate the UNF for a single file. By default, this outputs a full JSON report to stdout.

```bash
uv run dartfx-unf data.parquet
```

### Dataset Usage

Pass multiple files to calculate a dataset-level UNF.

```bash
uv run dartfx-unf file1.csv file2.parquet file3.tsv
```

### Formatting Options

*   **`--quiet` or `-q`**: Print *only* the top-level UNF string. perfect for pipes and shell scripts.
*   **`--verbose` or `-v`**: Print a human-friendly summary table showing UNFs for individual columns (for files) or individual files (for datasets).
*   **`--output FILE` or `-o FILE`**: Save the full JSON report to a file instead of stdout.
*   **`--validate`**: Ensure the JSON report matches the official UNF schema.

### Configuration Flags

*   **`--digits N`**: Number of significant digits for numeric precision (default: 7).
*   **`--hash-bits H`**: SHA-256 hash truncation in bits (128, 192, 196, or 256).
*   **`--characters X`**: String truncation length (default: 128).
*   **`--truncate`**: Use truncation (R1) instead of IEEE 754 rounding.

### Schema Specification

By default, `dartfx-unf` automatically infers column data types using Polars' type inference. For CSV files, you can override this behavior with a JSON Schema to ensure consistent type handling across systems.

**See the [Schema Specification Reference](schema.md) for comprehensive documentation**, including advanced features like custom date/datetime format support.

The `--schema` option accepts three formats:

#### 1. JSON Schema File

Create a file named `schema.json`:
```json
{
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "salary": {"type": "number"},
    "start_date": {"type": "date"}
  }
}
```

Then use it:
```bash
uv run dartfx-unf --schema schema.json data.csv
```

#### 2. Inline JSON Schema

Pass the schema directly on the command line:
```bash
uv run dartfx-unf --schema '{"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}' data.csv
```

#### 3. Simple Dictionary Format (CLI only)

For basic use cases, the inline format can be simplified to just `column: type` pairs if it parses properly.

**Supported JSON Schema Types:**
- `"integer"` → Int64
- `"number"` → Float64
- `"string"` → Utf8
- `"boolean"` → Boolean
- `"date"` → Date (supports custom formats via `format` property)
- `"time"` → Time
- `"date-time"` → Datetime (supports custom formats via `format` property)
- `"null"` → Null

#### Date/DateTime with Custom Formats

If your CSV contains dates or datetimes in a non-ISO 8601 format, specify the format using the `format` property:

**Single format example:**
```bash
uv run dartfx-unf --schema '{"properties": {"hire_date": {"type": "date", "format": "dd.mm.yyyy"}}}' data.csv
```

**Multiple formats (oneOf) example:**
```bash
uv run dartfx-unf --schema '{
  "properties": {
    "date": {
      "type": "date",
      "oneOf": [
        {"format": "dd.mm.yyyy"},
        {"format": "yyyy-mm-dd"}
      ]
    }
  }
}' data.csv
```

See the [Schema Specification Reference](schema.md) for a complete list of supported format strings and more examples.

**Error Handling:**
- **String columns** can be overridden to any type with a warning
- **Other type mismatches** raise an error (e.g., trying to cast an inferred integer to date)
- **Missing columns** in data are logged as warnings but don't fail
- **Format mismatch** raises an error with details (e.g., "Failed to cast column 'date' from String to Date")

**Example: Type Override**
```bash
# CSV infers "01234" as string, but you want it as integer
uv run dartfx-unf --schema '{"properties": {"id": {"type": "integer"}}}' data.csv
```

### Performance Tuning

*   **`--streaming`**: Force Polars' "out-of-core" streaming mode. Recommended for files larger than 1GB.
*   **`--batch-size ROWS`**: Set the batch size for streaming operations (default: 100,000).
*   **`--scan-length ROWS`**: Number of rows to scan for CSV schema inference (default: 10,000). Use `-1` to scan all rows for more accurate type detection.

---

## Python API

The Python API offers the most flexibility and integration capability.

### 1. File Hashing

To calculate a UNF for a single file (CSV, Parquet, or TSV):

```python
from dartfx.unf import unf_file

# Basic calculation
report = unf_file("data.parquet")
print(f"UNF: {report.result.unf}")

# Customizing parameters
from dartfx.unf.parameters import UNFParameters
params = UNFParameters(digits=9, hash_bits=256)
report = unf_file("data.csv", params=params)

# Control CSV schema inference
report = unf_file("data.csv", infer_schema_length=50_000)  # scan 50k rows
report = unf_file("data.csv", infer_schema_length=-1)     # scan all rows

# Use a JSON Schema to override type inference
report = unf_file("data.csv", schema="schema.json")  # file path

# Or provide inline JSON schema
schema_json = '{"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}'
report = unf_file("data.csv", schema=schema_json)

# Or use a Python dictionary (shorthand)
schema_dict = {"id": "integer", "name": "string", "salary": "number"}
report = unf_file("data.csv", schema=schema_dict)

# Use custom date formats
schema_with_dates = {
    "properties": {
        "hire_date": {
            "type": "date",
            "format": "dd.mm.yyyy"  # European format
        }
    }
}
report = unf_file("data.csv", schema=schema_with_dates)

# Support multiple date formats in same column
schema_mixed = {
    "properties": {
        "date": {
            "type": "date",
            "oneOf": [
                {"format": "dd.mm.yyyy"},
                {"format": "yyyy-mm-dd"}
            ]
        }
    }
}
report = unf_file("data.csv", schema=schema_mixed)
```

### 2. Large Datasets (Streaming)

Process datasets that exceed available RAM by leveraging the Polars streaming engine.

```python
from dartfx.unf import unf_file

# Process a massive file with constant memory usage
report = unf_file(
    "massive_dataset.parquet",
    streaming=True,
    batch_size=100_000
)
print(f"UNF: {report.result.unf}")

# For CSV files with uncertain types, scan all rows:
report = unf_file(
    "massive_dataset.csv",
    streaming=True,
    batch_size=100_000,
    infer_schema_length=-1  # scan all rows for type detection
)
```

### 3. Multiple Files (Datasets)

Calculate a combined fingerprint for a collection of files.

```python
from dartfx.unf import unf_dataset
from pathlib import Path

# Combine all parts of a partitioned dataset
files = list(Path("data/").glob("*.parquet"))
report = unf_dataset(files, label="My Large Dataset")

print(f"Dataset-level UNF: {report.result.unf}")
# Access individual file UNFs
for entry in report.result.entries:
    print(f"  {entry.label}: {entry.unf}")

# Apply a common schema to all files
schema = {"id": "integer", "date": "date", "value": "number"}
report = unf_dataset(files, schema=schema)
```

### 4. In-Memory Data (DataFrames & Series)

Calculate UNFs directly on existing Polars objects.

```python
import polars as pl
from dartfx.unf import unf_dataframe, unf_column

df = pl.DataFrame({
    "id": [1, 2, 3],
    "value": [1.1, 2.2, 3.3]
})

# Hash the entire DataFrame
df_report = unf_dataframe(df)

# Hash just a single column
col_unf = unf_column(df.get_column("value"))
```

### 5. Exporting Reports

The `UNFReport` object provides structured metadata including column types and timestamps.

```python
report = unf_file("data.parquet")

# Export to a Python dictionary
data = report.to_dict()

# Export to a JSON string (optionally validated)
json_str = report.to_json(validate=True)
```
