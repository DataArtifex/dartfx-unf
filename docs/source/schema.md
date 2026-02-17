# Schema Specification Reference

## Overview

The `--schema` option allows you to explicitly define data types for columns in CSV files, overriding Polars' automatic type inference. This is useful when:

- You need consistent type handling across different systems
- CSV data has ambiguous types (e.g., numeric IDs that look like strings)
- You're processing data from external sources with known schemas
- You want to ensure reproducible, deterministic fingerprints
- Your date or datetime data uses non-ISO 8601 formats

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

| JSON Schema Type | Polars Type | Example | Notes |
|---|---|---|---|
| `"integer"` | `Int64` | `42` | Whole numbers only |
| `"number"` | `Float64` | `3.14` | Floating-point values |
| `"string"` | `Utf8` | `"hello"` | Text data |
| `"boolean"` | `Boolean` | `true` / `false` | True/False values |
| `"date"` | `Date` | `"2024-02-16"` | ISO 8601 or custom format |
| `"time"` | `Time` | `"14:30:45"` | ISO 8601 time format |
| `"date-time"` | `Datetime` | `"2024-02-16T14:30:45Z"` | ISO 8601 or custom format |
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

## Date and DateTime Format Specification

By default, `date` and `date-time` columns expect data in ISO 8601 format:
- `date`: `"2024-02-16"` (YYYY-MM-DD)
- `date-time`: `"2024-02-16T14:30:45"` (ISO 8601)

If your data uses a different date or time format, you can specify it using the JSON Schema `format` property.

### Single Format

```json
{
  "properties": {
    "hire_date": {
      "type": "date",
      "format": "dd.mm.yyyy"
    }
  }
}
```

**Supported format strings:**

**Date formats:**
- `yyyy-mm-dd` → `2024-02-16` (ISO, default)
- `dd-mm-yyyy` → `16-02-2024` (day-month-year with dashes)
- `dd.mm.yyyy` → `16.02.2024` (day-month-year with dots)
- `dd/mm/yyyy` → `16/02/2024` (day-month-year with slashes)
- `mm-dd-yyyy` → `02-16-2024` (month-day-year with dashes)
- `mm.dd.yyyy` → `02.16.2024` (month-day-year with dots)
- `mm/dd/yyyy` → `02/16/2024` (month-day-year with slashes)
- `yy-mm-dd` → `24-02-16` (2-digit year)
- `dd-mm-yy` → `16-02-24`
- `mm-dd-yy` → `02-16-24`
- And variants with dots or slashes in place of dashes

**DateTime formats (with time):**
- `dd.mm.yyyy hh:mm:ss` → `16.02.2024 14:30:45`
- `dd-mm-yyyy hh:mm:ss` → `16-02-2024 14:30:45`
- `yyyy-mm-dd hh:mm:ss` → `2024-02-16 14:30:45`
- And variants with different separators

**DateTime formats (ISO T-separator):**
- `dd-mm-yyyyThh:mm:ss` → `16-02-2024T14:30:45`
- `yyyy-mm-ddThh:mm:ss` → `2024-02-16T14:30:45` (ISO default)

**Python Example:**
```python
from dartfx.unf import unf_file

# European date format (DD.MM.YYYY)
schema = {
    "properties": {
        "hire_date": {
            "type": "date",
            "format": "dd.mm.yyyy"
        }
    }
}
report = unf_file("employees.csv", schema=schema)
```

**CLI Example:**
```bash
uv run dartfx-unf --schema '{"properties": {"hire_date": {"type": "date", "format": "dd.mm.yyyy"}}}' employees.csv
```

### Multiple Formats (oneOf)

When your data contains mixed date or datetime formats in the same column, use the JSON Schema `oneOf` property to specify multiple alternatives. The parser will try each format in order until one succeeds:

```json
{
  "properties": {
    "transaction_date": {
      "type": "date",
      "oneOf": [
        {"format": "dd.mm.yyyy"},
        {"format": "dd-mm-yyyy"},
        {"format": "yyyy-mm-dd"}
      ]
    }
  }
}
```

