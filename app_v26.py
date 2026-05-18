from pathlib import Path
import pandas as pd
import streamlit as st

APP_VERSION = "v0.26 fictional demo dashboard fix"
DEMO_TAG = "EXPANDED_DEMO"

source_path = Path(__file__).with_name("app_v25.py")
source_code = source_path.read_text(encoding="utf-8")
definitions = source_code.rsplit("\nrun_grouped_app()", 1)[0] if "\nrun_grouped_app()" in source_code else source_code
namespace = {"__file__": str(source_path)}
exec(compile(definitions, str(source_path), "exec"), namespace)
namespace["APP_VERSION"] = APP_VERSION

init_db = namespace["init_db"]
style = namespace["style"]
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
demo_data_screen = namespace["demo_data_screen"]
load_expanded_demo_data = namespace["load_expanded_demo_data"]
clear_expanded_demo_data = namespace["clear_expanded_demo_data"]
hero = namespace["hero"]
hint = namespace["hint"]
show_df = namespace["show_df"]
df_sql = namespace["df_sql"]
exec_sql = namespace["exec_sql"]

LEGACY_DEMO_SUPPLIERS = ["ABC Transport Ltd", "Yorkshire Board Supplies", "Fast Fix Maintenance"]


def clear_legacy_demo_data():
    ids = []
    for name in LEGACY_DEMO_SUPPLIERS:
        df = df_sql("SELECT supplier_id FROM suppliers WHERE supplier_name=?", (name,))
        ids += [int(x) for x in df["supplier_id"].tolist()]
    for supplier_id in ids:
        exec_sql("DELETE FROM po_history WHERE supplier_id=?", (supplier_id,))
        exec_sql("DELETE FROM supplier_prices WHERE supplier_id=?", (supplier_id,))
        exec_sql("DELETE FROM supplier_documents WHERE supplier_id=?", (supplier_id,))
        exec_sql("DELETE FROM email_log WHERE supplier_id=?", (supplier_id,))
        exec_sql("DELETE FROM preferred_suppliers WHERE supplier_id=?", (supplier_id,))
        exec_sql("DELETE FROM erp_action_queue WHERE supplier_id=?", (supplier_id,))
        exec_sql("DELETE FROM suppliers WHERE supplier_id=?", (supplier_id,))


def reload_fictional_demo_clean():
    clear_legacy_demo_data()
    clear_expanded_demo_data()
    load_expanded_demo_data()


def intelligence_table_safe():
    # Use the app's performance screen as source of truth where possible, but query
    # the base tables directly for dashboard counts so this page never breaks if
    # an older demo record is partially loaded.
    suppliers = df_sql("SELECT * FROM suppliers ORDER BY supplier_name")
    if suppliers.empty:
        return pd.DataFrame()
    rows = []
    for _, s in suppliers.iterrows():
        po = df_sql("SELECT * FROM po_history WHERE supplier_id=?", (int(s["supplier_id"]),))
        spend = float(po["total_value"].fillna(0).sum()) if not po.empty and "total_value" in po.columns else 0
        otif = None
        if not po.empty:
            po["promised_dt"] = pd.to_datetime(po["promised_date"], errors="coerce")
            po["received_dt"] = pd.to_datetime(po["received_date"], errors="coerce")
            dated = po[po["promised_dt"].notna() & po["received_dt"].notna()].copy()
            if not dated.empty:
                otif = round(float((dated["received_dt"] <= dated["promised_dt"]).mean() * 100), 1)
        approved = 100 if s.get("approval_status", "") == "Approved" and s.get("app_status", "Active") == "Active" else 45
        overall = round((approved * 0.5) + ((otif if otif is not None else 50) * 0.3) + (min(100, spend / 2000) * 0.2), 1)
        icon = "🟢" if overall >= 80 else "🟠" if overall >= 55 else "🔴"
        active = "✅" if s.get("app_status", "Active") == "Active" else "⛔"
        rows.append({"Icon": icon, "Active": active, "Supplier": s["supplier_name"], "Category": s.get("category", ""), "Overall": overall, "OTIF": otif, "Spend": round(spend, 2), "Approval": s.get("approval_status", ""), "App Status": s.get("app_status", "")})
    return pd.DataFrame(rows)


def dashboard():
    hero("SupplierPass", "Supplier approval, documents, email chases, ERP actions and supplier intelligence.")
    suppliers = df_sql("SELECT * FROM suppliers")
    legacy = suppliers[suppliers["supplier_name"].isin(LEGACY_DEMO_SUPPLIERS)] if not suppliers.empty else pd.DataFrame()
    expanded = suppliers[suppliers["notes"].fillna("").str.contains(DEMO_TAG, na=False)] if not suppliers.empty and "notes" in suppliers.columns else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='kpi'><div class='lab'>Suppliers</div><div class='val'>{len(suppliers)}</div><div class='sub'>records</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='kpi'><div class='lab'>Expanded demo</div><div class='val'>{len(expanded)}</div><div class='sub'>fictional suppliers</div></div>", unsafe_allow_html=True)
    with c3:
        pending_docs = df_sql("SELECT * FROM supplier_documents WHERE review_status IN ('Uploaded','Under Review')")
        st.markdown(f"<div class='kpi'><div class='lab'>Docs waiting</div><div class='val'>{len(pending_docs)}</div><div class='sub'>review queue</div></div>", unsafe_allow_html=True)
    with c4:
        approvals = df_sql("SELECT * FROM new_supplier_requests WHERE status IN ('Draft','Awaiting Approval')")
        st.markdown(f"<div class='kpi'><div class='lab'>Approvals</div><div class='val'>{len(approvals)}</div><div class='sub'>active requests</div></div>", unsafe_allow_html=True)

    if not legacy.empty:
        st.warning("Legacy three-supplier demo data is still present. Remove it and load the fictional demo queues to test the current version properly.")
        if st.button("Remove legacy demo and load fictional queues", type="primary"):
            reload_fictional_demo_clean()
            st.success("Legacy demo removed and fictional queue demo loaded.")
            st.rerun()
    elif expanded.empty:
        st.info("No expanded fictional demo data is loaded yet.")
        if st.button("Load fictional demo queues", type="primary"):
            reload_fictional_demo_clean()
            st.success("Fictional queue demo loaded.")
            st.rerun()
    else:
        st.success("Fictional expanded demo data is loaded.")

    intel = intelligence_table_safe()
    if not intel.empty:
        st.subheader("Supplier scorecards")
        top = intel.sort_values("Overall", ascending=False).head(6)
        cols = st.columns(min(3, len(top)))
        for idx, (_, r) in enumerate(top.iterrows()):
            with cols[idx % len(cols)]:
                st.markdown(
                    f"<div class='card'><div class='big'>{r['Icon']} {r['Active']}</div><b>{r['Supplier']}</b><br><span class='sub'>Overall {r['Overall']}</span><br><span class='sub'>OTIF {r['OTIF'] if pd.notna(r['OTIF']) else '—'}%</span><br><span class='sub'>Spend £{r['Spend']:,.0f}</span></div>",
                    unsafe_allow_html=True,
                )
        show_df(intel.sort_values("Overall", ascending=False), "No supplier intelligence rows yet.")


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
