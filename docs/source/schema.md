# Schema Specification Reference

## Overview

The `--schema` option allows you to explicitly define data types for columns in CSV files, overriding Polars' automatic type inference. This is useful when:

- You need consistent type handling across different systems
- CSV data has ambiguous types (e.g., numeric IDs that look like strings)
- You're processing data from external sources with known schemas
- You want to ensure reproducible, deterministic fingerprints

## Schema Format: JSON Schema

The `dartfx-unf` package uses [JSON Schema](https://json-schema.org/) as its schema specification format. This is a standardized, widely-understood format that integrates well with data pipelines.

### Basic Structure

```json
{
  "properties": {
    "column_name": {"type": "type_name"},
    "another_column": {"type": "type_name"}
  }
}
```

**Example:**
```json
{
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "salary": {"type": "number"},
    "hired_date": {"type": "date"},
    "is_active": {"type": "boolean"}
  }
}
```

## Supported Data Types

| JSON Schema Type | Polars Type | Python Example | Notes |
|---|---|---|---|
| `"integer"` | `Int64` | `42` | Whole numbers only |
| `"number"` | `Float64` | `3.14` | Floating-point values |
| `"string"` | `Utf8` | `"hello"` | Text data |
| `"boolean"` | `Boolean` | `true` / `false` | True/False values |
| `"date"` | `Date` | `"2024-02-16"` | ISO 8601 date format |
| `"time"` | `Time` | `"14:30:45"` | ISO 8601 time format |
| `"date-time"` | `Datetime` | `"2024-02-16T14:30:45Z"` | ISO 8601 datetime |
| `"null"` | `Null` | `null` | Missing/null-only column |

## Input Methods

The `--schema` option (CLI) and `schema` parameter (Python API) accept three formats:

### 1. File Path

Provide a path to a JSON Schema file:

**CLI:**
```bash
uv run dartfx-unf --schema ./data/schema.json data.csv
```

**Python:**
```python
from dartfx.unf import unf_file
report = unf_file("data.csv", schema="schema.json")
```

### 2. Inline JSON String

Provide a JSON string directly:

**CLI:**
```bash
uv run dartfx-unf --schema '{"properties": {"id": {"type": "integer"}}}' data.csv
```

**Python:**
```python
schema_json = '{"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}'
report = unf_file("data.csv", schema=schema_json)
```

### 3. Python Dictionary (Python API only)

Pass a dictionary mapping column names to type names:

```python
schema_dict = {
    "id": "integer",
    "name": "string",
    "salary": "number",
    "hired_date": "date"
}
report = unf_file("data.csv", schema=schema_dict)
```

## Partial Schemas

You don't need to specify all columns. Columns not mentioned in the schema will use Polars' automatic type inference:

**Example:**
```python
# Only override the 'id' column; others inferred automatically
partial_schema = {"id": "integer"}
report = unf_file("data.csv", schema=partial_schema)
```

This is useful for large files where you only need to fix a few ambiguous columns.

## Error Handling

### String Columns → Any Type (Allowed with Warning)

If a column is inferred as `string` (UTF-8 text) but you specify a different type, the value is cast with a **warning**:

```
⚠️  Casting column 'id' from string to integer
```

This is safe because any string can be attempted to be cast to another type.

**Example:**
```csv
id,name
00001,Alice
00002,Bob
```

Without schema:
- `id` is inferred as `string` (because of leading zeros)

With schema:
```json
{"properties": {"id": {"type": "integer"}}}
```
- Casts to `integer` (leading zeros preserved in the fingerprint calculation)

### Other Type Mismatches (Error)

If a non-string column doesn't match the specified type, an error is raised:

```
❌ ValueError: Type mismatch for column 'salary': inferred as int64, user specified float64
```

**Solution:** Ensure your schema matches the actual data, or verify that the data is clean.

### Missing Columns in Data (Warning)

If your schema specifies a column that doesn't exist in the data, a warning is logged:

```
⚠️  Schema specifies column 'phone_number' which doesn't exist in data
```

The missing column is ignored, and processing continues.

## Use Cases

### 1. Standardizing CSV Type Inference

CSV files don't have built-in type metadata. Different systems (Excel, Python, R) may infer types differently.

**Before (inconsistent):**
```csv
id,date,value
001,2024-01-15,100
002,2024-01-16,200
```

- Excel might see `id` as text
- Python might see `date` as string
- R might see `value` as numeric

**After (with schema):**
```json
{
  "properties": {
    "id": {"type": "integer"},
    "date": {"type": "date"},
    "value": {"type": "number"}
  }
}
```

All systems produce the same UNF fingerprint.

### 2. Pre-processing Data from APIs

When exporting JSON data to CSV via an API, types are lost:

```python
# API response
[
  {"user_id": 123, "created_at": "2024-02-16T10:00:00Z"},
  {"user_id": 124, "created_at": "2024-02-16T11:00:00Z"}
]

# Exported to CSV (everything becomes string)
user_id,created_at
123,2024-02-16T10:00:00Z
124,2024-02-16T11:00:00Z
```

**Schema recovery:**
```json
{
  "properties": {
    "user_id": {"type": "integer"},
    "created_at": {"type": "date-time"}
  }
}
```

### 3. Data Lineage & Reproducibility

When sharing data with collaborators, include a schema file for reproducible fingerprinting:

```
dataset/
├── data.csv
├── schema.json          ← Include this
└── README.md
```

Everyone uses the same schema → everyone gets the same UNF → verifiable data integrity.

## Integration with Streaming Mode

Schema specification works seamlessly with streaming mode for large files:

**CLI:**
```bash
# Process 5GB file with schema override
uv run dartfx-unf --streaming --schema schema.json massive_data.csv
```

**Python:**
```python
report = unf_file(
    "5gb_data.csv",
    schema="schema.json",
    streaming=True,
    batch_size=100_000
)
```

The schema is applied to each batch before hashing, ensuring consistent type handling regardless of file size.

## CLI Examples

### Example 1: Type Correction

```bash
# Data has leading zeros that should be integers
uv run dartfx-unf --schema '{"properties": {"id": {"type": "integer"}}}' patients.csv
```

### Example 2: Date Standardization

```bash
# Ensure dates are parsed correctly
uv run dartfx-unf --schema '{"properties": {"birth_date": {"type": "date"}}}' patients.csv
```

### Example 3: Full Schema File

```bash
# Use a comprehensive schema file
cat > demographics_schema.json << 'EOF'
{
  "properties": {
    "patient_id": {"type": "integer"},
    "first_name": {"type": "string"},
    "last_name": {"type": "string"},
    "birth_date": {"type": "date"},
    "registration_date": {"type": "date-time"},
    "age": {"type": "integer"},
    "salary": {"type": "number"},
    "active": {"type": "boolean"}
  }
}
EOF

uv run dartfx-unf --schema demographics_schema.json patients.csv
```

### Example 4: Multiple Files with Shared Schema

```bash
# Apply the same schema to multiple CSV files
uv run dartfx-unf --schema shared_schema.json file1.csv file2.csv file3.csv
```

## Python API Examples

### Basic Usage

```python
from dartfx.unf import unf_file

# With dictionary schema
schema = {
    "order_id": "integer",
    "product_name": "string",
    "quantity": "integer",
    "price": "number"
}
report = unf_file("orders.csv", schema=schema)
print(f"UNF: {report.result.unf}")
```

### With Parameters

```python
from dartfx.unf import unf_file
from dartfx.unf.parameters import UNFParameters

params = UNFParameters(digits=9, hash_bits=256)
schema = {"id": "integer", "name": "string"}

report = unf_file(
    "data.csv",
    params=params,
    schema=schema,
    infer_schema_length=-1  # Scan all rows for type inference on other columns
)
```

### Dataset-Level

```python
from dartfx.unf import unf_dataset

files = ["part_1.csv", "part_2.csv", "part_3.csv"]
schema = {"id": "integer", "date": "date"}

report = unf_dataset(files, schema=schema)
print(f"Dataset UNF: {report.result.unf}")
```

### Accessing Schema in Reports

```python
from dartfx.unf import unf_file

report = unf_file("data.csv", schema={"id": "integer"})

# File-level result
for col in report.result.columns:
    print(f"{col.name}: {col.type} → {col.unf}")

# Export to JSON with schema information
json_report = report.to_json()
```

## Best Practices

1. **Version Your Schemas**: Keep schema files in version control alongside your data processing code.
   ```
   schemas/
   ├── v1.0_demographics.json
   ├── v1.1_demographics.json
   └── v2.0_demographics.json
   ```

2. **Document Type Decisions**: Add comments or a README explaining why certain types were chosen.
   ```json
   {
     "_comment": "id uses leading zeros in raw CSV, must specify as integer",
     "properties": {
       "id": {"type": "integer"}
     }
   }
   ```

3. **Test Schema Changes**: When modifying a schema, verify that UNF fingerprints change as expected.
   ```bash
   uv run dartfx-unf --quiet --schema schema_v1.json data.csv > hash_v1.txt
   uv run dartfx-unf --quiet --schema schema_v2.json data.csv > hash_v2.txt
   diff hash_v1.txt hash_v2.txt  # Should differ if types changed
   ```

4. **Validate Data**: Ensure your data actually matches the schema before calculating fingerprints.
   ```python
   import polars as pl
   df = pl.read_csv("data.csv")
   # Check for values that don't match schema
   ```

5. **Share Schemas**: Distribute schemas with exported data for reproducibility.
   ```bash
   # Package both together
   tar -czf dataset.tar.gz data.csv schema.json
   ```

## Troubleshooting

### "Type mismatch for column X"

**Problem:** You specified a type that doesn't match the inferred type.

**Solution:**
- Check the actual values in your CSV for that column
- Use `pl.read_csv()` to see what types are inferred
- Adjust the schema or clean the data

### "Schema specifies column X which doesn't exist"

**Problem:** Your schema has a column that's not in the data.

**Solution:**
- Remove the column from the schema
- Or verify the column name is spelled correctly

### "Failed to cast column X to type Y"

**Problem:** Type conversion failed (e.g., trying to cast "abc" to integer).

**Solution:**
- Data in that column doesn't match the specified type
- Clean the data before processing
- Or use a different type (e.g., "string" instead of "integer")

### Different UNF with/without schema

**Expected behavior:** Adding a schema *may* change the UNF if types are different.

**Example:**
- Without schema: `"001"` → string → UNF: `ABC...`
- With schema (`"integer"`): `1` (value changed) → UNF: `XYZ...`

This is **correct**. The UNF changed because the normalized value changed.

If you want the UNF to remain the same, don't use a schema, or ensure the schema types match the auto-inferred types.
