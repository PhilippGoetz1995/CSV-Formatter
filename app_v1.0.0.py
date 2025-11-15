from dotenv import load_dotenv
import os
import streamlit as st
import pandas as pd
from io import StringIO
from typing import Optional

# Number Handling
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Phonenumbers Handling
import phonenumbers

# Address Handling
from opencage.geocoder import OpenCageGeocode

load_dotenv()
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY")

geocoder = OpenCageGeocode(OPENCAGE_API_KEY)


# --------- Function 1: Numbers ---------- #
def parse_numeric_string(value: str) -> Optional[Decimal]:
    """
    Try to interpret a string as a number, handling both EU and US formats.
    Examples:
      "1.234,56" -> 1234.56
      "1,234.56" -> 1234.56
      "1234"     -> 1234
    Returns Decimal or None if parsing fails.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    s = str(value).strip()
    if not s:
        return None

    # Find the last comma/dot and treat it as decimal separator
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")
    last_sep = max(last_comma, last_dot)

    if last_sep == -1:
        # No decimal sep, just remove non-digit/+/-
        numeric_str = re.sub(r"[^\d+-]", "", s)
    else:
        int_part = s[:last_sep]
        frac_part = s[last_sep + 1 :]

        int_part_clean = re.sub(r"[^\d+-]", "", int_part)
        frac_part_clean = re.sub(r"[^\d]", "", frac_part)

        if frac_part_clean:
            numeric_str = f"{int_part_clean}.{frac_part_clean}"
        else:
            numeric_str = int_part_clean

    try:
        return Decimal(numeric_str)
    except InvalidOperation:
        return None


def format_numeric_string(
    value: str,
    decimal_sep: str,
    thousands_sep: str,
    decimal_places: int,
) -> str:
    """
    Parse an incoming numeric string and format it with the given
    decimal separator, thousands separator, and decimal places.
    If parsing fails, return the original value.
    """
    num = parse_numeric_string(value)
    if num is None:
        return value

    # Round to requested decimal places
    quant = Decimal(10) ** -decimal_places if decimal_places > 0 else Decimal("1")
    num = num.quantize(quant, rounding=ROUND_HALF_UP)

    # Convert to canonical string with '.' as decimal separator
    s = f"{num:f}"
    if "." in s:
        int_part, frac_part = s.split(".")
    else:
        int_part, frac_part = s, ""

    # Apply thousands separator
    sign = ""
    if int_part.startswith("-") or int_part.startswith("+"):
        sign, int_part = int_part[0], int_part[1:]

    if thousands_sep:
        groups = []
        while int_part:
            groups.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        int_part_formatted = sign + thousands_sep.join(groups)
    else:
        int_part_formatted = sign + int_part

    # Apply decimal separator
    if decimal_places > 0:
        frac_part = (frac_part + "0" * decimal_places)[:decimal_places]
        return f"{int_part_formatted}{decimal_sep}{frac_part}"
    else:
        return int_part_formatted

# --------- Function 2: Phone Number ---------- #
def normalize_phone_to_e164(value: str, default_region: str = "DE") -> str:
    """
    Normalize a phone number to E.164 format (e.g. +491701234567).
    If parsing fails, return the original value.
    """
    if pd.isna(value):
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    # Remove spaces and common separators, keep leading +
    raw = re.sub(r"[^\d+]", "", raw)

    try:
        if raw.startswith("+"):
            parsed = phonenumbers.parse(raw, None)
        else:
            parsed = phonenumbers.parse(raw, default_region)

        if not (phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed)):
            return value

        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return value

# --------- Function 3: Date ---------- #
def normalize_date_to_iso(value: str) -> str:
    """
    Try to parse a date string and return it as YYYY-MM-DD.
    If parsing fails, return the original value.
    """
    if pd.isna(value):
        return ""

    s = str(value).strip()
    if not s:
        return ""

    # Try European style first (dayfirst=True), then fallback
    for dayfirst in (True, False):
        try:
            dt = pd.to_datetime(s, dayfirst=dayfirst, errors="raise")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue

    # If nothing works, keep original
    return s


# --------- Function 4: Adresses ---------- #
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

    # Check for "ISO_3166-2"
    if isinstance(iso3166_2, list) and len(iso3166_2) > 0:
        # Return the first subdivision code (e.g., 'US-CA')
        return iso3166_2[0]
    elif isinstance(iso3166_2, str) and iso3166_2:
        return iso3166_2

    # Try combining "ISO_3166-1_alpha-2" and "state_code"
    iso3166_1 = comp.get("ISO_3166-1_alpha-2")
    state_code = comp.get("state_code")
    if iso3166_1 and state_code:
        return f"{iso3166_1}-{state_code}"

    # If neither, then return None
    return None





# ------------------ STREAMLIT UI ------------------ #
st.markdown("""
    <style>
        .block-container {
            padding-top: 4rem;
        }
    </style>
    <p style="text-align:center;">
        <img src="https://p-goetz.de/wp-content/uploads/2024/12/RedBull_Logo.jpg" width="180">
    </p>
    """,
    unsafe_allow_html=True
)

st.set_page_config(page_title="P-Goetz CSV Cleaner", layout="wide")

st.title("🧹 CSV Cleaner: Dates, Numbers, Phone Numbers & Addresses")
st.markdown(
    '<a href="https://p-goetz.de/"><img src="https://img.shields.io/badge/Version-v1.0.0-blue"></a>',
    unsafe_allow_html=True
)
st.write(
    """
