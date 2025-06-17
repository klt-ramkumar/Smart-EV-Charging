import requests
import streamlit as st

class CarbonIntensity:
    def __init__(self):
        self.api_url = "https://api.carbonintensity.org.uk/regional"
        self.cached_data = None

    def fetch_data(self):
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            self.cached_data = response.json()
        except Exception as e:
            st.warning(f"Carbon intensity data not available: {e}")
            self.cached_data = None

    def get_intensity_by_dnoregion(self, dnoregion_name):
        if not self.cached_data:
            self.fetch_data()
        if not self.cached_data:
            return None, None

        regions = self.cached_data['data'][0]['regions']
        for region in regions:
            if region['dnoregion'] == dnoregion_name:
                actual = region['intensity'].get('actual')
                forecast = region['intensity'].get('forecast')
                return actual, forecast
        return None, None
