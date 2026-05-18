from pathlib import Path
import pandas as pd
import streamlit as st

APP_VERSION = "v0.24 fictional demo data only"

source_path = Path(__file__).with_name("app_v22.py")
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
find_duplicate = namespace["find_duplicate"]
normalise_name = namespace["normalise_name"]
normalise_email = namespace["normalise_email"]

DEMO_TAG = "EXPANDED_DEMO"


def clear_expanded_demo_data():
    exec_sql("DELETE FROM po_history WHERE source_file='expanded_demo'")
    exec_sql("DELETE FROM supplier_prices WHERE source_file='expanded_demo'")
    exec_sql("DELETE FROM supplier_documents WHERE notes LIKE ? OR file_name LIKE ?", (f"%{DEMO_TAG}%", f"%{DEMO_TAG}%"))
    exec_sql("DELETE FROM email_log WHERE subject LIKE ? OR body LIKE ?", (f"%{DEMO_TAG}%", f"%{DEMO_TAG}%"))
    exec_sql("DELETE FROM preferred_suppliers WHERE reason LIKE ?", (f"%{DEMO_TAG}%",))
    exec_sql("DELETE FROM erp_action_queue WHERE action_reason LIKE ?", (f"%{DEMO_TAG}%",))
    exec_sql("DELETE FROM new_supplier_requests WHERE reason_needed LIKE ?", (f"%{DEMO_TAG}%",))
    exec_sql("DELETE FROM suppliers WHERE notes LIKE ?", (f"%{DEMO_TAG}%",))


