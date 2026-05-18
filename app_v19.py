from pathlib import Path

import pandas as pd
import streamlit as st

# SupplierPass v0.19
# Keeps the grouped commercial navigation from v18, the supplier intelligence
# and ERP action queue from v17, and restores Document Management + Email Centre.

APP_VERSION = "v0.19 grouped navigation + documents + email"

source_path = Path(__file__).with_name("app_v17.py")
source_code = source_path.read_text(encoding="utf-8")
definitions = source_code.split("init_db(); style()", 1)[0]
namespace = {"__file__": str(source_path)}
exec(compile(definitions, str(source_path), "exec"), namespace)
namespace["APP_VERSION"] = APP_VERSION

init_db = namespace["init_db"]
style = namespace["style"]
dashboard = namespace["dashboard"]
supplier_register = namespace["supplier_register"]
preferred_suppliers_screen = namespace["preferred_suppliers_screen"]
data_uploads = namespace["data_uploads"]
supplier_intelligence = namespace["supplier_intelligence"]
erp_actions = namespace["erp_actions"]
reports = namespace["reports"]
hero = namespace["hero"]
hint = namespace["hint"]
show_df = namespace["show_df"]
df_sql = namespace["df_sql"]
exec_sql = namespace["exec_sql"]

DOCUMENT_STATUSES = ["Uploaded", "Under Review", "Accepted", "Rejected / Needs replacement", "Archived / Ignore"]
EMAIL_TYPES = [
    "Missing document request",
    "Expired document chase",
    "Document expiring soon",
    "Supplier information request",
    "Annual supplier review request",
    "Bank verification request",
    "General supplier message",
]


