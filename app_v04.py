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

st.set_page_config(page_title="SupplierPass v0.4", page_icon="✅", layout="wide")

PRIMARY_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
REQUEST_STATUSES = ["Draft", "Awaiting Approval", "Approved", "Rejected", "On Hold"]


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
    for row in default_stages:
        cur.execute("""INSERT OR IGNORE INTO approval_stages
            (category, stage_name, approver_name, approver_email, sequence_order, is_required)
            VALUES (?, ?, ?, ?, ?, ?)""", row)

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
    for row in default_docs:
        cur.execute("""INSERT OR IGNORE INTO document_rules
            (category, document_type, is_critical, warning_days)
            VALUES (?, ?, ?, ?)""", row)

    c.commit()
    c.close()


def categories():
    df = df_sql("""
        SELECT DISTINCT category FROM approval_stages
        UNION SELECT DISTINCT category FROM document_rules
        UNION SELECT DISTINCT category FROM suppliers
        UNION SELECT DISTINCT category FROM new_supplier_requests
        ORDER BY category
    """)
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


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


def badge(status):
    return {"Green": "🟢 Green", "Amber": "🟠 Amber", "Red": "🔴 Red"}.get(status, status)


def save_upload(upload, supplier_id, doc_type):
    folder = UPLOAD_DIR / str(supplier_id)
    folder.mkdir(exist_ok=True)
    safe = upload.name.replace("/", "_").replace("\\", "_")
    path = folder / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{doc_type.replace('/', '-')}_{safe}"
    with open(path, "wb") as f:
        f.write(upload.getbuffer())
    return upload.name, str(path)


