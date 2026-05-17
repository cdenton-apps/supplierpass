import sqlite3
from datetime import date, datetime, timedelta
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
APP_VERSION = "v0.7 commercial polish prototype"

SUPPLIER_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
ISSUE_TYPES = ["Quality", "Delivery", "Pricing", "Service", "Compliance", "Finance", "Other"]
ISSUE_STATUS = ["Open", "In Progress", "Resolved", "Closed"]
EMAIL_TEMPLATE_TYPES = [
    "New supplier onboarding request",
    "Missing document request",
    "Expired document urgent chase",
    "Document expiring soon",
    "Approval request",
    "Approval reminder",
    "Supplier approved",
    "Supplier rejected",
    "Bank verification request",
    "Annual supplier review request",
]
IMPORT_PROFILES = {
    "Generic CSV": {"Supplier Name": ["SupplierName", "Supplier Name", "Name"], "Supplier Code": ["SupplierCode", "Supplier Code", "Code"], "Email": ["SupplierEmail", "Email", "Email Address"]},
    "Sage 200 Supplier Export": {"Supplier Name": ["SupplierAccountName", "Supplier Name", "Name"], "Supplier Code": ["SupplierAccountNumber", "AccountNumber", "Code"], "Email": ["EmailAddress", "Email"]},
    "Sage 50 Supplier Export": {"Supplier Name": ["Name", "Supplier Name"], "Supplier Code": ["A/C", "Account", "Supplier Code"], "Email": ["E-mail", "Email"]},
    "Business Central Vendor Export": {"Supplier Name": ["Name", "Vendor Name"], "Supplier Code": ["No.", "Vendor No."], "Email": ["Email"]},
    "Xero Contacts Export": {"Supplier Name": ["ContactName", "Name"], "Supplier Code": ["ContactID", "AccountNumber"], "Email": ["EmailAddress", "Email"]},
}


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def df_sql(sql, params=()):
    c = conn(); df = pd.read_sql_query(sql, c, params=params); c.close(); return df


def exec_sql(sql, params=()):
    c = conn(); cur = c.cursor(); cur.execute(sql, params); c.commit(); new_id = cur.lastrowid; c.close(); return new_id


def many_sql(sql, rows):
    if not rows: return
    c = conn(); cur = c.cursor(); cur.executemany(sql, rows); c.commit(); c.close()


