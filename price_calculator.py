import pandas as pd
from datetime import datetime
import pytz

class PriceCalculator:
    def __init__(self, df, battery_capacity, current_soc, target_soc, window_hours, timezone="Europe/London"):
        self.df = df.copy()
        # Ensure datetime columns are timezone-aware and in Europe/London
        london_tz = pytz.timezone(timezone)
        for col in ['valid_from_bst', 'valid_to_bst']:
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                if self.df[col].dt.tz is None:
                    # Naive: localize to UTC then convert
                    self.df[col] = self.df[col].dt.tz_localize('UTC').dt.tz_convert(london_tz)
                else:
                    self.df[col] = self.df[col].dt.tz_convert(london_tz)
            else:
                # Not datetime yet
                self.df[col] = pd.to_datetime(self.df[col], utc=True).dt.tz_convert(london_tz)
        self.df = self.df.sort_values('valid_from_bst').reset_index(drop=True)
        self.battery_capacity = battery_capacity
        self.current_soc = current_soc
        self.target_soc = target_soc
        self.window_hours = window_hours
        self.timezone = timezone

        self.kwh_needed = self._calculate_kwh_needed()
        self.now = datetime.now(london_tz)

    def _calculate_kwh_needed(self):
        soc_delta = max(0, self.target_soc - self.current_soc)
        return self.battery_capacity * soc_delta / 100

    def get_current_price(self):
        current_row = self.df[
            (self.df['valid_from_bst'] <= self.now) & (self.df['valid_to_bst'] > self.now)
        ]
        if not current_row.empty:
            return current_row.iloc[0]['price_gbp'], current_row.iloc[0]['valid_from_bst']
        return None, None

    def cost_to_charge_now(self):
        price, price_time = self.get_current_price()
        if price is not None:
            return self.kwh_needed * price, price, price_time
        return None, None, None

    def find_cheapest_window(self):
        slots_needed = int(self.window_hours * 2)  # 30-min slots
        if len(self.df) < slots_needed:
            return None, None, None, None, None

        min_avg = None
        min_start = None
        for i in range(0, len(self.df) - slots_needed + 1):
            window = self.df.iloc[i:i + slots_needed]
            avg = window['price_gbp'].mean()
            if (min_avg is None) or (avg < min_avg):
                min_avg = avg
                min_start = i

        if min_start is None:
            return None, None, None, None, None

        window_df = self.df.iloc[min_start:min_start + slots_needed]
        avg_price = window_df['price_gbp'].mean()
        cost = self.kwh_needed * avg_price
        start_time = window_df.iloc[0]['valid_from_bst']
        end_time = window_df.iloc[-1]['valid_to_bst']
        return cost, avg_price, start_time, end_time, window_df

    def find_cheapest_window_today(self):
        """Cheapest window for the whole day."""
        slots_needed = int(self.window_hours * 2)
        if len(self.df) < slots_needed:
            return None, None, None, None, None

        min_avg = None
        min_start = None
        for i in range(0, len(self.df) - slots_needed + 1):
            window = self.df.iloc[i:i + slots_needed]
            avg = window['price_gbp'].mean()
            if (min_avg is None) or (avg < min_avg):
                min_avg = avg
                min_start = i

        if min_start is None:
            return None, None, None, None, None

        window_df = self.df.iloc[min_start:min_start + slots_needed]
        avg_price = window_df['price_gbp'].mean()
        cost = self.kwh_needed * avg_price
        start_time = window_df.iloc[0]['valid_from_bst']
        end_time = window_df.iloc[-1]['valid_to_bst']
        return cost, avg_price, start_time, end_time, window_df

    def find_cheapest_window_from_now(self):
        """Cheapest window starting at or after now."""
        slots_needed = int(self.window_hours * 2)
        if len(self.df) < slots_needed:
            return None, None, None, None, None

        # Only consider windows starting at or after now
        now = self.now
        valid_starts = self.df[self.df['valid_from_bst'] >= now].index
        min_avg = None
        min_start = None
        for i in valid_starts:
            if i + slots_needed > len(self.df):
                break
            window = self.df.iloc[i:i + slots_needed]
            avg = window['price_gbp'].mean()
            if (min_avg is None) or (avg < min_avg):
                min_avg = avg
                min_start = i

        if min_start is None:
            return None, None, None, None, None

        window_df = self.df.iloc[min_start:min_start + slots_needed]
        avg_price = window_df['price_gbp'].mean()
        cost = self.kwh_needed * avg_price
        start_time = window_df.iloc[0]['valid_from_bst']
        end_time = window_df.iloc[-1]['valid_to_bst']
        return cost, avg_price, start_time, end_time, window_df

    def calculate_savings(self):
        cost_now, price_now, price_time = self.cost_to_charge_now()
        cost_cheapest, avg_price, start_time, end_time, window_df = self.find_cheapest_window()
        if cost_now is not None and cost_cheapest is not None:
            savings = cost_now - cost_cheapest
        else:
            savings = None
        return {
            "kwh_needed": self.kwh_needed,
            "cost_now": cost_now,
            "price_now": price_now,
            "price_time": price_time,
            "cost_cheapest": cost_cheapest,
            "avg_price": avg_price,
            "start_time": start_time,
            "end_time": end_time,
            "savings": savings,
            "window_df": window_df
        }