# UNF v6 Combination Algorithm: Implementation Variance Report

**Date:** 2026-03-09
**Author:** Pascal (DataArtifex / dartfx-unf)
**Status:** Resolved — dartfx-unf updated to match canonical Java behaviour
**Applies to:** UNF v6 Specification §IIa (Combining UNFs for data frames)

---

## 1. Executive Summary

During cross-validation between the Python `dartfx-unf` implementation and the canonical Java `UNF-dataverse` implementation, a discrepancy was found in how **file-level UNFs** are computed from individual column UNFs.

Both implementations produce **identical column-level UNFs**, confirming correct normalization and hashing at the vector level. However, the file-level (combined) UNFs differ due to a subtle difference in how the UNF strings are preprocessed before the combination step defined in §IIa of the specification.

**Root cause:** The Java reference implementation **strips the `UNF:6:` header prefix** from each column UNF before sorting and hashing them into the combined value. The Python implementation was using the full printable UNF strings.

The `dartfx-unf` Python implementation has been updated to match the Java behaviour, restoring full interoperability.

---

## 2. Background

### 2.1 The UNF v6 Combination Algorithm (Spec §IIa)

The specification describes combining column UNFs into a file-level UNF as follows:

> *"Sort the **printable UTF-8 representations of the individual UNFs** in the POSIX locale sort order. Apply the UNF algorithm to the resulting vector of character strings."*

This procedure ensures that the file-level UNF is **invariant to column order** — rearranging columns should not change the result.

### 2.2 Test Data

Four CSV files (101A–101D) were used for cross-validation. Files A and B contain the same data with columns in different order; likewise for C and D:

| File | Column Order |
|------|-------------|
| 101A | id, name, sex, dob, income |
| 101B | id, name, income, dob, sex |
| 101C | id, name, sex, dob, income (different data) |
| 101D | id, name, income, dob, sex (different data) |

---

## 3. The Discrepancy

### 3.1 Observed Results

Both implementations produce identical column UNFs. For example, file 101A:

| Column | UNF (both implementations) |
|--------|---------------------------|
| id     | `UNF:6:AvELPR5QTaBbnq6S22Msow==` |
| name   | `UNF:6:G3RHxSQPXELRGHIJ+FV6qA==` |
| sex    | `UNF:6:VSDSXcRD7ShBmQqv1WR9EA==` |
| dob    | `UNF:6:PH+jFA4u+yJSs1sIw64dyw==` |
| income | `UNF:6:v/5E9kHI79TVvlGYinvxTQ==` |

However, the file-level UNFs differ:

| File | Python (before fix) | Java (canonical) |
|------|---------------------|------------------|
| 101A | `UNF:6:/iH9nCE4fZqn1rBrrsOc7w==` | `UNF:6:kBkE4q7GbowX/3tKvDSEWg==` |
| 101B | `UNF:6:/iH9nCE4fZqn1rBrrsOc7w==` | `UNF:6:kBkE4q7GbowX/3tKvDSEWg==` |
| 101C | `UNF:6:jBDVQfqmx+NZ9nuRqeSn7w==` | `UNF:6:grJwrCwbQzxeZQ5fNkeApw==` |
| 101D | `UNF:6:jBDVQfqmx+NZ9nuRqeSn7w==` | `UNF:6:grJwrCwbQzxeZQ5fNkeApw==` |

Both implementations correctly produce order-independent results (A=B, C=D), confirming the sort step is correct. The difference lies in **what is being sorted and hashed**.

### 3.2 Root Cause Analysis

The Java implementation's `UnfDigest.addUNFs()` method (in `UnfDigest.java`, lines 483–514) processes UNF strings as follows:

```java
// Java: strips the "UNF:6:" prefix, keeps only the base64 hash
for (String str : b64) {
    String tosplit = ":";
    String res[] = str.split(tosplit);
    if (res.length >= 3 && str.startsWith("UNF:")) {
        combo.add(res[res.length - 1].trim());  // ← last segment only
    } else {
        combo.add(res[0].trim());
    }
}
Collections.sort(combo);
String fin = unfV(sortedb64, DEF_CDGTS, null);
```

The Python implementation was using the full strings:

```python
# Python (before fix): uses full UNF strings
sorted_unfs = sorted(unf_strings)  # "UNF:6:hash==" strings
for unf_str in sorted_unfs:
    concatenated += unf_str.encode("utf-8") + b"\n\x00"
```

This means the hash input differs:

| Implementation | Hash input for each element |
|---------------|---------------------------|
| **Java** | `AvELPR5QTaBbnq6S22Msow==\n\0` |
| **Python** (before fix) | `UNF:6:AvELPR5QTaBbnq6S22Msow==\n\0` |

---

## 4. Specification Ambiguity

The spec §IIa states:

> *"Sort the printable UTF-8 representations of the individual UNFs..."*

The phrase "printable UTF-8 representations of the individual UNFs" is ambiguous:

- **Interpretation A (literal):** The "printable representation" is the full string including the header, e.g., `UNF:6:AvELPR5QTaBbnq6S22Msow==`. This is what one sees when printing a UNF.
- **Interpretation B (Java implementation):** Only the base64 hash component is used, as the `UNF:6:` prefix is constant across all columns and carries no per-column discriminating information.

