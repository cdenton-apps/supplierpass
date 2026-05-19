import pandas as pd
import streamlit as st

# Reuse v29 SQL-backed supplier + document + email workflows, then add SQL-backed intelligence.
source_file = "app_v29_sql_documents_email.py"
source_code = open(source_file, "r", encoding="utf-8").read()
definitions = source_code.rsplit("\ninitialise_database()", 1)[0]
namespace = {"__file__": source_file}
exec(compile(definitions, source_file, "exec"), namespace)

APP_VERSION = "v0.30 SQL-backed Supplier Intelligence"

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
dashboard_screen_base = namespace["dashboard_screen"]
add_supplier_screen = namespace["add_supplier_screen"]
request_df = namespace["request_df"]
onboarding_screen = namespace["onboarding_screen"]
approval_queue_screen = namespace["approval_queue_screen"]
preferred_screen = namespace["preferred_screen"]
erp_actions_df = namespace["erp_actions_df"]
erp_action_queue_screen = namespace["erp_action_queue_screen"]
demo_data_screen = namespace["demo_data_screen"]
database_screen = namespace["database_screen"]
documents_screen = namespace["documents_screen"]
email_centre_screen = namespace["email_centre_screen"]
sql_documents_demo_screen = namespace["sql_documents_demo_screen"]


def is_sqlserver() -> bool:
    return connection_summary().get("mode") == "SQL Server"


def it(name: str) -> str:
    if is_sqlserver():
        return {
            "po_history": "dbo.PurchaseOrderHistory",
            "supplier_prices": "dbo.SupplierPrices",
            "recommendations": "dbo.RecommendationHistory",
            "preferred_suppliers": "dbo.PreferredSuppliers",
        }[name]
    return {
        "po_history": "po_history",
        "supplier_prices": "supplier_prices",
        "recommendations": "recommendation_history",
        "preferred_suppliers": "preferred_suppliers",
    }[name]


def ic(name: str) -> str:
    if is_sqlserver():
        return {
            "po_id": "POID", "supplier_id": "SupplierID", "supplier_name": "SupplierName", "supplier_key": "SupplierKey",
            "item_code": "ItemCode", "item_description": "ItemDescription", "po_number": "PONumber", "po_date": "PODate",
            "promised_date": "PromisedDate", "received_date": "ReceivedDate", "quantity": "Quantity", "unit_price": "UnitPrice",
            "total_value": "TotalValue", "source_file": "SourceFile", "uploaded_at": "UploadedAt",
            "price_id": "PriceID", "category": "Category", "currency": "Currency", "lead_time_days": "LeadTimeDays",
            "recommendation_id": "RecommendationID", "requirement": "Requirement", "chosen_supplier": "ChosenSupplier",
            "recommended_supplier": "RecommendedSupplier", "reason": "Reason", "created_by": "CreatedBy", "created_at": "CreatedAt",
            "is_preferred": "IsPreferred",
        }[name]
    return {
        "po_id": "po_id", "supplier_id": "supplier_id", "supplier_name": "supplier_name", "supplier_key": "supplier_key",
        "item_code": "item_code", "item_description": "item_description", "po_number": "po_number", "po_date": "po_date",
        "promised_date": "promised_date", "received_date": "received_date", "quantity": "quantity", "unit_price": "unit_price",
        "total_value": "total_value", "source_file": "source_file", "uploaded_at": "uploaded_at",
        "price_id": "price_id", "category": "category", "currency": "currency", "lead_time_days": "lead_time_days",
        "recommendation_id": "recommendation_id", "requirement": "requirement", "chosen_supplier": "chosen_supplier",
        "recommended_supplier": "recommended_supplier", "reason": "reason", "created_by": "created_by", "created_at": "created_at",
        "is_preferred": "is_preferred",
    }[name]


