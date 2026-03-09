from pathlib import Path

import pandas as pd
import pyreadstat

# Paths
base_dir = Path(__file__).parent.parent / "tests" / "101"
csv_files = list(base_dir.glob("*.csv"))

print(f"Generating test files from {len(csv_files)} .csv files in {base_dir}")

for csv_file in csv_files:
    # Read the data, ensuring consistent date parsing if necessary
    df = pd.read_csv(csv_file)

    # We attempt to convert any 'dob' columns to datetime just in case,
    # but pandas does an OK job natively
    # Pyreadstat write functions need consistent types.
    if "dob" in df.columns:
        df["dob"] = pd.to_datetime(df["dob"]).dt.date

    # Output paths
    sav_file = csv_file.with_suffix(".sav")
    dta_file = csv_file.with_suffix(".dta")
    xpt_file = csv_file.with_suffix(".xpt")

    # Write SPSS (.sav)
    print(f"Writing {sav_file.name}...")
    pyreadstat.write_sav(df, str(sav_file))

    # Write Stata (.dta)
    print(f"Writing {dta_file.name}...")
    pyreadstat.write_dta(df, str(dta_file))

    # Write SAS Xport (.xpt)
    print(f"Writing {xpt_file.name}...")
    pyreadstat.write_xport(df, str(xpt_file))

print("Done generating statistical test files.")
