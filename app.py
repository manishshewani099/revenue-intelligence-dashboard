import streamlit as st
import pandas as pd
import plotly.express as px

# Page Setup
st.set_page_config(page_title="Sales Executive Dashboard", layout="wide")
st.title("📊 Sales Opportunity Dashboard")

# 1. File Upload
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

if uploaded_file:
    try:
        # Load Data
        df = pd.read_excel(uploaded_file, sheet_name="7b_Consolidated_Opps", header=0)
        
        # Clean column names (strip spaces, ensure string)
        df.columns = [str(col).strip() for col in df.columns]

        # 2. Column Mapping (Sidebar)
        st.sidebar.header("1. Map Currency Columns")
        all_cols = list(df.columns)
        
        # Auto-detect TCV and FY columns
        def find_col(target):
            for i, c in enumerate(all_cols):
                if target.lower() in str(c).lower(): return i
            return 0

        col_tcv = st.sidebar.selectbox("TCV (MUSD) Column", all_cols, index=find_col("TCV"))
        col_fy = st.sidebar.selectbox("FY (MUSD) Column", all_cols, index=find_col("FY"))
        col_leader = st.sidebar.selectbox("Sales Leader Column", all_cols, index=find_col("Leader"))
        col_stage = st.sidebar.selectbox("Stage Column", all_cols, index=find_col("Stage"))

        # Convert to Numeric (and handle non-numeric values gracefully)
        df[col_tcv] = pd.to_numeric(df[col_tcv], errors='coerce').fillna(0)
        df[col_fy] = pd.to_numeric(df[col_fy], errors='coerce').fillna(0)

        # 3. Dynamic Filter System (All Columns) - FIXED FOR SORTING ERROR
        st.sidebar.header("2. Global Filters")
        active_filters = st.sidebar.multiselect("Select columns to filter by:", all_cols, default=[col_leader, col_stage])
        
        filtered_df = df.copy()
        for col in active_filters:
            # FIX: Convert unique values to strings before sorting to avoid float vs str error
            raw_vals = df[col].unique().tolist()
            vals = sorted([str(x) for x in raw_vals if pd.notna(x)])
            
            selected = st.sidebar.multiselect(f"Filter {col}", vals, key=f"filter_{col}")
            if selected:
                # Filter the dataframe (matching strings to strings)
                filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

        # 4. Calculation of Subtotals
        total_tcv = filtered_df[col_tcv].sum()
        total_fy = filtered_df[col_fy].sum()
        count_opps = len(filtered_df)

        # 5. KPI Cards
        st.subheader("Subtotals (Filtered Selection)")
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Opportunities", f"{count_opps}")
        k2.metric(f"Total {col_tcv}", f"{total_tcv:,.2f} MUSD")
        k3.metric(f"Total {col_fy}", f"{total_fy:,.2f} MUSD")

        # 6. Charts (Pie & Bar)
        st.markdown("---")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            fig_bar = px.bar(filtered_df, x=col_stage, y=col_tcv, color=col_stage, 
                             title=f"TCV by Stage", template="plotly_white")
            st.plotly_chart(fig_bar, use_container_width=True)

        with chart_col2:
            fig_pie = px.pie(filtered_df, values=col_tcv, names=col_leader, 
                             title=f"TCV Distribution by Leader", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        # 7. Data Table with Subtotals
        st.markdown("---")
        st.subheader("Detailed Data View")

        # Create the summary row
        summary_row = {col: "" for col in all_cols}
        summary_row[all_cols[0]] = "TOTAL (FILTERED)"
        summary_row[col_tcv] = total_tcv
        summary_row[col_fy] = total_fy
        
        summary_df = pd.DataFrame([summary_row])

        # Combine data and subtotal row
        # Convert entire dataframe to string for display to handle mixed types safely
        display_df_main = filtered_df.astype(str)
        # But ensure the numeric columns in summary are floats so formatting works (optional)
        final_display_df = pd.concat([filtered_df, summary_df], ignore_index=True)

        st.dataframe(final_display_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Awaiting Excel file upload...")