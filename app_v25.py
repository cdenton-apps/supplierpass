from pathlib import Path
import pandas as pd
import streamlit as st

APP_VERSION = "v0.25 fictional demo queues"
DEMO_TAG = "EXPANDED_DEMO"

source_path = Path(__file__).with_name("app_v24.py")
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
ensure_onboarding_schema = namespace["ensure_onboarding_schema"]
onboarding_screen = namespace["onboarding_screen"]
approval_queue_screen = namespace["approval_queue_screen"]
navigation_help = namespace["navigation_help"]
hero = namespace["hero"]
hint = namespace["hint"]
show_df = namespace["show_df"]
df_sql = namespace["df_sql"]
exec_sql = namespace["exec_sql"]
base_load_expanded_demo_data = namespace["load_expanded_demo_data"]
clear_expanded_demo_data = namespace["clear_expanded_demo_data"]


def supplier_id_by_name(name):
    df = df_sql("SELECT supplier_id FROM suppliers WHERE supplier_name=?", (name,))
    return None if df.empty else int(df.iloc[0]["supplier_id"])


def add_document(supplier_name, doc_type, expiry, status, note):
    sid = supplier_id_by_name(supplier_name)
    if sid is None:
        return
    exec_sql(
        """
        INSERT INTO supplier_documents
        (supplier_id, document_type, file_name, expiry_date, review_status, reviewed_by, review_notes, notes)
        VALUES (?, ?, ?, ?, ?, 'Demo user', ?, ?)
        """,
        (sid, doc_type, f"{doc_type} - {supplier_name} - {DEMO_TAG}.pdf", expiry, status, note, f"{DEMO_TAG} QUEUE_DEMO {note}"),
    )


