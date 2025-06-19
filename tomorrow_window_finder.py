import pandas as pd
from datetime import datetime, timedelta
import pytz

class TomorrowWindowFinder:
    def __init__(self, df, window_hours, timezone="Europe/London"):
        self.df = df.copy()
        self.window_hours = window_hours
        self.timezone = timezone
        self.london_tz = pytz.timezone(timezone)
        for col in ['valid_from_bst', 'valid_to_bst']:
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                if self.df[col].dt.tz is None:
                    self.df[col] = self.df[col].dt.tz_localize('UTC').dt.tz_convert(self.london_tz)
                else:
                    self.df[col] = self.df[col].dt.tz_convert(self.london_tz)
            else:
                self.df[col] = pd.to_datetime(self.df[col], utc=True).dt.tz_convert(self.london_tz)
        self.df = self.df.sort_values('valid_from_bst').reset_index(drop=True)

    def find_cheapest_window_tomorrow(self):
        tomorrow = (datetime.now(self.london_tz) + timedelta(days=1)).date()
        df_tomorrow = self.df[self.df['valid_from_bst'].dt.date == tomorrow].reset_index(drop=True)
        slots_needed = int(self.window_hours * 2)
        if len(df_tomorrow) < slots_needed:
            return None, None, None, None, None, len(df_tomorrow)

        min_avg = None
        min_start = None
        for i in range(0, len(df_tomorrow) - slots_needed + 1):
            window = df_tomorrow.iloc[i:i + slots_needed]
            avg = window['price_gbp'].mean()
            if (min_avg is None) or (avg < min_avg):
                min_avg = avg
                min_start = i

        if min_start is None:
            return None, None, None, None, None, len(df_tomorrow)

        window_df = df_tomorrow.iloc[min_start:min_start + slots_needed]
        avg_price = window_df['price_gbp'].mean()
        total_cost = avg_price * self.window_hours  # total cost for 1kW continuous charging
        start_time = window_df.iloc[0]['valid_from_bst']
        end_time = window_df.iloc[-1]['valid_to_bst']
        return total_cost, avg_price, start_time, end_time, window_df, len(df_tomorrow)