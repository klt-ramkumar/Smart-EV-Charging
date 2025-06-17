
import streamlit as st
from datetime import datetime
import pandas as pd
import requests
from carbon import CarbonIntensity
from price_prediction import PriceForecaster
from price_calculator import PriceCalculator
import pytz
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Smart EV Charging Scheduler")

# --- Region DataFrame ---
region_df = pd.DataFrame({
    "region": [
        "East Midlands", "Eastern England", "London", "Merseyside and North Wales",
        "Midlands", "North East England", "North Scotland", "North West England",
        "South East England", "South Scotland", "South Wales", "South West England",
        "Southern England", "Yorkshire"
    ],
    "code": ["E", "F", "A", "D", "M", "C", "P", "B", "J", "N", "K", "G", "H", "Y"],
    "lat": [52.8, 52.4, 51.5, 53.4, 52.5, 54.9, 57.5, 53.8, 51.3, 55.9, 51.6, 50.8, 51.0, 53.9],
    "lon": [-1.3, 0.9, -0.1, -3.0, -1.9, -1.5, -4.0, -2.6, 0.9, -3.9, -3.6, -3.5, -1.3, -1.3],
    "price": [0.18, 0.19, 0.20, 0.17, 0.18, 0.19, 0.21, 0.18, 0.19, 0.20, 0.17, 0.16, 0.18, 0.19],
    "dnoregion": [
        "WPD East Midlands", "UKPN East", "UKPN London", "SP Manweb", "WPD West Midlands",
        "NPG North East", "Scottish Hydro Electric Power Distribution", "Electricity North West",
        "UKPN South East", "SP Distribution", "WPD South Wales", "WPD South West",
        "SSE South", "NPG Yorkshire"
    ]
})

selected_region = st.selectbox("Select your UK region", region_df["region"])
selected_row = region_df[region_df["region"] == selected_region].iloc[0]
region_code = selected_row["code"]
dnoregion_name = selected_row["dnoregion"]

OCTOPUS_PRODUCT_CODE = "AGILE-18-02-21"

@st.cache_data(ttl=3600)
def fetch_octopus_prices(product_code, region_code):
    url = f"https://api.octopus.energy/v1/products/{product_code}/electricity-tariffs/E-1R-{product_code}-{region_code}/standard-unit-rates/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['results'])
        df['valid_from'] = pd.to_datetime(df['valid_from'], utc=True)
        df['valid_to'] = pd.to_datetime(df['valid_to'], utc=True)
        df['price_gbp'] = df['value_inc_vat'] / 100
        uk_tz = pytz.timezone('Europe/London')
        df['valid_from_bst'] = df['valid_from'].dt.tz_convert(uk_tz)
        df['valid_to_bst'] = df['valid_to'].dt.tz_convert(uk_tz)
        return df
    except:
        st.error("Failed to fetch Octopus Energy prices.")
        return pd.DataFrame()

carbon = CarbonIntensity()
carbon.fetch_data()

# NEW TAB STRUCTURE
tab1, tab2, tab3 = st.tabs([
    "🔌 Smart Charging Advisor",
    "🔮 Price Forecast",
    "📊 Regional Comparison"
])

