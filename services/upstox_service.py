from datetime import datetime, timedelta
from typing import List, Optional, Dict

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

        try:
            response = requests.get(self.config.UPSTOX_HOLDINGS_URL, headers=headers)
            response.raise_for_status()

            holdings_data = response.json().get('data', [])
            print(f"API returned {len(holdings_data)} holdings")

            holdings = []
            for i, holding_data in enumerate(holdings_data):
                print(f"Processing holding {i}: {holding_data.get('tradingsymbol', 'Unknown')}")

                holding = Holding(
                    tradingsymbol=holding_data.get('tradingsymbol', 'Unknown'),
                    quantity=holding_data.get('quantity', 0),
                    average_price=holding_data.get('average_price', 0),
                    last_price=holding_data.get('last_price', 0),
                    pnl=holding_data.get('pnl', 0),
                    close_price=holding_data.get('close_price', 0),
                    instrument_token=holding_data.get('instrument_token')
                )

                # Initialize day change attributes with default values
                holding.day_change = 0
                holding.day_change_percentage = 0
                holding.day_pnl = 0

                holdings.append(holding)
                print(f"Created holding object for {holding.tradingsymbol}")

            print(f"Successfully created {len(holdings)} holding objects")
            return holdings

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {str(e)}")
            return []
        except Exception as e:
            print(f"Error processing holdings data: {str(e)}")
            return []

    @handle_api_errors
    def get_holdings_with_day_change(self) -> List[Holding]:
        """Fetch holdings with 1-day change data"""
        print("Fetching holdings with day change data...")
        holdings = self.get_holdings()

        # Handle case where get_holdings returns error dict
        if isinstance(holdings, dict) and 'error' in holdings:
            print("Error in get_holdings, returning empty list")
            return []

        if not holdings:
            print("No holdings returned from get_holdings")
            return []

        print(f"Got {len(holdings)} holdings, fetching day change data...")

        # Get day change data for all holdings
        instrument_tokens = []
        for holding in holdings:
            if hasattr(holding, 'instrument_token') and holding.instrument_token:
                instrument_tokens.append(holding.instrument_token)
                print(f"Added instrument token for {holding.tradingsymbol}: {holding.instrument_token}")

        print(f"Fetching day change for {len(instrument_tokens)} instruments")
        day_change_data = self._fetch_day_change_batch(instrument_tokens)

        # Update holdings with day change information
        for holding in holdings:
            if hasattr(holding, 'instrument_token') and holding.instrument_token and holding.instrument_token in day_change_data:
                change_info = day_change_data[holding.instrument_token]
                holding.day_change = change_info['day_change']
                holding.day_change_percentage = change_info['day_change_percentage']
                holding.day_pnl = holding.day_change * holding.quantity
                print(f"Updated {holding.tradingsymbol} with day change: {holding.day_change_percentage:.2f}%")
            else:
                # Set default values if no day change data available
                holding.day_change = 0
                holding.day_change_percentage = 0
                holding.day_pnl = 0
                print(f"No day change data for {holding.tradingsymbol}, set to defaults")

        print(f"Returning {len(holdings)} holdings with day change data")
        return holdings

    def _fetch_day_change_batch(self, instrument_tokens: List[str]) -> Dict[str, Dict]:
        """Fetch 1-day change data for multiple instruments"""
        day_change_data = {}

        for token in instrument_tokens:
            try:
                # Get 2 days of data to calculate day change
                end_date = datetime.now()
                start_date = end_date - timedelta(days=5)  # Get more days to account for weekends/holidays

                hist_data = self.get_historical_data(token, start_date, end_date)

                if hist_data is not None and len(hist_data) >= 2:
                    # Get the last two trading days
                    latest_close = hist_data['close'].iloc[-1]
                    previous_close = hist_data['close'].iloc[-2]

                    day_change = latest_close - previous_close
                    day_change_percentage = (day_change / previous_close) * 100 if previous_close != 0 else 0

                    day_change_data[token] = {
                        'day_change': day_change,
                        'day_change_percentage': day_change_percentage,
                        'latest_close': latest_close,
                        'previous_close': previous_close
                    }
                    print(f"Day change calculated for {token}: {day_change_percentage:.2f}%")
                else:
                    # Fallback: no change data available
                    day_change_data[token] = {
                        'day_change': 0,
                        'day_change_percentage': 0,
                        'latest_close': 0,
                        'previous_close': 0
                    }
                    print(f"No historical data available for {token}")

            except Exception as e:
                print(f"Error fetching day change for {token}: {str(e)}")
                day_change_data[token] = {
                    'day_change': 0,
                    'day_change_percentage': 0,
                    'latest_close': 0,
                    'previous_close': 0
                }

        return day_change_data

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
                print(f"No candle data for {instrument_key}")
                return None

            df = pd.DataFrame(candles, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'unknown'])
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            df = df[~df.index.duplicated()]

            print(f"Historical data fetched for {instrument_key}: {len(df)} records")
            return df

        except Exception as e:
            print(f"Error fetching historical data for {instrument_key}: {str(e)}")
            return None

    @handle_api_errors
    def get_benchmark_data(self, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch benchmark (Nifty 50) historical data"""
        return self.get_historical_data(self.config.BENCHMARK_SYMBOL, start_date, end_date)
