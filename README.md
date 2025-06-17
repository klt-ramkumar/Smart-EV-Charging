# ⚡ Smart EV Charging Scheduler

This is a Streamlit-based prototype built to help electric vehicle (EV) users optimize their charging schedules using real-time electricity prices and carbon intensity data in the UK. It also includes a machine learning-based price forecaster. This project was designed with Axle Energy's mission in mind—to optimize smart device usage, support the energy grid, and reduce carbon emissions.

---

## 🚀 Features

### 🔌 Smart Charging Advisor
- Input EV battery size and current charge level
- Compare cost to charge now vs. cheapest time slot
- Automatically recommends optimal charging windows

### 📈 Electricity Price Forecast
- Uses XGBoost to predict next-day half-hourly electricity prices
- Visualizes forecasted prices with easy-to-understand charts

### 📊 Regional Comparison
- Interactive UK map showing regional electricity prices
- Toggle to view carbon intensity (gCO₂/kWh) by region

### 🌱 Live Carbon Intensity
- Fetches and displays regional real-time and forecasted carbon intensity

---

## 🧠 Tech Stack

- **Python**
- **Streamlit** – for web interface
- **Plotly** – for data visualizations
- **XGBoost** – for electricity price prediction
- **Pandas / NumPy** – for data processing
- **Requests API** – for fetching data from Octopus Energy and UK Carbon Intensity API

---

## 📡 Data Sources

- [Octopus Agile Tariffs API](https://octopus.energy)
- [Carbon Intensity API (UK)](https://carbon-intensity.github.io)

---

## 🎯 Purpose

This project demonstrates:
- Smart charging optimization logic
- Real-time and predictive analytics
- Regional comparison for informed energy decisions

🧑‍💻 Built as a prototype for **Axle Energy**, showcasing my ability to:
- Handle API integrations
- Work with energy market data
- Apply ML to real-world scenarios
- Build user-friendly dashboards for non-technical users

---

## 🛠️ How to Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/your-username/smart-ev-charging-scheduler.git
cd smart-ev-charging-scheduler

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run ev.py
