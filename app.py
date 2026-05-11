import os
import sqlite3
from datetime import date, datetime
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


def df_sql(sql, params=()):
    c = conn()
    df = pd.read_sql_query(sql, c, params=params)
    c.close()
    return df


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
            approval_status TEXT DEFAULT 'Approved',
            risk_level TEXT DEFAULT 'Medium',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            supplier_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT,
            file_path TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            review_status TEXT DEFAULT 'Pending Review',
            reviewed_by TEXT,
            review_notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            procurement_notes TEXT,
            quality_notes TEXT,
            finance_notes TEXT,
            approval_notes TEXT,
            target_approval_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chase_log (
            chase_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            request_id INTEGER,
            document_type TEXT,
            chase_date TEXT DEFAULT CURRENT_TIMESTAMP,
            chase_method TEXT DEFAULT 'Email',
            notes TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            request_id INTEGER,
            action TEXT,
            detail TEXT,
            user TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.commit()

    defaults = [
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
        ("Agency Labour", "Public Liability Insurance", 1, 60),
        ("Agency Labour", "Modern Slavery Statement", 1, 365),
        ("Agency Labour", "Contract", 1, 365),
        ("IT / Software", "Cyber Security Questionnaire", 1, 365),
        ("IT / Software", "Data Processing Agreement", 1, 365),
        ("IT / Software", "Professional Indemnity Insurance", 1, 60),
        ("Packaging", "ISO 9001 Certificate", 1, 60),
        ("Packaging", "FSC / PEFC Certificate", 0, 60),
        ("Packaging", "Public Liability Insurance", 1, 60),
        ("Service", "Public Liability Insurance", 1, 60),
        ("Service", "Contract / Terms", 0, 365),
    ]
    for row in defaults:
        cur.execute("""
            INSERT OR IGNORE INTO document_requirements
            (category, document_type, is_critical, warning_days)
            VALUES (?, ?, ?, ?)
        """, row)
    c.commit()
    c.close()


def parse_date(v):
    if v is None or v == "" or pd.isna(v):
        return None
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def days_left(v):
    d = parse_date(v)
    if d is None:
        return None
    return (d - date.today()).days


def doc_status(expiry_date, warning_days=60, missing=False, critical=True):
    if missing:
        return "Red" if critical else "Amber"
    d = days_left(expiry_date)
    if d is None:
        return "Amber"
    if d < 0:
        return "Red"
    if d <= int(warning_days or 60):
        return "Amber"
    return "Green"


def badge(status):
    return {"Green": "🟢 Green", "Amber": "🟠 Amber", "Red": "🔴 Red"}.get(status, "⚪ Unknown")


def categories():
    df = df_sql("""
        SELECT DISTINCT category FROM document_requirements
        UNION SELECT DISTINCT category FROM suppliers
        UNION SELECT DISTINCT category FROM new_supplier_requests
        ORDER BY category
    """)
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def reqs_for(category):
    return df_sql("SELECT * FROM document_requirements WHERE category = ? ORDER BY is_critical DESC, document_type", (category or "",))


def docs_for(supplier_id):
    return df_sql("SELECT * FROM supplier_documents WHERE supplier_id = ? ORDER BY document_type, expiry_date", (supplier_id,))


def supplier_checklist(supplier_id, category):
    reqs = reqs_for(category)
    docs = docs_for(supplier_id)
    rows = []

    for _, req in reqs.iterrows():
        doc_type = req["document_type"]
        matching = docs[docs["document_type"] == doc_type].copy()
        if matching.empty:
            rows.append({
                "Document Type": doc_type,
                "Required": "Yes" if req["is_critical"] else "Optional",
                "Status": doc_status(None, req["warning_days"], True, bool(req["is_critical"])),
                "Expiry Date": "",
                "Days Left": "",
                "File": "",
                "Issue": "Missing document",
            })
        else:
            matching["_days"] = matching["expiry_date"].apply(lambda x: days_left(x) if days_left(x) is not None else 999999)
            latest = matching.sort_values(["_days", "uploaded_at"], ascending=[False, False]).iloc[0]
            status = doc_status(latest["expiry_date"], req["warning_days"], False, bool(req["is_critical"]))
            issue = ""
            if status == "Red":
                issue = "Expired document"
            elif status == "Amber":
                issue = "Expiring soon / needs review"
            rows.append({
                "Document Type": doc_type,
                "Required": "Yes" if req["is_critical"] else "Optional",
                "Status": status,
                "Expiry Date": latest["expiry_date"] or "",
                "Days Left": days_left(latest["expiry_date"]) if days_left(latest["expiry_date"]) is not None else "",
                "File": latest["file_name"] or "",
                "Issue": issue,
            })

    required_types = set(reqs["document_type"].tolist()) if not reqs.empty else set()
    for _, doc in docs.iterrows():
        if doc["document_type"] not in required_types:
            rows.append({
                "Document Type": doc["document_type"],
                "Required": "No",
                "Status": doc_status(doc["expiry_date"], 60, False, False),
                "Expiry Date": doc["expiry_date"] or "",
                "Days Left": days_left(doc["expiry_date"]) if days_left(doc["expiry_date"]) is not None else "",
                "File": doc["file_name"] or "",
                "Issue": "Additional document",
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out, "Amber"
    if "Red" in out["Status"].values:
        return out, "Red"
    if "Amber" in out["Status"].values:
        return out, "Amber"
    return out, "Green"


def supplier_statuses():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    for _, s in suppliers.iterrows():
        checklist, overall = supplier_checklist(s["supplier_id"], s["category"] or "")
        missing = expiring = expired = 0
        next_expiry = ""
        actions = ""
        if not checklist.empty:
            missing = int((checklist["Issue"] == "Missing document").sum())
            expiring = int((checklist["Issue"] == "Expiring soon / needs review").sum())
            expired = int((checklist["Issue"] == "Expired document").sum())
            date_values = [parse_date(x) for x in checklist["Expiry Date"].tolist() if parse_date(x)]
            next_expiry = min(date_values).isoformat() if date_values else ""
            actions = ", ".join(checklist[checklist["Status"].isin(["Red", "Amber"] )]["Document Type"].head(3).tolist())
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
            "Expired": expired,
            "Next Expiry": next_expiry,
            "Action Needed": actions,
            "Notes": s["notes"],
        })
    return pd.DataFrame(rows)


def save_file(upload, supplier_id, document_type):
    folder = UPLOAD_DIR / str(supplier_id)
    folder.mkdir(exist_ok=True)
    name = upload.name.replace("/", "_").replace("\\", "_")
    path = folder / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document_type.replace('/', '-')}_{name}"
    with open(path, "wb") as f:
        f.write(upload.getbuffer())
    return name, str(path)


