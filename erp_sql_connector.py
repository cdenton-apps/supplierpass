"""Read-only ERP SQL connector for SupplierPass.

This is the first production-style connector layer. It is intentionally read-only.
It pulls ERP data into SupplierPass staging tables; it does not write back to the ERP.

Typical flow:

ERP SQL views
    -> erp_sql_connector.py
    -> SupplierPass staging tables
    -> SupplierPass Apply Sync
    -> scorecards/action queue

The connector is designed for local/server deployments where the Microsoft ODBC
Driver and pyodbc are installed. Streamlit Cloud may not support pyodbc, so this
module imports those pieces only when used.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from db import execute, get_engine

load_dotenv()


@dataclass
class ERPConnectionSettings:
    source_name: str
    driver: str
    server: str
    database: str
    trusted_connection: bool
    trust_cert: bool
    username: str = ""
    password: str = ""


def erp_settings_from_env() -> ERPConnectionSettings:
    return ERPConnectionSettings(
        source_name=os.getenv("SUPPLIERPASS_ERP_SOURCE_NAME", "Sage200"),
        driver=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_DRIVER", os.getenv("SUPPLIERPASS_SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")),
        server=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_HOST", ""),
        database=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_DATABASE", ""),
        trusted_connection=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_TRUSTED_CONNECTION", "yes").lower() in {"1", "yes", "true"},
        trust_cert=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_TRUST_CERT", "yes").lower() in {"1", "yes", "true"},
        username=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_USER", ""),
        password=os.getenv("SUPPLIERPASS_ERP_SQLSERVER_PASSWORD", ""),
    )


def erp_connection_url(settings: ERPConnectionSettings | None = None) -> str:
    settings = settings or erp_settings_from_env()
    if not settings.server or not settings.database:
        raise ValueError("ERP SQL Server and database must be configured in .env before running the connector.")

    parts = [
        f"DRIVER={{{settings.driver}}}",
        f"SERVER={settings.server}",
        f"DATABASE={settings.database}",
    ]
    if settings.trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([f"UID={settings.username}", f"PWD={settings.password}"])
    if settings.trust_cert:
        parts.append("TrustServerCertificate=yes")
    else:
        parts.append("Encrypt=yes")

    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))


def get_erp_engine(settings: ERPConnectionSettings | None = None) -> Engine:
    return create_engine(erp_connection_url(settings), future=True, pool_pre_ping=True)


def read_erp_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    with get_erp_engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


def insert_sync_log(sync_name: str, source: str, status: str, rows_read: int = 0, rows_inserted: int = 0, rows_updated: int = 0, message: str = "") -> None:
    # Works with the SQLite SupplierPass schema. SQL Server mode is normally handled by app_v31/v32.
    # This script is intended for SQLite/local pilot first, then can be adapted to stored procedures.
    execute(
        """
        INSERT INTO sync_log (sync_name, source_system, status, rows_read, rows_inserted, rows_updated, message, finished_at)
        VALUES (:sync_name, :source_system, :status, :rows_read, :rows_inserted, :rows_updated, :message, CURRENT_TIMESTAMP)
        """,
        {
            "sync_name": sync_name,
            "source_system": source,
            "status": status,
            "rows_read": rows_read,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
            "message": message,
        },
    )


def stage_erp_suppliers(df: pd.DataFrame, source_name: str, batch: str) -> int:
    inserted = 0
    for _, row in df.iterrows():
        supplier_name = str(row.get("SupplierName", "") or "").strip()
        if not supplier_name:
            continue
        supplier_code = str(row.get("SupplierCode", "") or "").strip()
        supplier_email = str(row.get("SupplierEmail", "") or "").strip().lower()
        supplier_key = "".join(ch for ch in supplier_name.lower() if ch.isalnum())
        execute(
            """
            INSERT INTO stg_erp_suppliers
            (source_system, supplier_code, supplier_name, supplier_key, supplier_email, email_key, category, is_active, raw_status, source_updated_at, sync_batch)
            VALUES (:source_system, :supplier_code, :supplier_name, :supplier_key, :supplier_email, :email_key, :category, :is_active, :raw_status, :source_updated_at, :sync_batch)
            """,
            {
                "source_system": source_name,
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "supplier_key": supplier_key,
                "supplier_email": supplier_email,
                "email_key": supplier_email,
                "category": row.get("Category", ""),
                "is_active": row.get("IsActive", ""),
                "raw_status": row.get("RawStatus", ""),
                "source_updated_at": str(row.get("SourceUpdatedAt", "") or "") or None,
                "sync_batch": batch,
            },
        )
        inserted += 1
    return inserted


def stage_erp_purchase_orders(df: pd.DataFrame, source_name: str, batch: str) -> int:
    inserted = 0
    for _, row in df.iterrows():
        supplier_name = str(row.get("SupplierName", "") or "").strip()
        if not supplier_name:
            continue
        supplier_key = "".join(ch for ch in supplier_name.lower() if ch.isalnum())
        execute(
            """
            INSERT INTO stg_erp_purchase_orders
            (source_system, supplier_code, supplier_name, supplier_key, item_code, item_description, po_number, po_date, promised_date, received_date, quantity, unit_price, total_value, sync_batch)
            VALUES (:source_system, :supplier_code, :supplier_name, :supplier_key, :item_code, :item_description, :po_number, :po_date, :promised_date, :received_date, :quantity, :unit_price, :total_value, :sync_batch)
            """,
            {
                "source_system": source_name,
                "supplier_code": row.get("SupplierCode", ""),
                "supplier_name": supplier_name,
                "supplier_key": supplier_key,
                "item_code": row.get("ItemCode", ""),
                "item_description": row.get("ItemDescription", ""),
                "po_number": row.get("PONumber", ""),
                "po_date": str(row.get("PODate", "") or "") or None,
                "promised_date": str(row.get("PromisedDate", "") or "") or None,
                "received_date": str(row.get("ReceivedDate", "") or "") or None,
                "quantity": float(row.get("Quantity", 0) or 0),
                "unit_price": float(row.get("UnitPrice", 0) or 0),
                "total_value": float(row.get("TotalValue", 0) or 0),
                "sync_batch": batch,
            },
        )
        inserted += 1
    return inserted


def stage_erp_supplier_prices(df: pd.DataFrame, source_name: str, batch: str) -> int:
    inserted = 0
    for _, row in df.iterrows():
        supplier_name = str(row.get("SupplierName", "") or "").strip()
        if not supplier_name:
            continue
        supplier_key = "".join(ch for ch in supplier_name.lower() if ch.isalnum())
        execute(
            """
            INSERT INTO stg_erp_supplier_prices
            (source_system, supplier_code, supplier_name, supplier_key, item_code, item_description, category, unit_price, currency, lead_time_days, sync_batch)
            VALUES (:source_system, :supplier_code, :supplier_name, :supplier_key, :item_code, :item_description, :category, :unit_price, :currency, :lead_time_days, :sync_batch)
            """,
            {
                "source_system": source_name,
                "supplier_code": row.get("SupplierCode", ""),
                "supplier_name": supplier_name,
                "supplier_key": supplier_key,
                "item_code": row.get("ItemCode", ""),
                "item_description": row.get("ItemDescription", ""),
                "category": row.get("Category", ""),
                "unit_price": float(row.get("UnitPrice", 0) or 0),
                "currency": row.get("Currency", "GBP") or "GBP",
                "lead_time_days": float(row.get("LeadTimeDays", 0) or 0),
                "sync_batch": batch,
            },
        )
        inserted += 1
    return inserted
