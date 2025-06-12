import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import requests
import matplotlib.pyplot as plt
import pytz
import plotly.express as px

# Set Streamlit page config FIRST
st.set_page_config(layout="wide", page_title="Smart EV Charging Scheduler")

# --- Region Selection ---
REGION_CODES = {
    "East Midlands": "E",
    "Eastern England": "F",
    "London": "A",
    "Merseyside and North Wales": "D",
    "Midlands": "M",
    "North East England": "C",
    "North Scotland": "P",
    "North West England": "B",
    "South East England": "J",
    "South Scotland": "N",
    "South Wales": "K",
    "South West England": "G",
    "Southern England": "H",
    "Yorkshire": "Y"
}

region_df = pd.DataFrame({
    "region": list(REGION_CODES.keys()),
    "code": list(REGION_CODES.values()),
    "lat": [52.8, 52.4, 51.5, 53.4, 52.5, 54.9, 57.5, 53.8, 51.3, 55.9, 51.6, 50.8, 51.0, 53.9],
    "lon": [-1.3, 0.9, -0.1, -3.0, -1.9, -1.5, -4.0, -2.6, 0.9, -3.9, -3.6, -3.5, -1.3, -1.3],
    "price": [0.18, 0.19, 0.20, 0.17, 0.18, 0.19, 0.21, 0.18, 0.19, 0.20, 0.17, 0.16, 0.18, 0.19],
    "carbon": [150, 140, 135, 160, 155, 145, 130, 150, 140, 125, 165, 170, 155, 145]
})

selected_region_name = st.selectbox("Select your UK region", list(REGION_CODES.keys()))
OCTOPUS_REGION_CODE = REGION_CODES[selected_region_name]

# --- Configuration ---
OCTOPUS_PRODUCT_CODE = "AGILE-18-02-21"
PUSHBULLET_ACCESS_TOKEN = 'o.nP2rRaXiZMPewnsKtXX2V8WhfjCOp7Ec'

@st.cache_data(ttl=3600)
def fetch_and_process_octopus_prices(product_code, region_code):
    url = f"https://api.octopus.energy/v1/products/{product_code}/electricity-tariffs/E-1R-{product_code}-{region_code}/standard-unit-rates/"
    params = {"page_size": 96, "order_by": "valid_from"}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data['results'])
        df['valid_from'] = pd.to_datetime(df['valid_from'], utc=True)
        df['valid_to'] = pd.to_datetime(df['valid_to'], utc=True)
        df['price_gbp'] = df['value_inc_vat'] / 100
        df = df.sort_values('valid_from').reset_index(drop=True)

        uk_timezone = pytz.timezone('Europe/London')
        df['valid_from_bst'] = df['valid_from'].dt.tz_convert(uk_timezone)
        df['valid_to_bst'] = df['valid_to'].dt.tz_convert(uk_timezone)

        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from Octopus Energy API: {e}")
        return pd.DataFrame()
    except KeyError:
        st.error("Could not parse Octopus Energy API response.")
        return pd.DataFrame()



def send_push_notification(message, access_token):
    if not access_token:
        st.warning("Pushbullet Access Token not set.")
        return

    data = {'type': 'note', 'title': 'Smart EV Scheduler Alert', 'body': message}
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.post('https://api.pushbullet.com/v2/pushes', data=data, headers=headers)
        response.raise_for_status()
        st.success("Notification sent successfully!")
    except requests.exceptions.RequestException as e:
        st.error(f"Notification failed: {e}")

# --- Tabs ---
tab1, tab2 = st.tabs(["Smart Scheduler", "UK Region Map"])