def ensure_document_email_schema():
    # These tables are intentionally small here. They restore the workflows that
    # were present in the fuller prototype while staying compatible with v17.
    exec_sql("""
        CREATE TABLE IF NOT EXISTS supplier_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            document_type TEXT,
            file_name TEXT,
            expiry_date TEXT,
            review_status TEXT DEFAULT 'Uploaded',
            reviewed_by TEXT,
            review_notes TEXT,
            notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT
        )
    """)
    exec_sql("""
        CREATE TABLE IF NOT EXISTS email_log (
            email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            email_type TEXT,
            recipient TEXT,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'Drafted',
            sent_by TEXT,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    exec_sql("""
        CREATE TABLE IF NOT EXISTS email_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type TEXT UNIQUE,
            subject TEXT,
            body TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    seed_email_templates()


def seed_email_templates():
    templates = [
        (
            "Missing document request",
            "Supplier document request - {supplier_name}",
            "Hi,\n\nWe are updating our approved supplier records for {supplier_name}.\n\nPlease send the following document(s):\n\n{document_list}\n\nMany thanks,\n{sender}",
        ),
        (
            "Expired document chase",
            "Expired supplier document - {supplier_name}",
            "Hi,\n\nOur records show the following document(s) for {supplier_name} have expired or need replacing:\n\n{document_list}\n\nPlease send updated copies as soon as possible.\n\nMany thanks,\n{sender}",
        ),
        (
            "Document expiring soon",
            "Supplier document expiring soon - {supplier_name}",
            "Hi,\n\nThe following document(s) for {supplier_name} are due to expire soon:\n\n{document_list}\n\nPlease send updated versions when available.\n\nMany thanks,\n{sender}",
        ),
        (
            "Supplier information request",
            "Supplier information request - {supplier_name}",
            "Hi,\n\nWe are reviewing our supplier records for {supplier_name}.\n\nPlease confirm your latest company details, key contact and compliance documents.\n\nMany thanks,\n{sender}",
        ),
        (
            "Annual supplier review request",
            "Annual supplier review - {supplier_name}",
            "Hi,\n\nWe are completing our annual supplier review for {supplier_name}.\n\nPlease confirm that your supplier details and compliance documents remain current.\n\nMany thanks,\n{sender}",
        ),
        (
            "Bank verification request",
            "Bank verification request - {supplier_name}",
            "Hi,\n\nAs part of our supplier controls, please confirm the correct finance contact for bank detail verification for {supplier_name}.\n\nMany thanks,\n{sender}",
        ),
        (
            "General supplier message",
            "Supplier query - {supplier_name}",
            "Hi,\n\nWe are contacting you about your supplier record for {supplier_name}.\n\n{custom_message}\n\nMany thanks,\n{sender}",
        ),
    ]
    for template_type, subject, body in templates:
        exec_sql(
            "INSERT OR IGNORE INTO email_templates (template_type, subject, body) VALUES (?, ?, ?)",
            (template_type, subject, body),
        )


def document_gap_table():
    docs = df_sql("""
        SELECT d.*, s.supplier_name, s.supplier_code, s.category, s.owner, s.supplier_email
        FROM supplier_documents d
        LEFT JOIN suppliers s ON d.supplier_id=s.supplier_id
        ORDER BY d.uploaded_at DESC
    """)
    if docs.empty:
        return docs
    docs = docs.copy()
    docs["Expiry Date Parsed"] = pd.to_datetime(docs["expiry_date"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    docs["Days Left"] = (docs["Expiry Date Parsed"] - today).dt.days
    def status_icon(row):
        if row["review_status"] == "Accepted" and pd.notna(row["Days Left"]) and row["Days Left"] >= 60:
            return "🟢"
        if row["review_status"] == "Accepted" and pd.notna(row["Days Left"]) and row["Days Left"] < 0:
            return "🔴"
        if row["review_status"] == "Rejected / Needs replacement":
            return "🔴"
        if row["review_status"] in ["Uploaded", "Under Review"]:
            return "🟠"
        return "⚪"
    docs["Icon"] = docs.apply(status_icon, axis=1)
    return docs


def document_management_screen():
    hero("Document Management", "Upload, review and chase supplier evidence.")
    hint("Accepted documents count as usable evidence. Uploaded and Under Review documents remain in the working queue. Rejected and archived documents are hidden by default.")

    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    tab_upload, tab_queue, tab_all, tab_gaps = st.tabs(["Upload Document", "Processing Queue", "All Documents", "Evidence Gaps"])

    with tab_upload:
        if suppliers.empty:
            st.info("Add suppliers first.")
        else:
            supplier_options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = supplier_options[st.selectbox("Supplier", list(supplier_options.keys()))]
            with st.form("document_upload_form"):
                doc_type = st.text_input("Document type", value="Public Liability Insurance")
                file_name = st.text_input("File name / reference")
                expiry = st.date_input("Expiry date", value=None)
                notes = st.text_area("Notes")
                if st.form_submit_button("Save document", type="primary"):
                    if not doc_type:
                        st.error("Document type is required.")
                    else:
                        exec_sql("""
                            INSERT INTO supplier_documents
                            (supplier_id, document_type, file_name, expiry_date, notes, review_status)
                            VALUES (?, ?, ?, ?, ?, 'Uploaded')
                        """, (sid, doc_type, file_name, expiry.isoformat() if expiry else None, notes))
                        st.success("Document saved and added to the processing queue.")
                        st.rerun()

    with tab_queue:
        queue = df_sql("""
            SELECT d.*, s.supplier_name, s.category, s.owner
            FROM supplier_documents d
            LEFT JOIN suppliers s ON d.supplier_id=s.supplier_id
            WHERE COALESCE(d.review_status, 'Uploaded') IN ('Uploaded', 'Under Review')
            ORDER BY d.uploaded_at DESC
        """)
        show_df(queue, "No documents waiting for review.")
        if not queue.empty:
            options = {f"{r['supplier_name']} - {r['document_type']} ({r['document_id']})": int(r["document_id"]) for _, r in queue.iterrows()}
            doc_id = options[st.selectbox("Select document to process", list(options.keys()))]
            doc = queue[queue["document_id"] == doc_id].iloc[0]
            st.write(f"**Supplier:** {doc['supplier_name']}")
            st.write(f"**Document:** {doc['document_type']}")
            st.write(f"**File/reference:** {doc['file_name'] or ''}")
            with st.form("process_document_form"):
                decision = st.selectbox("Decision", DOCUMENT_STATUSES, index=2)
                reviewed_by = st.text_input("Reviewed by")
                review_notes = st.text_area("Review notes")
                expiry = st.date_input("Confirmed expiry date", value=pd.to_datetime(doc["expiry_date"]).date() if pd.notna(doc["expiry_date"]) and str(doc["expiry_date"]) else None)
                if st.form_submit_button("Save review decision", type="primary"):
                    exec_sql("""
                        UPDATE supplier_documents
                        SET review_status=?, reviewed_by=?, review_notes=?, expiry_date=?, reviewed_at=CURRENT_TIMESTAMP
                        WHERE document_id=?
                    """, (decision, reviewed_by, review_notes, expiry.isoformat() if expiry else None, doc_id))
                    st.success("Document updated. It will leave the queue unless still Uploaded or Under Review.")
                    st.rerun()

    with tab_all:
        show_processed = st.checkbox("Include archived documents", value=False)
        where = "" if show_processed else "WHERE COALESCE(d.review_status,'') != 'Archived / Ignore'"
        docs = df_sql(f"""
            SELECT d.*, s.supplier_name, s.category, s.owner, s.supplier_email
            FROM supplier_documents d
            LEFT JOIN suppliers s ON d.supplier_id=s.supplier_id
            {where}
            ORDER BY d.uploaded_at DESC
        """)
        show_df(docs, "No documents yet.")

    with tab_gaps:
        gaps = document_gap_table()
        if gaps.empty:
            st.info("No documents to analyse yet.")
        else:
            gap_view = gaps[
                (gaps["review_status"].isin(["Uploaded", "Under Review", "Rejected / Needs replacement"])) |
                (gaps["Days Left"].notna() & (gaps["Days Left"] < 60))
            ]
            show_df(gap_view[["Icon", "supplier_name", "category", "document_type", "review_status", "expiry_date", "Days Left", "owner", "supplier_email"]], "No current document gaps.")


def build_document_list_for_email(supplier_id):
    docs = document_gap_table()
    if docs.empty:
        return "- Please confirm your latest supplier information and compliance documents."
    docs = docs[docs["supplier_id"] == supplier_id]
    docs = docs[
        (docs["review_status"].isin(["Uploaded", "Under Review", "Rejected / Needs replacement"])) |
        (docs["Days Left"].notna() & (docs["Days Left"] < 60))
    ]
    if docs.empty:
        return "- Please confirm your latest supplier information and compliance documents."
    rows = []
    for _, d in docs.iterrows():
        extra = f" - {d['review_status']}"
        if pd.notna(d.get("Days Left")):
            extra += f"; {int(d['Days Left'])} days left"
        rows.append(f"- {d['document_type']}{extra}")
    return "\n".join(rows)


def build_email(supplier, email_type, sender, custom_message):
    template = df_sql("SELECT * FROM email_templates WHERE template_type=?", (email_type,))
    if template.empty:
        subject = "Supplier query - {supplier_name}"
        body = "Hi,\n\n{custom_message}\n\nMany thanks,\n{sender}"
    else:
        subject = template.iloc[0]["subject"]
        body = template.iloc[0]["body"]
    replacements = {
        "{supplier_name}": supplier["supplier_name"] or "",
        "{document_list}": build_document_list_for_email(int(supplier["supplier_id"])),
        "{sender}": sender or "SupplierPass",
        "{custom_message}": custom_message or "",
    }
    for key, value in replacements.items():
        subject = subject.replace(key, value)
        body = body.replace(key, value)
    return subject, body


def email_centre_screen():
    hero("Email Centre", "Generate supplier chasers and log email activity.")
    hint("This prototype creates the email content and logs the chase. Direct sending can be added later with Microsoft Graph, SMTP or a transactional email provider.")

    tab_compose, tab_chase, tab_templates, tab_log = st.tabs(["Compose", "Chase Queue", "Templates", "Email Log"])
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")

    with tab_compose:
        if suppliers.empty:
            st.info("No suppliers yet.")
        else:
            options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = options[st.selectbox("Supplier", list(options.keys()))]
            supplier = suppliers[suppliers["supplier_id"] == sid].iloc[0]
            c1, c2 = st.columns(2)
            with c1:
                email_type = st.selectbox("Email type", EMAIL_TYPES)
                recipient = st.text_input("To", value=supplier["supplier_email"] or "")
                sender = st.text_input("From / signature", value=supplier["owner"] or "SupplierPass")
            with c2:
                docs = document_gap_table()
                gaps = docs[docs["supplier_id"] == sid] if not docs.empty else pd.DataFrame()
                show_df(gaps[["Icon", "document_type", "review_status", "expiry_date", "Days Left"]] if not gaps.empty else gaps, "No document history for this supplier yet.")
            custom_message = st.text_area("Custom message / extra notes")
            subject, body = build_email(supplier, email_type, sender, custom_message)
            subject = st.text_input("Subject", value=subject)
            body = st.text_area("Email body", value=body, height=300)
            st.caption("Copy the text into Outlook/Gmail, or use this as the basis for direct sending later.")
            c1, c2 = st.columns(2)
            if c1.button("Log as drafted"):
                exec_sql("""
                    INSERT INTO email_log (supplier_id, email_type, recipient, subject, body, status, sent_by)
                    VALUES (?, ?, ?, ?, ?, 'Drafted', ?)
                """, (sid, email_type, recipient, subject, body, sender))
                st.success("Email logged as drafted.")
            if c2.button("Mark as sent"):
                exec_sql("""
                    INSERT INTO email_log (supplier_id, email_type, recipient, subject, body, status, sent_by)
                    VALUES (?, ?, ?, ?, ?, 'Sent / manually recorded', ?)
                """, (sid, email_type, recipient, subject, body, sender))
                st.success("Email logged as sent.")

    with tab_chase:
        gaps = document_gap_table()
        if gaps.empty:
            st.info("No document gaps to chase yet.")
        else:
            chase = gaps[
                (gaps["review_status"].isin(["Uploaded", "Under Review", "Rejected / Needs replacement"])) |
                (gaps["Days Left"].notna() & (gaps["Days Left"] < 60))
            ]
            show_df(chase[["Icon", "supplier_name", "supplier_email", "document_type", "review_status", "expiry_date", "Days Left", "owner"]], "No chases currently needed.")

    with tab_templates:
        templates = df_sql("SELECT * FROM email_templates ORDER BY template_type")
        show_df(templates, "No templates yet.")
        template_type = st.selectbox("Template", EMAIL_TYPES)
        existing = df_sql("SELECT * FROM email_templates WHERE template_type=?", (template_type,))
        subject_value = existing.iloc[0]["subject"] if not existing.empty else ""
        body_value = existing.iloc[0]["body"] if not existing.empty else ""
        with st.form("edit_email_template"):
            subject = st.text_input("Subject", value=subject_value)
            body = st.text_area("Body", value=body_value, height=240)
            st.caption("Available fields: {supplier_name}, {document_list}, {sender}, {custom_message}")
            if st.form_submit_button("Save template"):
                exec_sql("""
                    INSERT INTO email_templates (template_type, subject, body, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(template_type)
                    DO UPDATE SET subject=excluded.subject, body=excluded.body, updated_at=CURRENT_TIMESTAMP
                """, (template_type, subject, body))
                st.success("Template saved.")
                st.rerun()

    with tab_log:
        log = df_sql("""
            SELECT e.*, s.supplier_name
            FROM email_log e
            LEFT JOIN suppliers s ON e.supplier_id=s.supplier_id
            ORDER BY e.sent_at DESC
        """)
        show_df(log, "No emails logged yet.")


def navigation_help():
    hero("SupplierPass Navigation", "A complete grouped workflow for supplier compliance, performance and ERP controls.")
    hint("Use the sidebar areas to move through the process: set up suppliers, manage documents, chase suppliers, upload ERP data, compare performance, queue ERP updates, then export reports.")
    st.markdown("""
    ### Suggested workflow

    **1. Supplier Setup**  
    Add suppliers, manage approval status, set inactive suppliers, and choose preferred suppliers by category.

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
    style()

    st.sidebar.markdown("# SupplierPass")
    st.sidebar.caption(APP_VERSION)

    area = st.sidebar.selectbox(
        "Area",
        [
            "🏠 Home",
            "🏢 Supplier Setup",
            "📄 Documents & Email",
            "🔄 ERP Data",
            "📊 Performance",
            "📁 Reports",
        ],
    )

    if area == "🏠 Home":
        page = st.sidebar.radio("Page", ["Dashboard", "How to use SupplierPass"])
        dashboard() if page == "Dashboard" else navigation_help()

    elif area == "🏢 Supplier Setup":
        page = st.sidebar.radio("Page", ["Suppliers", "Preferred by Category", "Supplier Controls"])
        if page == "Preferred by Category":
            preferred_suppliers_screen()
        else:
            supplier_register()

    elif area == "📄 Documents & Email":
        page = st.sidebar.radio("Page", ["Document Management", "Email Centre", "Evidence Chase Queue"])
        if page == "Email Centre":
            email_centre_screen()
        elif page == "Evidence Chase Queue":
            email_centre_screen()
        else:
            document_management_screen()

    elif area == "🔄 ERP Data":
        page = st.sidebar.radio("Page", ["Upload ERP Exports", "ERP Update Queue"])
        data_uploads() if page == "Upload ERP Exports" else erp_actions()

    elif area == "📊 Performance":
        page = st.sidebar.radio("Page", ["Supplier Scorecards", "Compare Suppliers", "Price Analysis", "OTIF Analysis", "Recommendation History"])
        supplier_intelligence()

    elif area == "📁 Reports":
        page = st.sidebar.radio("Page", ["Reports & Audit", "ERP Export Pack"])
        erp_actions() if page == "ERP Export Pack" else reports()


run_grouped_app()
