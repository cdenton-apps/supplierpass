import pandas as pd
import streamlit as st

# Reuse v30 SQL-backed product, then add ERP sync foundation/staging.
source_file = "app_v30_sql_intelligence.py"
source_code = open(source_file, "r", encoding="utf-8").read()
definitions = source_code.rsplit("\ninitialise_database()", 1)[0]
namespace = {"__file__": source_file}
exec(compile(definitions, source_file, "exec"), namespace)

APP_VERSION = "v0.31 SQL-backed ERP Sync Foundation"

connection_summary = namespace["connection_summary"]
execute = namespace["execute"]
initialise_database = namespace["initialise_database"]
read_df = namespace["read_df"]
normalise_name = namespace["normalise_name"]
normalise_email = namespace["normalise_email"]
q = namespace["q"]
cols = namespace["cols"]
supplier_df = namespace["supplier_df"]
find_duplicate = namespace["find_duplicate"]
show_df = namespace["show_df"]
hero = namespace["hero"]
kpi = namespace["kpi"]
add_supplier_screen = namespace["add_supplier_screen"]
onboarding_screen = namespace["onboarding_screen"]
approval_queue_screen = namespace["approval_queue_screen"]
preferred_screen = namespace["preferred_screen"]
erp_action_queue_screen = namespace["erp_action_queue_screen"]
demo_data_screen = namespace["demo_data_screen"]
database_screen = namespace["database_screen"]
documents_screen = namespace["documents_screen"]
email_centre_screen = namespace["email_centre_screen"]
sql_documents_demo_screen = namespace["sql_documents_demo_screen"]
data_uploads_screen = namespace["data_uploads_screen"]
intelligence_screen = namespace["intelligence_screen"]
sql_intelligence_demo_screen = namespace["sql_intelligence_demo_screen"]
intelligence_df = namespace["intelligence_df"]
resolve_supplier_for_import = namespace["resolve_supplier_for_import"]
it = namespace["it"]
ic = namespace["ic"]


def is_sqlserver() -> bool:
    return connection_summary().get("mode") == "SQL Server"


def stg(name: str) -> str:
    if is_sqlserver():
        return {
            "suppliers": "dbo.StgERPSuppliers",
            "po": "dbo.StgERPPurchaseOrders",
            "prices": "dbo.StgERPSupplierPrices",
            "sync_log": "dbo.SyncLog",
        }[name]
    return {
        "suppliers": "stg_erp_suppliers",
        "po": "stg_erp_purchase_orders",
        "prices": "stg_erp_supplier_prices",
        "sync_log": "sync_log",
    }[name]