with tab1:
    st.title("⚡ Smart EV Charging Scheduler")
    st.markdown("Optimize your EV charging by identifying the cheapest electricity periods based on Octopus Agile prices in your region.")

    prices_df = fetch_and_process_octopus_prices(OCTOPUS_PRODUCT_CODE, OCTOPUS_REGION_CODE)

    if not prices_df.empty and 'price_gbp' in prices_df.columns and not prices_df['price_gbp'].isnull().all():
        st.header("Current Electricity Price & Outlook")

        uk_timezone = pytz.timezone('Europe/London')
        now_uk = datetime.now(uk_timezone)

        current_slot = prices_df[(prices_df['valid_from_bst'] <= now_uk) & (prices_df['valid_to_bst'] > now_uk)]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(label="Your Region", value=f"{OCTOPUS_REGION_CODE} - {selected_region_name}")
            st.caption(f"Octopus Agile Product: `{OCTOPUS_PRODUCT_CODE}`")

        if not current_slot.empty:
            current_price = current_slot['price_gbp'].values[0]
            avg_price = prices_df['price_gbp'].mean()
            min_price = prices_df['price_gbp'].min()
            max_price = prices_df['price_gbp'].max()

            with col2:
                st.metric(label="Current Price (Now)", value=f"£{current_price:.4f}/kWh", delta=f"£{current_price - avg_price:.4f} vs Avg")
                st.caption(f"Current time: {now_uk.strftime('%Y-%m-%d %H:%M %Z%z')}")

            with col3:
                st.metric(label="Average Price (24-48h)", value=f"£{avg_price:.4f}/kWh")
                st.caption(f"Range: £{min_price:.4f} - £{max_price:.4f}")

            st.markdown("---")
            st.subheader("Charging Recommendation")

            message_to_send = ""
            if current_price < avg_price:
                st.success("✅ It's a good time to charge your EV!")
                message_to_send = f"⚡ Good time to charge! Current price: £{current_price:.4f}/kWh."
            elif current_price <= (avg_price * 1.1):
                st.info("💡 Slightly above average.")
                message_to_send = f"💡 Slightly above average: £{current_price:.4f}/kWh."
            else:
                st.warning("❌ Price is high. Consider waiting.")
                message_to_send = f"⚠️ High price: £{current_price:.4f}/kWh."

            st.subheader("Upcoming Cheapest Charging Window")
            charging_duration_hours = st.slider("Select desired charging duration (hours)", 1, 8, 4, 1)
            charging_slots = charging_duration_hours * 2
            future_prices_df = prices_df[prices_df['valid_from_bst'] > now_uk].copy()

            if not future_prices_df.empty and len(future_prices_df) >= charging_slots:
                future_prices_df['rolling_cost'] = future_prices_df['price_gbp'].rolling(window=charging_slots).sum()
                cheapest_start_idx = future_prices_df['rolling_cost'].idxmin()
                cheapest_window = future_prices_df.loc[cheapest_start_idx:cheapest_start_idx + charging_slots - 1]

                if not cheapest_window.empty:
                    cheapest_start = cheapest_window['valid_from_bst'].min()
                    cheapest_end = cheapest_window['valid_to_bst'].max()
                    total_cost = cheapest_window['rolling_cost'].min()
                    avg_kwh_price = total_cost / charging_slots

                    st.success(f"**Optimal {charging_duration_hours}-hour window:**")
                    st.write(f"**Start:** {cheapest_start.strftime('%Y-%m-%d %H:%M %Z')}")
                    st.write(f"**End:** {cheapest_end.strftime('%Y-%m-%d %H:%M %Z')}")
                    st.write(f"**Estimated Avg Price:** £{avg_kwh_price:.4f}/kWh")
                    message_to_send += f"\nOptimal {charging_duration_hours}h window: {cheapest_start.strftime('%H:%M')} to {cheapest_end.strftime('%H:%M')} at £{avg_kwh_price:.4f}/kWh."

            st.markdown("---")
            st.subheader("Send Notification")
            if st.button("Send Pushbullet Notification"):
                send_push_notification(message_to_send, PUSHBULLET_ACCESS_TOKEN)

            st.header("Electricity Price Trends")
            fig, ax = plt.subplots(figsize=(14, 7))
            ax.plot(prices_df['valid_from_bst'], prices_df['price_gbp'], marker='o', linestyle='-', markersize=4, label='Price per kWh')
            ax.axhline(avg_price, color='red', linestyle='--', label=f'Avg Price (£{avg_price:.4f}/kWh)')
            ax.axvline(now_uk, color='green', linestyle=':', linewidth=2, label='Now')
            ax.scatter(now_uk, current_price, color='black', s=100, zorder=5, label='Current Price')
            if 'cheapest_window' in locals() and not cheapest_window.empty:
                ax.axvspan(cheapest_start, cheapest_end, color='green', alpha=0.2, label='Cheapest Window')
            ax.set_title(f"Octopus Agile Prices - Region {OCTOPUS_REGION_CODE}")
            ax.set_xlabel("Time (BST)")
            ax.set_ylabel("Price (£/kWh)")
            ax.tick_params(axis='x', rotation=45)
            ax.legend()
            ax.grid(True)
            plt.tight_layout()
            st.pyplot(fig)

        else:
            st.error("No current price data available.")
    else:
        st.error("Failed to load electricity price data. Check your API or network.")

with tab2:
    st.title("UK Electricity Prices & Carbon Intensity by Region")
    fig_map = px.scatter_mapbox(
        region_df,
        lat="lat",
        lon="lon",
        hover_name="region",
        hover_data={"price": True, "carbon": True},
        color="price",
        size="carbon",
        size_max=25,
        zoom=4,
        mapbox_style="open-street-map",
        title="Regional Electricity Price (£/kWh) and Carbon Intensity (gCO2/kWh)"
    )
    st.plotly_chart(fig_map, use_container_width=True)

st.markdown("---")
st.markdown("Built by Ramkumar Kannan for Axle Energy prototype.")
st.markdown("[GitHub Link](https://github.com/your-github-profile/your-repo-name)")
