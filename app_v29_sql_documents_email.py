import pandas as pd
import streamlit as st

# Reuse the SQL-backed supplier setup from v28, then add SQL-backed documents + email.
source_file = "app_v28_sql_suppliers.py"
source_code = open(source_file, "r", encoding="utf-8").read()
definitions = source_code.rsplit("\ninitialise_database()", 1)[0]
namespace = {"__file__": source_file}
exec(compile(definitions, source_file, "exec"), namespace)

APP_VERSION = "v0.29 SQL-backed Documents + Email"

connection_summary = namespace["connection_summary"]
execute = namespace["execute"]
initialise_database = namespace["initialise_database"]
read_df = namespace["read_df"]
normalise_name = namespace["normalise_name"]
normalise_email = namespace["normalise_email"]
q = namespace["q"]
cols = namespace["cols"]
supplier_df = namespace["supplier_df"]
find_duplicate = namespace["find_duplicate"]
show_df = namespace["show_df"]
hero = namespace["hero"]
kpi = namespace["kpi"]
create_erp_action = namespace["create_erp_action"]
dashboard_screen = namespace["dashboard_screen"]
add_supplier_screen = namespace["add_supplier_screen"]
request_df = namespace["request_df"]
onboarding_screen = namespace["onboarding_screen"]
approval_queue_screen = namespace["approval_queue_screen"]
preferred_screen = namespace["preferred_screen"]
erp_actions_df = namespace["erp_actions_df"]
erp_action_queue_screen = namespace["erp_action_queue_screen"]
demo_data_screen = namespace["demo_data_screen"]
database_screen = namespace["database_screen"]

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


def is_sqlserver() -> bool:
    return connection_summary().get("mode") == "SQL Server"


def qt(name: str) -> str:
    if is_sqlserver():
        return {
            "documents": "dbo.SupplierDocuments",
            "email_log": "dbo.EmailLog",
            "email_templates": "dbo.EmailTemplates",
        }[name]
    return {
        "documents": "supplier_documents",
        "email_log": "email_log",
        "email_templates": "email_templates",
    }[name]


def dc(name: str) -> str:
    if is_sqlserver():
        return {
            "document_id": "DocumentID", "supplier_id": "SupplierID", "document_type": "DocumentType", "file_name": "FileName",
            "expiry_date": "ExpiryDate", "review_status": "ReviewStatus", "reviewed_by": "ReviewedBy", "review_notes": "ReviewNotes",
            "notes": "Notes", "uploaded_at": "UploadedAt", "reviewed_at": "ReviewedAt",
            "email_id": "EmailID", "email_type": "EmailType", "recipient": "Recipient", "subject": "Subject", "body": "Body",
            "status": "Status", "sent_by": "SentBy", "sent_at": "SentAt",
            "template_id": "TemplateID", "template_type": "TemplateType", "updated_at": "UpdatedAt",
        }[name]
    return {
        "document_id": "document_id", "supplier_id": "supplier_id", "document_type": "document_type", "file_name": "file_name",
        "expiry_date": "expiry_date", "review_status": "review_status", "reviewed_by": "reviewed_by", "review_notes": "review_notes",
        "notes": "notes", "uploaded_at": "uploaded_at", "reviewed_at": "reviewed_at",
        "email_id": "email_id", "email_type": "email_type", "recipient": "recipient", "subject": "subject", "body": "body",
        "status": "status", "sent_by": "sent_by", "sent_at": "sent_at",
        "template_id": "template_id", "template_type": "template_type", "updated_at": "updated_at",
    }[name]