def resolve_supplier_for_import(name: str, email: str = "", category: str = "") -> int:
    match = find_duplicate(name, email)
    if not match.empty:
        return int(match.iloc[0]["supplier_id"])
    sc = cols()
    execute(
        f"""
        INSERT INTO {q('suppliers')}
        ({sc['supplier_name']}, {sc['supplier_key']}, {sc['supplier_email']}, {sc['email_key']}, {sc['category']}, {sc['approval_status']}, {sc['app_status']}, {sc['risk_level']})
        VALUES (:name, :supplier_key, :email, :email_key, :category, 'Pending', 'Active', 'Medium')
        """,
        {"name": name, "supplier_key": normalise_name(name), "email": email, "email_key": normalise_email(email), "category": category},
    )
    resolved = find_duplicate(name, email)
    return int(resolved.iloc[0]["supplier_id"])


def po_history_df() -> pd.DataFrame:
    return read_df(f"""
        SELECT
            {ic('po_id')} AS po_id,
            {ic('supplier_id')} AS supplier_id,
            {ic('supplier_name')} AS supplier_name,
            {ic('supplier_key')} AS supplier_key,
            {ic('item_code')} AS item_code,
            {ic('item_description')} AS item_description,
            {ic('po_number')} AS po_number,
            {ic('po_date')} AS po_date,
            {ic('promised_date')} AS promised_date,
            {ic('received_date')} AS received_date,
            {ic('quantity')} AS quantity,
            {ic('unit_price')} AS unit_price,
            {ic('total_value')} AS total_value,
            {ic('source_file')} AS source_file,
            {ic('uploaded_at')} AS uploaded_at
        FROM {it('po_history')}
        ORDER BY {ic('po_date')} DESC
    """)


def supplier_prices_df() -> pd.DataFrame:
    return read_df(f"""
        SELECT
            {ic('price_id')} AS price_id,
            {ic('supplier_id')} AS supplier_id,
            {ic('supplier_name')} AS supplier_name,
            {ic('supplier_key')} AS supplier_key,
            {ic('item_code')} AS item_code,
            {ic('item_description')} AS item_description,
            {ic('category')} AS category,
            {ic('unit_price')} AS unit_price,
            {ic('currency')} AS currency,
            {ic('lead_time_days')} AS lead_time_days,
            {ic('source_file')} AS source_file,
            {ic('uploaded_at')} AS uploaded_at
        FROM {it('supplier_prices')}
        ORDER BY {ic('category')}, {ic('item_code')}, {ic('supplier_name')}
    """)


def preferred_set() -> set[tuple[int, str]]:
    df = read_df(f"SELECT {ic('supplier_id')} AS supplier_id, {ic('category')} AS category FROM {it('preferred_suppliers')} WHERE {ic('is_preferred')}=1")
    if df.empty:
        return set()
    return set((int(r["supplier_id"]), str(r["category"])) for _, r in df.iterrows())


def supplier_performance_summary(supplier_id: int) -> dict:
    po = po_history_df()
    po = po[po["supplier_id"] == supplier_id] if not po.empty else po
    if po.empty:
        return {"spend_12m": 0, "otif": None, "last_used": None, "avg_days_late": None, "usage": 0, "po_count": 0}
    po = po.copy()
    po["po_date_dt"] = pd.to_datetime(po["po_date"], errors="coerce")
    po["promised_dt"] = pd.to_datetime(po["promised_date"], errors="coerce")
    po["received_dt"] = pd.to_datetime(po["received_date"], errors="coerce")
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=12)
    recent = po[(po["po_date_dt"].isna()) | (po["po_date_dt"] >= cutoff)]
    spend_12m = float(pd.to_numeric(recent["total_value"], errors="coerce").fillna(0).sum())
    dated = po[po["promised_dt"].notna() & po["received_dt"].notna()].copy()
    otif = None
    avg_days_late = None
    if not dated.empty:
        dated["on_time"] = dated["received_dt"] <= dated["promised_dt"]
        dated["days_late"] = (dated["received_dt"] - dated["promised_dt"]).dt.days.clip(lower=0)
        otif = round(float(dated["on_time"].mean() * 100), 1)
        avg_days_late = round(float(dated["days_late"].mean()), 1)
    last_used = None
    usage = 0
    if po["po_date_dt"].notna().any():
        last = po["po_date_dt"].max().date()
        last_used = last.isoformat()
        usage = max(0, min(100, 100 - (pd.Timestamp.today().date() - last).days / 3.65))
    return {"spend_12m": round(spend_12m, 2), "otif": otif, "last_used": last_used, "avg_days_late": avg_days_late, "usage": round(usage, 1), "po_count": len(po)}