### 4.1 Practical Impact

For **default parameters** (`UNF:6:`), stripping the prefix does not affect **sort order** — all strings share the same prefix, so sorting with or without it produces the same ordering. The difference is only in the hash input.

For **non-default parameters** (e.g., `UNF:6:N9:`), stripping the prefix could theoretically change sort order if different columns used different parameter sets, but this scenario is not supported in practice — all columns in a data frame share the same parameters.

---

## 5. Resolution

### 5.1 Decision

The `dartfx-unf` Python implementation has been updated to **match the Java reference behaviour** (strip the header before combining). This is a pragmatic decision based on:

1. **Interoperability:** The Java implementation is the canonical reference used by the Dataverse ecosystem. All existing UNF signatures in Dataverse repositories were computed using this approach.
2. **Cross-validation:** The primary purpose of having multiple implementations is to validate each other. Using different combination algorithms defeats this purpose.
3. **Ecosystem consistency:** Any new implementation should be able to reproduce UNFs generated by the reference implementation.

### 5.2 Code Change

A new helper function `_strip_unf_header()` was added to `hasher.py`, and `combine_unfs()` was updated to strip headers before sorting and hashing. The change is fully documented with references to the Java implementation.

### 5.3 Verified Results (After Fix)

| File | Python (after fix) | Java (canonical) | Match |
|------|-------------------|------------------|-------|
| 101A | `UNF:6:kBkE4q7GbowX/3tKvDSEWg==` | `UNF:6:kBkE4q7GbowX/3tKvDSEWg==` | ✅ |
| 101B | `UNF:6:kBkE4q7GbowX/3tKvDSEWg==` | `UNF:6:kBkE4q7GbowX/3tKvDSEWg==` | ✅ |
| 101C | `UNF:6:grJwrCwbQzxeZQ5fNkeApw==` | `UNF:6:grJwrCwbQzxeZQ5fNkeApw==` | ✅ |
| 101D | `UNF:6:grJwrCwbQzxeZQ5fNkeApw==` | `UNF:6:grJwrCwbQzxeZQ5fNkeApw==` | ✅ |

---

## 6. Recommendations for the UNF Specification

### 6.1 Clarify §IIa Combination Wording

The specification should explicitly state whether the full printable UNF string (with header) or only the base64 hash component is used in the combination step. Suggested replacement:

> **Current:**
> *"Sort the printable UTF-8 representations of the individual UNFs in the POSIX locale sort order. Apply the UNF algorithm to the resulting vector of character strings."*
>
> **Proposed:**
> *"Extract the base64-encoded hash component from each individual UNF (i.e., strip the `UNF:` prefix, version number, and any parameter tokens). Sort these extracted hash strings in POSIX locale order. Apply the UNF algorithm to the resulting vector of character strings, treating each stripped hash as a string value."*

### 6.2 Add Cross-Validation Test Vectors for Combination

The existing official test vectors (in `unf_examples.txt`) only cover individual column UNFs. Adding test vectors for the **combination step** would help implementers catch this kind of discrepancy. Suggested additions:

```
# §IIa – File-level UNF combination test vectors
#
# Input columns (5 variables, default parameters):
#   UNF:6:AvELPR5QTaBbnq6S22Msow==
#   UNF:6:G3RHxSQPXELRGHIJ+FV6qA==
#   UNF:6:VSDSXcRD7ShBmQqv1WR9EA==
#   UNF:6:PH+jFA4u+yJSs1sIw64dyw==
#   UNF:6:v/5E9kHI79TVvlGYinvxTQ==
#
# Step 1: Strip headers → base64 hashes only
# Step 2: Sort in POSIX order:
#   AvELPR5QTaBbnq6S22Msow==
#   G3RHxSQPXELRGHIJ+FV6qA==
#   PH+jFA4u+yJSs1sIw64dyw==
#   VSDSXcRD7ShBmQqv1WR9EA==
#   v/5E9kHI79TVvlGYinvxTQ==
#
# Step 3: Apply UNF algorithm to sorted strings
# Expected file-level UNF: UNF:6:kBkE4q7GbowX/3tKvDSEWg==
```

### 6.3 Establish an Interoperability Test Suite

A shared, language-agnostic test suite (e.g., a JSON file with inputs and expected outputs at each level — normalization, column, file, dataset) would greatly facilitate cross-validation between implementations. The `unf6.schema.json` schema is a good foundation for this.

---

## 7. References

- [UNF v6 Specification](https://guides.dataverse.org/en/latest/developers/unf/unf-v6.html)
- [Java Reference Implementation (IQSS/UNF)](https://github.com/IQSS/UNF) — `UnfDigest.addUNFs()` method
- [Dataverse UNF Fork](https://github.com/IQSS/dataverse) — production usage
- [dartfx-unf Python Implementation](https://github.com/DataArtifex/dartfx-unf) — `hasher.combine_unfs()`
- Altman, M. (2008). *A Fingerprint Method for Verification of Scientific Data*. Springer Verlag.
