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

    def _is_cache_valid(self) -> bool:
        """Check if holdings cache is still valid"""
        if not self._cache_timestamp:
            return False
        return datetime.now() - self._cache_timestamp < timedelta(minutes=15)

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get comprehensive portfolio summary"""
        holdings = self._get_cached_holdings()

        # Convert to DataFrame for calculations
        holdings_data = []
        for holding in holdings:
            holdings_data.append({
                'tradingsymbol': holding.tradingsymbol,
                'quantity': holding.quantity,
                'average_price': holding.average_price,
                'last_price': holding.last_price,
                'pnl': holding.pnl,
                'close_price': holding.close_price
            })

        df = pd.DataFrame(holdings_data)

        # Calculate metrics
        df = self.calculator.calculate_portfolio_value(df)

        # Update holding objects with calculated values
        for i, holding in enumerate(holdings):
            holding.current_value = df.iloc[i]['current_value']
            holding.investment = df.iloc[i]['investment']
            holding.return_percentage = df.iloc[i]['return_%']
            holding.allocation_percentage = df.iloc[i]['allocation_%']

        total_value = df['current_value'].sum()
        total_investment = df['investment'].sum()
        total_pnl = df['pnl'].sum()
        total_return_percentage = ((total_pnl / total_investment) * 100) if total_investment > 0 else 0

        return PortfolioSummary(
            total_value=total_value,
            total_investment=total_investment,
            total_pnl=total_pnl,
            total_return_percentage=total_return_percentage,
            holdings=holdings
        )

    def get_performance_analysis(self, start_date: datetime, end_date: datetime) -> Tuple[Optional[PerformanceMetrics], Optional[PerformanceMetrics], pd.DataFrame]:
        """Get portfolio performance analysis with benchmark comparison"""
        holdings = self._get_cached_holdings()

        # Build portfolio returns DataFrame
        returns_df = pd.DataFrame()

        for holding in holdings:
            if not holding.instrument_token:
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
        """Get holdings with caching"""
        if not self._is_cache_valid():
            self._holdings_cache = self.upstox_service.get_holdings()
            self._cache_timestamp = datetime.now()

        return self._holdings_cache

    def refresh_cache(self):
        """Force refresh of holdings cache"""
        self._holdings_cache = None
        self._cache_timestamp = None
