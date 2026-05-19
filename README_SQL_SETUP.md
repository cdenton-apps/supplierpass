# SupplierPass SQL-ready setup

This is the first database foundation for turning SupplierPass from a prototype into a SQL-backed application.

It adds:

- `db.py` database layer
- SQLite demo mode
- SQL Server production-style mode
- SQL schema scripts
- SQL Server reporting views
- database initialisation and connection test tools
- `app_v27_sql_ready.py` to verify the database setup from Streamlit

## Files added

```text
app_v27_sql_ready.py
db.py
.env.example
requirements_sql.txt
sql/schema_sqlite.sql
sql/schema_sqlserver.sql
sql/views_sqlserver.sql
tools/init_database.py
tools/test_database_connection.py
```

## 1. Install dependencies

For SQL-ready mode use:

```bash
pip install -r requirements_sql.txt
```

If using SQL Server, also install the Microsoft ODBC Driver 18 for SQL Server on the machine running SupplierPass.

## 2. SQLite demo mode

Create a `.env` file from `.env.example` and set:

```text
SUPPLIERPASS_DB_MODE=sqlite
SUPPLIERPASS_SQLITE_PATH=data/supplierpass.db
```

Then initialise the database:

```bash
python tools/init_database.py
```

Test the connection:

```bash
python tools/test_database_connection.py
```

Run the SQL-ready test app:

```bash
streamlit run app_v27_sql_ready.py
```

## 3. SQL Server mode

Create a SQL Server database called:

```text
SupplierPass
```

Then set `.env` like this:

```text
SUPPLIERPASS_DB_MODE=sqlserver
SUPPLIERPASS_SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SUPPLIERPASS_SQLSERVER_HOST=YOUR_SQL_SERVER
SUPPLIERPASS_SQLSERVER_DATABASE=SupplierPass
SUPPLIERPASS_SQLSERVER_TRUSTED_CONNECTION=yes
SUPPLIERPASS_SQLSERVER_TRUST_CERT=yes
```

Then run:

```bash
python tools/init_database.py
```

This creates the SQL Server tables from:

```text
sql/schema_sqlserver.sql
```

To add SQL Server reporting views, run this in SQL Server Management Studio:

```text
sql/views_sqlserver.sql
```

## 4. What this does not do yet

This does not yet convert the full `app_v26.py` / `app_v25.py` SupplierPass UI to SQL Server.

It creates the bridge:

```text
SupplierPass UI
→ db.py database layer
→ SQLite or SQL Server
```

The next stage is to move the main SupplierPass pages onto this database layer one screen at a time.

## 5. Recommended next implementation order

1. Move supplier register to `db.py`
2. Move approval queue to `db.py`
3. Move document management to `db.py`
4. Move email centre to `db.py`
5. Move supplier intelligence to `db.py`
6. Add ERP read-only sync tables/views
7. Add sync history and unmatched supplier screens

## 6. Safe ERP integration approach

Start read-only:

```text
ERP SQL views
→ SupplierPass staging tables
→ SupplierPass scorecards/action queue
```

Avoid direct ERP writes at first. Use:

```text
SupplierPass ERP Action Queue
→ export/review
→ ERP update
```

Later this can become an approved API connector.
