import re
from datetime import datetime

import pandas as pd
import streamlit as st

from db import connection_summary, execute, initialise_database, read_df

st.set_page_config(page_title="SupplierPass SQL Suppliers", page_icon="✅", layout="wide")
APP_VERSION = "v0.28 SQL-backed Supplier Setup"

APPROVAL_STATUSES = ["Approved", "Pending", "Blocked", "Dormant", "On Hold", "Approval Revoked"]
APP_STATUSES = ["Active", "Inactive"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]
URGENCY_LEVELS = ["Low", "Normal", "High", "Critical"]


def normalise_name(name: str) -> str:
    value = str(name or "").lower().strip()
    value = re.sub(r"\b(limited|ltd|plc|llp|uk|the)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def normalise_email(email: str) -> str:
    return str(email or "").strip().lower()


def q(table_name: str) -> str:
    """Return the physical table name for the active database mode."""
    mode = connection_summary().get("mode")
    sqlserver_names = {
        "suppliers": "dbo.Suppliers",
        "approval_requests": "dbo.SupplierApprovalRequests",
        "preferred_suppliers": "dbo.PreferredSuppliers",
        "erp_action_queue": "dbo.ERPActionQueue",
    }
    sqlite_names = {
        "suppliers": "suppliers",
        "approval_requests": "new_supplier_requests",
        "preferred_suppliers": "preferred_suppliers",
        "erp_action_queue": "erp_action_queue",
    }
    return (sqlserver_names if mode == "SQL Server" else sqlite_names)[table_name]


def cols(prefix=""):
    mode = connection_summary().get("mode")
    if mode == "SQL Server":
        mapping = {
            "supplier_id": "SupplierID", "supplier_code": "SupplierCode", "supplier_name": "SupplierName", "supplier_key": "SupplierKey",
            "supplier_email": "SupplierEmail", "email_key": "EmailKey", "category": "Category", "owner": "Owner",
            "approval_status": "ApprovalStatus", "app_status": "AppStatus", "risk_level": "RiskLevel", "annual_spend": "AnnualSpend",
            "notes": "Notes", "created_at": "CreatedAt", "updated_at": "UpdatedAt",
            "request_id": "RequestID", "requested_by": "RequestedBy", "reason_needed": "ReasonNeeded", "expected_annual_spend": "ExpectedAnnualSpend",
            "urgency": "Urgency", "status": "Status", "approval_decision": "ApprovalDecision", "approval_notes": "ApprovalNotes",
            "approved_by": "ApprovedBy", "approved_at": "ApprovedAt", "converted_supplier_id": "ConvertedSupplierID",
            "preference_id": "PreferenceID", "is_preferred": "IsPreferred", "reason": "Reason", "set_by": "SetBy", "set_at": "SetAt",
            "action_id": "ActionID", "action_type": "ActionType", "action_reason": "ActionReason", "old_value": "OldValue", "new_value": "NewValue",
            "created_by": "CreatedBy", "exported_at": "ExportedAt",
        }
    else:
        mapping = {
            "supplier_id": "supplier_id", "supplier_code": "supplier_code", "supplier_name": "supplier_name", "supplier_key": "supplier_key",
            "supplier_email": "supplier_email", "email_key": "email_key", "category": "category", "owner": "owner",
            "approval_status": "approval_status", "app_status": "app_status", "risk_level": "risk_level", "annual_spend": "annual_spend",
            "notes": "notes", "created_at": "created_at", "updated_at": "updated_at",
            "request_id": "request_id", "requested_by": "requested_by", "reason_needed": "reason_needed", "expected_annual_spend": "expected_annual_spend",
            "urgency": "urgency", "status": "status", "approval_decision": "approval_decision", "approval_notes": "approval_notes",
            "approved_by": "approved_by", "approved_at": "approved_at", "converted_supplier_id": "converted_supplier_id",
            "preference_id": "preference_id", "is_preferred": "is_preferred", "reason": "reason", "set_by": "set_by", "set_at": "set_at",
            "action_id": "action_id", "action_type": "action_type", "action_reason": "action_reason", "old_value": "old_value", "new_value": "new_value",
            "created_by": "created_by", "exported_at": "exported_at",
        }
    return {k: (prefix + v if prefix else v) for k, v in mapping.items()}


def supplier_df() -> pd.DataFrame:
    c = cols()
    return read_df(f"""
        SELECT
            {c['supplier_id']} AS supplier_id,
            {c['supplier_code']} AS supplier_code,
            {c['supplier_name']} AS supplier_name,
            {c['supplier_key']} AS supplier_key,
            {c['supplier_email']} AS supplier_email,
            {c['email_key']} AS email_key,
            {c['category']} AS category,
            {c['owner']} AS owner,
            {c['approval_status']} AS approval_status,
            {c['app_status']} AS app_status,
            {c['risk_level']} AS risk_level,
            {c['annual_spend']} AS annual_spend,
            {c['notes']} AS notes,
            {c['created_at']} AS created_at,
            {c['updated_at']} AS updated_at
        FROM {q('suppliers')}
        ORDER BY {c['supplier_name']}
    """)


def find_duplicate(name: str, email: str = "") -> pd.DataFrame:
    c = cols()
    key = normalise_name(name)
    email_key = normalise_email(email)
    if email_key:
        return read_df(
            f"""
            SELECT {c['supplier_id']} AS supplier_id, {c['supplier_name']} AS supplier_name, {c['supplier_email']} AS supplier_email, {c['category']} AS category
            FROM {q('suppliers')}
            WHERE {c['supplier_key']} = :supplier_key OR {c['email_key']} = :email_key OR lower({c['supplier_email']}) = :email_key
            ORDER BY {c['supplier_name']}
            """,
            {"supplier_key": key, "email_key": email_key},
        )
    return read_df(
        f"""
        SELECT {c['supplier_id']} AS supplier_id, {c['supplier_name']} AS supplier_name, {c['supplier_email']} AS supplier_email, {c['category']} AS category
        FROM {q('suppliers')}
        WHERE {c['supplier_key']} = :supplier_key
        ORDER BY {c['supplier_name']}
        """,
        {"supplier_key": key},
    )


def show_df(df: pd.DataFrame, empty="No records found."):
    if df is None or df.empty:
        st.info(empty)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def hero(title, subtitle):
    st.markdown(
        f"""
        <div style="border-radius:22px;padding:24px 28px;background:linear-gradient(135deg,#0f172a,#1d4ed8 55%,#0f766e);color:white;margin-bottom:18px">
            <h1 style="margin:0;color:white">{title}</h1>
            <p style="color:#dbeafe;margin-bottom:0">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi(label, value, sub=""):
    st.markdown(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:16px;padding:16px;background:#fff">
            <div style="font-size:.82rem;color:#64748b">{label}</div>
            <div style="font-size:1.55rem;font-weight:750">{value}</div>
            <div style="font-size:.8rem;color:#64748b">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_erp_action(supplier_id: int, action_type: str, reason: str, old_value: str, new_value: str, user: str):
    c = cols()
    suppliers = read_df(
        f"SELECT {c['supplier_code']} AS supplier_code, {c['supplier_name']} AS supplier_name FROM {q('suppliers')} WHERE {c['supplier_id']}=:supplier_id",
        {"supplier_id": supplier_id},
    )
    if suppliers.empty:
        return
    supplier = suppliers.iloc[0]
    existing = read_df(
        f"""
        SELECT {c['action_id']} AS action_id
        FROM {q('erp_action_queue')}
        WHERE {c['supplier_id']}=:supplier_id AND {c['action_type']}=:action_type AND {c['new_value']}=:new_value AND {c['status']}='Pending Export'
        """,
        {"supplier_id": supplier_id, "action_type": action_type, "new_value": new_value},
    )
    if not existing.empty:
        return
    execute(
        f"""
        INSERT INTO {q('erp_action_queue')}
        ({c['supplier_id']}, {c['supplier_code']}, {c['supplier_name']}, {c['action_type']}, {c['action_reason']}, {c['old_value']}, {c['new_value']}, {c['status']}, {c['created_by']})
        VALUES (:supplier_id, :supplier_code, :supplier_name, :action_type, :reason, :old_value, :new_value, 'Pending Export', :created_by)
        """,
        {
            "supplier_id": supplier_id,
            "supplier_code": supplier["supplier_code"],
            "supplier_name": supplier["supplier_name"],
            "action_type": action_type,
            "reason": reason,
            "old_value": old_value,
            "new_value": new_value,
            "created_by": user,
        },
    )


def dashboard_screen():
    hero("SupplierPass SQL Supplier Setup", "First real SupplierPass workflow running through the SQL-ready database layer.")
    summary = connection_summary()
    st.caption(f"{APP_VERSION} | Database mode: {summary.get('mode')}")
    suppliers = supplier_df()
    requests = request_df()
    actions = erp_actions_df(pending_only=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Suppliers", len(suppliers), "SQL-backed records")
    with c2:
        kpi("Active", int((suppliers["app_status"] == "Active").sum()) if not suppliers.empty else 0, "available in app")
    with c3:
        kpi("Approvals", len(requests[requests["status"].isin(["Draft", "Awaiting Approval"])]) if not requests.empty else 0, "active requests")
    with c4:
        kpi("ERP Actions", len(actions), "pending export")
    st.subheader("Supplier register")
    show_df(suppliers, "No suppliers yet. Add one in Supplier Setup.")


def add_supplier_screen():
    hero("Suppliers", "Add, import and manage supplier records in the SQL-backed database.")
    tab_add, tab_manage, tab_import, tab_list = st.tabs(["Add Supplier", "Manage Supplier", "Import CSV", "Supplier List"])
    c = cols()
    with tab_add:
        with st.form("add_supplier"):
            a, b, ccol = st.columns(3)
            name = a.text_input("Supplier name *")
            code = a.text_input("Supplier code")
            email = a.text_input("Supplier email")
            category = b.text_input("Category")
            owner = b.text_input("Owner")
            spend = b.number_input("Annual spend", min_value=0.0, step=100.0)
            approval = ccol.selectbox("Approval", APPROVAL_STATUSES, index=1)
            app_status = ccol.selectbox("App status", APP_STATUSES)
            risk = ccol.selectbox("Risk", RISK_LEVELS, index=1)
            notes = st.text_area("Notes")
            if st.form_submit_button("Add supplier", type="primary"):
                if not name.strip():
                    st.error("Supplier name is required.")
                else:
                    dupes = find_duplicate(name, email)
                    if not dupes.empty:
                        st.warning("Possible duplicate found. Supplier not added.")
                        show_df(dupes)
                    else:
                        execute(
                            f"""
                            INSERT INTO {q('suppliers')}
                            ({c['supplier_code']}, {c['supplier_name']}, {c['supplier_key']}, {c['supplier_email']}, {c['email_key']}, {c['category']}, {c['owner']}, {c['approval_status']}, {c['app_status']}, {c['risk_level']}, {c['annual_spend']}, {c['notes']})
                            VALUES (:code, :name, :supplier_key, :email, :email_key, :category, :owner, :approval, :app_status, :risk, :spend, :notes)
                            """,
                            {
                                "code": code,
                                "name": name,
                                "supplier_key": normalise_name(name),
                                "email": email,
                                "email_key": normalise_email(email),
                                "category": category,
                                "owner": owner,
                                "approval": approval,
                                "app_status": app_status,
                                "risk": risk,
                                "spend": spend,
                                "notes": notes,
                            },
                        )
                        st.success("Supplier added.")
                        st.rerun()
    with tab_manage:
        suppliers = supplier_df()
        if suppliers.empty:
            st.info("No suppliers yet.")
        else:
            opts = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in suppliers.iterrows()}
            sid = opts[st.selectbox("Supplier", list(opts.keys()))]
            s = suppliers[suppliers["supplier_id"] == sid].iloc[0]
            with st.form("manage_supplier"):
                a, b, cc = st.columns(3)
                approval = a.selectbox("Approval", APPROVAL_STATUSES, index=APPROVAL_STATUSES.index(s["approval_status"]) if s["approval_status"] in APPROVAL_STATUSES else 1)
                app_status = a.selectbox("App status", APP_STATUSES, index=APP_STATUSES.index(s["app_status"]) if s["app_status"] in APP_STATUSES else 0)
                risk = b.selectbox("Risk", RISK_LEVELS, index=RISK_LEVELS.index(s["risk_level"]) if s["risk_level"] in RISK_LEVELS else 1)
                category = b.text_input("Category", value=s["category"] or "")
                owner = cc.text_input("Owner", value=s["owner"] or "")
                changed_by = cc.text_input("Changed by")
                reason = st.text_area("Reason / notes", value=s["notes"] or "")
                if st.form_submit_button("Save supplier controls", type="primary"):
                    old_app = s["app_status"]
                    old_approval = s["approval_status"]
                    execute(
                        f"""
                        UPDATE {q('suppliers')}
                        SET {c['approval_status']}=:approval, {c['app_status']}=:app_status, {c['risk_level']}=:risk, {c['category']}=:category, {c['owner']}=:owner, {c['notes']}=:notes, {c['updated_at']}=:updated_at
                        WHERE {c['supplier_id']}=:supplier_id
                        """,
                        {
                            "approval": approval,
                            "app_status": app_status,
                            "risk": risk,
                            "category": category,
                            "owner": owner,
                            "notes": reason,
                            "updated_at": datetime.now().isoformat(timespec="seconds"),
                            "supplier_id": sid,
                        },
                    )
                    if old_app == "Active" and app_status == "Inactive":
                        create_erp_action(sid, "SET_SUPPLIER_INACTIVE", reason or "Supplier made inactive in SupplierPass", old_app, app_status, changed_by)
                    if old_approval != approval and approval in ["Approval Revoked", "Blocked", "On Hold"]:
                        create_erp_action(sid, "REVOKE_APPROVAL_OR_BLOCK", reason or "Supplier approval changed in SupplierPass", old_approval, approval, changed_by)
                    st.success("Supplier updated. ERP action created if needed.")
                    st.rerun()
    with tab_import:
        file = st.file_uploader("Supplier CSV", type=["csv"])
        if file:
            data = pd.read_csv(file)
            st.dataframe(data.head(20), use_container_width=True, hide_index=True)
            all_cols = data.columns.tolist()
            name_col = st.selectbox("Supplier name column *", all_cols)
            code_col = st.selectbox("Supplier code column", [""] + all_cols)
            email_col = st.selectbox("Email column", [""] + all_cols)
            category_col = st.selectbox("Category column", [""] + all_cols)
            if st.button("Import suppliers", type="primary"):
                added = skipped = 0
                for _, row in data.iterrows():
                    name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
                    if not name:
                        continue
                    email = str(row[email_col]).strip() if email_col and pd.notna(row[email_col]) else ""
                    if not find_duplicate(name, email).empty:
                        skipped += 1
                        continue
                    execute(
                        f"""
                        INSERT INTO {q('suppliers')}
                        ({c['supplier_code']}, {c['supplier_name']}, {c['supplier_key']}, {c['supplier_email']}, {c['email_key']}, {c['category']}, {c['approval_status']}, {c['app_status']}, {c['risk_level']})
                        VALUES (:code, :name, :supplier_key, :email, :email_key, :category, 'Pending', 'Active', 'Medium')
                        """,
                        {
                            "code": str(row[code_col]).strip() if code_col and pd.notna(row[code_col]) else "",
                            "name": name,
                            "supplier_key": normalise_name(name),
                            "email": email,
                            "email_key": normalise_email(email),
                            "category": str(row[category_col]).strip() if category_col and pd.notna(row[category_col]) else "",
                        },
                    )
                    added += 1
                st.success(f"Imported {added}; skipped {skipped} duplicate(s).")
                st.rerun()
    with tab_list:
        show_df(supplier_df(), "No suppliers yet.")


def request_df() -> pd.DataFrame:
    c = cols()
    return read_df(f"""
        SELECT
            {c['request_id']} AS request_id,
            {c['supplier_name']} AS supplier_name,
            {c['supplier_email']} AS supplier_email,
            {c['requested_by']} AS requested_by,
            {c['category']} AS category,
            {c['reason_needed']} AS reason_needed,
            {c['expected_annual_spend']} AS expected_annual_spend,
            {c['urgency']} AS urgency,
            {c['status']} AS status,
            {c['approval_decision']} AS approval_decision,
            {c['approval_notes']} AS approval_notes,
            {c['approved_by']} AS approved_by,
            {c['approved_at']} AS approved_at,
            {c['converted_supplier_id']} AS converted_supplier_id,
            {c['created_at']} AS created_at,
            {c['updated_at']} AS updated_at
        FROM {q('approval_requests')}
        ORDER BY {c['created_at']} DESC
    """)


def onboarding_screen():
    hero("Supplier Onboarding", "Create supplier requests and route them through SQL-backed approval.")
    c = cols()
    tab_new, tab_all = st.tabs(["New Request", "All Requests"])
    with tab_new:
        with st.form("new_request"):
            a, b = st.columns(2)
            name = a.text_input("Supplier name *")
            email = a.text_input("Supplier email")
            requested_by = b.text_input("Requested by")
            category = b.text_input("Category")
            spend = b.number_input("Expected annual spend", min_value=0.0, step=100.0)
            urgency = b.selectbox("Urgency", URGENCY_LEVELS, index=1)
            reason = st.text_area("Why is the supplier needed?")
            submit_now = st.checkbox("Submit for approval now", value=True)
            if st.form_submit_button("Create request", type="primary"):
                if not name.strip():
                    st.error("Supplier name is required.")
                else:
                    status = "Awaiting Approval" if submit_now else "Draft"
                    execute(
                        f"""
                        INSERT INTO {q('approval_requests')}
                        ({c['supplier_name']}, {c['supplier_email']}, {c['requested_by']}, {c['category']}, {c['reason_needed']}, {c['expected_annual_spend']}, {c['urgency']}, {c['status']})
                        VALUES (:name, :email, :requested_by, :category, :reason, :spend, :urgency, :status)
                        """,
                        {"name": name, "email": email, "requested_by": requested_by, "category": category, "reason": reason, "spend": spend, "urgency": urgency, "status": status},
                    )
                    st.success(f"Request created with status: {status}")
                    st.rerun()
    with tab_all:
        show_df(request_df(), "No supplier requests yet.")


def approve_request(request_id: int, approved_by: str, notes: str):
    c = cols()
    req = read_df(f"SELECT * FROM {q('approval_requests')} WHERE {c['request_id']}=:request_id", {"request_id": request_id})
    if req.empty:
        return None, "Request not found."
    r = req.iloc[0]
    status_col = c["status"]
    converted_col = c["converted_supplier_id"]
    if pd.notna(r.get(converted_col)) and str(r.get(converted_col)) not in ["", "None", "nan"]:
        return int(r[converted_col]), f"Already converted to supplier ID {int(r[converted_col])}."
    if r[status_col] != "Awaiting Approval":
        return None, f"Request is {r[status_col]}, so it cannot be approved."
    dupes = find_duplicate(r[c["supplier_name"]], r[c["supplier_email"]] or "")
    if not dupes.empty:
        sid = int(dupes.iloc[0]["supplier_id"])
        execute(
            f"""
            UPDATE {q('approval_requests')}
            SET {c['status']}='Converted to Supplier', {c['approval_decision']}='Approved - linked existing supplier', {c['approval_notes']}=:notes, {c['approved_by']}=:approved_by, {c['approved_at']}=:approved_at, {c['converted_supplier_id']}=:supplier_id, {c['updated_at']}=:updated_at
            WHERE {c['request_id']}=:request_id
            """,
            {"notes": notes, "approved_by": approved_by, "approved_at": datetime.now().isoformat(timespec="seconds"), "updated_at": datetime.now().isoformat(timespec="seconds"), "supplier_id": sid, "request_id": request_id},
        )
        return sid, f"Linked to existing supplier ID {sid}."
    sid = execute(
        f"""
        INSERT INTO {q('suppliers')}
        ({c['supplier_name']}, {c['supplier_key']}, {c['supplier_email']}, {c['email_key']}, {c['category']}, {c['owner']}, {c['approval_status']}, {c['app_status']}, {c['risk_level']}, {c['annual_spend']}, {c['notes']})
        VALUES (:name, :supplier_key, :email, :email_key, :category, :owner, 'Approved', 'Active', 'Medium', :spend, :notes)
        """,
        {
            "name": r[c["supplier_name"]],
            "supplier_key": normalise_name(r[c["supplier_name"]]),
            "email": r[c["supplier_email"]] or "",
            "email_key": normalise_email(r[c["supplier_email"]] or ""),
            "category": r[c["category"]] or "",
            "owner": r[c["requested_by"]] or "",
            "spend": float(r[c["expected_annual_spend"]] or 0),
            "notes": f"Created from approval request {request_id}. {r[c['reason_needed']] or ''}\nApproval notes: {notes or ''}",
        },
    )
    if sid is None:
        # SQL Server may not return lastrowid. Resolve by supplier key.
        resolved = find_duplicate(r[c["supplier_name"]], r[c["supplier_email"]] or "")
        sid = int(resolved.iloc[0]["supplier_id"]) if not resolved.empty else None
    execute(
        f"""
        UPDATE {q('approval_requests')}
        SET {c['status']}='Converted to Supplier', {c['approval_decision']}='Approved', {c['approval_notes']}=:notes, {c['approved_by']}=:approved_by, {c['approved_at']}=:approved_at, {c['converted_supplier_id']}=:supplier_id, {c['updated_at']}=:updated_at
        WHERE {c['request_id']}=:request_id
        """,
        {"notes": notes, "approved_by": approved_by, "approved_at": datetime.now().isoformat(timespec="seconds"), "updated_at": datetime.now().isoformat(timespec="seconds"), "supplier_id": sid, "request_id": request_id},
    )
    return sid, f"Approved and created supplier ID {sid}."


def approval_queue_screen():
    hero("Approval Queue", "Approve, reject or submit supplier requests using SQL-backed workflow.")
    c = cols()
    requests = request_df()
    if requests.empty:
        st.info("No onboarding requests yet.")
        return
    show_all = st.checkbox("Show converted/rejected requests", value=False)
    view = requests if show_all else requests[requests["status"].isin(["Draft", "Awaiting Approval"])]
    show_df(view, "No active approval requests.")
    if view.empty:
        return
    opts = {f"{r['supplier_name']} ({r['request_id']}) - {r['status']}": int(r["request_id"]) for _, r in view.iterrows()}
    request_id = opts[st.selectbox("Request", list(opts.keys()))]
    req = requests[requests["request_id"] == request_id].iloc[0]
    st.subheader(req["supplier_name"])
    st.write(f"**Status:** {req['status']} | **Category:** {req['category'] or ''} | **Spend:** £{float(req['expected_annual_spend'] or 0):,.2f} | **Urgency:** {req['urgency']}")
    st.write(req["reason_needed"] or "")
    dupes = find_duplicate(req["supplier_name"], req["supplier_email"] or "")
    if not dupes.empty:
        st.warning("Possible existing supplier match. Approval will link to the existing supplier.")
        show_df(dupes)
    notes = st.text_area("Decision notes", value=req["approval_notes"] or "")
    decided_by = st.text_input("Decision by", value=req["approved_by"] or "")
    if req["status"] == "Draft":
        if st.button("Submit for approval", type="primary"):
            execute(
                f"UPDATE {q('approval_requests')} SET {c['status']}='Awaiting Approval', {c['updated_at']}=:updated_at WHERE {c['request_id']}=:request_id",
                {"updated_at": datetime.now().isoformat(timespec="seconds"), "request_id": request_id},
            )
            st.success("Submitted for approval.")
            st.rerun()
    elif req["status"] == "Awaiting Approval":
        a, b = st.columns(2)
        if a.button("Approve & Create/Link Supplier", type="primary"):
            _, message = approve_request(request_id, decided_by, notes)
            st.success(message)
            st.rerun()
        if b.button("Reject"):
            execute(
                f"""
                UPDATE {q('approval_requests')}
                SET {c['status']}='Rejected', {c['approval_decision']}='Rejected', {c['approval_notes']}=:notes, {c['approved_by']}=:approved_by, {c['approved_at']}=:approved_at, {c['updated_at']}=:updated_at
                WHERE {c['request_id']}=:request_id
                """,
                {"notes": notes, "approved_by": decided_by, "approved_at": datetime.now().isoformat(timespec="seconds"), "updated_at": datetime.now().isoformat(timespec="seconds"), "request_id": request_id},
            )
            st.warning("Request rejected.")
            st.rerun()


def preferred_screen():
    hero("Preferred Suppliers", "Set manual preferred suppliers by category in SQL.")
    c = cols()
    suppliers = supplier_df()
    if suppliers.empty:
        st.info("No suppliers yet.")
        return
    categories = sorted([x for x in suppliers["category"].dropna().unique().tolist() if str(x).strip()])
    category = st.selectbox("Category", categories + ["Other"] if categories else ["Other"])
    if category == "Other":
        category = st.text_input("Other category")
    filtered = suppliers[suppliers["category"] == category] if category else suppliers
    if filtered.empty:
        filtered = suppliers
    opts = {f"{r['supplier_name']} ({r['supplier_id']})": int(r["supplier_id"]) for _, r in filtered.iterrows()}
    sid = opts[st.selectbox("Supplier", list(opts.keys()))]
    existing = read_df(
        f"SELECT * FROM {q('preferred_suppliers')} WHERE {c['supplier_id']}=:supplier_id AND {c['category']}=:category",
        {"supplier_id": sid, "category": category},
    )
    current = False
    if not existing.empty:
        current = bool(existing.iloc[0][c["is_preferred"]])
    with st.form("preferred"):
        is_preferred = st.checkbox("Preferred supplier for this category", value=current)
        reason = st.text_area("Reason", value="" if existing.empty else str(existing.iloc[0].get(c["reason"], "") or ""))
        set_by = st.text_input("Set by")
        if st.form_submit_button("Save preferred setting", type="primary"):
            if existing.empty:
                execute(
                    f"""
                    INSERT INTO {q('preferred_suppliers')}
                    ({c['supplier_id']}, {c['category']}, {c['is_preferred']}, {c['reason']}, {c['set_by']})
                    VALUES (:supplier_id, :category, :is_preferred, :reason, :set_by)
                    """,
                    {"supplier_id": sid, "category": category, "is_preferred": 1 if is_preferred else 0, "reason": reason, "set_by": set_by},
                )
            else:
                execute(
                    f"""
                    UPDATE {q('preferred_suppliers')}
                    SET {c['is_preferred']}=:is_preferred, {c['reason']}=:reason, {c['set_by']}=:set_by
                    WHERE {c['supplier_id']}=:supplier_id AND {c['category']}=:category
                    """,
                    {"is_preferred": 1 if is_preferred else 0, "reason": reason, "set_by": set_by, "supplier_id": sid, "category": category},
                )
            st.success("Preferred setting saved.")
            st.rerun()
    st.subheader("Preferred matrix")
    show_df(read_df(f"SELECT * FROM {q('preferred_suppliers')} ORDER BY {c['category']}, {c['is_preferred']} DESC"), "No preferred suppliers yet.")


def erp_actions_df(pending_only=False) -> pd.DataFrame:
    c = cols()
    where = f"WHERE {c['status']}='Pending Export'" if pending_only else ""
    return read_df(f"SELECT * FROM {q('erp_action_queue')} {where} ORDER BY {c['created_at']} DESC")


def erp_action_queue_screen():
    hero("ERP Action Queue", "SupplierPass control changes waiting for ERP review/export.")
    c = cols()
    actions = erp_actions_df(False)
    show_df(actions, "No ERP actions yet.")
    pending = erp_actions_df(True)
    if not pending.empty:
        st.download_button("Download pending ERP actions CSV", pending.to_csv(index=False).encode("utf-8"), file_name="supplierpass_pending_erp_actions.csv", mime="text/csv")
        action_id = st.selectbox("Action to update", pending[c["action_id"]].tolist())
        a, b = st.columns(2)
        if a.button("Mark exported"):
            execute(
                f"UPDATE {q('erp_action_queue')} SET {c['status']}='Exported', {c['exported_at']}=:exported_at WHERE {c['action_id']}=:action_id",
                {"exported_at": datetime.now().isoformat(timespec="seconds"), "action_id": int(action_id)},
            )
            st.success("Marked exported.")
            st.rerun()
        if b.button("Ignore"):
            execute(
                f"UPDATE {q('erp_action_queue')} SET {c['status']}='Ignored', {c['exported_at']}=:exported_at WHERE {c['action_id']}=:action_id",
                {"exported_at": datetime.now().isoformat(timespec="seconds"), "action_id": int(action_id)},
            )
            st.warning("Ignored.")
            st.rerun()


def demo_data_screen():
    hero("SQL Demo Data", "Load a small fictional supplier dataset into the active SQL-ready database.")
    c = cols()
    if st.button("Load SQL supplier demo", type="primary"):
        demo = [
            ("TRN001", "BluePeak Logistics Ltd", "ops@bluepeak.demo", "Transport", "Logistics", "Approved", "Active", "Medium", 185000),
            ("PKG001", "Northstar Board & Packaging Ltd", "quality@northstar.demo", "Packaging", "Quality", "Approved", "Active", "Low", 245000),
            ("RAW001", "Rivergate Adhesives Ltd", "technical@rivergate.demo", "Raw Materials", "Production", "Pending", "Active", "Medium", 64000),
            ("IT001", "NimbusCore Systems Ltd", "security@nimbuscore.demo", "IT / Software", "IT", "On Hold", "Active", "High", 52000),
            ("GEN001", "PaperTrail Office Supplies Ltd", "orders@papertrail.demo", "Office Supplies", "Admin", "Dormant", "Inactive", "Low", 2500),
        ]
        added = skipped = 0
        for code, name, email, category, owner, approval, app_status, risk, spend in demo:
            if not find_duplicate(name, email).empty:
                skipped += 1
                continue
            execute(
                f"""
                INSERT INTO {q('suppliers')}
                ({c['supplier_code']}, {c['supplier_name']}, {c['supplier_key']}, {c['supplier_email']}, {c['email_key']}, {c['category']}, {c['owner']}, {c['approval_status']}, {c['app_status']}, {c['risk_level']}, {c['annual_spend']}, {c['notes']})
                VALUES (:code, :name, :supplier_key, :email, :email_key, :category, :owner, :approval, :app_status, :risk, :spend, 'SQL demo supplier')
                """,
                {"code": code, "name": name, "supplier_key": normalise_name(name), "email": email, "email_key": normalise_email(email), "category": category, "owner": owner, "approval": approval, "app_status": app_status, "risk": risk, "spend": spend},
            )
            added += 1
        requests = [
            ("BrightHarbour Pallet Services Ltd", "sales@brightharbour.demo", "Logistics", "Transport", "Backup courier for urgent pallet movements", 45000, "High", "Awaiting Approval"),
            ("SlateFox Corrugated Ltd", "hello@slatefox.demo", "Procurement", "Packaging", "Alternative corrugated supplier", 90000, "Normal", "Draft"),
        ]
        for name, email, requested_by, category, reason, spend, urgency, status in requests:
            execute(
                f"""
                INSERT INTO {q('approval_requests')}
                ({c['supplier_name']}, {c['supplier_email']}, {c['requested_by']}, {c['category']}, {c['reason_needed']}, {c['expected_annual_spend']}, {c['urgency']}, {c['status']})
                VALUES (:name, :email, :requested_by, :category, :reason, :spend, :urgency, :status)
                """,
                {"name": name, "email": email, "requested_by": requested_by, "category": category, "reason": reason, "spend": spend, "urgency": urgency, "status": status},
            )
        st.success(f"Loaded demo suppliers. Added {added}, skipped {skipped} duplicate(s). Added approval requests too.")
        st.rerun()
    show_df(supplier_df(), "No suppliers yet.")


def database_screen():
    hero("Database", "Initialise and inspect the active SupplierPass database.")
    st.json(connection_summary())
    a, b = st.columns(2)
    if a.button("Initialise / update schema", type="primary"):
        initialise_database()
        st.success("Database schema initialised.")
    if b.button("Test connection"):
        show_df(read_df("SELECT 1 AS connection_ok"))
    st.subheader("SupplierPass tables")
    try:
        if connection_summary().get("mode") == "SQLite":
            show_df(read_df("SELECT name AS table_name FROM sqlite_master WHERE type='table' ORDER BY name"))
        else:
            show_df(read_df("SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS table_name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME"))
    except Exception as exc:
        st.warning(str(exc))


initialise_database()

st.sidebar.markdown("# SupplierPass")
st.sidebar.caption(APP_VERSION)
area = st.sidebar.selectbox("Area", ["Dashboard", "Database", "SQL Demo Data", "Suppliers", "Supplier Onboarding", "Approval Queue", "Preferred Suppliers", "ERP Action Queue"])

if area == "Dashboard":
    dashboard_screen()
elif area == "Database":
    database_screen()
elif area == "SQL Demo Data":
    demo_data_screen()
elif area == "Suppliers":
    add_supplier_screen()
elif area == "Supplier Onboarding":
    onboarding_screen()
elif area == "Approval Queue":
    approval_queue_screen()
elif area == "Preferred Suppliers":
    preferred_screen()
elif area == "ERP Action Queue":
    erp_action_queue_screen()
