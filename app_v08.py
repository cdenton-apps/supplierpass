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

APP_VERSION = "v0.8 stable commercial polish"
SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
ISSUE_TYPES = ["Quality", "Delivery", "Pricing", "Service", "Compliance", "Finance", "Other"]
ISSUE_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]
IMPORT_PROFILES = {
    "Generic CSV": {
        "Supplier Name": ["SupplierName", "Supplier Name", "Name"],
        "Supplier Code": ["SupplierCode", "Supplier Code", "Code"],
        "Email": ["SupplierEmail", "Email", "Email Address"],
    },
    "Sage 200 Supplier Export": {
        "Supplier Name": ["SupplierAccountName", "Supplier Name", "Name"],
        "Supplier Code": ["SupplierAccountNumber", "AccountNumber", "Code"],
        "Email": ["EmailAddress", "Email"],
    },
    "Sage 50 Supplier Export": {
        "Supplier Name": ["Name", "Supplier Name"],
        "Supplier Code": ["A/C", "Account", "Supplier Code"],
        "Email": ["E-mail", "Email"],
    },
    "Business Central Vendor Export": {
        "Supplier Name": ["Name", "Vendor Name"],
        "Supplier Code": ["No.", "Vendor No."],
        "Email": ["Email"],
    },
    "Xero Contacts Export": {
        "Supplier Name": ["ContactName", "Name"],
        "Supplier Code": ["ContactID", "AccountNumber"],
        "Email": ["EmailAddress", "Email"],
    },
}


# -----------------------------
# Database helpers
# -----------------------------

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


# -----------------------------
# Database schema
# -----------------------------

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
            annual_spend REAL DEFAULT 0,
            criticality TEXT DEFAULT 'Standard',
            company_number TEXT,
            vat_number TEXT,
            website TEXT,
            company_status TEXT DEFAULT 'Not checked',
            vat_status TEXT DEFAULT 'Not checked',
            sanctions_status TEXT DEFAULT 'Not checked',
            bank_verification_status TEXT DEFAULT 'Not started',
            last_reviewed TEXT,
            next_review_date TEXT,
            review_frequency_months INTEGER DEFAULT 12,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT,
            file_path TEXT,
            expiry_date TEXT,
            reviewed_by TEXT,
            review_status TEXT DEFAULT 'Uploaded',
            notes TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            company_number TEXT,
            vat_number TEXT,
            website TEXT,
            company_status TEXT DEFAULT 'Not checked',
            vat_status TEXT DEFAULT 'Not checked',
            sanctions_status TEXT DEFAULT 'Not checked',
            supplier_confidence TEXT DEFAULT 'Not checked',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            request_id INTEGER,
            event_type TEXT,
            event_detail TEXT,
            user TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_type TEXT UNIQUE,
            subject TEXT,
            body TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.commit()
    c.close()

    migrations = {
        "suppliers": {
            "criticality": "TEXT DEFAULT 'Standard'",
            "company_number": "TEXT",
            "vat_number": "TEXT",
            "website": "TEXT",
            "company_status": "TEXT DEFAULT 'Not checked'",
            "vat_status": "TEXT DEFAULT 'Not checked'",
            "sanctions_status": "TEXT DEFAULT 'Not checked'",
            "bank_verification_status": "TEXT DEFAULT 'Not started'",
            "last_reviewed": "TEXT",
            "next_review_date": "TEXT",
            "review_frequency_months": "INTEGER DEFAULT 12",
        },
        "supplier_documents": {
            "reviewed_by": "TEXT",
            "review_status": "TEXT DEFAULT 'Uploaded'",
        },
        "new_supplier_requests": {
            "company_number": "TEXT",
            "vat_number": "TEXT",
            "website": "TEXT",
            "company_status": "TEXT DEFAULT 'Not checked'",
            "vat_status": "TEXT DEFAULT 'Not checked'",
            "sanctions_status": "TEXT DEFAULT 'Not checked'",
            "supplier_confidence": "TEXT DEFAULT 'Not checked'",
        },
    }
    for table, cols in migrations.items():
        for column, definition in cols.items():
            ensure_column(table, column, definition)

    seed_defaults()


