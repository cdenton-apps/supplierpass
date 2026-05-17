import re
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

APP_NAME = "SupplierPass"
APP_VERSION = "v0.6 commercial plus prototype"

SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
COMPANY_STATUSES = ["Not checked", "Active", "Dormant", "Dissolved", "Unknown / Needs review"]
VAT_STATUSES = ["Not checked", "Valid", "Invalid", "Not VAT registered", "Unknown / Needs review"]
SANCTIONS_STATUSES = ["Not checked", "Clear", "Possible match", "Needs review"]
BANK_STATUSES = ["Not required", "Not started", "Details received", "Verified", "Rejected / Needs review"]

TEMPLATES = {
    "Manufacturing": [("ISO 9001 Certificate", 1, 60), ("Public Liability Insurance", 1, 60), ("Supplier Questionnaire", 1, 365), ("Specification Agreement", 0, 365)],
    "Packaging": [("ISO 9001 Certificate", 1, 60), ("Public Liability Insurance", 1, 60), ("FSC / PEFC Certificate", 0, 60), ("Material Compliance Declaration", 0, 365)],
    "Food / BRC": [("BRC Certificate", 1, 60), ("Food Safety Certificate", 1, 60), ("Public Liability Insurance", 1, 60), ("Allergen Statement", 0, 365)],
    "Transport": [("Public Liability Insurance", 1, 60), ("Goods in Transit Insurance", 1, 60), ("Operator Licence", 1, 60), ("Rate Agreement", 0, 365)],
    "Contractor": [("Public Liability Insurance", 1, 60), ("RAMS", 1, 30), ("Health & Safety Policy", 1, 365), ("Method Statement", 0, 365)],
    "IT / Software": [("Cyber Security Questionnaire", 1, 365), ("Data Processing Agreement", 1, 365), ("Professional Indemnity Insurance", 1, 60)],
    "Agency Labour": [("Public Liability Insurance", 1, 60), ("Modern Slavery Statement", 1, 365), ("Contract", 1, 365)],
}


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
    if not rows:
        return
    c = conn()
    cur = c.cursor()
    cur.executemany(sql, rows)
    c.commit()
    c.close()


