import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from io import StringIO
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import time
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False

st.set_page_config(page_title="CSV Cleaner (Dates, Numbers, Phones, Addresses)", layout="wide")

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


def format_numeric_string(
    raw: str,
    target_decimal: str,
    target_thousands: str | None,
    decimal_places: int | None = None,
):
    """
    Take a raw number string, normalize it, and reformat it with the desired separators
    and optional fixed decimal places. If it can't be parsed as a number, return the
    original raw string.
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

    if decimal_places is not None:
        try:
            quantizer = Decimal("1").scaleb(-decimal_places)
            norm = format(
                Decimal(norm).quantize(quantizer, rounding=ROUND_HALF_UP), "f"
            )
        except (InvalidOperation, ValueError):
            return raw

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


# ------------------ ADDRESS HANDLING ------------------ #

@st.cache_data
def get_geocoder():
    """Initialize and cache the geocoder instance."""
    if not GEOPY_AVAILABLE:
        return None
    try:
        # Try to initialize with default settings first
        return Nominatim(user_agent="csv_formatter_app")
    except AttributeError as e:
        # Handle SSL context error - try with scheme specification
        try:
            # Workaround for SSL context issues
            from geopy.adapters import RequestsAdapter
            return Nominatim(
                user_agent="csv_formatter_app",
                scheme='https',
                adapter_factory=RequestsAdapter
            )
        except Exception:
            # If that fails, try without specifying adapter
            try:
                return Nominatim(
                    user_agent="csv_formatter_app",
                    scheme='https'
                )
            except Exception:
                # Last resort - just return None and let user know
                st.error(
                    "⚠️ Error initializing geocoder. This may be due to SSL/requests library compatibility. "
                    "Please try: `pip install --upgrade geopy requests`"
                )
                return None


def extract_iso3166_2_code(address: str, geocoder_cache: dict = None):
    """
    Extract ISO-3166-2 code from an address string using geocoding.
    Returns the ISO-3166-2 code (e.g., "US-CA", "DE-BY") or None if not found.
    Uses reverse geocoding which provides more reliable ISO-3166-2 codes.
    """
    if geocoder_cache is None:
        geocoder_cache = {}
    
    if pd.isna(address):
        return None
    
    address_str = str(address).strip()
    if not address_str:
        return None
    
    # Check cache first
    if address_str in geocoder_cache:
        return geocoder_cache[address_str]
    
    if not GEOPY_AVAILABLE:
        return None
    
    try:
        geocoder = get_geocoder()
        if geocoder is None:
            return None
        
        # Step 1: Geocode the address to get coordinates
        # Use addressdetails=True to get full address information
        try:
            location = geocoder.geocode(address_str, timeout=10, exactly_one=True, addressdetails=True)
        except AttributeError as e:
            # Handle SSL context error - this is a known geopy/requests compatibility issue
            if 'ssl_context' in str(e) or 'RequestsHTTPWithSSLContextAdapter' in str(e):
                # Suggest updating libraries
                import warnings
                warnings.warn(
                    "Geopy SSL error detected. Please update: pip install --upgrade geopy requests urllib3",
                    UserWarning
                )
            # Try fallback without addressdetails
            try:
                location = geocoder.geocode(address_str, timeout=10, exactly_one=True)
            except Exception:
                geocoder_cache[address_str] = None
                return None
        except Exception:
            # Fallback without addressdetails
            try:
                location = geocoder.geocode(address_str, timeout=10, exactly_one=True)
            except Exception:
                geocoder_cache[address_str] = None
                return None
        
        if location is None:
            geocoder_cache[address_str] = None
            return None
        
        iso_code = None
        
        # Step 2: Try to get ISO-3166-2 from forward geocoding result first
        # Check the raw response structure
        raw_data = location.raw
        address_components = raw_data.get('address', {})
        
        # Also check if ISO code is at the root level
        if 'ISO3166-2' in raw_data:
            iso_code = raw_data['ISO3166-2']
        
        # Check all keys in raw_data for ISO3166-2
        if iso_code is None:
            for key in raw_data.keys():
                if 'ISO3166-2' in key.upper():
                    value = raw_data[key]
                    if value:
                        iso_code = value
                        break
        
        # Check multiple possible locations for ISO-3166-2 code
        # Nominatim sometimes puts it in different places
        if 'ISO3166-2' in address_components:
            iso_code = address_components['ISO3166-2']
        elif 'ISO3166-2:lvl4' in address_components:  # Sometimes in level fields
            iso_code = address_components['ISO3166-2:lvl4']
        elif 'ISO3166-2:lvl6' in address_components:
            iso_code = address_components['ISO3166-2:lvl6']
        # Check for state_code + country_code (common in US addresses)
        elif 'state_code' in address_components:
            country_code = address_components.get('country_code', '').upper()
            state_code = address_components['state_code'].upper()
            if country_code:
                iso_code = f"{country_code}-{state_code}"
        
        # Step 3: If not found, use reverse geocoding (often more reliable for ISO codes)
        if iso_code is None:
            try:
                # Use addressdetails=True to get full address details in reverse geocoding
                reverse_location = geocoder.reverse(
                    (location.latitude, location.longitude),
                    timeout=10,
                    exactly_one=True,
                    language='en',
                    addressdetails=True
                )
                
                if reverse_location:
                    reverse_raw = reverse_location.raw
                    reverse_address = reverse_raw.get('address', {})
                    
                    # Check for ISO-3166-2 in reverse geocoding results (multiple possible locations)
                    # Check direct address fields
                    if 'ISO3166-2' in reverse_address:
                        iso_code = reverse_address['ISO3166-2']
                    # Check for variations like ISO3166-2:lvl4, ISO3166-2:lvl6
                    for key in reverse_address.keys():
                        if 'ISO3166-2' in key.upper():
                            iso_code = reverse_address[key]
                            break
                    
                    # Also check extratags which sometimes contains ISO codes
                    if iso_code is None and 'extratags' in reverse_raw:
                        extratags = reverse_raw.get('extratags', {})
                        if 'ISO3166-2' in extratags:
                            iso_code = extratags['ISO3166-2']
                        # Check all extratags for ISO3166-2
                        else:
                            for key in extratags.keys():
                                if 'ISO3166-2' in key.upper():
                                    iso_code = extratags[key]
                                    break
                    
                    # Try constructing from state_code (for US and some other countries)
                    if iso_code is None and 'state_code' in reverse_address:
                        country_code = reverse_address.get('country_code', '').upper()
                        state_code = reverse_address['state_code'].upper()
                        if country_code and state_code:
                            iso_code = f"{country_code}-{state_code}"
                    
                    # Try other administrative codes (county_code, etc.)
                    if iso_code is None:
                        country_code = reverse_address.get('country_code', '').upper()
                        # Check for various administrative codes
                        for code_field in ['state_code', 'county_code', 'region_code', 'province_code']:
                            if code_field in reverse_address:
                                admin_code = reverse_address[code_field].upper()
                                if country_code and admin_code:
                                    iso_code = f"{country_code}-{admin_code}"
                                    break
                    
                    # Try to find in all reverse_raw keys (sometimes it's at root level)
                    if iso_code is None:
                        for key in reverse_raw.keys():
                            if 'ISO3166-2' in key.upper():
                                value = reverse_raw[key]
                                if value:
                                    iso_code = value
                                    break
                    
            except Exception:
                pass
        
        # Step 4: If still not found, try to construct from available fields
        if iso_code is None:
            country_code = address_components.get('country_code', '').upper()
            
            # Try to find administrative level fields that might have codes
            # Nominatim uses admin_level fields (1-10) where lower numbers are larger areas
            for level in ['1', '2', '3', '4']:
                admin_level = address_components.get(f'admin_level_{level}')
                if admin_level:
                    # Some countries use numeric codes we could map, but this is complex
                    # Better to rely on reverse geocoding which we already tried
                    break
        
        # Cache the result
        geocoder_cache[address_str] = iso_code
        
        # Rate limiting: be nice to the geocoding service
        time.sleep(1)
        
        return iso_code
        
    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
        # If geocoding fails, cache None and return None
        geocoder_cache[address_str] = None
        return None


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

st.title("🧹 CSV Cleaner: Dates, Numbers, Phone Numbers & Addresses")
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

    col1, col2, col3 = st.columns(3)
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

    with col3:
        decimal_places = st.selectbox(
            "Decimal places to display",
            options=[None, 0, 1, 2, 3, 4, 5, 6],
            index=0,
            format_func=lambda x: "Preserve input"
            if x is None
            else f"{x} decimal{'s' if x != 1 else ''}",
        )

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
    st.subheader("4️⃣ Address column (ISO-3166-2 codes)")
    address_column = st.selectbox(
        "Select the column containing addresses (a new column with ISO-3166-2 codes will be added)",
        options=["None"] + list(df.columns),
        index=0,
        help="ISO-3166-2 codes are country subdivision codes (e.g., US-CA for California, DE-BY for Bavaria)",
    )
    
    if address_column != "None":
        if not GEOPY_AVAILABLE:
            st.warning("⚠️ The 'geopy' library is not installed. Please install it to use this feature: `pip install geopy`")
        else:
            st.info("ℹ️ Address geocoding may take some time and requires an internet connection. Progress will be shown during processing.")
            
            # Debug/test feature - show what data is available for a sample address
            with st.expander("🔍 Test address geocoding (debug mode)"):
                test_address = st.text_input(
                    "Enter an address to test (or leave empty to use first address from your data):",
                    value="",
                    help="This will show you what data Nominatim returns for an address, which can help debug ISO-3166-2 extraction"
                )
                if st.button("Test geocoding", key="test_geocode"):
                    if not test_address and address_column != "None" and len(df) > 0:
                        test_address = str(df[address_column].iloc[0])
                    
                    if test_address:
                        try:
                            geocoder = get_geocoder()
                            st.write(f"**Testing address:** {test_address}")
                            
                            # Forward geocoding
                            with st.spinner("Geocoding address..."):
                                try:
                                    location = geocoder.geocode(test_address, timeout=10, exactly_one=True, addressdetails=True)
                                except AttributeError as e:
                                    if 'ssl_context' in str(e) or 'RequestsHTTPWithSSLContextAdapter' in str(e):
                                        st.error(
                                            "❌ SSL Context Error detected!\n\n"
                                            "This is a known issue with geopy/requests library compatibility.\n\n"
                                            "**Solution:** Please update your libraries by running:\n"
                                            "```bash\n"
                                            "pip install --upgrade geopy requests urllib3\n"
                                            "```\n\n"
                                            "Or if using conda:\n"
                                            "```bash\n"
                                            "conda update geopy requests urllib3\n"
                                            "```"
                                        )
                                        st.stop()
                                    raise  # Re-raise if it's a different AttributeError
                            
                            if location:
                                st.success(f"✅ Geocoded successfully: {location.latitude}, {location.longitude}")
                                
                                # Show raw data
                                raw_data = location.raw
                                st.write("**Raw geocoding data:**")
                                st.json(raw_data)
                                
                                # Show address components
                                address_components = raw_data.get('address', {})
                                st.write("**Address components:**")
                                st.json(address_components)
                                
                                # Try reverse geocoding
                                with st.spinner("Reverse geocoding..."):
                                    reverse_location = geocoder.reverse(
                                        (location.latitude, location.longitude),
                                        timeout=10,
                                        exactly_one=True,
                                        language='en',
                                        addressdetails=True
                                    )
                                
                                if reverse_location:
                                    st.write("**Reverse geocoding data:**")
                                    st.json(reverse_location.raw)
                                
                                # Test extraction
                                iso_code = extract_iso3166_2_code(test_address, {})
                                if iso_code:
                                    st.success(f"✅ Extracted ISO-3166-2 code: **{iso_code}**")
                                else:
                                    st.warning("⚠️ Could not extract ISO-3166-2 code. Check the data above to see what fields are available.")
                            else:
                                st.error("❌ Could not geocode this address")
                        except Exception as e:
                            st.error(f"Error during geocoding: {e}")
                    else:
                        st.warning("Please enter an address or ensure your CSV has data in the selected address column.")

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
                    lambda v: format_numeric_string(
                        v, target_decimal, target_thousands, decimal_places
                    )
                )

        # Phone numbers
        for col in phone_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(
                    lambda v: format_phone_e164(v, default_region=default_region)
                )

        # Address column - add ISO-3166-2 code column
        if address_column != "None" and address_column in df_clean.columns:
            if GEOPY_AVAILABLE:
                iso_column_name = f"{address_column}_ISO3166-2"
                geocoder_cache = {}
                
                # Show progress
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_rows = len(df_clean)
                iso_codes = []
                ssl_error_detected = False
                
                try:
                    for idx, address in enumerate(df_clean[address_column]):
                        status_text.text(f"Processing address {idx + 1} of {total_rows}...")
                        try:
                            iso_code = extract_iso3166_2_code(address, geocoder_cache)
                            iso_codes.append(iso_code if iso_code else "")
                        except AttributeError as e:
                            # Check for SSL context error
                            if 'ssl_context' in str(e) or 'RequestsHTTPWithSSLContextAdapter' in str(e):
                                ssl_error_detected = True
                                progress_bar.empty()
                                status_text.empty()
                                st.error(
                                    "❌ **SSL Context Error detected!**\n\n"
                                    "This is a known issue with geopy/requests library compatibility.\n\n"
                                    "**Solution:** Please update your libraries by running:\n"
                                    "```bash\n"
                                    "pip install --upgrade geopy requests urllib3\n"
                                    "```\n\n"
                                    "Or if using conda:\n"
                                    "```bash\n"
                                    "conda update geopy requests urllib3\n"
                                    "```\n\n"
                                    "After updating, restart your application and try again."
                                )
                                break
                            else:
                                # Different AttributeError - append empty and continue
                                iso_codes.append("")
                        except Exception as e:
                            # Other errors - append empty and continue
                            iso_codes.append("")
                        
                        if not ssl_error_detected:
                            progress_bar.progress((idx + 1) / total_rows)
                
                except Exception as e:
                    if not ssl_error_detected:
                        st.error(f"Error during address processing: {e}")
                
                if ssl_error_detected:
                    # Fill remaining with empty strings
                    while len(iso_codes) < total_rows:
                        iso_codes.append("")
                    # Don't add the column if SSL error occurred
                    st.stop()
                
                # Add the new column
                df_clean[iso_column_name] = iso_codes
                
                status_text.text(f"✅ Completed processing {total_rows} addresses")
                progress_bar.empty()
                status_text.empty()
                
                # Show statistics
                non_empty_codes = sum(1 for code in iso_codes if code)
                if total_rows > 0:
                    success_rate = non_empty_codes / total_rows * 100
                    st.info(f"📍 Extracted ISO-3166-2 codes for {non_empty_codes} out of {total_rows} addresses ({success_rate:.1f}%)")
                else:
                    st.info("📍 No addresses to process")
            else:
                st.warning("⚠️ Cannot process addresses: 'geopy' library is not installed. Please install it: `pip install geopy`")

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
