import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import requests
from carbon import CarbonIntensity
from price_prediction import PriceForecaster
from price_calculator import PriceCalculator
from tomorrow_window_finder import TomorrowWindowFinder
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
tab1, tab2, tab3, tab4 = st.tabs([
    "🔌 Smart Charging Advisor",
    "📆 Plan Ahead & Save",
    "🔮 Price Forecast",
    "📊 Regional Comparison"
])

# --- Tab 1: Smart Scheduler ---
with tab1:
    st.title("🔌 Smart Charging Advisor")

    # --- EV Charging Input ---
    col1, col2, col3 = st.columns(3)
    with col1:
        battery_capacity = st.number_input("Battery Capacity (kWh)", min_value=10.0, max_value=150.0, value=60.0, step=1.0)
    with col2:
        current_soc = st.slider("Current Charge (%)", min_value=0, max_value=100, value=20)
    with col3:
        target_soc = st.slider("Target Charge (%)", min_value=1, max_value=100, value=80)

    # --- Calculate kWh needed and time ---
    soc_delta = max(0, target_soc - current_soc)
    kwh_needed = battery_capacity * soc_delta / 100
    charging_power = 7.4  # kW
    hours_needed = kwh_needed / charging_power if kwh_needed > 0 else 0

    st.info(f"⚡ You need to charge {kwh_needed:.2f} kWh.")
    st.info(f"⏱️ It will take approximately {hours_needed:.2f} hours at 7.4 kW.")

    # --- User-defined charging window ---
    available_hours = st.slider("How many hours are you available to charge?", min_value=1, max_value=12, value=min(6, int(hours_needed) + 1))
    energy_possible = available_hours * charging_power
    energy_to_charge = min(kwh_needed, energy_possible)
    st.info(f"🔋 You can actually charge {energy_to_charge:.2f} kWh in {available_hours} hours.")

    # --- Fetch price data ---
    df = fetch_octopus_prices(OCTOPUS_PRODUCT_CODE, region_code)
    if df.empty:
        st.warning("No price data available.")
    else:
        import pandas as pd
        import plotly.graph_objects as go
        import pytz
        from datetime import datetime, timedelta

        now = datetime.now(pytz.timezone("Europe/London"))

        # --- Show current electricity price ---
        current_row = df[(df['valid_from_bst'] <= now) & (df['valid_to_bst'] > now)]
        if not current_row.empty:
            current_price = current_row.iloc[0]['price_gbp']
            current_time = current_row.iloc[0]['valid_from_bst']
            st.metric("Current Electricity Price", f"£{current_price:.4f}/kWh", help=f"Slot starting {current_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            current_price = None
            current_time = None
            st.warning("No current price available.")

        # --- Calculate slot-by-slot cost for user window ---
        slots_needed = int(available_hours * 2)
        df_future = df[df['valid_from_bst'] >= now].head(slots_needed)
        if len(df_future) < slots_needed:
            st.warning("Not enough future price slots available.")
        else:
            energy_per_slot = energy_to_charge / slots_needed if slots_needed > 0 else 0
            df_future = df_future.copy()
            df_future['energy_kwh'] = energy_per_slot
            df_future['cost'] = df_future['price_gbp'] * df_future['energy_kwh']
            total_cost = df_future['cost'].sum()
            st.success(
                f"💰 **Estimated cost to charge {energy_to_charge:.2f} kWh over {available_hours} hours:** £{total_cost:.2f}"
            )
            with st.expander("Show slot-by-slot breakdown"):
                df_show = df_future[['valid_from_bst', 'price_gbp', 'energy_kwh', 'cost']]
                df_show.columns = ['Start Time', 'Price (£/kWh)', 'Energy (kWh)', 'Cost (£)']
                st.dataframe(df_show, hide_index=True)

        # --- Find today's cheapest 4-hour slot (with correct time logic) ---
        default_window_hours = 4
        default_window_slots = default_window_hours * 2
        df_today = df[df['valid_from_bst'].dt.date == now.date()].sort_values('valid_from_bst').reset_index(drop=True)
        df_today['rolling_avg'] = df_today['price_gbp'].rolling(window=default_window_slots).mean()
        best_today_idx = df_today['rolling_avg'].idxmin()
        window_start = window_end = None
        best_today_window = None
        if (
            not pd.isna(best_today_idx)
            and best_today_idx - default_window_slots + 1 >= 0
        ):
            start_idx = best_today_idx - default_window_slots + 1
            end_idx = best_today_idx
            best_today_window = df_today.iloc[start_idx:end_idx + 1]
            window_start = best_today_window['valid_from_bst'].iloc[0]
            window_end = best_today_window['valid_to_bst'].iloc[-1]
            today_cost = best_today_window['price_gbp'].mean() * default_window_hours
            st.info(
                f"🟢 Cheapest 4-hour slot today: {window_start.strftime('%H:%M')} – {window_end.strftime('%H:%M')}, £{today_cost:.2f} (for 4 hours at 1kW)"
            )

        # --- Find best (cheapest) charging window from now onwards for available_hours ---
        slots_needed = int(available_hours * 2)
        df_future_all = df[df['valid_from_bst'] >= now].sort_values('valid_from_bst').reset_index(drop=True)
        df_future_all['rolling_avg'] = df_future_all['price_gbp'].rolling(window=slots_needed).mean()
        best_now_idx = df_future_all['rolling_avg'].idxmin()
        now_window_start = now_window_end = None
        best_now_window = None
        if (
            not pd.isna(best_now_idx)
            and best_now_idx - slots_needed + 1 >= 0
        ):
            start_idx = best_now_idx - slots_needed + 1
            end_idx = best_now_idx
            best_now_window = df_future_all.iloc[start_idx:end_idx + 1]
            now_window_start = best_now_window['valid_from_bst'].iloc[0]
            now_window_end = best_now_window['valid_to_bst'].iloc[-1]
            now_window_cost = best_now_window['price_gbp'].mean() * available_hours
            st.info(
                f"🟠 Cheapest {available_hours}-hour slot from now: {now_window_start.strftime('%H:%M')} – {now_window_end.strftime('%H:%M')}, £{now_window_cost:.2f} (for {available_hours} hours at 1kW)"
            )

        # --- Chart: Full price trend with highlights ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['valid_from_bst'],
            y=df['price_gbp'],
            mode='lines+markers',
            marker=dict(color='blue', size=6),
            name='30-min Price'
        ))

        # Highlight user's charging window
        if not df_future.empty:
            user_start = df_future['valid_from_bst'].iloc[0]
            user_end = df_future['valid_to_bst'].iloc[-1]
            if pd.notnull(user_start) and pd.notnull(user_end):
                fig.add_vrect(
                    x0=user_start, x1=user_end,
                    fillcolor="orange", opacity=0.15, line_width=0,
                    annotation_text="Your Charging Window", annotation_position="top right"
                )

        # Highlight today's cheapest 4-hour slot
        if (
            window_start is not None and window_end is not None
            and not pd.isnull(window_start) and not pd.isnull(window_end)
        ):
            fig.add_vrect(
                x0=window_start, x1=window_end,
                fillcolor="green", opacity=0.15, line_width=0,
                annotation_text="Today's Cheapest 4h", annotation_position="top left"
            )
            if best_today_window is not None:
                fig.add_trace(go.Scatter(
                    x=best_today_window['valid_from_bst'],
                    y=best_today_window['price_gbp'],
                    mode='markers',
                    marker=dict(color='green', size=10, symbol='diamond'),
                    name='Cheapest 4h Window'
                ))

        # Highlight current price as a marker
        if current_price is not None and current_time is not None:
            fig.add_trace(go.Scatter(
                x=[current_time],
                y=[current_price],
                mode='markers+text',
                marker=dict(color='red', size=14, symbol='star'),
                text=["Current Price"],
                textposition="top center",
                name="Current Price"
            ))

        # Highlight best (cheapest) charging window from now onwards in orange
        if (
            now_window_start is not None and now_window_end is not None
            and not pd.isnull(now_window_start) and not pd.isnull(now_window_end)
        ):
            fig.add_vrect(
                x0=now_window_start, x1=now_window_end,
                fillcolor="orange", opacity=0.25, line_width=0,
                annotation_text=f"Best {available_hours}h From Now", annotation_position="top right"
            )
            if best_now_window is not None:
                fig.add_trace(go.Scatter(
                    x=best_now_window['valid_from_bst'],
                    y=best_now_window['price_gbp'],
                    mode='markers',
                    marker=dict(color='orange', size=10, symbol='circle'),
                    name=f'Best {available_hours}h From Now'
                ))

        # Set x-axis to full day
        london_tz = pytz.timezone("Europe/London")
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = today_midnight + timedelta(hours=23, minutes=30)
        fig.update_xaxes(range=[today_midnight, end_of_day])
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Price (£/kWh)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            title="Price Trend with Highlights"
        )
        st.plotly_chart(fig, use_container_width=True)


