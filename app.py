import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import numpy as np
import math

# --- DB CONNECTION ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("🗄️ Robust Sales Dashboard (Final JSON Fix)")

# --- THE ULTIMATE JSON SANITIZER ---
def sanitize_for_supabase(val):
    """
    The most aggressive way to ensure a value is JSON-compliant.
    Converts NaN, Inf, and Pandas-style Nulls to Python None.
    """
    # 1. Handle standard None
    if val is None:
        return None
    
    # 2. Handle Pandas/Numpy Nulls (pd.NA, pd.NaT, np.nan)
    if pd.isna(val):
        return None
    
    # 3. Handle Floats (NaN and Infinity)
    if isinstance(val, float):
        if not math.isfinite(val):
            return None
            
    # 4. Handle anything else (Strings, Ints, etc.)
    return val

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
        
        st.write("Identify your KPI columns:")
        all_actual_cols = list(df_excel.columns)
        
        def get_default_idx(query):
            for i, c in enumerate(all_actual_cols):
                if query.lower() in c.lower(): return i
            return 0

        col_tcv_orig = st.selectbox("Select TCV Column", all_actual_cols, index=get_default_idx("TCV"))
        col_fy_orig = st.selectbox("Select FY Column", all_actual_cols, index=get_default_idx("FY"))

        if st.button("Push All Data to Database"):
            to_insert_raw = []
            
            # Step 1: Build the list of records
            for _, row in df_excel.iterrows():
                # Convert row to dict
                full_row_dict = row.to_dict()
                
                # Extract TCV and FY for the specific math columns
                try:
                    tcv_val = float(row[col_tcv_orig])
                    if not math.isfinite(tcv_val): tcv_val = 0.0
                except:
                    tcv_val = 0.0
                    
                try:
                    fy_val = float(row[col_fy_orig])
                    if not math.isfinite(fy_val): fy_val = 0.0
                except:
                    fy_val = 0.0

                record = {
                    "TCV_MUSD": tcv_val,
                    "FY_MUSD": fy_val,
                    "all_data": full_row_dict 
                }
                to_insert_raw.append(record)
            
            # Step 2: THE CRITICAL STEP - Sanitize every single key/value for JSON
            # This walks every dictionary and cleans out any NaN hidden in 'all_data'
            final_insert_list = []
            for record in to_insert_raw:
                clean_record = {
                    "TCV_MUSD": record["TCV_MUSD"],
                    "FY_MUSD": record["FY_MUSD"],
                    "all_data": {k: sanitize_for_supabase(v) for k, v in record["all_data"].items()}
                }
                final_insert_list.append(clean_record)
            
            # Step 3: Batch Insert
            try:
                supabase.table("sales_opportunities").insert(final_insert_list).execute()
                st.success(f"Successfully pushed {len(final_insert_list)} rows! JSON error solved.")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")

# 2. Load Dashboard
df_raw = fetch_data()

if not df_raw.empty:
    # Reconstruct columns from JSON
    df_meta = pd.json_normalize(df_raw['all_data'])
    df = pd.concat([df_raw[['id']], df_meta], axis=1)
    
    # Locate Math Columns
    tcv_col = next((c for c in df.columns if "TCV" in str(c).upper()), "TCV_MUSD")
    fy_col = next((c for c in df.columns if "FY" in str(c).upper()), "FY_MUSD")

    # --- CRUD EDITOR ---
    st.header("📝 Full Column Editor")
    edited_data = st.data_editor(df.fillna(""), num_rows="dynamic", use_container_width=True, key="main_editor")

    if st.button("Save All Changes"):
        updates_list = []
        for _, row in edited_data.iterrows():
            curr_dict = row.to_dict()
            rid = curr_dict.pop('id', None)
            
            # Sanitize row data
            clean_all_data = {k: sanitize_for_supabase(v) for k, v in curr_dict.items() if v != ""}
            
            # Build the update record
            up_rec = {
                "TCV_MUSD": pd.to_numeric(row.get(tcv_col, 0), errors='coerce'),
                "FY_MUSD": pd.to_numeric(row.get(fy_col, 0), errors='coerce'),
                "all_data": clean_all_data
            }
            
            # One last pass to ensure the math columns aren't NaN
            up_rec["TCV_MUSD"] = sanitize_for_supabase(up_rec["TCV_MUSD"]) or 0.0
            up_rec["FY_MUSD"] = sanitize_for_supabase(up_rec["FY_MUSD"]) or 0.0

            if pd.notna(rid) and rid != "":
                supabase.table("sales_opportunities").update(up_rec).eq("id", rid).execute()
            else:
                supabase.table("sales_opportunities").insert(up_rec).execute()
        st.success("Database Saved!")
        st.rerun()

    # --- FILTERS ---
    st.sidebar.header("Filters")
    filter_on = st.sidebar.multiselect("Active Filters:", df.columns, default=df.columns[1:min(5, len(df.columns))])
    
    filtered_df = df.copy()
    for f_col in filter_on:
        u_vals = sorted([str(x) for x in df[f_col].unique() if pd.notna(x)])
        sel = st.sidebar.multiselect(f"Filter {f_col}", u_vals)
        if sel:
            filtered_df = filtered_df[filtered_df[f_col].astype(str).isin(sel)]

    # --- KPI ---
    val_tcv = pd.to_numeric(filtered_df[tcv_col], errors='coerce').fillna(0).sum()
    val_fy = pd.to_numeric(filtered_df[fy_col], errors='coerce').fillna(0).sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("Opportunities", len(filtered_df))
    k2.metric(f"Total TCV", f"{val_tcv:,.2f} MUSD")
    k3.metric(f"Total FY", f"{val_fy:,.2f} MUSD")

    # --- CHART ---
    lead_col = next((c for c in df.columns if "LEADER" in str(c).upper()), df.columns[1])
    st.plotly_chart(px.pie(filtered_df, values=tcv_col, names=lead_col, title="TCV Distribution", hole=0.4), use_container_width=True)

    # --- FINAL TABLE ---
    st.subheader("Filtered Table View")
    summary = pd.DataFrame([{tcv_col: val_tcv, fy_col: val_fy, df.columns[1]: "SUBTOTAL"}])
    st.dataframe(pd.concat([filtered_df, summary], ignore_index=True).fillna(""), use_container_width=True)

else:
    st.warning("No data found. Upload an Excel file.")