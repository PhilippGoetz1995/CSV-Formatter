# Frontend Libraries
import streamlit as st
import pandas as pd

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False



# ------------------ STREAMLIT UI ------------------ #

st.set_page_config(page_title="P-Goetz CSV Cleaner", layout="wide")

st.title("🧹 CSV Cleaner: Dates, Numbers, Phone Numbers & Addresses")
st.markdown(
    '<a href="https://p-goetz.de/"><img src="https://img.shields.io/badge/Version-v0.1-blue"></a>',
    unsafe_allow_html=True
)
st.write(
    """
Upload a CSV, select which columns contain dates, numbers, phone numbers, and addresses,
then download a cleaned CSV:
- Dates → normalized to **YYYY-MM-DD**
- Numbers → configurable separators & decimal places
- Phone numbers → normalized to **E.164** (`+491701234567`)
- Addresses → extract **ISO-3166-2** codes (e.g., `US-CA`, `DE-BY`)
"""
)

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

# Optional: choose delimiter
delimiter = st.radio(
    "CSV delimiter",
    options=[",", ";", "\t"],
    index=0,
    format_func=lambda x: {",": "Comma (,)", ";": "Semicolon (;)", "\t": "Tab (\\t)"}[x],
)

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, dtype=str, sep=delimiter)
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()

    st.subheader("Preview of uploaded data")
    st.dataframe(df.head())


    st.write("---")
    st.subheader("1️⃣ Date columns")
    date_columns = st.multiselect(
        "Columns containing dates (will be converted to ISO: YYYY-MM-DD)",
        options=list(df.columns),
    )


else:
    st.info("Please upload a CSV file to get started.")