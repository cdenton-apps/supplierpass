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

st.set_page_config(page_title="SupplierPass v0.3", page_icon="✅", layout="wide")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def exec_sql(sql, params=()):
    c = conn(); cur = c.cursor(); cur.execute(sql, params); c.commit(); new_id = cur.lastrowid; c.close(); return new_id


def many_sql(sql, rows):
    c = conn(); cur = c.cursor(); cur.executemany(sql, rows); c.commit(); c.close()


def df_sql(sql, params=()):
    c = conn(); df = pd.read_sql_query(sql, c, params=params); c.close(); return df


def init_db():
    c = conn(); cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_code TEXT,
        supplier_name TEXT NOT NULL,
        supplier_email TEXT,
        category TEXT,
        owner TEXT,
        approval_status TEXT DEFAULT 'Approved',
        risk_level TEXT DEFAULT 'Medium',
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
    defaults = [
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
    for r in defaults:
        cur.execute("""INSERT OR IGNORE INTO approval_stages
            (category, stage_name, approver_name, approver_email, sequence_order, is_required)
            VALUES (?, ?, ?, ?, ?, ?)""", r)
    c.commit(); c.close()


def categories():
    df = df_sql("""SELECT DISTINCT category FROM approval_stages UNION SELECT DISTINCT category FROM suppliers UNION SELECT DISTINCT category FROM new_supplier_requests ORDER BY category""")
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def stages_for(category):
    return df_sql("SELECT * FROM approval_stages WHERE category=? AND is_required=1 ORDER BY sequence_order", (category or "",))


def decisions_for(request_id):
    return df_sql("""SELECT d.*, s.stage_name, s.sequence_order, s.approver_name, s.approver_email
        FROM approval_decisions d JOIN approval_stages s ON d.stage_id=s.stage_id
        WHERE d.request_id=? ORDER BY s.sequence_order""", (request_id,))


def current_stage(request_id, category):
    stages = stages_for(category); decisions = decisions_for(request_id)
    approved = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
    for _, stage in stages.iterrows():
        if int(stage["stage_id"]) not in approved:
            return stage
    return None


def smtp_configured():
    return all(k in st.secrets for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"])


def send_email(to_email, subject, body):
    if not smtp_configured():
        return False, "SMTP is not configured. Email preview/log only."
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
    exec_sql("""INSERT INTO email_log (request_id, supplier_id, email_type, recipient, subject, body, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (request_id, supplier_id, email_type, recipient, subject, body, status, error))


def approval_email(req, stage):
    subject = f"SupplierPass approval required - {req['supplier_name']}"
    body = f"""Hi {stage['approver_name']},

A new supplier request is awaiting your review.

Supplier: {req['supplier_name']}
Category: {req['category']}
Requested by: {req['requested_by'] or ''}
Expected annual spend: {req['expected_annual_spend'] or 0}
Urgency: {req['urgency'] or 'Normal'}
Current stage: {stage['stage_name']}

Reason needed:
{req['reason_needed'] or ''}

Please review this request in SupplierPass and approve, reject, or place it on hold.

Thanks,
SupplierPass
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


def parse_date(v):
    try:
        if v is None or v == "" or pd.isna(v): return None
        return pd.to_datetime(v).date()
    except Exception:
        return None


def days_left(v):
    d = parse_date(v)
    return None if d is None else (d - date.today()).days


def save_upload(upload, supplier_id, doc_type):
    folder = UPLOAD_DIR / str(supplier_id); folder.mkdir(exist_ok=True)
    safe = upload.name.replace("/", "_").replace("\\", "_")
    path = folder / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{doc_type.replace('/', '-')}_{safe}"
    with open(path, "wb") as f: f.write(upload.getbuffer())
    return upload.name, str(path)


def supplier_import_tab():
    st.subheader("Import Suppliers from CSV")
    st.write("Use this for your supplier file. Upload the CSV, map the columns, then import.")
    st.code("SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,Notes")
    file = st.file_uploader("Upload supplier CSV", type=["csv"], key="supplier_csv")
    if not file:
        return
    data = pd.read_csv(file)
    st.dataframe(data.head(25), use_container_width=True, hide_index=True)
    cols = data.columns.tolist()
    c_code = st.selectbox("Supplier Code column", [""] + cols)
    c_name = st.selectbox("Supplier Name column *", cols)
    c_email = st.selectbox("Supplier Email column", [""] + cols)
    c_cat = st.selectbox("Category column", [""] + cols)
    c_owner = st.selectbox("Owner column", [""] + cols)
    c_status = st.selectbox("Approval Status column", [""] + cols)
    c_notes = st.selectbox("Notes column", [""] + cols)
    skip_duplicates = st.checkbox("Skip suppliers with the same supplier code", value=True)
    if st.button("Import Supplier File"):
        existing_codes = set(df_sql("SELECT supplier_code FROM suppliers WHERE supplier_code IS NOT NULL AND supplier_code <> ''")["supplier_code"].astype(str).tolist())
        rows = []
        skipped = 0
        for _, r in data.iterrows():
            name = str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
            if not name: continue
            code = str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else ""
            if skip_duplicates and code and code in existing_codes:
                skipped += 1; continue
            rows.append((code, name,
                str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "",
                str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else "",
                str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "",
                str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved",
                "Medium",
                str(r[c_notes]).strip() if c_notes and pd.notna(r[c_notes]) else ""))
        if rows:
            many_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rows)
        st.success(f"Imported {len(rows)} suppliers. Skipped {skipped} duplicates.")


init_db()
st.sidebar.title("SupplierPass")
st.sidebar.caption("v0.3 supplier import + approvals")
page = st.sidebar.radio("Navigation", ["Dashboard", "Supplier Register", "Supplier Documents", "New Supplier Requests", "Approval Stages", "Email Log", "Exports", "Help"])

if page == "Dashboard":
    st.title("SupplierPass v0.3")
    st.caption("Supplier import, supplier document uploads, new supplier approvals, and optional email sending.")
    suppliers = df_sql("SELECT * FROM suppliers")
    requests = df_sql("SELECT * FROM new_supplier_requests")
    docs = df_sql("SELECT * FROM supplier_documents")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Suppliers", len(suppliers))
    c2.metric("Supplier Documents", len(docs))
    c3.metric("Open Requests", int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0)
    c4.metric("Email Mode", "SMTP" if smtp_configured() else "Preview")
    st.subheader("Current Requests")
    if requests.empty: st.info("No requests yet.")
    else: st.dataframe(requests.sort_values("created_at", ascending=False), use_container_width=True, hide_index=True)

elif page == "Supplier Register":
    st.title("Supplier Register")
    tab1, tab2, tab3 = st.tabs(["Supplier List", "Add Supplier", "Import Supplier File"])
    with tab1:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers yet. Use the Import Supplier File tab.")
        else:
            st.dataframe(suppliers, use_container_width=True, hide_index=True)
            st.download_button("Download Suppliers CSV", suppliers.to_csv(index=False).encode("utf-8"), "suppliers_export.csv", "text/csv")
    with tab2:
        with st.form("add_supplier"):
            code = st.text_input("Supplier Code")
            name = st.text_input("Supplier Name *")
            email = st.text_input("Supplier Email")
            cat = st.selectbox("Category", [""] + categories())
            owner = st.text_input("Owner")
            status = st.selectbox("Approval Status", ["Approved", "Pending", "Blocked", "Dormant", "On Hold"])
            risk = st.selectbox("Risk Level", ["Low", "Medium", "High", "Critical"], index=1)
            notes = st.text_area("Notes")
            if st.form_submit_button("Add Supplier"):
                if not name.strip(): st.error("Supplier name is required.")
                else:
                    exec_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (code, name, email, cat, owner, status, risk, notes))
                    st.success("Supplier added.")
    with tab3:
        supplier_import_tab()

elif page == "Supplier Documents":
    st.title("Supplier Documents")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.info("Add or import suppliers before uploading documents.")
    else:
        opts = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
        sid = opts[st.selectbox("Select supplier", list(opts.keys()))]
        with st.form("upload_doc"):
            doc_type = st.text_input("Document Type", placeholder="Public Liability Insurance")
            expiry = st.date_input("Expiry Date", value=None)
            notes = st.text_area("Notes")
            upload = st.file_uploader("Upload supplier document")
            if st.form_submit_button("Save Document"):
                if not doc_type.strip() or not upload: st.error("Document type and file are required.")
                else:
                    fname, fpath = save_upload(upload, sid, doc_type)
                    exec_sql("""INSERT INTO supplier_documents (supplier_id, document_type, file_name, file_path, expiry_date, notes)
                              VALUES (?, ?, ?, ?, ?, ?)""", (sid, doc_type, fname, fpath, expiry.isoformat() if expiry else None, notes))
                    st.success("Document uploaded.")
        docs = df_sql("""SELECT d.*, s.supplier_name FROM supplier_documents d JOIN suppliers s ON d.supplier_id=s.supplier_id ORDER BY d.uploaded_at DESC""")
        if docs.empty: st.info("No documents uploaded yet.")
        else:
            docs["days_left"] = docs["expiry_date"].apply(days_left)
            st.dataframe(docs, use_container_width=True, hide_index=True)

elif page == "New Supplier Requests":
    st.title("New Supplier Requests")
    tab1, tab2 = st.tabs(["Request List / Approval", "Create Request"])
    with tab2:
        with st.form("create_request"):
            name = st.text_input("Supplier Name *")
            email = st.text_input("Supplier Email")
            requested_by = st.text_input("Requested By")
            cat = st.selectbox("Category", [""] + categories())
            reason = st.text_area("Reason Needed")
            spend = st.number_input("Expected Annual Spend", min_value=0.0, step=100.0)
            urgency = st.selectbox("Urgency", ["Low", "Normal", "High", "Critical"], index=1)
            submit_now = st.checkbox("Submit for approval immediately", value=True)
            if st.form_submit_button("Create Request"):
                if not name.strip(): st.error("Supplier name is required.")
                else:
                    status = "Awaiting Approval" if submit_now else "Draft"
                    rid = exec_sql("""INSERT INTO new_supplier_requests (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status)
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (name, email, requested_by, cat, reason, spend, urgency, status))
                    st.success("Request created.")
                    if submit_now:
                        req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]
                        ok, msg, subject, body = notify_current_approver(req)
                        st.write(msg); st.text_input("Subject", subject); st.text_area("Email body", body, height=220)
    with tab1:
        reqs = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
        if reqs.empty: st.info("No requests yet.")
        else:
            st.dataframe(reqs, use_container_width=True, hide_index=True)
            opts = {f"{r['supplier_name']} ({r['request_id']})": int(r["request_id"]) for _, r in reqs.iterrows()}
            rid = opts[st.selectbox("Select request", list(opts.keys()))]
            req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]
            stage = current_stage(rid, req["category"]); decisions = decisions_for(rid)
            st.subheader(req["supplier_name"])
            st.write(f"Status: **{req['status']}** | Category: **{req['category']}** | Urgency: **{req['urgency']}**")
            st.write(req["reason_needed"] or "")
            route = stages_for(req["category"])
            if route.empty: st.warning("No approval route configured for this category.")
            else:
                approved = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
                route2 = route.copy(); route2["stage_status"] = route2["stage_id"].apply(lambda x: "Approved" if x in approved else "Pending")
                st.dataframe(route2[["sequence_order", "stage_name", "approver_name", "approver_email", "stage_status"]], use_container_width=True, hide_index=True)
            if not decisions.empty: st.dataframe(decisions, use_container_width=True, hide_index=True)
            if req["status"] == "Draft":
                if st.button("Submit for Approval"):
                    exec_sql("UPDATE new_supplier_requests SET status='Awaiting Approval', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                    notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]); st.rerun()
            elif req["status"] in ["Approved", "Rejected"]: st.info(f"Already {req['status']}.")
            elif stage is None:
                st.success("All approval stages complete.")
                if st.button("Mark Approved"):
                    exec_sql("UPDATE new_supplier_requests SET status='Approved', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); st.rerun()
                if st.button("Convert to Supplier"):
                    exec_sql("""INSERT INTO suppliers (supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                              VALUES (?, ?, ?, ?, 'Approved', 'Medium', ?)""", (req["supplier_name"], req["supplier_email"], req["category"], req["requested_by"], f"Created from request {rid}")); st.success("Supplier created.")
            else:
                st.write(f"Awaiting **{stage['stage_name']}** from **{stage['approver_name']}** <{stage['approver_email']}>")
                subject, body = approval_email(req, stage)
                st.text_input("Email To", stage["approver_email"]); st.text_input("Subject", subject); st.text_area("Body", body, height=220)
                col1, col2, col3 = st.columns(3)
                if col1.button("Send / Log Email"):
                    ok, msg = send_email(stage["approver_email"], subject, body)
                    log_email(rid, None, "Approval Request", stage["approver_email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
                    st.write(msg)
                notes = st.text_area("Decision notes")
                decided_by = st.text_input("Decided by", value=stage["approver_name"])
                if col2.button("Approve Stage"):
                    exec_sql("""INSERT OR REPLACE INTO approval_decisions (request_id, stage_id, decision, decided_by, notes, decided_at)
                              VALUES (?, ?, 'Approved', ?, ?, CURRENT_TIMESTAMP)""", (rid, int(stage["stage_id"]), decided_by, notes))
                    next_stage = current_stage(rid, req["category"])
                    if next_stage is None: exec_sql("UPDATE new_supplier_requests SET status='Approved', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                    else:
                        exec_sql("UPDATE new_supplier_requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (f"Awaiting {next_stage['stage_name']}", rid))
                        notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0])
                    st.rerun()
                if col3.button("Reject Request"):
                    exec_sql("""INSERT OR REPLACE INTO approval_decisions (request_id, stage_id, decision, decided_by, notes, decided_at)
                              VALUES (?, ?, 'Rejected', ?, ?, CURRENT_TIMESTAMP)""", (rid, int(stage["stage_id"]), decided_by, notes))
                    exec_sql("UPDATE new_supplier_requests SET status='Rejected', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); st.rerun()

elif page == "Approval Stages":
    st.title("Approval Stages")
    stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
    st.dataframe(stages, use_container_width=True, hide_index=True)
    with st.form("add_stage"):
        mode = st.radio("Category", ["Use existing", "Create new"], horizontal=True)
        cat = st.selectbox("Existing Category", categories()) if mode == "Use existing" else st.text_input("New Category")
        stage_name = st.text_input("Stage Name")
        approver_name = st.text_input("Approver Name")
        approver_email = st.text_input("Approver Email")
        order = st.number_input("Order", min_value=1, step=1)
        if st.form_submit_button("Add Stage"):
            if not cat or not stage_name or not approver_name or not approver_email: st.error("All fields are required.")
            else:
                try:
                    exec_sql("INSERT INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, 1)", (cat, stage_name, approver_name, approver_email, int(order)))
                    st.success("Stage added."); st.rerun()
                except sqlite3.IntegrityError: st.warning("That stage already exists.")
    st.subheader("Import Approval Stages from CSV")
    st.code("Category,StageName,ApproverName,ApproverEmail,Order")
    file = st.file_uploader("Upload approval stages CSV", type=["csv"], key="approval_csv")
    if file:
        data = pd.read_csv(file); st.dataframe(data.head(20), use_container_width=True, hide_index=True)
        if st.button("Import Approval Stages"):
            rows=[]
            for _, r in data.iterrows():
                rows.append((str(r["Category"]), str(r["StageName"]), str(r["ApproverName"]), str(r["ApproverEmail"]), int(r["Order"]), 1))
            many_sql("INSERT OR IGNORE INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, ?)", rows)
            st.success(f"Imported {len(rows)} approval stages.")

elif page == "Email Log":
    st.title("Email Log")
    emails = df_sql("SELECT * FROM email_log ORDER BY sent_at DESC")
    if emails.empty: st.info("No emails logged yet.")
    else: st.dataframe(emails, use_container_width=True, hide_index=True)

elif page == "Exports":
    st.title("Exports")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
    docs = df_sql("SELECT * FROM supplier_documents ORDER BY uploaded_at DESC")
    st.download_button("Download Suppliers CSV", suppliers.to_csv(index=False).encode("utf-8"), "suppliers.csv", "text/csv")
    st.download_button("Download Requests CSV", requests.to_csv(index=False).encode("utf-8"), "supplier_requests.csv", "text/csv")
    xlsx = DATA_DIR / f"supplierpass_export_{date.today().isoformat()}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        suppliers.to_excel(writer, index=False, sheet_name="Suppliers")
        requests.to_excel(writer, index=False, sheet_name="Requests")
        stages.to_excel(writer, index=False, sheet_name="Approval Stages")
        docs.to_excel(writer, index=False, sheet_name="Documents")
    with open(xlsx, "rb") as f:
        st.download_button("Download Full Excel Export", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif page == "Help":
    st.title("Help")
    st.write("Use `Supplier Register > Import Supplier File` to upload your supplier CSV file.")
    st.write("Use `Approval Stages` to set who receives each approval email by category.")
    st.write("Email sending is preview/log only unless SMTP secrets are configured in Streamlit.")
    st.code('''SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "supplierpass@yourcompany.co.uk"
SMTP_PASSWORD = "your-password-or-app-password"
FROM_EMAIL = "supplierpass@yourcompany.co.uk"
REPLY_TO_EMAIL = "your.name@yourcompany.co.uk"''', language="toml")
