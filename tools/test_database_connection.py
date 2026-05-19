from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import connection_summary, read_df


if __name__ == "__main__":
    print("Testing SupplierPass database connection...")
    print(connection_summary())
    df = read_df("SELECT 1 AS connection_ok")
    print(df.to_string(index=False))
    print("Connection OK.")
