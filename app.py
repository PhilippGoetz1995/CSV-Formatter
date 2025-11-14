import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from io import StringIO

st.set_page_config(page_title="CSV Date Fixer", layout="wide")

COMMON_FORMATS = [
    "%Y-%m-%d",  # 2003-08-25
    "%d.%m.%Y",  # 25.08.2003
    "%d/%m/%Y",  # 25/08/2003
    "%m/%d/%Y",  # 08/25/2003
    "%d-%m-%Y",  # 25-08-2003
    "%m-%d-%Y",  # 08-25-2003
    "%d.%m.%y",  # 25.08.03
    "%d/%m/%y",  # 25/08/03
    "%m/%d/%y",  # 08/25/03
]


def parse_mixed_date(value: str):
    """Try to convert a value to ISO date (YYYY-MM-DD). If not possible, return the original."""
    if pd.isna(value):
        return value

    s = str(value).strip()
    if not s:
        return value

    # Try strict formats first
    for fmt in COMMON_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue

    # Fallback: very flexible parser (assume dayfirst to handle European formats)
    try:
        dt = date_parser.parse(s, dayfirst=True)
        return dt.date().isoformat()
    except Exception:
        return value


st.title("📅 CSV Date Fixer")
st.write("Upload a CSV, fix date columns, preview, and download the cleaned CSV.")

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

# Optional: choose delimiter
delimiter = st.radio("CSV delimiter", options=[",", ";", "\t"], index=0, format_func=lambda x: {";": "Semicolon (;)", ",": "Comma (,)", "\t": "Tab"}[x])

if uploaded_file is not None:
    # Read as strings to avoid automatic date parsing
    try:
        df = pd.read_csv(uploaded_file, dtype=str, sep=delimiter)
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()

    st.subheader("Preview of uploaded data")
    st.dataframe(df.head())

    st.write("---")
    st.subheader("Select date columns to normalize")

    # Let user choose which columns contain dates
    date_columns = st.multiselect(
        "Columns that contain dates",
        options=list(df.columns),
    )

    if date_columns:
        st.write("The following columns will be converted to ISO format (YYYY-MM-DD):")
        st.write(date_columns)

        if st.button("🛠 Fix dates"):
            df_clean = df.copy()
            for col in date_columns:
                df_clean[col] = df_clean[col].apply(parse_mixed_date)

            st.success("Dates normalized successfully!")

            st.subheader("Preview of cleaned data")
            st.dataframe(df_clean.head())

            # Convert back to CSV for download
            csv_buffer = StringIO()
            df_clean.to_csv(csv_buffer, index=False, sep=delimiter)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")

            st.download_button(
                label="⬇️ Download cleaned CSV",
                data=csv_bytes,
                file_name="cleaned_dates.csv",
                mime="text/csv",
            )
    else:
        st.info("Select at least one column to treat as a date column.")
else:
    st.info("Please upload a CSV file to get started.")
