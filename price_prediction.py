import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split

class PriceForecaster:
    def __init__(self):
        self.model = XGBRegressor(n_estimators=100, random_state=42)
        self.trained = False

    def prepare_features(self, df):
        # Feature engineering: hour, day of week, etc.
        df = df.copy()
        df['hour'] = df['valid_from_bst'].dt.hour
        df['dayofweek'] = df['valid_from_bst'].dt.dayofweek
        return df[['hour', 'dayofweek']]

    def fit(self, df):
        df = df.sort_values('valid_from_bst')
        X = self.prepare_features(df)
        y = df['price_gbp']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        self.trained = True

    def predict_next_day(self, df):
        # Predict for next 24 hours
        last_date = df['valid_from_bst'].max()
        next_hours = pd.date_range(last_date + pd.Timedelta(minutes=30), periods=48, freq='30T')
        pred_df = pd.DataFrame({
            'valid_from_bst': next_hours,
            'hour': next_hours.hour,
            'dayofweek': next_hours.dayofweek
        })
        X_pred = pred_df[['hour', 'dayofweek']]
        pred_df['predicted_price'] = self.model.predict(X_pred)
        return pred_df