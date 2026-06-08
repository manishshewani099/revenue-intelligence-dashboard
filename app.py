import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- DB CONNECTION ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Page Config
st.set_page_config(page_title="Supabase Sales CRM", layout="wide")
st.title("🗄️ Sales Dashboard (Powered by Supabase)")

# --- HELPER FUNCTIONS ---
def fetch_data():
    """Fetch all rows from Supabase"""
    response = supabase.table("sales_opportunities").select("*").execute()
    return pd.DataFrame(response.data)

def upload_initial_data(df, col_map):
    """Initial bulk upload from Excel to Supabase"""
    # Standardize column names to match DB
    to_insert = []
    for _, row in df.iterrows():
        to_insert.append({
            "account": str(row[col_map['account']]),
            "sales_leader": str(row[col_map['leader']]),
            "stage": str(row[col_map['stage']]),
            "tcv_musd": float(row[col_map['tcv']]),
            "fy_musd": float(row[col_map['fy']])
        })
    supabase.table("sales_opportunities").insert(to_insert).execute()
    st.success("Data uploaded to Database!")

# --- MAIN APP LOGIC ---

# 1. Initial Data Import
with st.expander("⬆️ Initial Excel Import (Run once)"):
    uploaded_file = st.file_uploader("Upload Excel to populate Database", type=["xlsx"])
    if uploaded_file:
        df_excel = pd.read_excel(uploaded_file, sheet_name="7b_Consolidated_Opps")
        df_excel.columns = [str(c).strip() for c in df_excel.columns]
        
        st.write("Map your columns before importing:")
        c_acc = st.selectbox("Account", df_excel.columns)
        c_lead = st.selectbox("Leader", df_excel.columns)
        c_stage = st.selectbox("Stage", df_excel.columns)
        c_tcv = st.selectbox("TCV (MUSD)", df_excel.columns)
        c_fy = st.selectbox("FY (MUSD)", df_excel.columns)
        
        if st.button("Push to Database"):
            mapping = {'account': c_acc, 'leader': c_lead, 'stage': c_stage, 'tcv': c_tcv, 'fy': c_fy}
            upload_initial_data(df_excel, mapping)
            st.rerun()

# 2. Fetch Data from DB
df = fetch_data()

if not df.empty:
    # --- CRUD SECTION ---
    st.header("📝 Database Editor (Live CRUD)")
    st.info("Any changes here update Supabase instantly.")
    
    # st.data_editor with Supabase integration
    edited_data = st.data_editor(
        df, 
        num_rows="dynamic", 
        key="db_editor", 
        use_container_width=True,
        disabled=["id", "last_updated"] # Don't let users edit primary keys
    )

    # Detect changes to save back to DB
    if st.button("Save Changes to Database"):
        # This is a simplified logic. In a production app, you would 
        # compare st.session_state.db_editor['edited_rows'] etc.
        # For this demo, we will do a simple 'Upsert' logic:
        for _, row in edited_data.iterrows():
            row_data = {
                "account": row['account'],
                "sales_leader": row['sales_leader'],
                "stage": row['stage'],
                "tcv_musd": row['tcv_musd'],
                "fy_musd": row['fy_musd']
            }
            if pd.notna(row['id']): # Update existing
                supabase.table("sales_opportunities").update(row_data).eq("id", row['id']).execute()
            else: # Insert new
                supabase.table("sales_opportunities").insert(row_data).execute()
        
        # Handle Deletions
        # Note: Data editor deletions are complex; usually you'd track deleted IDs.
        st.success("Database Updated!")
        st.rerun()

    # --- DASHBOARD SECTION ---
    st.markdown("---")
    st.header("📊 Filtered Dashboard")

    # Filters
    st.sidebar.header("Filters")
    sel_leader = st.sidebar.multiselect("Leader", df['sales_leader'].unique(), default=df['sales_leader'].unique())
    sel_stage = st.sidebar.multiselect("Stage", df['stage'].unique(), default=df['stage'].unique())

    filtered_df = df[(df['sales_leader'].isin(sel_leader)) & (df['stage'].isin(sel_stage))]

    # Metrics
    k1, k2, k3 = st.columns(3)
    k1.metric("Opportunities", len(filtered_df))
    k2.metric("Total TCV (MUSD)", f"{filtered_df['tcv_musd'].sum():,.2f}")
    k3.metric("Total FY (MUSD)", f"{filtered_df['fy_musd'].sum():,.2f}")

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(filtered_df, x="stage", y="tcv_musd", color="stage", title="TCV by Stage"), use_container_width=True)
    with c2:
        st.plotly_chart(px.pie(filtered_df, values="tcv_musd", names="sales_leader", title="TCV by Leader"), use_container_width=True)

    # Table with Subtotal
    st.subheader("Filtered Table View")
    sub_row = pd.DataFrame([{
        "account": "TOTAL", 
        "tcv_musd": filtered_df['tcv_musd'].sum(),
        "fy_musd": filtered_df['fy_musd'].sum()
    }])
    st.dataframe(pd.concat([filtered_df, sub_row], ignore_index=True), use_container_width=True)

else:
    st.warning("Database is empty. Please upload an Excel file using the section above.")