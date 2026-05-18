from pathlib import Path
import re
import pandas as pd
import streamlit as st

APP_VERSION = "v0.22 full grouped workflow - helper compatibility fix"

source_path = Path(__file__).with_name("app_v19.py")
source_code = source_path.read_text(encoding="utf-8")
definitions = source_code.rsplit("\nrun_grouped_app()", 1)[0] if "\nrun_grouped_app()" in source_code else source_code
namespace = {"__file__": str(source_path)}
exec(compile(definitions, str(source_path), "exec"), namespace)
namespace["APP_VERSION"] = APP_VERSION

init_db = namespace["init_db"]
style = namespace["style"]
dashboard = namespace["dashboard"]
supplier_register = namespace["supplier_register"]
preferred_suppliers_screen = namespace["preferred_suppliers_screen"]
document_management_screen = namespace["document_management_screen"]
email_centre_screen = namespace["email_centre_screen"]
data_uploads = namespace["data_uploads"]
supplier_intelligence = namespace["supplier_intelligence"]
erp_actions = namespace["erp_actions"]
reports = namespace["reports"]
ensure_document_email_schema = namespace["ensure_document_email_schema"]
hero = namespace["hero"]
hint = namespace["hint"]
show_df = namespace["show_df"]
df_sql = namespace["df_sql"]
exec_sql = namespace["exec_sql"]


