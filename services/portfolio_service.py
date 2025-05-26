import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from models.portfolio import PortfolioSummary, PerformanceMetrics, Holding
from services.upstox_service import UpstoxService
from utils.calculations import FinancialCalculator

class PortfolioService:
    """Service for portfolio calculations and analysis"""

    def __init__(self):
        self.upstox_service = UpstoxService()
        self.calculator = FinancialCalculator()
        self._holdings_cache = None
        self._cache_timestamp = None
        self._cache_timeout_minutes = 5  # Unified cache timeout

    def _is_cache_valid(self) -> bool:
        """Check if holdings cache is still valid"""
        if not self._cache_timestamp:
            return False
        return datetime.now() - self._cache_timestamp < timedelta(minutes=self._cache_timeout_minutes)

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get comprehensive portfolio summary with day change data"""
        holdings = self._get_cached_holdings_with_day_change()

        # Handle empty holdings or error case
        if not holdings:
            return PortfolioSummary(
                total_value=0,
                total_investment=0,
                total_pnl=0,
                total_return_percentage=0,
                holdings=[],
                total_day_change=0,
                total_day_change_percentage=0,
                total_day_pnl=0
            )

        # Convert to DataFrame for calculations
        holdings_data = []
        for holding in holdings:
            # Ensure we have Holding objects, not dicts
            if isinstance(holding, dict):
                continue  # Skip invalid entries

            holdings_data.append({
                'tradingsymbol': holding.tradingsymbol,
                'quantity': holding.quantity,
                'average_price': holding.average_price,
                'last_price': holding.last_price,
                'pnl': holding.pnl,
                'close_price': holding.close_price,
                'day_change': getattr(holding, 'day_change', 0),
                'day_change_percentage': getattr(holding, 'day_change_percentage', 0),
                'day_pnl': getattr(holding, 'day_pnl', 0)
            })

        if not holdings_data:
            return PortfolioSummary(
                total_value=0,
                total_investment=0,
                total_pnl=0,
                total_return_percentage=0,
                holdings=[],
                total_day_change=0,
                total_day_change_percentage=0,
                total_day_pnl=0
            )

        df = pd.DataFrame(holdings_data)

        # Calculate metrics
        df = self.calculator.calculate_portfolio_value(df)

        # Update holding objects with calculated values
        valid_holdings = []
        for i, holding in enumerate(holdings):
            if isinstance(holding, dict):
                continue  # Skip invalid entries

            if i < len(df):
                holding.current_value = df.iloc[i]['current_value']
                holding.investment = df.iloc[i]['investment']
                holding.return_percentage = df.iloc[i]['return_%']
                holding.allocation_percentage = df.iloc[i]['allocation_%']
                # Day change values are already set from the API
                if not hasattr(holding, 'day_change'):
                    holding.day_change = 0
                if not hasattr(holding, 'day_change_percentage'):
                    holding.day_change_percentage = 0
                if not hasattr(holding, 'day_pnl'):
                    holding.day_pnl = 0

                valid_holdings.append(holding)

        total_value = df['current_value'].sum()
        total_investment = df['investment'].sum()
        total_pnl = df['pnl'].sum()
        total_return_percentage = ((total_pnl / total_investment) * 100) if total_investment > 0 else 0

        # Calculate total day change metrics
        total_day_pnl = df['day_pnl'].sum()
        total_day_change_percentage = (total_day_pnl / total_value) * 100 if total_value > 0 else 0
        total_day_change = df['day_change'].sum()  # This is less meaningful but included for completeness

        return PortfolioSummary(
            total_value=total_value,
            total_investment=total_investment,
            total_pnl=total_pnl,
            total_return_percentage=total_return_percentage,
            holdings=valid_holdings,
            total_day_change=total_day_change,
            total_day_change_percentage=total_day_change_percentage,
            total_day_pnl=total_day_pnl
        )

    def get_performance_analysis(self, start_date: datetime, end_date: datetime) -> Tuple[Optional[PerformanceMetrics], Optional[PerformanceMetrics], pd.DataFrame]:
        """Get portfolio performance analysis with benchmark comparison"""
        holdings = self._get_cached_holdings()

        # Handle case where holdings might be empty or contain errors
        if not holdings:
            return None, None, pd.DataFrame()

        # Build portfolio returns DataFrame
        returns_df = pd.DataFrame()

        for holding in holdings:
            # Skip if holding is a dict (error case) or missing instrument_token
            if isinstance(holding, dict):
                continue

            if not hasattr(holding, 'instrument_token') or not holding.instrument_token:
                continue

            hist_data = self.upstox_service.get_historical_data(
                holding.instrument_token, start_date, end_date
            )

            if hist_data is not None:
                # Calculate position value over time
                position_value = hist_data['close'] * holding.quantity
                returns_df[holding.tradingsymbol] = position_value

        if returns_df.empty:
            return None, None, pd.DataFrame()

        # Calculate portfolio total value and returns
        returns_df = returns_df.sort_index()
        returns_df = returns_df.ffill().fillna(0)
        returns_df['Portfolio Value'] = returns_df.sum(axis=1)
        portfolio_returns = returns_df['Portfolio Value'].pct_change().fillna(0)

        # Calculate portfolio metrics
        portfolio_metrics_data = self.calculator.calculate_metrics(portfolio_returns)
        portfolio_metrics = PerformanceMetrics(
            volatility=portfolio_metrics_data['volatility'],
            sharpe_ratio=portfolio_metrics_data['sharpe'],
            max_drawdown=portfolio_metrics_data['max_drawdown'],
            total_return=portfolio_metrics_data['total_return'],
            cumulative_returns=portfolio_metrics_data['cumulative_returns']
        )

        # Get benchmark data
        benchmark_metrics = None
        benchmark_data = self.upstox_service.get_benchmark_data(start_date, end_date)

        if benchmark_data is not None:
            benchmark_returns = benchmark_data['close'].pct_change().fillna(0)
            benchmark_metrics_data = self.calculator.calculate_metrics(benchmark_returns)
            benchmark_metrics = PerformanceMetrics(
                volatility=benchmark_metrics_data['volatility'],
                sharpe_ratio=benchmark_metrics_data['sharpe'],
                max_drawdown=benchmark_metrics_data['max_drawdown'],
                total_return=benchmark_metrics_data['total_return'],
                cumulative_returns=benchmark_metrics_data['cumulative_returns']
            )

        return portfolio_metrics, benchmark_metrics, returns_df

    def _get_cached_holdings(self) -> List[Holding]:
        """Get holdings with caching (without day change data)"""
        if not self._is_cache_valid():
            try:
                print("Regular cache invalid, fetching fresh holdings...")
                self._holdings_cache = self.upstox_service.get_holdings()
                self._cache_timestamp = datetime.now()
                print(f"Cached {len(self._holdings_cache)} regular holdings")
            except Exception as e:
                print(f"Error fetching regular holdings: {str(e)}")
                self._holdings_cache = []

        return self._holdings_cache or []

    def _get_cached_holdings_with_day_change(self) -> List[Holding]:
        """Get holdings with day change data and caching"""
        if not self._is_cache_valid():
            try:
                print("Day change cache invalid, fetching fresh holdings with day change...")
                self._holdings_cache = self.upstox_service.get_holdings_with_day_change()
                self._cache_timestamp = datetime.now()
                print(f"Cached {len(self._holdings_cache)} holdings with day change data")
            except Exception as e:
                print(f"Error fetching holdings with day change: {str(e)}")
                # Fallback to regular holdings without day change
                try:
                    print("Falling back to regular holdings...")
                    holdings = self.upstox_service.get_holdings()
                    # Add default day change values
                    for holding in holdings:
                        if hasattr(holding, 'tradingsymbol'):  # Ensure it's a valid Holding object
                            holding.day_change = 0
                            holding.day_change_percentage = 0
                            holding.day_pnl = 0
                    self._holdings_cache = holdings
                    self._cache_timestamp = datetime.now()
                    print(f"Fallback successful, cached {len(self._holdings_cache)} holdings")
                except Exception as e2:
                    print(f"Error fetching regular holdings: {str(e2)}")
                    self._holdings_cache = []

        return self._holdings_cache or []

    def refresh_cache(self):
        """Force refresh of holdings cache and clear all cached data"""
        print("Refreshing portfolio cache...")
        self._holdings_cache = None
        self._cache_timestamp = None
        print("Cache cleared, next request will fetch fresh data")

    def force_refresh_day_change(self):
        """Force refresh of day change data specifically"""
        print("Force refreshing day change data...")
        try:
            # Bypass cache and fetch fresh day change data
            self._holdings_cache = self.upstox_service.get_holdings_with_day_change()
            self._cache_timestamp = datetime.now()
            print(f"Day change data refreshed for {len(self._holdings_cache)} holdings")
        except Exception as e:
            print(f"Error refreshing day change data: {str(e)}")
            # Fallback to regular holdings
            self._holdings_cache = self.upstox_service.get_holdings()
            for holding in self._holdings_cache:
                if hasattr(holding, 'tradingsymbol'):
                    holding.day_change = 0
                    holding.day_change_percentage = 0
                    holding.day_pnl = 0
            self._cache_timestamp = datetime.now()
