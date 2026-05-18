import re
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "supplierpass.db"
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="SupplierPass", page_icon="✅", layout="wide")
APP_VERSION = "v0.17 preferred suppliers + ERP action queue"

SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold", "Approval Revoked"]
APP_STATUSES = ["Active", "Inactive"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def df_sql(sql, params=()):
    c = conn()
    df = pd.read_sql_query(sql, c, params=params)
    c.close()
    return df


def exec_sql(sql, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(sql, params)
    c.commit()
    new_id = cur.lastrowid
    c.close()
    return new_id


def ensure_column(table, column, definition):
    info = df_sql(f"PRAGMA table_info({table})")
    if column not in info["name"].tolist():
        exec_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def normalise_name(name):
    value = str(name or "").lower().strip()
    value = re.sub(r"\b(limited|ltd|plc|llp|uk|the)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def normalise_email(email):
    return str(email or "").strip().lower()


def init_db():
    c = conn()
    cur = c.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT,
            supplier_name TEXT NOT NULL,
            supplier_key TEXT,
            supplier_email TEXT,
            email_key TEXT,
            category TEXT,
            owner TEXT,
            approval_status TEXT DEFAULT 'Pending',
            app_status TEXT DEFAULT 'Active',
            risk_level TEXT DEFAULT 'Medium',
            annual_spend REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS po_history (
            po_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            supplier_name TEXT,
            supplier_key TEXT,
            item_code TEXT,
            item_description TEXT,
            po_number TEXT,
            po_date TEXT,
            promised_date TEXT,
            received_date TEXT,
            quantity REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            source_file TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            supplier_name TEXT,
            supplier_key TEXT,
            item_code TEXT,
            item_description TEXT,
            category TEXT,
            unit_price REAL DEFAULT 0,
            currency TEXT DEFAULT 'GBP',
            lead_time_days REAL,
            source_file TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS preferred_suppliers (
            preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            is_preferred INTEGER DEFAULT 1,
            reason TEXT,
            set_by TEXT,
            set_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(supplier_id, category)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS erp_action_queue (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            supplier_code TEXT,
            supplier_name TEXT,
            action_type TEXT,
            action_reason TEXT,
            old_value TEXT,
            new_value TEXT,
            status TEXT DEFAULT 'Pending Export',
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            exported_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_history (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement TEXT,
            category TEXT,
            chosen_supplier TEXT,
            recommended_supplier TEXT,
            reason TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.commit()
    c.close()

    for col, definition in {
        "supplier_key": "TEXT",
        "email_key": "TEXT",
        "app_status": "TEXT DEFAULT 'Active'",
    }.items():
        ensure_column("suppliers", col, definition)
    backfill_supplier_keys()


def backfill_supplier_keys():
    suppliers = df_sql("SELECT supplier_id, supplier_name, supplier_email FROM suppliers WHERE supplier_key IS NULL OR supplier_key='' OR email_key IS NULL")
    for _, s in suppliers.iterrows():
        exec_sql("UPDATE suppliers SET supplier_key=?, email_key=? WHERE supplier_id=?", (normalise_name(s["supplier_name"]), normalise_email(s["supplier_email"]), int(s["supplier_id"])))


def style():
    st.markdown("""
    <style>
    .block-container{padding-top:1rem}.hero{border-radius:22px;padding:24px 28px;background:linear-gradient(135deg,#0f172a,#1d4ed8 55%,#0f766e);color:white;margin-bottom:18px}.hero h1{margin:0;color:white}.hero p{color:#dbeafe}.kpi{border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff}.lab{font-size:.82rem;color:#64748b}.val{font-size:1.55rem;font-weight:750}.sub{font-size:.8rem;color:#64748b}.card{border:1px solid #e5e7eb;border-radius:18px;padding:18px;background:#fff;margin-bottom:12px;box-shadow:0 1px 2px rgba(15,23,42,.06)}.big{font-size:2rem}.hint{border-left:4px solid #2563eb;background:#eff6ff;padding:12px 14px;border-radius:10px;margin:8px 0 16px 0;color:#1e3a8a}[data-testid="stSidebar"]{background:#0f172a}[data-testid="stSidebar"] *{color:#f8fafc!important}
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def hint(text):
    st.markdown(f"<div class='hint'>{text}</div>", unsafe_allow_html=True)


def kpi(label, value, sub=""):
    st.markdown(f"<div class='kpi'><div class='lab'>{label}</div><div class='val'>{value}</div><div class='sub'>{sub}</div></div>", unsafe_allow_html=True)


def show_df(df, empty="No records found."):
    if df is None or df.empty:
        st.info(empty)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def icon(score):
    if score is None or pd.isna(score): return "⚪"
    if score >= 80: return "🟢"
    if score >= 55: return "🟠"
    return "🔴"


def active_icon(status):
    return "✅" if status == "Active" else "⛔"


def preferred_icon(is_preferred):
    return "⭐" if is_preferred else ""


def parse_date(value):
    try:
        if value is None or value == "" or pd.isna(value): return None
        return pd.to_datetime(value)
    except Exception:
        return None


def find_duplicate(name, email=""):
    key = normalise_name(name)
    ekey = normalise_email(email)
    if ekey:
        return df_sql("SELECT * FROM suppliers WHERE supplier_key=? OR email_key=? OR lower(supplier_email)=?", (key, ekey, ekey))
    return df_sql("SELECT * FROM suppliers WHERE supplier_key=?", (key,))


def resolve_supplier(name, email="", category=""):
    match = find_duplicate(name, email)
    if not match.empty: return int(match.iloc[0]["supplier_id"])
    return exec_sql("INSERT INTO suppliers (supplier_name, supplier_key, supplier_email, email_key, category, approval_status, app_status, risk_level) VALUES (?, ?, ?, ?, ?, 'Pending', 'Active', 'Medium')", (name, normalise_name(name), email, normalise_email(email), category))


def categories():
    dfs = [df_sql("SELECT DISTINCT category FROM suppliers"), df_sql("SELECT DISTINCT category FROM supplier_prices"), df_sql("SELECT DISTINCT category FROM preferred_suppliers")]
    vals = []
    for df in dfs:
        if not df.empty:
            vals += [x for x in df["category"].dropna().tolist() if str(x).strip()]
    return sorted(set(vals))


def add_erp_action(supplier_id, action_type, reason, old_value, new_value, user=""):
    s = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,))
    if s.empty: return
    s = s.iloc[0]
    exists = df_sql("""
        SELECT * FROM erp_action_queue
        WHERE supplier_id=? AND action_type=? AND status='Pending Export' AND new_value=?
    """, (supplier_id, action_type, str(new_value)))
    if not exists.empty: return
    exec_sql("""
        INSERT INTO erp_action_queue
        (supplier_id, supplier_code, supplier_name, action_type, action_reason, old_value, new_value, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (supplier_id, s["supplier_code"], s["supplier_name"], action_type, reason, str(old_value), str(new_value), user))


def compliance_score(s):
    score = 100
    if s["app_status"] != "Active": score -= 60
    if s["approval_status"] != "Approved": score -= 25
    if s["approval_status"] == "Approval Revoked": score -= 50
    if s["risk_level"] == "High": score -= 15
    if s["risk_level"] == "Critical": score -= 30
    return max(0, min(100, score))


def supplier_perf(supplier_id):
    po = df_sql("SELECT * FROM po_history WHERE supplier_id=?", (supplier_id,))
    if po.empty: return {"spend": 0, "otif": None, "last_used": None, "avg_days_late": None, "usage": 0}
    po["po_date_dt"] = pd.to_datetime(po["po_date"], errors="coerce")
    po["promised_dt"] = pd.to_datetime(po["promised_date"], errors="coerce")
    po["received_dt"] = pd.to_datetime(po["received_date"], errors="coerce")
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=12)
    recent = po[(po["po_date_dt"].isna()) | (po["po_date_dt"] >= cutoff)]
    spend = round(float(recent["total_value"].fillna(0).sum()), 2)
    with_dates = po[po["promised_dt"].notna() & po["received_dt"].notna()].copy()
    otif = avg_days_late = None
    if not with_dates.empty:
        with_dates["on_time"] = with_dates["received_dt"] <= with_dates["promised_dt"]
        with_dates["days_late"] = (with_dates["received_dt"] - with_dates["promised_dt"]).dt.days.clip(lower=0)
        otif = round(float(with_dates["on_time"].mean() * 100), 1)
        avg_days_late = round(float(with_dates["days_late"].mean()), 1)
    last_used = None
    usage = 0
    if po["po_date_dt"].notna().any():
        last = po["po_date_dt"].max().date()
        last_used = last.isoformat()
        usage = max(0, min(100, 100 - (date.today() - last).days / 3.65))
    return {"spend": spend, "otif": otif, "last_used": last_used, "avg_days_late": avg_days_late, "usage": round(usage, 1)}


def price_score_for_supplier(supplier_id):
    prices = df_sql("SELECT * FROM supplier_prices")
    if prices.empty: return None
    scores = []
    for item, grp in prices.groupby("item_code"):
        own = grp[grp["supplier_id"] == supplier_id]
        if own.empty: continue
        min_price = pd.to_numeric(grp["unit_price"], errors="coerce").replace(0, pd.NA).min()
        own_price = pd.to_numeric(own["unit_price"], errors="coerce").replace(0, pd.NA).mean()
        if pd.notna(min_price) and pd.notna(own_price) and own_price > 0:
            scores.append(max(0, min(100, float(min_price / own_price * 100))))
    return round(sum(scores) / len(scores), 1) if scores else None


def preference_lookup():
    pref = df_sql("SELECT * FROM preferred_suppliers WHERE is_preferred=1")
    if pref.empty: return set()
    return set((int(r["supplier_id"]), str(r["category"])) for _, r in pref.iterrows())


def intelligence_table():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    prefs = preference_lookup()
    rows = []
    for _, s in suppliers.iterrows():
        comp = compliance_score(s)
        perf = supplier_perf(int(s["supplier_id"]))
        price = price_score_for_supplier(int(s["supplier_id"]))
        otif_component = perf["otif"] if perf["otif"] is not None else 50
        price_component = price if price is not None else 50
        preferred = (int(s["supplier_id"]), str(s["category"])) in prefs
        preferred_bonus = 8 if preferred else 0
        can_buy_factor = 100 if s["approval_status"] == "Approved" and s["app_status"] == "Active" else 10
        overall = round(min(100, comp * 0.30 + price_component * 0.25 + otif_component * 0.25 + perf["usage"] * 0.10 + can_buy_factor * 0.10 + preferred_bonus), 1)
        rows.append({
            "Icon": icon(overall), "Active": active_icon(s["app_status"]), "Preferred": preferred_icon(preferred),
            "Supplier ID": s["supplier_id"], "Supplier Code": s["supplier_code"], "Supplier": s["supplier_name"], "Category": s["category"],
            "Overall": overall, "Compliance": comp, "Price": price, "OTIF": perf["otif"], "Usage": perf["usage"],
            "12M Spend": perf["spend"], "Last Used": perf["last_used"], "Avg Days Late": perf["avg_days_late"],
            "App Status": s["app_status"], "Approval": s["approval_status"], "Risk": s["risk_level"], "Email": s["supplier_email"]
        })
    return pd.DataFrame(rows)


def get_val(row, mapping, label, default=""):
    col = mapping.get(label, "")
    if col and col in row.index and pd.notna(row[col]): return row[col]
    return default


def column_mapper(df, mode):
    cols = df.columns.tolist()
    def select(label, guesses, required=False):
        opts = cols if required else [""] + cols
        idx = 0
        for g in guesses:
            if g in opts: idx = opts.index(g); break
        return st.selectbox(label, opts, idx, key=f"map_{mode}_{label}")
    c1, c2, c3 = st.columns(3)
    mapping = {}
    with c1:
        mapping["Supplier Name"] = select("Supplier Name", ["SupplierName", "Supplier Name", "Supplier", "Vendor", "Name"], True)
        mapping["Supplier Email"] = select("Supplier Email", ["Email", "SupplierEmail", "Email Address"])
        mapping["Item Code"] = select("Item Code", ["ItemCode", "Item Code", "StockCode", "Product Code", "Code"])
        mapping["Item Description"] = select("Item Description", ["ItemDescription", "Item Description", "Description"])
    with c2:
        mapping["PO Number"] = select("PO Number", ["PONumber", "PO Number", "DocumentNo", "Order Number"])
        mapping["PO Date"] = select("PO Date", ["PODate", "PO Date", "Order Date", "Date"])
        mapping["Promised Date"] = select("Promised Date", ["PromisedDate", "Promised Date", "Due Date", "RequestedDeliveryDate"])
        mapping["Received Date"] = select("Received Date", ["ReceivedDate", "Received Date", "Receipt Date", "GRN Date"])
    with c3:
        mapping["Quantity"] = select("Quantity", ["Quantity", "Qty", "Order Quantity"])
        mapping["Unit Price"] = select("Unit Price", ["UnitPrice", "Unit Price", "Price", "Net Price"])
        mapping["Total Value"] = select("Total Value", ["TotalValue", "Total Value", "Line Total", "Net Value"])
        mapping["Category"] = select("Category", ["Category", "Product Group", "Supplier Category"])
        mapping["Lead Time Days"] = select("Lead Time Days", ["LeadTimeDays", "Lead Time", "Lead Time Days"])
    return mapping


def load_demo_data():
    demo = [
        ("SUP001", "ABC Transport Ltd", "accounts@abctransport.co.uk", "Transport", "Connor", "Approved", "Medium"),
        ("SUP002", "Yorkshire Board Supplies", "quality@yorkshireboard.co.uk", "Manufacturing", "Quality", "Approved", "High"),
        ("SUP003", "Fast Fix Maintenance", "fastfix@gmail.com", "Contractor", "Maintenance", "Pending", "Medium"),
    ]
    for code, name, email, cat, owner, status, risk in demo:
        if find_duplicate(name, email).empty:
            exec_sql("INSERT INTO suppliers (supplier_code, supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, app_status, risk_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)", (code, name, normalise_name(name), email, normalise_email(email), cat, owner, status, risk))
    suppliers = df_sql("SELECT * FROM suppliers")
    today = pd.Timestamp.today()
    for _, s in suppliers.iterrows():
        if not df_sql("SELECT * FROM po_history WHERE supplier_id=? AND source_file='demo'", (int(s["supplier_id"]),)).empty: continue
        for i in range(1, 7):
            po_date = today - pd.DateOffset(days=i * 31)
            promised = po_date + pd.DateOffset(days=7)
            received = promised + pd.DateOffset(days=(i + int(s["supplier_id"])) % 4 - 1)
            total = 200 + i * 110 + int(s["supplier_id"]) * 70
            exec_sql("INSERT INTO po_history (supplier_id, supplier_name, supplier_key, item_code, item_description, po_number, po_date, promised_date, received_date, quantity, unit_price, total_value, source_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'demo')", (int(s["supplier_id"]), s["supplier_name"], s["supplier_key"], f"ITEM-{i%3+1}", f"Demo item {i%3+1}", f"PO-DEMO-{s['supplier_id']}-{i}", po_date.date().isoformat(), promised.date().isoformat(), received.date().isoformat(), i * 10, total / (i * 10), total))
        for item in range(1, 4):
            exec_sql("INSERT INTO supplier_prices (supplier_id, supplier_name, supplier_key, item_code, item_description, category, unit_price, lead_time_days, source_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'demo')", (int(s["supplier_id"]), s["supplier_name"], s["supplier_key"], f"ITEM-{item}", f"Demo item {item}", s["category"], 10 + item + (int(s["supplier_id"]) % 3), 3 + (int(s["supplier_id"]) % 5)))
    st.success("Demo supplier intelligence data loaded.")


def dashboard():
    hero("SupplierPass", "Supplier approval, preferred suppliers, ERP action queue and supplier intelligence.")
    intel = intelligence_table()
    erp_pending = df_sql("SELECT * FROM erp_action_queue WHERE status='Pending Export'")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Suppliers", len(df_sql("SELECT * FROM suppliers")), "supplier records")
    with c2: kpi("Preferred", len(df_sql("SELECT * FROM preferred_suppliers WHERE is_preferred=1")), "manual choices")
    with c3: kpi("ERP actions", len(erp_pending), "pending export")
    with c4: kpi("Best score", f"{intel['Overall'].max():.0f}" if not intel.empty else "—", "supplier intelligence")
    if intel.empty:
        st.warning("No supplier intelligence data yet.")
        if st.button("Load demo data"):
            load_demo_data(); st.rerun()
    else:
        st.subheader("Top supplier scorecards")
        top = intel.sort_values("Overall", ascending=False).head(4)
        cols = st.columns(len(top))
        for i, (_, r) in enumerate(top.iterrows()):
            with cols[i]:
                st.markdown(f"<div class='card'><div class='big'>{r['Icon']} {r['Preferred']} {r['Active']}</div><b>{r['Supplier']}</b><br><span class='sub'>Overall {r['Overall']}</span><br><span class='sub'>OTIF {r['OTIF'] if pd.notna(r['OTIF']) else '—'}%</span><br><span class='sub'>Spend £{r['12M Spend']:,.0f}</span></div>", unsafe_allow_html=True)
        show_df(intel.sort_values("Overall", ascending=False), "No intelligence rows yet.")


def supplier_register():
    hero("Supplier Register", "Add suppliers, revoke approval, make inactive and trigger ERP actions.")
    tab_add, tab_manage, tab_list = st.tabs(["Add / Import", "Manage Supplier", "Register"])
    with tab_add:
        with st.form("add_supplier"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Supplier name *")
            code = c1.text_input("Supplier code")
            email = c1.text_input("Email")
            cat = c2.text_input("Category")
            owner = c2.text_input("Owner")
            status = c3.selectbox("Approval", SUPPLIER_STATUSES, index=1)
            app_status = c3.selectbox("App status", APP_STATUSES)
            risk = c3.selectbox("Risk", RISK_LEVELS, index=1)
            if st.form_submit_button("Add supplier"):
                if not name: st.error("Supplier name is required.")
                elif not find_duplicate(name, email).empty:
                    st.warning("Possible duplicate found. Supplier was not added."); st.dataframe(find_duplicate(name, email), use_container_width=True, hide_index=True)
                else:
                    exec_sql("INSERT INTO suppliers (supplier_code, supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, app_status, risk_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (code, name, normalise_name(name), email, normalise_email(email), cat, owner, status, app_status, risk))
                    st.success("Supplier added."); st.rerun()
    with tab_manage:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers yet."); return
        options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
        sid = options[st.selectbox("Supplier", list(options.keys()))]
        s = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)).iloc[0]
        st.write(f"Current: **{s['approval_status']}** / **{s['app_status']}**")
        with st.form("manage_supplier"):
            c1, c2, c3 = st.columns(3)
            approval = c1.selectbox("Approval", SUPPLIER_STATUSES, index=SUPPLIER_STATUSES.index(s["approval_status"]) if s["approval_status"] in SUPPLIER_STATUSES else 1)
            app_status = c1.selectbox("App status", APP_STATUSES, index=APP_STATUSES.index(s["app_status"]) if s["app_status"] in APP_STATUSES else 0)
            risk = c2.selectbox("Risk", RISK_LEVELS, index=RISK_LEVELS.index(s["risk_level"]) if s["risk_level"] in RISK_LEVELS else 1)
            category = c2.text_input("Category", value=s["category"] or "")
            owner = c3.text_input("Owner", value=s["owner"] or "")
            user = c3.text_input("Changed by")
            reason = st.text_area("Reason / notes")
            if st.form_submit_button("Save supplier controls", type="primary"):
                old_approval = s["approval_status"]
                old_app = s["app_status"]
                exec_sql("UPDATE suppliers SET approval_status=?, app_status=?, risk_level=?, category=?, owner=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?", (approval, app_status, risk, category, owner, reason, sid))
                if old_app == "Active" and app_status == "Inactive":
                    add_erp_action(sid, "SET_SUPPLIER_INACTIVE", reason or "Supplier made inactive in SupplierPass", old_app, app_status, user)
                if old_approval != approval and approval in ["Approval Revoked", "Blocked"]:
                    add_erp_action(sid, "REVOKE_APPROVAL_OR_BLOCK", reason or "Approval revoked/blocked in SupplierPass", old_approval, approval, user)
                st.success("Supplier controls saved. Any ERP updates have been added to the ERP Action Queue.")
                st.rerun()
    with tab_list:
        show_df(intelligence_table(), "No suppliers yet.")


def preferred_suppliers_screen():
    hero("Preferred Suppliers", "Manually flag preferred suppliers by category with a visible ⭐ in comparisons.")
    hint("Preferred is a manual commercial/procurement decision. It adds a small score bonus and is clearly shown as ⭐, but inactive or revoked suppliers should not be selected as preferred.")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.info("No suppliers yet."); return
    tab_set, tab_view = st.tabs(["Set Preferred", "Preferred Matrix"])
    with tab_set:
        cats = categories() or sorted([x for x in suppliers["category"].dropna().unique().tolist() if str(x).strip()])
        category = st.selectbox("Category", cats + ["Other"])
        if category == "Other": category = st.text_input("Other category")
        category_suppliers = suppliers[suppliers["category"] == category] if category else suppliers
        if category_suppliers.empty:
            st.warning("No suppliers in this category yet.")
            category_suppliers = suppliers
        options = {f"{r['supplier_name']} ({r['supplier_id']}) - {r['app_status']} / {r['approval_status']}": int(r["supplier_id"]) for _, r in category_suppliers.iterrows()}
        sid = options[st.selectbox("Supplier", list(options.keys()))]
        s = suppliers[suppliers["supplier_id"] == sid].iloc[0]
        existing = df_sql("SELECT * FROM preferred_suppliers WHERE supplier_id=? AND category=?", (sid, category))
        current = bool(not existing.empty and int(existing.iloc[0]["is_preferred"]) == 1)
        if s["app_status"] != "Active" or s["approval_status"] != "Approved":
            st.warning("This supplier is not fully active and approved. You can still save it, but the app will show it as a warning in comparisons.")
        with st.form("preferred_form"):
            preferred = st.checkbox("Preferred supplier for this category", value=current)
            reason = st.text_area("Reason", value=existing.iloc[0]["reason"] if not existing.empty else "")
            user = st.text_input("Set by", value=existing.iloc[0]["set_by"] if not existing.empty else "")
            if st.form_submit_button("Save preferred setting", type="primary"):
                exec_sql("""
                    INSERT INTO preferred_suppliers (supplier_id, category, is_preferred, reason, set_by, set_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(supplier_id, category)
                    DO UPDATE SET is_preferred=excluded.is_preferred, reason=excluded.reason, set_by=excluded.set_by, set_at=CURRENT_TIMESTAMP
                """, (sid, category, 1 if preferred else 0, reason, user))
                st.success("Preferred setting saved.")
                st.rerun()
    with tab_view:
        matrix = df_sql("""
            SELECT p.category, CASE WHEN p.is_preferred=1 THEN '⭐' ELSE '' END AS Preferred,
                   s.supplier_name, s.supplier_code, s.app_status, s.approval_status, s.risk_level, p.reason, p.set_by, p.set_at
            FROM preferred_suppliers p
            JOIN suppliers s ON p.supplier_id=s.supplier_id
            ORDER BY p.category, p.is_preferred DESC, s.supplier_name
        """)
        show_df(matrix, "No preferred suppliers set yet.")


def data_uploads():
    hero("Data Uploads", "Upload ERP exports for PO history, receipts, OTIF and supplier pricing.")
    hint("Use CSV exports first. The same structure can later be fed automatically from Sage, Business Central, Xero or another ERP.")
    mode = st.radio("Upload type", ["PO / receipt history", "Supplier price list"], horizontal=True)
    file = st.file_uploader("CSV export", type=["csv"], key=mode)
    if not file: return
    data = pd.read_csv(file)
    st.dataframe(data.head(20), use_container_width=True, hide_index=True)
    mapping = column_mapper(data, mode)
    if st.button("Process upload", type="primary"):
        added = 0
        for _, row in data.iterrows():
            name = str(get_val(row, mapping, "Supplier Name", "")).strip()
            if not name: continue
            email = str(get_val(row, mapping, "Supplier Email", "")).strip()
            cat = str(get_val(row, mapping, "Category", "")).strip()
            supplier_id = resolve_supplier(name, email, cat)
            supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).iloc[0]
            if mode == "PO / receipt history":
                qty = pd.to_numeric(get_val(row, mapping, "Quantity", 0), errors="coerce")
                unit = pd.to_numeric(get_val(row, mapping, "Unit Price", 0), errors="coerce")
                total = pd.to_numeric(get_val(row, mapping, "Total Value", 0), errors="coerce")
                if pd.isna(total) or float(total) == 0: total = (0 if pd.isna(qty) else float(qty)) * (0 if pd.isna(unit) else float(unit))
                exec_sql("INSERT INTO po_history (supplier_id, supplier_name, supplier_key, item_code, item_description, po_number, po_date, promised_date, received_date, quantity, unit_price, total_value, source_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (supplier_id, name, supplier["supplier_key"], str(get_val(row, mapping, "Item Code", "")), str(get_val(row, mapping, "Item Description", "")), str(get_val(row, mapping, "PO Number", "")), str(get_val(row, mapping, "PO Date", "")), str(get_val(row, mapping, "Promised Date", "")), str(get_val(row, mapping, "Received Date", "")), 0 if pd.isna(qty) else float(qty), 0 if pd.isna(unit) else float(unit), 0 if pd.isna(total) else float(total), file.name))
            else:
                price = pd.to_numeric(get_val(row, mapping, "Unit Price", 0), errors="coerce")
                lead = pd.to_numeric(get_val(row, mapping, "Lead Time Days", None), errors="coerce")
                exec_sql("INSERT INTO supplier_prices (supplier_id, supplier_name, supplier_key, item_code, item_description, category, unit_price, lead_time_days, source_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (supplier_id, name, supplier["supplier_key"], str(get_val(row, mapping, "Item Code", "")), str(get_val(row, mapping, "Item Description", "")), cat or supplier["category"], 0 if pd.isna(price) else float(price), None if pd.isna(lead) else float(lead), file.name))
            added += 1
        st.success(f"Processed {added} row(s).")
        st.rerun()


def supplier_intelligence():
    hero("Supplier Intelligence", "Compare suppliers on preferred status, price, usage, OTIF, compliance and risk.")
    tab_score, tab_compare, tab_price, tab_otif, tab_history = st.tabs(["Scorecards", "Compare", "Price Analysis", "OTIF Analysis", "Recommendation History"])
    intel = intelligence_table()
    with tab_score:
        show_df(intel.sort_values("Overall", ascending=False) if not intel.empty else intel, "No supplier intelligence yet.")
        if not intel.empty:
            st.subheader("Visual scorecards")
            for _, r in intel.sort_values("Overall", ascending=False).head(12).iterrows():
                st.markdown(f"<div class='card'><span class='big'>{r['Icon']} {r['Preferred']} {r['Active']}</span> <b>{r['Supplier']}</b><br>Overall {r['Overall']} | Compliance {r['Compliance']} | Price {r['Price'] if pd.notna(r['Price']) else '—'} | OTIF {r['OTIF'] if pd.notna(r['OTIF']) else '—'}%<br>Approval: {r['Approval']} | App: {r['App Status']} | Last used: {r['Last Used'] or '—'} | 12M spend: £{r['12M Spend']:,.0f}</div>", unsafe_allow_html=True)
    with tab_compare:
        if intel.empty:
            st.info("No suppliers to compare yet.")
        else:
            cats = ["All"] + categories()
            cat = st.selectbox("Category", cats)
            view = intel if cat == "All" else intel[intel["Category"] == cat]
            include_inactive = st.checkbox("Include inactive/revoked suppliers", value=False)
            if not include_inactive:
                view = view[(view["App Status"] == "Active") & (view["Approval"] != "Approval Revoked")]
            chosen = st.multiselect("Suppliers", view["Supplier"].tolist(), default=view.sort_values("Overall", ascending=False)["Supplier"].head(3).tolist() if not view.empty else [])
            comp = view[view["Supplier"].isin(chosen)] if chosen else view
            show_df(comp.sort_values("Overall", ascending=False), "Select suppliers to compare.")
            if not comp.empty:
                rec = comp.sort_values(["Preferred", "Overall"], ascending=[False, False]).iloc[0]
                st.success(f"Recommended: {rec['Icon']} {rec['Preferred']} {rec['Supplier']} — score {rec['Overall']}.")
                reason = f"Recommended {rec['Supplier']} based on preferred status '{rec['Preferred']}', overall score {rec['Overall']}, compliance {rec['Compliance']}, price score {rec['Price'] if pd.notna(rec['Price']) else 'not available'}, OTIF {rec['OTIF'] if pd.notna(rec['OTIF']) else 'not available'} and recent usage."
                with st.form("save_rec"):
                    req = st.text_input("Requirement / comparison reason", value=f"Supplier comparison - {cat}")
                    user = st.text_input("Created by")
                    selected_supplier = st.selectbox("Chosen supplier", comp["Supplier"].tolist(), index=comp["Supplier"].tolist().index(rec["Supplier"]))
                    if st.form_submit_button("Save recommendation"):
                        exec_sql("INSERT INTO recommendation_history (requirement, category, chosen_supplier, recommended_supplier, reason, created_by) VALUES (?, ?, ?, ?, ?, ?)", (req, cat, selected_supplier, rec["Supplier"], reason, user))
                        st.success("Recommendation saved.")
    with tab_price:
        prices = df_sql("SELECT * FROM supplier_prices")
        if prices.empty: st.info("No price data uploaded yet.")
        else:
            item = st.selectbox("Item", ["All"] + sorted([x for x in prices["item_code"].dropna().unique().tolist() if str(x).strip()]))
            view = prices if item == "All" else prices[prices["item_code"] == item]
            if not view.empty:
                view = view.copy(); view["Best"] = view.groupby("item_code")["unit_price"].transform(lambda s: s == s.min()).map(lambda x: "🏆" if x else "")
            show_df(view[["Best", "supplier_name", "item_code", "item_description", "category", "unit_price", "currency", "lead_time_days", "source_file", "uploaded_at"]], "No price rows.")
            if item != "All" and not view.empty: st.bar_chart(view.set_index("supplier_name")["unit_price"])
    with tab_otif:
        po = df_sql("SELECT * FROM po_history")
        if po.empty: st.info("No PO/receipt history uploaded yet.")
        else:
            rows = []
            for sid in po["supplier_id"].dropna().unique():
                s = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (int(sid),))
                if s.empty: continue
                perf = supplier_perf(int(sid))
                rows.append({"Icon": icon(perf["otif"] if perf["otif"] is not None else 50), "Supplier": s.iloc[0]["supplier_name"], "OTIF %": perf["otif"], "Avg Days Late": perf["avg_days_late"], "Last Used": perf["last_used"], "12M Spend": perf["spend"]})
            otif = pd.DataFrame(rows).sort_values("OTIF %", ascending=False, na_position="last") if rows else pd.DataFrame()
            show_df(otif, "No OTIF rows calculated.")
            if not otif.empty and otif["OTIF %"].notna().any(): st.bar_chart(otif.dropna(subset=["OTIF %"]).set_index("Supplier")["OTIF %"])
    with tab_history:
        show_df(df_sql("SELECT * FROM recommendation_history ORDER BY created_at DESC"), "No recommendations saved yet.")


def erp_actions():
    hero("ERP Action Queue", "Export supplier master updates caused by approval revocation or inactivation.")
    hint("This is deliberately export-first. In production, the same queue can be sent to Sage/ERP by API after admin review.")
    tab_queue, tab_export = st.tabs(["Queue", "Export"])
    with tab_queue:
        actions = df_sql("SELECT * FROM erp_action_queue ORDER BY created_at DESC")
        show_df(actions, "No ERP actions queued.")
        pending = actions[actions["status"] == "Pending Export"] if not actions.empty else pd.DataFrame()
        if not pending.empty:
            action_id = st.selectbox("Mark action exported / ignored", pending["action_id"].tolist())
            c1, c2 = st.columns(2)
            if c1.button("Mark exported"):
                exec_sql("UPDATE erp_action_queue SET status='Exported', exported_at=CURRENT_TIMESTAMP WHERE action_id=?", (int(action_id),))
                st.success("Marked exported."); st.rerun()
            if c2.button("Ignore action"):
                exec_sql("UPDATE erp_action_queue SET status='Ignored', exported_at=CURRENT_TIMESTAMP WHERE action_id=?", (int(action_id),))
                st.warning("Action ignored."); st.rerun()
    with tab_export:
        pending = df_sql("SELECT * FROM erp_action_queue WHERE status='Pending Export' ORDER BY created_at")
        show_df(pending, "No pending ERP actions to export.")
        if not pending.empty:
            export = pending[["supplier_code", "supplier_name", "action_type", "old_value", "new_value", "action_reason", "created_by", "created_at"]].copy()
            st.download_button("Download ERP action CSV", export.to_csv(index=False).encode("utf-8"), file_name=f"supplierpass_erp_actions_{date.today().isoformat()}.csv", mime="text/csv")


def reports():
    hero("Reports", "Download supplier intelligence and ERP action data.")
    intel = intelligence_table()
    c1, c2, c3 = st.columns(3)
    with c1: kpi("Suppliers", len(df_sql("SELECT * FROM suppliers")), "records")
    with c2: kpi("Preferred", len(df_sql("SELECT * FROM preferred_suppliers WHERE is_preferred=1")), "manual")
    with c3: kpi("Pending ERP", len(df_sql("SELECT * FROM erp_action_queue WHERE status='Pending Export'")), "actions")
    show_df(intel, "No intelligence rows yet.")
    xlsx = DATA_DIR / f"supplierpass_v17_{date.today().isoformat()}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        intel.to_excel(writer, index=False, sheet_name="Supplier Intelligence")
        df_sql("SELECT * FROM suppliers").to_excel(writer, index=False, sheet_name="Suppliers")
        df_sql("SELECT * FROM preferred_suppliers").to_excel(writer, index=False, sheet_name="Preferred")
        df_sql("SELECT * FROM erp_action_queue").to_excel(writer, index=False, sheet_name="ERP Actions")
        df_sql("SELECT * FROM po_history").to_excel(writer, index=False, sheet_name="PO History")
        df_sql("SELECT * FROM supplier_prices").to_excel(writer, index=False, sheet_name="Prices")
        df_sql("SELECT * FROM recommendation_history").to_excel(writer, index=False, sheet_name="Recommendations")
    with open(xlsx, "rb") as f:
        st.download_button("Download SupplierPass pack", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


init_db(); style()
st.sidebar.markdown("# SupplierPass")
st.sidebar.caption(APP_VERSION)
page = st.sidebar.radio("Navigation", ["Dashboard", "Supplier Register", "Preferred Suppliers", "Data Uploads", "Supplier Intelligence", "ERP Action Queue", "Reports"])
if page == "Dashboard": dashboard()
elif page == "Supplier Register": supplier_register()
elif page == "Preferred Suppliers": preferred_suppliers_screen()
elif page == "Data Uploads": data_uploads()
elif page == "Supplier Intelligence": supplier_intelligence()
elif page == "ERP Action Queue": erp_actions()
elif page == "Reports": reports()
