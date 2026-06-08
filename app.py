import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Advanced Sales Opportunity Dashboard")

uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

if uploaded_file:
    try:
        # 1. Load Data
        df = pd.read_excel(uploaded_file, sheet_name="7b_Consolidated_Opps", header=0)
        
        # Clean column names (strip spaces, ensure string)
        df.columns = [str(col).strip() for col in df.columns]

        # 2. Identify the specific MUSD columns
        # We search for columns containing "FY" and "TCV" to map them automatically
        all_cols = list(df.columns)
        
        def find_col(target_snippets):
            for col in all_cols:
                if any(snippet.lower() in col.lower() for snippet in target_snippets):
                    return col
            return all_cols[0]

        col_fy = st.sidebar.selectbox("Identify FY (MUSD) column", all_cols, index=all_cols.index(find_col(["FY", "MUSD"])))
        col_tcv = st.sidebar.selectbox("Identify TCV (MUSD) column", all_cols, index=all_cols.index(find_col(["TCV", "MUSD"])))

        # Convert to numeric (Safety)
        df[col_fy] = pd.to_numeric(df[col_fy], errors='coerce').fillna(0)
        df[col_tcv] = pd.to_numeric(df[col_tcv], errors='coerce').fillna(0)

        # 3. DYNAMIC FILTERING ON ALL COLUMNS
        st.sidebar.header("Filter Data")
        
        # Allow users to select which columns they want to filter by
        filter_cols = st.sidebar.multiselect("Add filters for specific columns:", all_cols, default=all_cols[:3])

        filtered_df = df.copy()

        # Generate filter UI for each selected column
        for col in filter_cols:
            unique_vals = df[col].unique().tolist()
            selected = st.sidebar.multiselect(f"Filter {col}", options=unique_vals, key=col)
            if selected:
                filtered_df = filtered_df[filtered_df[col].isin(selected)]

        # 4. CALCULATE DYNAMIC SUBTOTALS
        total_fy_musd = filtered_df[col_fy].sum()
        total_tcv_musd = filtered_df[col_tcv].sum()
        count_opps = len(filtered_df)

        # 5. KPI CARDS
        st.subheader("Subtotals (Filtered Selection)")
        k1, k2, k3 = st.columns(3)
        
        k1.metric("Total Opportunities", f"{count_opps}")
        k2.metric(f"Total {col_fy}", f"{total_fy_musd:,.2f} MUSD")
        k3.metric(f"Total {col_tcv}", f"{total_tcv_musd:,.2f} MUSD")

        # 6. GRAPHS (Optional Toggle)
        st.sidebar.markdown("---")
        if st.sidebar.checkbox("Show Visualizations", value=True):
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                # Use the first available column for chart axis if Stage isn't found
                chart_axis = find_col(["Stage", "Status", "Leader"])
                fig1 = px.bar(filtered_df, x=chart_axis, y=col_tcv, title=f"{col_tcv} by {chart_axis}")
                st.plotly_chart(fig1, use_container_width=True)
            with c2:
                fig2 = px.histogram(filtered_df, x=col_fy, title=f"Distribution of {col_fy}")
                st.plotly_chart(fig2, use_container_width=True)

        # 7. DATA TABLE WITH TOTAL ROW
        st.markdown("---")
        st.subheader("Detailed Data View")

        # Create a summary row for the table
        summary_data = {col: "" for col in all_cols}
        summary_data[all_cols[0]] = "SUBTOTAL"
        summary_data[col_fy] = total_fy_musd
        summary_data[col_tcv] = total_tcv_musd
        
        summary_df = pd.DataFrame([summary_data])

        # Combine actual data + summary row
        # (Using .astype(str) for the first column to avoid mixing types)
        final_display_df = pd.concat([filtered_df, summary_df], ignore_index=True)

        # Styling to highlight the last row
        st.dataframe(final_display_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Please upload your Excel file to start.")