def seed_email_templates():
    templates = [
        ("Missing document request", "Supplier document request - {supplier_name}", "Hi,\n\nWe are updating our supplier records for {supplier_name}.\n\nPlease send the following document(s):\n\n{document_list}\n\nMany thanks,\n{sender}"),
        ("Expired document chase", "Expired supplier document - {supplier_name}", "Hi,\n\nThe following document(s) have expired or need replacement:\n\n{document_list}\n\nPlease send updated copies as soon as possible.\n\nMany thanks,\n{sender}"),
        ("Document expiring soon", "Supplier document expiring soon - {supplier_name}", "Hi,\n\nThe following document(s) are due to expire soon:\n\n{document_list}\n\nPlease send updated versions when available.\n\nMany thanks,\n{sender}"),
        ("Supplier information request", "Supplier information request - {supplier_name}", "Hi,\n\nPlease confirm your latest company details, key contact and compliance documents for {supplier_name}.\n\nMany thanks,\n{sender}"),
        ("Annual supplier review request", "Annual supplier review - {supplier_name}", "Hi,\n\nWe are completing our annual supplier review for {supplier_name}. Please confirm your details and documents remain current.\n\nMany thanks,\n{sender}"),
        ("Bank verification request", "Bank verification request - {supplier_name}", "Hi,\n\nPlease confirm the correct finance contact for bank detail verification for {supplier_name}.\n\nMany thanks,\n{sender}"),
        ("General supplier message", "Supplier query - {supplier_name}", "Hi,\n\nWe are contacting you about your supplier record for {supplier_name}.\n\n{custom_message}\n\nMany thanks,\n{sender}"),
    ]
    for template_type, subject, body in templates:
        existing = read_df(f"SELECT {dc('template_id')} AS template_id FROM {qt('email_templates')} WHERE {dc('template_type')}=:template_type", {"template_type": template_type})
        if existing.empty:
            execute(
                f"INSERT INTO {qt('email_templates')} ({dc('template_type')}, {dc('subject')}, {dc('body')}) VALUES (:template_type, :subject, :body)",
                {"template_type": template_type, "subject": subject, "body": body},
            )