def ensure_erp_sync_schema():
    if is_sqlserver():
        execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='StgERPSuppliers' AND schema_id=SCHEMA_ID('dbo'))
        CREATE TABLE dbo.StgERPSuppliers (
            StagingID int IDENTITY(1,1) PRIMARY KEY,
            SourceSystem nvarchar(100) NULL,
            SupplierCode nvarchar(50) NULL,
            SupplierName nvarchar(255) NULL,
            SupplierKey nvarchar(255) NULL,
            SupplierEmail nvarchar(255) NULL,
            EmailKey nvarchar(255) NULL,
            Category nvarchar(100) NULL,
            IsActive nvarchar(50) NULL,
            RawStatus nvarchar(100) NULL,
            SourceUpdatedAt datetime2 NULL,
            ImportedAt datetime2 NOT NULL DEFAULT sysdatetime(),
            SyncBatch nvarchar(100) NULL
        )
        """)
        execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='StgERPPurchaseOrders' AND schema_id=SCHEMA_ID('dbo'))
        CREATE TABLE dbo.StgERPPurchaseOrders (
            StagingID int IDENTITY(1,1) PRIMARY KEY,
            SourceSystem nvarchar(100) NULL,
            SupplierCode nvarchar(50) NULL,
            SupplierName nvarchar(255) NULL,
            SupplierKey nvarchar(255) NULL,
            ItemCode nvarchar(100) NULL,
            ItemDescription nvarchar(500) NULL,
            PONumber nvarchar(100) NULL,
            PODate date NULL,
            PromisedDate date NULL,
            ReceivedDate date NULL,
            Quantity decimal(18,4) NULL,
            UnitPrice decimal(18,4) NULL,
            TotalValue decimal(18,2) NULL,
            ImportedAt datetime2 NOT NULL DEFAULT sysdatetime(),
            SyncBatch nvarchar(100) NULL
        )
        """)
        execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='StgERPSupplierPrices' AND schema_id=SCHEMA_ID('dbo'))
        CREATE TABLE dbo.StgERPSupplierPrices (
            StagingID int IDENTITY(1,1) PRIMARY KEY,
            SourceSystem nvarchar(100) NULL,
            SupplierCode nvarchar(50) NULL,
            SupplierName nvarchar(255) NULL,
            SupplierKey nvarchar(255) NULL,
            ItemCode nvarchar(100) NULL,
            ItemDescription nvarchar(500) NULL,
            Category nvarchar(100) NULL,
            UnitPrice decimal(18,4) NULL,
            Currency nvarchar(10) NULL,
            LeadTimeDays decimal(18,2) NULL,
            ImportedAt datetime2 NOT NULL DEFAULT sysdatetime(),
            SyncBatch nvarchar(100) NULL
        )
        """)
    else:
        execute("""
        CREATE TABLE IF NOT EXISTS stg_erp_suppliers (
            staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system TEXT,
            supplier_code TEXT,
            supplier_name TEXT,
            supplier_key TEXT,
            supplier_email TEXT,
            email_key TEXT,
            category TEXT,
            is_active TEXT,
            raw_status TEXT,
            source_updated_at TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_batch TEXT
        )
        """)
        execute("""
        CREATE TABLE IF NOT EXISTS stg_erp_purchase_orders (
            staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system TEXT,
            supplier_code TEXT,
            supplier_name TEXT,
            supplier_key TEXT,
            item_code TEXT,
            item_description TEXT,
            po_number TEXT,
            po_date TEXT,
            promised_date TEXT,
            received_date TEXT,
            quantity REAL,
            unit_price REAL,
            total_value REAL,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_batch TEXT
        )
        """)
        execute("""
        CREATE TABLE IF NOT EXISTS stg_erp_supplier_prices (
            staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_system TEXT,
            supplier_code TEXT,
            supplier_name TEXT,
            supplier_key TEXT,
            item_code TEXT,
            item_description TEXT,
            category TEXT,
            unit_price REAL,
            currency TEXT,
            lead_time_days REAL,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_batch TEXT
        )
        """)


def table_cols(kind: str) -> dict[str, str]:
    if is_sqlserver():
        common = {
            "staging_id": "StagingID", "source_system": "SourceSystem", "supplier_code": "SupplierCode",
            "supplier_name": "SupplierName", "supplier_key": "SupplierKey", "supplier_email": "SupplierEmail",
            "email_key": "EmailKey", "category": "Category", "is_active": "IsActive", "raw_status": "RawStatus",
            "source_updated_at": "SourceUpdatedAt", "imported_at": "ImportedAt", "sync_batch": "SyncBatch",
            "item_code": "ItemCode", "item_description": "ItemDescription", "po_number": "PONumber", "po_date": "PODate",
            "promised_date": "PromisedDate", "received_date": "ReceivedDate", "quantity": "Quantity", "unit_price": "UnitPrice",
            "total_value": "TotalValue", "currency": "Currency", "lead_time_days": "LeadTimeDays",
        }
    else:
        common = {
            "staging_id": "staging_id", "source_system": "source_system", "supplier_code": "supplier_code",
            "supplier_name": "supplier_name", "supplier_key": "supplier_key", "supplier_email": "supplier_email",
            "email_key": "email_key", "category": "category", "is_active": "is_active", "raw_status": "raw_status",
            "source_updated_at": "source_updated_at", "imported_at": "imported_at", "sync_batch": "sync_batch",
            "item_code": "item_code", "item_description": "item_description", "po_number": "po_number", "po_date": "po_date",
            "promised_date": "promised_date", "received_date": "received_date", "quantity": "quantity", "unit_price": "unit_price",
            "total_value": "total_value", "currency": "currency", "lead_time_days": "lead_time_days",
        }
    return common


def sync_log(sync_name, source, status, rows_read=0, rows_inserted=0, rows_updated=0, message=""):
    if is_sqlserver():
        execute(
            """
            INSERT INTO dbo.SyncLog (SyncName, SourceSystem, Status, RowsRead, RowsInserted, RowsUpdated, Message, FinishedAt)
            VALUES (:sync_name, :source, :status, :rows_read, :rows_inserted, :rows_updated, :message, sysdatetime())
            """,
            {"sync_name": sync_name, "source": source, "status": status, "rows_read": rows_read, "rows_inserted": rows_inserted, "rows_updated": rows_updated, "message": message},
        )
    else:
        execute(
            """
            INSERT INTO sync_log (sync_name, source_system, status, rows_read, rows_inserted, rows_updated, message, finished_at)
            VALUES (:sync_name, :source, :status, :rows_read, :rows_inserted, :rows_updated, :message, CURRENT_TIMESTAMP)
            """,
            {"sync_name": sync_name, "source": source, "status": status, "rows_read": rows_read, "rows_inserted": rows_inserted, "rows_updated": rows_updated, "message": message},
        )


def map_columns(df, mode):
    cols = df.columns.tolist()
    def select(label, guesses, required=False):
        options = cols if required else [""] + cols
        idx = 0
        for g in guesses:
            if g in options:
                idx = options.index(g)
                break
        return st.selectbox(label, options, index=idx, key=f"erp_{mode}_{label}")
    a, b, c = st.columns(3)
    mapping = {}
    with a:
        mapping["Supplier Name"] = select("Supplier Name", ["SupplierName", "Supplier Name", "Supplier", "Vendor", "Vendor Name"], True)
        mapping["Supplier Code"] = select("Supplier Code", ["SupplierCode", "Supplier Code", "AccountNumber", "Vendor No.", "Code"])
        mapping["Supplier Email"] = select("Supplier Email", ["Email", "SupplierEmail", "Email Address"])
        mapping["Category"] = select("Category", ["Category", "Product Group", "Supplier Category"])
    with b:
        mapping["Item Code"] = select("Item Code", ["ItemCode", "Item Code", "StockCode", "Product Code", "Code"])
        mapping["Item Description"] = select("Item Description", ["ItemDescription", "Item Description", "Description"])
        mapping["PO Number"] = select("PO Number", ["PONumber", "PO Number", "DocumentNo", "Order Number"])
        mapping["PO Date"] = select("PO Date", ["PODate", "PO Date", "Order Date", "Date"])
    with c:
        mapping["Promised Date"] = select("Promised Date", ["PromisedDate", "Promised Date", "Due Date", "RequestedDeliveryDate"])
        mapping["Received Date"] = select("Received Date", ["ReceivedDate", "Received Date", "Receipt Date", "GRN Date"])
        mapping["Quantity"] = select("Quantity", ["Quantity", "Qty", "Order Quantity"])
        mapping["Unit Price"] = select("Unit Price", ["UnitPrice", "Unit Price", "Price", "Net Price"])
        mapping["Total Value"] = select("Total Value", ["TotalValue", "Total Value", "Line Total", "Net Value"])
        mapping["Lead Time Days"] = select("Lead Time Days", ["LeadTimeDays", "Lead Time", "Lead Time Days"])
    return mapping


def get_val(row, mapping, label, default=""):
    col = mapping.get(label, "")
    if col and col in row.index and pd.notna(row[col]):
        return row[col]
    return default


def import_to_staging(data, mapping, mode, source_system, batch):
    c = table_cols(mode)
    inserted = 0
    for _, row in data.iterrows():
        name = str(get_val(row, mapping, "Supplier Name", "")).strip()
        if not name:
            continue
        code = str(get_val(row, mapping, "Supplier Code", "")).strip()
        email = str(get_val(row, mapping, "Supplier Email", "")).strip()
        category = str(get_val(row, mapping, "Category", "")).strip()
        base = {"source": source_system, "code": code, "name": name, "supplier_key": normalise_name(name), "email": email, "email_key": normalise_email(email), "category": category, "batch": batch}
        if mode == "suppliers":
            execute(
                f"""
                INSERT INTO {stg('suppliers')}
                ({c['source_system']}, {c['supplier_code']}, {c['supplier_name']}, {c['supplier_key']}, {c['supplier_email']}, {c['email_key']}, {c['category']}, {c['is_active']}, {c['raw_status']}, {c['sync_batch']})
                VALUES (:source, :code, :name, :supplier_key, :email, :email_key, :category, 'Active', 'Imported', :batch)
                """,
                base,
            )
        elif mode == "po":
            qty = pd.to_numeric(get_val(row, mapping, "Quantity", 0), errors="coerce")
            unit = pd.to_numeric(get_val(row, mapping, "Unit Price", 0), errors="coerce")
            total = pd.to_numeric(get_val(row, mapping, "Total Value", 0), errors="coerce")
            if pd.isna(total) or float(total) == 0:
                total = (0 if pd.isna(qty) else float(qty)) * (0 if pd.isna(unit) else float(unit))
            values = base | {
                "item_code": str(get_val(row, mapping, "Item Code", "")), "item_description": str(get_val(row, mapping, "Item Description", "")),
                "po_number": str(get_val(row, mapping, "PO Number", "")), "po_date": str(get_val(row, mapping, "PO Date", "")) or None,
                "promised_date": str(get_val(row, mapping, "Promised Date", "")) or None, "received_date": str(get_val(row, mapping, "Received Date", "")) or None,
                "quantity": 0 if pd.isna(qty) else float(qty), "unit_price": 0 if pd.isna(unit) else float(unit), "total_value": 0 if pd.isna(total) else float(total),
            }
            execute(
                f"""
                INSERT INTO {stg('po')}
                ({c['source_system']}, {c['supplier_code']}, {c['supplier_name']}, {c['supplier_key']}, {c['item_code']}, {c['item_description']}, {c['po_number']}, {c['po_date']}, {c['promised_date']}, {c['received_date']}, {c['quantity']}, {c['unit_price']}, {c['total_value']}, {c['sync_batch']})
                VALUES (:source, :code, :name, :supplier_key, :item_code, :item_description, :po_number, :po_date, :promised_date, :received_date, :quantity, :unit_price, :total_value, :batch)
                """,
                values,
            )
        elif mode == "prices":
            price = pd.to_numeric(get_val(row, mapping, "Unit Price", 0), errors="coerce")
            lead = pd.to_numeric(get_val(row, mapping, "Lead Time Days", None), errors="coerce")
            values = base | {
                "item_code": str(get_val(row, mapping, "Item Code", "")), "item_description": str(get_val(row, mapping, "Item Description", "")),
                "unit_price": 0 if pd.isna(price) else float(price), "lead_time_days": None if pd.isna(lead) else float(lead), "currency": "GBP",
            }
            execute(
                f"""
                INSERT INTO {stg('prices')}
                ({c['source_system']}, {c['supplier_code']}, {c['supplier_name']}, {c['supplier_key']}, {c['item_code']}, {c['item_description']}, {c['category']}, {c['unit_price']}, {c['currency']}, {c['lead_time_days']}, {c['sync_batch']})
                VALUES (:source, :code, :name, :supplier_key, :item_code, :item_description, :category, :unit_price, :currency, :lead_time_days, :batch)
                """,
                values,
            )
        inserted += 1
    sync_log(f"Stage {mode}", source_system, "Success", len(data), inserted, 0, f"Batch {batch}")
    return inserted


def sync_staging_to_core():
    sc = cols()
    c = table_cols("suppliers")
    inserted = updated = 0

    suppliers = read_df(f"SELECT * FROM {stg('suppliers')}")
    for _, r in suppliers.iterrows():
        name = r[c["supplier_name"]]
        email = r.get(c["supplier_email"], "") or ""
        match = find_duplicate(name, email)
        if match.empty:
            execute(
                f"""
                INSERT INTO {q('suppliers')}
                ({sc['supplier_code']}, {sc['supplier_name']}, {sc['supplier_key']}, {sc['supplier_email']}, {sc['email_key']}, {sc['category']}, {sc['approval_status']}, {sc['app_status']}, {sc['risk_level']}, {sc['notes']})
                VALUES (:code, :name, :supplier_key, :email, :email_key, :category, 'Pending', 'Active', 'Medium', 'Created from ERP staging sync')
                """,
                {"code": r.get(c["supplier_code"], ""), "name": name, "supplier_key": normalise_name(name), "email": email, "email_key": normalise_email(email), "category": r.get(c["category"], "")},
            )
            inserted += 1
        else:
            sid = int(match.iloc[0]["supplier_id"])
            execute(
                f"""
                UPDATE {q('suppliers')}
                SET {sc['supplier_code']}=:code, {sc['supplier_email']}=:email, {sc['email_key']}=:email_key, {sc['category']}=:category
                WHERE {sc['supplier_id']}=:supplier_id
                """,
                {"code": r.get(c["supplier_code"], ""), "email": email, "email_key": normalise_email(email), "category": r.get(c["category"], ""), "supplier_id": sid},
            )
            updated += 1

    po = read_df(f"SELECT * FROM {stg('po')}")
    po_inserted = 0
    for _, r in po.iterrows():
        name = r[c["supplier_name"]]
        sid = resolve_supplier_for_import(name, "", "")
        supplier = supplier_df()
        srow = supplier[supplier["supplier_id"] == sid].iloc[0]
        execute(
            f"""
            INSERT INTO {it('po_history')}
            ({ic('supplier_id')}, {ic('supplier_name')}, {ic('supplier_key')}, {ic('item_code')}, {ic('item_description')}, {ic('po_number')}, {ic('po_date')}, {ic('promised_date')}, {ic('received_date')}, {ic('quantity')}, {ic('unit_price')}, {ic('total_value')}, {ic('source_file')})
            VALUES (:supplier_id, :supplier_name, :supplier_key, :item_code, :item_description, :po_number, :po_date, :promised_date, :received_date, :quantity, :unit_price, :total_value, 'erp_staging_sync')
            """,
            {"supplier_id": sid, "supplier_name": name, "supplier_key": srow["supplier_key"], "item_code": r.get(c["item_code"], ""), "item_description": r.get(c["item_description"], ""), "po_number": r.get(c["po_number"], ""), "po_date": r.get(c["po_date"], None), "promised_date": r.get(c["promised_date"], None), "received_date": r.get(c["received_date"], None), "quantity": r.get(c["quantity"], 0) or 0, "unit_price": r.get(c["unit_price"], 0) or 0, "total_value": r.get(c["total_value"], 0) or 0},
        )
        po_inserted += 1

    prices = read_df(f"SELECT * FROM {stg('prices')}")
    price_inserted = 0
    for _, r in prices.iterrows():
        name = r[c["supplier_name"]]
        sid = resolve_supplier_for_import(name, "", r.get(c["category"], ""))
        supplier = supplier_df()
        srow = supplier[supplier["supplier_id"] == sid].iloc[0]
        execute(
            f"""
            INSERT INTO {it('supplier_prices')}
            ({ic('supplier_id')}, {ic('supplier_name')}, {ic('supplier_key')}, {ic('item_code')}, {ic('item_description')}, {ic('category')}, {ic('unit_price')}, {ic('currency')}, {ic('lead_time_days')}, {ic('source_file')})
            VALUES (:supplier_id, :supplier_name, :supplier_key, :item_code, :item_description, :category, :unit_price, :currency, :lead_time_days, 'erp_staging_sync')
            """,
            {"supplier_id": sid, "supplier_name": name, "supplier_key": srow["supplier_key"], "item_code": r.get(c["item_code"], ""), "item_description": r.get(c["item_description"], ""), "category": r.get(c["category"], ""), "unit_price": r.get(c["unit_price"], 0) or 0, "currency": r.get(c["currency"], "GBP") or "GBP", "lead_time_days": r.get(c["lead_time_days"], None)},
        )
        price_inserted += 1

    sync_log("Apply staging to SupplierPass", "ERP Staging", "Success", len(suppliers) + len(po) + len(prices), inserted + po_inserted + price_inserted, updated, "Applied staging to core tables")
    return inserted, updated, po_inserted, price_inserted


def staging_counts():
    return {
        "ERP suppliers": len(read_df(f"SELECT * FROM {stg('suppliers')}")),
        "ERP PO rows": len(read_df(f"SELECT * FROM {stg('po')}")),
        "ERP price rows": len(read_df(f"SELECT * FROM {stg('prices')}")),
    }


def erp_sync_screen():
    hero("ERP Sync", "Staging, sync history and unmatched supplier workflow for future Sage/ERP integration.")
    ensure_erp_sync_schema()
    tab_status, tab_stage, tab_apply, tab_unmatched, tab_history, tab_design = st.tabs(["Status", "Stage Data", "Apply Sync", "Unmatched", "Sync History", "Design Notes"])

    with tab_status:
        st.subheader("Current staging counts")
        counts = staging_counts()
        a, b, c = st.columns(3)
        with a: kpi("ERP suppliers", counts["ERP suppliers"], "staging rows")
        with b: kpi("ERP PO rows", counts["ERP PO rows"], "staging rows")
        with c: kpi("ERP price rows", counts["ERP price rows"], "staging rows")
        if st.button("Initialise ERP sync tables"):
            ensure_erp_sync_schema()
            st.success("ERP sync tables ready.")

    with tab_stage:
        mode_label = st.radio("Data type", ["ERP supplier master", "ERP purchase/receipt history", "ERP supplier prices"], horizontal=True)
        mode = {"ERP supplier master": "suppliers", "ERP purchase/receipt history": "po", "ERP supplier prices": "prices"}[mode_label]
        source = st.text_input("Source system", value="Sage200")
        batch = st.text_input("Batch name", value=f"manual_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}")
        file = st.file_uploader("CSV export", type=["csv"], key=f"stage_{mode}")
        if file:
            data = pd.read_csv(file)
            st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            mapping = map_columns(data, mode)
            if st.button("Load to ERP staging", type="primary"):
                inserted = import_to_staging(data, mapping, mode, source, batch)
                st.success(f"Loaded {inserted} staging row(s).")
                st.rerun()

    with tab_apply:
        st.warning("This applies staged ERP rows into SupplierPass core tables. It does not write back to the ERP.")
        if st.button("Apply staging to SupplierPass", type="primary"):
            inserted, updated, po_inserted, price_inserted = sync_staging_to_core()
            st.success(f"Sync complete. Suppliers inserted: {inserted}, suppliers updated: {updated}, PO rows: {po_inserted}, price rows: {price_inserted}.")
            st.rerun()

    with tab_unmatched:
        c = table_cols("suppliers")
        stg_suppliers = read_df(f"SELECT * FROM {stg('suppliers')}")
        rows = []
        for _, r in stg_suppliers.iterrows():
            name = r[c["supplier_name"]]
            email = r.get(c["supplier_email"], "") or ""
            match = find_duplicate(name, email)
            if match.empty:
                rows.append({"Supplier Code": r.get(c["supplier_code"], ""), "Supplier Name": name, "Email": email, "Category": r.get(c["category"], ""), "Status": "Unmatched"})
        show_df(pd.DataFrame(rows), "No unmatched staged suppliers.")

    with tab_history:
        if is_sqlserver():
            history = read_df("SELECT TOP 200 * FROM dbo.SyncLog ORDER BY StartedAt DESC")
        else:
            history = read_df("SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 200")
        show_df(history, "No sync history yet.")

    with tab_design:
        st.markdown("""
        ### ERP sync design

        This is the safe foundation before direct ERP integration:

        ```text
        ERP SQL/views/exports
        → SupplierPass staging tables
        → Apply sync into SupplierPass core tables
        → SupplierPass scorecards/action queue
        → reviewed ERP export/API later
        ```

        For Sage 200 or similar SQL-backed ERPs, the next step is to replace manual CSV staging with a scheduled read-only SQL pull.
        """)


def dashboard_screen():
    hero("SupplierPass SQL", "SQL-backed supplier management, documents, email, intelligence and ERP sync foundation.")
    st.caption(f"{APP_VERSION} | Database mode: {connection_summary().get('mode')}")
    suppliers = supplier_df()
    intel = intelligence_df()
    ensure_erp_sync_schema()
    counts = staging_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Suppliers", len(suppliers), "SQL-backed records")
    with c2: kpi("Best score", f"{intel['Overall'].max():.0f}" if not intel.empty else "—", "supplier intelligence")
    with c3: kpi("ERP staging", sum(counts.values()), "rows waiting/loaded")
    with c4:
        actions = read_df(f"SELECT * FROM {q('erp_action_queue')}")
        kpi("ERP actions", len(actions), "action queue")
    if not intel.empty:
        show_df(intel.sort_values("Overall", ascending=False), "No intelligence rows yet.")


initialise_database()
ensure_erp_sync_schema()

st.sidebar.markdown("# SupplierPass")
st.sidebar.caption(APP_VERSION)
area = st.sidebar.selectbox(
    "Area",
    [
        "Dashboard",
        "Database",
        "SQL Demo Data",
        "SQL Documents Demo",
        "SQL Intelligence Demo",
        "Suppliers",
        "Supplier Onboarding",
        "Approval Queue",
        "Preferred Suppliers",
        "Document Management",
        "Email Centre",
        "ERP Data Uploads",
        "Supplier Intelligence",
        "ERP Sync",
        "ERP Action Queue",
    ],
)

if area == "Dashboard":
    dashboard_screen()
elif area == "Database":
    database_screen()
elif area == "SQL Demo Data":
    demo_data_screen()
elif area == "SQL Documents Demo":
    sql_documents_demo_screen()
elif area == "SQL Intelligence Demo":
    sql_intelligence_demo_screen()
elif area == "Suppliers":
    add_supplier_screen()
elif area == "Supplier Onboarding":
    onboarding_screen()
elif area == "Approval Queue":
    approval_queue_screen()
elif area == "Preferred Suppliers":
    preferred_screen()
elif area == "Document Management":
    documents_screen()
elif area == "Email Centre":
    email_centre_screen()
elif area == "ERP Data Uploads":
    data_uploads_screen()
elif area == "Supplier Intelligence":
    intelligence_screen()
elif area == "ERP Sync":
    erp_sync_screen()
elif area == "ERP Action Queue":
    erp_action_queue_screen()