def ensure_column(table, column, definition):
    info = df_sql(f"PRAGMA table_info({table})")
    if column not in info["name"].tolist():
        exec_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    c = conn(); cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS suppliers (
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
        preferred_supplier INTEGER DEFAULT 0,
        company_number TEXT,
        vat_number TEXT,
        website TEXT,
        domain TEXT,
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
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS supplier_documents (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        document_type TEXT NOT NULL,
        file_name TEXT,
        file_path TEXT,
        expiry_date TEXT,
        notes TEXT,
        reviewed_by TEXT,
        review_status TEXT DEFAULT 'Uploaded',
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
        company_number TEXT,
        vat_number TEXT,
        website TEXT,
        domain TEXT,
        company_status TEXT DEFAULT 'Not checked',
        vat_status TEXT DEFAULT 'Not checked',
        sanctions_status TEXT DEFAULT 'Not checked',
        supplier_confidence TEXT DEFAULT 'Not checked',
        bank_verification_status TEXT DEFAULT 'Not started',
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
    cur.execute("""CREATE TABLE IF NOT EXISTS supplier_issues (
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
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS supplier_timeline (
        timeline_id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        request_id INTEGER,
        event_type TEXT,
        event_detail TEXT,
        user TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS email_templates (
        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_type TEXT UNIQUE,
        subject TEXT,
        body TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.commit(); c.close()
    for table, cols in {
        "suppliers": {"next_review_date":"TEXT", "review_frequency_months":"INTEGER DEFAULT 12", "company_number":"TEXT", "vat_number":"TEXT", "website":"TEXT", "domain":"TEXT", "company_status":"TEXT DEFAULT 'Not checked'", "vat_status":"TEXT DEFAULT 'Not checked'", "sanctions_status":"TEXT DEFAULT 'Not checked'", "bank_verification_status":"TEXT DEFAULT 'Not started'", "criticality":"TEXT DEFAULT 'Standard'", "preferred_supplier":"INTEGER DEFAULT 0"},
        "supplier_documents": {"reviewed_by":"TEXT", "review_status":"TEXT DEFAULT 'Uploaded'"},
    }.items():
        for col, definition in cols.items(): ensure_column(table, col, definition)
    seed_defaults()


def seed_defaults():
    doc_rows = [
        ("Manufacturing", "ISO 9001 Certificate", 1, 60), ("Manufacturing", "Public Liability Insurance", 1, 60), ("Manufacturing", "Supplier Questionnaire", 1, 365),
        ("Packaging", "ISO 9001 Certificate", 1, 60), ("Packaging", "Public Liability Insurance", 1, 60), ("Packaging", "FSC / PEFC Certificate", 0, 60),
        ("Transport", "Public Liability Insurance", 1, 60), ("Transport", "Goods in Transit Insurance", 1, 60), ("Transport", "Operator Licence", 1, 60),
        ("Contractor", "Public Liability Insurance", 1, 60), ("Contractor", "RAMS", 1, 30), ("Contractor", "Health & Safety Policy", 1, 365),
        ("IT / Software", "Cyber Security Questionnaire", 1, 365), ("IT / Software", "Data Processing Agreement", 1, 365),
    ]
    many_sql("INSERT OR IGNORE INTO document_rules (category, document_type, is_critical, warning_days) VALUES (?, ?, ?, ?)", doc_rows)
    stages = []
    for cat in ["Manufacturing", "Packaging", "Transport"]:
        stages += [(cat, "Procurement Review", "Procurement", "procurement@example.com", 1, 1), (cat, "Quality Review", "Quality", "quality@example.com", 2, 1), (cat, "Finance Review", "Finance", "finance@example.com", 3, 1)]
    stages += [("Contractor", "H&S Review", "Health and Safety", "hs@example.com", 1, 1), ("Contractor", "Finance Review", "Finance", "finance@example.com", 2, 1), ("IT / Software", "IT / Cyber Review", "IT", "it@example.com", 1, 1), ("IT / Software", "Finance Review", "Finance", "finance@example.com", 2, 1)]
    many_sql("INSERT OR IGNORE INTO approval_stages (category, stage_name, approver_name, approver_email, sequence_order, is_required) VALUES (?, ?, ?, ?, ?, ?)", stages)
    templates = [
        ("Missing document request", "Supplier document request - {document_type}", "Hi {supplier_name},\n\nWe are updating our approved supplier records and need the following document from you:\n\n{document_type}\n\nReason: {issue}\n\nPlease send the latest version, including the expiry date where applicable.\n\nMany thanks,\n{sender}"),
        ("Approval request", "Supplier approval required - {supplier_name}", "Hi {approver_name},\n\nA supplier request is awaiting your review.\n\nSupplier: {supplier_name}\nCategory: {category}\nRequested by: {requested_by}\n\nPlease review and record your decision.\n\nThanks,\nSupplierPass"),
        ("Annual supplier review request", "Annual supplier review due - {supplier_name}", "Hi {owner},\n\nThe supplier {supplier_name} is due for review. Please check documents, risk, ownership and approval status.\n\nThanks,\nSupplierPass"),
        ("Bank verification request", "Bank verification required - {supplier_name}", "Hi Finance,\n\nPlease verify bank details for {supplier_name}.\n\nThanks,\nSupplierPass"),
    ]
    many_sql("INSERT OR IGNORE INTO email_templates (template_type, subject, body) VALUES (?, ?, ?)", templates)


def apply_style():
    st.markdown("""
    <style>
    .block-container{padding-top:1rem}.hero{border-radius:22px;padding:24px 28px;background:linear-gradient(135deg,#0f172a,#1d4ed8 55%,#0f766e);color:white;margin-bottom:18px}.hero h1{margin:0;color:white}.hero p{color:#dbeafe}.kpi{border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff}.lab{font-size:.82rem;color:#64748b}.val{font-size:1.6rem;font-weight:750}.sub{font-size:.8rem;color:#64748b}.card{border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff;margin-bottom:10px}.pill{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:650;font-size:.82rem}.green{background:#dcfce7;color:#166534}.amber{background:#fef3c7;color:#92400e}.red{background:#fee2e2;color:#991b1b}.blue{background:#dbeafe;color:#1e40af}.grey{background:#f1f5f9;color:#334155}
    [data-testid="stSidebar"]{background:#0f172a}[data-testid="stSidebar"] *{color:#f8fafc!important}
    </style>""", unsafe_allow_html=True)


def hero(t, s): st.markdown(f"<div class='hero'><h1>{t}</h1><p>{s}</p></div>", unsafe_allow_html=True)
def kpi(label, value, sub=""): st.markdown(f"<div class='kpi'><div class='lab'>{label}</div><div class='val'>{value}</div><div class='sub'>{sub}</div></div>", unsafe_allow_html=True)
def pill(v):
    c="grey"
    if v in ["Can Buy","Approved","Green","Low","Resolved","Closed"]: c="green"
    elif v in ["Can Buy with Warning","Amber","Pending","Medium","In Progress"]: c="amber"
    elif v in ["Do Not Use","Red","Blocked","High","Critical","Rejected"]: c="red"
    elif v in ["Approval Pending","Dormant","Draft","Open"]: c="blue"
    return f"<span class='pill {c}'>{v}</span>"


def categories():
    df=df_sql("SELECT DISTINCT category FROM suppliers UNION SELECT DISTINCT category FROM document_rules UNION SELECT DISTINCT category FROM new_supplier_requests UNION SELECT DISTINCT category FROM approval_stages ORDER BY category")
    return [x for x in df["category"].dropna().tolist() if str(x).strip()]


def parse_date(v):
    try:
        if v is None or v=="" or pd.isna(v): return None
        return pd.to_datetime(v).date()
    except Exception: return None

def days_left(v):
    d=parse_date(v); return None if d is None else (d-date.today()).days

def doc_status(expiry, warning=60, missing=False, critical=True):
    if missing: return "Red" if critical else "Amber"
    d=days_left(expiry)
    if d is None: return "Amber"
    if d<0: return "Red"
    if d<=int(warning or 60): return "Amber"
    return "Green"


def supplier_checklist(s):
    rules=df_sql("SELECT * FROM document_rules WHERE category=?", (s["category"] or "",)); docs=df_sql("SELECT * FROM supplier_documents WHERE supplier_id=?", (s["supplier_id"],)); rows=[]
    for _,r in rules.iterrows():
        m=docs[docs["document_type"]==r["document_type"]]
        if m.empty: rows.append({"Document Type":r["document_type"],"Status":doc_status(None,r["warning_days"],True,bool(r["is_critical"])),"Issue":"Missing document","Expiry Date":"","Days Left":""})
        else:
            latest=m.sort_values("uploaded_at", ascending=False).iloc[0]; stt=doc_status(latest["expiry_date"],r["warning_days"],False,bool(r["is_critical"])); issue="Expired document" if stt=="Red" else "Expiring soon" if stt=="Amber" else ""
            rows.append({"Document Type":r["document_type"],"Status":stt,"Issue":issue,"Expiry Date":latest["expiry_date"] or "","Days Left":days_left(latest["expiry_date"]) if days_left(latest["expiry_date"]) is not None else ""})
    return pd.DataFrame(rows)


def readiness(s):
    cl=supplier_checklist(s); missing=int((cl["Issue"]=="Missing document").sum()) if not cl.empty else 0; expired=int((cl["Issue"]=="Expired document").sum()) if not cl.empty else 0; expiring=int((cl["Issue"]=="Expiring soon").sum()) if not cl.empty else 0
    issues=df_sql("SELECT * FROM supplier_issues WHERE supplier_id=? AND status NOT IN ('Resolved','Closed')", (s["supplier_id"],)); high_issues=len(issues[issues["severity"].isin(["High","Critical"])]) if not issues.empty else 0
    score=max(0,min(100,100-missing*18-expired*25-expiring*8-high_issues*15-(40 if s["approval_status"]=="Blocked" else 0)))
    if s["approval_status"]=="Blocked" or expired>0 or high_issues>0: buy="Do Not Use"
    elif s["approval_status"] in ["Pending","On Hold"]: buy="Approval Pending"
    elif s["approval_status"]=="Dormant": buy="Dormant"
    elif missing>0 or expiring>0: buy="Can Buy with Warning"
    else: buy="Can Buy"
    reasons=[]
    if missing: reasons.append(f"{missing} missing document(s)")
    if expired: reasons.append(f"{expired} expired document(s)")
    if expiring: reasons.append(f"{expiring} document(s) expiring soon")
    if high_issues: reasons.append(f"{high_issues} high/critical open issue(s)")
    if s["approval_status"]!="Approved": reasons.append(f"Approval status is {s['approval_status']}")
    return score,buy,reasons,missing,expired,expiring


def supplier_table():
    suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name"); rows=[]
    for _,s in suppliers.iterrows():
        score,buy,reasons,missing,expired,expiring=readiness(s)
        rows.append({"Supplier ID":s["supplier_id"],"Supplier Code":s["supplier_code"],"Supplier Name":s["supplier_name"],"Can I Buy?":buy,"Readiness":score,"Reasons":"; ".join(reasons),"Email":s["supplier_email"],"Category":s["category"],"Owner":s["owner"],"Approval Status":s["approval_status"],"Risk":s["risk_level"],"Spend":s["annual_spend"] or 0,"Missing Docs":missing,"Expired Docs":expired,"Expiring Soon":expiring,"Next Review":s["next_review_date"]})
    return pd.DataFrame(rows)


def evidence_gaps():
    rows=[]; suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    for _,s in suppliers.iterrows():
        cl=supplier_checklist(s)
        if not cl.empty:
            for _,d in cl[cl["Status"].isin(["Red","Amber"])].iterrows(): rows.append({"Supplier ID":s["supplier_id"],"Supplier Name":s["supplier_name"],"Gap":d["Issue"],"Severity":d["Status"],"Owner":s["owner"],"Detail":d["Document Type"],"Action":"Chase supplier"})
        if not s["owner"]: rows.append({"Supplier ID":s["supplier_id"],"Supplier Name":s["supplier_name"],"Gap":"Missing owner","Severity":"Amber","Owner":"","Detail":"No internal owner","Action":"Assign owner"})
        if s["next_review_date"] and parse_date(s["next_review_date"]) and parse_date(s["next_review_date"])<date.today(): rows.append({"Supplier ID":s["supplier_id"],"Supplier Name":s["supplier_name"],"Gap":"Review overdue","Severity":"Amber","Owner":s["owner"],"Detail":s["next_review_date"],"Action":"Complete supplier review"})
    return pd.DataFrame(rows)


def audit_score():
    suppliers=supplier_table(); gaps=evidence_gaps()
    if suppliers.empty: return 0, ["No suppliers loaded"]
    score=100; reasons=[]
    if len(gaps): score-=min(40,len(gaps)*3); reasons.append(f"{len(gaps)} evidence gap(s)")
    do_not=len(suppliers[suppliers["Can I Buy?"]=="Do Not Use"]); score-=do_not*8
    if do_not: reasons.append(f"{do_not} Do Not Use supplier(s)")
    no_owner=len(suppliers[suppliers["Owner"].fillna("")==""]); score-=no_owner*3
    if no_owner: reasons.append(f"{no_owner} supplier(s) without owner")
    return max(0,min(100,score)), reasons


def add_timeline(supplier_id=None, request_id=None, event_type="", detail="", user=""):
    exec_sql("INSERT INTO supplier_timeline (supplier_id, request_id, event_type, event_detail, user) VALUES (?, ?, ?, ?, ?)", (supplier_id, request_id, event_type, detail, user))


def load_demo_data():
    suppliers=[("SUP001","ABC Transport Ltd","accounts@abctransport.co.uk","Transport","Connor","Approved","Medium",85000,"Important"),("SUP002","Yorkshire Board Supplies","quality@yorkshireboard.co.uk","Manufacturing","Quality","Approved","High",120000,"Critical"),("SUP003","Fast Fix Maintenance","fastfix@gmail.com","Contractor","Maintenance","Pending","Medium",14000,"Standard"),("SUP004","CloudOps Software","security@cloudops.co.uk","IT / Software","IT","On Hold","High",42000,"Important"),("SUP005","LabelCo Print Ltd","hello@labelco.co.uk","Packaging","Procurement","Approved","Low",22000,"Standard")]
    many_sql("INSERT INTO suppliers (supplier_code,supplier_name,supplier_email,category,owner,approval_status,risk_level,annual_spend,criticality) VALUES (?,?,?,?,?,?,?,?,?)", suppliers)
    st.success("Demo data loaded. Refresh if the dashboard has not updated.")


def today_screen():
    hero("Today in SupplierPass", "One place to see what needs chasing, approving and fixing.")
    suppliers=supplier_table(); gaps=evidence_gaps(); reqs=df_sql("SELECT * FROM new_supplier_requests")
    score,reasons=audit_score(); c1,c2,c3,c4=st.columns(4)
    with c1:kpi("Audit readiness", f"{score}%", "; ".join(reasons[:2]) or "healthy")
    with c2:kpi("Do Not Use", len(suppliers[suppliers["Can I Buy?"]=="Do Not Use"]) if not suppliers.empty else 0, "supplier blocks")
    with c3:kpi("Open approvals", int((~reqs["status"].isin(["Approved","Rejected"])).sum()) if not reqs.empty else 0, "requests")
    with c4:kpi("Evidence gaps", len(gaps), "actions")
    if suppliers.empty:
        st.warning("No suppliers loaded yet.")
        if st.button("Load demo data"): load_demo_data(); st.rerun()
    st.subheader("Priorities")
    if gaps.empty: st.success("No priority evidence gaps found.")
    else: st.dataframe(gaps.head(20),use_container_width=True,hide_index=True)


def role_views():
    hero("Role Views", "Tailored dashboards for Management, Procurement, Quality and Finance.")
    role=st.radio("View", ["Management", "Procurement", "Quality", "Finance", "Admin"], horizontal=True)
    suppliers=supplier_table(); gaps=evidence_gaps(); reqs=df_sql("SELECT * FROM new_supplier_requests")
    if role=="Management":
        st.subheader("Management summary")
        score,reasons=audit_score(); kpi("Audit readiness", f"{score}%", "; ".join(reasons) or "No deductions")
        st.dataframe(suppliers.sort_values("Readiness").head(20),use_container_width=True,hide_index=True) if not suppliers.empty else st.info("No suppliers")
    elif role=="Procurement":
        st.subheader("Procurement queue")
        st.dataframe(gaps[gaps["Action"].str.contains("Chase|Assign", na=False)] if not gaps.empty else gaps,use_container_width=True,hide_index=True)
        st.dataframe(reqs[~reqs["status"].isin(["Approved","Rejected"])] if not reqs.empty else reqs,use_container_width=True,hide_index=True)
    elif role=="Quality":
        st.subheader("Quality evidence")
        q=gaps[gaps["Detail"].str.contains("ISO|BRC|FSC|Questionnaire|Certificate", case=False, na=False)] if not gaps.empty else gaps
        st.dataframe(q,use_container_width=True,hide_index=True)
    elif role=="Finance":
        st.subheader("Finance controls")
        f=suppliers[(suppliers["Spend"]>50000) | (suppliers["Can I Buy?"]!="Can Buy")] if not suppliers.empty else suppliers
        st.dataframe(f,use_container_width=True,hide_index=True)
    else:
        st.subheader("Admin data quality")
        st.dataframe(data_quality(),use_container_width=True,hide_index=True)


def data_quality():
    suppliers=df_sql("SELECT * FROM suppliers"); rows=[]
    if suppliers.empty: return pd.DataFrame()
    for _,s in suppliers.iterrows():
        if not s["supplier_email"]: rows.append({"Issue":"Missing supplier email","Supplier":s["supplier_name"],"Severity":"Amber"})
        if not s["category"]: rows.append({"Issue":"Missing category","Supplier":s["supplier_name"],"Severity":"Amber"})
        if not s["owner"]: rows.append({"Issue":"Missing owner","Supplier":s["supplier_name"],"Severity":"Amber"})
    dup=suppliers[suppliers.duplicated("supplier_name", keep=False)]
    for _,s in dup.iterrows(): rows.append({"Issue":"Possible duplicate supplier","Supplier":s["supplier_name"],"Severity":"Amber"})
    return pd.DataFrame(rows)


def suppliers_screen():
    hero("Supplier Register", "Import, segment and manage supplier profiles.")
    tab1,tab2,tab3,tab4=st.tabs(["Import", "Register", "Profile", "Portal Preview"])
    with tab1:
        profile=st.selectbox("Import profile", list(IMPORT_PROFILES.keys()))
        st.caption("Profiles are pre-mapping helpers for common exports. You can still override every column.")
        file=st.file_uploader("Supplier CSV", type=["csv"])
        if file:
            data=pd.read_csv(file); cols=data.columns.tolist(); st.dataframe(data.head(20),use_container_width=True,hide_index=True)
            guesses=IMPORT_PROFILES[profile]
            def guess(names):
                for n in names:
                    if n in cols: return n
                return ""
            c1,c2,c3=st.columns(3); c_code=c1.selectbox("Supplier Code", [""]+cols, index=([""]+cols).index(guess(guesses["Supplier Code"])) if guess(guesses["Supplier Code"]) in cols else 0); c_name=c1.selectbox("Supplier Name *", cols, index=cols.index(guess(guesses["Supplier Name"])) if guess(guesses["Supplier Name"]) in cols else 0); c_email=c1.selectbox("Email", [""]+cols, index=([""]+cols).index(guess(guesses["Email"])) if guess(guesses["Email"]) in cols else 0); c_cat=c2.selectbox("Category", [""]+cols); c_owner=c2.selectbox("Owner", [""]+cols); c_status=c2.selectbox("Status", [""]+cols); c_spend=c3.selectbox("Annual Spend", [""]+cols); default_cat=c3.selectbox("Default category", [""]+categories())
            if st.button("Import suppliers", type="primary"):
                rows=[]
                for _,r in data.iterrows():
                    name=str(r[c_name]).strip() if pd.notna(r[c_name]) else ""
                    if not name: continue
                    try: spend=float(r[c_spend]) if c_spend and pd.notna(r[c_spend]) else 0
                    except Exception: spend=0
                    rows.append((str(r[c_code]).strip() if c_code and pd.notna(r[c_code]) else "",name,str(r[c_email]).strip() if c_email and pd.notna(r[c_email]) else "",str(r[c_cat]).strip() if c_cat and pd.notna(r[c_cat]) else default_cat,str(r[c_owner]).strip() if c_owner and pd.notna(r[c_owner]) else "",str(r[c_status]).strip() if c_status and pd.notna(r[c_status]) else "Approved","Medium",spend))
                many_sql("INSERT INTO suppliers (supplier_code,supplier_name,supplier_email,category,owner,approval_status,risk_level,annual_spend) VALUES (?,?,?,?,?,?,?,?)", rows); st.success(f"Imported {len(rows)} suppliers."); st.rerun()
    with tab2:
        table=supplier_table(); st.dataframe(table,use_container_width=True,hide_index=True) if not table.empty else st.info("No suppliers yet.")
    with tab3:
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers yet."); return
        sid={f"{r['supplier_name']} ({r['supplier_id']})":int(r["supplier_id"]) for _,r in suppliers.iterrows()}[st.selectbox("Supplier", [f"{r['supplier_name']} ({r['supplier_id']})" for _,r in suppliers.iterrows()])]
        s=df_sql("SELECT * FROM suppliers WHERE supplier_id=?", (sid,)).iloc[0]; score,buy,reasons,_,_,_=readiness(s)
        c1,c2,c3=st.columns(3)
        with c1:kpi("Can I Buy?", buy, "; ".join(reasons) or "No blocking issues")
        with c2:kpi("Readiness", f"{score}%", "supplier score")
        with c3:kpi("Next review", s["next_review_date"] or "Not set", "review cycle")
        with st.form("edit_supplier"):
            a,b,c=st.columns(3); name=a.text_input("Name",s["supplier_name"]); email=a.text_input("Email",s["supplier_email"] or ""); cat=b.selectbox("Category",[""]+categories(), index=([""]+categories()).index(s["category"] or "") if (s["category"] or "") in ([""]+categories()) else 0); owner=b.text_input("Owner",s["owner"] or ""); status=b.selectbox("Status",SUPPLIER_STATUSES,index=SUPPLIER_STATUSES.index(s["approval_status"]) if s["approval_status"] in SUPPLIER_STATUSES else 0); risk=c.selectbox("Risk",RISK_LEVELS,index=RISK_LEVELS.index(s["risk_level"]) if s["risk_level"] in RISK_LEVELS else 1); spend=c.number_input("Spend",value=float(s["annual_spend"] or 0),min_value=0.0,step=100.0); next_review=c.date_input("Next review", value=parse_date(s["next_review_date"]) or date.today()+timedelta(days=365)); notes=st.text_area("Notes",s["notes"] or "")
            if st.form_submit_button("Save"):
                exec_sql("UPDATE suppliers SET supplier_name=?,supplier_email=?,category=?,owner=?,approval_status=?,risk_level=?,annual_spend=?,next_review_date=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE supplier_id=?", (name,email,cat,owner,status,risk,spend,next_review.isoformat(),notes,sid)); add_timeline(sid,None,"Supplier updated",f"Status {status}, risk {risk}",owner); st.success("Saved"); st.rerun()
        st.subheader("Timeline"); tl=df_sql("SELECT * FROM supplier_timeline WHERE supplier_id=? ORDER BY created_at DESC", (sid,)); st.dataframe(tl,use_container_width=True,hide_index=True) if not tl.empty else st.info("No timeline events yet.")
    with tab4:
        st.subheader("Supplier Portal Preview")
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers yet.")
        else:
            s=suppliers.iloc[0]; rules=df_sql("SELECT * FROM document_rules WHERE category=?", (s["category"] or "",))
            st.markdown(f"### Welcome {s['supplier_name']}")
            st.write("Please upload the following documents:")
            st.dataframe(rules[["document_type","is_critical"]] if not rules.empty else pd.DataFrame({"document_type":["Supplier onboarding documents"]}),use_container_width=True,hide_index=True)
            st.info("This is a preview only. The real portal would generate a secure upload link for each supplier.")


def compliance_screen():
    hero("Risk & Compliance", "Evidence gaps, issue logs, review cycles and audit readiness.")
    tab1,tab2,tab3,tab4,tab5=st.tabs(["Evidence Gaps", "Documents", "Issue Log", "Review Cycle", "Templates"])
    with tab1:
        gaps=evidence_gaps(); st.dataframe(gaps,use_container_width=True,hide_index=True) if not gaps.empty else st.success("No evidence gaps.")
    with tab2:
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers")
        else:
            sid={f"{r['supplier_name']} ({r['supplier_id']})":int(r["supplier_id"]) for _,r in suppliers.iterrows()}[st.selectbox("Supplier",[f"{r['supplier_name']} ({r['supplier_id']})" for _,r in suppliers.iterrows()])]
            with st.form("upload_doc"):
                dtype=st.text_input("Document type"); expiry=st.date_input("Expiry date",value=None); upload=st.file_uploader("Document"); notes=st.text_area("Notes")
                if st.form_submit_button("Save document"):
                    if upload and dtype:
                        path=UPLOAD_DIR/str(sid); path.mkdir(exist_ok=True); fpath=path/upload.name; fpath.write_bytes(upload.getbuffer()); exec_sql("INSERT INTO supplier_documents (supplier_id,document_type,file_name,file_path,expiry_date,notes) VALUES (?,?,?,?,?,?)", (sid,dtype,upload.name,str(fpath),expiry.isoformat() if expiry else None,notes)); add_timeline(sid,None,"Document uploaded",dtype,""); st.success("Saved")
            docs=df_sql("SELECT * FROM supplier_documents WHERE supplier_id=?", (sid,)); st.dataframe(docs,use_container_width=True,hide_index=True)
    with tab3:
        suppliers=df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
        if suppliers.empty: st.info("No suppliers")
        else:
            with st.form("issue"):
                opts={f"{r['supplier_name']} ({r['supplier_id']})":int(r["supplier_id"]) for _,r in suppliers.iterrows()}; sid=opts[st.selectbox("Supplier",list(opts.keys()))]; itype=st.selectbox("Issue type",ISSUE_TYPES); sev=st.selectbox("Severity",["Low","Medium","High","Critical"]); status=st.selectbox("Status",ISSUE_STATUS); owner=st.text_input("Owner"); desc=st.text_area("Description"); res=st.text_area("Resolution")
                if st.form_submit_button("Save issue"):
                    exec_sql("INSERT INTO supplier_issues (supplier_id,issue_type,severity,status,owner,description,resolution) VALUES (?,?,?,?,?,?,?)", (sid,itype,sev,status,owner,desc,res)); add_timeline(sid,None,"Issue logged",f"{itype}: {sev}",owner); st.success("Issue saved")
            st.dataframe(df_sql("SELECT i.*, s.supplier_name FROM supplier_issues i JOIN suppliers s ON i.supplier_id=s.supplier_id ORDER BY i.created_at DESC"),use_container_width=True,hide_index=True)
    with tab4:
        table=supplier_table(); overdue=table[table["Next Review"].apply(lambda x: parse_date(x) is not None and parse_date(x)<date.today())] if not table.empty else table
        st.dataframe(overdue,use_container_width=True,hide_index=True) if not overdue.empty else st.success("No overdue reviews.")
    with tab5:
        st.subheader("Email templates")
        templates=df_sql("SELECT * FROM email_templates ORDER BY template_type"); st.dataframe(templates,use_container_width=True,hide_index=True)
        with st.form("template"):
            t=st.selectbox("Template type",EMAIL_TEMPLATE_TYPES); subject=st.text_input("Subject"); body=st.text_area("Body",height=180)
            if st.form_submit_button("Save template"):
                exec_sql("INSERT OR REPLACE INTO email_templates (template_type,subject,body,updated_at) VALUES (?,?,?,CURRENT_TIMESTAMP)", (t,subject,body)); st.success("Template saved"); st.rerun()


def onboarding_screen():
    hero("Onboarding Wizard", "Supplier details → checks → route → email → submit.")
    st.info("This wizard-style page keeps onboarding easy to follow. It stores requests for later approval routing.")
    with st.form("wizard"):
        st.markdown("### Step 1: Supplier identity")
        a,b=st.columns(2); name=a.text_input("Supplier name *"); email=a.text_input("Supplier email"); company=a.text_input("Company number"); vat=a.text_input("VAT number"); website=b.text_input("Website"); category=b.selectbox("Category",[""]+categories()); spend=b.number_input("Expected spend",min_value=0.0,step=100.0); requested=b.text_input("Requested by")
        st.markdown("### Step 2: Business reason")
        reason=st.text_area("Why is the supplier needed?")
        if st.form_submit_button("Create draft request",type="primary"):
            if not name: st.error("Supplier name is required")
            else:
                rid=exec_sql("INSERT INTO new_supplier_requests (supplier_name,supplier_email,requested_by,category,reason_needed,expected_annual_spend,status,company_number,vat_number,website) VALUES (?,?,?,?,?,?,?,?,?,?)", (name,email,requested,category,reason,spend,"Draft",company,vat,website)); st.success("Draft request created."); add_timeline(None,rid,"Request created",name,requested)
    st.subheader("Requests")
    st.dataframe(df_sql("SELECT * FROM new_supplier_requests ORDER BY created_at DESC"),use_container_width=True,hide_index=True)


def reports_screen():
    hero("Audit Pack & Value Tracker", "Management reporting, ROI signals and downloadable audit evidence.")
    tab1,tab2,tab3=st.tabs(["Audit Readiness", "Value Tracker", "Export"])
    with tab1:
        score,reasons=audit_score(); kpi("Audit readiness", f"{score}%", "; ".join(reasons) or "No deductions")
        gaps=evidence_gaps(); st.dataframe(gaps,use_container_width=True,hide_index=True) if not gaps.empty else st.success("No gaps")
    with tab2:
        emails=df_sql("SELECT * FROM email_log"); issues=df_sql("SELECT * FROM supplier_issues"); docs=df_sql("SELECT * FROM supplier_documents")
        c1,c2,c3,c4=st.columns(4)
        with c1:kpi("Emails generated",len(emails),"chases/approvals")
        with c2:kpi("Documents stored",len(docs),"evidence files")
        with c3:kpi("Issues logged",len(issues),"supplier performance")
        with c4:kpi("Estimated hours saved",round((len(emails)*4+len(docs)*2)/60,1),"manual admin")
    with tab3:
        xlsx=DATA_DIR/f"supplierpass_v07_audit_{date.today().isoformat()}.xlsx"
        with pd.ExcelWriter(xlsx,engine="openpyxl") as writer:
            supplier_table().to_excel(writer,index=False,sheet_name="Readiness"); df_sql("SELECT * FROM suppliers").to_excel(writer,index=False,sheet_name="Suppliers"); evidence_gaps().to_excel(writer,index=False,sheet_name="Evidence Gaps"); df_sql("SELECT * FROM supplier_documents").to_excel(writer,index=False,sheet_name="Documents"); df_sql("SELECT * FROM supplier_issues").to_excel(writer,index=False,sheet_name="Issues"); df_sql("SELECT * FROM supplier_timeline").to_excel(writer,index=False,sheet_name="Timeline"); df_sql("SELECT * FROM new_supplier_requests").to_excel(writer,index=False,sheet_name="Requests")
        with open(xlsx,"rb") as f: st.download_button("Download audit pack",f,file_name=xlsx.name,mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def admin_screen():
    hero("Admin", "Demo mode, implementation checklist and setup settings.")
    if st.button("Load demo data"):
        load_demo_data(); st.rerun()
    st.subheader("Implementation checklist")
    for item in ["Import suppliers", "Assign categories", "Assign owners", "Configure document rules", "Configure approval routes", "Upload key documents", "Review evidence gaps", "Complete finance checks", "Export first audit pack"]:
        st.checkbox(item)
    st.warning("Prototype only. Production still needs authentication, tenant separation, secure storage, backups, licensing and customer support tooling.")


init_db(); apply_style()
st.sidebar.markdown("# SupplierPass"); st.sidebar.caption(APP_VERSION)
page=st.sidebar.radio("Navigation", ["Today", "Role Views", "Suppliers", "Risk & Compliance", "Onboarding Wizard", "Reports", "Admin"])
if page=="Today": today_screen()
elif page=="Role Views": role_views()
elif page=="Suppliers": suppliers_screen()
elif page=="Risk & Compliance": compliance_screen()
elif page=="Onboarding Wizard": onboarding_screen()
elif page=="Reports": reports_screen()
elif page=="Admin": admin_screen()
