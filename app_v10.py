import sqlite3
from datetime import date, timedelta
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
APP_VERSION = "v0.10 stable document workflow"

SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
DOC_REVIEW_STATUSES = ["Uploaded", "Under Review", "Accepted", "Rejected / Needs replacement", "Archived / Ignore"]

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code TEXT,
            supplier_name TEXT NOT NULL,
            supplier_email TEXT,
            category TEXT,
            owner TEXT,
            approval_status TEXT DEFAULT 'Pending',
            risk_level TEXT DEFAULT 'Medium',
            annual_spend REAL DEFAULT 0,
            criticality TEXT DEFAULT 'Standard',
            company_number TEXT,
            vat_number TEXT,
            website TEXT,
            company_status TEXT DEFAULT 'Not checked',
            vat_status TEXT DEFAULT 'Not checked',
            sanctions_status TEXT DEFAULT 'Not checked',
            bank_verification_status TEXT DEFAULT 'Not started',
            next_review_date TEXT,
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
            reviewed_by TEXT,
            review_status TEXT DEFAULT 'Uploaded',
            review_notes TEXT,
            notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_issues (
            issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            issue_type TEXT,
            severity TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Open',
            owner TEXT,
            description TEXT,
            resolution TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_timeline (
            timeline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            event_type TEXT,
            event_detail TEXT,
            user TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            expected_annual_spend REAL,
            urgency TEXT DEFAULT 'Normal',
            status TEXT DEFAULT 'Draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.commit()
    c.close()

    for table, cols in {
        "suppliers": {
            "criticality": "TEXT DEFAULT 'Standard'",
            "company_number": "TEXT",
            "vat_number": "TEXT",
            "website": "TEXT",
            "company_status": "TEXT DEFAULT 'Not checked'",
            "vat_status": "TEXT DEFAULT 'Not checked'",
            "sanctions_status": "TEXT DEFAULT 'Not checked'",
            "bank_verification_status": "TEXT DEFAULT 'Not started'",
            "next_review_date": "TEXT",
        },
        "supplier_documents": {
            "reviewed_by": "TEXT",
            "review_status": "TEXT DEFAULT 'Uploaded'",
            "review_notes": "TEXT",
            "reviewed_at": "TEXT",
        },
    }.items():
        for col, definition in cols.items():
            ensure_column(table, col, definition)

    many_sql(
        "INSERT OR IGNORE INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)",
        DEFAULT_RULES,
    )


def apply_style():
    st.markdown("""
    <style>
    .block-container{padding-top:1rem}
    .hero{border-radius:22px;padding:24px 28px;background:linear-gradient(135deg,#0f172a,#1d4ed8 55%,#0f766e);color:white;margin-bottom:18px}
    .hero h1{margin:0;color:white}.hero p{color:#dbeafe}
    .kpi{border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff}
    .lab{font-size:.82rem;color:#64748b}.val{font-size:1.6rem;font-weight:750}.sub{font-size:.8rem;color:#64748b}
    .hint{border-left:4px solid #2563eb;background:#eff6ff;padding:12px 14px;border-radius:10px;margin:8px 0 16px 0;color:#1e3a8a}
    [data-testid="stSidebar"]{background:#0f172a}[data-testid="stSidebar"] *{color:#f8fafc!important}
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
        ORDER BY category
    """)
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def add_timeline(supplier_id, event_type, detail, user=""):
    exec_sql("INSERT INTO supplier_timeline (supplier_id, event_type, event_detail, user) VALUES (?, ?, ?, ?)", (supplier_id, event_type, detail, user))


def supplier_checklist(supplier):
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (supplier["category"] or "",))
    docs = df_sql("SELECT * FROM supplier_documents WHERE supplier_id=? AND review_status != 'Archived / Ignore'", (supplier["supplier_id"],))
    rows = []
    for _, rule in rules.iterrows():
        matching = docs[docs["document_type"] == rule["document_type"]]
        if matching.empty:
            rows.append({"Document Type": rule["document_type"], "Required": "Yes" if rule["is_critical"] else "Optional", "Status": "Red" if rule["is_critical"] else "Amber", "Issue": "Missing document", "Review Status": "Not received", "Expiry Date": "", "Days Left": ""})
            continue
        accepted = matching[matching["review_status"] == "Accepted"]
        latest = (accepted if not accepted.empty else matching).sort_values("uploaded_at", ascending=False).iloc[0]
        if latest["review_status"] != "Accepted":
            status = "Amber"
            issue = "Needs review"
        else:
            dleft = days_left(latest["expiry_date"])
            if dleft is None:
                status = "Amber"
                issue = "No expiry date"
            elif dleft < 0:
                status = "Red"
                issue = "Expired document"
            elif dleft <= int(rule["warning_days"] or 60):
                status = "Amber"
                issue = "Expiring soon"
            else:
                status = "Green"
                issue = ""
        rows.append({"Document Type": rule["document_type"], "Required": "Yes" if rule["is_critical"] else "Optional", "Status": status, "Issue": issue, "Review Status": latest["review_status"], "Expiry Date": latest["expiry_date"] or "", "Days Left": days_left(latest["expiry_date"]) if days_left(latest["expiry_date"]) is not None else ""})
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
    elif supplier["approval_status"] == "Dormant":
        buy = "Dormant"
    elif missing > 0 or needs_review > 0 or expiring > 0:
        buy = "Can Buy with Warning"
    else:
        buy = "Can Buy"
    reasons = []
    if missing: reasons.append(f"{missing} missing document(s)")
    if needs_review: reasons.append(f"{needs_review} document(s) awaiting review")
    if expired: reasons.append(f"{expired} expired document(s)")
    if expiring: reasons.append(f"{expiring} document(s) expiring soon")
    if supplier["approval_status"] != "Approved": reasons.append(f"Approval status is {supplier['approval_status']}")
    return score, buy, reasons, missing, needs_review, expired, expiring


def supplier_table():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    for _, s in suppliers.iterrows():
        score, buy, reasons, missing, needs_review, expired, expiring = supplier_readiness(s)
        rows.append({"Supplier ID": s["supplier_id"], "Supplier Code": s["supplier_code"], "Supplier Name": s["supplier_name"], "Can I Buy?": buy, "Readiness": score, "Reasons": "; ".join(reasons), "Email": s["supplier_email"], "Category": s["category"], "Owner": s["owner"], "Approval Status": s["approval_status"], "Risk": s["risk_level"], "Spend": s["annual_spend"] or 0, "Missing Docs": missing, "Needs Review": needs_review, "Expired Docs": expired, "Expiring Soon": expiring, "Next Review": s["next_review_date"]})
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


def load_demo_data():
    rows = [
        ("SUP001", "ABC Transport Ltd", "accounts@abctransport.co.uk", "Transport", "Connor", "Approved", "Medium", 85000, "Important"),
        ("SUP002", "Yorkshire Board Supplies", "quality@yorkshireboard.co.uk", "Manufacturing", "Quality", "Approved", "High", 120000, "Critical"),
        ("SUP003", "Fast Fix Maintenance", "fastfix@gmail.com", "Contractor", "Maintenance", "Pending", "Medium", 14000, "Standard"),
        ("SUP004", "CloudOps Software", "security@cloudops.co.uk", "IT / Software", "IT", "On Hold", "High", 42000, "Important"),
        ("SUP005", "LabelCo Print Ltd", "hello@labelco.co.uk", "Packaging", "Procurement", "Approved", "Low", 22000, "Standard"),
    ]
    many_sql("INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, criticality) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def today_screen():
    hero("Today in SupplierPass", "Your daily queue: process uploaded documents, chase evidence and fix supplier gaps.")
    suppliers = supplier_table()
    gaps = evidence_gaps()
    docs_to_review = df_sql("SELECT * FROM supplier_documents WHERE review_status IN ('Uploaded', 'Under Review')")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Suppliers", len(suppliers), "in register")
    with c2: kpi("Documents to process", len(docs_to_review), "waiting review")
    with c3: kpi("Evidence gaps", len(gaps), "open actions")
    with c4: kpi("Do Not Use", len(suppliers[suppliers["Can I Buy?"] == "Do Not Use"]) if not suppliers.empty else 0, "blocked")
    if suppliers.empty:
        st.warning("No suppliers loaded yet.")
        if st.button("Load demo data"):
            load_demo_data()
            st.success("Demo data loaded.")
            st.rerun()
    if not docs_to_review.empty:
        st.info("Next step: go to Document Processing and accept/reject uploaded documents.")
    elif not gaps.empty:
        st.info("Next step: review evidence gaps below.")
    else:
        st.success("No immediate actions found.")
    show_df(gaps, "No evidence gaps found.")


def suppliers_screen():
    hero("Supplier Register", "Import suppliers, view readiness and update supplier details.")
    tab_import, tab_register, tab_profile = st.tabs(["Import", "Register", "Profile"])
    with tab_import:
        file = st.file_uploader("Supplier CSV", type=["csv"])
        if file:
            data = pd.read_csv(file)
            st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            cols = data.columns.tolist()
            c1, c2, c3 = st.columns(3)
            c_name = c1.selectbox("Supplier Name *", cols)
            c_code = c1.selectbox("Supplier Code", [""] + cols)
            c_email = c1.selectbox("Email", [""] + cols)
            c_cat = c2.selectbox("Category", [""] + cols)
            c_owner = c2.selectbox("Owner", [""] + cols)
            c_status = c2.selectbox("Status", [""] + cols)
            c_spend = c3.selectbox("Annual Spend", [""] + cols)
            default_cat = c3.selectbox("Default category", [""] + categories())
            if st.button("Import suppliers", type="primary"):
                rows = []
                for _, r in data.iterrows():
                    name = str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not name: continue
                    try: spend = float(r[c_spend]) if c_spend and pd.notna(r[c_spend]) else 0
                    except Exception: spend = 0
                    rows.append((str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else "", name, str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "", str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else default_cat, str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "", str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Pending", "Medium", spend))
                many_sql("INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
                st.success(f"Imported {len(rows)} suppliers.")
                st.rerun()
    with tab_register:
        show_df(supplier_table(), "No suppliers yet.")
    with tab_profile:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers yet.")
            return
        options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
        supplier_id = options[st.selectbox("Supplier", list(options.keys()))]
        supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).iloc[0]
        score, buy, reasons, *_ = supplier_readiness(supplier)
        c1, c2, c3 = st.columns(3)
        with c1: kpi("Can I Buy?", buy, "; ".join(reasons) or "No blocking issues")
        with c2: kpi("Readiness", f"{score}%", "supplier score")
        with c3: kpi("Category", supplier["category"] or "Not set", "document rules")
        with st.form("edit_supplier"):
            a, b, c = st.columns(3)
            name = a.text_input("Name", supplier["supplier_name"])
            email = a.text_input("Email", supplier["supplier_email"] or "")
            category_options = [""] + categories()
            category = b.selectbox("Category", category_options, index=category_options.index(supplier["category"] or "") if (supplier["category"] or "") in category_options else 0)
            owner = b.text_input("Owner", supplier["owner"] or "")
            status = b.selectbox("Status", SUPPLIER_STATUSES, index=SUPPLIER_STATUSES.index(supplier["approval_status"]) if supplier["approval_status"] in SUPPLIER_STATUSES else 0)
            risk = c.selectbox("Risk", RISK_LEVELS, index=RISK_LEVELS.index(supplier["risk_level"]) if supplier["risk_level"] in RISK_LEVELS else 1)
            spend = c.number_input("Spend", value=float(supplier["annual_spend"] or 0), min_value=0.0, step=100.0)
            if st.form_submit_button("Save supplier"):
                exec_sql("UPDATE suppliers SET supplier_name=?, supplier_email=?, category=?, owner=?, approval_status=?, risk_level=?, annual_spend=?, updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?", (name, email, category, owner, status, risk, spend, supplier_id))
                add_timeline(supplier_id, "Supplier updated", f"Status {status}, risk {risk}", owner)
                st.success("Saved")
                st.rerun()
        st.subheader("Checklist")
        show_df(supplier_checklist(supplier), "No document rules configured for this supplier category.")
        st.subheader("Timeline")
        show_df(df_sql("SELECT * FROM supplier_timeline WHERE supplier_id=? ORDER BY created_at DESC", (supplier_id,)), "No timeline events yet.")


def upload_document_screen():
    hero("Upload Document", "Upload files against a supplier. Uploading stores the file; processing accepts it as evidence.")
    hint("After upload, go to Document Processing. A file does not improve supplier readiness until it is marked Accepted.")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.info("Add/import suppliers first.")
        return
    options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
    supplier_id = options[st.selectbox("Supplier", list(options.keys()))]
    supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).iloc[0]
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (supplier["category"] or "",))
    doc_types = rules["document_type"].tolist() if not rules.empty else []
    with st.form("upload_doc"):
        choice = st.selectbox("Document type", doc_types + ["Other"])
        other = st.text_input("Other document type") if choice == "Other" else ""
        expiry = st.date_input("Expiry date", value=None)
        upload = st.file_uploader("Document")
        notes = st.text_area("Notes")
        if st.form_submit_button("Upload document", type="primary"):
            doc_type = other.strip() if choice == "Other" else choice
            if not upload or not doc_type:
                st.error("Choose a file and document type.")
                return
            folder = UPLOAD_DIR / str(supplier_id)
            folder.mkdir(exist_ok=True)
            file_path = folder / upload.name
            file_path.write_bytes(upload.getbuffer())
            exec_sql("INSERT INTO supplier_documents (supplier_id, document_type, file_name, file_path, expiry_date, notes, review_status) VALUES (?, ?, ?, ?, ?, ?, 'Uploaded')", (supplier_id, doc_type, upload.name, str(file_path), expiry.isoformat() if expiry else None, notes))
            add_timeline(supplier_id, "Document uploaded", doc_type, "")
            st.success("Document uploaded. It is now waiting in Document Processing.")
    st.subheader("Documents for this supplier")
    show_df(df_sql("SELECT * FROM supplier_documents WHERE supplier_id=? ORDER BY uploaded_at DESC", (supplier_id,)), "No documents for this supplier yet.")


def document_processing_screen():
    hero("Document Processing", "Review uploaded files and decide whether they count as accepted supplier evidence.")
    hint("If an old document is linked to a missing supplier, it will appear as Unlinked rather than crashing. Reassign it or archive it.")
    docs = df_sql("""
        SELECT d.*, COALESCE(s.supplier_name, 'Unlinked document') AS supplier_name, s.category AS supplier_category
        FROM supplier_documents d
        LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
        WHERE COALESCE(d.review_status, 'Uploaded') != 'Archived / Ignore'
        ORDER BY CASE WHEN d.review_status IN ('Uploaded','Under Review') THEN 0 ELSE 1 END, d.uploaded_at DESC
    """)
    if docs.empty:
        st.info("No documents uploaded yet.")
        return
    show_df(docs[["document_id", "supplier_id", "supplier_name", "supplier_category", "document_type", "file_name", "expiry_date", "review_status", "uploaded_at"]])
    options = {f"{r['supplier_name']} - {r['document_type']} - {r['file_name']} ({r['document_id']})": int(r["document_id"]) for _, r in docs.iterrows()}
    document_id = options[st.selectbox("Select document to process", list(options.keys()))]
    doc_df = docs[docs["document_id"] == document_id]
    if doc_df.empty:
        st.error("Selected document could not be found. Refresh and try again.")
        return
    doc = doc_df.iloc[0]
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    supplier_options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
    current_supplier_key = None
    for key, val in supplier_options.items():
        if val == doc["supplier_id"]:
            current_supplier_key = key
            break
    if current_supplier_key is None and supplier_options:
        current_supplier_key = list(supplier_options.keys())[0]
    if suppliers.empty:
        st.error("There are no suppliers to assign this document to. Add/import a supplier first.")
        return
    assigned_supplier_key = st.selectbox("Assigned supplier", list(supplier_options.keys()), index=list(supplier_options.keys()).index(current_supplier_key))
    assigned_supplier_id = supplier_options[assigned_supplier_key]
    assigned_supplier = suppliers[suppliers["supplier_id"] == assigned_supplier_id].iloc[0]
    rules = df_sql("SELECT * FROM document_rules WHERE category=? ORDER BY is_critical DESC, document_type", (assigned_supplier["category"] or "",))
    doc_types = rules["document_type"].tolist() if not rules.empty else []
    if doc["document_type"] not in doc_types:
        doc_types = [doc["document_type"]] + doc_types
    doc_types = list(dict.fromkeys(doc_types + ["Other"]))
    with st.form("process_doc"):
        confirmed_type = st.selectbox("Confirmed document type", doc_types, index=doc_types.index(doc["document_type"]) if doc["document_type"] in doc_types else 0)
        other = st.text_input("Other document type") if confirmed_type == "Other" else ""
        expiry = st.date_input("Confirmed expiry date", value=parse_date(doc["expiry_date"]))
        review_status = st.selectbox("Review decision", DOC_REVIEW_STATUSES, index=DOC_REVIEW_STATUSES.index(doc["review_status"]) if doc["review_status"] in DOC_REVIEW_STATUSES else 0)
        reviewed_by = st.text_input("Reviewed by", value=doc["reviewed_by"] or "")
        review_notes = st.text_area("Review notes", value=doc["review_notes"] or "")
        if st.form_submit_button("Save review decision", type="primary"):
            final_type = other.strip() if confirmed_type == "Other" else confirmed_type
            if not final_type:
                st.error("Document type is required.")
                return
            exec_sql("""
                UPDATE supplier_documents
                SET supplier_id=?, document_type=?, expiry_date=?, review_status=?, reviewed_by=?, review_notes=?, reviewed_at=CURRENT_TIMESTAMP
                WHERE document_id=?
            """, (assigned_supplier_id, final_type, expiry.isoformat() if expiry else None, review_status, reviewed_by, review_notes, document_id))
            add_timeline(assigned_supplier_id, f"Document {review_status}", final_type, reviewed_by)
            st.success("Document updated. Supplier readiness has been recalculated.")
            st.rerun()
    st.subheader("Checklist after this decision")
    show_df(supplier_checklist(assigned_supplier), "No document rules configured for this supplier category.")


def risk_screen():
    hero("Risk & Compliance", "Evidence gaps, document rules and issue log.")
    tab_gaps, tab_rules, tab_issues = st.tabs(["Evidence Gaps", "Document Rules", "Issue Log"])
    with tab_gaps:
        show_df(evidence_gaps(), "No evidence gaps.")
    with tab_rules:
        show_df(df_sql("SELECT * FROM document_rules ORDER BY category, is_critical DESC, document_type"), "No document rules yet.")
        with st.form("add_rule"):
            a, b, c = st.columns(3)
            category = a.text_input("Category")
            doc_type = b.text_input("Document type")
            critical = b.checkbox("Critical", value=True)
            warning_days = c.number_input("Warning days", min_value=0, value=60)
            if st.form_submit_button("Add rule"):
                if not category or not doc_type:
                    st.error("Category and document type are required.")
                else:
                    try:
                        exec_sql("INSERT INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)", (category, doc_type, int(critical), int(warning_days)))
                        st.success("Rule added")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.warning("That rule already exists.")
    with tab_issues:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers")
            return
        with st.form("issue"):
            options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            supplier_id = options[st.selectbox("Supplier", list(options.keys()))]
            issue_type = st.selectbox("Issue type", ["Quality", "Delivery", "Pricing", "Service", "Compliance", "Finance", "Other"])
            severity = st.selectbox("Severity", ["Low", "Medium", "High", "Critical"])
            status = st.selectbox("Status", ["Open", "In Progress", "Resolved", "Closed"])
            owner = st.text_input("Owner")
            description = st.text_area("Description")
            resolution = st.text_area("Resolution")
            if st.form_submit_button("Save issue"):
                exec_sql("INSERT INTO supplier_issues (supplier_id, issue_type, severity, status, owner, description, resolution) VALUES (?, ?, ?, ?, ?, ?, ?)", (supplier_id, issue_type, severity, status, owner, description, resolution))
                add_timeline(supplier_id, "Issue logged", f"{issue_type}: {severity}", owner)
                st.success("Issue saved")
        show_df(df_sql("SELECT i.*, s.supplier_name FROM supplier_issues i JOIN suppliers s ON i.supplier_id=s.supplier_id ORDER BY i.created_at DESC"), "No supplier issues yet.")


def onboarding_screen():
    hero("Onboarding Wizard", "Create a new supplier request with the minimum information needed.")
    with st.form("new_request"):
        a, b = st.columns(2)
        name = a.text_input("Supplier name *")
        email = a.text_input("Supplier email")
        category = b.selectbox("Category", [""] + categories())
        spend = b.number_input("Expected spend", min_value=0.0, step=100.0)
        requested_by = b.text_input("Requested by")
        reason = st.text_area("Why is the supplier needed?")
        if st.form_submit_button("Create request", type="primary"):
            if not name:
                st.error("Supplier name is required")
            else:
                exec_sql("INSERT INTO new_supplier_requests (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, status) VALUES (?, ?, ?, ?, ?, ?, 'Draft')", (name, email, requested_by, category, reason, spend))
                st.success("Request created")
    show_df(df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"), "No supplier requests yet.")


def reports_screen():
    hero("Audit Pack & Value Tracker", "Download supplier readiness, evidence and risk reports.")
    score = 100
    gaps = evidence_gaps()
    if not gaps.empty:
        score -= min(50, len(gaps) * 4)
    score = max(0, score)
    c1, c2, c3 = st.columns(3)
    with c1: kpi("Audit readiness", f"{score}%", "based on open gaps")
    with c2: kpi("Suppliers", len(supplier_table()), "records")
    with c3: kpi("Evidence gaps", len(gaps), "open")
    show_df(gaps, "No evidence gaps.")
    xlsx = DATA_DIR / f"supplierpass_v10_audit_{date.today().isoformat()}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        supplier_table().to_excel(writer, index=False, sheet_name="Readiness")
        df_sql("SELECT * FROM suppliers").to_excel(writer, index=False, sheet_name="Suppliers")
        evidence_gaps().to_excel(writer, index=False, sheet_name="Evidence Gaps")
        df_sql("SELECT * FROM supplier_documents").to_excel(writer, index=False, sheet_name="Documents")
        df_sql("SELECT * FROM supplier_issues").to_excel(writer, index=False, sheet_name="Issues")
        df_sql("SELECT * FROM supplier_timeline").to_excel(writer, index=False, sheet_name="Timeline")
        df_sql("SELECT * FROM new_supplier_requests").to_excel(writer, index=False, sheet_name="Requests")
    with open(xlsx, "rb") as f:
        st.download_button("Download audit pack", f, file_name=xlsx.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def admin_screen():
    hero("Admin", "Demo mode and database helpers.")
    if st.button("Load demo data"):
        load_demo_data()
        st.success("Demo data loaded")
        st.rerun()
    st.subheader("Database health")
    suppliers = df_sql("SELECT * FROM suppliers")
    docs = df_sql("SELECT * FROM supplier_documents")
    if docs.empty:
        st.info("No documents stored.")
    else:
        linked = df_sql("""
            SELECT d.document_id, d.supplier_id, d.file_name, s.supplier_name
            FROM supplier_documents d
            LEFT JOIN suppliers s ON d.supplier_id=s.supplier_id
            WHERE s.supplier_id IS NULL
        """)
        if linked.empty:
            st.success("No orphaned/unlinked documents found.")
        else:
            st.warning("Some documents are linked to missing suppliers. Use Document Processing to reassign or archive them.")
            show_df(linked)
    st.warning("Prototype only. Production still needs authentication, tenant separation, secure storage, backups, licensing and support tooling.")


init_db()
apply_style()
st.sidebar.markdown("# SupplierPass")
st.sidebar.caption(APP_VERSION)
page = st.sidebar.radio("Navigation", ["Today", "Suppliers", "Upload Document", "Document Processing", "Risk & Compliance", "Onboarding", "Reports", "Admin"])

if page == "Today":
    today_screen()
elif page == "Suppliers":
    suppliers_screen()
elif page == "Upload Document":
    upload_document_screen()
elif page == "Document Processing":
    document_processing_screen()
elif page == "Risk & Compliance":
    risk_screen()
elif page == "Onboarding":
    onboarding_screen()
elif page == "Reports":
    reports_screen()
elif page == "Admin":
    admin_screen()