def price_score_for_supplier(supplier_id: int) -> float | None:
    prices = supplier_prices_df()
    if prices.empty:
        return None
    scores = []
    for item, grp in prices.groupby("item_code"):
        own = grp[grp["supplier_id"] == supplier_id]
        if own.empty:
            continue
        all_prices = pd.to_numeric(grp["unit_price"], errors="coerce").replace(0, pd.NA)
        own_prices = pd.to_numeric(own["unit_price"], errors="coerce").replace(0, pd.NA)
        min_price = all_prices.min()
        own_price = own_prices.mean()
        if pd.notna(min_price) and pd.notna(own_price) and own_price > 0:
            scores.append(max(0, min(100, float(min_price / own_price * 100))))
    return round(sum(scores) / len(scores), 1) if scores else None


def compliance_score(row) -> int:
    score = 100
    if row["app_status"] != "Active":
        score -= 60
    if row["approval_status"] != "Approved":
        score -= 25
    if row["approval_status"] == "Approval Revoked":
        score -= 50
    if row["risk_level"] == "High":
        score -= 15
    if row["risk_level"] == "Critical":
        score -= 30
    return max(0, min(100, score))


def score_icon(score) -> str:
    if score >= 80:
        return "🟢"
    if score >= 55:
        return "🟠"
    return "🔴"


def intelligence_df() -> pd.DataFrame:
    suppliers = supplier_df()
    prefs = preferred_set()
    rows = []
    for _, s in suppliers.iterrows():
        sid = int(s["supplier_id"])
        comp = compliance_score(s)
        perf = supplier_performance_summary(sid)
        price = price_score_for_supplier(sid)
        otif_component = perf["otif"] if perf["otif"] is not None else 50
        price_component = price if price is not None else 50
        preferred = (sid, str(s["category"])) in prefs
        preferred_bonus = 8 if preferred else 0
        active_factor = 100 if s["approval_status"] == "Approved" and s["app_status"] == "Active" else 10
        overall = round(min(100, comp * 0.30 + price_component * 0.25 + otif_component * 0.25 + perf["usage"] * 0.10 + active_factor * 0.10 + preferred_bonus), 1)
        rows.append({
            "Icon": score_icon(overall),
            "Preferred": "⭐" if preferred else "",
            "Active": "✅" if s["app_status"] == "Active" else "⛔",
            "Supplier ID": sid,
            "Supplier": s["supplier_name"],
            "Category": s["category"],
            "Overall": overall,
            "Compliance": comp,
            "Price": price,
            "OTIF": perf["otif"],
            "Usage": perf["usage"],
            "12M Spend": perf["spend_12m"],
            "Last Used": perf["last_used"],
            "Avg Days Late": perf["avg_days_late"],
            "PO Count": perf["po_count"],
            "Approval": s["approval_status"],
            "App Status": s["app_status"],
            "Risk": s["risk_level"],
        })
    return pd.DataFrame(rows)


