import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from io import StringIO
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
import re

st.set_page_config(page_title="CSV Cleaner (Dates, Numbers, Phones)", layout="wide")

# ------------------ DATE HANDLING ------------------ #

COMMON_DATE_FORMATS = [
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
    for fmt in COMMON_DATE_FORMATS:
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


# ------------------ NUMBER HANDLING ------------------ #

def normalize_numeric_string(raw: str):
    """
    Normalize a human-formatted number string into a canonical form:
        sign + digits[.digits]
    Returns None if it can't be interpreted as a number.
    """
    if pd.isna(raw):
        return None

    s = str(raw).strip().replace(" ", "")  # remove spaces
    if not s:
        return None

    # Handle sign
    sign = ""
    if s[0] in "+-":
        sign, s = s[0], s[1:]

    # If nothing left: invalid
    if not s:
        return None

    # Determine decimal and thousands separators based on positions of '.' and ','
    dot_pos = s.rfind(".")
    comma_pos = s.rfind(",")

    decimal_char = None
    thousands_char = None

    if "." in s and "," in s:
        # Assume the last separator is the decimal separator
        if comma_pos > dot_pos:
            decimal_char = ","
            thousands_char = "."
        else:
            decimal_char = "."
            thousands_char = ","
    elif "," in s:
        # Only comma present -> treat as decimal separator
        decimal_char = ","
        thousands_char = None
    elif "." in s:
        # Only dot present -> treat as decimal separator
        decimal_char = "."
        thousands_char = None
    else:
        # No separators -> integer
        decimal_char = None
        thousands_char = None

    # Remove thousands separator
    if thousands_char:
        s = s.replace(thousands_char, "")

    # Replace decimal char with '.'
    if decimal_char and decimal_char != ".":
        s = s.replace(decimal_char, ".")

    # Validate: allowed: digits + optional one dot
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        return None

    return sign + s


def format_numeric_string(raw: str, target_decimal: str, target_thousands: str | None):
    """
    Take a raw number string, normalize it, and reformat it with the desired separators.
    If it can't be parsed as a number, return the original raw string.
    """
    if pd.isna(raw):
        return raw

    norm = normalize_numeric_string(raw)
    if norm is None:
        return raw

    # Separate sign
    sign = ""
    if norm[0] in "+-":
        sign, norm = norm[0], norm[1:]

    int_part, _, frac_part = norm.partition(".")

    # Add thousands separators to integer part
    if target_thousands:
        groups = []
        while len(int_part) > 3:
            groups.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        if int_part:
            groups.insert(0, int_part)
        int_part_formatted = target_thousands.join(groups)
    else:
        int_part_formatted = int_part

    if frac_part:
        return f"{sign}{int_part_formatted}{target_decimal}{frac_part}"
    else:
        return f"{sign}{int_part_formatted}"


# ------------------ PHONE HANDLING ------------------ #

def format_phone_e164(value: str, default_region: str = "DE"):
    """
    Convert a phone number string into E.164 format (+<countrycode><number>).
    If parsing fails or number is invalid, return the original value.
    """
    if pd.isna(value):
        return value

    s = str(value).strip()
    if not s:
        return value

    try:
        num = phonenumbers.parse(s, default_region)
    except NumberParseException:
        return value

    if not phonenumbers.is_valid_number(num):
        return value

    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


# ------------------ STREAMLIT UI ------------------ #

st.title("🧹 CSV Cleaner: Dates, Numbers & Phone Numbers")
st.write(
    """
Upload a CSV, select which columns contain dates, numbers and phone numbers,
then download a cleaned CSV:
- Dates → normalized to **YYYY-MM-DD**
- Numbers → configurable decimal/thousands separators
- Phone numbers → normalized to **E.164** (`+491701234567`)
"""
)

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

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
    st.subheader("2️⃣ Number columns & format")
    number_columns = st.multiselect(
        "Columns containing numbers to reformat",
        options=list(df.columns),
    )

    col1, col2 = st.columns(2)
    with col1:
        target_decimal = st.selectbox(
            "Decimal separator",
            options=[".", ","],
            index=0,
            format_func=lambda x: f"{x} (decimal)",
        )
    with col2:
        thousands_choice = st.selectbox(
            "Thousands separator",
            options=["None", ",", ".", "Space"],
            index=0,
            format_func=lambda x: {
                "None": "No thousands separator",
                ",": "Comma (,)",
                ".": "Dot (.)",
                "Space": "Space ( )",
            }[x],
        )

    if thousands_choice == "None":
        target_thousands = None
    elif thousands_choice == "Space":
        target_thousands = " "
    else:
        target_thousands = thousands_choice

    st.write("---")
    st.subheader("3️⃣ Phone number columns (E.164)")
    phone_columns = st.multiselect(
        "Columns containing phone numbers (will be converted to E.164 if possible)",
        options=list(df.columns),
    )

    default_region = st.text_input(
        "Default country/region for phone parsing (2-letter code, e.g. DE, AT, CH, US)",
        value="DE",
        max_chars=2,
    ).upper()

    st.write("---")
    if st.button("🚀 Apply transformations & generate cleaned CSV"):
        df_clean = df.copy()

        # Dates
        for col in date_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(parse_mixed_date)

        # Numbers
        for col in number_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(
                    lambda v: format_numeric_string(v, target_decimal, target_thousands)
                )

        # Phone numbers
        for col in phone_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(
                    lambda v: format_phone_e164(v, default_region=default_region)
                )

        st.success("✅ Transformations applied successfully!")

        st.subheader("Preview of cleaned data")
        st.dataframe(df_clean.head())

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