def ensure_column(table, column, definition):
    info = df_sql(f"PRAGMA table_info({table})")
    if column not in info["name"].tolist():
        exec_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
        reviewed_by TEXT,
        review_status TEXT DEFAULT 'Uploaded',
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
    cur.execute("""CREATE TABLE IF NOT EXISTS preapproval_profiles (
        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        supplier_email TEXT,
        website TEXT,
        domain TEXT,
        company_number TEXT,
        vat_number TEXT,
        category TEXT,
        company_status TEXT DEFAULT 'Not checked',
        vat_status TEXT DEFAULT 'Not checked',
        sanctions_status TEXT DEFAULT 'Not checked',
        duplicate_warning TEXT,
        supplier_confidence TEXT DEFAULT 'Not checked',
        expected_annual_spend REAL DEFAULT 0,
        owner TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bank_verification (
        bank_check_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        request_id INTEGER,
        status TEXT DEFAULT 'Not started',
        details_received INTEGER DEFAULT 0,
        verified_by_phone INTEGER DEFAULT 0,
        verified_by TEXT,
        verification_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS risk_rules (
        risk_rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_name TEXT NOT NULL,
        condition_text TEXT,
        action_text TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.commit()
    c.close()

    for table, cols in {
        "suppliers": {
            "annual_spend": "REAL DEFAULT 0", "criticality": "TEXT DEFAULT 'Standard'", "preferred_supplier": "INTEGER DEFAULT 0",
            "company_number": "TEXT", "vat_number": "TEXT", "website": "TEXT", "domain": "TEXT", "company_status": "TEXT DEFAULT 'Not checked'",
            "vat_status": "TEXT DEFAULT 'Not checked'", "sanctions_status": "TEXT DEFAULT 'Not checked'", "bank_verification_status": "TEXT DEFAULT 'Not started'", "last_reviewed": "TEXT"
        },
        "new_supplier_requests": {
            "company_number": "TEXT", "vat_number": "TEXT", "website": "TEXT", "domain": "TEXT", "company_status": "TEXT DEFAULT 'Not checked'",
            "vat_status": "TEXT DEFAULT 'Not checked'", "sanctions_status": "TEXT DEFAULT 'Not checked'", "supplier_confidence": "TEXT DEFAULT 'Not checked'", "bank_verification_status": "TEXT DEFAULT 'Not started'"
        },
        "supplier_documents": {"reviewed_by": "TEXT", "review_status": "TEXT DEFAULT 'Uploaded'"}
    }.items():
        for col, definition in cols.items():
            ensure_column(table, col, definition)

    seed_defaults()


def seed_defaults():
    stage_rows = []
    for cat in ["Manufacturing", "Packaging", "Transport", "Raw Material"]:
        stage_rows += [(cat, "Procurement Review", "Procurement", "procurement@example.com", 1, 1), (cat, "Quality Review", "Quality", "quality@example.com", 2, 1), (cat, "Finance Review", "Finance", "finance@example.com", 3, 1)]
    stage_rows += [("Contractor", "H&S Review", "Health and Safety", "hs@example.com", 1, 1), ("Contractor", "Finance Review", "Finance", "finance@example.com", 2, 1), ("IT / Software", "IT / Cyber Review", "IT", "it@example.com", 1, 1), ("IT / Software", "Finance Review", "Finance", "finance@example.com", 2, 1)]
    many_sql("""INSERT OR IGNORE INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, ?)""", stage_rows)
    doc_rows = []
    for cat, docs in TEMPLATES.items():
        doc_rows += [(cat, doc, critical, warning) for doc, critical, warning in docs]
    doc_rows += [("Raw Material", "ISO 9001 Certificate", 1, 60), ("Raw Material", "Public Liability Insurance", 1, 60), ("Raw Material", "Supplier Questionnaire", 1, 365)]
    many_sql("""INSERT OR IGNORE INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)""", doc_rows)
    risk_rows = [("High spend supplier", "Annual spend is over £50,000", "Require finance or senior approval", 1), ("Critical supplier", "Criticality is Critical", "Require senior review and owner assignment", 1), ("Expired critical evidence", "Critical document is expired or missing", "Mark Do Not Use", 1), ("IT supplier", "Category is IT / Software", "Require IT / Cyber review", 1), ("Bank details changed", "Bank verification is not complete", "Require finance verification", 1)]
    many_sql("INSERT OR IGNORE INTO risk_rules (rule_name, condition_text, action_text, is_active) VALUES (?, ?, ?, ?)", risk_rows)


def apply_style():
    st.markdown("""
    <style>
    .block-container {padding-top: 1.1rem; padding-bottom: 2rem;}
    [data-testid="stSidebar"] {background: #0f172a;} [data-testid="stSidebar"] * {color: #f8fafc !important;}
    .hero {border-radius: 22px; padding: 24px 28px; background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #0f766e 100%); color: white; margin-bottom: 18px;}
    .hero h1 {margin:0; color:white; font-size:2.1rem;} .hero p {margin:8px 0 0 0; color:#dbeafe;}
    .card {border:1px solid #e5e7eb; border-radius:16px; padding:18px; background:#fff; box-shadow:0 1px 2px rgba(15,23,42,.06); margin-bottom:12px;}
    .soft {border:1px solid #e5e7eb; border-radius:16px; padding:16px; background:#f8fafc; margin-bottom:12px;}
    .kpi {border:1px solid #e5e7eb; border-radius:16px; padding:16px; background:#fff;} .kpi-label{font-size:.82rem;color:#64748b}.kpi-value{font-size:1.6rem;font-weight:750;color:#0f172a}.kpi-sub{font-size:.8rem;color:#64748b}
    .pill{display:inline-block;padding:4px 10px;border-radius:999px;font-size:.82rem;font-weight:650;margin-right:5px}.green{background:#dcfce7;color:#166534}.amber{background:#fef3c7;color:#92400e}.red{background:#fee2e2;color:#991b1b}.blue{background:#dbeafe;color:#1e40af}.grey{background:#f1f5f9;color:#334155}
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def kpi(label, value, sub=""):
    st.markdown(f"<div class='kpi'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div><div class='kpi-sub'>{sub}</div></div>", unsafe_allow_html=True)


def pill(status):
    cls = "grey"
    if status in ["Green", "Approved", "Sent", "Low", "Can Buy", "Valid", "Active", "Clear", "High", "Verified"]: cls = "green"
    elif status in ["Amber", "Pending", "Awaiting Approval", "Medium", "Normal", "Preview / Failed", "Can Buy with Warning", "Not checked", "Details received"]: cls = "amber"
    elif status in ["Red", "Blocked", "Rejected", "Critical", "Do Not Use", "Invalid", "Dissolved", "Possible match", "Rejected / Needs review"]: cls = "red"
    elif status in ["Draft", "On Hold", "Dormant", "Approval Pending", "Not started"]: cls = "blue"
    return f"<span class='pill {cls}'>{status}</span>"


def categories():
    df = df_sql("""SELECT DISTINCT category FROM approval_stages UNION SELECT DISTINCT category FROM document_rules UNION SELECT DISTINCT category FROM suppliers UNION SELECT DISTINCT category FROM new_supplier_requests UNION SELECT DISTINCT category FROM preapproval_profiles ORDER BY category""")
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def clean_domain(value):
    if not value: return ""
    v = str(value).strip().lower().replace("https://", "").replace("http://", "").replace("www.", "")
    if "@" in v: v = v.split("@")[-1]
    return v.split("/")[0]


def free_email(domain):
    return domain in {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "aol.com", "live.com"}


def parse_date(v):
    try:
        if v is None or v == "" or pd.isna(v): return None
        return pd.to_datetime(v).date()
    except Exception:
        return None


def days_left(v):
    d = parse_date(v); return None if d is None else (d - date.today()).days


def doc_status(expiry, warning_days=60, missing=False, critical=True):
    if missing: return "Red" if critical else "Amber"
    d = days_left(expiry)
    if d is None: return "Amber"
    if d < 0: return "Red"
    if d <= int(warning_days or 60): return "Amber"
    return "Green"


def stages_for(category):
    return df_sql("SELECT * FROM approval_stages WHERE category=? AND is_required=1 ORDER BY sequence_order", (category or "",))


def decisions_for(request_id):
    return df_sql("""SELECT d.*, s.stage_name, s.sequence_order, s.approver_name, s.approver_email FROM approval_decisions d JOIN approval_stages s ON d.stage_id=s.stage_id WHERE d.request_id=? ORDER BY s.sequence_order""", (request_id,))


def current_stage(request_id, category):
    stages = stages_for(category); decisions = decisions_for(request_id)
    approved = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
    for _, stage in stages.iterrows():
        if int(stage["stage_id"]) not in approved: return stage
    return None


def supplier_checklist(s):
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (s["category"] or "",))
    docs = df_sql("SELECT * FROM supplier_documents WHERE supplier_id=?", (s["supplier_id"],))
    rows = []
    for _, r in rules.iterrows():
        matching = docs[docs["document_type"] == r["document_type"]]
        if matching.empty:
            rows.append({"Document Type": r["document_type"], "Required": "Yes" if r["is_critical"] else "Optional", "Status": doc_status(None, r["warning_days"], True, bool(r["is_critical"])), "Issue": "Missing document", "Expiry Date": "", "Days Left": ""})
        else:
            latest = matching.sort_values("uploaded_at", ascending=False).iloc[0]
            stt = doc_status(latest["expiry_date"], r["warning_days"], False, bool(r["is_critical"]))
            issue = "Expired document" if stt == "Red" else "Expiring soon / needs review" if stt == "Amber" else ""
            rows.append({"Document Type": r["document_type"], "Required": "Yes" if r["is_critical"] else "Optional", "Status": stt, "Issue": issue, "Expiry Date": latest["expiry_date"] or "", "Days Left": days_left(latest["expiry_date"]) if days_left(latest["expiry_date"]) is not None else ""})
    return pd.DataFrame(rows)


def supplier_readiness(s):
    checklist = supplier_checklist(s)
    missing = int((checklist["Issue"] == "Missing document").sum()) if not checklist.empty else 0
    expiring = int((checklist["Issue"] == "Expiring soon / needs review").sum()) if not checklist.empty else 0
    expired = int((checklist["Issue"] == "Expired document").sum()) if not checklist.empty else 0
    score = 100 - missing * 18 - expired * 25 - expiring * 8
    if s["approval_status"] == "Blocked": score -= 45
    if s["approval_status"] in ["Pending", "On Hold"]: score -= 15
    if s["risk_level"] == "Critical": score -= 15
    if s["risk_level"] == "High": score -= 10
    if s["company_status"] not in ["Active", "Not checked", None, ""]: score -= 20
    if s["vat_status"] == "Invalid": score -= 15
    if s["sanctions_status"] in ["Possible match", "Needs review"]: score -= 40
    if s["bank_verification_status"] == "Rejected / Needs review": score -= 25
    score = max(0, min(100, score))
    if s["approval_status"] == "Blocked" or expired > 0 or s["sanctions_status"] == "Possible match": can_buy = "Do Not Use"
    elif s["approval_status"] in ["Pending", "On Hold"]: can_buy = "Approval Pending"
    elif s["approval_status"] == "Dormant": can_buy = "Dormant"
    elif missing > 0 or expiring > 0 or s["company_status"] == "Unknown / Needs review" or s["vat_status"] == "Unknown / Needs review": can_buy = "Can Buy with Warning"
    else: can_buy = "Can Buy"
    return score, can_buy, missing, expiring, expired


def supplier_table():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    for _, s in suppliers.iterrows():
        score, can_buy, missing, expiring, expired = supplier_readiness(s)
        rows.append({"Supplier ID": s["supplier_id"], "Supplier Code": s["supplier_code"], "Supplier Name": s["supplier_name"], "Can I Buy?": can_buy, "Readiness": score, "Email": s["supplier_email"], "Category": s["category"], "Owner": s["owner"], "Approval Status": s["approval_status"], "Risk Level": s["risk_level"], "Annual Spend": s["annual_spend"] or 0, "Criticality": s["criticality"], "Missing Docs": missing, "Expiring Soon": expiring, "Expired Docs": expired, "Company Status": s["company_status"], "VAT Status": s["vat_status"], "Sanctions": s["sanctions_status"], "Bank Check": s["bank_verification_status"]})
    return pd.DataFrame(rows)


def document_actions():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    for _, s in suppliers.iterrows():
        checklist = supplier_checklist(s)
        if checklist.empty: continue
        for _, item in checklist[checklist["Status"].isin(["Red", "Amber"])].iterrows():
            rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Email": s["supplier_email"], "Category": s["category"], "Owner": s["owner"], "Document Type": item["Document Type"], "Status": item["Status"], "Issue": item["Issue"] or "Needs review", "Expiry Date": item["Expiry Date"], "Days Left": item["Days Left"]})
    return pd.DataFrame(rows)


def evidence_gaps():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    actions = document_actions()
    for _, a in actions.iterrows():
        rows.append({"Supplier ID": a["Supplier ID"], "Supplier Name": a["Supplier Name"], "Gap Type": a["Issue"], "Severity": a["Status"], "Owner": a["Owner"], "Detail": a["Document Type"], "Recommended Action": "Request document from supplier"})
    for _, s in suppliers.iterrows():
        if not s["category"]: rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap Type": "Missing category", "Severity": "Amber", "Owner": s["owner"], "Detail": "Supplier category is blank", "Recommended Action": "Assign category"})
        if not s["owner"]: rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap Type": "Missing owner", "Severity": "Amber", "Owner": "", "Detail": "No internal owner", "Recommended Action": "Assign owner"})
        if not s["supplier_email"]: rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap Type": "Missing email", "Severity": "Amber", "Owner": s["owner"], "Detail": "No supplier email", "Recommended Action": "Add contact email"})
        if float(s["annual_spend"] or 0) > 50000 and s["bank_verification_status"] not in ["Verified", "Not required"]: rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap Type": "Finance verification", "Severity": "Red", "Owner": s["owner"], "Detail": "High-spend supplier without verified bank check", "Recommended Action": "Complete bank verification"})
        if s["sanctions_status"] in ["Possible match", "Needs review"]: rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Gap Type": "Sanctions screening", "Severity": "Red", "Owner": s["owner"], "Detail": s["sanctions_status"], "Recommended Action": "Escalate for review"})
    return pd.DataFrame(rows)


def data_quality_checks():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    if suppliers.empty: return pd.DataFrame()
    for _, s in suppliers[suppliers.duplicated(subset=["supplier_name"], keep=False)].iterrows(): rows.append({"Check": "Possible duplicate name", "Supplier": s["supplier_name"], "Severity": "Amber", "Detail": "Another supplier has the same name"})
    for _, s in suppliers.iterrows():
        d = clean_domain(s["supplier_email"])
        if d and free_email(d): rows.append({"Check": "Free email domain", "Supplier": s["supplier_name"], "Severity": "Amber", "Detail": d})
        if s["approval_status"] == "Approved" and not s["category"]: rows.append({"Check": "Approved without category", "Supplier": s["supplier_name"], "Severity": "Amber", "Detail": "No category"})
    return pd.DataFrame(rows)


def confidence(company_status, vat_status, sanctions_status, domain, name, duplicate):
    score = 0; warnings = []
    if company_status == "Active": score += 30
    elif company_status in ["Dissolved", "Unknown / Needs review"]: warnings.append("Company status needs review")
    if vat_status == "Valid": score += 20
    elif vat_status == "Invalid": warnings.append("VAT invalid")
    if sanctions_status == "Clear": score += 25
    elif sanctions_status in ["Possible match", "Needs review"]: warnings.append("Sanctions needs review")
    if domain:
        if free_email(domain): warnings.append("Free email domain")
        else: score += 15
    if duplicate: warnings.append("Possible duplicate")
    return ("High" if score >= 75 and not warnings else "Medium" if score >= 45 else "Low"), "; ".join(warnings)


def management_summary():
    status = supplier_table(); gaps = evidence_gaps(); requests = df_sql("SELECT * FROM new_supplier_requests")
    if status.empty: return "No suppliers have been loaded yet."
    red = len(status[status["Can I Buy?"] == "Do Not Use"]); amber = len(status[status["Can I Buy?"] == "Can Buy with Warning"])
    open_req = int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0
    high_spend = len(status[(status["Annual Spend"] > 50000) & (status["Can I Buy?"] != "Can Buy")])
    return "\n".join([f"- {red} suppliers are marked Do Not Use.", f"- {amber} suppliers can be used with warning.", f"- {len(gaps)} evidence gaps are open.", f"- {open_req} new supplier requests need action.", f"- {high_spend} high-spend suppliers have unresolved risk."])


def save_upload(upload, supplier_id, doc_type):
    folder = UPLOAD_DIR / str(supplier_id); folder.mkdir(exist_ok=True)
    safe = upload.name.replace("/", "_").replace("\\", "_")
    path = folder / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{doc_type.replace('/', '-')}_{safe}"
    with open(path, "wb") as f: f.write(upload.getbuffer())
    return upload.name, str(path)


def smtp_configured():
    return all(k in st.secrets for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"])


def send_email(to_email, subject, body):
    if not smtp_configured(): return False, "SMTP not configured. Email preview/log only."
    try:
        msg = EmailMessage(); msg["Subject"] = subject; msg["From"] = st.secrets["FROM_EMAIL"]; msg["To"] = to_email
        if "REPLY_TO_EMAIL" in st.secrets: msg["Reply-To"] = st.secrets["REPLY_TO_EMAIL"]
        msg.set_content(body)
        with smtplib.SMTP(st.secrets["SMTP_HOST"], int(st.secrets["SMTP_PORT"])) as server:
            server.starttls(); server.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASSWORD"]); server.send_message(msg)
        return True, "Sent"
    except Exception as e:
        return False, str(e)


def log_email(request_id, supplier_id, email_type, recipient, subject, body, status, error=""):
    exec_sql("""INSERT INTO email_log (request_id, supplier_id, email_type, recipient, subject, body, status, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (request_id, supplier_id, email_type, recipient, subject, body, status, error))


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


def notify_current_approver(req):
    stage = current_stage(req["request_id"], req["category"])
    if stage is None: return False, "No current approval stage found.", "", ""
    subject, body = approval_email(req, stage); ok, msg = send_email(stage["approver_email"], subject, body)
    log_email(req["request_id"], None, "Approval Request", stage["approver_email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
    return ok, msg, subject, body


def supplier_doc_email(row):
    return f"Supplier document request - {row['Document Type']}", f"""Hi {row['Supplier Name']},

We are updating our approved supplier records and need the following document from you:

{row['Document Type']}

Reason: {row['Issue']}

Please send the latest version, including the expiry date where applicable.

Many thanks,
[Your Name]
"""


def supplier_pack_email(profile):
    rules = df_sql("SELECT document_type FROM document_rules WHERE category=? ORDER BY document_type", (profile["category"] or "",))
    docs = "\n".join([f"- {x}" for x in rules["document_type"].tolist()]) if not rules.empty else "- Supplier onboarding documents"
    return "Supplier onboarding information request", f"""Hi {profile['supplier_name']},

We are reviewing your setup as a supplier.

Please could you provide the following information and documents:

{docs}

Please also confirm:
- Company registration number
- VAT number
- Main contact details
- Remittance email address
- Bank details on official letterhead, where applicable

Many thanks,
[Your Name]
"""


# Screens

def command_centre():
    hero(APP_NAME, "Know who you can safely buy from, what needs chasing, and what would fail an audit.")
    status = supplier_table(); gaps = evidence_gaps(); requests = df_sql("SELECT * FROM new_supplier_requests")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Suppliers", len(status), "total records")
    with c2: kpi("Do Not Use", len(status[status["Can I Buy?"] == "Do Not Use"]) if not status.empty else 0, "blocked by risk")
    with c3: kpi("Open approvals", int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0, "supplier requests")
    with c4: kpi("Evidence gaps", len(gaps), "audit issues")
    st.markdown("### Management summary")
    st.markdown(f"<div class='card'>{management_summary().replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("### Supplier readiness")
        if status.empty: st.info("No suppliers loaded yet. Start in Suppliers > Import.")
        else: st.dataframe(status.sort_values(["Can I Buy?", "Readiness"]).head(30), use_container_width=True, hide_index=True)
    with right:
        st.markdown("### Priority actions")
        if gaps.empty: st.success("No evidence gaps found.")
        else:
            for _, r in gaps.head(8).iterrows(): st.markdown(f"<div class='soft'>{pill(r['Severity'])} <b>{r['Supplier Name']}</b><br><span style='color:#64748b'>{r['Gap Type']}: {r['Detail']}</span><br><span style='color:#64748b'>Action: {r['Recommended Action']}</span></div>", unsafe_allow_html=True)


def preapproval():
    hero("Pre-Approval Builder", "Do the checks before supplier approval and create a ready-to-route onboarding request.")
    tab1, tab2 = st.tabs(["Build profile", "Saved profiles"])
    with tab1:
        with st.form("preapproval"):
            a, b, c = st.columns(3)
            name = a.text_input("Supplier name *"); email = a.text_input("Supplier email"); website = a.text_input("Website")
            company_no = b.text_input("Company number"); vat_no = b.text_input("VAT number"); category = b.selectbox("Suggested category", [""] + categories())
            owner = c.text_input("Internal owner"); spend = c.number_input("Expected annual spend", min_value=0.0, step=100.0); company_status = c.selectbox("Company status", COMPANY_STATUSES)
            vat_status = st.selectbox("VAT status", VAT_STATUSES); sanctions = st.selectbox("Sanctions screening", SANCTIONS_STATUSES); notes = st.text_area("Pre-approval notes")
            if st.form_submit_button("Build pre-approval profile", type="primary"):
                if not name.strip(): st.error("Supplier name is required.")
                else:
                    domain = clean_domain(email) or clean_domain(website); suppliers = df_sql("SELECT supplier_name FROM suppliers")
                    dup = "Possible duplicate in supplier register" if not suppliers.empty and not suppliers[suppliers["supplier_name"].str.lower().str.contains(re.escape(name.lower()), na=False)].empty else ""
                    conf, warnings = confidence(company_status, vat_status, sanctions, domain, name, dup)
                    pid = exec_sql("""INSERT INTO preapproval_profiles (supplier_name, supplier_email, website, domain, company_number, vat_number, category, company_status, vat_status, sanctions_status, duplicate_warning, supplier_confidence, expected_annual_spend, owner, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (name, email, website, domain, company_no, vat_no, category, company_status, vat_status, sanctions, dup, conf, spend, owner, notes + ("\nWarnings: " + warnings if warnings else "")))
                    st.session_state["profile_id"] = pid; st.success("Profile built.")
    with tab2:
        profiles = df_sql("SELECT * FROM preapproval_profiles ORDER BY created_at DESC")
        if profiles.empty: st.info("No profiles yet."); return
        st.dataframe(profiles, use_container_width=True, hide_index=True)
        opts = {f"{r['supplier_name']} ({r['profile_id']})": int(r["profile_id"]) for _, r in profiles.iterrows()}
        pid = st.session_state.get("profile_id") or opts[st.selectbox("Select profile", list(opts.keys()))]
        p = df_sql("SELECT * FROM preapproval_profiles WHERE profile_id=?", (pid,)).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi("Confidence", p["supplier_confidence"], "pre-approval")
        with c2: kpi("Company", p["company_status"], "identity")
        with c3: kpi("VAT", p["vat_status"], "tax")
        with c4: kpi("Sanctions", p["sanctions_status"], "screening")
        if p["duplicate_warning"]: st.warning(p["duplicate_warning"])
        subject, body = supplier_pack_email(p)
        with st.expander("Supplier information request email"):
            st.text_input("Subject", subject); st.text_area("Body", body, height=220)
        c1, c2 = st.columns(2)
        if c1.button("Create supplier request from profile"):
            exec_sql("""INSERT INTO new_supplier_requests (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status, company_number, vat_number, website, domain, company_status, vat_status, sanctions_status, supplier_confidence) VALUES (?, ?, ?, ?, ?, ?, 'Normal', 'Draft', ?, ?, ?, ?, ?, ?, ?, ?)""", (p["supplier_name"], p["supplier_email"], p["owner"], p["category"], p["notes"], p["expected_annual_spend"], p["company_number"], p["vat_number"], p["website"], p["domain"], p["company_status"], p["vat_status"], p["sanctions_status"], p["supplier_confidence"])); st.success("Request created.")
        if c2.button("Create pending supplier from profile"):
            exec_sql("""INSERT INTO suppliers (supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, notes, company_number, vat_number, website, domain, company_status, vat_status, sanctions_status) VALUES (?, ?, ?, ?, 'Pending', 'Medium', ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (p["supplier_name"], p["supplier_email"], p["category"], p["owner"], p["expected_annual_spend"], p["notes"], p["company_number"], p["vat_number"], p["website"], p["domain"], p["company_status"], p["vat_status"], p["sanctions_status"])); st.success("Supplier created as pending.")


def suppliers_screen():
    hero("Supplier Register", "Import, edit, classify and monitor supplier readiness.")
    tab1, tab2, tab3, tab4 = st.tabs(["Import", "Register", "Profile", "Finance checks"])
    with tab1:
        st.code("SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,AnnualSpend,CompanyNumber,VATNumber,Website,Notes")
        file = st.file_uploader("Choose supplier CSV", type=["csv"])
        if file:
            data = pd.read_csv(file); st.dataframe(data.head(30), use_container_width=True, hide_index=True); cols = data.columns.tolist()
            a,b,c = st.columns(3)
            c_code=a.selectbox("Supplier Code", [""]+cols); c_name=a.selectbox("Supplier Name *", cols); c_email=a.selectbox("Supplier Email", [""]+cols)
            c_cat=b.selectbox("Category", [""]+cols); c_owner=b.selectbox("Owner", [""]+cols); c_status=b.selectbox("Approval Status", [""]+cols)
            c_spend=c.selectbox("Annual Spend", [""]+cols); c_company=c.selectbox("Company Number", [""]+cols); c_vat=c.selectbox("VAT Number", [""]+cols); c_web=st.selectbox("Website", [""]+cols); c_notes=st.selectbox("Notes", [""]+cols); default_cat=st.selectbox("Default category if blank", [""]+categories())
            if st.button("Import suppliers", type="primary"):
                rows=[]
                for _, r in data.iterrows():
                    name=str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not name: continue
                    email=str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else ""; website=str(r[c_web]).strip() if c_web and pd.notna(r[c_web]) else ""; domain=clean_domain(email) or clean_domain(website)
                    try: spend=float(r[c_spend]) if c_spend and pd.notna(r[c_spend]) else 0
                    except Exception: spend=0
                    rows.append((str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else "", name, email, str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else default_cat, str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "", str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved", "Medium", spend, str(r[c_notes]).strip() if c_notes and pd.notna(r[c_notes]) else "", str(r[c_company]).strip() if c_company and pd.notna(r[c_company]) else "", str(r[c_vat]).strip() if c_vat and pd.notna(r[c_vat]) else "", website, domain))
                many_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, notes, company_number, vat_number, website, domain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows); st.success(f"Imported {len(rows)} suppliers."); st.rerun()
    with tab2:
        status=supplier_table()
        if status.empty: st.info("No suppliers yet.")
        else:
            q=st.text_input("Search"); view=status.copy()
            if q: view=view[view.apply(lambda r: q.lower() in " ".join([str(x).lower() for x in r.values]), axis=1)]
            st.dataframe(view, use_container_width=True, hide_index=True); st.download_button("Download supplier register", status.to_csv(index=False).encode("utf-8"), "supplier_register.csv", "text/csv")
    with tab3:
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers available.")
        else:
            opts={f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _,r in suppliers.iterrows()}; sid=opts[st.selectbox("Select supplier", list(opts.keys()))]; s=df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)).iloc[0]
            score, can_buy, missing, expiring, expired=supplier_readiness(s); c1,c2,c3,c4=st.columns(4)
            with c1: kpi("Can I Buy?", can_buy, "buying decision")
            with c2: kpi("Readiness", f"{score}%", "supplier score")
            with c3: kpi("Missing docs", missing, "evidence gaps")
            with c4: kpi("Spend", f"£{float(s['annual_spend'] or 0):,.0f}", "annual estimate")
            with st.form("edit_supplier"):
                a,b,c=st.columns(3); code=a.text_input("Supplier Code", s["supplier_code"] or ""); name=a.text_input("Supplier Name", s["supplier_name"] or ""); email=a.text_input("Supplier Email", s["supplier_email"] or ""); cat_list=[""]+categories(); cat=b.selectbox("Category", cat_list, index=cat_list.index(s["category"] or "") if (s["category"] or "") in cat_list else 0); owner=b.text_input("Owner", s["owner"] or ""); approval=b.selectbox("Approval Status", SUPPLIER_STATUSES, index=SUPPLIER_STATUSES.index(s["approval_status"]) if s["approval_status"] in SUPPLIER_STATUSES else 0); risk=c.selectbox("Risk Level", RISK_LEVELS, index=RISK_LEVELS.index(s["risk_level"]) if s["risk_level"] in RISK_LEVELS else 1); spend=c.number_input("Annual Spend", min_value=0.0, step=100.0, value=float(s["annual_spend"] or 0)); criticality=c.selectbox("Criticality", ["Standard", "Important", "Critical"], index=["Standard", "Important", "Critical"].index(s["criticality"]) if s["criticality"] in ["Standard", "Important", "Critical"] else 0)
                company_number=a.text_input("Company Number", s["company_number"] or ""); vat_number=a.text_input("VAT Number", s["vat_number"] or ""); website=a.text_input("Website", s["website"] or ""); company_status=b.selectbox("Company Status", COMPANY_STATUSES, index=COMPANY_STATUSES.index(s["company_status"]) if s["company_status"] in COMPANY_STATUSES else 0); vat_status=b.selectbox("VAT Status", VAT_STATUSES, index=VAT_STATUSES.index(s["vat_status"]) if s["vat_status"] in VAT_STATUSES else 0); sanctions=c.selectbox("Sanctions", SANCTIONS_STATUSES, index=SANCTIONS_STATUSES.index(s["sanctions_status"]) if s["sanctions_status"] in SANCTIONS_STATUSES else 0); bank=c.selectbox("Bank Verification", BANK_STATUSES, index=BANK_STATUSES.index(s["bank_verification_status"]) if s["bank_verification_status"] in BANK_STATUSES else 1); notes=st.text_area("Notes", s["notes"] or "")
                if st.form_submit_button("Save supplier"):
                    domain=clean_domain(email) or clean_domain(website); exec_sql("""UPDATE suppliers SET supplier_code=?, supplier_name=?, supplier_email=?, category=?, owner=?, approval_status=?, risk_level=?, annual_spend=?, criticality=?, notes=?, company_number=?, vat_number=?, website=?, domain=?, company_status=?, vat_status=?, sanctions_status=?, bank_verification_status=?, updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?""", (code,name,email,cat,owner,approval,risk,spend,criticality,notes,company_number,vat_number,website,domain,company_status,vat_status,sanctions,bank,sid)); st.success("Supplier saved."); st.rerun()
            st.markdown("### Required evidence"); checklist=supplier_checklist(s); st.dataframe(checklist, use_container_width=True, hide_index=True) if not checklist.empty else st.info("No document rules configured for this category.")
    with tab4:
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers available.")
        else:
            opts={f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _,r in suppliers.iterrows()}; sid=opts[st.selectbox("Supplier to verify", list(opts.keys()), key="bank_supplier")]; s=df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)).iloc[0]
            with st.form("bank_form"):
                status=st.selectbox("Verification status", BANK_STATUSES, index=BANK_STATUSES.index(s["bank_verification_status"]) if s["bank_verification_status"] in BANK_STATUSES else 1); received=st.checkbox("Bank details received on official document"); phone=st.checkbox("Verified by phone / trusted route"); verified_by=st.text_input("Verified by"); notes=st.text_area("Notes")
                if st.form_submit_button("Save finance verification"):
                    exec_sql("UPDATE suppliers SET bank_verification_status=?, updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?", (status,sid)); exec_sql("INSERT INTO bank_verification (supplier_id,status,details_received,verified_by_phone,verified_by,verification_date,notes) VALUES (?,?,?,?,?,?,?)", (sid,status,int(received),int(phone),verified_by,date.today().isoformat(),notes)); st.success("Bank verification saved."); st.rerun()
            hist=df_sql("SELECT * FROM bank_verification WHERE supplier_id=? ORDER BY created_at DESC", (sid,)); st.dataframe(hist, use_container_width=True, hide_index=True) if not hist.empty else None


def compliance():
    hero("Risk & Compliance", "Rules, templates, evidence gaps, data quality and owner accountability.")
    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["Document rules", "Industry templates", "Upload evidence", "Evidence gaps", "Data quality", "Owner accountability"])
    with tab1:
        st.dataframe(df_sql("SELECT * FROM document_rules ORDER BY category, is_critical DESC, document_type"), use_container_width=True, hide_index=True)
        with st.form("add_doc_rule"):
            a,b,c=st.columns(3); mode=a.radio("Category", ["Use existing", "Create new"], horizontal=True); cat=a.selectbox("Existing category", categories()) if mode=="Use existing" else a.text_input("New category"); doc=b.text_input("Required document"); critical=b.checkbox("Critical", value=True); warning=c.number_input("Warning days", min_value=0, value=60)
            if st.form_submit_button("Add rule"):
                try: exec_sql("INSERT INTO document_rules (category,document_type,is_critical,warning_days) VALUES (?,?,?,?)", (cat,doc,int(critical),int(warning))); st.success("Rule added."); st.rerun()
                except sqlite3.IntegrityError: st.warning("That rule already exists.")
    with tab2:
        template=st.selectbox("Template", list(TEMPLATES.keys())); target=st.text_input("Apply to category", value=template); st.dataframe(pd.DataFrame(TEMPLATES[template], columns=["Document Type","Critical","Warning Days"]), use_container_width=True, hide_index=True)
        if st.button("Apply template", type="primary"):
            many_sql("INSERT OR IGNORE INTO document_rules (category,document_type,is_critical,warning_days) VALUES (?,?,?,?)", [(target,d,c,w) for d,c,w in TEMPLATES[template]]); st.success("Template applied."); st.rerun()
    with tab3:
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("Add suppliers first.")
        else:
            opts={f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _,r in suppliers.iterrows()}; sid=opts[st.selectbox("Supplier", list(opts.keys()))]; s=df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)).iloc[0]; rules=df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (s["category"] or "",)); st.dataframe(rules, use_container_width=True, hide_index=True) if not rules.empty else None
            with st.form("upload_doc"):
                opts_doc=rules["document_type"].tolist() if not rules.empty else []; choice=st.selectbox("Document type", opts_doc+["Other"]); custom=st.text_input("Other document type") if choice=="Other" else ""; expiry=st.date_input("Expiry date", value=None); reviewed=st.text_input("Reviewed by"); review_status=st.selectbox("Review status", ["Uploaded", "Reviewed", "Rejected / Needs review"]); notes=st.text_area("Notes"); upload=st.file_uploader("Choose document")
                if st.form_submit_button("Save document"):
                    dtype=custom.strip() if choice=="Other" else choice
                    if not dtype or not upload: st.error("Document type and file are required.")
                    else:
                        fname,path=save_upload(upload,sid,dtype); exec_sql("INSERT INTO supplier_documents (supplier_id,document_type,file_name,file_path,expiry_date,notes,reviewed_by,review_status) VALUES (?,?,?,?,?,?,?,?)", (sid,dtype,fname,path,expiry.isoformat() if expiry else None,notes,reviewed,review_status)); st.success("Document saved."); st.rerun()
    with tab4:
        gaps=evidence_gaps(); st.dataframe(gaps, use_container_width=True, hide_index=True) if not gaps.empty else st.success("No evidence gaps found.")
        actions=document_actions()
        if not actions.empty:
            opts={f"{r['Supplier Name']} - {r['Document Type']} ({r['Issue']})": i for i,r in actions.iterrows()}; idx=opts[st.selectbox("Select chase action", list(opts.keys()))]; row=actions.loc[idx]; subject,body=supplier_doc_email(row); st.text_input("To", row["Email"] or ""); st.text_input("Subject", subject); st.text_area("Body", body, height=220)
            if st.button("Send / log supplier chase"):
                ok,msg=send_email(row["Email"],subject,body); log_email(None,int(row["Supplier ID"]),"Supplier Document Chase",row["Email"],subject,body,"Sent" if ok else "Preview / Failed","" if ok else msg); st.info(msg)
    with tab5:
        checks=data_quality_checks(); st.dataframe(checks,use_container_width=True,hide_index=True) if not checks.empty else st.success("No data quality issues found.")
    with tab6:
        gaps=evidence_gaps()
        if gaps.empty: st.info("No owner actions.")
        else:
            acc=gaps.groupby(["Owner","Severity"]).size().reset_index(name="Open Actions").sort_values("Open Actions", ascending=False); st.dataframe(acc, use_container_width=True, hide_index=True); st.bar_chart(acc.pivot_table(index="Owner", columns="Severity", values="Open Actions", aggfunc="sum", fill_value=0))


def onboarding():
    hero("Onboarding", "Route new suppliers from request to approval.")
    tab1,tab2,tab3=st.tabs(["Create request", "Review approvals", "Approval routes"])
    with tab1:
        with st.form("create_request"):
            a,b=st.columns(2); name=a.text_input("Supplier name *"); email=a.text_input("Supplier email"); requested=a.text_input("Requested by"); company=a.text_input("Company number"); vat=a.text_input("VAT number"); website=a.text_input("Website"); cat=b.selectbox("Supplier category", [""]+categories()); spend=b.number_input("Expected annual spend", min_value=0.0, step=100.0); urgency=b.selectbox("Urgency", ["Low","Normal","High","Critical"], index=1); company_status=b.selectbox("Company status", COMPANY_STATUSES); vat_status=b.selectbox("VAT status", VAT_STATUSES); sanctions=b.selectbox("Sanctions", SANCTIONS_STATUSES); reason=st.text_area("Why is this supplier needed?"); submit=st.checkbox("Submit for approval immediately", value=True)
            if st.form_submit_button("Create request", type="primary"):
                if not name.strip(): st.error("Supplier name is required.")
                else:
                    domain=clean_domain(email) or clean_domain(website); conf,warn=confidence(company_status,vat_status,sanctions,domain,name,""); status="Awaiting Approval" if submit else "Draft"; rid=exec_sql("""INSERT INTO new_supplier_requests (supplier_name,supplier_email,requested_by,category,reason_needed,expected_annual_spend,urgency,status,company_number,vat_number,website,domain,company_status,vat_status,sanctions_status,supplier_confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (name,email,requested,cat,reason+("\nWarnings: "+warn if warn else ""),spend,urgency,status,company,vat,website,domain,company_status,vat_status,sanctions,conf)); st.success("Request created.")
                    if submit:
                        req=df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]; ok,msg,subject,body=notify_current_approver(req); st.info(msg); st.text_input("Subject", subject); st.text_area("Email", body, height=220)
    with tab2:
        review_approvals()
    with tab3:
        approval_routes()


def review_approvals():
    reqs=df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    if reqs.empty: st.info("No requests yet."); return
    open_only=st.checkbox("Open only", value=True); view=reqs[~reqs["status"].isin(["Approved","Rejected"])] if open_only else reqs; st.dataframe(view,use_container_width=True,hide_index=True)
    if view.empty: return
    opts={f"{r['supplier_name']} ({r['request_id']})": int(r["request_id"]) for _,r in view.iterrows()}; rid=opts[st.selectbox("Select request", list(opts.keys()))]; req=df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]; stage=current_stage(rid,req["category"]); decisions=decisions_for(rid)
    st.markdown(f"### {req['supplier_name']}"); st.markdown(pill(req["status"]), unsafe_allow_html=True); st.write(f"**Category:** {req['category']} | **Urgency:** {req['urgency']} | **Spend:** £{float(req['expected_annual_spend'] or 0):,.2f}"); st.write(f"**Confidence:** {req['supplier_confidence']} | **Company:** {req['company_status']} | **VAT:** {req['vat_status']} | **Sanctions:** {req['sanctions_status']}"); st.write(req["reason_needed"] or "")
    route=stages_for(req["category"])
    if not route.empty:
        approved=set(decisions[decisions["decision"]=="Approved"]["stage_id"].tolist()) if not decisions.empty else set(); route2=route.copy(); route2["stage_status"]=route2["stage_id"].apply(lambda x:"Approved" if x in approved else "Pending"); st.dataframe(route2[["sequence_order","stage_name","approver_name","approver_email","stage_status"]],use_container_width=True,hide_index=True)
    if not decisions.empty: st.dataframe(decisions,use_container_width=True,hide_index=True)
    if req["status"]=="Draft":
        if st.button("Submit for approval", type="primary"): exec_sql("UPDATE new_supplier_requests SET status='Awaiting Approval',updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]); st.rerun()
    elif req["status"] in ["Approved","Rejected"]: st.info(f"This request is already {req['status']}.")
    elif stage is None:
        st.success("All stages complete."); c1,c2=st.columns(2)
        if c1.button("Mark approved"): exec_sql("UPDATE new_supplier_requests SET status='Approved',updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); st.rerun()
        if c2.button("Convert to supplier"):
            exec_sql("""INSERT INTO suppliers (supplier_name,supplier_email,category,owner,approval_status,risk_level,annual_spend,notes,company_number,vat_number,website,domain,company_status,vat_status,sanctions_status,bank_verification_status) VALUES (?,?,?,?, 'Approved','Medium',?,?,?,?,?,?,?,?,?,?)""", (req["supplier_name"],req["supplier_email"],req["category"],req["requested_by"],float(req["expected_annual_spend"] or 0),f"Created from request {rid}",req["company_number"],req["vat_number"],req["website"],req["domain"],req["company_status"],req["vat_status"],req["sanctions_status"],req["bank_verification_status"])); st.success("Supplier created.")
    else:
        st.info(f"Current stage: {stage['stage_name']} — {stage['approver_name']} <{stage['approver_email']}>"); subject,body=approval_email(req,stage); st.text_input("To", stage["approver_email"]); st.text_input("Subject", subject); st.text_area("Body", body, height=220); c1,c2,c3=st.columns(3)
        if c1.button("Send / log email"): ok,msg=send_email(stage["approver_email"],subject,body); log_email(rid,None,"Approval Request",stage["approver_email"],subject,body,"Sent" if ok else "Preview / Failed","" if ok else msg); st.info(msg)
        notes=st.text_area("Decision notes"); decided=st.text_input("Decided by", value=stage["approver_name"])
        if c2.button("Approve stage", type="primary"):
            exec_sql("INSERT OR REPLACE INTO approval_decisions (request_id,stage_id,decision,decided_by,notes,decided_at) VALUES (?,?,'Approved',?,?,CURRENT_TIMESTAMP)", (rid,int(stage["stage_id"]),decided,notes)); next_stage=current_stage(rid,req["category"])
            if next_stage is None: exec_sql("UPDATE new_supplier_requests SET status='Approved',updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
            else: exec_sql("UPDATE new_supplier_requests SET status=?,updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (f"Awaiting {next_stage['stage_name']}",rid)); notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0])
            st.rerun()
        if c3.button("Reject request"): exec_sql("INSERT OR REPLACE INTO approval_decisions (request_id,stage_id,decision,decided_by,notes,decided_at) VALUES (?,?,'Rejected',?,?,CURRENT_TIMESTAMP)", (rid,int(stage["stage_id"]),decided,notes)); exec_sql("UPDATE new_supplier_requests SET status='Rejected',updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); st.rerun()


def approval_routes():
    st.dataframe(df_sql("SELECT * FROM approval_stages ORDER BY category,sequence_order"), use_container_width=True, hide_index=True)
    with st.form("add_stage"):
        a,b,c=st.columns(3); mode=a.radio("Category", ["Use existing","Create new"], horizontal=True); cat=a.selectbox("Existing category", categories()) if mode=="Use existing" else a.text_input("New category"); stage=b.text_input("Stage name"); order=b.number_input("Order", min_value=1, step=1); name=c.text_input("Approver name"); email=c.text_input("Approver email")
        if st.form_submit_button("Add stage"):
            try: exec_sql("INSERT INTO approval_stages (category,stage_name,approver_name,approver_email,sequence_order,is_required) VALUES (?,?,?,?,?,1)", (cat,stage,name,email,int(order))); st.success("Stage added."); st.rerun()
            except sqlite3.IntegrityError: st.warning("That stage already exists.")


def reports():
    hero("Reports & Audit Mode", "Export audit-ready supplier evidence and management summaries.")
    tab1,tab2,tab3=st.tabs(["Management summary", "Audit mode", "Exports"])
    with tab1:
        st.markdown(f"<div class='card'>{management_summary().replace(chr(10), '<br>')}</div>", unsafe_allow_html=True); status=supplier_table()
        if not status.empty:
            split=status.groupby("Can I Buy?").size().reset_index(name="Suppliers"); st.dataframe(split,use_container_width=True,hide_index=True); st.bar_chart(split.set_index("Can I Buy?"))
    with tab2:
        gaps=evidence_gaps(); checks=data_quality_checks(); reqs=df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"); c1,c2,c3=st.columns(3)
        with c1: kpi("Evidence gaps", len(gaps), "documents / controls")
        with c2: kpi("Data issues", len(checks), "master data")
        with c3: kpi("Approved requests", len(reqs[reqs["status"]=="Approved"]) if not reqs.empty else 0, "all time")
        if not gaps.empty: st.dataframe(gaps,use_container_width=True,hide_index=True)
        if not checks.empty: st.dataframe(checks,use_container_width=True,hide_index=True)
    with tab3:
        status=supplier_table(); suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name"); reqs=df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"); stages=df_sql("SELECT * FROM approval_stages ORDER BY category,sequence_order"); docs=df_sql("SELECT * FROM supplier_documents ORDER BY uploaded_at DESC"); emails=df_sql("SELECT * FROM email_log ORDER BY sent_at DESC"); gaps=evidence_gaps(); checks=data_quality_checks(); actions=document_actions()
        if not status.empty: st.download_button("Download supplier compliance CSV", status.to_csv(index=False).encode("utf-8"), "supplierpass_compliance.csv", "text/csv")
        xlsx=DATA_DIR / f"supplierpass_audit_export_{date.today().isoformat()}.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            suppliers.to_excel(writer,index=False,sheet_name="Suppliers"); status.to_excel(writer,index=False,sheet_name="Readiness"); docs.to_excel(writer,index=False,sheet_name="Documents"); actions.to_excel(writer,index=False,sheet_name="Document Actions"); gaps.to_excel(writer,index=False,sheet_name="Evidence Gaps"); checks.to_excel(writer,index=False,sheet_name="Data Quality"); reqs.to_excel(writer,index=False,sheet_name="Requests"); stages.to_excel(writer,index=False,sheet_name="Approval Routes"); emails.to_excel(writer,index=False,sheet_name="Email Log")
        with open(xlsx,"rb") as f: st.download_button("Download full audit pack", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def admin():
    hero("Admin", "Email mode, logs and prototype settings.")
    st.info("SMTP sending is active." if smtp_configured() else "Preview/log mode only. Add SMTP secrets to send real emails.")
    with st.expander("SMTP secrets example"):
        st.code('''SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "supplierpass@yourcompany.co.uk"
SMTP_PASSWORD = "your-password-or-app-password"
FROM_EMAIL = "supplierpass@yourcompany.co.uk"
REPLY_TO_EMAIL = "your.name@yourcompany.co.uk"''', language="toml")
    emails=df_sql("SELECT * FROM email_log ORDER BY sent_at DESC"); st.dataframe(emails,use_container_width=True,hide_index=True) if not emails.empty else st.info("No emails logged yet.")
    st.warning("This is a commercial prototype. Before charging customers, add authentication, tenant separation, secure object storage, a production database, backups, role permissions, licensing, support tooling and legal/security documentation.")


init_db(); apply_style()
st.sidebar.markdown(f"# {APP_NAME}"); st.sidebar.caption(APP_VERSION)
page=st.sidebar.radio("Navigation", ["Command Centre", "Pre-Approval", "Suppliers", "Risk & Compliance", "Onboarding", "Reports", "Admin"])
if page=="Command Centre": command_centre()
elif page=="Pre-Approval": preapproval()
elif page=="Suppliers": suppliers_screen()
elif page=="Risk & Compliance": compliance()
elif page=="Onboarding": onboarding()
elif page=="Reports": reports()
elif page=="Admin": admin()