def log_audit(supplier_id=None, request_id=None, action="", detail="", user=""):
    exec_sql("INSERT INTO audit_log (supplier_id, request_id, action, detail, user) VALUES (?, ?, ?, ?, ?)", (supplier_id, request_id, action, detail, user))


init_db()

st.sidebar.title("SupplierPass")
st.sidebar.caption("v0.1 internal prototype")
page = st.sidebar.radio("Navigation", ["Dashboard", "Suppliers", "Documents", "New Supplier Requests", "Actions", "Settings", "Exports"])
st.sidebar.caption(f"Database: {DB_PATH.name}")

if page == "Dashboard":
    st.title("SupplierPass Dashboard")
    st.caption("Supplier compliance, document expiry and onboarding overview.")
    statuses = supplier_statuses()
    requests = df_sql("SELECT * FROM new_supplier_requests")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Suppliers", len(statuses))
    c2.metric("Green", int((statuses["Compliance"] == "Green").sum()) if not statuses.empty else 0)
    c3.metric("Amber", int((statuses["Compliance"] == "Amber").sum()) if not statuses.empty else 0)
    c4.metric("Red", int((statuses["Compliance"] == "Red").sum()) if not statuses.empty else 0)
    c5.metric("Open Requests", int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0)
    st.divider()
    st.subheader("Suppliers Needing Attention")
    if statuses.empty:
        st.info("No suppliers loaded yet. Import a CSV or add suppliers manually.")
    else:
        attention = statuses[(statuses["Compliance"].isin(["Red", "Amber"])) | (statuses["Approval Status"].isin(["Pending", "Blocked", "On Hold"]))].copy()
        if attention.empty:
            st.success("No current compliance issues found.")
        else:
            attention["Compliance"] = attention["Compliance"].apply(badge)
            st.dataframe(attention, use_container_width=True, hide_index=True)

