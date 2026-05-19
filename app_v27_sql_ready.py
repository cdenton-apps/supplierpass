import streamlit as st

from db import connection_summary, initialise_database, read_df

st.set_page_config(page_title="SupplierPass SQL Ready", page_icon="✅", layout="wide")

st.title("SupplierPass SQL-ready foundation")
st.caption("v0.27 database foundation")

summary = connection_summary()

st.subheader("Database connection")
st.json(summary)

c1, c2 = st.columns(2)
with c1:
    if st.button("Initialise / update database schema", type="primary"):
        initialise_database()
        st.success("Database schema initialised.")
with c2:
    if st.button("Test connection"):
        df = read_df("SELECT 1 AS connection_ok")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.success("Connection OK.")

st.divider()
st.subheader("Available tables / quick checks")

try:
    mode = summary.get("mode")
    if mode == "SQLite":
        tables = read_df("SELECT name AS table_name FROM sqlite_master WHERE type='table' ORDER BY name")
    else:
        tables = read_df("SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS table_name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA, TABLE_NAME")
    st.dataframe(tables, use_container_width=True, hide_index=True)
except Exception as exc:
    st.warning(f"Could not list tables yet: {exc}")

st.divider()
st.subheader("What this version is for")
st.markdown(
    """
    This is not the full SupplierPass UI yet. It is the first SQL-ready foundation.

    It proves that SupplierPass can now run against either:

    - local SQLite for demo/testing
    - SQL Server for production-style deployments

    Next step is to move the main SupplierPass screens onto this shared database layer.
    """
)