def normalise_name(value):
    fn = namespace.get("normalise_name")
    if callable(fn):
        return fn(value)
    value = str(value or "").lower().strip()
    value = re.sub(r"\b(limited|ltd|plc|llp|uk|the)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def normalise_email(value):
    fn = namespace.get("normalise_email")
    if callable(fn):
        return fn(value)
    return str(value or "").strip().lower()


def find_duplicate(name, email=""):
    fn = namespace.get("find_duplicate") or namespace.get("find_duplicate_suppliers")
    if callable(fn):
        return fn(name, email)
    key = normalise_name(name)
    email_key = normalise_email(email)
    if email_key:
        return df_sql(
            """
            SELECT * FROM suppliers
            WHERE supplier_key=? OR email_key=? OR lower(supplier_email)=?
            ORDER BY supplier_name
            """,
            (key, email_key, email_key),
        )
    return df_sql("SELECT * FROM suppliers WHERE supplier_key=? ORDER BY supplier_name", (key,))


def ensure_onboarding_schema():
    exec_sql("""
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


def create_supplier_from_request_safe(request_id, approved_by, notes):
    req_df = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (request_id,))
    if req_df.empty:
        return None, "Request not found."
    req = req_df.iloc[0]
    converted = req.get("converted_supplier_id")
    if pd.notna(converted) and str(converted) not in ["", "None", "nan"]:
        supplier_id = int(converted)
        exec_sql("UPDATE new_supplier_requests SET status='Converted to Supplier', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (request_id,))
        return supplier_id, f"Already converted to supplier ID {supplier_id}. No duplicate was created."
    if req["status"] != "Awaiting Approval":
        return None, f"This request is {req['status']}, so it cannot be approved."
    existing = find_duplicate(req["supplier_name"], req["supplier_email"] or "")
    if not existing.empty:
        supplier_id = int(existing.iloc[0]["supplier_id"])
        exec_sql(
            """
            UPDATE new_supplier_requests
            SET status='Converted to Supplier', approval_decision='Approved - linked existing supplier',
                approval_notes=?, approved_by=?, approved_at=CURRENT_TIMESTAMP, converted_supplier_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE request_id=?
            """,
            (notes, approved_by, supplier_id, request_id),
        )
        return supplier_id, f"A matching supplier already existed, so the request was linked to supplier ID {supplier_id}. No duplicate was created."
    supplier_id = exec_sql(
        """
        INSERT INTO suppliers
        (supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, app_status, risk_level, annual_spend, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'Approved', 'Active', 'Medium', ?, ?)
        """,
        (
            req["supplier_name"], normalise_name(req["supplier_name"]), req["supplier_email"] or "",
            normalise_email(req["supplier_email"] or ""), req["category"] or "", req["requested_by"] or "",
            float(req["expected_annual_spend"] or 0),
            f"Created from onboarding request {request_id}. {req['reason_needed'] or ''}\nApproval notes: {notes or ''}",
        ),
    )
    exec_sql(
        """
        UPDATE new_supplier_requests
        SET status='Converted to Supplier', approval_decision='Approved', approval_notes=?, approved_by=?,
            approved_at=CURRENT_TIMESTAMP, converted_supplier_id=?, updated_at=CURRENT_TIMESTAMP
        WHERE request_id=?
        """,
        (notes, approved_by, supplier_id, request_id),
    )
    return supplier_id, f"Approved and supplier created. Supplier ID: {supplier_id}."


def onboarding_screen():
    hero("Supplier Onboarding", "Create new supplier requests before they become approved supplier records.")
    hint("Create a request, then approve it in the Approval Queue. Approval automatically creates or links the supplier record.")
    tab_new, tab_requests = st.tabs(["New Request", "All Requests"])
    with tab_new:
        with st.form("new_supplier_request"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Supplier name *")
            email = c1.text_input("Supplier email")
            category = c2.text_input("Category")
            spend = c2.number_input("Expected annual spend", min_value=0.0, step=100.0)
            urgency = c2.selectbox("Urgency", ["Low", "Normal", "High", "Critical"], index=1)
            requested_by = c2.text_input("Requested by")
            reason = st.text_area("Why is the supplier needed?")
            submit_now = st.checkbox("Submit for approval now", value=True)
            if st.form_submit_button("Create request", type="primary"):
                if not name:
                    st.error("Supplier name is required.")
                else:
                    existing = find_duplicate(name, email)
                    if not existing.empty:
                        st.warning("A matching supplier already exists. Approval will link to the existing supplier rather than create a duplicate.")
                        st.dataframe(existing, use_container_width=True, hide_index=True)
                    status = "Awaiting Approval" if submit_now else "Draft"
                    exec_sql(
                        """
                        INSERT INTO new_supplier_requests
                        (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (name, email, requested_by, category, reason, spend, urgency, status),
                    )
                    st.success(f"Request created with status: {status}")
                    st.rerun()
    with tab_requests:
        show_df(df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"), "No supplier requests yet.")


def approval_queue_screen():
    hero("Approval Queue", "Review onboarding requests, reject them, or approve and create/link suppliers.")
    hint("Only Draft and Awaiting Approval requests show by default. Converted or rejected requests are hidden unless you choose to show all.")
    requests = df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC")
    if requests.empty:
        st.info("No onboarding requests yet. Create one in Supplier Onboarding.")
        return
    show_all = st.checkbox("Show converted/rejected requests", value=False)
    view = requests if show_all else requests[requests["status"].isin(["Draft", "Awaiting Approval"])]
    cols = ["request_id", "supplier_name", "category", "requested_by", "expected_annual_spend", "urgency", "status", "approved_by", "approved_at", "converted_supplier_id"]
    show_df(view[cols] if not view.empty else view, "No active approval requests.")
    if view.empty:
        return
    options = {f"{r['supplier_name']} ({r['request_id']}) - {r['status']}": int(r["request_id"]) for _, r in view.iterrows()}
    request_id = options[st.selectbox("Select request", list(options.keys()))]
    req = df_sql("SELECT * FROM new_supplier_requests WHERE request_id=?", (request_id,)).iloc[0]
    st.subheader(req["supplier_name"])
    st.write(f"**Status:** {req['status']} | **Category:** {req['category'] or ''} | **Spend:** £{float(req['expected_annual_spend'] or 0):,.2f} | **Urgency:** {req['urgency']}")
    st.write(f"**Requested by:** {req['requested_by'] or ''}")
    st.write(req["reason_needed"] or "")
    duplicate_matches = find_duplicate(req["supplier_name"], req["supplier_email"] or "")
    if not duplicate_matches.empty:
        st.warning("Possible existing supplier match found. Approval will link to the existing supplier instead of creating another one.")
        st.dataframe(duplicate_matches, use_container_width=True, hide_index=True)
    notes = st.text_area("Decision notes", value=req["approval_notes"] or "")
    decided_by = st.text_input("Decision by", value=req["approved_by"] or "")
    if req["status"] == "Draft":
        if st.button("Submit for approval", type="primary"):
            exec_sql("UPDATE new_supplier_requests SET status='Awaiting Approval', updated_at=CURRENT_TIMESTAMP WHERE request_id=?", (request_id,))
            st.success("Submitted for approval.")
            st.rerun()
    elif req["status"] == "Awaiting Approval":
        c1, c2 = st.columns(2)
        button_text = "Approve & Link Existing Supplier" if not duplicate_matches.empty else "Approve & Create Supplier"
        if c1.button(button_text, type="primary", key=f"approve_{request_id}"):
            supplier_id, message = create_supplier_from_request_safe(request_id, decided_by, notes)
            st.success(message) if supplier_id else st.warning(message)
            st.rerun()
        if c2.button("Reject", key=f"reject_{request_id}"):
            exec_sql(
                """
                UPDATE new_supplier_requests
                SET status='Rejected', approval_decision='Rejected', approval_notes=?, approved_by=?, approved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE request_id=? AND status='Awaiting Approval'
                """,
                (notes, decided_by, request_id),
            )
            st.warning("Request rejected.")
            st.rerun()
    elif req["status"] == "Converted to Supplier":
        st.success(f"This request has already been converted/linked to supplier ID {req['converted_supplier_id']}.")
    elif req["status"] == "Rejected":
        st.warning("This request has been rejected.")


def navigation_help():
    hero("SupplierPass Navigation", "A full grouped workflow for onboarding, documents, email, ERP data, supplier performance and ERP controls.")
    hint("Use the sidebar areas to move through the process from request to approval, documents, chasers, ERP data, supplier comparison and ERP export.")
    st.markdown("""
    ### Suggested workflow

    **1. Supplier Setup**  
    Create onboarding requests, approve suppliers, manage supplier records, set inactive suppliers and choose preferred suppliers by category.

    **2. Documents & Email**  
    Upload supplier documents, approve/reject evidence, review gaps, generate supplier chasers and log emails.

    **3. ERP Data**  
    Upload PO/receipt history and price exports, then review ERP update actions created by SupplierPass.

    **4. Performance**  
    Compare suppliers using visual scorecards, price, OTIF, usage, preferred status and approval status.

    **5. Reports**  
    Export the SupplierPass pack for audit, management review or ERP follow-up.
    """)


def run_grouped_app():
    init_db()
    ensure_document_email_schema()
    ensure_onboarding_schema()
    style()
    st.sidebar.markdown("# SupplierPass")
    st.sidebar.caption(APP_VERSION)
    area = st.sidebar.selectbox("Area", ["🏠 Home", "🏢 Supplier Setup", "📄 Documents & Email", "🔄 ERP Data", "📊 Performance", "📁 Reports"])
    if area == "🏠 Home":
        page = st.sidebar.radio("Page", ["Dashboard", "How to use SupplierPass"])
        dashboard() if page == "Dashboard" else navigation_help()
    elif area == "🏢 Supplier Setup":
        page = st.sidebar.radio("Page", ["Supplier Onboarding", "Approval Queue", "Suppliers", "Preferred by Category", "Supplier Controls"])
        if page == "Supplier Onboarding": onboarding_screen()
        elif page == "Approval Queue": approval_queue_screen()
        elif page == "Preferred by Category": preferred_suppliers_screen()
        else: supplier_register()
    elif area == "📄 Documents & Email":
        page = st.sidebar.radio("Page", ["Document Management", "Email Centre", "Evidence Chase Queue"])
        email_centre_screen() if page in ["Email Centre", "Evidence Chase Queue"] else document_management_screen()
    elif area == "🔄 ERP Data":
        page = st.sidebar.radio("Page", ["Upload ERP Exports", "ERP Update Queue"])
        data_uploads() if page == "Upload ERP Exports" else erp_actions()
    elif area == "📊 Performance":
        st.sidebar.radio("Page", ["Supplier Scorecards", "Compare Suppliers", "Price Analysis", "OTIF Analysis", "Recommendation History"])
        supplier_intelligence()
    elif area == "📁 Reports":
        page = st.sidebar.radio("Page", ["Reports & Audit", "ERP Export Pack"])
        erp_actions() if page == "ERP Export Pack" else reports()


run_grouped_app()
