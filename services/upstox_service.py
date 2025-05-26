from datetime import datetime
from typing import List, Optional

import pandas as pd
import requests

from config import Config
from models.portfolio import Holding
from services.auth_service import AuthService
from utils.decorators import handle_api_errors


class UpstoxService:
    """Service for Upstox API interactions"""

    def __init__(self):
        self.config = Config()
        self.auth_service = AuthService()

    @handle_api_errors
    def get_holdings(self) -> List[Holding]:
        """Fetch user holdings from Upstox API"""
        headers = self.auth_service.get_headers()

        response = requests.get(self.config.UPSTOX_HOLDINGS_URL, headers=headers)
        response.raise_for_status()

        holdings_data = response.json().get('data', [])

        holdings = []
        for holding_data in holdings_data:
            holding = Holding(
                tradingsymbol=holding_data.get('tradingsymbol', 'Unknown'),
                quantity=holding_data.get('quantity', 0),
                average_price=holding_data.get('average_price', 0),
                last_price=holding_data.get('last_price', 0),
                pnl=holding_data.get('pnl', 0),
                close_price=holding_data.get('close_price', 0),
                instrument_token=holding_data.get('instrument_token')
            )
            holdings.append(holding)

        return holdings

    @handle_api_errors
    def get_historical_data(self, instrument_key: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch historical price data for an instrument"""
        headers = self.auth_service.get_headers()

        url = f"{self.config.UPSTOX_HISTORICAL_URL}/{instrument_key}/days/1/{end_date.date()}/{start_date.date()}"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            hist_data = response.json().get('data', {})
            candles = hist_data.get('candles', [])

            if not candles:
                return None

            df = pd.DataFrame(candles, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'unknown'])
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            df = df[~df.index.duplicated()]

            return df

        except Exception as e:
            print(f"Error fetching historical data for {instrument_key}: {str(e)}")
            return None

    @handle_api_errors
    def get_benchmark_data(self, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch benchmark (Nifty 50) historical data"""
        return self.get_historical_data(self.config.BENCHMARK_SYMBOL, start_date, end_date)