def supplier_status_table():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rules = df_sql("SELECT * FROM document_rules")
    docs = df_sql("SELECT * FROM supplier_documents")
    rows = []
    for _, s in suppliers.iterrows():
        supplier_rules = rules[rules["category"] == s["category"]]
        supplier_docs = docs[docs["supplier_id"] == s["supplier_id"]]
        missing = 0
        expiring = 0
        expired = 0
        overall = "Green"
        next_expiry = ""
        expiry_dates = []
        for _, rule in supplier_rules.iterrows():
            matching = supplier_docs[supplier_docs["document_type"] == rule["document_type"]]
            if matching.empty:
                status = doc_status(None, rule["warning_days"], True, bool(rule["is_critical"]))
                missing += 1
            else:
                latest = matching.sort_values("uploaded_at", ascending=False).iloc[0]
                status = doc_status(latest["expiry_date"], rule["warning_days"], False, bool(rule["is_critical"]))
                d = parse_date(latest["expiry_date"])
                if d:
                    expiry_dates.append(d)
            if status == "Red":
                expired += 1 if not matching.empty else 0
                overall = "Red"
            elif status == "Amber" and overall != "Red":
                expiring += 1 if not matching.empty else 0
                overall = "Amber"
        if expiry_dates:
            next_expiry = min(expiry_dates).isoformat()
        rows.append({
            "Supplier ID": s["supplier_id"],
            "Supplier Code": s["supplier_code"],
            "Supplier Name": s["supplier_name"],
            "Email": s["supplier_email"],
            "Category": s["category"],
            "Owner": s["owner"],
            "Approval Status": s["approval_status"],
            "Compliance": overall,
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
                rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Email": s["supplier_email"], "Category": s["category"], "Document Type": rule["document_type"], "Status": status, "Issue": "Missing document", "Expiry Date": "", "Days Left": ""})
            else:
                latest = matching.sort_values("uploaded_at", ascending=False).iloc[0]
                status = doc_status(latest["expiry_date"], rule["warning_days"], False, bool(rule["is_critical"]))
                if status in ["Red", "Amber"]:
                    issue = "Expired document" if status == "Red" else "Expiring soon / needs review"
                    rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Email": s["supplier_email"], "Category": s["category"], "Document Type": rule["document_type"], "Status": status, "Issue": issue, "Expiry Date": latest["expiry_date"], "Days Left": days_left(latest["expiry_date"])} )
    return pd.DataFrame(rows)


def supplier_import_screen():
    st.write("Upload your supplier file, preview it, then map the columns. Only Supplier Name is required.")
    st.code("SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,Notes")
    file = st.file_uploader("Choose supplier CSV", type=["csv"], key="supplier_csv")
    if not file:
        st.info("Upload a CSV export from Sage, Excel, or your current approved supplier list.")
        return
    data = pd.read_csv(file)
    st.success(f"Loaded {len(data)} rows and {len(data.columns)} columns.")
    st.dataframe(data.head(30), use_container_width=True, hide_index=True)
    cols = data.columns.tolist()
    with st.expander("Map columns", expanded=True):
        c1, c2 = st.columns(2)
        c_code = c1.selectbox("Supplier Code", [""] + cols)
        c_name = c1.selectbox("Supplier Name *", cols)
        c_email = c1.selectbox("Supplier Email", [""] + cols)
        c_cat = c2.selectbox("Category", [""] + cols)
        c_owner = c2.selectbox("Owner", [""] + cols)
        c_status = c2.selectbox("Approval Status", [""] + cols)
        c_notes = st.selectbox("Notes", [""] + cols)
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
            rows.append((code, name,
                str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "",
                str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else "",
                str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "",
                str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved",
                "Medium",
                str(r[c_notes]).strip() if c_notes and pd.notna(r[c_notes]) else ""))
        many_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rows)
        st.success(f"Imported {len(rows)} suppliers. Skipped {skipped} duplicates.")


init_db()

st.markdown("""
<style>
.big-card {border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; background: #fafafa; margin-bottom: 10px;}
.step-pill {display:inline-block; padding: 4px 10px; border-radius: 20px; background:#eef2ff; margin-right:6px; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("SupplierPass")
st.sidebar.caption("v0.4 guided workflow")
page = st.sidebar.radio("Process", [
    "Home",
    "1. Import Suppliers",
    "2. Set Rules & Approvers",
    "3. Supplier Documents",
    "4. New Supplier Request",
    "5. Review Approvals",
    "6. Actions & Chasers",
    "7. Reports & Exports",
    "Admin / Email Log",
])

if page == "Home":
    st.title("SupplierPass")
    st.caption("A guided workflow for supplier compliance and new supplier onboarding.")
    suppliers = df_sql("SELECT * FROM suppliers")
    requests = df_sql("SELECT * FROM new_supplier_requests")
    stages = df_sql("SELECT * FROM approval_stages WHERE is_required=1")
    actions = document_actions()

    st.markdown("""
    <div class='big-card'>
    <b>Recommended process</b><br><br>
    <span class='step-pill'>1 Import suppliers</span>
    <span class='step-pill'>2 Set rules & approvers</span>
    <span class='step-pill'>3 Upload documents</span>
    <span class='step-pill'>4 Request new supplier</span>
    <span class='step-pill'>5 Review approvals</span>
    <span class='step-pill'>6 Chase issues</span>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Suppliers", len(suppliers))
    c2.metric("Approval stages", len(stages))
    c3.metric("Open requests", int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0)
    c4.metric("Document actions", len(actions))

    st.subheader("What needs doing next?")
    if suppliers.empty:
        st.warning("Start by importing your supplier file in step 1.")
    elif stages.empty:
        st.warning("Set approval stages in step 2.")
    elif not actions.empty:
        st.warning("There are supplier document actions to review in step 6.")
    else:
        st.success("The basic setup looks ready. Create a new supplier request or upload supplier documents.")

    st.subheader("Quick view: suppliers needing document attention")
    if actions.empty:
        st.info("No missing or expiring document actions found yet.")
    else:
        show = actions.copy(); show["Status"] = show["Status"].apply(badge)
        st.dataframe(show, use_container_width=True, hide_index=True)

elif page == "1. Import Suppliers":
    st.title("Step 1 — Import Suppliers")
    st.caption("Bring in your current supplier list first. This becomes the base supplier register.")
    tab1, tab2 = st.tabs(["Import supplier file", "View / edit supplier register"])
    with tab1:
        supplier_import_screen()
    with tab2:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers imported yet.")
        else:
            search = st.text_input("Search suppliers")
            view = suppliers.copy()
            if search:
                mask = view.apply(lambda r: search.lower() in " ".join([str(x).lower() for x in r.values]), axis=1)
                view = view[mask]
            st.dataframe(view, use_container_width=True, hide_index=True)
        with st.expander("Add one supplier manually"):
            with st.form("manual_supplier"):
                code = st.text_input("Supplier Code")
                name = st.text_input("Supplier Name *")
                email = st.text_input("Supplier Email")
                cat = st.selectbox("Category", [""] + categories())
                owner = st.text_input("Owner")
                status = st.selectbox("Approval Status", PRIMARY_STATUSES)
                risk = st.selectbox("Risk Level", ["Low", "Medium", "High", "Critical"], index=1)
                notes = st.text_area("Notes")
                if st.form_submit_button("Add supplier"):
                    if not name.strip(): st.error("Supplier name is required.")
                    else:
                        exec_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (code, name, email, cat, owner, status, risk, notes))
                        st.success("Supplier added."); st.rerun()

elif page == "2. Set Rules & Approvers":
    st.title("Step 2 — Set Rules & Approvers")
    st.caption("Tell SupplierPass what documents are needed and who approves each category.")
    tab1, tab2 = st.tabs(["Document rules", "Approval stages"])
    with tab1:
        rules = df_sql("SELECT * FROM document_rules ORDER BY category, is_critical DESC, document_type")
        st.dataframe(rules, use_container_width=True, hide_index=True)
        with st.form("add_doc_rule"):
            st.subheader("Add document rule")
            mode = st.radio("Category", ["Use existing", "Create new"], horizontal=True, key="doc_cat_mode")
            cat = st.selectbox("Existing category", categories(), key="doc_cat_existing") if mode == "Use existing" else st.text_input("New category", key="doc_cat_new")
            doc_type = st.text_input("Required document", placeholder="Public Liability Insurance")
            critical = st.checkbox("Critical document", value=True)
            warning = st.number_input("Warn when expiry is within this many days", min_value=0, value=60)
            if st.form_submit_button("Add document rule"):
                try:
                    exec_sql("INSERT INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)", (cat, doc_type, int(critical), int(warning)))
                    st.success("Document rule added."); st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("That rule already exists.")
    with tab2:
        stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
        st.dataframe(stages, use_container_width=True, hide_index=True)
        with st.form("add_stage"):
            st.subheader("Add approval stage")
            mode = st.radio("Category", ["Use existing", "Create new"], horizontal=True, key="stage_cat_mode")
            cat = st.selectbox("Existing category", categories(), key="stage_cat_existing") if mode == "Use existing" else st.text_input("New category", key="stage_cat_new")
            stage_name = st.text_input("Stage name", placeholder="Quality Review")
            approver_name = st.text_input("Approver name")
            approver_email = st.text_input("Approver email")
            order = st.number_input("Order", min_value=1, step=1)
            if st.form_submit_button("Add approval stage"):
                try:
                    exec_sql("INSERT INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, 1)", (cat, stage_name, approver_name, approver_email, int(order)))
                    st.success("Approval stage added."); st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("That stage already exists.")
        st.subheader("Bulk import approval stages")
        st.code("Category,StageName,ApproverName,ApproverEmail,Order")
        file = st.file_uploader("Upload approval stages CSV", type=["csv"], key="approval_stage_csv")
        if file:
            data = pd.read_csv(file); st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            if st.button("Import approval stages"):
                rows = [(str(r["Category"]), str(r["StageName"]), str(r["ApproverName"]), str(r["ApproverEmail"]), int(r["Order"]), 1) for _, r in data.iterrows()]
                many_sql("INSERT OR IGNORE INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, ?)", rows)
                st.success(f"Imported {len(rows)} approval stages."); st.rerun()

elif page == "3. Supplier Documents":
    st.title("Step 3 — Supplier Documents")
    st.caption("Upload documents against suppliers and track expiry dates.")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.warning("Import suppliers first.")
    else:
        opts = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
        sid = opts[st.selectbox("Supplier", list(opts.keys()))]
        supplier = suppliers[suppliers["supplier_id"] == sid].iloc[0]
        rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (supplier["category"] or "",))
        if not rules.empty:
            st.write("Required documents for this supplier category:")
            st.dataframe(rules[["document_type", "is_critical", "warning_days"]], use_container_width=True, hide_index=True)
        with st.form("doc_upload"):
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
                    st.success("Document saved."); st.rerun()
        docs = df_sql("""SELECT d.*, s.supplier_name FROM supplier_documents d JOIN suppliers s ON d.supplier_id=s.supplier_id ORDER BY d.uploaded_at DESC""")
        if docs.empty:
            st.info("No documents uploaded yet.")
        else:
            docs["days_left"] = docs["expiry_date"].apply(days_left)
            st.dataframe(docs, use_container_width=True, hide_index=True)