def dashboard_screen():
    hero("SupplierPass SQL", "SQL-backed supplier setup, documents, email and supplier intelligence.")
    st.caption(f"{APP_VERSION} | Database mode: {connection_summary().get('mode')}")
    suppliers = supplier_df()
    intel = intelligence_df()
    po = po_history_df()
    prices = supplier_prices_df()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Suppliers", len(suppliers), "SQL-backed records")
    with c2:
        kpi("PO rows", len(po), "performance history")
    with c3:
        kpi("Price rows", len(prices), "commercial data")
    with c4:
        kpi("Best score", f"{intel['Overall'].max():.0f}" if not intel.empty else "—", "supplier intelligence")
    if not intel.empty:
        st.subheader("Top supplier scorecards")
        top = intel.sort_values("Overall", ascending=False).head(6)
        columns = st.columns(min(3, len(top)))
        for idx, (_, r) in enumerate(top.iterrows()):
            with columns[idx % len(columns)]:
                st.markdown(
                    f"""
                    <div style="border:1px solid #e5e7eb;border-radius:18px;padding:18px;background:#fff;margin-bottom:12px">
                        <div style="font-size:2rem">{r['Icon']} {r['Preferred']} {r['Active']}</div>
                        <b>{r['Supplier']}</b><br>
                        <span style="color:#64748b">Overall {r['Overall']} | OTIF {r['OTIF'] if pd.notna(r['OTIF']) else '—'}%</span><br>
                        <span style="color:#64748b">Spend £{r['12M Spend']:,.0f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        show_df(intel.sort_values("Overall", ascending=False), "No intelligence rows yet.")


def map_upload_columns(df, mode):
    all_cols = df.columns.tolist()
    def select(label, guesses, required=False):
        options = all_cols if required else [""] + all_cols
        idx = 0
        for g in guesses:
            if g in options:
                idx = options.index(g)
                break
        return st.selectbox(label, options, index=idx, key=f"{mode}_{label}")
    a, b, c = st.columns(3)
    mapping = {}
    with a:
        mapping["Supplier Name"] = select("Supplier Name", ["SupplierName", "Supplier Name", "Supplier", "Vendor", "Vendor Name"], True)
        mapping["Supplier Email"] = select("Supplier Email", ["Email", "SupplierEmail", "Email Address"])
        mapping["Item Code"] = select("Item Code", ["ItemCode", "Item Code", "StockCode", "Product Code", "Code"])
        mapping["Item Description"] = select("Item Description", ["ItemDescription", "Item Description", "Description"])
    with b:
        mapping["PO Number"] = select("PO Number", ["PONumber", "PO Number", "DocumentNo", "Order Number"])
        mapping["PO Date"] = select("PO Date", ["PODate", "PO Date", "Order Date", "Date"])
        mapping["Promised Date"] = select("Promised Date", ["PromisedDate", "Promised Date", "Due Date", "RequestedDeliveryDate"])
        mapping["Received Date"] = select("Received Date", ["ReceivedDate", "Received Date", "Receipt Date", "GRN Date"])
    with c:
        mapping["Quantity"] = select("Quantity", ["Quantity", "Qty", "Order Quantity"])
        mapping["Unit Price"] = select("Unit Price", ["UnitPrice", "Unit Price", "Price", "Net Price"])
        mapping["Total Value"] = select("Total Value", ["TotalValue", "Total Value", "Line Total", "Net Value"])
        mapping["Category"] = select("Category", ["Category", "Product Group", "Supplier Category"])
        mapping["Lead Time Days"] = select("Lead Time Days", ["LeadTimeDays", "Lead Time", "Lead Time Days"])
    return mapping


def get_value(row, mapping, label, default=""):
    col = mapping.get(label, "")
    if col and col in row.index and pd.notna(row[col]):
        return row[col]
    return default


def data_uploads_screen():
    hero("ERP Data Uploads", "Upload PO/receipt history and supplier prices into the SQL-backed intelligence tables.")
    mode = st.radio("Upload type", ["PO / receipt history", "Supplier price list"], horizontal=True)
    file = st.file_uploader("CSV export", type=["csv"], key=mode)
    if not file:
        return
    data = pd.read_csv(file)
    st.dataframe(data.head(20), use_container_width=True, hide_index=True)
    mapping = map_upload_columns(data, mode)
    if st.button("Process upload", type="primary"):
        added = 0
        for _, row in data.iterrows():
            name = str(get_value(row, mapping, "Supplier Name", "")).strip()
            if not name:
                continue
            email = str(get_value(row, mapping, "Supplier Email", "")).strip()
            category = str(get_value(row, mapping, "Category", "")).strip()
            sid = resolve_supplier_for_import(name, email, category)
            supplier = supplier_df()
            srow = supplier[supplier["supplier_id"] == sid].iloc[0]
            if mode == "PO / receipt history":
                qty = pd.to_numeric(get_value(row, mapping, "Quantity", 0), errors="coerce")
                unit = pd.to_numeric(get_value(row, mapping, "Unit Price", 0), errors="coerce")
                total = pd.to_numeric(get_value(row, mapping, "Total Value", 0), errors="coerce")
                if pd.isna(total) or float(total) == 0:
                    total = (0 if pd.isna(qty) else float(qty)) * (0 if pd.isna(unit) else float(unit))
                execute(
                    f"""
                    INSERT INTO {it('po_history')}
                    ({ic('supplier_id')}, {ic('supplier_name')}, {ic('supplier_key')}, {ic('item_code')}, {ic('item_description')}, {ic('po_number')}, {ic('po_date')}, {ic('promised_date')}, {ic('received_date')}, {ic('quantity')}, {ic('unit_price')}, {ic('total_value')}, {ic('source_file')})
                    VALUES (:supplier_id, :supplier_name, :supplier_key, :item_code, :item_description, :po_number, :po_date, :promised_date, :received_date, :quantity, :unit_price, :total_value, :source_file)
                    """,
                    {
                        "supplier_id": sid,
                        "supplier_name": name,
                        "supplier_key": srow["supplier_key"],
                        "item_code": str(get_value(row, mapping, "Item Code", "")),
                        "item_description": str(get_value(row, mapping, "Item Description", "")),
                        "po_number": str(get_value(row, mapping, "PO Number", "")),
                        "po_date": str(get_value(row, mapping, "PO Date", "")) or None,
                        "promised_date": str(get_value(row, mapping, "Promised Date", "")) or None,
                        "received_date": str(get_value(row, mapping, "Received Date", "")) or None,
                        "quantity": 0 if pd.isna(qty) else float(qty),
                        "unit_price": 0 if pd.isna(unit) else float(unit),
                        "total_value": 0 if pd.isna(total) else float(total),
                        "source_file": file.name,
                    },
                )
            else:
                price = pd.to_numeric(get_value(row, mapping, "Unit Price", 0), errors="coerce")
                lead = pd.to_numeric(get_value(row, mapping, "Lead Time Days", None), errors="coerce")
                execute(
                    f"""
                    INSERT INTO {it('supplier_prices')}
                    ({ic('supplier_id')}, {ic('supplier_name')}, {ic('supplier_key')}, {ic('item_code')}, {ic('item_description')}, {ic('category')}, {ic('unit_price')}, {ic('currency')}, {ic('lead_time_days')}, {ic('source_file')})
                    VALUES (:supplier_id, :supplier_name, :supplier_key, :item_code, :item_description, :category, :unit_price, 'GBP', :lead_time_days, :source_file)
                    """,
                    {
                        "supplier_id": sid,
                        "supplier_name": name,
                        "supplier_key": srow["supplier_key"],
                        "item_code": str(get_value(row, mapping, "Item Code", "")),
                        "item_description": str(get_value(row, mapping, "Item Description", "")),
                        "category": category or srow["category"],
                        "unit_price": 0 if pd.isna(price) else float(price),
                        "lead_time_days": None if pd.isna(lead) else float(lead),
                        "source_file": file.name,
                    },
                )
            added += 1
        st.success(f"Processed {added} row(s).")
        st.rerun()


def intelligence_screen():
    hero("Supplier Intelligence", "SQL-backed supplier scorecards, comparison, price analysis and OTIF.")
    tab_score, tab_compare, tab_price, tab_otif, tab_history = st.tabs(["Scorecards", "Compare", "Price Analysis", "OTIF Analysis", "Recommendation History"])
    intel = intelligence_df()
    with tab_score:
        show_df(intel.sort_values("Overall", ascending=False) if not intel.empty else intel, "No supplier intelligence data yet.")
    with tab_compare:
        if intel.empty:
            st.info("No suppliers to compare yet.")
        else:
            categories = ["All"] + sorted([x for x in intel["Category"].dropna().unique().tolist() if str(x).strip()])
            category = st.selectbox("Category", categories)
            view = intel if category == "All" else intel[intel["Category"] == category]
            include_inactive = st.checkbox("Include inactive/revoked suppliers", value=False)
            if not include_inactive:
                view = view[(view["App Status"] == "Active") & (view["Approval"] != "Approval Revoked")]
            chosen = st.multiselect("Suppliers", view["Supplier"].tolist(), default=view.sort_values("Overall", ascending=False)["Supplier"].head(3).tolist() if not view.empty else [])
            comp = view[view["Supplier"].isin(chosen)] if chosen else view
            show_df(comp.sort_values("Overall", ascending=False), "Select suppliers to compare.")
            if not comp.empty:
                rec = comp.sort_values(["Preferred", "Overall"], ascending=[False, False]).iloc[0]
                st.success(f"Recommended: {rec['Icon']} {rec['Preferred']} {rec['Supplier']} — score {rec['Overall']}.")
                reason = f"Recommended {rec['Supplier']} based on preferred status '{rec['Preferred']}', overall score {rec['Overall']}, compliance {rec['Compliance']}, price score {rec['Price'] if pd.notna(rec['Price']) else 'not available'}, OTIF {rec['OTIF'] if pd.notna(rec['OTIF']) else 'not available'} and recent usage."
                with st.form("save_recommendation"):
                    requirement = st.text_input("Requirement / comparison reason", value=f"Supplier comparison - {category}")
                    user = st.text_input("Created by")
                    selected_supplier = st.selectbox("Chosen supplier", comp["Supplier"].tolist(), index=comp["Supplier"].tolist().index(rec["Supplier"]))
                    if st.form_submit_button("Save recommendation"):
                        execute(
                            f"""
                            INSERT INTO {it('recommendations')}
                            ({ic('requirement')}, {ic('category')}, {ic('chosen_supplier')}, {ic('recommended_supplier')}, {ic('reason')}, {ic('created_by')})
                            VALUES (:requirement, :category, :chosen_supplier, :recommended_supplier, :reason, :created_by)
                            """,
                            {"requirement": requirement, "category": category, "chosen_supplier": selected_supplier, "recommended_supplier": rec["Supplier"], "reason": reason, "created_by": user},
                        )
                        st.success("Recommendation saved.")
    with tab_price:
        prices = supplier_prices_df()
        if prices.empty:
            st.info("No price data yet.")
        else:
            item = st.selectbox("Item", ["All"] + sorted([x for x in prices["item_code"].dropna().unique().tolist() if str(x).strip()]))
            view = prices if item == "All" else prices[prices["item_code"] == item]
            if not view.empty:
                view = view.copy()
                view["Best"] = view.groupby("item_code")["unit_price"].transform(lambda s: s == s.min()).map(lambda x: "🏆" if x else "")
            show_df(view[["Best", "supplier_name", "item_code", "item_description", "category", "unit_price", "currency", "lead_time_days", "source_file", "uploaded_at"]], "No prices for this filter.")
            if item != "All" and not view.empty:
                st.bar_chart(view.set_index("supplier_name")["unit_price"])
    with tab_otif:
        rows = []
        suppliers = supplier_df()
        for _, s in suppliers.iterrows():
            perf = supplier_performance_summary(int(s["supplier_id"]))
            if perf["po_count"] == 0:
                continue
            rows.append({"Icon": score_icon(perf["otif"] if perf["otif"] is not None else 50), "Supplier": s["supplier_name"], "OTIF %": perf["otif"], "Avg Days Late": perf["avg_days_late"], "Last Used": perf["last_used"], "12M Spend": perf["spend_12m"], "PO Count": perf["po_count"]})
        otif = pd.DataFrame(rows).sort_values("OTIF %", ascending=False, na_position="last") if rows else pd.DataFrame()
        show_df(otif, "No OTIF rows calculated yet.")
        if not otif.empty and otif["OTIF %"].notna().any():
            st.bar_chart(otif.dropna(subset=["OTIF %"]).set_index("Supplier")["OTIF %"])
    with tab_history:
        history = read_df(f"SELECT * FROM {it('recommendations')} ORDER BY {ic('created_at')} DESC")
        show_df(history, "No recommendations saved yet.")


def sql_intelligence_demo_screen():
    hero("SQL Intelligence Demo", "Load fictional PO history and price data into the active SQL database.")
    suppliers = supplier_df()
    if suppliers.empty:
        st.info("Load supplier demo data first from SQL Demo Data.")
        return
    if st.button("Load intelligence demo", type="primary"):
        today = pd.Timestamp.today().normalize()
        for _, s in suppliers.iterrows():
            sid = int(s["supplier_id"])
            category = s["category"] or "General"
            prefix = {"Transport": "FRT", "Packaging": "PKG", "Raw Materials": "RAW", "IT / Software": "ITS", "Office Supplies": "OFF"}.get(category, "GEN")
            for item_no in range(1, 4):
                execute(
                    f"""
                    INSERT INTO {it('supplier_prices')}
                    ({ic('supplier_id')}, {ic('supplier_name')}, {ic('supplier_key')}, {ic('item_code')}, {ic('item_description')}, {ic('category')}, {ic('unit_price')}, {ic('currency')}, {ic('lead_time_days')}, {ic('source_file')})
                    VALUES (:supplier_id, :supplier_name, :supplier_key, :item_code, :item_description, :category, :unit_price, 'GBP', :lead_time_days, 'sql_intelligence_demo')
                    """,
                    {"supplier_id": sid, "supplier_name": s["supplier_name"], "supplier_key": s["supplier_key"], "item_code": f"{prefix}-{item_no:03d}", "item_description": f"Demo item {item_no}", "category": category, "unit_price": round(10 + item_no + (sid % 5), 2), "lead_time_days": 2 + (sid % 6)},
                )
            for i in range(1, 10):
                po_date = today - pd.DateOffset(days=i * 28)
                promised = po_date + pd.DateOffset(days=7 + (i % 3))
                days_late = max(0, ((i + sid) % 5) - 2)
                received = promised + pd.DateOffset(days=days_late)
                qty = 10 + (i * 2)
                unit_price = 8 + (sid % 7) + (i % 3)
                execute(
                    f"""
                    INSERT INTO {it('po_history')}
                    ({ic('supplier_id')}, {ic('supplier_name')}, {ic('supplier_key')}, {ic('item_code')}, {ic('item_description')}, {ic('po_number')}, {ic('po_date')}, {ic('promised_date')}, {ic('received_date')}, {ic('quantity')}, {ic('unit_price')}, {ic('total_value')}, {ic('source_file')})
                    VALUES (:supplier_id, :supplier_name, :supplier_key, :item_code, :item_description, :po_number, :po_date, :promised_date, :received_date, :quantity, :unit_price, :total_value, 'sql_intelligence_demo')
                    """,
                    {"supplier_id": sid, "supplier_name": s["supplier_name"], "supplier_key": s["supplier_key"], "item_code": f"{prefix}-{(i % 3) + 1:03d}", "item_description": f"Demo item {(i % 3) + 1}", "po_number": f"PO-SQL-{sid}-{i:03d}", "po_date": po_date.date().isoformat(), "promised_date": promised.date().isoformat(), "received_date": received.date().isoformat(), "quantity": qty, "unit_price": unit_price, "total_value": qty * unit_price},
                )
        st.success("SQL intelligence demo loaded.")
        st.rerun()
    show_df(intelligence_df(), "No intelligence rows yet.")


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
        "SQL Intelligence Demo",
        "Suppliers",
        "Supplier Onboarding",
        "Approval Queue",
        "Preferred Suppliers",
        "Document Management",
        "Email Centre",
        "ERP Data Uploads",
        "Supplier Intelligence",
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
elif area == "SQL Intelligence Demo":
    sql_intelligence_demo_screen()
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
elif area == "ERP Data Uploads":
    data_uploads_screen()
elif area == "Supplier Intelligence":
    intelligence_screen()
elif area == "ERP Action Queue":
    erp_action_queue_screen()
