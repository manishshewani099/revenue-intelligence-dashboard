import pandas as pd

def load_data(uploaded_file):
    df = pd.read_excel(
        uploaded_file,
        sheet_name="7b_Consolidated_Opps"
    )
    return df

