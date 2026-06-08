<> Python
import streamlit as st
import pandas as pd
import plotly.express as px

# Set page configuration
st.set_page_config(page_title="Sales Opportunity Dashboard", layout="wide")

st.title("📊 Sales Opportunity Dashboard")

# 1. Upload Excel file
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

if uploaded_file:
    try:
        # 2. Read specific sheet
        df = pd.read_excel(uploaded_file, sheet_name="7b_Consolidated_Opps")

        # Basic Data Cleaning: Ensure numeric types for calculations
        # Adjust column names if they have leading/trailing spaces in your file
        df.columns = df.columns.str.strip()
        
        # Ensure Probability and TCV are numeric
        if 'TCV' in df.columns:
            df['TCV'] = pd.to_numeric(df['TCV'], errors='coerce').fillna(0)
        if 'Probability' in df.columns:
            df['Probability'] = pd.to_numeric(df['Probability'], errors='coerce').fillna(0)

        # 5. Add sidebar filters
        st.sidebar.header("Filters")
        
        sales_leader = st.sidebar.multiselect(
            "Select Sales Leader",
            options=df["Sales Leader"].unique(),
            default=df["Sales Leader"].unique()
        )

        stage = st.sidebar.multiselect(
            "Select Stage",
            options=df["Stage"].unique(),
            default=df["Stage"].unique()
        )

        account = st.sidebar.multiselect(
            "Select Account",
            options=df["Account"].unique(),
            default=df["Account"].unique()
        )

        # 6. Update dashboard dynamically based on filters
        filtered_df = df[
            (df["Sales Leader"].isin(sales_leader)) &
            (df["Stage"].isin(stage)) &
            (df["Account"].isin(account))
        ]

        # 4. Show Metrics
        col1, col2, col3 = st.columns(3)
        
        total_opps = len(filtered_df)
        total_tcv = filtered_df["TCV"].sum()
        avg_prob = filtered_df["Probability"].mean() if not filtered_df.empty else 0

        col1.metric("Total Opportunities", f"{total_opps:,}")
        col2.metric("Total TCV", f"${total_tcv:,.2f}")
        col3.metric("Average Probability", f"{avg_prob:.1f}%")

        # Visualizations (Using Plotly)
        st.markdown("---")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("TCV by Stage")
            fig_stage = px.bar(filtered_df, x="Stage", y="TCV", color="Stage", 
                               title="Total TCV per Stage")
            st.plotly_chart(fig_stage, use_container_width=True)

        with chart_col2:
            st.subheader("TCV by Sales Leader")
            fig_leader = px.pie(filtered_df, values="TCV", names="Sales Leader", 
                                title="TCV Distribution by Leader")
            st.plotly_chart(fig_leader, use_container_width=True)

        # 3. Display dataframe
        st.subheader("Detailed Data View")
        st.dataframe(filtered_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error: Could not find sheet '7b_Consolidated_Opps' or file is malformed. {e}")
else:
    st.info("Please upload an Excel file to get started.")
