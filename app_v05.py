import smtplib
import sqlite3
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
UPLOAD_DIR = APP_DIR / "uploads"
DB_PATH = DATA_DIR / "supplierpass.db"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="SupplierPass", page_icon="✅", layout="wide")

# -----------------------------------------------------------------------------
# Commercial prototype note
# -----------------------------------------------------------------------------
# This is still a Streamlit prototype, but the UX is now shaped like a sellable
# product: command centre, guided setup, supplier lifecycle, compliance actions,
# approval routing, document rules, email previews/logging, and audit exports.
# -----------------------------------------------------------------------------

APP_VERSION = "v0.5 commercial prototype"
APP_NAME = "SupplierPass"

SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
URGENCY_LEVELS = ["Low", "Normal", "High", "Critical"]


# -----------------------------------------------------------------------------
# Database helpers
# -----------------------------------------------------------------------------

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def exec_sql(sql, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(sql, params)
    c.commit()
    new_id = cur.lastrowid
    c.close()
    return new_id


def many_sql(sql, rows):
    if not rows:
        return
    c = conn()
    cur = c.cursor()
    cur.executemany(sql, rows)
    c.commit()
    c.close()


def df_sql(sql, params=()):
    c = conn()
    df = pd.read_sql_query(sql, c, params=params)
    c.close()
    return df


def table_exists(name):
    return not df_sql("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).empty


def ensure_column(table, column, definition):
    info = df_sql(f"PRAGMA table_info({table})")
    if column not in info["name"].tolist():
        exec_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# -----------------------------------------------------------------------------
# Initial schema
# -----------------------------------------------------------------------------

def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_code TEXT,
        supplier_name TEXT NOT NULL,
        supplier_email TEXT,
        category TEXT,
        owner TEXT,
        approval_status TEXT DEFAULT 'Approved',
        risk_level TEXT DEFAULT 'Medium',
        annual_spend REAL DEFAULT 0,
        criticality TEXT DEFAULT 'Standard',
        preferred_supplier INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS supplier_documents (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        document_type TEXT NOT NULL,
        file_name TEXT,
        file_path TEXT,
        expiry_date TEXT,
        notes TEXT,
        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS document_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        document_type TEXT NOT NULL,
        is_critical INTEGER DEFAULT 1,
        warning_days INTEGER DEFAULT 60,
        UNIQUE(category, document_type)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS new_supplier_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        supplier_email TEXT,
        requested_by TEXT,
        category TEXT,
        reason_needed TEXT,
        expected_annual_spend REAL,
        urgency TEXT DEFAULT 'Normal',
        status TEXT DEFAULT 'Draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS approval_stages (
        stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        stage_name TEXT NOT NULL,
        approver_name TEXT NOT NULL,
        approver_email TEXT NOT NULL,
        sequence_order INTEGER NOT NULL,
        is_required INTEGER DEFAULT 1,
        UNIQUE(category, stage_name, sequence_order)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS approval_decisions (
        decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        stage_id INTEGER NOT NULL,
        decision TEXT NOT NULL,
        decided_by TEXT,
        notes TEXT,
        decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(request_id, stage_id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS email_log (
        email_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        supplier_id INTEGER,
        email_type TEXT,
        recipient TEXT,
        subject TEXT,
        body TEXT,
        status TEXT,
        error_message TEXT,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        request_id INTEGER,
        action TEXT,
        detail TEXT,
        user TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.commit()
    c.close()

    # Safe migrations for older local databases.
    ensure_column("suppliers", "annual_spend", "REAL DEFAULT 0")
    ensure_column("suppliers", "criticality", "TEXT DEFAULT 'Standard'")
    ensure_column("suppliers", "preferred_supplier", "INTEGER DEFAULT 0")

    seed_defaults()


def seed_defaults():
    default_stages = [
        ("Raw Material", "Procurement Review", "Procurement", "procurement@example.com", 1, 1),
        ("Raw Material", "Quality Review", "Quality", "quality@example.com", 2, 1),
        ("Raw Material", "Finance Review", "Finance", "finance@example.com", 3, 1),
        ("Transport", "Procurement Review", "Procurement", "procurement@example.com", 1, 1),
        ("Transport", "Quality Review", "Quality", "quality@example.com", 2, 1),
        ("Transport", "Finance Review", "Finance", "finance@example.com", 3, 1),
        ("Contractor", "H&S Review", "Health and Safety", "hs@example.com", 1, 1),
        ("Contractor", "Finance Review", "Finance", "finance@example.com", 2, 1),
        ("IT / Software", "IT / Cyber Review", "IT", "it@example.com", 1, 1),
        ("IT / Software", "Finance Review", "Finance", "finance@example.com", 2, 1),
        ("Packaging", "Procurement Review", "Procurement", "procurement@example.com", 1, 1),
        ("Packaging", "Quality Review", "Quality", "quality@example.com", 2, 1),
        ("Packaging", "Finance Review", "Finance", "finance@example.com", 3, 1),
    ]
    many_sql("""INSERT OR IGNORE INTO approval_stages
        (category, stage_name, approver_name, approver_email, sequence_order, is_required)
        VALUES (?, ?, ?, ?, ?, ?)""", default_stages)

    default_docs = [
        ("Raw Material", "ISO 9001 Certificate", 1, 60),
        ("Raw Material", "Public Liability Insurance", 1, 60),
        ("Raw Material", "Supplier Questionnaire", 1, 365),
        ("Transport", "Public Liability Insurance", 1, 60),
        ("Transport", "Goods in Transit Insurance", 1, 60),
        ("Transport", "Operator Licence", 1, 60),
        ("Transport", "Rate Agreement", 0, 365),
        ("Contractor", "Public Liability Insurance", 1, 60),
        ("Contractor", "RAMS", 1, 30),
        ("Contractor", "Health & Safety Policy", 1, 365),
        ("IT / Software", "Cyber Security Questionnaire", 1, 365),
        ("IT / Software", "Data Processing Agreement", 1, 365),
        ("Packaging", "ISO 9001 Certificate", 1, 60),
        ("Packaging", "Public Liability Insurance", 1, 60),
        ("Packaging", "FSC / PEFC Certificate", 0, 60),
    ]
    many_sql("""INSERT OR IGNORE INTO document_rules
        (category, document_type, is_critical, warning_days)
        VALUES (?, ?, ?, ?)""", default_docs)


# -----------------------------------------------------------------------------
# UI styling
# -----------------------------------------------------------------------------

def apply_style():
    st.markdown("""
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stSidebar"] {background: #0f172a;}
    [data-testid="stSidebar"] * {color: #f8fafc !important;}
    .sp-hero {border-radius: 20px; padding: 22px 26px; background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #0f766e 100%); color: white; margin-bottom: 18px;}
    .sp-hero h1 {margin: 0; color: white; font-size: 2.1rem;}
    .sp-hero p {margin: 6px 0 0 0; color: #e2e8f0;}
    .sp-card {border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px; background: #ffffff; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); margin-bottom: 12px;}
    .sp-soft-card {border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px; background: #f8fafc; margin-bottom: 12px;}
    .sp-kpi {border: 1px solid #e5e7eb; border-radius: 16px; padding: 16px; background: #ffffff;}
    .sp-kpi-label {font-size: 0.82rem; color: #64748b; margin-bottom: 6px;}
    .sp-kpi-value {font-size: 1.75rem; font-weight: 750; color: #0f172a;}
    .sp-kpi-sub {font-size: 0.8rem; color: #64748b;}
    .pill {display:inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.82rem; font-weight: 650; margin-right: 5px;}
    .pill-green {background:#dcfce7; color:#166534;}
    .pill-amber {background:#fef3c7; color:#92400e;}
    .pill-red {background:#fee2e2; color:#991b1b;}
    .pill-blue {background:#dbeafe; color:#1e40af;}
    .pill-grey {background:#f1f5f9; color:#334155;}
    .process-step {display:flex; align-items:center; gap:12px; padding: 10px 0; border-bottom:1px solid #e5e7eb;}
    .step-number {width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; background:#2563eb; color:white; font-weight:700;}
    .step-title {font-weight:700; color:#0f172a;}
    .step-copy {color:#64748b; font-size:0.9rem;}
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f"""
    <div class='sp-hero'>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def kpi(label, value, sub=""):
    st.markdown(f"""
    <div class='sp-kpi'>
      <div class='sp-kpi-label'>{label}</div>
      <div class='sp-kpi-value'>{value}</div>
      <div class='sp-kpi-sub'>{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def status_pill(status):
    cls = "pill-grey"
    if status in ["Green", "Approved", "Sent", "Low"]:
        cls = "pill-green"
    elif status in ["Amber", "Pending", "Awaiting Approval", "Medium", "Normal", "Preview / Failed"]:
        cls = "pill-amber"
    elif status in ["Red", "Blocked", "Rejected", "High", "Critical"]:
        cls = "pill-red"
    elif status in ["Draft", "On Hold", "Dormant"]:
        cls = "pill-blue"
    return f"<span class='pill {cls}'>{status}</span>"


# -----------------------------------------------------------------------------
# Business logic
# -----------------------------------------------------------------------------

def categories():
    df = df_sql("""
        SELECT DISTINCT category FROM approval_stages
        UNION SELECT DISTINCT category FROM document_rules
        UNION SELECT DISTINCT category FROM suppliers
        UNION SELECT DISTINCT category FROM new_supplier_requests
        ORDER BY category
    """)
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def parse_date(v):
    try:
        if v is None or v == "" or pd.isna(v):
            return None
        return pd.to_datetime(v).date()
    except Exception:
        return None


def days_left(v):
    d = parse_date(v)
    return None if d is None else (d - date.today()).days


def doc_status(expiry, warning_days=60, missing=False, critical=True):
    if missing:
        return "Red" if critical else "Amber"
    d = days_left(expiry)
    if d is None:
        return "Amber"
    if d < 0:
        return "Red"
    if d <= int(warning_days or 60):
        return "Amber"
    return "Green"


def stages_for(category):
    return df_sql("SELECT * FROM approval_stages WHERE category=? AND is_required=1 ORDER BY sequence_order", (category or "",))


def decisions_for(request_id):
    return df_sql("""SELECT d.*, s.stage_name, s.sequence_order, s.approver_name, s.approver_email
        FROM approval_decisions d JOIN approval_stages s ON d.stage_id=s.stage_id
        WHERE d.request_id=? ORDER BY s.sequence_order""", (request_id,))


def current_stage(request_id, category):
    stages = stages_for(category)
    decisions = decisions_for(request_id)
    approved = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
    for _, stage in stages.iterrows():
        if int(stage["stage_id"]) not in approved:
            return stage
    return None


def supplier_profile_statuses():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rules = df_sql("SELECT * FROM document_rules")
    docs = df_sql("SELECT * FROM supplier_documents")
    rows = []
    for _, s in suppliers.iterrows():
        supplier_rules = rules[rules["category"] == s["category"]]
        supplier_docs = docs[docs["supplier_id"] == s["supplier_id"]]
        missing = expiring = expired = 0
        status = "Green"
        next_expiry = ""
        expiry_dates = []
        for _, rule in supplier_rules.iterrows():
            matching = supplier_docs[supplier_docs["document_type"] == rule["document_type"]]
            if matching.empty:
                dstatus = doc_status(None, rule["warning_days"], True, bool(rule["is_critical"]))
                missing += 1
            else:
                latest = matching.sort_values("uploaded_at", ascending=False).iloc[0]
                dstatus = doc_status(latest["expiry_date"], rule["warning_days"], False, bool(rule["is_critical"]))
                d = parse_date(latest["expiry_date"])
                if d:
                    expiry_dates.append(d)
            if dstatus == "Red":
                status = "Red"
                if not matching.empty:
                    expired += 1
            elif dstatus == "Amber" and status != "Red":
                status = "Amber"
                if not matching.empty:
                    expiring += 1
        if expiry_dates:
            next_expiry = min(expiry_dates).isoformat()
        score = 100
        score -= missing * 20
        score -= expired * 25
        score -= expiring * 10
        if s["approval_status"] == "Blocked":
            score -= 40
        if s["risk_level"] == "Critical":
            score -= 15
        elif s["risk_level"] == "High":
            score -= 10
        score = max(0, min(100, score))
        rows.append({
            "Supplier ID": s["supplier_id"],
            "Supplier Code": s["supplier_code"],
            "Supplier Name": s["supplier_name"],
            "Email": s["supplier_email"],
            "Category": s["category"],
            "Owner": s["owner"],
            "Approval Status": s["approval_status"],
            "Risk Level": s["risk_level"],
            "Annual Spend": s["annual_spend"] or 0,
            "Criticality": s["criticality"],
            "Preferred": "Yes" if s["preferred_supplier"] else "No",
            "Compliance": status,
            "Health Score": score,
            "Missing Docs": missing,
            "Expiring Soon": expiring,
            "Expired Docs": expired,
            "Next Expiry": next_expiry,
        })
    return pd.DataFrame(rows)


def document_actions():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rules = df_sql("SELECT * FROM document_rules")
    docs = df_sql("SELECT * FROM supplier_documents")
    rows = []
    for _, s in suppliers.iterrows():
        supplier_rules = rules[rules["category"] == s["category"]]
        supplier_docs = docs[docs["supplier_id"] == s["supplier_id"]]
        for _, rule in supplier_rules.iterrows():
            matching = supplier_docs[supplier_docs["document_type"] == rule["document_type"]]
            if matching.empty:
                status = doc_status(None, rule["warning_days"], True, bool(rule["is_critical"]))
                rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Email": s["supplier_email"], "Category": s["category"], "Owner": s["owner"], "Document Type": rule["document_type"], "Status": status, "Issue": "Missing document", "Expiry Date": "", "Days Left": ""})
            else:
                latest = matching.sort_values("uploaded_at", ascending=False).iloc[0]
                status = doc_status(latest["expiry_date"], rule["warning_days"], False, bool(rule["is_critical"]))
                if status in ["Red", "Amber"]:
                    issue = "Expired document" if status == "Red" else "Expiring soon / needs review"
                    rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Email": s["supplier_email"], "Category": s["category"], "Owner": s["owner"], "Document Type": rule["document_type"], "Status": status, "Issue": issue, "Expiry Date": latest["expiry_date"], "Days Left": days_left(latest["expiry_date"])})
    return pd.DataFrame(rows)


def setup_progress():
    suppliers = len(df_sql("SELECT supplier_id FROM suppliers"))
    stages = len(df_sql("SELECT stage_id FROM approval_stages WHERE is_required=1"))
    rules = len(df_sql("SELECT rule_id FROM document_rules"))
    docs = len(df_sql("SELECT document_id FROM supplier_documents"))
    complete = sum([suppliers > 0, stages > 0, rules > 0, docs > 0])
    return int((complete / 4) * 100), suppliers, stages, rules, docs


def save_upload(upload, supplier_id, doc_type):
    folder = UPLOAD_DIR / str(supplier_id)
    folder.mkdir(exist_ok=True)
    safe = upload.name.replace("/", "_").replace("\\", "_")
    path = folder / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{doc_type.replace('/', '-')}_{safe}"
    with open(path, "wb") as f:
        f.write(upload.getbuffer())
    return upload.name, str(path)


# -----------------------------------------------------------------------------
# Email
# -----------------------------------------------------------------------------

def smtp_configured():
    return all(k in st.secrets for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"])


def send_email(to_email, subject, body):
    if not smtp_configured():
        return False, "SMTP not configured. Email preview/log only."
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = st.secrets["FROM_EMAIL"]
        msg["To"] = to_email
        if "REPLY_TO_EMAIL" in st.secrets:
            msg["Reply-To"] = st.secrets["REPLY_TO_EMAIL"]
        msg.set_content(body)
        with smtplib.SMTP(st.secrets["SMTP_HOST"], int(st.secrets["SMTP_PORT"])) as server:
            server.starttls()
            server.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASSWORD"])
            server.send_message(msg)
        return True, "Sent"
    except Exception as e:
        return False, str(e)


def log_email(request_id, supplier_id, email_type, recipient, subject, body, status, error=""):
    exec_sql("""INSERT INTO email_log (request_id, supplier_id, email_type, recipient, subject, body, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (request_id, supplier_id, email_type, recipient, subject, body, status, error))


def approval_email(req, stage):
    subject = f"Supplier approval required - {req['supplier_name']}"
    body = f"""Hi {stage['approver_name']},

A supplier request is awaiting your review in SupplierPass.

Supplier: {req['supplier_name']}
Category: {req['category']}
Requested by: {req['requested_by'] or ''}
Expected annual spend: £{float(req['expected_annual_spend'] or 0):,.2f}
Urgency: {req['urgency'] or 'Normal'}
Stage: {stage['stage_name']}

Reason needed:
{req['reason_needed'] or ''}

Please review this request and record your approval decision.

Thanks,
SupplierPass
"""
    return subject, body


def supplier_doc_email(row):
    subject = f"Supplier document request - {row['Document Type']}"
    body = f"""Hi {row['Supplier Name']},

We are updating our approved supplier records and need the following document from you:

{row['Document Type']}

Reason: {row['Issue']}

Please send the latest version, including the expiry date where applicable.

Many thanks,
[Your Name]
"""
    return subject, body


def notify_current_approver(req):
    stage = current_stage(req["request_id"], req["category"])
    if stage is None:
        return False, "No current approval stage found.", "", ""
    subject, body = approval_email(req, stage)
    ok, msg = send_email(stage["approver_email"], subject, body)
    log_email(req["request_id"], None, "Approval Request", stage["approver_email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
    return ok, msg, subject, body


# -----------------------------------------------------------------------------
# Screens
# -----------------------------------------------------------------------------

def screen_command_centre():
    hero(APP_NAME, "Supplier onboarding, compliance tracking and document chasing for operational SMEs.")
    progress, supplier_count, stage_count, rule_count, doc_count = setup_progress()
    status_table = supplier_profile_statuses()
    requests = df_sql("SELECT * FROM new_supplier_requests")
    actions = document_actions()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Suppliers", supplier_count, "supplier register")
    with c2:
        open_reqs = int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0
        kpi("Open approvals", open_reqs, "supplier requests")
    with c3:
        kpi("Document actions", len(actions), "missing or expiring")
    with c4:
        kpi("Setup", f"{progress}%", "prototype readiness")

    st.markdown("### Guided setup")
    st.progress(progress / 100)
    st.markdown("""
    <div class='sp-card'>
      <div class='process-step'><div class='step-number'>1</div><div><div class='step-title'>Import suppliers</div><div class='step-copy'>Upload your current supplier list from Sage, Excel or your approved supplier list.</div></div></div>
      <div class='process-step'><div class='step-number'>2</div><div><div class='step-title'>Set rules and approvers</div><div class='step-copy'>Define required documents and who approves each supplier category.</div></div></div>
      <div class='process-step'><div class='step-number'>3</div><div><div class='step-title'>Upload evidence</div><div class='step-copy'>Attach certificates, insurance documents and agreements with expiry dates.</div></div></div>
      <div class='process-step'><div class='step-number'>4</div><div><div class='step-title'>Run approvals and chase issues</div><div class='step-copy'>Create supplier requests, route approvals and chase missing documents.</div></div></div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("### Supplier risk overview")
        if status_table.empty:
            st.info("No suppliers yet. Start by importing your supplier list.")
        else:
            display = status_table.sort_values(["Compliance", "Health Score"], ascending=[False, True]).head(20).copy()
            display["Compliance"] = display["Compliance"].apply(lambda x: x)
            st.dataframe(display, use_container_width=True, hide_index=True)
    with right:
        st.markdown("### What needs attention")
        if actions.empty:
            st.success("No missing or expiring document actions found.")
        else:
            for _, r in actions.head(8).iterrows():
                st.markdown(f"""
                <div class='sp-soft-card'>
                  {status_pill(r['Status'])} <b>{r['Supplier Name']}</b><br>
                  <span style='color:#64748b'>{r['Document Type']} — {r['Issue']}</span>
                </div>
                """, unsafe_allow_html=True)


def screen_suppliers():
    hero("Suppliers", "Manage your supplier register and supplier health scores.")
    tab_import, tab_register, tab_profile = st.tabs(["Import", "Register", "Supplier profile"])

    with tab_import:
        st.markdown("### Import supplier file")
        st.caption("Upload your supplier file and map the columns. Only Supplier Name is required.")
        st.code("SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,AnnualSpend,Notes")
        file = st.file_uploader("Choose supplier CSV", type=["csv"], key="supplier_csv_v05")
        if file:
            data = pd.read_csv(file)
            st.success(f"Loaded {len(data)} rows and {len(data.columns)} columns.")
            st.dataframe(data.head(30), use_container_width=True, hide_index=True)
            cols = data.columns.tolist()
            c1, c2, c3 = st.columns(3)
            c_code = c1.selectbox("Supplier Code", [""] + cols)
            c_name = c1.selectbox("Supplier Name *", cols)
            c_email = c1.selectbox("Supplier Email", [""] + cols)
            c_cat = c2.selectbox("Category", [""] + cols)
            c_owner = c2.selectbox("Owner", [""] + cols)
            c_status = c2.selectbox("Approval Status", [""] + cols)
            c_spend = c3.selectbox("Annual Spend", [""] + cols)
            c_notes = c3.selectbox("Notes", [""] + cols)
            default_cat = c3.selectbox("Default category if blank", [""] + categories())
            skip_duplicates = st.checkbox("Skip duplicate supplier codes", value=True)
            if st.button("Import suppliers", type="primary"):
                existing_codes = set(df_sql("SELECT supplier_code FROM suppliers WHERE supplier_code IS NOT NULL AND supplier_code <> ''")["supplier_code"].astype(str).tolist())
                rows = []
                skipped = 0
                for _, r in data.iterrows():
                    name = str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not name:
                        continue
                    code = str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else ""
                    if skip_duplicates and code and code in existing_codes:
                        skipped += 1
                        continue
                    category = str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else default_cat
                    try:
                        annual_spend = float(r[c_spend]) if c_spend and pd.notna(r[c_spend]) else 0
                    except Exception:
                        annual_spend = 0
                    rows.append((code, name,
                        str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "",
                        category,
                        str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "",
                        str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved",
                        "Medium",
                        annual_spend,
                        str(r[c_notes]).strip() if c_notes and pd.notna(r[c_notes]) else ""))
                many_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows)
                st.success(f"Imported {len(rows)} suppliers. Skipped {skipped} duplicates.")
                st.rerun()
        else:
            st.info("No file uploaded yet.")

    with tab_register:
        st.markdown("### Supplier register")
        status_table = supplier_profile_statuses()
        if status_table.empty:
            st.info("No suppliers yet.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            q = col1.text_input("Search")
            cat = col2.multiselect("Category", sorted(status_table["Category"].dropna().unique().tolist()))
            comp = col3.multiselect("Compliance", ["Green", "Amber", "Red"])
            app = col4.multiselect("Approval", SUPPLIER_STATUSES)
            view = status_table.copy()
            if q:
                view = view[view.apply(lambda r: q.lower() in " ".join([str(x).lower() for x in r.values]), axis=1)]
            if cat:
                view = view[view["Category"].isin(cat)]
            if comp:
                view = view[view["Compliance"].isin(comp)]
            if app:
                view = view[view["Approval Status"].isin(app)]
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("Download supplier register", status_table.to_csv(index=False).encode("utf-8"), "supplier_register.csv", "text/csv")

        st.markdown("### Add supplier manually")
        with st.expander("Manual supplier entry"):
            with st.form("manual_supplier_v05"):
                c1, c2, c3 = st.columns(3)
                code = c1.text_input("Supplier Code")
                name = c1.text_input("Supplier Name *")
                email = c1.text_input("Supplier Email")
                cat = c2.selectbox("Category", [""] + categories())
                owner = c2.text_input("Owner")
                status = c2.selectbox("Approval Status", SUPPLIER_STATUSES)
                risk = c3.selectbox("Risk Level", RISK_LEVELS, index=1)
                spend = c3.number_input("Annual Spend", min_value=0.0, step=100.0)
                criticality = c3.selectbox("Criticality", ["Standard", "Important", "Critical"])
                notes = st.text_area("Notes")
                if st.form_submit_button("Add supplier"):
                    if not name.strip():
                        st.error("Supplier name is required.")
                    else:
                        exec_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, criticality, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (code, name, email, cat, owner, status, risk, spend, criticality, notes))
                        st.success("Supplier added.")
                        st.rerun()

    with tab_profile:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers available.")
        else:
            opts = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = opts[st.selectbox("Select supplier", list(opts.keys()))]
            supplier = suppliers[suppliers["supplier_id"] == sid].iloc[0]
            status_table = supplier_profile_statuses()
            row = status_table[status_table["Supplier ID"] == sid].iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi("Health score", row["Health Score"], "out of 100")
            with c2: kpi("Compliance", row["Compliance"], "document status")
            with c3: kpi("Missing docs", row["Missing Docs"], "required evidence")
            with c4: kpi("Spend", f"£{float(row['Annual Spend']):,.0f}", "annual estimate")

            with st.expander("Edit supplier details", expanded=True):
                with st.form(f"edit_supplier_{sid}"):
                    c1, c2, c3 = st.columns(3)
                    code = c1.text_input("Supplier Code", supplier["supplier_code"] or "")
                    name = c1.text_input("Supplier Name", supplier["supplier_name"] or "")
                    email = c1.text_input("Supplier Email", supplier["supplier_email"] or "")
                    cat_list = [""] + categories()
                    cat = c2.selectbox("Category", cat_list, index=cat_list.index(supplier["category"] or "") if (supplier["category"] or "") in cat_list else 0)
                    owner = c2.text_input("Owner", supplier["owner"] or "")
                    approval = c2.selectbox("Approval Status", SUPPLIER_STATUSES, index=SUPPLIER_STATUSES.index(supplier["approval_status"]) if supplier["approval_status"] in SUPPLIER_STATUSES else 0)
                    risk = c3.selectbox("Risk Level", RISK_LEVELS, index=RISK_LEVELS.index(supplier["risk_level"]) if supplier["risk_level"] in RISK_LEVELS else 1)
                    spend = c3.number_input("Annual Spend", min_value=0.0, step=100.0, value=float(supplier["annual_spend"] or 0))
                    criticality = c3.selectbox("Criticality", ["Standard", "Important", "Critical"], index=["Standard", "Important", "Critical"].index(supplier["criticality"]) if supplier["criticality"] in ["Standard", "Important", "Critical"] else 0)
                    notes = st.text_area("Notes", supplier["notes"] or "")
                    if st.form_submit_button("Save supplier"):
                        exec_sql("""UPDATE suppliers SET supplier_code=?, supplier_name=?, supplier_email=?, category=?, owner=?, approval_status=?, risk_level=?, annual_spend=?, criticality=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?""", (code, name, email, cat, owner, approval, risk, spend, criticality, notes, sid))
                        st.success("Supplier updated.")
                        st.rerun()

            st.markdown("### Documents")
            docs = df_sql("SELECT * FROM supplier_documents WHERE supplier_id=? ORDER BY uploaded_at DESC", (sid,))
            if docs.empty:
                st.info("No documents uploaded for this supplier.")
            else:
                docs["days_left"] = docs["expiry_date"].apply(days_left)
                st.dataframe(docs, use_container_width=True, hide_index=True)


def screen_compliance():
    hero("Compliance", "Define document rules and manage supplier evidence.")
    tab_rules, tab_upload, tab_actions = st.tabs(["Document rules", "Upload documents", "Action list"])
    with tab_rules:
        rules = df_sql("SELECT * FROM document_rules ORDER BY category, is_critical DESC, document_type")
        st.dataframe(rules, use_container_width=True, hide_index=True)
        with st.form("add_doc_rule_v05"):
            st.markdown("### Add document rule")
            c1, c2, c3 = st.columns(3)
            mode = c1.radio("Category", ["Use existing", "Create new"], horizontal=True, key="doc_rule_mode_v05")
            cat = c1.selectbox("Existing category", categories(), key="doc_rule_cat_v05") if mode == "Use existing" else c1.text_input("New category", key="doc_rule_new_cat_v05")
            doc_type = c2.text_input("Required document", placeholder="Public Liability Insurance")
            critical = c2.checkbox("Critical document", value=True)
            warning = c3.number_input("Expiry warning days", min_value=0, value=60)
            if st.form_submit_button("Add rule"):
                if not cat or not doc_type:
                    st.error("Category and document type are required.")
                else:
                    try:
                        exec_sql("INSERT INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)", (cat, doc_type, int(critical), int(warning)))
                        st.success("Rule added.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.warning("That rule already exists.")
    with tab_upload:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("Add suppliers first.")
        else:
            opts = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = opts[st.selectbox("Supplier", list(opts.keys()))]
            supplier = suppliers[suppliers["supplier_id"] == sid].iloc[0]
            rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (supplier["category"] or "",))
            if not rules.empty:
                st.markdown("Required for this category")
                st.dataframe(rules[["document_type", "is_critical", "warning_days"]], use_container_width=True, hide_index=True)
            with st.form("upload_doc_v05"):
                doc_options = rules["document_type"].tolist() if not rules.empty else []
                doc_choice = st.selectbox("Document type", doc_options + ["Other"])
                custom = st.text_input("Other document type") if doc_choice == "Other" else ""
                expiry = st.date_input("Expiry date", value=None)
                notes = st.text_area("Notes")
                upload = st.file_uploader("Choose document")
                if st.form_submit_button("Save document"):
                    dtype = custom.strip() if doc_choice == "Other" else doc_choice
                    if not dtype or not upload:
                        st.error("Document type and file are required.")
                    else:
                        fname, fpath = save_upload(upload, sid, dtype)
                        exec_sql("INSERT INTO supplier_documents (supplier_id, document_type, file_name, file_path, expiry_date, notes) VALUES (?, ?, ?, ?, ?, ?)", (sid, dtype, fname, fpath, expiry.isoformat() if expiry else None, notes))
                        st.success("Document saved.")
                        st.rerun()
    with tab_actions:
        actions = document_actions()
        if actions.empty:
            st.success("No missing or expiring document actions.")
        else:
            show = actions.copy()
            st.dataframe(show, use_container_width=True, hide_index=True)
            opts = {f"{r['Supplier Name']} - {r['Document Type']} ({r['Issue']})": i for i, r in actions.iterrows()}
            idx = opts[st.selectbox("Select action", list(opts.keys()))]
            row = actions.loc[idx]
            subject, body = supplier_doc_email(row)
            st.text_input("To", row["Email"] or "")
            st.text_input("Subject", subject)
            st.text_area("Body", body, height=220)
            if st.button("Send / log chase email"):
                ok, msg = send_email(row["Email"], subject, body)
                log_email(None, int(row["Supplier ID"]), "Supplier Document Chase", row["Email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
                st.info(msg)


def screen_onboarding():
    hero("New Supplier Onboarding", "Request, route, approve and convert new suppliers.")
    tab_create, tab_review, tab_routes = st.tabs(["Create request", "Review approvals", "Approval routes"])

    with tab_create:
        st.markdown("### Supplier request wizard")
        with st.form("create_request_v05"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Supplier name *")
            email = c1.text_input("Supplier email")
            requested_by = c1.text_input("Requested by")
            cat = c2.selectbox("Supplier category", [""] + categories())
            spend = c2.number_input("Expected annual spend", min_value=0.0, step=100.0)
            urgency = c2.selectbox("Urgency", URGENCY_LEVELS, index=1)
            reason = st.text_area("Why is this supplier needed?", placeholder="What do they supply, why are they needed, and are alternatives available?")
            submit = st.checkbox("Submit for approval immediately", value=True)
            if st.form_submit_button("Create supplier request", type="primary"):
                if not name.strip():
                    st.error("Supplier name is required.")
                else:
                    status = "Awaiting Approval" if submit else "Draft"
                    rid = exec_sql("""INSERT INTO new_supplier_requests (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (name, email, requested_by, cat, reason, spend, urgency, status))
                    st.success("Request created.")
                    if submit:
                        req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]
                        ok, msg, subject, body = notify_current_approver(req)
                        st.info(msg)
                        with st.expander("Approver email preview", expanded=True):
                            st.text_input("Subject", subject)
                            st.text_area("Body", body, height=240)

    with tab_review:
        requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
        if requests.empty:
            st.info("No supplier requests yet.")
            return
        c1, c2 = st.columns([1, 3])
        with c1:
            open_only = st.checkbox("Open only", value=True)
        view = requests[~requests["status"].isin(["Approved", "Rejected"])] if open_only else requests
        if view.empty:
            st.info("No matching requests.")
            return
        st.dataframe(view, use_container_width=True, hide_index=True)
        opts = {f"{r['supplier_name']} ({r['request_id']})": int(r["request_id"]) for _, r in view.iterrows()}
        rid = opts[st.selectbox("Select request", list(opts.keys()))]
        req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]
        stage = current_stage(rid, req["category"])
        decisions = decisions_for(rid)

        st.markdown(f"### {req['supplier_name']}")
        st.markdown(status_pill(req["status"]), unsafe_allow_html=True)
        st.write(f"**Category:** {req['category']} | **Urgency:** {req['urgency']} | **Spend:** £{float(req['expected_annual_spend'] or 0):,.2f}")
        st.write(req["reason_needed"] or "")

        route = stages_for(req["category"])
        if route.empty:
            st.warning("No approval route configured for this category.")
        else:
            approved = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
            route2 = route.copy()
            route2["stage_status"] = route2["stage_id"].apply(lambda x: "Approved" if x in approved else "Pending")
            st.dataframe(route2[["sequence_order", "stage_name", "approver_name", "approver_email", "stage_status"]], use_container_width=True, hide_index=True)

        if not decisions.empty:
            with st.expander("Approval history"):
                st.dataframe(decisions, use_container_width=True, hide_index=True)

        if req["status"] == "Draft":
            if st.button("Submit for approval", type="primary"):
                exec_sql("UPDATE new_supplier_requests SET status='Awaiting Approval', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0])
                st.rerun()
        elif req["status"] in ["Approved", "Rejected"]:
            st.info(f"This request is already {req['status']}.")
        elif stage is None:
            st.success("All approval stages complete.")
            c1, c2 = st.columns(2)
            if c1.button("Mark request approved"):
                exec_sql("UPDATE new_supplier_requests SET status='Approved', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                st.rerun()
            if c2.button("Convert to supplier"):
                exec_sql("""INSERT INTO suppliers (supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, notes)
                    VALUES (?, ?, ?, ?, 'Approved', 'Medium', ?, ?)""", (req["supplier_name"], req["supplier_email"], req["category"], req["requested_by"], float(req["expected_annual_spend"] or 0), f"Created from request {rid}"))
                st.success("Supplier created.")
        else:
            st.info(f"Current stage: {stage['stage_name']} — {stage['approver_name']} <{stage['approver_email']}>")
            subject, body = approval_email(req, stage)
            with st.expander("Email preview", expanded=True):
                st.text_input("To", stage["approver_email"])
                st.text_input("Subject", subject)
                st.text_area("Body", body, height=220)
            c1, c2, c3 = st.columns(3)
            if c1.button("Send / log email"):
                ok, msg = send_email(stage["approver_email"], subject, body)
                log_email(rid, None, "Approval Request", stage["approver_email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
                st.info(msg)
            notes = st.text_area("Decision notes")
            decided_by = st.text_input("Decided by", value=stage["approver_name"])
            if c2.button("Approve stage", type="primary"):
                exec_sql("""INSERT OR REPLACE INTO approval_decisions (request_id, stage_id, decision, decided_by, notes, decided_at)
                    VALUES (?, ?, 'Approved', ?, ?, CURRENT_TIMESTAMP)""", (rid, int(stage["stage_id"]), decided_by, notes))
                next_stage = current_stage(rid, req["category"])
                if next_stage is None:
                    exec_sql("UPDATE new_supplier_requests SET status='Approved', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                else:
                    exec_sql("UPDATE new_supplier_requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (f"Awaiting {next_stage['stage_name']}", rid))
                    notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0])
                st.rerun()
            if c3.button("Reject request"):
                exec_sql("""INSERT OR REPLACE INTO approval_decisions (request_id, stage_id, decision, decided_by, notes, decided_at)
                    VALUES (?, ?, 'Rejected', ?, ?, CURRENT_TIMESTAMP)""", (rid, int(stage["stage_id"]), decided_by, notes))
                exec_sql("UPDATE new_supplier_requests SET status='Rejected', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                st.rerun()

    with tab_routes:
        stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
        st.dataframe(stages, use_container_width=True, hide_index=True)
        with st.form("add_stage_v05"):
            st.markdown("### Add approval stage")
            c1, c2, c3 = st.columns(3)
            mode = c1.radio("Category", ["Use existing", "Create new"], horizontal=True, key="stage_mode_v05")
            cat = c1.selectbox("Existing category", categories(), key="stage_cat_v05") if mode == "Use existing" else c1.text_input("New category", key="stage_new_cat_v05")
            stage_name = c2.text_input("Stage name", placeholder="Quality Review")
            order = c2.number_input("Order", min_value=1, step=1)
            approver_name = c3.text_input("Approver name")
            approver_email = c3.text_input("Approver email")
            if st.form_submit_button("Add approval stage"):
                try:
                    exec_sql("INSERT INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, 1)", (cat, stage_name, approver_name, approver_email, int(order)))
                    st.success("Approval stage added.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("That stage already exists.")
        st.markdown("### Bulk import approval stages")
        st.code("Category,StageName,ApproverName,ApproverEmail,Order")
        file = st.file_uploader("Upload approval stages CSV", type=["csv"], key="approval_stage_import_v05")
        if file:
            data = pd.read_csv(file)
            st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            if st.button("Import approval stages"):
                rows = [(str(r["Category"]), str(r["StageName"]), str(r["ApproverName"]), str(r["ApproverEmail"]), int(r["Order"]), 1) for _, r in data.iterrows()]
                many_sql("INSERT OR IGNORE INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, ?)", rows)
                st.success(f"Imported {len(rows)} approval stages.")
                st.rerun()


def screen_reports():
    hero("Reports & Audit Pack", "Export supplier compliance, approval and document evidence.")
    status = supplier_profile_statuses()
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
    docs = df_sql("SELECT * FROM supplier_documents ORDER BY uploaded_at DESC")
    emails = df_sql("SELECT * FROM email_log ORDER BY sent_at DESC")
    actions = document_actions()

    if not status.empty:
        st.markdown("### Compliance summary")
        st.dataframe(status, use_container_width=True, hide_index=True)
        st.download_button("Download compliance CSV", status.to_csv(index=False).encode("utf-8"), "supplierpass_compliance.csv", "text/csv")

    xlsx = DATA_DIR / f"supplierpass_audit_export_{date.today().isoformat()}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        suppliers.to_excel(writer, index=False, sheet_name="Suppliers")
        status.to_excel(writer, index=False, sheet_name="Compliance")
        docs.to_excel(writer, index=False, sheet_name="Documents")
        actions.to_excel(writer, index=False, sheet_name="Actions")
        requests.to_excel(writer, index=False, sheet_name="Requests")
        stages.to_excel(writer, index=False, sheet_name="Approval Routes")
        emails.to_excel(writer, index=False, sheet_name="Email Log")
    with open(xlsx, "rb") as f:
        st.download_button("Download full audit export", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def screen_admin():
    hero("Admin", "Email mode, logs and prototype settings.")
    st.markdown("### Email status")
    st.info("SMTP sending is active." if smtp_configured() else "Preview/log mode only. Add SMTP secrets to send real email.")
    with st.expander("SMTP secrets example"):
        st.code('''SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "supplierpass@yourcompany.co.uk"
SMTP_PASSWORD = "your-password-or-app-password"
FROM_EMAIL = "supplierpass@yourcompany.co.uk"
REPLY_TO_EMAIL = "your.name@yourcompany.co.uk"''', language="toml")
    emails = df_sql("SELECT * FROM email_log ORDER BY sent_at DESC")
    st.markdown("### Email log")
    if emails.empty:
        st.info("No emails logged yet.")
    else:
        st.dataframe(emails, use_container_width=True, hide_index=True)

    st.markdown("### Prototype limitations")
    st.warning("This is a commercial prototype, not a production SaaS product. Before selling/hosting it, add authentication, tenant separation, secure file storage, backups, role permissions, licensing, and a proper database server.")


# -----------------------------------------------------------------------------
# Run app
# -----------------------------------------------------------------------------

init_db()
apply_style()

st.sidebar.markdown(f"# {APP_NAME}")
st.sidebar.caption(APP_VERSION)
page = st.sidebar.radio("Navigation", [
    "Command Centre",
    "Suppliers",
    "Compliance",
    "Onboarding",
    "Reports",
    "Admin",
])

if page == "Command Centre":
    screen_command_centre()
elif page == "Suppliers":
    screen_suppliers()
elif page == "Compliance":
    screen_compliance()
elif page == "Onboarding":
    screen_onboarding()
elif page == "Reports":
    screen_reports()
elif page == "Admin":
    screen_admin()
