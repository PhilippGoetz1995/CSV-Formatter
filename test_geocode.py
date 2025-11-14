import streamlit as st
from geopy.geocoders import Nominatim

st.title("Geocode Test")

address = st.text_input("Enter an address:")

if st.button("Geocode"):
    if not address:
        st.error("Please enter an address.")
    else:
        try:
            # Create a fresh geocoder object each time (important!)
            geolocator = Nominatim(user_agent="streamlit-test-app", timeout=10)

            location = geolocator.geocode(address)
            if location:
                st.success("Geocoding successful!")
                st.write(f"**Address:** {location.address}")
                st.write(f"**Latitude:** {location.latitude}")
                st.write(f"**Longitude:** {location.longitude}")
            else:
                st.warning("Could not find this address.")
        except Exception as e:
            st.error(f"Error during geocoding: {e}")
