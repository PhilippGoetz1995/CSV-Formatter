from dotenv import load_dotenv
import os
import streamlit as st
import pandas as pd
from io import StringIO
from typing import Optional

# Address Handling
from opencage.geocoder import OpenCageGeocode

load_dotenv()
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY")

geocoder = OpenCageGeocode(OPENCAGE_API_KEY)

# ------------------ Address Handling ------------------ #

def address_to_iso_3166_2_opencage(address: str) -> Optional[str]:
    """
    Use OpenCage API to return ISO 3166-2 subdivision code for an address.
    Falls back to ISO 3166-1 alpha-2 if subdivision is unavailable.
    """
    if not address:
        return None

    try:
        results = geocoder.geocode(address)
    except Exception as e:
        print(f"OpenCage error: {e}")
        return None

    if not results:
        return None

    # The OpenCage geocoder returns a list of results; each result has a 'components' dict.
    comp = results[0].get("components", {})

    iso3166_2 = comp.get("ISO_3166-2")

    if isinstance(iso3166_2, list) and len(iso3166_2) > 0:
        # Return the first subdivision code (e.g., 'US-CA')
        return iso3166_2[0]
    elif isinstance(iso3166_2, str) and iso3166_2:
        return iso3166_2

    # Fallback: return country code only in ISO 3166-1 alpha-2 (uppercase)
    country_code = comp.get("country_code")
    if country_code:
        return country_code.upper()

    return None




# ------------------ STREAMLIT UI ------------------ #

st.set_page_config(page_title="P-Goetz CSV Cleaner", layout="wide")

st.title("🧹 CSV Cleaner: Dates, Numbers, Phone Numbers & Addresses")
st.markdown(
    '<a href="https://p-goetz.de/"><img src="https://img.shields.io/badge/Version-v0.2-blue"></a>',
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

    st.write("---")
    st.subheader("2️⃣ Format Adress to iso_3166 in new Column")
    address_columns = st.selectbox(
        "Columns containing Address",
        options=list(df.columns),
    )


    st.write("---")

    if st.button("🚀 Apply transformations & generate cleaned CSV"):

        # First just copy dataframe into a new one to avoid modifying the original
        df_clean = df.copy()

        # For the selected address column, add a new column with ISO 3166-2 code
        if address_columns:
            new_iso_col = f"{address_columns}_iso_3166_2"
            # Insert the new column immediately after the address column
            col_idx = df_clean.columns.get_loc(address_columns)
            # Show a progress bar while processing rows (loading animation)
            with st.spinner("Looking up ISO 3166-2 codes..."):
                iso_codes = []
                total = len(df_clean)
                progress_bar = st.progress(0)
                for idx, addr in enumerate(df_clean[address_columns]):
                    if pd.notnull(addr) and str(addr).strip():
                        iso_code = address_to_iso_3166_2_opencage(addr)
                    else:
                        iso_code = ""
                    iso_codes.append(iso_code)
                    if total > 1:
                        progress_bar.progress((idx + 1) / total)
                progress_bar.empty()  # Remove progress bar
            # Insert the new column
            df_clean.insert(col_idx + 1, new_iso_col, iso_codes)

            
        

        st.success("✅ Transformations applied successfully!")

        st.subheader("Preview of cleaned data")
        st.dataframe(df_clean.head())


        # ----> This section converts the cleaned DataFrame to a CSV buffer for download.
        # 1. Create a StringIO object to hold the CSV data => to not store it on the disk
        # 2. Convert the DataFrame to CSV using the selected delimiter
        # 3. Encode the CSV data to UTF-8
        # 4. Create a download button that allows the user to download the cleaned CSV

        csv_buffer = StringIO()
        df_clean.to_csv(csv_buffer, index=False, sep=delimiter)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")

        st.download_button(
            label="⬇️ Download cleaned CSV",
            data=csv_bytes,
            file_name="cleaned_cleaned.csv",
            mime="text/csv",
        )

else:
    st.info("Please upload a CSV file to get started.")