Upload a CSV, select which columns contain dates, numbers, phone numbers, and addresses,
then download a cleaned CSV:
- Numbers → configurable separators & decimal places
- Dates → normalized to **YYYY-MM-DD**
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


    # --------- Function 1: Numbers ---------- #
    st.write("---")
    st.subheader("1️⃣ Normalize Numbers")

    number_columns = st.multiselect(
        "Columns containing numbers (optional)",
        options=list(df.columns),
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        target_decimal = st.selectbox(
            "Decimal separator",
            options=[".", ","],
            index=0,
        )
    with col_b:
        target_thousands = st.selectbox(
            "Thousands separator",
            options=["", ",", ".", " "],
            index=0,
            format_func=lambda x: {
                "": "None",
                ",": "Comma (,)",
                ".": "Dot (.)",
                " ": "Space",
            }[x],
        )
    with col_c:
        decimal_places = st.number_input(
            "Decimal places",
            min_value=0,
            max_value=10,
            value=2,
            step=1,
        )

    # --------- Function 2: Dates ---------- #
    st.write("---")
    st.subheader("2️⃣ Normalize Dates to YYYY-MM-DD")

    date_column = st.selectbox(
        "Column containing dates (optional)",
        options=[""] + list(df.columns),
        index=0,
    )

    # --------- Function 3: Phone Numbers ---------- #
    st.write("---")
    st.subheader("3️⃣ Normalize Phone Numbers to E.164")

    phone_column = st.selectbox(
        "Column containing phone numbers (optional)",
        options=[""] + list(df.columns),
        index=0,
    )
    default_region = st.text_input(
        "Default region (for numbers without country code)",
        value="DE",
        help="Use ISO 3166-1 alpha-2 country code, e.g. DE, AT, CH, US...",
    )


    # --------- Function 3: Adresses ---------- #
    st.write("---")
    st.subheader("4️⃣ Format Adress to iso_3166 in new Column")
    address_columns = st.selectbox(
        "Columns containing Address",
        options=[""] + list(df.columns),
        index=0,
    )


    st.write("---")
    if st.button("🚀 Apply transformations & generate cleaned CSV"):

        # First just copy dataframe into a new one to avoid modifying the original
        df_clean = df.copy()


        # --------- Function 1: Numbers ---------- #
        for col in number_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(
                    lambda v: format_numeric_string(
                        v,
                        decimal_sep=target_decimal,
                        thousands_sep=target_thousands,
                        decimal_places=int(decimal_places),
                    )
                )

        # --------- Function 2: Dates ---------- #
        if date_column != "":
            df_clean[date_column] = df_clean[date_column].apply(normalize_date_to_iso)

        # --------- Function 3: Phone Number ---------- #
        if phone_column != "":
            df_clean[phone_column] = df_clean[phone_column].apply(
                lambda v: normalize_phone_to_e164(v, default_region=default_region)
            )

        # --------- Function 4: Adresses ---------- #
        # For the selected address column, add a new column with ISO 3166-2 code
        if address_columns != "":
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