from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import initialise_database
from erp_sql_connector import (
    erp_settings_from_env,
    insert_sync_log,
    read_erp_query,
    stage_erp_purchase_orders,
    stage_erp_supplier_prices,
    stage_erp_suppliers,
)


SUPPLIER_QUERY = """
SELECT
    SupplierCode,
    SupplierName,
    SupplierEmail,
    Category,
    IsActive,
    RawStatus,
    SourceUpdatedAt
FROM vw_SupplierPass_ERP_Suppliers
"""

PO_QUERY = """
SELECT
    SupplierCode,
    SupplierName,
    ItemCode,
    ItemDescription,
    PONumber,
    PODate,
    PromisedDate,
    ReceivedDate,
    Quantity,
    UnitPrice,
    TotalValue
FROM vw_SupplierPass_ERP_PurchaseOrders
"""

PRICE_QUERY = """
SELECT
    SupplierCode,
    SupplierName,
    ItemCode,
    ItemDescription,
    Category,
    UnitPrice,
    Currency,
    LeadTimeDays
FROM vw_SupplierPass_ERP_SupplierPrices
"""


if __name__ == "__main__":
    initialise_database()
    settings = erp_settings_from_env()
    batch = pd.Timestamp.now().strftime("erp_sql_%Y%m%d_%H%M%S")
    print(f"Starting ERP SQL sync from {settings.source_name}, batch {batch}")

    try:
        suppliers = read_erp_query(SUPPLIER_QUERY)
        inserted = stage_erp_suppliers(suppliers, settings.source_name, batch)
        insert_sync_log("ERP SQL suppliers to staging", settings.source_name, "Success", len(suppliers), inserted, 0, batch)
        print(f"Supplier rows staged: {inserted}")
    except Exception as exc:
        insert_sync_log("ERP SQL suppliers to staging", settings.source_name, "Failed", 0, 0, 0, str(exc))
        print(f"Supplier sync failed: {exc}")

    try:
        po = read_erp_query(PO_QUERY)
        inserted = stage_erp_purchase_orders(po, settings.source_name, batch)
        insert_sync_log("ERP SQL purchase orders to staging", settings.source_name, "Success", len(po), inserted, 0, batch)
        print(f"PO rows staged: {inserted}")
    except Exception as exc:
        insert_sync_log("ERP SQL purchase orders to staging", settings.source_name, "Failed", 0, 0, 0, str(exc))
        print(f"PO sync failed: {exc}")

    try:
        prices = read_erp_query(PRICE_QUERY)
        inserted = stage_erp_supplier_prices(prices, settings.source_name, batch)
        insert_sync_log("ERP SQL prices to staging", settings.source_name, "Success", len(prices), inserted, 0, batch)
        print(f"Price rows staged: {inserted}")
    except Exception as exc:
        insert_sync_log("ERP SQL prices to staging", settings.source_name, "Failed", 0, 0, 0, str(exc))
        print(f"Price sync failed: {exc}")

    print("Done. Open SupplierPass ERP Sync > Apply Sync to apply staged rows to core tables.")
