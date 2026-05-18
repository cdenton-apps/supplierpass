import base64
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
UPLOAD_DIR = APP_DIR / "uploads"
DB_PATH = DATA_DIR / "supplierpass.db"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="SupplierPass", page_icon="✅", layout="wide")
APP_VERSION = "v0.15 supplier email centre"

SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
DOC_STATUSES = ["Uploaded", "Under Review", "Accepted", "Rejected / Needs replacement", "Archived / Ignore"]
EMAIL_TYPES = [
    "Missing document request",
    "Expired document chase",
    "Document expiring soon",
    "Supplier information request",
    "Annual supplier review request",
    "Bank verification request",
    "General supplier message",
]

DEFAULT_RULES = [
    ("Manufacturing", "ISO 9001 Certificate", 1, 60),
    ("Manufacturing", "Public Liability Insurance", 1, 60),
    ("Manufacturing", "Supplier Questionnaire", 1, 365),
    ("Packaging", "ISO 9001 Certificate", 1, 60),
    ("Packaging", "Public Liability Insurance", 1, 60),
    ("Packaging", "FSC / PEFC Certificate", 0, 60),
    ("Transport", "Public Liability Insurance", 1, 60),
    ("Transport", "Goods in Transit Insurance", 1, 60),
    ("Transport", "Operator Licence", 1, 60),
    ("Contractor", "Public Liability Insurance", 1, 60),
    ("Contractor", "RAMS", 1, 30),
    ("Contractor", "Health & Safety Policy", 1, 365),
    ("IT / Software", "Cyber Security Questionnaire", 1, 365),
    ("IT / Software", "Data Processing Agreement", 1, 365),
]


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


def many_sql(sql, rows):
    if rows:
        c = conn()
        c.executemany(sql, rows)
        c.commit()
        c.close()


