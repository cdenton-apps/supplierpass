from pathlib import Path

import streamlit as st

# Reuse the stable v0.17 business logic, database schema and screens, but replace
# the flat sidebar with grouped commercial navigation.
APP_VERSION = "v0.18 grouped navigation"

source_path = Path(__file__).with_name("app_v17.py")
source_code = source_path.read_text(encoding="utf-8")

# Execute the v17 definitions only. This intentionally stops before the v17 app runner.
# v17 contains the stable feature set: supplier controls, preferred suppliers,
# supplier intelligence, ERP action queue and reports.
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


def navigation_help():
    hero("SupplierPass Navigation", "A cleaner workflow view for suppliers, ERP data, performance and audit outputs.")
    hint("Use the sidebar sections to move through the process: set up suppliers, upload ERP data, compare performance, queue ERP updates, then report/export.")
    st.markdown("""
    ### Suggested workflow

    **1. Supplier Setup**  
    Add suppliers, manage approval status, set inactive suppliers, and choose preferred suppliers by category.

    **2. ERP Data**  
    Upload PO/receipt history and price exports, then review ERP update actions created by SupplierPass.

    **3. Performance**  
    Compare suppliers using visual scorecards, price, OTIF, usage, preferred status and approval status.

    **4. Reports**  
    Export the SupplierPass pack for audit, management review or ERP action follow-up.
    """)


def run_grouped_app():
    init_db()
    style()

    st.sidebar.markdown("# SupplierPass")
    st.sidebar.caption(APP_VERSION)

    area = st.sidebar.selectbox(
        "Area",
        [
            "🏠 Home",
            "🏢 Supplier Setup",
            "🔄 ERP Data",
            "📊 Performance",
            "📁 Reports",
        ],
    )

    if area == "🏠 Home":
        page = st.sidebar.radio("Page", ["Dashboard", "How to use SupplierPass"])
        if page == "Dashboard":
            dashboard()
        else:
            navigation_help()

    elif area == "🏢 Supplier Setup":
        page = st.sidebar.radio(
            "Page",
            [
                "Suppliers",
                "Preferred by Category",
                "Supplier Controls",
            ],
        )
        if page == "Preferred by Category":
            preferred_suppliers_screen()
        else:
            supplier_register()

    elif area == "🔄 ERP Data":
        page = st.sidebar.radio(
            "Page",
            [
                "Upload ERP Exports",
                "ERP Update Queue",
            ],
        )
        if page == "Upload ERP Exports":
            data_uploads()
        else:
            erp_actions()

    elif area == "📊 Performance":
        page = st.sidebar.radio(
            "Page",
            [
                "Supplier Scorecards",
                "Compare Suppliers",
                "Price Analysis",
                "OTIF Analysis",
                "Recommendation History",
            ],
        )
        # These are currently tabs inside the Supplier Intelligence screen. The grouped
        # sidebar makes the user intent clearer, while the screen keeps the tabs available.
        supplier_intelligence()

    elif area == "📁 Reports":
        page = st.sidebar.radio("Page", ["Reports & Audit", "ERP Export Pack"])
        if page == "ERP Export Pack":
            erp_actions()
        else:
            reports()


run_grouped_app()