elif page == "4. New Supplier Request":
    st.title("Step 4 — New Supplier Request")
    st.caption("Use this when someone wants to create or approve a new supplier.")
    with st.form("new_request_guided"):
        name = st.text_input("Supplier name *")
        email = st.text_input("Supplier email")
        requested_by = st.text_input("Requested by")
        cat = st.selectbox("Supplier category", [""] + categories())
        reason = st.text_area("Why is this supplier needed?")
        spend = st.number_input("Expected annual spend", min_value=0.0, step=100.0)
        urgency = st.selectbox("Urgency", ["Low", "Normal", "High", "Critical"], index=1)
        submit = st.checkbox("Submit for approval immediately", value=True)
        if st.form_submit_button("Create request", type="primary"):
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
                    with st.expander("Email preview", expanded=True):
                        st.text_input("Subject", subject)
                        st.text_area("Body", body, height=240)

elif page == "5. Review Approvals":
    st.title("Step 5 — Review Approvals")
    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    if requests.empty:
        st.info("No supplier requests yet.")
    else:
        open_only = st.checkbox("Show open requests only", value=True)
        view = requests[~requests["status"].isin(["Approved", "Rejected"])] if open_only else requests
        st.dataframe(view, use_container_width=True, hide_index=True)
        opts = {f"{r['supplier_name']} ({r['request_id']})": int(r["request_id"]) for _, r in view.iterrows()}
        if opts:
            rid = opts[st.selectbox("Select request", list(opts.keys()))]
            req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0]
            stage = current_stage(rid, req["category"])
            decisions = decisions_for(rid)
            st.subheader(req["supplier_name"])
            st.write(f"Status: **{req['status']}** | Category: **{req['category']}** | Urgency: **{req['urgency']}**")
            st.write(req["reason_needed"] or "")
            route = stages_for(req["category"])
            if not route.empty:
                approved = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
                route2 = route.copy(); route2["stage_status"] = route2["stage_id"].apply(lambda x: "Approved" if x in approved else "Pending")
                st.dataframe(route2[["sequence_order", "stage_name", "approver_name", "approver_email", "stage_status"]], use_container_width=True, hide_index=True)
            if not decisions.empty:
                st.write("Approval history")
                st.dataframe(decisions, use_container_width=True, hide_index=True)
            if req["status"] == "Draft":
                if st.button("Submit for approval", type="primary"):
                    exec_sql("UPDATE new_supplier_requests SET status='Awaiting Approval', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,))
                    notify_current_approver(df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (rid,)).iloc[0])
                    st.rerun()
            elif req["status"] in ["Approved", "Rejected"]:
                st.info(f"Already {req['status']}.")
            elif stage is None:
                st.success("All approval stages complete.")
                c1, c2 = st.columns(2)
                if c1.button("Mark approved"):
                    exec_sql("UPDATE new_supplier_requests SET status='Approved', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); st.rerun()
                if c2.button("Convert to supplier"):
                    exec_sql("""INSERT INTO suppliers (supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                              VALUES (?, ?, ?, ?, 'Approved', 'Medium', ?)""", (req["supplier_name"], req["supplier_email"], req["category"], req["requested_by"], f"Created from request {rid}"))
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
                    exec_sql("UPDATE new_supplier_requests SET status='Rejected', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (rid,)); st.rerun()

elif page == "6. Actions & Chasers":
    st.title("Step 6 — Actions & Chasers")
    actions = document_actions()
    if actions.empty:
        st.success("No missing or expiring document actions found.")
    else:
        show = actions.copy(); show["Status"] = show["Status"].apply(badge)
        st.dataframe(show, use_container_width=True, hide_index=True)
        opts = {f"{r['Supplier Name']} - {r['Document Type']} ({r['Issue']})": i for i, r in actions.iterrows()}
        idx = opts[st.selectbox("Select action", list(opts.keys()))]
        row = actions.loc[idx]
        subject = f"Supplier document request - {row['Document Type']}"
        body = f"""Hi {row['Supplier Name']},

We are updating our approved supplier records and need the following document from you:

{row['Document Type']}

Reason: {row['Issue']}

Please could you send the latest version, including the expiry date where applicable?

Many thanks,
[Your Name]
"""
        st.text_input("To", row["Email"] or "")
        st.text_input("Subject", subject)
        st.text_area("Body", body, height=220)
        if st.button("Send / log chase email"):
            ok, msg = send_email(row["Email"], subject, body)
            log_email(None, int(row["Supplier ID"]), "Supplier Document Chase", row["Email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
            st.info(msg)

elif page == "7. Reports & Exports":
    st.title("Step 7 — Reports & Exports")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    status = supplier_status_table()
    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
    docs = df_sql("SELECT * FROM supplier_documents ORDER BY uploaded_at DESC")
    st.subheader("Supplier compliance summary")
    if status.empty:
        st.info("No suppliers yet.")
    else:
        show = status.copy(); show["Compliance"] = show["Compliance"].apply(badge)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button("Download supplier compliance CSV", status.to_csv(index=False).encode("utf-8"), "supplier_compliance.csv", "text/csv")
    xlsx = DATA_DIR / f"supplierpass_export_{date.today().isoformat()}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        suppliers.to_excel(writer, index=False, sheet_name="Suppliers")
        status.to_excel(writer, index=False, sheet_name="Compliance")
        requests.to_excel(writer, index=False, sheet_name="Requests")
        stages.to_excel(writer, index=False, sheet_name="Approval Stages")
        docs.to_excel(writer, index=False, sheet_name="Documents")
        document_actions().to_excel(writer, index=False, sheet_name="Actions")
    with open(xlsx, "rb") as f:
        st.download_button("Download full Excel export", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif page == "Admin / Email Log":
    st.title("Admin / Email Log")
    st.info("Email mode: SMTP sending is active." if smtp_configured() else "Email mode: preview/log only. Add SMTP secrets to send real emails.")
    with st.expander("SMTP secrets example"):
        st.code('''SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "supplierpass@yourcompany.co.uk"
SMTP_PASSWORD = "your-password-or-app-password"
FROM_EMAIL = "supplierpass@yourcompany.co.uk"
REPLY_TO_EMAIL = "your.name@yourcompany.co.uk"''', language="toml")
    emails = df_sql("SELECT * FROM email_log ORDER BY sent_at DESC")
    if emails.empty:
        st.info("No emails logged yet.")
    else:
        st.dataframe(emails, use_container_width=True, hide_index=True)
