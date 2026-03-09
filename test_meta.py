from pathlib import Path

import pyreadstat

path = Path("tests/101/101A.sav")

if path.exists():
    df, meta = pyreadstat.read_sav(path)
    print("Metadata properties:")
    for prop in dir(meta):
        if not prop.startswith("_"):
            try:
                print(f"- {prop}: {getattr(meta, prop)}")
            except Exception:
                pass
