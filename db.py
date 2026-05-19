"""SupplierPass database layer.

This module is the first step away from a prototype-only SQLite app.
It allows SupplierPass to run in either:

- SQLite mode for local demos and simple testing
- SQL Server mode for production-style deployments

Configuration is controlled by environment variables or a .env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def get_db_mode() -> str:
    return os.getenv("SUPPLIERPASS_DB_MODE", "sqlite").strip().lower()


def get_sqlite_url() -> str:
    sqlite_path = os.getenv("SUPPLIERPASS_SQLITE_PATH", str(DATA_DIR / "supplierpass.db"))
    return f"sqlite:///{sqlite_path}"


def get_sqlserver_url() -> str:
    """Build a SQL Server SQLAlchemy connection URL.

    Supports either a full ODBC connection string or separate settings.
    For Windows/domain environments, trusted connection is usually easiest.
    """

    explicit = os.getenv("SUPPLIERPASS_SQLSERVER_ODBC_CONNECTION")
    if explicit:
        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(explicit)

    driver = os.getenv("SUPPLIERPASS_SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("SUPPLIERPASS_SQLSERVER_HOST", "localhost")
    database = os.getenv("SUPPLIERPASS_SQLSERVER_DATABASE", "SupplierPass")
    trusted = os.getenv("SUPPLIERPASS_SQLSERVER_TRUSTED_CONNECTION", "yes").lower() in {"1", "yes", "true"}
    trust_cert = os.getenv("SUPPLIERPASS_SQLSERVER_TRUST_CERT", "yes").lower() in {"1", "yes", "true"}

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
    ]

    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        user = os.getenv("SUPPLIERPASS_SQLSERVER_USER", "")
        password = os.getenv("SUPPLIERPASS_SQLSERVER_PASSWORD", "")
        parts.extend([f"UID={user}", f"PWD={password}"])

    if trust_cert:
        parts.append("TrustServerCertificate=yes")
    else:
        parts.append("Encrypt=yes")

    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))


def get_database_url() -> str:
    mode = get_db_mode()
    if mode == "sqlite":
        return get_sqlite_url()
    if mode in {"sqlserver", "mssql"}:
        return get_sqlserver_url()
    raise ValueError(f"Unsupported SUPPLIERPASS_DB_MODE: {mode}")


_ENGINE: Engine | None = None


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        connect_args: dict[str, Any] = {}
        if get_db_mode() == "sqlite":
            connect_args["check_same_thread"] = False
        _ENGINE = create_engine(get_database_url(), future=True, pool_pre_ping=True, connect_args=connect_args)
    return _ENGINE


def read_df(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    with get_engine().connect() as connection:
        return pd.read_sql_query(text(sql), connection, params=params or {})


def execute(sql: str, params: dict[str, Any] | None = None) -> int | None:
    with get_engine().begin() as connection:
        result = connection.execute(text(sql), params or {})
        try:
            return result.lastrowid
        except Exception:
            return None


def execute_many(sql: str, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    with get_engine().begin() as connection:
        connection.execute(text(sql), rows)


def run_sql_file(path: str | Path) -> None:
    """Run a SQL file split by GO or semicolon-style batches.

    SQL Server scripts often use GO separators. SQLite scripts usually use
    semicolons. This helper supports both well enough for our setup scripts.
    """

    path = Path(path)
    script = path.read_text(encoding="utf-8")
    batches: list[str] = []
    current: list[str] = []
    for line in script.splitlines():
        if line.strip().upper() == "GO":
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    final_batch = "\n".join(current).strip()
    if final_batch:
        batches.append(final_batch)

    with get_engine().begin() as connection:
        for batch in batches:
            if get_db_mode() == "sqlite":
                for statement in [s.strip() for s in batch.split(";") if s.strip()]:
                    connection.execute(text(statement))
            else:
                connection.execute(text(batch))


def initialise_database() -> None:
    mode = get_db_mode()
    schema = ROOT_DIR / "sql" / ("schema_sqlserver.sql" if mode in {"sqlserver", "mssql"} else "schema_sqlite.sql")
    run_sql_file(schema)


def connection_summary() -> dict[str, str]:
    mode = get_db_mode()
    if mode == "sqlite":
        return {"mode": "SQLite", "database": os.getenv("SUPPLIERPASS_SQLITE_PATH", str(DATA_DIR / "supplierpass.db"))}
    return {
        "mode": "SQL Server",
        "server": os.getenv("SUPPLIERPASS_SQLSERVER_HOST", "localhost"),
        "database": os.getenv("SUPPLIERPASS_SQLSERVER_DATABASE", "SupplierPass"),
    }