elif page == "Suppliers":
    st.title("Suppliers")
    tab1, tab2, tab3 = st.tabs(["Supplier List", "Add Supplier", "CSV Import"])

    with tab1:
        statuses = supplier_statuses()
        if statuses.empty:
            st.info("No suppliers found.")
        else:
            col1, col2, col3 = st.columns(3)
            cats = col1.multiselect("Category", sorted(statuses["Category"].dropna().unique().tolist()))
            comps = col2.multiselect("Compliance", ["Green", "Amber", "Red"])
            apps = col3.multiselect("Approval", sorted(statuses["Approval Status"].dropna().unique().tolist()))
            view = statuses.copy()
            if cats:
                view = view[view["Category"].isin(cats)]
            if comps:
                view = view[view["Compliance"].isin(comps)]
            if apps:
                view = view[view["Approval Status"].isin(apps)]
            show = view.copy()
            show["Compliance"] = show["Compliance"].apply(badge)
            st.dataframe(show, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Supplier Profile")
            opts = {f"{r['Supplier Name']} ({r['Supplier ID']})": int(r["Supplier ID"]) for _, r in statuses.iterrows()}
            sid = opts[st.selectbox("Select supplier", list(opts.keys()))]
            s = df_sql("SELECT * FROM suppliers WHERE supplier_id = ?", (sid,)).iloc[0]
            checklist, overall = supplier_checklist(sid, s["category"] or "")
            m1, m2, m3 = st.columns(3)
            m1.metric("Approval", s["approval_status"])
            m2.metric("Compliance", badge(overall))
            m3.metric("Category", s["category"] or "Uncategorised")

            with st.expander("Edit Supplier"):
                with st.form(f"edit_{sid}"):
                    supplier_code = st.text_input("Supplier Code", s["supplier_code"] or "")
                    supplier_name = st.text_input("Supplier Name", s["supplier_name"] or "")
                    supplier_email = st.text_input("Supplier Email", s["supplier_email"] or "")
                    category_list = sorted(set(categories() + [s["category"] or ""]))
                    category = st.selectbox("Category", category_list, index=category_list.index(s["category"] or "") if (s["category"] or "") in category_list else 0)
                    owner = st.text_input("Owner", s["owner"] or "")
                    approval = st.selectbox("Approval Status", ["Approved", "Pending", "Blocked", "Dormant", "On Hold"], index=["Approved", "Pending", "Blocked", "Dormant", "On Hold"].index(s["approval_status"]) if s["approval_status"] in ["Approved", "Pending", "Blocked", "Dormant", "On Hold"] else 0)
                    risk = st.selectbox("Risk Level", ["Low", "Medium", "High", "Critical"], index=["Low", "Medium", "High", "Critical"].index(s["risk_level"]) if s["risk_level"] in ["Low", "Medium", "High", "Critical"] else 1)
                    notes = st.text_area("Notes", s["notes"] or "")
                    if st.form_submit_button("Save"):
                        exec_sql("""UPDATE suppliers SET supplier_code=?, supplier_name=?, supplier_email=?, category=?, owner=?, approval_status=?, risk_level=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?""", (supplier_code, supplier_name, supplier_email, category, owner, approval, risk, notes, sid))
                        log_audit(supplier_id=sid, action="Supplier updated", user=owner)
                        st.success("Supplier updated.")
                        st.rerun()

            st.subheader("Compliance Checklist")
            if checklist.empty:
                st.warning("No document rules configured for this category.")
            else:
                out = checklist.copy()
                out["Status"] = out["Status"].apply(badge)
                st.dataframe(out, use_container_width=True, hide_index=True)

            st.subheader("Upload Document")
            reqs = reqs_for(s["category"] or "")
            doc_options = reqs["document_type"].tolist() if not reqs.empty else []
            doc_options += ["Other"]
            with st.form(f"upload_{sid}", clear_on_submit=True):
                doc_choice = st.selectbox("Document Type", doc_options)
                custom = st.text_input("Custom Document Type") if doc_choice == "Other" else ""
                issue = st.date_input("Issue Date", value=None)
                expiry = st.date_input("Expiry Date", value=None)
                reviewed_by = st.text_input("Reviewed By")
                review_notes = st.text_area("Review Notes")
                upload = st.file_uploader("Upload file")
                if st.form_submit_button("Save Document"):
                    if not upload:
                        st.error("Please choose a file.")
                    else:
                        dtype = custom.strip() if doc_choice == "Other" else doc_choice
                        fname, fpath = save_file(upload, sid, dtype)
                        exec_sql("""INSERT INTO supplier_documents (supplier_id, document_type, file_name, file_path, issue_date, expiry_date, review_status, reviewed_by, review_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (sid, dtype, fname, fpath, issue.isoformat() if issue else None, expiry.isoformat() if expiry else None, "Reviewed" if reviewed_by else "Pending Review", reviewed_by, review_notes))
                        log_audit(supplier_id=sid, action="Document uploaded", detail=dtype, user=reviewed_by)
                        st.success("Document saved.")
                        st.rerun()

            st.subheader("Uploaded Documents")
            docs = docs_for(sid)
            if docs.empty:
                st.info("No documents uploaded yet.")
            else:
                st.dataframe(docs, use_container_width=True, hide_index=True)

    with tab2:
        with st.form("add_supplier"):
            supplier_code = st.text_input("Supplier Code")
            supplier_name = st.text_input("Supplier Name *")
            supplier_email = st.text_input("Supplier Email")
            category = st.selectbox("Category", [""] + categories())
            owner = st.text_input("Owner")
            approval = st.selectbox("Approval Status", ["Approved", "Pending", "Blocked", "Dormant", "On Hold"])
            risk = st.selectbox("Risk Level", ["Low", "Medium", "High", "Critical"], index=1)
            notes = st.text_area("Notes")
            if st.form_submit_button("Add Supplier"):
                if not supplier_name.strip():
                    st.error("Supplier name is required.")
                else:
                    sid = exec_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (supplier_code, supplier_name, supplier_email, category, owner, approval, risk, notes))
                    log_audit(supplier_id=sid, action="Supplier created", user=owner)
                    st.success("Supplier added.")

    with tab3:
        st.write("Upload a CSV with supplier columns. You can map the columns before importing.")
        st.code("SupplierCode,SupplierName,SupplierEmail,Category,Owner,ApprovalStatus,Notes")
        file = st.file_uploader("Supplier CSV", type=["csv"])
        if file:
            import_df = pd.read_csv(file)
            st.dataframe(import_df.head(20), use_container_width=True)
            cols = import_df.columns.tolist()
            c_code = st.selectbox("Supplier Code column", [""] + cols)
            c_name = st.selectbox("Supplier Name column", cols)
            c_email = st.selectbox("Supplier Email column", [""] + cols)
            c_cat = st.selectbox("Category column", [""] + cols)
            c_owner = st.selectbox("Owner column", [""] + cols)
            c_status = st.selectbox("Approval Status column", [""] + cols)
            c_notes = st.selectbox("Notes column", [""] + cols)
            if st.button("Import Suppliers"):
                count = 0
                for _, r in import_df.iterrows():
                    name = str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not name:
                        continue
                    exec_sql("""INSERT INTO suppliers (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                        str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else "",
                        name,
                        str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "",
                        str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else "",
                        str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "",
                        str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved",
                        "Medium",
                        str(r[c_notes]).strip() if c_notes and pd.notna(r[c_notes]) else "",
                    ))
                    count += 1
                st.success(f"Imported {count} suppliers.")

elif page == "Documents":
    st.title("Documents")
    docs = df_sql("""
        SELECT d.document_id, s.supplier_name, s.category, d.document_type, d.file_name, d.issue_date, d.expiry_date, d.review_status, d.reviewed_by, d.uploaded_at, d.review_notes
        FROM supplier_documents d
        JOIN suppliers s ON d.supplier_id = s.supplier_id
        ORDER BY d.expiry_date
    """)
    if docs.empty:
        st.info("No documents uploaded yet.")
    else:
        docs["Days Left"] = docs["expiry_date"].apply(days_left)
        docs["Status"] = docs["expiry_date"].apply(lambda x: doc_status(x, 60))
        docs["Status"] = docs["Status"].apply(badge)
        st.dataframe(docs, use_container_width=True, hide_index=True)

elif page == "New Supplier Requests":
    st.title("New Supplier Requests")
    tab1, tab2 = st.tabs(["Request List", "Create Request"])
    with tab1:
        reqs = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
        if reqs.empty:
            st.info("No new supplier requests yet.")
        else:
            st.dataframe(reqs, use_container_width=True, hide_index=True)
            opts = {f"{r['supplier_name']} ({r['request_id']})": int(r["request_id"]) for _, r in reqs.iterrows()}
            rid = opts[st.selectbox("Select request", list(opts.keys()))]
            req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id = ?", (rid,)).iloc[0]
            st.subheader(req["supplier_name"])
            st.write(req["reason_needed"] or "")
            st.write("Required documents")
            st.dataframe(reqs_for(req["category"] or ""), use_container_width=True, hide_index=True)
            with st.form(f"req_{rid}"):
                status = st.selectbox("Status", ["Draft", "Awaiting Supplier Info", "Awaiting Procurement Review", "Awaiting Quality Review", "Awaiting Finance Review", "Approved", "Rejected", "On Hold"], index=["Draft", "Awaiting Supplier Info", "Awaiting Procurement Review", "Awaiting Quality Review", "Awaiting Finance Review", "Approved", "Rejected", "On Hold"].index(req["status"]) if req["status"] in ["Draft", "Awaiting Supplier Info", "Awaiting Procurement Review", "Awaiting Quality Review", "Awaiting Finance Review", "Approved", "Rejected", "On Hold"] else 0)
                pn = st.text_area("Procurement Notes", req["procurement_notes"] or "")
                qn = st.text_area("Quality Notes", req["quality_notes"] or "")
                fn = st.text_area("Finance Notes", req["finance_notes"] or "")
                an = st.text_area("Approval Notes", req["approval_notes"] or "")
                if st.form_submit_button("Save Request"):
                    exec_sql("""UPDATE new_supplier_requests SET status=?, procurement_notes=?, quality_notes=?, finance_notes=?, approval_notes=?, updated_at=CURRENT_TIMESTAMP WHERE request_id=?""", (status, pn, qn, fn, an, rid))
                    log_audit(request_id=rid, action="Request updated", detail=status)
                    st.success("Request updated.")
                    st.rerun()
            if st.button("Generate Supplier Info Request Email"):
                req_docs = reqs_for(req["category"] or "")
                docs_text = "\n".join([f"- {x}" for x in req_docs["document_type"].tolist()]) or "- Supplier onboarding documents"
                body = f"""Hi {req['supplier_name']},

We are reviewing your setup as a new supplier.

Please could you provide the following information/documents:

{docs_text}

Please also confirm:
- Company registration number
- VAT number
- Main contact details
- Remittance email address
- Bank details on official letterhead, where applicable

Many thanks,
[Your Name]
"""
                exec_sql("INSERT INTO chase_log (request_id, notes) VALUES (?, ?)", (rid, "Generated new supplier info request"))
                st.text_input("Subject", "New supplier onboarding information request")
                st.text_area("Email Body", body, height=300)
            if req["status"] == "Approved":
                if st.button("Convert to Supplier"):
                    sid = exec_sql("""INSERT INTO suppliers (supplier_name, supplier_email, category, owner, approval_status, risk_level, notes) VALUES (?, ?, ?, ?, ?, ?, ?)""", (req["supplier_name"], req["supplier_email"], req["category"], req["requested_by"], "Approved", "Medium", f"Created from request {rid}. {req['approval_notes'] or ''}"))
                    log_audit(supplier_id=sid, request_id=rid, action="Request converted to supplier", detail=str(sid))
                    st.success("Supplier record created.")
    with tab2:
        with st.form("new_req"):
            supplier_name = st.text_input("Supplier Name *")
            supplier_email = st.text_input("Supplier Email")
            requested_by = st.text_input("Requested By")
            category = st.selectbox("Category", [""] + categories())
            reason = st.text_area("Reason Needed")
            spend = st.number_input("Expected Annual Spend", min_value=0.0, step=100.0)
            urgency = st.selectbox("Urgency", ["Low", "Normal", "High", "Critical"], index=1)
            target = st.date_input("Target Approval Date", value=None)
            if st.form_submit_button("Create Request"):
                if not supplier_name.strip():
                    st.error("Supplier name is required.")
                else:
                    rid = exec_sql("""INSERT INTO new_supplier_requests (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, target_approval_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (supplier_name, supplier_email, requested_by, category, reason, spend, urgency, target.isoformat() if target else None, "Draft"))
                    log_audit(request_id=rid, action="New supplier request created", user=requested_by)
                    st.success("Request created.")

elif page == "Actions":
    st.title("Actions")
    rows = []
    for _, s in df_sql("SELECT * FROM suppliers ORDER BY supplier_name").iterrows():
        checklist, _ = supplier_checklist(s["supplier_id"], s["category"] or "")
        if checklist.empty:
            continue
        for _, issue in checklist[checklist["Status"].isin(["Red", "Amber"])].iterrows():
            rows.append({"Supplier ID": s["supplier_id"], "Supplier Name": s["supplier_name"], "Email": s["supplier_email"], "Document Type": issue["Document Type"], "Status": issue["Status"], "Issue": issue["Issue"], "Expiry Date": issue["Expiry Date"], "Days Left": issue["Days Left"]})
    actions = pd.DataFrame(rows)
    if actions.empty:
        st.success("No document chase actions found.")
    else:
        show = actions.copy()
        show["Status"] = show["Status"].apply(badge)
        st.dataframe(show, use_container_width=True, hide_index=True)
        opts = {f"{r['Supplier Name']} - {r['Document Type']} ({r['Issue']})": i for i, r in actions.iterrows()}
        row = actions.loc[opts[st.selectbox("Select action", list(opts.keys()))]]
        subject = f"Supplier document request - {row['Document Type']}"
        body = f"""Hi {row['Supplier Name']},

We are updating our approved supplier records and need the following from you:

{row['Document Type']}

Reason: {row['Issue']}

Please could you send the latest version, including the expiry date where applicable?

Many thanks,
[Your Name]
"""
        st.text_input("To", row["Email"] or "")
        st.text_input("Subject", subject)
        st.text_area("Email Body", body, height=260)
        if st.button("Log Chase Generated"):
            exec_sql("INSERT INTO chase_log (supplier_id, document_type, notes) VALUES (?, ?, ?)", (int(row["Supplier ID"]), row["Document Type"], row["Issue"]))
            st.success("Chase logged.")
    st.subheader("Chase History")
    st.dataframe(df_sql("""SELECT c.chase_date, s.supplier_name, r.supplier_name AS request_supplier_name, c.document_type, c.chase_method, c.notes FROM chase_log c LEFT JOIN suppliers s ON c.supplier_id=s.supplier_id LEFT JOIN new_supplier_requests r ON c.request_id=r.request_id ORDER BY c.chase_date DESC"""), use_container_width=True, hide_index=True)

elif page == "Settings":
    st.title("Settings")
    st.subheader("Document Requirement Rules")
    rules = df_sql("SELECT * FROM document_requirements ORDER BY category, is_critical DESC, document_type")
    st.dataframe(rules, use_container_width=True, hide_index=True)
    with st.form("add_rule"):
        mode = st.radio("Category", ["Use existing", "Create new"], horizontal=True)
        category = st.selectbox("Existing Category", categories()) if mode == "Use existing" else st.text_input("New Category")
        doc_type = st.text_input("Document Type")
        critical = st.checkbox("Critical", value=True)
        warning = st.number_input("Warning Days", min_value=0, value=60)
        if st.form_submit_button("Add Rule"):
            if not category or not doc_type:
                st.error("Category and document type are required.")
            else:
                try:
                    exec_sql("INSERT INTO document_requirements (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)", (category, doc_type, int(critical), int(warning)))
                    st.success("Rule added.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("That rule already exists.")

elif page == "Exports":
    st.title("Exports")
    statuses = supplier_statuses()
    if statuses.empty:
        st.info("No data to export.")
    else:
        st.download_button("Download Supplier Compliance CSV", statuses.to_csv(index=False).encode("utf-8"), file_name=f"supplierpass_compliance_{date.today().isoformat()}.csv", mime="text/csv")
        path = DATA_DIR / f"supplierpass_export_{date.today().isoformat()}.xlsx"
        docs = df_sql("""SELECT s.supplier_code, s.supplier_name, s.category, d.* FROM supplier_documents d JOIN suppliers s ON d.supplier_id=s.supplier_id ORDER BY s.supplier_name, d.document_type""")
        reqs = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
        rules = df_sql("SELECT * FROM document_requirements ORDER BY category, document_type")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            statuses.to_excel(writer, index=False, sheet_name="Supplier Status")
            docs.to_excel(writer, index=False, sheet_name="Documents")
            reqs.to_excel(writer, index=False, sheet_name="New Supplier Requests")
            rules.to_excel(writer, index=False, sheet_name="Requirement Rules")
        with open(path, "rb") as f:
            st.download_button("Download Full Excel Export", f, file_name=path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