# --- Tab 2: Make Your Time Free ---
with tab2:
    st.title("📅 Make Your Time Free")
    st.markdown("Find the cheapest charging window for tomorrow using Octopus Agile prices.")

    window_hours = st.slider("How many hours do you want to charge?", min_value=1, max_value=12, value=4)

    df = fetch_octopus_prices(OCTOPUS_PRODUCT_CODE, region_code)
    finder = TomorrowWindowFinder(df, window_hours)
    total_cost, avg_price, start_time, end_time, window_df, tomorrow_slots = finder.find_cheapest_window_tomorrow()

    if tomorrow_slots == 0:
        st.warning("⚠️ Tomorrow's prices are not yet released. Please check after 4:00 PM.")
    elif total_cost is None:
        st.warning(f"Not enough half-hour slots for a {window_hours}-hour window tomorrow.")
    else:
        st.success(
            f"🕓 **Cheapest {window_hours}-hour slot tomorrow:** "
            f"{start_time.strftime('%Y-%m-%d %H:%M')} – {end_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"💸 **Total cost (1kW):** £{total_cost:.2f}\n"
            f"📉 **Avg price:** £{avg_price:.4f}/kWh"
        )
        # Optional: Show tomorrow's price trend with window highlighted
        import plotly.express as px
        import plotly.graph_objects as go
        fig = px.line(
            pd.concat([
                window_df,
                df[df['valid_from_bst'].dt.date == (datetime.now(pytz.timezone('Europe/London')) + timedelta(days=1)).date()]
            ], ignore_index=True),
            x='valid_from_bst', y='price_gbp', title="Tomorrow's Price Trend"
        )
        fig.add_trace(go.Scatter(
            x=window_df['valid_from_bst'],
            y=window_df['price_gbp'],
            mode='markers',
            marker=dict(color='green', size=8),
            name='Cheapest Window'
        ))
        fig.add_vrect(
            x0=start_time, x1=end_time,
            fillcolor="green", opacity=0.2, line_width=0,
            annotation_text="Cheapest Window", annotation_position="top left"
        )
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Price (£/kWh)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.title("Future Price Forecast (ML)")
    df = fetch_octopus_prices(OCTOPUS_PRODUCT_CODE, region_code)
    if not df.empty:
        forecaster = PriceForecaster()
        forecaster.fit(df)
        forecast_df = forecaster.predict_next_day(df)
        st.subheader("Next Day Price Forecast")
        st.line_chart(forecast_df.set_index("valid_from_bst")["predicted_price"])
        st.dataframe(forecast_df)
    else:
        st.warning("No price data available.")

with tab4:
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