**How it works:**
1. For each row, the parser tries the first format (`dd.mm.yyyy`)
2. If parsing fails, it tries the next format (`dd-mm-yyyy`)
3. Continues until a format succeeds
4. Rows that can't be parsed with any format will cause an error

**Python Example with Mixed Date Formats:**
```python
from dartfx.unf import unf_file

schema = {
    "properties": {
        "date": {
            "type": "date",
            "oneOf": [
                {"format": "dd.mm.yyyy"},     # Try European first
                {"format": "dd-mm-yyyy"},     # Then dash separator
                {"format": "yyyy-mm-dd"}      # Finally ISO (fallback)
            ]
        }
    }
}
report = unf_file("mixed_dates.csv", schema=schema)
```

**CSV Data Example:**
```csv
date
15.03.2024
20-05-2024
2024-02-16
```

All three dates are successfully parsed despite different formats.

**Python Example with Mixed DateTime Formats:**
```python
from dartfx.unf import unf_file

schema = {
    "properties": {
        "timestamp": {
            "type": "date-time",
            "oneOf": [
                {"format": "dd.mm.yyyy hh:mm:ss"},
                {"format": "dd-mm-yyyyThh:mm:ss"},
                {"format": "yyyy-mm-ddThh:mm:ss"}
            ]
        }
    }
}
report = unf_file("mixed_timestamps.csv", schema=schema)
```

**Notes on oneOf:**
- Formats are tried in the order specified
- Use the most specific format first (more likely to succeed)
- Use a general fallback format last (e.g., ISO 8601)
- Empty values or NULL values will still parse as missing/null

## Nullable Types

JSON Schema supports union types that combine multiple type options, including `null`. This is useful for describing optional fields:

**Example Schema:**
```json
{
  "properties": {
    "id": {"type": ["integer", "null"]},
    "name": {"type": ["string", "null"]},
    "salary": {"type": ["number", "null"]}
  }
}
```

When a type specification is a list, `dartfx-unf` automatically extracts the **primary (non-null) type**:

| Schema Type | Primary Type Used | Reason |
|---|---|---|
| `"integer"` | `integer` | Single type, used directly |
| `["integer", "null"]` | `integer` | Filters out `null`, uses `integer` |
| `["null", "string"]` | `string` | Filters out `null`, uses `string` |
| `["null"]` | *(skipped)* | No primary type; column ignored with warning |

**Python Example:**
```python
from dartfx.unf import unf_file

# Schema with nullable types
schema = {
    "id": ["integer", "null"],
    "name": ["string", "null"],
    "salary": ["number", "null"]
}
report = unf_file("data.csv", schema=schema)
```

**CLI Example:**
```bash
uv run dartfx-unf \
  --schema '{"properties": {"id": {"type": ["integer", "null"]}, "name": {"type": ["string", "null"]}}}' \
  data.csv
```

### Order Independence

The order of types in the list doesn't matter:

```json
{"type": ["integer", "null"]}    # ← integer will be used
{"type": ["null", "integer"]}    # ← integer will be used (same result)
```

## Error Handling

### Type Casting Behavior

The tool attempts to cast all columns to their specified schema types. If a cast fails, an error is raised with details about what went wrong:

```
❌ ValueError: Failed to cast column 'id' from String to Int64: ...
```

**Example that causes an error:**
```csv
id,name,value
alpha,Alice,100.5
beta,Bob,200.75
```

With schema:
```json
{
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "value": {"type": "number"}
  }
}
```

This raises an error because `alpha` and `beta` cannot be cast to integers.

### Successful Type Conversions

**Any type to string** (always succeeds):
```csv
id,value
1,100
2,200
```

Schema:
```json
{
  "properties": {
    "id": {"type": "string"},
    "value": {"type": "string"}
  }
}
```

Result: ✓ Success. `1` and `2` become `"1"` and `"2"`.

**String to number** (succeeds if values are numeric):
```csv
id,amount
"1","100.5"
"2","200.75"
```

Schema:
```json
{
  "properties": {
    "id": {"type": "integer"},
    "amount": {"type": "number"}
  }
}
```

Result: ✓ Success, if all values are validly formatted numbers.