def seed_defaults():
    doc_rows = [
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
    many_sql(
        "INSERT OR IGNORE INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)",
        doc_rows,
    )

    template_rows = [
        (
            "Missing document request",
            "Supplier document request - {document_type}",
            "Hi {supplier_name},\n\nWe are updating our approved supplier records and need the following document from you:\n\n{document_type}\n\nReason: {issue}\n\nPlease send the latest version, including the expiry date where applicable.\n\nMany thanks,\n{sender}",
        ),
        (
            "Annual supplier review request",
            "Annual supplier review due - {supplier_name}",
            "Hi {owner},\n\nThe supplier {supplier_name} is due for review. Please check documents, risk, ownership and approval status.\n\nThanks,\nSupplierPass",
        ),
        (
            "Bank verification request",
            "Bank verification required - {supplier_name}",
            "Hi Finance,\n\nPlease verify bank details for {supplier_name}.\n\nThanks,\nSupplierPass",
        ),
    ]
    many_sql(
        "INSERT OR IGNORE INTO email_templates (template_type, subject, body) VALUES (?, ?, ?)",
        template_rows,
    )


# -----------------------------
# UI helpers
# -----------------------------

def apply_style():
    st.markdown(
        """
        <style>
        .block-container{padding-top:1rem}
        .hero{border-radius:22px;padding:24px 28px;background:linear-gradient(135deg,#0f172a,#1d4ed8 55%,#0f766e);color:white;margin-bottom:18px}
        .hero h1{margin:0;color:white}.hero p{color:#dbeafe}
        .kpi{border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff}
        .lab{font-size:.82rem;color:#64748b}.val{font-size:1.6rem;font-weight:750}.sub{font-size:.8rem;color:#64748b}
        .pill{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:650;font-size:.82rem}
        .green{background:#dcfce7;color:#166534}.amber{background:#fef3c7;color:#92400e}.red{background:#fee2e2;color:#991b1b}.blue{background:#dbeafe;color:#1e40af}.grey{background:#f1f5f9;color:#334155}
        [data-testid="stSidebar"]{background:#0f172a}[data-testid="stSidebar"] *{color:#f8fafc!important}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title, subtitle):
    st.markdown(f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def kpi(label, value, sub=""):
    st.markdown(
        f"<div class='kpi'><div class='lab'>{label}</div><div class='val'>{value}</div><div class='sub'>{sub}</div></div>",
        unsafe_allow_html=True,
    )


def status_class(value):
    if value in ["Can Buy", "Approved", "Green", "Low", "Resolved", "Closed"]:
        return "green"
    if value in ["Can Buy with Warning", "Amber", "Pending", "Medium", "In Progress"]:
        return "amber"
    if value in ["Do Not Use", "Red", "Blocked", "High", "Critical", "Rejected"]:
        return "red"
    if value in ["Approval Pending", "Dormant", "Draft", "Open"]:
        return "blue"
    return "grey"


def pill(value):
    return f"<span class='pill {status_class(value)}'>{value}</span>"


def show_df(df, empty_message="No records found."):
    if df is None or df.empty:
        st.info(empty_message)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


# -----------------------------
# Business logic
# -----------------------------

def categories():
    df = df_sql(
        """
        SELECT DISTINCT category FROM suppliers
        UNION SELECT DISTINCT category FROM document_rules
        UNION SELECT DISTINCT category FROM new_supplier_requests
        ORDER BY category
        """
    )
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def parse_date(value):
    try:
        if value is None or value == "" or pd.isna(value):
            return None
        return pd.to_datetime(value).date()
    except Exception:
        return None


def days_left(value):
    d = parse_date(value)
    if d is None:
        return None
    return (d - date.today()).days


def document_status(expiry, warning=60, missing=False, critical=True):
    if missing:
        return "Red" if critical else "Amber"
    d = days_left(expiry)
    if d is None:
        return "Amber"
    if d < 0:
        return "Red"
    if d <= int(warning or 60):
        return "Amber"
    return "Green"


def supplier_checklist(supplier):
    rules = df_sql("SELECT * FROM document_rules WHERE category=?", (supplier["category"] or "",))
    docs = df_sql("SELECT * FROM supplier_documents WHERE supplier_id=?", (supplier["supplier_id"],))
    rows = []
    for _, rule in rules.iterrows():
        matching = docs[docs["document_type"] == rule["document_type"]]
        if matching.empty:
            rows.append(
                {
                    "Document Type": rule["document_type"],
                    "Status": document_status(None, rule["warning_days"], True, bool(rule["is_critical"])),
                    "Issue": "Missing document",
                    "Expiry Date": "",
                    "Days Left": "",
                }
            )
        else:
            latest = matching.sort_values("uploaded_at", ascending=False).iloc[0]
            status = document_status(latest["expiry_date"], rule["warning_days"], False, bool(rule["is_critical"]))
            issue = ""
            if status == "Red":
                issue = "Expired document"
            elif status == "Amber":
                issue = "Expiring soon"
            rows.append(
                {
                    "Document Type": rule["document_type"],
                    "Status": status,
                    "Issue": issue,
                    "Expiry Date": latest["expiry_date"] or "",
                    "Days Left": days_left(latest["expiry_date"]) if days_left(latest["expiry_date"]) is not None else "",
                }
            )
    return pd.DataFrame(rows)


def supplier_readiness(supplier):
    checklist = supplier_checklist(supplier)
    missing = int((checklist["Issue"] == "Missing document").sum()) if not checklist.empty else 0
    expired = int((checklist["Issue"] == "Expired document").sum()) if not checklist.empty else 0
    expiring = int((checklist["Issue"] == "Expiring soon").sum()) if not checklist.empty else 0

    issues = df_sql(
        "SELECT * FROM supplier_issues WHERE supplier_id=? AND status NOT IN ('Resolved','Closed')",
        (supplier["supplier_id"],),
    )
    high_issues = 0
    if not issues.empty:
        high_issues = len(issues[issues["severity"].isin(["High", "Critical"])])

    score = 100 - missing * 18 - expired * 25 - expiring * 8 - high_issues * 15
    if supplier["approval_status"] == "Blocked":
        score -= 40
    score = max(0, min(100, score))

    if supplier["approval_status"] == "Blocked" or expired > 0 or high_issues > 0:
        buy_status = "Do Not Use"
    elif supplier["approval_status"] in ["Pending", "On Hold"]:
        buy_status = "Approval Pending"
    elif supplier["approval_status"] == "Dormant":
        buy_status = "Dormant"
    elif missing > 0 or expiring > 0:
        buy_status = "Can Buy with Warning"
    else:
        buy_status = "Can Buy"

    reasons = []
    if missing:
        reasons.append(f"{missing} missing document(s)")
    if expired:
        reasons.append(f"{expired} expired document(s)")
    if expiring:
        reasons.append(f"{expiring} document(s) expiring soon")
    if high_issues:
        reasons.append(f"{high_issues} high/critical open issue(s)")
    if supplier["approval_status"] != "Approved":
        reasons.append(f"Approval status is {supplier['approval_status']}")

    return score, buy_status, reasons, missing, expired, expiring


def supplier_table():
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    rows = []
    for _, supplier in suppliers.iterrows():
        score, buy_status, reasons, missing, expired, expiring = supplier_readiness(supplier)
        rows.append(
            {
                "Supplier ID": supplier["supplier_id"],
                "Supplier Code": supplier["supplier_code"],
                "Supplier Name": supplier["supplier_name"],
                "Can I Buy?": buy_status,
                "Readiness": score,
                "Reasons": "; ".join(reasons),
                "Email": supplier["supplier_email"],
                "Category": supplier["category"],
                "Owner": supplier["owner"],
                "Approval Status": supplier["approval_status"],
                "Risk": supplier["risk_level"],
                "Spend": supplier["annual_spend"] or 0,
                "Missing Docs": missing,
                "Expired Docs": expired,
                "Expiring Soon": expiring,
                "Next Review": supplier["next_review_date"],
            }
        )
    return pd.DataFrame(rows)


def evidence_gaps():
    rows = []
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    for _, supplier in suppliers.iterrows():
        checklist = supplier_checklist(supplier)
        if not checklist.empty:
            problem_docs = checklist[checklist["Status"].isin(["Red", "Amber"])]
            for _, doc in problem_docs.iterrows():
                rows.append(
                    {
                        "Supplier ID": supplier["supplier_id"],
                        "Supplier Name": supplier["supplier_name"],
                        "Gap": doc["Issue"],
                        "Severity": doc["Status"],
                        "Owner": supplier["owner"],
                        "Detail": doc["Document Type"],
                        "Action": "Chase supplier",
                    }
                )
        if not supplier["owner"]:
            rows.append(
                {
                    "Supplier ID": supplier["supplier_id"],
                    "Supplier Name": supplier["supplier_name"],
                    "Gap": "Missing owner",
                    "Severity": "Amber",
                    "Owner": "",
                    "Detail": "No internal owner",
                    "Action": "Assign owner",
                }
            )
        review_date = parse_date(supplier["next_review_date"])
        if review_date and review_date < date.today():
            rows.append(
                {
                    "Supplier ID": supplier["supplier_id"],
                    "Supplier Name": supplier["supplier_name"],
                    "Gap": "Review overdue",
                    "Severity": "Amber",
                    "Owner": supplier["owner"],
                    "Detail": supplier["next_review_date"],
                    "Action": "Complete supplier review",
                }
            )
    return pd.DataFrame(rows)


def audit_score():
    suppliers = supplier_table()
    gaps = evidence_gaps()
    if suppliers.empty:
        return 0, ["No suppliers loaded"]
    score = 100
    reasons = []
    if len(gaps):
        score -= min(40, len(gaps) * 3)
        reasons.append(f"{len(gaps)} evidence gap(s)")
    do_not = len(suppliers[suppliers["Can I Buy?"] == "Do Not Use"])
    if do_not:
        score -= do_not * 8
        reasons.append(f"{do_not} Do Not Use supplier(s)")
    no_owner = len(suppliers[suppliers["Owner"].fillna("") == ""])
    if no_owner:
        score -= no_owner * 3
        reasons.append(f"{no_owner} supplier(s) without owner")
    return max(0, min(100, score)), reasons


def data_quality():
    suppliers = df_sql("SELECT * FROM suppliers")
    rows = []
    if suppliers.empty:
        return pd.DataFrame()
    for _, supplier in suppliers.iterrows():
        if not supplier["supplier_email"]:
            rows.append({"Issue": "Missing supplier email", "Supplier": supplier["supplier_name"], "Severity": "Amber"})
        if not supplier["category"]:
            rows.append({"Issue": "Missing category", "Supplier": supplier["supplier_name"], "Severity": "Amber"})
        if not supplier["owner"]:
            rows.append({"Issue": "Missing owner", "Supplier": supplier["supplier_name"], "Severity": "Amber"})
    duplicates = suppliers[suppliers.duplicated("supplier_name", keep=False)]
    for _, supplier in duplicates.iterrows():
        rows.append({"Issue": "Possible duplicate supplier", "Supplier": supplier["supplier_name"], "Severity": "Amber"})
    return pd.DataFrame(rows)


def add_timeline(supplier_id=None, request_id=None, event_type="", detail="", user=""):
    exec_sql(
        "INSERT INTO supplier_timeline (supplier_id, request_id, event_type, event_detail, user) VALUES (?, ?, ?, ?, ?)",
        (supplier_id, request_id, event_type, detail, user),
    )


def load_demo_data():
    suppliers = [
        ("SUP001", "ABC Transport Ltd", "accounts@abctransport.co.uk", "Transport", "Connor", "Approved", "Medium", 85000, "Important"),
        ("SUP002", "Yorkshire Board Supplies", "quality@yorkshireboard.co.uk", "Manufacturing", "Quality", "Approved", "High", 120000, "Critical"),
        ("SUP003", "Fast Fix Maintenance", "fastfix@gmail.com", "Contractor", "Maintenance", "Pending", "Medium", 14000, "Standard"),
        ("SUP004", "CloudOps Software", "security@cloudops.co.uk", "IT / Software", "IT", "On Hold", "High", 42000, "Important"),
        ("SUP005", "LabelCo Print Ltd", "hello@labelco.co.uk", "Packaging", "Procurement", "Approved", "Low", 22000, "Standard"),
    ]
    many_sql(
        """
        INSERT INTO suppliers
        (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend, criticality)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        suppliers,
    )
    st.success("Demo data loaded.")


# -----------------------------
# Screens
# -----------------------------

def today_screen():
    hero("Today in SupplierPass", "One place to see what needs chasing, approving and fixing.")
    suppliers = supplier_table()
    gaps = evidence_gaps()
    requests = df_sql("SELECT * FROM new_supplier_requests")
    score, reasons = audit_score()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Audit readiness", f"{score}%", "; ".join(reasons[:2]) or "healthy")
    with c2:
        blocked_count = len(suppliers[suppliers["Can I Buy?"] == "Do Not Use"]) if not suppliers.empty else 0
        kpi("Do Not Use", blocked_count, "supplier blocks")
    with c3:
        open_approvals = 0
        if not requests.empty:
            open_approvals = int((~requests["status"].isin(["Approved", "Rejected"])).sum())
        kpi("Open approvals", open_approvals, "requests")
    with c4:
        kpi("Evidence gaps", len(gaps), "actions")

    if suppliers.empty:
        st.warning("No suppliers loaded yet.")
        if st.button("Load demo data"):
            load_demo_data()
            st.rerun()

    st.subheader("Priorities")
    if gaps.empty:
        st.success("No priority evidence gaps found.")
    else:
        st.dataframe(gaps.head(20), use_container_width=True, hide_index=True)


def role_views():
    hero("Role Views", "Tailored dashboards for Management, Procurement, Quality and Finance.")
    role = st.radio("View", ["Management", "Procurement", "Quality", "Finance", "Admin"], horizontal=True)
    suppliers = supplier_table()
    gaps = evidence_gaps()
    requests = df_sql("SELECT * FROM new_supplier_requests")

    if role == "Management":
        st.subheader("Management summary")
        score, reasons = audit_score()
        kpi("Audit readiness", f"{score}%", "; ".join(reasons) or "No deductions")
        if suppliers.empty:
            st.info("No suppliers")
        else:
            st.dataframe(suppliers.sort_values("Readiness").head(20), use_container_width=True, hide_index=True)
    elif role == "Procurement":
        st.subheader("Procurement queue")
        if gaps.empty:
            st.info("No procurement actions")
        else:
            procurement_gaps = gaps[gaps["Action"].str.contains("Chase|Assign", na=False)]
            st.dataframe(procurement_gaps, use_container_width=True, hide_index=True)
        if requests.empty:
            st.info("No supplier requests")
        else:
            st.dataframe(requests[~requests["status"].isin(["Approved", "Rejected"])], use_container_width=True, hide_index=True)
    elif role == "Quality":
        st.subheader("Quality evidence")
        if gaps.empty:
            st.info("No quality evidence gaps")
        else:
            quality_gaps = gaps[gaps["Detail"].str.contains("ISO|BRC|FSC|Questionnaire|Certificate", case=False, na=False)]
            st.dataframe(quality_gaps, use_container_width=True, hide_index=True)
    elif role == "Finance":
        st.subheader("Finance controls")
        if suppliers.empty:
            st.info("No suppliers")
        else:
            finance_view = suppliers[(suppliers["Spend"] > 50000) | (suppliers["Can I Buy?"] != "Can Buy")]
            st.dataframe(finance_view, use_container_width=True, hide_index=True)
    else:
        st.subheader("Admin data quality")
        show_df(data_quality(), "No data quality issues found.")


def suppliers_screen():
    hero("Supplier Register", "Import, segment and manage supplier profiles.")
    tab_import, tab_register, tab_profile, tab_portal = st.tabs(["Import", "Register", "Profile", "Portal Preview"])

    with tab_import:
        profile = st.selectbox("Import profile", list(IMPORT_PROFILES.keys()))
        st.caption("Profiles are pre-mapping helpers for common exports. You can still override every column.")
        file = st.file_uploader("Supplier CSV", type=["csv"])
        if file:
            data = pd.read_csv(file)
            cols = data.columns.tolist()
            st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            guesses = IMPORT_PROFILES[profile]

            def guess(names):
                for name in names:
                    if name in cols:
                        return name
                return ""

            c1, c2, c3 = st.columns(3)
            code_guess = guess(guesses["Supplier Code"])
            name_guess = guess(guesses["Supplier Name"])
            email_guess = guess(guesses["Email"])
            code_options = [""] + cols
            c_code = c1.selectbox("Supplier Code", code_options, index=code_options.index(code_guess) if code_guess in code_options else 0)
            c_name = c1.selectbox("Supplier Name *", cols, index=cols.index(name_guess) if name_guess in cols else 0)
            c_email = c1.selectbox("Email", code_options, index=code_options.index(email_guess) if email_guess in code_options else 0)
            c_cat = c2.selectbox("Category", code_options)
            c_owner = c2.selectbox("Owner", code_options)
            c_status = c2.selectbox("Status", code_options)
            c_spend = c3.selectbox("Annual Spend", code_options)
            default_cat = c3.selectbox("Default category", [""] + categories())

            if st.button("Import suppliers", type="primary"):
                rows = []
                for _, r in data.iterrows():
                    supplier_name = str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not supplier_name:
                        continue
                    try:
                        spend = float(r[c_spend]) if c_spend and pd.notna(r[c_spend]) else 0
                    except Exception:
                        spend = 0
                    rows.append(
                        (
                            str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else "",
                            supplier_name,
                            str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "",
                            str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else default_cat,
                            str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "",
                            str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved",
                            "Medium",
                            spend,
                        )
                    )
                many_sql(
                    """
                    INSERT INTO suppliers
                    (supplier_code, supplier_name, supplier_email, category, owner, approval_status, risk_level, annual_spend)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                st.success(f"Imported {len(rows)} suppliers.")
                st.rerun()

    with tab_register:
        show_df(supplier_table(), "No suppliers yet.")

    with tab_profile:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers yet.")
        else:
            options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            selected = st.selectbox("Supplier", list(options.keys()))
            supplier_id = options[selected]
            supplier = df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).iloc[0]
            score, buy_status, reasons, _, _, _ = supplier_readiness(supplier)
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi("Can I Buy?", buy_status, "; ".join(reasons) or "No blocking issues")
            with c2:
                kpi("Readiness", f"{score}%", "supplier score")
            with c3:
                kpi("Next review", supplier["next_review_date"] or "Not set", "review cycle")

            with st.form("edit_supplier"):
                a, b, c = st.columns(3)
                name = a.text_input("Name", supplier["supplier_name"])
                email = a.text_input("Email", supplier["supplier_email"] or "")
                category_options = [""] + categories()
                category_index = category_options.index(supplier["category"] or "") if (supplier["category"] or "") in category_options else 0
                category = b.selectbox("Category", category_options, index=category_index)
                owner = b.text_input("Owner", supplier["owner"] or "")
                status_index = SUPPLIER_STATUSES.index(supplier["approval_status"]) if supplier["approval_status"] in SUPPLIER_STATUSES else 0
                status = b.selectbox("Status", SUPPLIER_STATUSES, index=status_index)
                risk_index = RISK_LEVELS.index(supplier["risk_level"]) if supplier["risk_level"] in RISK_LEVELS else 1
                risk = c.selectbox("Risk", RISK_LEVELS, index=risk_index)
                spend = c.number_input("Spend", value=float(supplier["annual_spend"] or 0), min_value=0.0, step=100.0)
                next_review = c.date_input(
                    "Next review",
                    value=parse_date(supplier["next_review_date"]) or date.today() + timedelta(days=365),
                )
                notes = st.text_area("Notes", supplier["notes"] or "")
                if st.form_submit_button("Save"):
                    exec_sql(
                        """
                        UPDATE suppliers
                        SET supplier_name=?, supplier_email=?, category=?, owner=?, approval_status=?, risk_level=?,
                            annual_spend=?, next_review_date=?, notes=?, updated_at=CURRENT_TIMESTAMP
                        WHERE supplier_id=?
                        """,
                        (name, email, category, owner, status, risk, spend, next_review.isoformat(), notes, supplier_id),
                    )
                    add_timeline(supplier_id, None, "Supplier updated", f"Status {status}, risk {risk}", owner)
                    st.success("Saved")
                    st.rerun()

            st.subheader("Timeline")
            timeline = df_sql("SELECT * FROM supplier_timeline WHERE supplier_id=? ORDER BY created_at DESC", (supplier_id,))
            show_df(timeline, "No timeline events yet.")

    with tab_portal:
        st.subheader("Supplier Portal Preview")
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers yet.")
        else:
            supplier = suppliers.iloc[0]
            rules = df_sql("SELECT * FROM document_rules WHERE category=?", (supplier["category"] or "",))
            st.markdown(f"### Welcome {supplier['supplier_name']}")
            st.write("Please upload the following documents:")
            if rules.empty:
                st.info("Supplier onboarding documents")
            else:
                st.dataframe(rules[["document_type", "is_critical"]], use_container_width=True, hide_index=True)
            st.info("This is a preview only. The real portal would generate a secure upload link for each supplier.")


def compliance_screen():
    hero("Risk & Compliance", "Evidence gaps, issue logs, review cycles and audit readiness.")
    tab_gaps, tab_documents, tab_issues, tab_reviews, tab_templates = st.tabs(
        ["Evidence Gaps", "Documents", "Issue Log", "Review Cycle", "Templates"]
    )

    with tab_gaps:
        show_df(evidence_gaps(), "No evidence gaps.")

    with tab_documents:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers")
        else:
            options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            supplier_id = options[st.selectbox("Supplier", list(options.keys()))]
            with st.form("upload_doc"):
                doc_type = st.text_input("Document type")
                expiry = st.date_input("Expiry date", value=None)
                upload = st.file_uploader("Document")
                notes = st.text_area("Notes")
                if st.form_submit_button("Save document"):
                    if upload and doc_type:
                        path = UPLOAD_DIR / str(supplier_id)
                        path.mkdir(exist_ok=True)
                        file_path = path / upload.name
                        file_path.write_bytes(upload.getbuffer())
                        exec_sql(
                            """
                            INSERT INTO supplier_documents
                            (supplier_id, document_type, file_name, file_path, expiry_date, notes)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (supplier_id, doc_type, upload.name, str(file_path), expiry.isoformat() if expiry else None, notes),
                        )
                        add_timeline(supplier_id, None, "Document uploaded", doc_type, "")
                        st.success("Saved")
                    else:
                        st.error("Choose a document and enter a document type.")
            docs = df_sql("SELECT * FROM supplier_documents WHERE supplier_id=?", (supplier_id,))
            show_df(docs, "No documents uploaded for this supplier.")

    with tab_issues:
        suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty:
            st.info("No suppliers")
        else:
            with st.form("issue"):
                options = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
                supplier_id = options[st.selectbox("Supplier", list(options.keys()))]
                issue_type = st.selectbox("Issue type", ISSUE_TYPES)
                severity = st.selectbox("Severity", ["Low", "Medium", "High", "Critical"])
                status = st.selectbox("Status", ISSUE_STATUSES)
                owner = st.text_input("Owner")
                description = st.text_area("Description")
                resolution = st.text_area("Resolution")
                if st.form_submit_button("Save issue"):
                    exec_sql(
                        """
                        INSERT INTO supplier_issues
                        (supplier_id, issue_type, severity, status, owner, description, resolution)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (supplier_id, issue_type, severity, status, owner, description, resolution),
                    )
                    add_timeline(supplier_id, None, "Issue logged", f"{issue_type}: {severity}", owner)
                    st.success("Issue saved")
            issues = df_sql(
                """
                SELECT i.*, s.supplier_name
                FROM supplier_issues i
                JOIN suppliers s ON i.supplier_id=s.supplier_id
                ORDER BY i.created_at DESC
                """
            )
            show_df(issues, "No supplier issues yet.")

    with tab_reviews:
        table = supplier_table()
        if table.empty:
            st.info("No suppliers")
        else:
            review_mask = table["Next Review"].apply(lambda x: parse_date(x) is not None and parse_date(x) < date.today())
            overdue = table[review_mask]
            show_df(overdue, "No overdue reviews.")

    with tab_templates:
        templates = df_sql("SELECT * FROM email_templates ORDER BY template_type")
        show_df(templates, "No templates yet.")
        with st.form("template"):
            template_type = st.text_input("Template type")
            subject = st.text_input("Subject")
            body = st.text_area("Body", height=180)
            if st.form_submit_button("Save template"):
                if template_type:
                    exec_sql(
                        """
                        INSERT OR REPLACE INTO email_templates (template_type, subject, body, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (template_type, subject, body),
                    )
                    st.success("Template saved")
                    st.rerun()
                else:
                    st.error("Template type is required.")


def onboarding_screen():
    hero("Onboarding Wizard", "Supplier details → checks → route → email → submit.")
    with st.form("wizard"):
        st.markdown("### Step 1: Supplier identity")
        a, b = st.columns(2)
        name = a.text_input("Supplier name *")
        email = a.text_input("Supplier email")
        company = a.text_input("Company number")
        vat = a.text_input("VAT number")
        website = b.text_input("Website")
        category = b.selectbox("Category", [""] + categories())
        spend = b.number_input("Expected spend", min_value=0.0, step=100.0)
        requested_by = b.text_input("Requested by")
        st.markdown("### Step 2: Business reason")
        reason = st.text_area("Why is the supplier needed?")
        if st.form_submit_button("Create draft request", type="primary"):
            if not name:
                st.error("Supplier name is required")
            else:
                request_id = exec_sql(
                    """
                    INSERT INTO new_supplier_requests
                    (supplier_name, supplier_email, requested_by, category, reason_needed, expected_annual_spend,
                     status, company_number, vat_number, website)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, email, requested_by, category, reason, spend, "Draft", company, vat, website),
                )
                add_timeline(None, request_id, "Request created", name, requested_by)
                st.success("Draft request created.")
    st.subheader("Requests")
    show_df(df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"), "No supplier requests yet.")


def reports_screen():
    hero("Audit Pack & Value Tracker", "Management reporting, ROI signals and downloadable audit evidence.")
    tab_audit, tab_value, tab_export = st.tabs(["Audit Readiness", "Value Tracker", "Export"])

    with tab_audit:
        score, reasons = audit_score()
        kpi("Audit readiness", f"{score}%", "; ".join(reasons) or "No deductions")
        gaps = evidence_gaps()
        if gaps.empty:
            st.success("No gaps")
        else:
            st.dataframe(gaps, use_container_width=True, hide_index=True)

    with tab_value:
        issues = df_sql("SELECT * FROM supplier_issues")
        docs = df_sql("SELECT * FROM supplier_documents")
        requests = df_sql("SELECT * FROM new_supplier_requests")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi("Supplier requests", len(requests), "onboarding workflow")
        with c2:
            kpi("Documents stored", len(docs), "evidence files")
        with c3:
            kpi("Issues logged", len(issues), "supplier performance")
        with c4:
            estimated = round((len(requests) * 6 + len(docs) * 2 + len(issues) * 4) / 60, 1)
            kpi("Estimated hours saved", estimated, "manual admin")

    with tab_export:
        xlsx = DATA_DIR / f"supplierpass_v08_audit_{date.today().isoformat()}.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            supplier_table().to_excel(writer, index=False, sheet_name="Readiness")
            df_sql("SELECT * FROM suppliers").to_excel(writer, index=False, sheet_name="Suppliers")
            evidence_gaps().to_excel(writer, index=False, sheet_name="Evidence Gaps")
            df_sql("SELECT * FROM supplier_documents").to_excel(writer, index=False, sheet_name="Documents")
            df_sql("SELECT * FROM supplier_issues").to_excel(writer, index=False, sheet_name="Issues")
            df_sql("SELECT * FROM supplier_timeline").to_excel(writer, index=False, sheet_name="Timeline")
            df_sql("SELECT * FROM new_supplier_requests").to_excel(writer, index=False, sheet_name="Requests")
        with open(xlsx, "rb") as f:
            st.download_button(
                "Download audit pack",
                f,
                file_name=xlsx.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def admin_screen():
    hero("Admin", "Demo mode, implementation checklist and setup settings.")
    if st.button("Load demo data"):
        load_demo_data()
        st.rerun()
    st.subheader("Implementation checklist")
    checklist_items = [
        "Import suppliers",
        "Assign categories",
        "Assign owners",
        "Configure document rules",
        "Upload key documents",
        "Review evidence gaps",
        "Complete finance checks",
        "Export first audit pack",
    ]
    for item in checklist_items:
        st.checkbox(item)
    st.warning(
        "Prototype only. Production still needs authentication, tenant separation, secure storage, backups, licensing and customer support tooling."
    )


# -----------------------------
# Run app
# -----------------------------

init_db()
apply_style()
st.sidebar.markdown("# SupplierPass")
st.sidebar.caption(APP_VERSION)
page = st.sidebar.radio("Navigation", ["Today", "Role Views", "Suppliers", "Risk & Compliance", "Onboarding Wizard", "Reports", "Admin"])

if page == "Today":
    today_screen()
elif page == "Role Views":
    role_views()
elif page == "Suppliers":
    suppliers_screen()
elif page == "Risk & Compliance":
    compliance_screen()
elif page == "Onboarding Wizard":
    onboarding_screen()
elif page == "Reports":
    reports_screen()
elif page == "Admin":
    admin_screen()