def upsert_demo_supplier(code, name, email, category, owner, approval, app_status, risk, spend, notes):
    existing = find_duplicate(name, email)
    if not existing.empty:
        supplier_id = int(existing.iloc[0]["supplier_id"])
        exec_sql(
            """
            UPDATE suppliers
            SET supplier_code=?, supplier_email=?, email_key=?, category=?, owner=?, approval_status=?, app_status=?, risk_level=?, annual_spend=?, notes=?, updated_at=CURRENT_TIMESTAMP
            WHERE supplier_id=?
            """,
            (code, email, normalise_email(email), category, owner, approval, app_status, risk, spend, notes, supplier_id),
        )
        return supplier_id
    return exec_sql(
        """
        INSERT INTO suppliers
        (supplier_code, supplier_name, supplier_key, supplier_email, email_key, category, owner, approval_status, app_status, risk_level, annual_spend, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, name, normalise_name(name), email, normalise_email(email), category, owner, approval, app_status, risk, spend, notes),
    )


def add_demo_document(supplier_id, doc_type, expiry, status, notes, file_name=""):
    exec_sql(
        """
        INSERT INTO supplier_documents
        (supplier_id, document_type, file_name, expiry_date, review_status, reviewed_by, review_notes, notes)
        VALUES (?, ?, ?, ?, ?, 'Demo user', ?, ?)
        """,
        (supplier_id, doc_type, file_name or f"{doc_type} - {DEMO_TAG}.pdf", expiry, status, notes, f"{DEMO_TAG} {notes}"),
    )


def add_demo_prices(supplier_id, supplier_name, supplier_key, category, item_prefix, base_price, lead_time):
    items = [
        (f"{item_prefix}-001", "Standard supply item", base_price, lead_time),
        (f"{item_prefix}-002", "Premium / urgent supply item", base_price * 1.18, max(1, lead_time - 1)),
        (f"{item_prefix}-003", "Bulk supply item", base_price * 0.92, lead_time + 2),
    ]
    for code, desc, price, lt in items:
        exec_sql(
            """
            INSERT INTO supplier_prices
            (supplier_id, supplier_name, supplier_key, item_code, item_description, category, unit_price, currency, lead_time_days, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'GBP', ?, 'expanded_demo')
            """,
            (supplier_id, supplier_name, supplier_key, code, desc, category, round(price, 2), lt),
        )


def add_demo_po_history(supplier_id, supplier_name, supplier_key, item_prefix, reliability, spend_multiplier):
    today = pd.Timestamp.today().normalize()
    for i in range(1, 13):
        po_date = today - pd.DateOffset(days=i * 28)
        promised = po_date + pd.DateOffset(days=7 + (i % 3))
        late_pattern = (i + supplier_id) % 5
        days_late = 0 if late_pattern < reliability else late_pattern - reliability + 1
        received = promised + pd.DateOffset(days=days_late)
        qty = 10 + (i * 3)
        unit_price = 8 + (supplier_id % 7) + (i % 3) * 1.25
        total = qty * unit_price * spend_multiplier
        exec_sql(
            """
            INSERT INTO po_history
            (supplier_id, supplier_name, supplier_key, item_code, item_description, po_number, po_date, promised_date, received_date, quantity, unit_price, total_value, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'expanded_demo')
            """,
            (
                supplier_id, supplier_name, supplier_key,
                f"{item_prefix}-{(i % 3) + 1:03d}", f"Expanded demo item {(i % 3) + 1}",
                f"PO-XD-{supplier_id}-{i:03d}", po_date.date().isoformat(), promised.date().isoformat(),
                received.date().isoformat(), qty, round(unit_price, 2), round(total, 2),
            ),
        )


def load_expanded_demo_data():
    clear_expanded_demo_data()

    suppliers = [
        ("TRN001", "BluePeak Logistics Ltd", "ops@bluepeak-logistics.demo", "Transport", "Logistics", "Approved", "Active", "Medium", 185000, "Fast and cost-effective regional haulier"),
        ("TRN002", "SilverRoute Distribution Ltd", "traffic@silverroute.demo", "Transport", "Logistics", "Approved", "Active", "Low", 142000, "Preferred tail-lift and timed delivery partner"),
        ("TRN003", "Redwood Express Carriers Ltd", "accounts@redwood-express.demo", "Transport", "Logistics", "Approval Revoked", "Inactive", "High", 72000, "Service failures; inactive pending ERP update"),
        ("PKG001", "Northstar Board & Packaging Ltd", "quality@northstar-board.demo", "Packaging", "Quality", "Approved", "Active", "Medium", 245000, "Main board and sheet supplier"),
        ("PKG002", "Amberline Labels Ltd", "sales@amberline-labels.demo", "Packaging", "Procurement", "Approved", "Active", "Low", 88000, "Label and print finishing specialist"),
        ("RAW001", "Rivergate Adhesives Ltd", "technical@rivergate-adhesives.demo", "Raw Materials", "Production", "Pending", "Active", "Medium", 64000, "Awaiting insurance evidence"),
        ("MNT001", "Oakbridge Site Services Ltd", "helpdesk@oakbridge-services.demo", "Contractor", "Maintenance", "Approved", "Active", "High", 38000, "Useful but higher H&S risk"),
        ("IT001", "NimbusCore Systems Ltd", "security@nimbuscore.demo", "IT / Software", "IT", "On Hold", "Active", "High", 52000, "Cyber review still open"),
        ("UTL001", "ClearCurrent Utilities Ltd", "business@clearcurrent.demo", "Utilities", "Finance", "Approved", "Active", "Low", 120000, "Stable utility provider"),
        ("GEN001", "PaperTrail Office Supplies Ltd", "orders@papertrail-office.demo", "Office Supplies", "Admin", "Dormant", "Inactive", "Low", 2500, "Dormant supplier for inactive testing"),
    ]

    supplier_ids = {}
    for code, name, email, category, owner, approval, app_status, risk, spend, note in suppliers:
        sid = upsert_demo_supplier(code, name, email, category, owner, approval, app_status, risk, spend, f"{DEMO_TAG}: FICTIONAL DEMO SUPPLIER - {note}")
        supplier_ids[name] = sid

    supplier_df = df_sql("SELECT * FROM suppliers WHERE notes LIKE ?", (f"%{DEMO_TAG}%",))
    for _, s in supplier_df.iterrows():
        category = s["category"] or "General"
        prefix = {
            "Transport": "FRT",
            "Packaging": "PKG",
            "Raw Materials": "RAW",
            "Contractor": "MNT",
            "IT / Software": "ITS",
            "Utilities": "UTL",
            "Office Supplies": "OFF",
        }.get(category, "GEN")
        reliability = {"Low": 4, "Medium": 3, "High": 2, "Critical": 1}.get(s["risk_level"], 3)
        add_demo_prices(int(s["supplier_id"]), s["supplier_name"], s["supplier_key"], category, prefix, 10 + (int(s["supplier_id"]) % 6), 3 + (int(s["supplier_id"]) % 5))
        add_demo_po_history(int(s["supplier_id"]), s["supplier_name"], s["supplier_key"], prefix, reliability, 1 + (float(s["annual_spend"] or 0) / 200000))

    add_demo_document(supplier_ids["BluePeak Logistics Ltd"], "Goods in Transit Insurance", "2027-02-28", "Accepted", "Valid GIT evidence")
    add_demo_document(supplier_ids["BluePeak Logistics Ltd"], "Public Liability Insurance", "2026-07-31", "Accepted", "Accepted but expiring within review period")
    add_demo_document(supplier_ids["SilverRoute Distribution Ltd"], "Public Liability Insurance", "2027-05-30", "Accepted", "Clean record")
    add_demo_document(supplier_ids["Redwood Express Carriers Ltd"], "Operator Licence", "2025-11-30", "Rejected / Needs replacement", "Rejected licence copy")
    add_demo_document(supplier_ids["Northstar Board & Packaging Ltd"], "ISO 9001 Certificate", "2027-01-31", "Accepted", "Accepted quality certificate")
    add_demo_document(supplier_ids["Northstar Board & Packaging Ltd"], "FSC / PEFC Certificate", "2026-04-30", "Under Review", "Awaiting quality approval")
    add_demo_document(supplier_ids["Rivergate Adhesives Ltd"], "Public Liability Insurance", "2025-12-31", "Uploaded", "Uploaded but not reviewed")
    add_demo_document(supplier_ids["Oakbridge Site Services Ltd"], "RAMS", "2026-03-31", "Under Review", "Needs H&S review")
    add_demo_document(supplier_ids["NimbusCore Systems Ltd"], "Cyber Security Questionnaire", "2026-06-30", "Uploaded", "Awaiting IT security approval")
    add_demo_document(supplier_ids["ClearCurrent Utilities Ltd"], "Supplier Questionnaire", "2027-03-31", "Accepted", "Stable supplier")

    preferences = [
        (supplier_ids["SilverRoute Distribution Ltd"], "Transport", "Preferred for timed/tail-lift deliveries"),
        (supplier_ids["Northstar Board & Packaging Ltd"], "Packaging", "Preferred board supplier due to reliability"),
        (supplier_ids["Amberline Labels Ltd"], "Packaging", "Preferred for labels and print finishing"),
        (supplier_ids["ClearCurrent Utilities Ltd"], "Utilities", "Preferred utility provider"),
    ]
    for sid, category, reason in preferences:
        exec_sql(
            """
            INSERT INTO preferred_suppliers (supplier_id, category, is_preferred, reason, set_by, set_at)
            VALUES (?, ?, 1, ?, 'Demo user', CURRENT_TIMESTAMP)
            ON CONFLICT(supplier_id, category)
            DO UPDATE SET is_preferred=1, reason=excluded.reason, set_by='Demo user', set_at=CURRENT_TIMESTAMP
            """,
            (sid, category, f"{DEMO_TAG}: {reason}"),
        )

    requests = [
        ("ValePoint Couriers Ltd", "newbiz@valepoint-couriers.demo", "Logistics", "Transport", "Backup courier for urgent pallet movements. EXPANDED_DEMO", 30000, "High", "Awaiting Approval"),
        ("GreenLoop Recycling Ltd", "hello@greenloop-recycling.demo", "Operations", "Waste / Recycling", "New waste provider for site review. EXPANDED_DEMO", 18000, "Normal", "Draft"),
        ("ShieldFox Security Testing Ltd", "security@shieldfox.demo", "IT", "IT / Software", "Cybersecurity supplier proposal. EXPANDED_DEMO", 12000, "Normal", "Rejected"),
    ]
    for row in requests:
        exec_sql(
            """
            INSERT INTO new_supplier_requests
            (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend, urgency, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    email_rows = [
        (supplier_ids["Rivergate Adhesives Ltd"], "Missing document request", "technical@rivergate-adhesives.demo", f"{DEMO_TAG} Supplier document request - Rivergate Adhesives", "Please send updated insurance evidence.", "Drafted", "Procurement"),
        (supplier_ids["Oakbridge Site Services Ltd"], "Expired document chase", "helpdesk@oakbridge-services.demo", f"{DEMO_TAG} RAMS review required - Oakbridge Site Services", "RAMS is awaiting review.", "Sent / manually recorded", "Maintenance"),
        (supplier_ids["NimbusCore Systems Ltd"], "Cyber Security Questionnaire", "security@nimbuscore.demo", f"{DEMO_TAG} Cyber review outstanding - NimbusCore Systems", "Please complete the cyber security questionnaire.", "Drafted", "IT"),
    ]
    for row in email_rows:
        exec_sql(
            """
            INSERT INTO email_log (supplier_id, email_type, recipient, subject, body, status, sent_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    erp_actions = [
        (supplier_ids["Redwood Express Carriers Ltd"], "TRN003", "Redwood Express Carriers Ltd", "SET_SUPPLIER_INACTIVE", f"{DEMO_TAG}: Approval revoked due to service failures", "Active", "Inactive", "Pending Export", "Demo user"),
        (supplier_ids["PaperTrail Office Supplies Ltd"], "GEN001", "PaperTrail Office Supplies Ltd", "SET_SUPPLIER_INACTIVE", f"{DEMO_TAG}: Dormant supplier no longer required", "Active", "Inactive", "Pending Export", "Demo user"),
    ]
    for row in erp_actions:
        exec_sql(
            """
            INSERT INTO erp_action_queue
            (supplier_id, supplier_code, supplier_name, action_type, action_reason, old_value, new_value, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )


def demo_data_screen():
    hero("Expanded Demo Data", "Load a fictional dataset to test the full SupplierPass workflow.")
    hint("All demo suppliers in v24 are fictional and use .demo email domains. Loading the pack clears any previous EXPANDED_DEMO rows first.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load fictional expanded demo data", type="primary"):
            load_expanded_demo_data()
            st.success("Fictional expanded demo data loaded.")
            st.rerun()
    with c2:
        if st.button("Clear expanded demo data"):
            clear_expanded_demo_data()
            st.warning("Expanded demo data cleared.")
            st.rerun()

    st.subheader("Demo coverage")
    st.markdown(
        """
        - **10 fictional suppliers** across Transport, Packaging, Raw Materials, Contractor, IT, Utilities and Office Supplies
        - **Preferred supplier flags** using ⭐
        - **Active/inactive and revoked approval examples**
        - **PO/receipt history** for OTIF and last-used calculations
        - **Price records** for supplier comparison and 🏆 best-price flags
        - **Supplier documents** with accepted, uploaded, under-review and rejected statuses
        - **Email log entries** and chase examples
        - **Onboarding requests** in Draft, Awaiting Approval and Rejected states
        - **ERP Action Queue** examples for inactive/revoked suppliers
        """
    )

    tabs = st.tabs(["Suppliers", "Documents", "Emails", "Onboarding", "ERP Actions", "Prices", "PO History"])
    with tabs[0]:
        show_df(df_sql("SELECT supplier_code, supplier_name, category, approval_status, app_status, risk_level, annual_spend FROM suppliers WHERE notes LIKE ? ORDER BY category, supplier_name", (f"%{DEMO_TAG}%",)), "No expanded demo suppliers loaded.")
    with tabs[1]:
        show_df(df_sql("SELECT d.document_type, d.expiry_date, d.review_status, s.supplier_name FROM supplier_documents d LEFT JOIN suppliers s ON d.supplier_id=s.supplier_id WHERE d.notes LIKE ? ORDER BY s.supplier_name", (f"%{DEMO_TAG}%",)), "No expanded demo documents loaded.")
    with tabs[2]:
        show_df(df_sql("SELECT e.email_type, e.recipient, e.subject, e.status, s.supplier_name FROM email_log e LEFT JOIN suppliers s ON e.supplier_id=s.supplier_id WHERE e.subject LIKE ? ORDER BY e.sent_at DESC", (f"%{DEMO_TAG}%",)), "No expanded demo emails loaded.")
    with tabs[3]:
        show_df(df_sql("SELECT supplier_name, category, requested_by, expected_annual_spend, urgency, status FROM new_supplier_requests WHERE reason_needed LIKE ? ORDER BY created_at DESC", (f"%{DEMO_TAG}%",)), "No expanded demo onboarding rows loaded.")
    with tabs[4]:
        show_df(df_sql("SELECT supplier_code, supplier_name, action_type, old_value, new_value, status, action_reason FROM erp_action_queue WHERE action_reason LIKE ?", (f"%{DEMO_TAG}%",)), "No expanded demo ERP actions loaded.")
    with tabs[5]:
        show_df(df_sql("SELECT supplier_name, category, item_code, item_description, unit_price, lead_time_days FROM supplier_prices WHERE source_file='expanded_demo' ORDER BY category, item_code, supplier_name"), "No expanded demo prices loaded.")
    with tabs[6]:
        show_df(df_sql("SELECT supplier_name, item_code, po_number, po_date, promised_date, received_date, total_value FROM po_history WHERE source_file='expanded_demo' ORDER BY po_date DESC LIMIT 100"), "No expanded demo PO rows loaded.")


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
