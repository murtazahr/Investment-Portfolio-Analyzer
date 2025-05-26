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

                # Initialize day change and real-time attributes with default values
                holding.day_change = 0
                holding.day_change_percentage = 0
                holding.day_pnl = 0
                holding.real_time_price = holding.last_price
                holding.previous_close = holding.close_price

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
        """Fetch holdings with 1-day change data using market quotes API"""
        print("=== FETCHING HOLDINGS WITH DAY CHANGE DATA (Market Quotes) ===")
        print(f"Request time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        holdings = self.get_holdings()

        # Handle case where get_holdings returns error dict
        if isinstance(holdings, dict) and 'error' in holdings:
            print("Error in get_holdings, returning empty list")
            return []

        if not holdings:
            print("No holdings returned from get_holdings")
            return []

        print(f"Got {len(holdings)} holdings, fetching market quotes for day change...")

        # Get instrument keys for market quotes API
        instrument_keys = []
        holdings_map = {}

        for holding in holdings:
            if hasattr(holding, 'instrument_token') and holding.instrument_token:
                instrument_keys.append(holding.instrument_token)
                holdings_map[holding.instrument_token] = holding
                print(f"Added instrument key for {holding.tradingsymbol}: {holding.instrument_token}")

        if not instrument_keys:
            print("No valid instrument keys found")
            return holdings

        print(f"Fetching market quotes for {len(instrument_keys)} instruments")
        market_quotes = self._fetch_market_quotes(instrument_keys)

        # Update holdings with day change information from market quotes
        print(f"\n=== MATCHING HOLDINGS WITH MARKET QUOTES ===")
        print(f"Holdings instrument tokens: {[h.instrument_token for h in holdings if hasattr(h, 'instrument_token')]}")
        print(f"Market quotes keys: {list(market_quotes.keys())}")

        for holding in holdings:
            if hasattr(holding, 'instrument_token') and holding.instrument_token:
                print(f"\nProcessing {holding.tradingsymbol} with token: {holding.instrument_token}")

                # Try to find matching quote data using multiple strategies
                quote_data = None
                matching_key = None

                # Strategy 1: Direct instrument token match
                if holding.instrument_token in market_quotes:
                    quote_data = market_quotes[holding.instrument_token]
                    matching_key = holding.instrument_token
                    print(f"  ✅ Direct token match: {matching_key}")

                # Strategy 2: Match by symbol name
                elif not quote_data:
                    for quote_key, quote_info in market_quotes.items():
                        if quote_info.get('symbol') == holding.tradingsymbol:
                            quote_data = quote_info
                            matching_key = quote_key
                            print(f"  ✅ Symbol match: {quote_key} -> {holding.tradingsymbol}")
                            break

                # Strategy 3: Try case-insensitive symbol match
                elif not quote_data:
                    for quote_key, quote_info in market_quotes.items():
                        if quote_info.get('symbol', '').upper() == holding.tradingsymbol.upper():
                            quote_data = quote_info
                            matching_key = quote_key
                            print(f"  ✅ Case-insensitive symbol match: {quote_key} -> {holding.tradingsymbol}")
                            break

                # Strategy 4: Try partial symbol match (in case of different naming)
                elif not quote_data:
                    for quote_key, quote_info in market_quotes.items():
                        quote_symbol = quote_info.get('symbol', '')
                        if (holding.tradingsymbol in quote_symbol or
                                quote_symbol in holding.tradingsymbol):
                            quote_data = quote_info
                            matching_key = quote_key
                            print(f"  ✅ Partial symbol match: {quote_key} ({quote_symbol}) -> {holding.tradingsymbol}")
                            break

                if not quote_data:
                    print(f"  ❌ No match found for {holding.tradingsymbol} ({holding.instrument_token})")
                    print(f"     Available quotes:")
                    for k, v in list(market_quotes.items())[:3]:  # Show first 3 for debugging
                        print(f"       {k}: {v.get('symbol', 'No symbol')}")
                    if len(market_quotes) > 3:
                        print(f"       ... and {len(market_quotes) - 3} more")

                if quote_data:
                    # Extract day change data from market quotes
                    last_price = quote_data.get('last_price', holding.last_price)
                    net_change = quote_data.get('net_change', 0)
                    previous_close = quote_data.get('ohlc', {}).get('close', holding.close_price)

                    # Calculate day change percentage
                    day_change_percentage = (net_change / previous_close * 100) if previous_close != 0 else 0

                    # Update holding with market quote data
                    holding.real_time_price = last_price  # Store real-time price
                    holding.last_price = last_price  # Update current price
                    holding.previous_close = previous_close  # Store previous close
                    holding.day_change = net_change
                    holding.day_change_percentage = day_change_percentage
                    holding.day_pnl = net_change * holding.quantity

                    print(f"  ✅ Updated {holding.tradingsymbol}: {day_change_percentage:.2f}% (₹{net_change:.2f}, P&L: ₹{holding.day_pnl:.2f})")
                    print(f"     Real-time Price: ₹{last_price:.2f}, Previous Close: ₹{previous_close:.2f}")
                else:
                    # Set default values if no market quote data available
                    holding.day_change = 0
                    holding.day_change_percentage = 0
                    holding.day_pnl = 0
                    holding.real_time_price = holding.last_price
                    holding.previous_close = holding.close_price
                    print(f"  ❌ No market quote data for {holding.tradingsymbol}, set to defaults")
            else:
                print(f"\n{holding.tradingsymbol}: No instrument token available")
                holding.day_change = 0
                holding.day_change_percentage = 0
                holding.day_pnl = 0
                holding.real_time_price = holding.last_price
                holding.previous_close = holding.close_price

        print(f"=== RETURNING {len(holdings)} HOLDINGS WITH REAL-TIME DAY CHANGE DATA ===")
        return holdings

    def _fetch_market_quotes(self, instrument_keys: List[str]) -> Dict[str, Dict]:
        """Fetch market quotes for multiple instruments"""
        print(f"=== FETCHING MARKET QUOTES FOR {len(instrument_keys)} INSTRUMENTS ===")

        try:
            headers = self.auth_service.get_headers()

            # Market quotes API endpoint
            url = f"{self.config.UPSTOX_BASE_URL}/v2/market-quote/quotes"

            # Split into batches of 500 (API limit)
            batch_size = 500
            all_quotes = {}

            for i in range(0, len(instrument_keys), batch_size):
                batch = instrument_keys[i:i + batch_size]
                batch_str = ','.join(batch)

                print(f"Fetching batch {i//batch_size + 1}: {len(batch)} instruments")

                params = {'instrument_key': batch_str}
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()

                batch_data = response.json()

                if batch_data.get('status') == 'success' and 'data' in batch_data:
                    batch_quotes = batch_data['data']
                    all_quotes.update(batch_quotes)
                    print(f"Successfully fetched quotes for {len(batch_quotes)} instruments in batch")

                    # Log sample data for debugging
                    for instrument_key, quote in list(batch_quotes.items())[:2]:  # Show first 2
                        last_price = quote.get('last_price', 0)
                        net_change = quote.get('net_change', 0)
                        previous_close = quote.get('ohlc', {}).get('close', 0)
                        day_change_pct = (net_change / previous_close * 100) if previous_close != 0 else 0

                        print(f"  Sample: {quote.get('symbol', instrument_key)}")
                        print(f"    Last: ₹{last_price:.2f}, Change: ₹{net_change:.2f} ({day_change_pct:.2f}%)")
                else:
                    print(f"Error in market quotes response: {batch_data}")

            print(f"=== MARKET QUOTES SUMMARY: {len(all_quotes)} quotes fetched ===")
            return all_quotes

        except requests.exceptions.RequestException as e:
            print(f"❌ Market quotes API request failed: {str(e)}")
            return {}
        except Exception as e:
            print(f"❌ Error fetching market quotes: {str(e)}")
            return {}

    def _fetch_day_change_batch(self, instrument_tokens: List[str]) -> Dict[str, Dict]:
        """
        Fetch day change data using market quotes API
        Returns data in format expected by existing code
        """
        market_quotes = self._fetch_market_quotes(instrument_tokens)

        # Convert market quotes format to day change format
        day_change_data = {}

        for instrument_key, quote_data in market_quotes.items():
            last_price = quote_data.get('last_price', 0)
            net_change = quote_data.get('net_change', 0)
            previous_close = quote_data.get('ohlc', {}).get('close', 0)

            day_change_percentage = (net_change / previous_close * 100) if previous_close != 0 else 0

            day_change_data[instrument_key] = {
                'day_change': float(net_change),
                'day_change_percentage': float(day_change_percentage),
                'latest_close': float(last_price),
                'previous_close': float(previous_close),
                'data_date': datetime.now().strftime('%Y-%m-%d'),
                'source': 'market_quotes'
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