with tab1:
    st.title("🔌 Smart Charging Advisor")

    df = fetch_octopus_prices(OCTOPUS_PRODUCT_CODE, region_code)
    actual, forecast = carbon.get_intensity_by_dnoregion(dnoregion_name)
    now = datetime.now(pytz.timezone("Europe/London"))
    current_row = df[(df['valid_from_bst'] <= now) & (df['valid_to_bst'] > now)]

    if not current_row.empty:
        st.metric("Current Electricity Price", f"£{current_row.iloc[0]['price_gbp']:.4f}/kWh")

    st.markdown("Enter your EV details and see how much charging will cost now vs. the cheapest slot!")

    col1, col2, col3 = st.columns(3)
    with col1:
        battery_capacity = st.number_input("Battery Capacity (kWh)", min_value=10.0, max_value=150.0, value=60.0)
    with col2:
        current_soc = st.slider("Current Charge (%)", 0, 100, 20)
    with col3:
        target_soc = st.slider("Target Charge (%)", 1, 100, 80)

    window_hours = st.slider("Charging Window (hours)", 2, 6, 4)

    if not df.empty:
        calc = PriceCalculator(df, battery_capacity, current_soc, target_soc, window_hours)
        results = calc.calculate_savings()

        st.info(f"🔋 You need to charge: {results['kwh_needed']:.2f} kWh")

        if results["cost_now"] is not None:
            st.metric("💰 Cost to Charge Now", f"£{results['cost_now']:.2f}", help=f"At current price: £{results['price_now']:.4f}/kWh")
        if results["cost_cheapest"] is not None:
            st.success(
    f"📅 Cheapest {window_hours}-hour slot: {results['start_time'].strftime('%H:%M')} – {results['end_time'].strftime('%H:%M')}  \n"
    f"💸 Cost: £{results['cost_cheapest']:.2f}  \n"
    f"💡 You save: £{results['savings']:.2f}"
)
            st.caption(f"Cheapest slot avg price: £{results['avg_price']:.4f}/kWh")

        fig = px.line(df, x='valid_from_bst', y='price_gbp', title="Price Trend with Cheapest Window")
        fig.add_trace(go.Scatter(x=df['valid_from_bst'], y=df['price_gbp'], mode='markers', marker=dict(color='blue', size=6), name='30-min Price'))

        if results["window_df"] is not None:
            fig.add_vrect(x0=results["start_time"], x1=results["end_time"], fillcolor="green", opacity=0.2, line_width=0)

        if results["price_now"] is not None and results["price_time"] is not None:
            fig.add_trace(go.Scatter(
                x=[results["price_time"]],
                y=[results["price_now"]],
                mode='markers+text',
                marker=dict(color='red', size=12, symbol='star'),
                text=["Current Price"],
                textposition="top center",
                name="Current Price"
            ))

        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.title("🔮 Price Forecast")
    df = fetch_octopus_prices(OCTOPUS_PRODUCT_CODE, region_code)
    if not df.empty:
        forecaster = PriceForecaster()
        forecaster.fit(df)
        pred_df = forecaster.predict_next_day(df)
        st.line_chart(pred_df.set_index('valid_from_bst')['predicted_price'])
        st.dataframe(pred_df[['valid_from_bst', 'predicted_price']].rename(columns={'valid_from_bst': 'Time', 'predicted_price': 'Forecast Price (£/kWh)'}))
    else:
        st.warning("No price data available for forecasting.")

with tab3:
    st.title("📊 Regional Comparison")
    choice = st.radio("View:", ["Electricity Price", "Carbon Intensity"])

    if choice == "Electricity Price":
        fig = px.scatter_mapbox(
            region_df, lat="lat", lon="lon", color="price", size=[10]*len(region_df),
            hover_name="region", zoom=4, mapbox_style="open-street-map",
            title="Electricity Price by Region (£/kWh)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        if carbon.cached_data:
            regional_data = carbon.cached_data['data'][0]['regions']
            c_df = pd.DataFrame([{
                "dnoregion": r['dnoregion'],
                "carbon": r['intensity'].get('forecast'),
                "index": r['intensity'].get('index')
            } for r in regional_data if r['intensity'].get('forecast') is not None])

            c_df = c_df.merge(region_df, on="dnoregion", how="left")
            fig = px.scatter_mapbox(
                c_df,
                lat="lat", lon="lon", color="carbon", size=[30]*len(c_df),
                color_continuous_scale="Viridis",
                hover_name="region",
                hover_data={"carbon": True, "index": True, "lat": False, "lon": False},
                zoom=4, mapbox_style="carto-positron",
                title="Regional Carbon Intensity (gCO₂/kWh)"
            )
            fig.update_traces(marker=dict(opacity=0.85))
            fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown("Built by Ramkumar Kannan for Axle Energy prototype.")
