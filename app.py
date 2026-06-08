import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import json

# --- DB CONNECTION ---
# Ensure these are set in your Streamlit Secrets
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Dynamic Sales CRM", layout="wide")
st.title("🗄️ Full-Column Sales Dashboard")

# --- HELPER FUNCTIONS ---
def fetch_data():
    try:
        response = supabase.table("sales_opportunities").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"DB Fetch Error: {e}")
        return pd.DataFrame()

# 1. Excel Import (Handling Newlines in Headers)
with st.expander("⬆️ Upload & Sync Excel to Supabase"):
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    if uploaded_file:
        df_excel = pd.read_excel(uploaded_file, sheet_name="7b_Consolidated_Opps")
        
        # FIX 1: Clean Newlines and Spaces from Column Headers
        df_excel.columns = [str(c).replace('\n', ' ').strip() for c in df_excel.columns]
        
        st.write("Identify your KPI columns:")
        all_actual_cols = list(df_excel.columns)
        
        # Try to auto-select columns that look like TCV or FY
        def get_default_idx(query):
            for i, c in enumerate(all_actual_cols):
                if query.lower() in c.lower(): return i
            return 0

        col_tcv_orig = st.selectbox("Select TCV Column", all_actual_cols, index=get_default_idx("TCV"))
        col_fy_orig = st.selectbox("Select FY Column", all_actual_cols, index=get_default_idx("FY"))

        if st.button("Push All Data to Database"):
            # FIX 2: Force Currency columns to be numeric, turning text/errors into 0
            df_excel[col_tcv_orig] = pd.to_numeric(df_excel[col_tcv_orig], errors='coerce').fillna(0)
            df_excel[col_fy_orig] = pd.to_numeric(df_excel[col_fy_orig], errors='coerce').fillna(0)
            
            to_insert = []
            for _, row in df_excel.iterrows():
                # Store original row as a dictionary
                clean_row_dict = row.to_dict()
                
                record = {
                    "TCV_MUSD": float(row[col_tcv_orig]),
                    "FY_MUSD": float(row[col_fy_orig]),
                    "all_data": clean_row_dict # Entire row saved here
                }
                to_insert.append(record)
            
            # Batch Insert
            supabase.table("sales_opportunities").insert(to_insert).execute()
            st.success("Successfully pushed all data!")
            st.rerun()

# 2. Load Dashboard
df_raw = fetch_data()

if not df_raw.empty:
    # Reconstruct original columns from the JSON column
    df_meta = pd.json_normalize(df_raw['all_data'])
    df = pd.concat([df_raw[['id']], df_meta], axis=1)
    
    # Ensure math columns in the final dataframe are floats
    # We find the columns that match the TCV/FY names saved in the JSON
    possible_tcv = [c for c in df.columns if "TCV" in str(c).upper()]
    possible_fy = [c for c in df.columns if "FY" in str(c).upper()]
    
    tcv_col = possible_tcv[0] if possible_tcv else "TCV_MUSD"
    fy_col = possible_fy[0] if possible_fy else "FY_MUSD"

    # --- CRUD EDITOR ---
    st.header("📝 Full Column Editor")
    edited_data = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="main_editor")

    if st.button("Save All Changes"):
        for _, row in edited_data.iterrows():
            # Update the record
            # Convert row to dict but remove the 'id' before saving to 'all_data'
            current_row_dict = row.to_dict()
            rid = current_row_dict.pop('id', None)
            
            updated_record = {
                "TCV_MUSD": pd.to_numeric(row.get(tcv_col, 0), errors='coerce'),
                "FY_MUSD": pd.to_numeric(row.get(fy_col, 0), errors='coerce'),
                "all_data": current_row_dict
            }
            
            if pd.notna(rid):
                supabase.table("sales_opportunities").update(updated_record).eq("id", rid).execute()
            else:
                supabase.table("sales_opportunities").insert(updated_record).execute()
        st.success("Database Updated!")
        st.rerun()

    # --- FILTERS ---
    st.sidebar.header("Dashboard Filters")
    # Dynamically allow filtering on the first few columns
    filter_on = st.sidebar.multiselect("Add Filters:", df.columns, default=df.columns[1:5])
    
    filtered_df = df.copy()
    for f_col in filter_on:
        unique_vals = sorted([str(x) for x in df[f_col].unique() if pd.notna(x)])
        selected = st.sidebar.multiselect(f"Filter {f_col}", unique_vals)
        if selected:
            filtered_df = filtered_df[filtered_df[f_col].astype(str).isin(selected)]

    # --- KPI & SUBTOTALS ---
    st.markdown("---")
    # Convert to numeric one last time for the subtotal to avoid string errors
    val_tcv = pd.to_numeric(filtered_df[tcv_col], errors='coerce').fillna(0).sum()
    val_fy = pd.to_numeric(filtered_df[fy_col], errors='coerce').fillna(0).sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("Opportunities", len(filtered_df))
    k2.metric(f"Total TCV", f"{val_tcv:,.2f} MUSD")
    k3.metric(f"Total FY", f"{val_fy:,.2f} MUSD")

    # --- CHART ---
    # Find a good column for the Pie Chart labels (like 'Sales Leader' or 'Stage')
    label_col = "Sales Leader" if "Sales Leader" in df.columns else df.columns[1]
    st.plotly_chart(px.pie(filtered_df, values=tcv_col, names=label_col, title="TCV Distribution"), use_container_width=True)

    # --- DATA TABLE WITH SUBTOTAL ---
    st.subheader("Filtered Table View")
    summary = pd.DataFrame([{tcv_col: val_tcv, fy_col: val_fy, df.columns[1]: "SUBTOTAL"}])
    st.dataframe(pd.concat([filtered_df, summary], ignore_index=True), use_container_width=True)

else:
    st.warning("No data in Supabase. Upload an Excel file to get started.")