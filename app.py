import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import numpy as np

# --- DB CONNECTION ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("🗄️ Full-Column Sales Dashboard")

# --- HELPER FUNCTIONS ---
def fetch_data():
    try:
        response = supabase.table("sales_opportunities").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"DB Fetch Error: {e}")
        return pd.DataFrame()

# 1. Excel Import Section
with st.expander("⬆️ Upload & Sync Excel to Supabase"):
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    if uploaded_file:
        df_excel = pd.read_excel(uploaded_file, sheet_name="7b_Consolidated_Opps")
        
        # Clean Headers
        df_excel.columns = [str(c).replace('\n', ' ').strip() for c in df_excel.columns]
        
        # FIX FOR JSON ERROR: Replace all NaN/NaT with None
        # This makes the data JSON-compliant
        df_excel = df_excel.replace({np.nan: None, pd.NA: None, pd.NaT: None})
        
        st.write("Identify your KPI columns:")
        all_actual_cols = list(df_excel.columns)
        
        def get_default_idx(query):
            for i, c in enumerate(all_actual_cols):
                if query.lower() in c.lower(): return i
            return 0

        col_tcv_orig = st.selectbox("Select TCV Column", all_actual_cols, index=get_default_idx("TCV"))
        col_fy_orig = st.selectbox("Select FY Column", all_actual_cols, index=get_default_idx("FY"))

        if st.button("Push All Data to Database"):
            to_insert = []
            for _, row in df_excel.iterrows():
                # Extract values and ensure they are float for the math columns
                # We use 0.0 if the cell is empty for these specific columns
                tcv_val = row[col_tcv_orig] if row[col_tcv_orig] is not None else 0.0
                fy_val = row[col_fy_orig] if row[col_fy_orig] is not None else 0.0
                
                try:
                    tcv_val = float(tcv_val)
                    fy_val = float(fy_val)
                except:
                    tcv_val, fy_val = 0.0, 0.0

                record = {
                    "TCV_MUSD": tcv_val,
                    "FY_MUSD": fy_val,
                    "all_data": row.to_dict() # Now contains None instead of NaN
                }
                to_insert.append(record)
            
            # Batch Insert to Supabase
            try:
                supabase.table("sales_opportunities").insert(to_insert).execute()
                st.success("Successfully pushed data! JSON error avoided.")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")

# 2. Load Dashboard
df_raw = fetch_data()

if not df_raw.empty:
    # Reconstruct columns from JSON
    df_meta = pd.json_normalize(df_raw['all_data'])
    df = pd.concat([df_raw[['id']], df_meta], axis=1)
    
    # Identify Math columns in the reconstructed DF
    tcv_col = next((c for c in df.columns if "TCV" in str(c).upper()), "TCV_MUSD")
    fy_col = next((c for c in df.columns if "FY" in str(c).upper()), "FY_MUSD")

    # --- CRUD EDITOR ---
    st.header("📝 Full Column Editor")
    # Replace None back to empty string for cleaner editing
    edited_data = st.data_editor(df.fillna(""), num_rows="dynamic", use_container_width=True, key="main_editor")

    if st.button("Save All Changes"):
        for _, row in edited_data.iterrows():
            # Prep dict and handle the ID
            current_row_dict = row.to_dict()
            rid = current_row_dict.pop('id', None)
            
            # Clean dict for JSON storage (remove empty strings to None)
            clean_dict = {k: (None if v == "" else v) for k, v in current_row_dict.items()}
            
            updated_record = {
                "TCV_MUSD": pd.to_numeric(row.get(tcv_col, 0), errors='coerce'),
                "FY_MUSD": pd.to_numeric(row.get(fy_col, 0), errors='coerce'),
                "all_data": clean_dict
            }
            
            if pd.notna(rid) and rid != "":
                supabase.table("sales_opportunities").update(updated_record).eq("id", rid).execute()
            else:
                supabase.table("sales_opportunities").insert(updated_record).execute()
        st.success("Database Updated!")
        st.rerun()

    # --- FILTERS ---
    st.sidebar.header("Dashboard Filters")
    filter_on = st.sidebar.multiselect("Add Filters:", df.columns, default=df.columns[1:5])
    
    filtered_df = df.copy()
    for f_col in filter_on:
        unique_vals = sorted([str(x) for x in df[f_col].unique() if pd.notna(x)])
        selected = st.sidebar.multiselect(f"Filter {f_col}", unique_vals)
        if selected:
            filtered_df = filtered_df[filtered_df[f_col].astype(str).isin(selected)]

    # --- KPI & SUBTOTALS ---
    st.markdown("---")
    val_tcv = pd.to_numeric(filtered_df[tcv_col], errors='coerce').fillna(0).sum()
    val_fy = pd.to_numeric(filtered_df[fy_col], errors='coerce').fillna(0).sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("Opportunities", len(filtered_df))
    k2.metric(f"Total TCV", f"{val_tcv:,.2f} MUSD")
    k3.metric(f"Total FY", f"{val_fy:,.2f} MUSD")

    # --- CHART ---
    label_col = "Sales Leader" if "Sales Leader" in df.columns else df.columns[1]
    st.plotly_chart(px.pie(filtered_df, values=tcv_col, names=label_col, title="TCV Distribution", hole=0.4), use_container_width=True)

    # --- DATA TABLE WITH SUBTOTAL ---
    st.subheader("Filtered Table View")
    summary = pd.DataFrame([{tcv_col: val_tcv, fy_col: val_fy, df.columns[1]: "SUBTOTAL"}])
    st.dataframe(pd.concat([filtered_df, summary], ignore_index=True).fillna(""), use_container_width=True)

else:
    st.warning("No data found. Upload an Excel file.")