def ensure_column(table, column, definition):
    info = df_sql(f"PRAGMA table_info({table})")
    if column not in info["name"].tolist():
        exec_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def normalise_name(name):
    value = str(name or "").lower().strip()
    value = re.sub(r"\b(limited|ltd|plc|llp|uk|the)\b", "", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


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
            risk_level TEXT DEFAULT 'Medium',
            annual_spend REAL DEFAULT 0,
            criticality TEXT DEFAULT 'Standard',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            document_type TEXT NOT NULL,
            is_critical INTEGER DEFAULT 1,
            warning_days INTEGER DEFAULT 60,
            UNIQUE(category, document_type)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            document_type TEXT NOT NULL,
            file_name TEXT,
            file_path TEXT,
            expiry_date TEXT,
            review_status TEXT DEFAULT 'Uploaded',
            reviewed_by TEXT,
            review_notes TEXT,
            notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS new_supplier_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT NOT NULL,
            supplier_email TEXT,
            requested_by TEXT,
            category TEXT,
            reason_needed TEXT,
            expected_annual_spend REAL DEFAULT 0,
            urgency TEXT DEFAULT 'Normal',
            status TEXT DEFAULT 'Draft',
            approval_decision TEXT,
            approval_notes TEXT,
            approved_by TEXT,
            approved_at TEXT,
            converted_supplier_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_timeline (
            timeline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            request_id INTEGER,
            event_type TEXT,
            event_detail TEXT,
            user TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            request_id INTEGER,
            email_type TEXT,
            recipient TEXT,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'Drafted',
            sent_by TEXT,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type TEXT UNIQUE,
            subject TEXT,
            body TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.commit()
    c.close()

    migrations = {
        "suppliers": {"supplier_key": "TEXT", "email_key": "TEXT", "criticality": "TEXT DEFAULT 'Standard'"},
        "supplier_documents": {"review_status": "TEXT DEFAULT 'Uploaded'", "reviewed_by": "TEXT", "review_notes": "TEXT", "reviewed_at": "TEXT"},
        "new_supplier_requests": {"urgency": "TEXT DEFAULT 'Normal'", "approval_decision": "TEXT", "approval_notes": "TEXT", "approved_by": "TEXT", "approved_at": "TEXT", "converted_supplier_id": "INTEGER"},
        "supplier_timeline": {"request_id": "INTEGER"},
        "email_log": {"request_id": "INTEGER", "sent_by": "TEXT"},
    }
    for table, cols in migrations.items():
        for col, definition in cols.items():
            ensure_column(table, col, definition)

    many_sql("INSERT OR IGNORE INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)", DEFAULT_RULES)
    seed_email_templates()
    backfill_supplier_keys()


def seed_email_templates():
    rows = [
        (
            "Missing document request",
            "Supplier document request - {supplier_name}",
            "Hi,\n\nWe are updating our approved supplier records for {supplier_name}.\n\nPlease send the following document(s):\n\n{document_list}\n\nThis is required so we can keep your supplier approval record up to date.\n\nMany thanks,\n{sender}",
        ),
        (
            "Expired document chase",
            "Expired supplier document - {supplier_name}",
            "Hi,\n\nOur records show the following document(s) for {supplier_name} have expired:\n\n{document_list}\n\nPlease send updated copies as soon as possible.\n\nMany thanks,\n{sender}",
        ),
        (
            "Document expiring soon",
            "Supplier document expiring soon - {supplier_name}",
            "Hi,\n\nThe following document(s) for {supplier_name} are due to expire soon:\n\n{document_list}\n\nPlease send updated versions when available.\n\nMany thanks,\n{sender}",
        ),
        (
            "Supplier information request",
            "Supplier information request - {supplier_name}",
            "Hi,\n\nWe are reviewing our supplier records for {supplier_name}.\n\nPlease confirm your latest company details, key contact, insurance/certification status and any updated compliance documents.\n\nMany thanks,\n{sender}",
        ),
        (
            "Annual supplier review request",
            "Annual supplier review - {supplier_name}",
            "Hi,\n\nWe are completing our annual supplier review for {supplier_name}.\n\nPlease confirm that your supplier details and compliance documents remain current.\n\nMany thanks,\n{sender}",
        ),
        (
            "Bank verification request",
            "Bank verification request - {supplier_name}",
            "Hi,\n\nAs part of our supplier controls, please confirm the correct finance contact for bank detail verification for {supplier_name}.\n\nPlease do not send bank details unless requested through our approved process.\n\nMany thanks,\n{sender}",
        ),
        (
            "General supplier message",
            "Supplier query - {supplier_name}",
            "Hi,\n\nWe are contacting you about your supplier record for {supplier_name}.\n\n{custom_message}\n\nMany thanks,\n{sender}",
        ),
    ]
    many_sql("INSERT OR IGNORE INTO email_templates (template_type, subject, body) VALUES (?, ?, ?)", rows)


def backfill_supplier_keys():
    suppliers = df_sql("SELECT supplier_id, supplier_name, supplier_email FROM suppliers WHERE supplier_key IS NULL OR supplier_key='' OR email_key IS NULL")
    for _, s in suppliers.iterrows():
        exec_sql("UPDATE suppliers SET supplier_key=?, email_key=? WHERE supplier_id=?", (normalise_name(s["supplier_name"]), normalise_email(s["supplier_email"]), int(s["supplier_id"])))


def apply_style():
    st.markdown("""
    <style>
    .block-container{padding-top:1rem}.hero{border-radius:22px;padding:24px 28px;background:linear-gradient(135deg,#0f172a,#1d4ed8 55%,#0f766e);color:white;margin-bottom:18px}.hero h1{margin:0;color:white}.hero p{color:#dbeafe}.kpi{border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff}.lab{font-size:.82rem;color:#64748b}.val{font-size:1.6rem;font-weight:750}.sub{font-size:.8rem;color:#64748b}.hint{border-left:4px solid #2563eb;background:#eff6ff;padding:12px 14px;border-radius:10px;margin:8px 0 16px 0;color:#1e3a8a}.review-card{border:1px solid #e5e7eb;border-radius:16px;padding:18px;background:#fff;margin-top:12px}[data-testid="stSidebar"]{background:#0f172a}[data-testid="stSidebar"] *{color:#f8fafc!important}
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def hint(text):
    st.markdown(f"<div class='hint'>{text}</div>", unsafe_allow_html=True)


def kpi(label, value, sub=""):
    st.markdown(f"<div class='kpi'><div class='lab'>{label}</div><div class='val'>{value}</div><div class='sub'>{sub}</div></div>", unsafe_allow_html=True)


def show_df(df, empty_message="No records found."):
    if df is None or df.empty:
        st.info(empty_message)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def parse_date(value):
    try:
        if value is None or value == "" or pd.isna(value):
            return None
        return pd.to_datetime(value).date()
    except Exception:
        return None


def days_left(value):
    d = parse_date(value)
    return None if d is None else (d - date.today()).days


def categories():
    df = df_sql("""
        SELECT DISTINCT category FROM suppliers
        UNION SELECT DISTINCT category FROM document_rules
        UNION SELECT DISTINCT category FROM new_supplier_requests
        ORDER BY category
    """)
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def add_timeline(supplier_id=None, request_id=None, event_type="", detail="", user=""):
    exec_sql("INSERT INTO supplier_timeline (supplier_id, request_id, event_type, event_detail, user) VALUES (?, ?, ?, ?, ?)", (supplier_id, request_id, event_type, detail, user))


def find_duplicate_suppliers(name, email=""):
    name_key = normalise_name(name)
    email_key = normalise_email(email)
    if email_key:
        return df_sql("""
            SELECT supplier_id, supplier_name, supplier_email, category, owner, approval_status
            FROM suppliers
            WHERE supplier_key=? OR email_key=? OR lower(supplier_email)=?
            ORDER BY supplier_name
        """, (name_key, email_key, email_key))
    return df_sql("""
        SELECT supplier_id, supplier_name, supplier_email, category, owner, approval_status
        FROM suppliers
        WHERE supplier_key=?
        ORDER BY supplier_name
    """, (name_key,))


def duplicate_report():
    suppliers = df_sql("SELECT supplier_id, supplier_name, supplier_email, supplier_key, email_key, category FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        return pd.DataFrame()
    rows = []
    name_dupes = suppliers[suppliers["supplier_key"].notna() & suppliers["supplier_key"].duplicated(keep=False)]
    for _, r in name_dupes.iterrows():
        rows.append({"Duplicate Type": "Name match", "Supplier ID": r["supplier_id"], "Supplier Name": r["supplier_name"], "Email": r["supplier_email"], "Category": r["category"]})
    email_dupes = suppliers[(suppliers["email_key"].fillna("") != "") & suppliers["email_key"].duplicated(keep=False)]
    for _, r in email_dupes.iterrows():
        rows.append({"Duplicate Type": "Email match", "Supplier ID": r["supplier_id"], "Supplier Name": r["supplier_name"], "Email": r["supplier_email"], "Category": r["category"]})
    return pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame()


def render_file_preview(file_path, file_name):
    path = Path(file_path or "")
    if not path.exists():
        st.warning("The file record exists, but the physical file could not be found in storage. On Streamlit Cloud, local uploads may disappear after a redeploy.")
        return
    data = path.read_bytes()
    st.download_button("Download / open document", data, file_name=file_name or path.name)
    suffix = path.suffix.lower()
    if suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        st.image(data, caption=file_name or path.name, use_container_width=True)
    elif suffix == ".pdf":
        encoded = base64.b64encode(data).decode("utf-8")
        st.markdown(f"<iframe src='data:application/pdf;base64,{encoded}' width='100%' height='650'></iframe>", unsafe_allow_html=True)
    elif suffix in [".txt", ".csv", ".log"]:
        st.text_area("File preview", data.decode("utf-8", errors="replace"), height=350)
    else:
        st.info("Preview is not available for this file type. Use the download button above to open it.")


def supplier_checklist(supplier):
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (supplier["category"] or "",))
    docs = df_sql("SELECT * FROM supplier_documents WHERE supplier_id=? AND review_status != 'Archived / Ignore'", (supplier["supplier_id"],))
    rows = []
    for _, rule in rules.iterrows():
        matching = docs[docs["document_type"] == rule["document_type"]]
        if matching.empty:
            rows.append({"Document Type": rule["document_type"], "Status": "Red" if rule["is_critical"] else "Amber", "Issue": "Missing document", "Review Status": "Not received", "Expiry Date": ""})
            continue
        accepted = matching[matching["review_status"] == "Accepted"]
        latest = (accepted if not accepted.empty else matching).sort_values("uploaded_at", ascending=False).iloc[0]
        if latest["review_status"] != "Accepted":
            status, issue = "Amber", "Needs review"
        else:
            dleft = days_left(latest["expiry_date"])
            if dleft is None:
                status, issue = "Amber", "No expiry date"
            elif dleft < 0:
                status, issue = "Red", "Expired document"
            elif dleft <= int(rule["warning_days"] or 60):
                status, issue = "Amber", "Expiring soon"
            else:
                status, issue = "Green", ""
        rows.append({"Document Type": rule["document_type"], "Status": status, "Issue": issue, "Review Status": latest["review_status"], "Expiry Date": latest["expiry_date"] or ""})
    return pd.DataFrame(rows)


def supplier_readiness(supplier):
    checklist = supplier_checklist(supplier)
    missing = int((checklist["Issue"] == "Missing document").sum()) if not checklist.empty else 0
    needs_review = int((checklist["Issue"] == "Needs review").sum()) if not checklist.empty else 0
    expired = int((checklist["Issue"] == "Expired document").sum()) if not checklist.empty else 0
    expiring = int((checklist["Issue"] == "Expiring soon").sum()) if not checklist.empty else 0
    score = max(0, min(100, 100 - missing * 18 - needs_review * 10 - expired * 25 - expiring * 8))
    if supplier["approval_status"] == "Blocked" or expired > 0:
        buy = "Do Not Use"
    elif supplier["approval_status"] in ["Pending", "On Hold"]:
        buy = "Approval Pending"
    elif missing or needs_review or expiring:
        buy = "Can Buy with Warning"
    else:
        buy = "Can Buy"
    reasons = []
    if missing: reasons.append(f"{missing} missing document(s)")
    if needs_review: reasons.append(f"{needs_review} document(s) awaiting review")
    if expired: reasons.append(f"{expired} expired document(s)")
    if expiring: reasons.append(f"{expiring} document(s) expiring soon")
    if supplier["approval_status"] != "Approved": reasons.append(f"Approval status is {supplier['approval_status']}")
    return score, buy, reasons


def supplier_table():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    for _, s in suppliers.iterrows():
        score, buy, reasons = supplier_readiness(s)
        rows.append({"Supplier ID": s["supplier_id"], "Supplier Code": s["supplier_code"], "Supplier Name": s["supplier_name"], "Can I Buy?": buy, "Readiness": score, "Reasons": "; ".join(reasons), "Email": s["supplier_email"], "Category": s["category"], "Owner": s["owner"], "Approval Status": s["approval_status"], "Risk": s["risk_level"], "Spend": s["annual_spend"] or 0})
    return pd.DataFrame(rows)


def evidence_gaps():
    rows = []
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    for _, s in suppliers.iterrows():
        checklist = supplier_checklist(s)
        if not checklist.empty:
            for _, doc in checklist[checklist["Status"].isin(["Red", "Amber"])].iterrows():
                rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap": doc["Issue"], "Severity": doc["Status"], "Owner": s["owner"], "Detail": doc["Document Type"], "Action": "Review document" if doc["Issue"] == "Needs review" else "Chase supplier"})
        if not s["owner"]:
            rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap": "Missing owner", "Severity": "Amber", "Owner": "", "Detail": "No internal owner", "Action": "Assign owner"})
    return pd.DataFrame(rows)


def missing_docs_for_supplier(supplier):
    checklist = supplier_checklist(supplier)
    if checklist.empty:
        return []
    return checklist[checklist["Issue"].isin(["Missing document", "Expired document", "Expiring soon", "Needs review", "No expiry date"])]


def build_email(supplier, email_type, document_rows, sender, custom_message):
    template = df_sql("SELECT * FROM email_templates WHERE template_type=?", (email_type,))
    if template.empty:
        subject = f"Supplier query - {supplier['supplier_name']}"
        body = "Hi,\n\n{custom_message}\n\nMany thanks,\n{sender}"
    else:
        subject = template.iloc[0]["subject"]
        body = template.iloc[0]["body"]
    document_list = ""
    if document_rows is not None and not document_rows.empty:
        lines = []
        for _, row in document_rows.iterrows():
            detail = row["Document Type"]
            if row.get("Issue"):
                detail += f" - {row['Issue']}"
            if row.get("Expiry Date"):
                detail += f" (expiry: {row['Expiry Date']})"
            lines.append(f"- {detail}")
        document_list = "\n".join(lines)
    else:
        document_list = "- Please confirm your latest supplier information and compliance documents."
    replacements = {
        "{supplier_name}": supplier["supplier_name"] or "",
        "{document_list}": document_list,
        "{sender}": sender or "SupplierPass",
        "{custom_message}": custom_message or "",
    }
    for key, value in replacements.items():
        subject = subject.replace(key, value)
        body = body.replace(key, value)
    return subject, body


def create_supplier_from_request_safe(request_id, approved_by, notes):
    c = conn(); cur = c.cursor()
    req = cur.execute("SELECT * FROM new_supplier_requests WHERE request_id=?", (request_id,)).fetchone()
    if req is None:
        c.close(); return None, "Request not found."
    if req["converted_supplier_id"]:
        supplier_id = int(req["converted_supplier_id"])
        cur.execute("UPDATE new_supplier_requests SET status='Converted to Supplier' WHERE request_id=?", (request_id,))
        c.commit(); c.close()
        return supplier_id, f"Already converted to supplier ID {supplier_id}. No duplicate was created."
    if req["status"] != "Awaiting Approval":
        c.close(); return None, f"This request is {req['status']}, so it cannot be approved again."
    name_key = normalise_name(req["supplier_name"]); email_key = normalise_email(req["supplier_email"])
    duplicate = None
    if email_key:
        duplicate = cur.execute("SELECT * FROM suppliers WHERE supplier_key=? OR email_key=? OR lower(supplier_email)=? ORDER BY supplier_id LIMIT 1", (name_key, email_key, email_key)).fetchone()
    else:
        duplicate = cur.execute("SELECT * FROM suppliers WHERE supplier_key=? ORDER BY supplier_id LIMIT 1", (name_key,)).fetchone()
    if duplicate:
        supplier_id = int(duplicate["supplier_id"])
        cur.execute("""
            UPDATE new_supplier_requests
            SET status='Converted to Supplier', approval_decision='Approved - linked existing supplier', approval_notes=?, approved_by=?, approved_at=CURRENT_TIMESTAMP, converted_supplier_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE request_id=? AND converted_supplier_id IS NULL
        """, (notes, approved_by, supplier_id, request_id))
        cur.execute("INSERT INTO supplier_timeline (supplier_id, request_id, event_type, event_detail, user) VALUES (?, ?, ?, ?, ?)", (supplier_id, request_id, "Onboarding linked to existing supplier", req["supplier_name"], approved_by))
        c.commit(); c.close()
        return supplier_id, f"A matching supplier already existed, so the request was linked to supplier ID {supplier_id}. No duplicate was created."
    cur.execute("""
        INSERT INTO suppliers
        (supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, risk_level, annual_spend, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'Approved', 'Medium', ?, ?)
    """, (req["supplier_name"], name_key, req["supplier_email"], email_key, req["category"], req["requested_by"], float(req["expected_annual_spend"] or 0), f"Created from onboarding request {request_id}. {req['reason_needed'] or ''}\nApproval notes: {notes or ''}"))
    supplier_id = cur.lastrowid
    cur.execute("""
        UPDATE new_supplier_requests
        SET status='Converted to Supplier', approval_decision='Approved', approval_notes=?, approved_by=?, approved_at=CURRENT_TIMESTAMP, converted_supplier_id=?, updated_at=CURRENT_TIMESTAMP
        WHERE request_id=? AND converted_supplier_id IS NULL
    """, (notes, approved_by, supplier_id, request_id))
    cur.execute("INSERT INTO supplier_timeline (supplier_id, request_id, event_type, event_detail, user) VALUES (?, ?, ?, ?, ?)", (supplier_id, request_id, "Approved and supplier created", req["supplier_name"], approved_by))
    c.commit(); c.close()
    return supplier_id, f"Approved and supplier created. Supplier ID: {supplier_id}."


def load_demo_data():
    rows = [
        ("SUP001", "ABC Transport Ltd", normalise_name("ABC Transport Ltd"), "accounts@abctransport.co.uk", normalise_email("accounts@abctransport.co.uk"), "Transport", "Connor", "Approved", "Medium", 85000, "Important"),
        ("SUP002", "Yorkshire Board Supplies", normalise_name("Yorkshire Board Supplies"), "quality@yorkshireboard.co.uk", normalise_email("quality@yorkshireboard.co.uk"), "Manufacturing", "Quality", "Approved", "High", 120000, "Critical"),
        ("SUP003", "Fast Fix Maintenance", normalise_name("Fast Fix Maintenance"), "fastfix@gmail.com", normalise_email("fastfix@gmail.com"), "Contractor", "Maintenance", "Pending", "Medium", 14000, "Standard"),
    ]
    imported = skipped = 0
    for row in rows:
        if find_duplicate_suppliers(row[1], row[3]).empty:
            exec_sql("INSERT INTO suppliers (supplier_code, supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, risk_level, annual_spend, criticality) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
            imported += 1
        else:
            skipped += 1
    st.success(f"Demo data loaded. Added {imported}; skipped {skipped} duplicate(s).")


def today_screen():
    hero("Today in SupplierPass", "Your daily queue: process documents, approve suppliers, send chasers and fix evidence gaps.")
    suppliers = supplier_table(); gaps = evidence_gaps()
    docs_to_review = df_sql("SELECT * FROM supplier_documents WHERE review_status IN ('Uploaded', 'Under Review')")
    open_requests = df_sql("SELECT * FROM new_supplier_requests WHERE status IN ('Draft', 'Awaiting Approval')")
    missing_email = df_sql("SELECT * FROM suppliers WHERE supplier_email IS NULL OR supplier_email='' OR supplier_email NOT LIKE '%@%' ")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Suppliers", len(suppliers), "in register")
    with c2: kpi("Documents to process", len(docs_to_review), "waiting review")
    with c3: kpi("Onboarding queue", len(open_requests), "draft/approval")
    with c4: kpi("Email gaps", len(missing_email), "missing supplier emails")
    if suppliers.empty:
        st.warning("No suppliers loaded yet.")
        if st.button("Load demo data"):
            load_demo_data(); st.rerun()
    show_df(gaps, "No evidence gaps found.")


def suppliers_screen():
    hero("Supplier Register", "Import suppliers, view readiness and update supplier details.")
    tab_import, tab_register, tab_duplicates = st.tabs(["Import", "Register", "Duplicate Check"])
    with tab_import:
        file = st.file_uploader("Supplier CSV", type=["csv"])
        if file:
            data = pd.read_csv(file); st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            cols = data.columns.tolist(); c1, c2, c3 = st.columns(3)
            c_name = c1.selectbox("Supplier Name *", cols); c_code = c1.selectbox("Supplier Code", [""] + cols); c_email = c1.selectbox("Email", [""] + cols)
            c_cat = c2.selectbox("Category", [""] + cols); c_owner = c2.selectbox("Owner", [""] + cols); c_status = c2.selectbox("Status", [""] + cols)
            c_spend = c3.selectbox("Annual Spend", [""] + cols); default_cat = c3.selectbox("Default category", [""] + categories())
            if st.button("Import suppliers", type="primary"):
                imported = skipped = 0
                for _, r in data.iterrows():
                    name = str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not name: continue
                    email = str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else ""
                    if not find_duplicate_suppliers(name, email).empty:
                        skipped += 1; continue
                    try: spend = float(r[c_spend]) if c_spend and pd.notna(r[c_spend]) else 0
                    except Exception: spend = 0
                    exec_sql("""
                        INSERT INTO suppliers
                        (supplier_code, supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, risk_level, annual_spend)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Medium', ?)
                    """, (
                        str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else "", name, normalise_name(name), email, normalise_email(email),
                        str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else default_cat,
                        str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "", str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Pending", spend,
                    ))
                    imported += 1
                st.success(f"Imported {imported} supplier(s). Skipped {skipped} duplicate(s).")
                st.rerun()
    with tab_register:
        show_df(supplier_table(), "No suppliers yet.")
    with tab_duplicates:
        hint("This checks likely duplicates by normalised supplier name and exact email.")
        show_df(duplicate_report(), "No likely duplicates found.")


def upload_document_screen():
    hero("Upload Document", "Upload files against a supplier. Uploading stores the file; processing accepts it as evidence.")
    hint("After upload, go to Document Processing. A file does not improve supplier readiness until it is marked Accepted.")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.info("Add/import suppliers first."); return
    options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
    supplier_id = options[st.selectbox("Supplier", list(options.keys()))]
    supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).iloc[0]
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (supplier["category"] or "",))
    doc_types = rules["document_type"].tolist() if not rules.empty else []
    with st.form("upload_doc"):
        choice = st.selectbox("Document type", doc_types + ["Other"]); other = st.text_input("Other document type") if choice == "Other" else ""
        expiry = st.date_input("Expiry date", value=None); upload = st.file_uploader("Document"); notes = st.text_area("Notes")
        if st.form_submit_button("Upload document", type="primary"):
            doc_type = other.strip() if choice == "Other" else choice
            if not upload or not doc_type:
                st.error("Choose a file and document type."); return
            folder = UPLOAD_DIR / str(supplier_id); folder.mkdir(exist_ok=True)
            safe_name = upload.name.replace("/", "_").replace("\\", "_"); file_path = folder / safe_name; file_path.write_bytes(upload.getbuffer())
            exec_sql("INSERT INTO supplier_documents (supplier_id, document_type, file_name, file_path, expiry_date, notes, review_status) VALUES (?, ?, ?, ?, ?, ?, 'Uploaded')", (supplier_id, doc_type, safe_name, str(file_path), expiry.isoformat() if expiry else None, notes))
            add_timeline(supplier_id, None, "Document uploaded", doc_type, "")
            st.success("Document uploaded. It is now waiting in Document Processing.")


def document_processing_screen():
    hero("Document Processing", "Review uploaded files and decide whether they count as accepted supplier evidence.")
    hint("Only Uploaded or Under Review documents appear by default. Accepted, rejected and archived documents are removed from the working list.")
    show_processed = st.checkbox("Show accepted/rejected/archived documents", value=False)
    status_filter = "" if show_processed else "WHERE COALESCE(d.review_status, 'Uploaded') IN ('Uploaded', 'Under Review')"
    docs = df_sql(f"""
        SELECT d.*, COALESCE(s.supplier_name, 'Unlinked document') AS supplier_name, s.category AS supplier_category
        FROM supplier_documents d
        LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
        {status_filter}
        ORDER BY CASE WHEN d.review_status IN ('Uploaded','Under Review') THEN 0 ELSE 1 END, d.uploaded_at DESC
    """)
    if docs.empty:
        st.success("No documents are waiting for processing."); return
    show_df(docs[["document_id", "supplier_id", "supplier_name", "supplier_category", "document_type", "file_name", "expiry_date", "review_status", "uploaded_at"]])
    options = {f"{r['supplier_name']} - {r['document_type']} - {r['file_name']} ({r['document_id']})": int(r["document_id"]) for _, r in docs.iterrows()}
    document_id = options[st.selectbox("Select document to process", list(options.keys()))]
    doc = docs[docs["document_id"] == document_id].iloc[0]
    st.markdown("<div class='review-card'>", unsafe_allow_html=True)
    st.subheader("Document to review")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.write(f"**Supplier:** {doc['supplier_name']}"); st.write(f"**Current type:** {doc['document_type']}"); st.write(f"**File:** {doc['file_name']}"); st.write(f"**Current status:** {doc['review_status']}"); st.write(f"**Uploaded:** {doc['uploaded_at']}")
    with c2: render_file_preview(doc["file_path"], doc["file_name"])
    st.markdown("</div>", unsafe_allow_html=True)
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.error("There are no suppliers to assign this document to. Add/import a supplier first."); return
    supplier_options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
    supplier_keys = list(supplier_options.keys()); current_key = supplier_keys[0]
    for key, val in supplier_options.items():
        if val == doc["supplier_id"]: current_key = key; break
    assigned_key = st.selectbox("Assigned supplier", supplier_keys, index=supplier_keys.index(current_key)); assigned_id = supplier_options[assigned_key]
    assigned_supplier = suppliers[suppliers["supplier_id"] == assigned_id].iloc[0]
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (assigned_supplier["category"] or "",))
    doc_types = rules["document_type"].tolist() if not rules.empty else []
    if doc["document_type"] not in doc_types: doc_types = [doc["document_type"]] + doc_types
    doc_types = list(dict.fromkeys(doc_types + ["Other"]))
    with st.form("process_doc"):
        confirmed_type = st.selectbox("Confirmed document type", doc_types, index=doc_types.index(doc["document_type"]) if doc["document_type"] in doc_types else 0)
        other = st.text_input("Other document type") if confirmed_type == "Other" else ""
        expiry = st.date_input("Confirmed expiry date", value=parse_date(doc["expiry_date"]))
        review_status = st.selectbox("Review decision", DOC_STATUSES, index=DOC_STATUSES.index(doc["review_status"]) if doc["review_status"] in DOC_STATUSES else 0)
        reviewed_by = st.text_input("Reviewed by", value=doc["reviewed_by"] or ""); review_notes = st.text_area("Review notes", value=doc["review_notes"] or "")
        if st.form_submit_button("Save review decision", type="primary"):
            final_type = other.strip() if confirmed_type == "Other" else confirmed_type
            if not final_type: st.error("Document type is required."); return
            exec_sql("""
                UPDATE supplier_documents
                SET supplier_id=?, document_type=?, expiry_date=?, review_status=?, reviewed_by=?, review_notes=?, reviewed_at=CURRENT_TIMESTAMP
                WHERE document_id=?
            """, (assigned_id, final_type, expiry.isoformat() if expiry else None, review_status, reviewed_by, review_notes, document_id))
            add_timeline(assigned_id, None, f"Document {review_status}", final_type, reviewed_by)
            st.success("Document updated. It has been removed from the working queue unless it remains Uploaded or Under Review."); st.rerun()
    st.subheader("Supplier checklist after this decision")
    show_df(supplier_checklist(assigned_supplier), "No document rules configured for this supplier category.")


def email_centre_screen():
    hero("Email Centre", "Generate supplier chasers, open them in your email app and log what has been sent.")
    hint("This prototype does not send directly through Microsoft 365 yet. It generates the email, opens it using a mailto link, and logs the chase. Direct sending can be added later with Microsoft Graph, SendGrid or SMTP.")
    tab_compose, tab_chase, tab_templates, tab_log = st.tabs(["Compose", "Chase Queue", "Templates", "Email Log"])
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    with tab_compose:
        if suppliers.empty:
            st.info("No suppliers yet."); return
        options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
        selected_supplier = st.selectbox("Supplier", list(options.keys()))
        supplier_id = options[selected_supplier]
        supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).iloc[0]
        problem_docs = missing_docs_for_supplier(supplier)
        c1, c2 = st.columns(2)
        with c1:
            email_type = st.selectbox("Email type", EMAIL_TYPES)
            recipient = st.text_input("To", value=supplier["supplier_email"] or "")
            sender = st.text_input("From / signature name", value=supplier["owner"] or "SupplierPass")
        with c2:
            if supplier["supplier_email"] in [None, ""] or "@" not in str(supplier["supplier_email"]):
                st.warning("This supplier does not have a valid email address in the register.")
            show_df(problem_docs, "No obvious document gaps for this supplier.")
        custom_message = st.text_area("Extra message / notes to include", "")
        subject, body = build_email(supplier, email_type, problem_docs, sender, custom_message)
        subject = st.text_input("Subject", value=subject)
        body = st.text_area("Email body", value=body, height=320)
        mailto = f"mailto:{quote(recipient)}?subject={quote(subject)}&body={quote(body)}"
        st.markdown(f"[Open in email app]({mailto})")
        c1, c2 = st.columns(2)
        if c1.button("Log as drafted"):
            exec_sql("INSERT INTO email_log (supplier_id, email_type, recipient, subject, body, status, sent_by) VALUES (?, ?, ?, ?, ?, 'Drafted', ?)", (supplier_id, email_type, recipient, subject, body, sender))
            add_timeline(supplier_id, None, "Email drafted", email_type, sender)
            st.success("Email logged as drafted.")
        if c2.button("Mark as sent"):
            exec_sql("INSERT INTO email_log (supplier_id, email_type, recipient, subject, body, status, sent_by) VALUES (?, ?, ?, ?, ?, 'Sent / manually recorded', ?)", (supplier_id, email_type, recipient, subject, body, sender))
            add_timeline(supplier_id, None, "Email sent / manually recorded", email_type, sender)
            st.success("Email logged as sent.")
    with tab_chase:
        gaps = evidence_gaps()
        if gaps.empty:
            st.success("No evidence gaps found.")
        else:
            chase = gaps[gaps["Action"].isin(["Chase supplier", "Review document"])]
            show_df(chase, "No supplier chases needed.")
            st.caption("Use the Compose tab to select one of these suppliers and generate the chase email.")
    with tab_templates:
        templates = df_sql("SELECT * FROM email_templates ORDER BY template_type")
        show_df(templates, "No templates yet.")
        st.subheader("Edit template")
        template_type = st.selectbox("Template", EMAIL_TYPES)
        existing = df_sql("SELECT * FROM email_templates WHERE template_type=?", (template_type,))
        current_subject = existing.iloc[0]["subject"] if not existing.empty else ""
        current_body = existing.iloc[0]["body"] if not existing.empty else ""
        with st.form("template_edit"):
            subject = st.text_input("Template subject", value=current_subject)
            body = st.text_area("Template body", value=current_body, height=240)
            st.caption("Available fields: {supplier_name}, {document_list}, {sender}, {custom_message}")
            if st.form_submit_button("Save template"):
                exec_sql("INSERT OR REPLACE INTO email_templates (template_type, subject, body, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (template_type, subject, body))
                st.success("Template saved."); st.rerun()
    with tab_log:
        log = df_sql("""
            SELECT e.*, s.supplier_name
            FROM email_log e
            LEFT JOIN suppliers s ON e.supplier_id=s.supplier_id
            ORDER BY e.sent_at DESC
        """)
        show_df(log, "No emails logged yet.")


def onboarding_screen():
    hero("Onboarding", "Create new supplier requests. Submitted requests go to the Approval Queue.")
    with st.form("new_request"):
        a, b = st.columns(2)
        name = a.text_input("Supplier name *"); email = a.text_input("Supplier email")
        category = b.selectbox("Category", [""] + categories()); spend = b.number_input("Expected spend", min_value=0.0, step=100.0)
        urgency = b.selectbox("Urgency", ["Low", "Normal", "High", "Critical"], index=1); requested_by = b.text_input("Requested by")
        reason = st.text_area("Why is the supplier needed?"); submit_now = st.checkbox("Submit for approval now", value=True)
        if st.form_submit_button("Create request", type="primary"):
            if not name:
                st.error("Supplier name is required")
            else:
                existing = find_duplicate_suppliers(name, email)
                if not existing.empty:
                    st.warning("A matching supplier already exists. Approval will link to the existing supplier rather than create a duplicate."); st.dataframe(existing, use_container_width=True, hide_index=True)
                status = "Awaiting Approval" if submit_now else "Draft"
                request_id = exec_sql("""
                    INSERT INTO new_supplier_requests
                    (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, email, requested_by, category, reason, spend, urgency, status))
                add_timeline(None, request_id, "Onboarding request created", f"{name} - {status}", requested_by)
                st.success(f"Request created with status: {status}")
    show_df(df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"), "No supplier requests yet.")


def approval_queue_screen():
    hero("Approval Queue", "Duplicate-safe approval: each request can only create or link one supplier.")
    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    if requests.empty:
        st.info("No onboarding requests yet. Create one in Onboarding."); return
    active_only = st.checkbox("Show only active requests", value=True)
    view = requests[requests["status"].isin(["Draft", "Awaiting Approval"])] if active_only else requests
    show_df(view[["request_id", "supplier_name", "category", "requested_by", "expected_annual_spend", "urgency", "status", "approved_by", "approved_at", "converted_supplier_id"]])
    if view.empty: return
    options = {f"{r['supplier_name']} ({r['request_id']}) - {r['status']}": int(r["request_id"]) for _, r in view.iterrows()}
    request_id = options[st.selectbox("Select request", list(options.keys()))]
    req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (request_id,)).iloc[0]
    st.subheader(req["supplier_name"])
    st.write(f"**Status:** {req['status']} | **Category:** {req['category']} | **Spend:** £{float(req['expected_annual_spend'] or 0):,.2f} | **Urgency:** {req['urgency']}")
    st.write(f"**Requested by:** {req['requested_by'] or ''}"); st.write(req["reason_needed"] or "")
    duplicate_matches = find_duplicate_suppliers(req["supplier_name"], req["supplier_email"])
    if not duplicate_matches.empty:
        st.warning("Possible existing supplier match found. Approval will link to the existing supplier instead of creating another one."); st.dataframe(duplicate_matches, use_container_width=True, hide_index=True)
    notes = st.text_area("Decision notes", value=req["approval_notes"] or ""); decided_by = st.text_input("Decision by", value=req["approved_by"] or "")
    if req["status"] == "Draft":
        if st.button("Submit for approval", type="primary"):
            exec_sql("UPDATE new_supplier_requests SET status='Awaiting Approval', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (request_id,))
            add_timeline(None, request_id, "Request submitted for approval", req["supplier_name"], decided_by)
            st.success("Submitted for approval."); st.rerun()
    elif req["status"] == "Awaiting Approval":
        c1, c2 = st.columns(2); button_text = "Approve & Link Existing Supplier" if not duplicate_matches.empty else "Approve & Create Supplier"
        if c1.button(button_text, type="primary", key=f"approve_{request_id}"):
            supplier_id, message = create_supplier_from_request_safe(request_id, decided_by, notes)
            st.success(message) if supplier_id else st.warning(message)
            st.rerun()
        if c2.button("Reject", key=f"reject_{request_id}"):
            exec_sql("""
                UPDATE new_supplier_requests
                SET status='Rejected', approval_decision='Rejected', approval_notes=?, approved_by=?, approved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE request_id=? AND status='Awaiting Approval'
            """, (notes, decided_by, request_id))
            add_timeline(None, request_id, "Request rejected", req["supplier_name"], decided_by)
            st.warning("Request rejected."); st.rerun()
    elif req["status"] == "Converted to Supplier":
        st.success(f"This request has already been approved and converted/linked to supplier ID {req['converted_supplier_id']}.")
    elif req["status"] == "Rejected":
        st.warning("This request has been rejected.")


def risk_screen():
    hero("Risk & Compliance", "Evidence gaps and document rules.")
    tab_gaps, tab_rules = st.tabs(["Evidence Gaps", "Document Rules"])
    with tab_gaps: show_df(evidence_gaps(), "No evidence gaps.")
    with tab_rules: show_df(df_sql("SELECT * FROM document_rules ORDER BY category, is_critical DESC, document_type"), "No document rules yet.")


def reports_screen():
    hero("Reports", "Download supplier readiness, evidence, email and onboarding data.")
    gaps = evidence_gaps(); c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Suppliers", len(supplier_table()), "records")
    with c2: kpi("Evidence gaps", len(gaps), "open")
    with c3: kpi("Emails logged", len(df_sql("SELECT * FROM email_log")), "drafted/sent")
    with c4: kpi("Likely duplicates", len(duplicate_report()), "check required")
    show_df(gaps, "No evidence gaps.")
    xlsx = DATA_DIR / f"supplierpass_v15_audit_{date.today().isoformat()}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        supplier_table().to_excel(writer, index=False, sheet_name="Readiness")
        df_sql("SELECT * FROM suppliers").to_excel(writer, index=False, sheet_name="Suppliers")
        duplicate_report().to_excel(writer, index=False, sheet_name="Duplicate Check")
        evidence_gaps().to_excel(writer, index=False, sheet_name="Evidence Gaps")
        df_sql("SELECT * FROM supplier_documents").to_excel(writer, index=False, sheet_name="Documents")
        df_sql("SELECT * FROM new_supplier_requests").to_excel(writer, index=False, sheet_name="Onboarding")
        df_sql("SELECT * FROM email_log").to_excel(writer, index=False, sheet_name="Email Log")
        df_sql("SELECT * FROM supplier_timeline").to_excel(writer, index=False, sheet_name="Timeline")
    with open(xlsx, "rb") as f:
        st.download_button("Download audit pack", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def admin_screen():
    hero("Admin", "Demo mode and prototype notes.")
    if st.button("Load demo data"):
        load_demo_data(); st.rerun()
    st.subheader("Likely duplicate suppliers")
    show_df(duplicate_report(), "No likely duplicates found.")
    st.warning("Prototype only. Production still needs authentication, tenant separation, secure storage, backups, licensing, direct email sending and support tooling. On Streamlit Cloud, local uploaded files are not permanent after redeploys; production needs proper cloud object storage.")


init_db(); apply_style()
st.sidebar.markdown("# SupplierPass"); st.sidebar.caption(APP_VERSION)
page = st.sidebar.radio("Navigation", ["Today", "Suppliers", "Upload Document", "Document Processing", "Email Centre", "Risk & Compliance", "Onboarding", "Approval Queue", "Reports", "Admin"])

if page == "Today": today_screen()
elif page == "Suppliers": suppliers_screen()
elif page == "Upload Document": upload_document_screen()
elif page == "Document Processing": document_processing_screen()
elif page == "Email Centre": email_centre_screen()
elif page == "Risk & Compliance": risk_screen()
elif page == "Onboarding": onboarding_screen()
elif page == "Approval Queue": approval_queue_screen()
elif page == "Reports": reports_screen()
elif page == "Admin": admin_screen()