def add_email(supplier_name, email_type, subject, status, sent_by):
    sid = supplier_id_by_name(supplier_name)
    if sid is None:
        return
    supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)).iloc[0]
    exec_sql(
        """
        INSERT INTO email_log (supplier_id, email_type, recipient, subject, body, status, sent_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid,
            email_type,
            supplier["supplier_email"] or "demo@example.demo",
            f"{DEMO_TAG} {subject}",
            f"{DEMO_TAG} Demo queue email for {supplier_name}. Please review the outstanding supplier action.",
            status,
            sent_by,
        ),
    )


def add_erp_action(supplier_name, code, action_type, reason, old_value, new_value):
    sid = supplier_id_by_name(supplier_name)
    if sid is None:
        return
    exec_sql(
        """
        INSERT INTO erp_action_queue
        (supplier_id, supplier_code, supplier_name, action_type, action_reason, old_value, new_value, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending Export', 'Demo user')
        """,
        (sid, code, supplier_name, action_type, f"{DEMO_TAG}: {reason}", old_value, new_value),
    )


def add_extra_queue_demo_data():
    # Extra document work deliberately populates the processing queue.
    extra_docs = [
        ("BluePeak Logistics Ltd", "Operator Licence", "2026-08-31", "Uploaded", "Waiting for transport manager review"),
        ("BluePeak Logistics Ltd", "Fleet Insurance Schedule", "2026-05-15", "Under Review", "Insurance schedule needs expiry confirmation"),
        ("SilverRoute Distribution Ltd", "Goods in Transit Insurance", "2026-02-28", "Uploaded", "New copy received but not reviewed"),
        ("Amberline Labels Ltd", "ISO 9001 Certificate", "2026-09-30", "Uploaded", "Awaiting quality approval"),
        ("Amberline Labels Ltd", "Supplier Questionnaire", "2026-12-31", "Under Review", "Procurement review in progress"),
        ("Rivergate Adhesives Ltd", "Technical Data Sheet", "2027-01-31", "Uploaded", "Needs production sign-off"),
        ("Rivergate Adhesives Ltd", "REACH Declaration", "2026-01-31", "Rejected / Needs replacement", "Old declaration uploaded"),
        ("Oakbridge Site Services Ltd", "Public Liability Insurance", "2026-04-30", "Uploaded", "Waiting for maintenance manager review"),
        ("NimbusCore Systems Ltd", "Data Processing Agreement", "2027-04-30", "Under Review", "Legal review required"),
        ("ClearCurrent Utilities Ltd", "Service Continuity Statement", "2026-10-31", "Uploaded", "Finance review required"),
        ("PaperTrail Office Supplies Ltd", "Supplier Questionnaire", "2025-10-31", "Rejected / Needs replacement", "Dormant supplier evidence expired"),
    ]
    for row in extra_docs:
        add_document(*row)

    # Extra approval work deliberately populates the onboarding and approval queues.
    extra_requests = [
        ("BrightHarbour Pallet Services Ltd", "sales@brightharbour.demo", "Logistics", "Transport", "Urgent overflow pallet carrier required. EXPANDED_DEMO", 45000, "High", "Awaiting Approval"),
        ("SlateFox Corrugated Ltd", "hello@slatefox.demo", "Procurement", "Packaging", "Alternative corrugated supplier for price comparison. EXPANDED_DEMO", 90000, "Normal", "Awaiting Approval"),
        ("CopperBee Components Ltd", "orders@copperbee.demo", "Production", "Raw Materials", "Trial supplier for specialist components. EXPANDED_DEMO", 22000, "Normal", "Awaiting Approval"),
        ("FrostVale Engineering Ltd", "support@frostvale.demo", "Maintenance", "Contractor", "Emergency engineering support supplier. EXPANDED_DEMO", 16000, "Critical", "Awaiting Approval"),
        ("BlueLedger Analytics Ltd", "security@blueledger.demo", "IT", "IT / Software", "BI reporting vendor proposal. EXPANDED_DEMO", 28000, "Normal", "Draft"),
        ("LumenArc Training Ltd", "contact@lumenarc.demo", "HR", "Training", "Supplier training provider for operational rollout. EXPANDED_DEMO", 9500, "Low", "Draft"),
        ("StoneBridge Cleaning Ltd", "info@stonebridge-cleaning.demo", "Operations", "Facilities", "Site cleaning tender option. EXPANDED_DEMO", 32000, "Normal", "Rejected"),
        ("JuniperGate Print Ltd", "sales@junipergate.demo", "Procurement", "Packaging", "Rejected due to duplicate capability. EXPANDED_DEMO", 42000, "Normal", "Rejected"),
    ]
    for row in extra_requests:
        exec_sql(
            """
            INSERT INTO new_supplier_requests
            (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    # Extra email work deliberately populates drafted and sent queues.
    extra_emails = [
        ("BluePeak Logistics Ltd", "Document expiring soon", "Operator licence review required", "Drafted", "Logistics"),
        ("SilverRoute Distribution Ltd", "Missing document request", "Goods in transit insurance copy required", "Drafted", "Logistics"),
        ("Amberline Labels Ltd", "Annual supplier review request", "Annual review evidence request", "Drafted", "Procurement"),
        ("Rivergate Adhesives Ltd", "Expired document chase", "Replacement REACH declaration required", "Sent / manually recorded", "Production"),
        ("Oakbridge Site Services Ltd", "Missing document request", "Public liability evidence required", "Drafted", "Maintenance"),
        ("NimbusCore Systems Ltd", "Bank verification request", "Finance contact verification required", "Drafted", "Finance"),
    ]
    for row in extra_emails:
        add_email(*row)

    # Extra ERP work deliberately populates the ERP update queue.
    extra_erp = [
        ("Redwood Express Carriers Ltd", "TRN003", "REVOKE_APPROVAL_OR_BLOCK", "Approval revoked in SupplierPass after repeated late deliveries", "Approved", "Approval Revoked"),
        ("Rivergate Adhesives Ltd", "RAW001", "HOLD_SUPPLIER_FOR_EVIDENCE", "Supplier still pending insurance evidence", "Approved", "On Hold"),
        ("NimbusCore Systems Ltd", "IT001", "HOLD_SUPPLIER_FOR_SECURITY_REVIEW", "Cyber review not complete", "Approved", "On Hold"),
        ("PaperTrail Office Supplies Ltd", "GEN001", "SET_SUPPLIER_INACTIVE", "Dormant office supplier no longer required", "Active", "Inactive"),
    ]
    for row in extra_erp:
        add_erp_action(*row)


def load_expanded_demo_data():
    base_load_expanded_demo_data()
    add_extra_queue_demo_data()


def demo_data_screen():
    hero("Expanded Demo Data", "Load a fictional dataset with active work queues.")
    hint("All demo suppliers are fictional and use .demo email domains. This version intentionally fills approval queues, document review queues, email chases and ERP action queues so you can test the full workflow.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load fictional demo queues", type="primary"):
            load_expanded_demo_data()
            st.success("Fictional demo queues loaded.")
            st.rerun()
    with c2:
        if st.button("Clear expanded demo data"):
            clear_expanded_demo_data()
            st.warning("Expanded demo data cleared.")
            st.rerun()

    st.subheader("Queue coverage")
    st.markdown(
        """
        - **Approval Queue:** multiple Awaiting Approval, Draft and Rejected onboarding requests
        - **Document Processing Queue:** Uploaded and Under Review documents waiting for action
        - **Evidence Chase Queue:** rejected, expiring and unreviewed documents
        - **Email Centre:** drafted and manually recorded supplier chases
        - **ERP Update Queue:** inactive, revoked and on-hold supplier actions
        - **Supplier Intelligence:** PO history, OTIF data, prices, preferred suppliers and inactive examples
        """
    )

    tabs = st.tabs(["Approvals", "Documents Waiting", "Email Chases", "ERP Actions", "Suppliers", "Prices", "PO History"])
    with tabs[0]:
        show_df(df_sql("SELECT supplier_name, category, requested_by, expected_annual_spend, urgency, status FROM new_supplier_requests WHERE reason_needed LIKE ? ORDER BY status, urgency", (f"%{DEMO_TAG}%",)), "No demo approvals loaded.")
    with tabs[1]:
        show_df(df_sql("""
            SELECT s.supplier_name, d.document_type, d.expiry_date, d.review_status, s.owner
            FROM supplier_documents d
            LEFT JOIN suppliers s ON d.supplier_id=s.supplier_id
            WHERE d.notes LIKE ? AND d.review_status IN ('Uploaded','Under Review','Rejected / Needs replacement')
            ORDER BY d.review_status, s.supplier_name
        """, (f"%{DEMO_TAG}%",)), "No waiting demo documents loaded.")
    with tabs[2]:
        show_df(df_sql("SELECT e.email_type, e.recipient, e.subject, e.status, s.supplier_name FROM email_log e LEFT JOIN suppliers s ON e.supplier_id=s.supplier_id WHERE e.subject LIKE ? ORDER BY e.status, e.sent_at DESC", (f"%{DEMO_TAG}%",)), "No demo emails loaded.")
    with tabs[3]:
        show_df(df_sql("SELECT supplier_code, supplier_name, action_type, old_value, new_value, status, action_reason FROM erp_action_queue WHERE action_reason LIKE ? ORDER BY created_at DESC", (f"%{DEMO_TAG}%",)), "No demo ERP actions loaded.")
    with tabs[4]:
        show_df(df_sql("SELECT supplier_code, supplier_name, category, approval_status, app_status, risk_level, annual_spend FROM suppliers WHERE notes LIKE ? ORDER BY category, supplier_name", (f"%{DEMO_TAG}%",)), "No demo suppliers loaded.")
    with tabs[5]:
        show_df(df_sql("SELECT supplier_name, category, item_code, item_description, unit_price, lead_time_days FROM supplier_prices WHERE source_file='expanded_demo' ORDER BY category, item_code, supplier_name"), "No demo prices loaded.")
    with tabs[6]:
        show_df(df_sql("SELECT supplier_name, item_code, po_number, po_date, promised_date, received_date, total_value FROM po_history WHERE source_file='expanded_demo' ORDER BY po_date DESC LIMIT 100"), "No demo PO rows loaded.")


def run_grouped_app():
    init_db()
    ensure_document_email_schema()
    ensure_onboarding_schema()
    style()
    st.sidebar.markdown("# SupplierPass")
    st.sidebar.caption(APP_VERSION)
    area = st.sidebar.selectbox("Area", ["🏠 Home", "🏢 Supplier Setup", "📄 Documents & Email", "🔄 ERP Data", "📊 Performance", "📁 Reports"])
    if area == "🏠 Home":
        page = st.sidebar.radio("Page", ["Dashboard", "Expanded Demo Data", "How to use SupplierPass"])
        if page == "Dashboard": dashboard()
        elif page == "Expanded Demo Data": demo_data_screen()
        else: navigation_help()
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
