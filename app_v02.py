import smtplib
import sqlite3
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "supplierpass.db"
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="SupplierPass v0.2", page_icon="✅", layout="wide")


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
        CREATE TABLE IF NOT EXISTS approval_stages (
            stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            approver_name TEXT NOT NULL,
            approver_email TEXT NOT NULL,
            sequence_order INTEGER NOT NULL,
            is_required INTEGER DEFAULT 1,
            UNIQUE(category, stage_name, sequence_order)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            stage_id INTEGER NOT NULL,
            decision TEXT NOT NULL,
            decided_by TEXT,
            notes TEXT,
            decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(request_id, stage_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
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
    for row in defaults:
        cur.execute("""
            INSERT OR IGNORE INTO approval_stages
            (category, stage_name, approver_name, approver_email, sequence_order, is_required)
            VALUES (?, ?, ?, ?, ?, ?)
        """, row)

    c.commit()
    c.close()


def log_audit(request_id=None, supplier_id=None, action="", detail="", user=""):
    exec_sql(
        "INSERT INTO audit_log (request_id, supplier_id, action, detail, user) VALUES (?, ?, ?, ?, ?)",
        (request_id, supplier_id, action, detail, user),
    )


def categories():
    df = df_sql("""
        SELECT DISTINCT category FROM approval_stages
        UNION SELECT DISTINCT category FROM new_supplier_requests
        UNION SELECT DISTINCT category FROM suppliers
        ORDER BY category
    """)
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def stages_for(category):
    return df_sql(
        "SELECT * FROM approval_stages WHERE category = ? AND is_required = 1 ORDER BY sequence_order",
        (category or "",),
    )


def decisions_for(request_id):
    return df_sql("""
        SELECT d.*, s.stage_name, s.sequence_order, s.approver_name, s.approver_email
        FROM approval_decisions d
        JOIN approval_stages s ON d.stage_id = s.stage_id
        WHERE d.request_id = ?
        ORDER BY s.sequence_order
    """, (request_id,))


def current_stage(request_id, category):
    stages = stages_for(category)
    decisions = decisions_for(request_id)
    approved_stage_ids = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
    if stages.empty:
        return None
    for _, stage in stages.iterrows():
        if int(stage["stage_id"]) not in approved_stage_ids:
            return stage
    return None


def smtp_configured():
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"]
    return all(k in st.secrets for k in required)


def send_email(to_email, subject, body):
    if not smtp_configured():
        return False, "SMTP is not configured in Streamlit secrets. Email preview generated only."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = st.secrets["FROM_EMAIL"]
    msg["To"] = to_email
    if "REPLY_TO_EMAIL" in st.secrets:
        msg["Reply-To"] = st.secrets["REPLY_TO_EMAIL"]
    msg.set_content(body)

    try:
        with smtplib.SMTP(st.secrets["SMTP_HOST"], int(st.secrets["SMTP_PORT"])) as server:
            server.starttls()
            server.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASSWORD"])
            server.send_message(msg)
        return True, "Sent"
    except Exception as e:
        return False, str(e)


def log_email(request_id, email_type, recipient, subject, body, status, error=""):
    exec_sql("""
        INSERT INTO email_log
        (request_id, email_type, recipient, subject, body, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (request_id, email_type, recipient, subject, body, status, error))


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
    log_email(req["request_id"], "Approval Request", stage["approver_email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
    return ok, msg, subject, body


init_db()

st.sidebar.title("SupplierPass")
st.sidebar.caption("v0.2 approval + email workflow")
page = st.sidebar.radio("Navigation", ["Dashboard", "New Supplier Requests", "Approval Stages", "Email Log", "Supplier Register", "Help"])

if page == "Dashboard":
    st.title("SupplierPass v0.2")
    st.caption("New supplier approval routing with configurable approvers and optional SMTP email sending.")

    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    emails = df_sql("SELECT * FROM email_log ORDER BY sent_at DESC")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Supplier Requests", len(requests))
    c2.metric("Approved", int((requests["status"] == "Approved").sum()) if not requests.empty else 0)
    c3.metric("Open", int((~requests["status"].isin(["Approved", "Rejected"])).sum()) if not requests.empty else 0)
    c4.metric("Suppliers", len(suppliers))

    st.info("Email mode: SMTP sending is active." if smtp_configured() else "Email mode: preview only.")

    st.subheader("Requests Awaiting Approval")
    if requests.empty:
        st.write("No requests yet.")
    else:
        open_reqs = requests[~requests["status"].isin(["Approved", "Rejected"])]
        rows = []
        for _, req in open_reqs.iterrows():
            stage = current_stage(req["request_id"], req["category"])
            rows.append({
                "Request ID": req["request_id"],
                "Supplier": req["supplier_name"],
                "Category": req["category"],
                "Status": req["status"],
                "Current Stage": stage["stage_name"] if stage is not None else "No stage configured",
                "Approver": stage["approver_name"] if stage is not None else "",
                "Approver Email": stage["approver_email"] if stage is not None else "",
                "Urgency": req["urgency"],
                "Created": req["created_at"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page == "New Supplier Requests":
    st.title("New Supplier Requests")
    tab_list, tab_create = st.tabs(["Request List / Approval", "Create Request"])

    with tab_create:
        st.subheader("Create New Supplier Request")
        with st.form("create_request"):
            supplier_name = st.text_input("Supplier Name *")
            supplier_email = st.text_input("Supplier Email")
            requested_by = st.text_input("Requested By")
            category = st.selectbox("Category", [""] + categories())
            reason = st.text_area("Reason Needed")
            spend = st.number_input("Expected Annual Spend", min_value=0.0, step=100.0)
            urgency = st.selectbox("Urgency", ["Low", "Normal", "High", "Critical"], index=1)
            target = st.date_input("Target Approval Date", value=None)
            submit_now = st.checkbox("Submit for approval immediately", value=True)

            if st.form_submit_button("Create Request"):
                if not supplier_name.strip():
                    st.error("Supplier name is required.")
                else:
                    status = "Awaiting Approval" if submit_now else "Draft"
                    rid = exec_sql("""
                        INSERT INTO new_supplier_requests
                        (supplier_name, supplier_email, requested_by, category, reason_needed,
                         expected_annual_spend, urgency, target_approval_date, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (supplier_name, supplier_email, requested_by, category, reason, spend, urgency, target.isoformat() if target else None, status))
                    log_audit(request_id=rid, action="Request created", detail=status, user=requested_by)
                    st.success(f"Request created: {supplier_name}")
                    if submit_now:
                        req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id = ?", (rid,)).iloc[0]
                        ok, msg, subject, body = notify_current_approver(req)
                        st.write(msg)
                        st.text_input("Email subject", subject)
                        st.text_area("Email body", body, height=250)

    with tab_list:
        requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
        if requests.empty:
            st.info("No requests yet.")
        else:
            st.dataframe(requests, use_container_width=True, hide_index=True)
            opts = {f"{r['supplier_name']} ({r['request_id']})": int(r["request_id"]) for _, r in requests.iterrows()}
            rid = opts[st.selectbox("Select request", list(opts.keys()))]
            req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id = ?", (rid,)).iloc[0]
            stage = current_stage(rid, req["category"])
            decisions = decisions_for(rid)

            st.subheader(req["supplier_name"])
            a, b, c = st.columns(3)
            a.metric("Status", req["status"])
            b.metric("Category", req["category"] or "")
            c.metric("Urgency", req["urgency"] or "")

            st.write("**Reason needed:**")
            st.write(req["reason_needed"] or "")

            st.subheader("Approval Route")
            route = stages_for(req["category"])
            if route.empty:
                st.warning("No approval stages configured for this category. Add them in Approval Stages.")
            else:
                approved_ids = set(decisions[decisions["decision"] == "Approved"]["stage_id"].tolist()) if not decisions.empty else set()
                route_display = route.copy()
                route_display["stage_status"] = route_display["stage_id"].apply(lambda x: "Approved" if x in approved_ids else "Pending")
                st.dataframe(route_display[["sequence_order", "stage_name", "approver_name", "approver_email", "stage_status"]], use_container_width=True, hide_index=True)

            if not decisions.empty:
                st.subheader("Approval History")
                st.dataframe(decisions, use_container_width=True, hide_index=True)

            st.subheader("Current Action")
            if req["status"] == "Draft":
                if st.button("Submit for Approval"):
                    exec_sql("UPDATE new_supplier_requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE request_id = ?", ("Awaiting Approval", rid))
                    log_audit(request_id=rid, action="Submitted for approval", user=req["requested_by"])
                    req2 = df_sql("SELECT * FROM new_supplier_requests WHERE request_id = ?", (rid,)).iloc[0]
                    ok, msg, subject, body = notify_current_approver(req2)
                    st.success("Submitted for approval.")
                    st.write(msg)
                    st.rerun()
            elif req["status"] in ["Approved", "Rejected"]:
                st.info(f"This request is already {req['status']}.")
            elif stage is None:
                st.success("All approval stages are complete.")
                if st.button("Mark Request Approved"):
                    exec_sql("UPDATE new_supplier_requests SET status = 'Approved', updated_at = CURRENT_TIMESTAMP WHERE request_id = ?", (rid,))
                    log_audit(request_id=rid, action="Request approved", user="SupplierPass")
                    st.rerun()
                if st.button("Convert to Supplier"):
                    sid = exec_sql("""
                        INSERT INTO suppliers
                        (supplier_name, supplier_email, category, owner, approval_status, risk_level, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (req["supplier_name"], req["supplier_email"], req["category"], req["requested_by"], "Approved", "Medium", f"Created from request {rid}."))
                    log_audit(request_id=rid, supplier_id=sid, action="Converted to supplier", detail=str(sid))
                    st.success("Supplier record created.")
            else:
                st.write(f"Awaiting: **{stage['stage_name']}**")
                st.write(f"Approver: **{stage['approver_name']}** <{stage['approver_email']}>")

                subject, body = approval_email(req, stage)
                with st.expander("Preview approver email", expanded=True):
                    st.text_input("To", stage["approver_email"])
                    st.text_input("Subject", subject)
                    st.text_area("Body", body, height=240)

                col1, col2, col3 = st.columns(3)
                if col1.button("Send / Log Approver Email"):
                    ok, msg = send_email(stage["approver_email"], subject, body)
                    log_email(rid, "Approval Request", stage["approver_email"], subject, body, "Sent" if ok else "Preview / Failed", "" if ok else msg)
                    st.success("Email sent." if ok else "Email preview logged; SMTP not sent.")
                    st.write(msg)

                decision_notes = st.text_area("Decision notes")
                decided_by = st.text_input("Decided by", value=stage["approver_name"])

                if col2.button("Approve Current Stage"):
                    exec_sql("""
                        INSERT OR REPLACE INTO approval_decisions
                        (request_id, stage_id, decision, decided_by, notes, decided_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (rid, int(stage["stage_id"]), "Approved", decided_by, decision_notes))
                    log_audit(request_id=rid, action="Approval stage approved", detail=stage["stage_name"], user=decided_by)

                    next_stage = current_stage(rid, req["category"])
                    if next_stage is None:
                        exec_sql("UPDATE new_supplier_requests SET status = 'Approved', updated_at = CURRENT_TIMESTAMP WHERE request_id = ?", (rid,))
                        st.success("All stages approved. Request marked Approved.")
                    else:
                        exec_sql("UPDATE new_supplier_requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE request_id = ?", (f"Awaiting {next_stage['stage_name']}", rid))
                        req2 = df_sql("SELECT * FROM new_supplier_requests WHERE request_id = ?", (rid,)).iloc[0]
                        notify_current_approver(req2)
                        st.success(f"Approved. Moved to {next_stage['stage_name']}.")
                    st.rerun()

                if col3.button("Reject Request"):
                    exec_sql("""
                        INSERT OR REPLACE INTO approval_decisions
                        (request_id, stage_id, decision, decided_by, notes, decided_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (rid, int(stage["stage_id"]), "Rejected", decided_by, decision_notes))
                    exec_sql("UPDATE new_supplier_requests SET status = 'Rejected', updated_at = CURRENT_TIMESTAMP WHERE request_id = ?", (rid,))
                    log_audit(request_id=rid, action="Request rejected", detail=stage["stage_name"], user=decided_by)
                    st.error("Request rejected.")
                    st.rerun()

elif page == "Approval Stages":
    st.title("Approval Stages")
    st.caption("Set who receives approval emails for each supplier category and stage.")

    stages = df_sql("SELECT * FROM approval_stages ORDER BY category, sequence_order")
    st.dataframe(stages, use_container_width=True, hide_index=True)

    st.subheader("Add Approval Stage")
    with st.form("add_stage"):
        mode = st.radio("Category", ["Use existing", "Create new"], horizontal=True)
        category = st.selectbox("Existing Category", categories()) if mode == "Use existing" else st.text_input("New Category")
        stage_name = st.text_input("Stage Name", placeholder="Quality Review")
        approver_name = st.text_input("Approver Name")
        approver_email = st.text_input("Approver Email")
        sequence = st.number_input("Order", min_value=1, step=1)
        required = st.checkbox("Required", value=True)
        if st.form_submit_button("Add Stage"):
            if not category or not stage_name or not approver_name or not approver_email:
                st.error("Category, stage, approver name and approver email are required.")
            else:
                try:
                    exec_sql("""
                        INSERT INTO approval_stages
                        (category, stage_name, approver_name, approver_email, sequence_order, is_required)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (category, stage_name, approver_name, approver_email, int(sequence), int(required)))
                    st.success("Approval stage added.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("That approval stage already exists.")

    st.subheader("Disable Stage")
    if not stages.empty:
        opts = {f"{r['category']} | {r['sequence_order']} | {r['stage_name']} | {r['approver_email']}": int(r["stage_id"]) for _, r in stages.iterrows()}
        sid = opts[st.selectbox("Select stage", list(opts.keys()))]
        if st.button("Disable Selected Stage"):
            exec_sql("UPDATE approval_stages SET is_required = 0 WHERE stage_id = ?", (sid,))
            st.success("Stage disabled.")
            st.rerun()

elif page == "Email Log":
    st.title("Email Log")
    emails = df_sql("SELECT * FROM email_log ORDER BY sent_at DESC")
    if emails.empty:
        st.info("No emails logged yet.")
    else:
        st.dataframe(emails, use_container_width=True, hide_index=True)

elif page == "Supplier Register":
    st.title("Supplier Register")
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        st.info("No suppliers converted yet.")
    else:
        st.dataframe(suppliers, use_container_width=True, hide_index=True)

elif page == "Help":
    st.title("Email Setup Help")
    st.write("This version can either preview/log emails or send via SMTP if Streamlit secrets are configured.")
    st.code('''SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "supplierpass@yourcompany.co.uk"
SMTP_PASSWORD = "your-password-or-app-password"
FROM_EMAIL = "supplierpass@yourcompany.co.uk"
REPLY_TO_EMAIL = "your.name@yourcompany.co.uk"''', language="toml")
    st.warning("Do not commit real passwords or secrets to GitHub. Add them in Streamlit Community Cloud under App > Settings > Secrets.")