**String to date** (succeeds if format matches schema):
```csv
date
2024-02-16
2024-02-17
```

Schema with default format:
```json
{
  "properties": {
    "date": {"type": "date"}
  }
}
```

Result: ✓ Success (ISO 8601 format is default).

With custom format:
```json
{
  "properties": {
    "date": {"type": "date", "format": "dd.mm.yyyy"}
  }
}
```

If the CSV contains `16.02.2024`, it will parse successfully. If it contains `2024-02-16` (ISO format), it will fail.

### Date Format Mismatch Errors

**Problem:** Format in schema doesn't match the actual data.

**Example:**
```csv
date
16.02.2024
17.02.2024
```

Schema says ISO format:
```json
{
  "properties": {
    "date": {"type": "date"}
  }
}
```

Result: ✗ Error: `Failed to cast column 'date' from String to Date`

**Solution:** Update the schema to match your data:
```json
{
  "properties": {
    "date": {"type": "date", "format": "dd.mm.yyyy"}
  }
}
```

### Missing Columns

**Problem:** Your schema has a column that's not in the data.

**Solution:**
- Remove the column from the schema
- Or verify the column name is spelled correctly

### Failed Type Conversion

**Problem:** Type conversion failed (e.g., trying to cast "abc" to integer).

**Solution:**
- Data in that column doesn't match the specified type
- Clean the data before processing
- Or use a different type (e.g., "string" instead of "integer")

### Different UNF with/without Schema

**Expected behavior:** Adding a schema *may* change the UNF if types are different.

**Example:**
- Without schema: `"001"` → string → UNF: `ABC...`
- With schema (`"integer"`): `1` (value changed) → UNF: `XYZ...`

This is **correct**. The UNF changed because the normalized value changed.

If you want the UNF to remain the same, don't use a schema, or ensure the schema types match the auto-inferred types.

## Best Practices

1. **Start Simple**: Only override columns that truly need it.
   ```python
   # Good: Just override the ambiguous 'id' column
   schema = {"properties": {"id": {"type": "integer"}}}
   ```

2. **Use Standards-Compliant Formats**: Use ISO 8601 or well-known regional formats.
   ```python
   # Good: Standard European format
   {"format": "dd.mm.yyyy"}

   # Less ideal: Obscure custom format
   {"format": "d/M/yyyy"}  # Would need to be manually supported
   ```

3. **Validate Your Data**: Before applying a schema, check that your data matches.
   ```python
   import polars as pl
   df = pl.read_csv("data.csv")
   # Manually check a few rows match the schema
   ```

4. **Document Your Schema**: Include comments or a README explaining why the schema is needed.
   ```json
   {
     "description": "Employee records with European date format",
     "properties": {
       "hire_date": {
         "type": "date",
         "format": "dd.mm.yyyy",
         "description": "Hire date in European format DD.MM.YYYY"
       }
     }
   }
   ```

5. **Test Schema Changes**: When modifying a schema, verify that UNF fingerprints change as expected.
   ```bash
   uv run dartfx-unf --quiet --schema schema_v1.json data.csv > hash_v1.txt
   uv run dartfx-unf --quiet --schema schema_v2.json data.csv > hash_v2.txt
   diff hash_v1.txt hash_v2.txt  # Should differ if types changed
   ```

6. **Share Schemas**: Distribute schemas with exported data for reproducibility.
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

### "Could not parse dates with any provided format"

**Problem:** None of the formats in `oneOf` matched the actual data.

**Solution:**
- Add the correct format to the `oneOf` list
- Check data for inconsistencies (e.g., different separators than expected)
- Verify the format string is spelled correctly (lowercase letters: `dd`, `mm`, `yyyy`, `hh`, `mm`, `ss`)

### Different UNF with/without schema

**Expected behavior:** Adding a schema *may* change the UNF if types are different.

**Example:**
- Without schema: `"001"` → string → UNF: `ABC...`
- With schema (`"integer"`): `1` (value changed) → UNF: `XYZ...`

This is **correct**. The UNF changed because the normalized value changed.

If you want the UNF to remain the same, don't use a schema, or ensure the schema types match the auto-inferred types.