def document_df(include_archived=False) -> pd.DataFrame:
    sc = cols()
    where = "" if include_archived else f"WHERE COALESCE(d.{dc('review_status')}, '') <> 'Archived / Ignore'"
    df = read_df(f"""
        SELECT
            d.{dc('document_id')} AS document_id,
            d.{dc('supplier_id')} AS supplier_id,
            s.{sc['supplier_name']} AS supplier_name,
            s.{sc['supplier_code']} AS supplier_code,
            s.{sc['category']} AS category,
            s.{sc['owner']} AS owner,
            s.{sc['supplier_email']} AS supplier_email,
            d.{dc('document_type')} AS document_type,
            d.{dc('file_name')} AS file_name,
            d.{dc('expiry_date')} AS expiry_date,
            d.{dc('review_status')} AS review_status,
            d.{dc('reviewed_by')} AS reviewed_by,
            d.{dc('review_notes')} AS review_notes,
            d.{dc('notes')} AS notes,
            d.{dc('uploaded_at')} AS uploaded_at,
            d.{dc('reviewed_at')} AS reviewed_at
        FROM {qt('documents')} d
        LEFT JOIN {q('suppliers')} s ON d.{dc('supplier_id')} = s.{sc['supplier_id']}
        {where}
        ORDER BY d.{dc('uploaded_at')} DESC
    """)
    if df.empty:
        return df
    df["expiry_dt"] = pd.to_datetime(df["expiry_date"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    df["days_left"] = (df["expiry_dt"] - today).dt.days
    def icon(row):
        if row["review_status"] == "Accepted" and pd.notna(row["days_left"]) and row["days_left"] >= 60:
            return "🟢"
        if row["review_status"] == "Accepted" and pd.notna(row["days_left"]) and row["days_left"] < 60:
            return "🟠"
        if row["review_status"] == "Rejected / Needs replacement":
            return "🔴"
        if row["review_status"] in ["Uploaded", "Under Review"]:
            return "🟠"
        return "⚪"
    df["icon"] = df.apply(icon, axis=1)
    return df


def document_gaps_df() -> pd.DataFrame:
    docs = document_df(False)
    if docs.empty:
        return docs
    return docs[
        (docs["review_status"].isin(["Uploaded", "Under Review", "Rejected / Needs replacement"])) |
        (docs["days_left"].notna() & (docs["days_left"] < 60))
    ].copy()


def documents_screen():
    hero("Document Management", "SQL-backed supplier evidence upload, review and gap tracking.")
    suppliers = supplier_df()
    tab_upload, tab_queue, tab_all, tab_gaps = st.tabs(["Upload Document", "Processing Queue", "All Documents", "Evidence Gaps"])

    with tab_upload:
        if suppliers.empty:
            st.info("Add suppliers first.")
        else:
            options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = options[st.selectbox("Supplier", list(options.keys()))]
            with st.form("upload_doc_sql"):
                doc_type = st.text_input("Document type", value="Public Liability Insurance")
                file_name = st.text_input("File/reference")
                expiry = st.date_input("Expiry date", value=None)
                notes = st.text_area("Notes")
                if st.form_submit_button("Save document", type="primary"):
                    if not doc_type.strip():
                        st.error("Document type is required.")
                    else:
                        execute(
                            f"""
                            INSERT INTO {qt('documents')}
                            ({dc('supplier_id')}, {dc('document_type')}, {dc('file_name')}, {dc('expiry_date')}, {dc('review_status')}, {dc('notes')})
                            VALUES (:supplier_id, :document_type, :file_name, :expiry_date, 'Uploaded', :notes)
                            """,
                            {"supplier_id": sid, "document_type": doc_type, "file_name": file_name, "expiry_date": expiry.isoformat() if expiry else None, "notes": notes},
                        )
                        st.success("Document added to processing queue.")
                        st.rerun()

    with tab_queue:
        docs = document_df(False)
        queue = docs[docs["review_status"].isin(["Uploaded", "Under Review"])] if not docs.empty else docs
        show_df(queue[["icon", "document_id", "supplier_name", "document_type", "file_name", "expiry_date", "review_status", "owner"]] if not queue.empty else queue, "No documents waiting for review.")
        if not queue.empty:
            options = {f"{r['supplier_name']} - {r['document_type']} ({r['document_id']})": int(r["document_id"]) for _, r in queue.iterrows()}
            doc_id = options[st.selectbox("Document to process", list(options.keys()))]
            doc = queue[queue["document_id"] == doc_id].iloc[0]
            with st.form("review_doc_sql"):
                decision = st.selectbox("Decision", DOCUMENT_STATUSES, index=2)
                reviewed_by = st.text_input("Reviewed by")
                review_notes = st.text_area("Review notes")
                expiry_value = pd.to_datetime(doc["expiry_date"]).date() if pd.notna(doc["expiry_date"]) and str(doc["expiry_date"]) else None
                expiry = st.date_input("Confirmed expiry", value=expiry_value)
                if st.form_submit_button("Save review decision", type="primary"):
                    execute(
                        f"""
                        UPDATE {qt('documents')}
                        SET {dc('review_status')}=:decision,
                            {dc('reviewed_by')}=:reviewed_by,
                            {dc('review_notes')}=:review_notes,
                            {dc('expiry_date')}=:expiry_date,
                            {dc('reviewed_at')}=:reviewed_at
                        WHERE {dc('document_id')}=:document_id
                        """,
                        {"decision": decision, "reviewed_by": reviewed_by, "review_notes": review_notes, "expiry_date": expiry.isoformat() if expiry else None, "reviewed_at": pd.Timestamp.now().isoformat(timespec="seconds"), "document_id": doc_id},
                    )
                    st.success("Document updated.")
                    st.rerun()

    with tab_all:
        include_archived = st.checkbox("Include archived documents", value=False)
        docs = document_df(include_archived)
        show_df(docs[["icon", "document_id", "supplier_name", "category", "document_type", "file_name", "expiry_date", "days_left", "review_status", "reviewed_by"]] if not docs.empty else docs, "No documents yet.")

    with tab_gaps:
        gaps = document_gaps_df()
        show_df(gaps[["icon", "supplier_name", "supplier_email", "category", "document_type", "expiry_date", "days_left", "review_status", "owner"]] if not gaps.empty else gaps, "No evidence gaps.")


def build_document_list(supplier_id: int) -> str:
    gaps = document_gaps_df()
    if gaps.empty:
        return "- Please confirm your current supplier information and compliance documents."
    gaps = gaps[gaps["supplier_id"] == supplier_id]
    if gaps.empty:
        return "- Please confirm your current supplier information and compliance documents."
    rows = []
    for _, d in gaps.iterrows():
        detail = f"- {d['document_type']} ({d['review_status']})"
        if pd.notna(d.get("days_left")):
            detail += f" - {int(d['days_left'])} days left"
        rows.append(detail)
    return "\n".join(rows)


def build_email_body(supplier, email_type, sender, custom_message):
    template = read_df(f"SELECT * FROM {qt('email_templates')} WHERE {dc('template_type')}=:template_type", {"template_type": email_type})
    if template.empty:
        subject = "Supplier query - {supplier_name}"
        body = "Hi,\n\n{custom_message}\n\nMany thanks,\n{sender}"
    else:
        row = template.iloc[0]
        subject = row[dc("subject")]
        body = row[dc("body")]
    replacements = {
        "{supplier_name}": supplier["supplier_name"],
        "{document_list}": build_document_list(int(supplier["supplier_id"])),
        "{sender}": sender or "SupplierPass",
        "{custom_message}": custom_message or "",
    }
    for k, v in replacements.items():
        subject = str(subject).replace(k, v)
        body = str(body).replace(k, v)
    return subject, body


def email_log_df() -> pd.DataFrame:
    sc = cols()
    return read_df(f"""
        SELECT
            e.{dc('email_id')} AS email_id,
            e.{dc('supplier_id')} AS supplier_id,
            s.{sc['supplier_name']} AS supplier_name,
            e.{dc('email_type')} AS email_type,
            e.{dc('recipient')} AS recipient,
            e.{dc('subject')} AS subject,
            e.{dc('body')} AS body,
            e.{dc('status')} AS status,
            e.{dc('sent_by')} AS sent_by,
            e.{dc('sent_at')} AS sent_at
        FROM {qt('email_log')} e
        LEFT JOIN {q('suppliers')} s ON e.{dc('supplier_id')} = s.{sc['supplier_id']}
        ORDER BY e.{dc('sent_at')} DESC
    """)


def email_centre_screen():
    hero("Email Centre", "SQL-backed supplier chasers, templates and email log.")
    seed_email_templates()
    suppliers = supplier_df()
    tab_compose, tab_chase, tab_templates, tab_log = st.tabs(["Compose", "Chase Queue", "Templates", "Email Log"])

    with tab_compose:
        if suppliers.empty:
            st.info("Add suppliers first.")
        else:
            options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = options[st.selectbox("Supplier", list(options.keys()))]
            supplier = suppliers[suppliers["supplier_id"] == sid].iloc[0]
            a, b = st.columns(2)
            with a:
                email_type = st.selectbox("Email type", EMAIL_TYPES)
                recipient = st.text_input("To", value=supplier["supplier_email"] or "")
                sender = st.text_input("From / signature", value=supplier["owner"] or "SupplierPass")
            with b:
                gaps = document_gaps_df()
                supplier_gaps = gaps[gaps["supplier_id"] == sid] if not gaps.empty else gaps
                show_df(supplier_gaps[["icon", "document_type", "expiry_date", "days_left", "review_status"]] if not supplier_gaps.empty else supplier_gaps, "No current document gaps for this supplier.")
            custom = st.text_area("Custom message / extra notes")
            subject, body = build_email_body(supplier, email_type, sender, custom)
            subject = st.text_input("Subject", value=subject)
            body = st.text_area("Email body", value=body, height=320)
            c1, c2 = st.columns(2)
            if c1.button("Log as drafted"):
                execute(
                    f"""
                    INSERT INTO {qt('email_log')}
                    ({dc('supplier_id')}, {dc('email_type')}, {dc('recipient')}, {dc('subject')}, {dc('body')}, {dc('status')}, {dc('sent_by')})
                    VALUES (:supplier_id, :email_type, :recipient, :subject, :body, 'Drafted', :sent_by)
                    """,
                    {"supplier_id": sid, "email_type": email_type, "recipient": recipient, "subject": subject, "body": body, "sent_by": sender},
                )
                st.success("Email logged as drafted.")
            if c2.button("Mark as sent"):
                execute(
                    f"""
                    INSERT INTO {qt('email_log')}
                    ({dc('supplier_id')}, {dc('email_type')}, {dc('recipient')}, {dc('subject')}, {dc('body')}, {dc('status')}, {dc('sent_by')})
                    VALUES (:supplier_id, :email_type, :recipient, :subject, :body, 'Sent / manually recorded', :sent_by)
                    """,
                    {"supplier_id": sid, "email_type": email_type, "recipient": recipient, "subject": subject, "body": body, "sent_by": sender},
                )
                st.success("Email logged as sent.")

    with tab_chase:
        gaps = document_gaps_df()
        show_df(gaps[["icon", "supplier_name", "supplier_email", "document_type", "expiry_date", "days_left", "review_status", "owner"]] if not gaps.empty else gaps, "No supplier chases needed.")

    with tab_templates:
        templates = read_df(f"SELECT * FROM {qt('email_templates')} ORDER BY {dc('template_type')}")
        show_df(templates, "No templates yet.")
        template_type = st.selectbox("Template", EMAIL_TYPES)
        existing = read_df(f"SELECT * FROM {qt('email_templates')} WHERE {dc('template_type')}=:template_type", {"template_type": template_type})
        subject_value = existing.iloc[0][dc("subject")] if not existing.empty else ""
        body_value = existing.iloc[0][dc("body")] if not existing.empty else ""
        with st.form("template_edit"):
            subject = st.text_input("Subject", value=subject_value)
            body = st.text_area("Body", value=body_value, height=250)
            st.caption("Available fields: {supplier_name}, {document_list}, {sender}, {custom_message}")
            if st.form_submit_button("Save template", type="primary"):
                if existing.empty:
                    execute(
                        f"INSERT INTO {qt('email_templates')} ({dc('template_type')}, {dc('subject')}, {dc('body')}) VALUES (:template_type, :subject, :body)",
                        {"template_type": template_type, "subject": subject, "body": body},
                    )
                else:
                    execute(
                        f"UPDATE {qt('email_templates')} SET {dc('subject')}=:subject, {dc('body')}=:body WHERE {dc('template_type')}=:template_type",
                        {"template_type": template_type, "subject": subject, "body": body},
                    )
                st.success("Template saved.")
                st.rerun()

    with tab_log:
        show_df(email_log_df(), "No emails logged yet.")


def sql_documents_demo_screen():
    hero("SQL Documents Demo", "Load fictional document and email queue data into the active database.")
    suppliers = supplier_df()
    if suppliers.empty:
        st.info("Load supplier demo data first from SQL Demo Data.")
        return
    if st.button("Load document/email demo", type="primary"):
        for _, s in suppliers.head(5).iterrows():
            sid = int(s["supplier_id"])
            execute(
                f"""
                INSERT INTO {qt('documents')}
                ({dc('supplier_id')}, {dc('document_type')}, {dc('file_name')}, {dc('expiry_date')}, {dc('review_status')}, {dc('notes')})
                VALUES (:supplier_id, 'Public Liability Insurance', :file_name, '2026-04-30', 'Uploaded', 'SQL document demo')
                """,
                {"supplier_id": sid, "file_name": f"PLI - {s['supplier_name']}.pdf"},
            )
        seed_email_templates()
        st.success("Document/email demo loaded.")
        st.rerun()
    show_df(document_df(False), "No documents yet.")


initialise_database()

st.sidebar.markdown("# SupplierPass")
st.sidebar.caption(APP_VERSION)
area = st.sidebar.selectbox(
    "Area",
    [
        "Dashboard",
        "Database",
        "SQL Demo Data",
        "SQL Documents Demo",
        "Suppliers",
        "Supplier Onboarding",
        "Approval Queue",
        "Preferred Suppliers",
        "Document Management",
        "Email Centre",
        "ERP Action Queue",
    ],
)

if area == "Dashboard":
    dashboard_screen()
elif area == "Database":
    database_screen()
elif area == "SQL Demo Data":
    demo_data_screen()
elif area == "SQL Documents Demo":
    sql_documents_demo_screen()
elif area == "Suppliers":
    add_supplier_screen()
elif area == "Supplier Onboarding":
    onboarding_screen()
elif area == "Approval Queue":
    approval_queue_screen()
elif area == "Preferred Suppliers":
    preferred_screen()
elif area == "Document Management":
    documents_screen()
elif area == "Email Centre":
    email_centre_screen()
elif area == "ERP Action Queue":
    erp_action_queue_screen()
