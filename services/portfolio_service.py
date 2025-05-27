import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
import logging

from models.portfolio import PortfolioSummary, PerformanceMetrics, Holding
from services.upstox_service import UpstoxService
from services.market_data_service import MarketDataService
from utils.calculations import FinancialCalculator
from utils.projections import PortfolioProjector, ProjectionResults, ScenarioResult

logger = logging.getLogger(__name__)

class PortfolioService:
    """Service for portfolio calculations and analysis"""

    def __init__(self):
        self.upstox_service = UpstoxService()
        self.market_data_service = MarketDataService()
        self.calculator = FinancialCalculator()
        self.projector = PortfolioProjector(market_data_service=self.market_data_service)
        self._holdings_cache = None
        self._cache_timestamp = None
        self._cache_timeout_minutes = 5  # Unified cache timeout
        self._historical_cache = {}  # Cache for historical data
        self._historical_cache_timeout = timedelta(hours=1)  # Historical data cache timeout

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

            hist_data = self._get_cached_historical_data(
                holding.instrument_token, holding.tradingsymbol, start_date, end_date
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

    def get_portfolio_projections(
            self,
            years: int = 5,
            simulations: int = 10000,
            method: str = 'parametric',
            use_historical: bool = True
    ) -> ProjectionResults:
        """
        Get Monte Carlo projections for portfolio

        Args:
            years: Number of years to project
            simulations: Number of Monte Carlo simulations
            method: 'historical' or 'parametric'
            use_historical: Whether to use historical data for calculations

        Returns:
            ProjectionResults object with simulation results
        """
        # Get current portfolio value
        portfolio_summary = self.get_portfolio_summary()
        current_value = portfolio_summary.total_value

        if current_value <= 0:
            raise ValueError("No portfolio value to project")

        # Calculate portfolio statistics
        if use_historical and method == 'historical':
            # Get historical returns for the portfolio
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * 3)  # 3 years of data

            portfolio_metrics, _, returns_df = self.get_performance_analysis(start_date, end_date)

            if portfolio_metrics and not returns_df.empty:
                # Use historical portfolio returns
                portfolio_returns = returns_df['Portfolio Value'].pct_change().dropna()

                projections = self.projector.monte_carlo_projection(
                    current_value=current_value,
                    historical_returns=portfolio_returns,
                    years=years,
                    simulations=simulations,
                    method='historical'
                )
            else:
                # Fallback to parametric if no historical data
                method = 'parametric'

        if method == 'parametric' or not use_historical:
            # Use parametric method with market-derived parameters
            market_params = self.market_data_service.get_market_parameters()
            expected_return = market_params['expected_return']
            volatility = market_params['volatility']

            logger.info(f"Using market parameters: return={expected_return:.2%}, vol={volatility:.2%}")

            # Optionally adjust based on portfolio allocation
            # This is a simplified approach - you could make this more sophisticated
            if portfolio_summary.holdings:
                # Could analyze holdings to adjust expectations
                # For example, if portfolio has small/mid-cap stocks, increase volatility
                pass

            projections = self.projector.monte_carlo_projection(
                current_value=current_value,
                expected_return=expected_return,
                volatility=volatility,
                years=years,
                simulations=simulations,
                method='parametric'
            )

        return projections

    def get_scenario_analysis(self, years: int = 5) -> List[ScenarioResult]:
        """
        Get scenario analysis for portfolio

        Args:
            years: Number of years to project

        Returns:
            List of ScenarioResult objects
        """
        portfolio_summary = self.get_portfolio_summary()
        current_value = portfolio_summary.total_value

        if current_value <= 0:
            raise ValueError("No portfolio value for scenario analysis")

        return self.projector.scenario_analysis(
            current_value=current_value,
            years=years
        )

    def get_fire_projections(
            self,
            annual_expenses: float,
            current_age: int,
            retirement_age: int,
            life_expectancy: int = 90
    ) -> Dict[str, float]:
        """
        Get FIRE (Financial Independence) projections

        Args:
            annual_expenses: Current annual expenses
            current_age: Current age
            retirement_age: Target retirement age
            life_expectancy: Expected life span

        Returns:
            Dictionary with FIRE calculations
        """
        portfolio_summary = self.get_portfolio_summary()
        current_value = portfolio_summary.total_value

        # Calculate FIRE number
        fire_calcs = self.projector.calculate_fire_number(
            annual_expenses=annual_expenses,
            current_age=current_age,
            retirement_age=retirement_age,
            life_expectancy=life_expectancy
        )

        # Calculate required savings to reach FIRE
        savings_calcs = self.projector.calculate_required_savings(
            current_value=current_value,
            target_value=fire_calcs['fire_number'],
            years=fire_calcs['years_to_retirement']
        )

        # Combine results
        return {
            **fire_calcs,
            'current_portfolio_value': current_value,
            'gap_to_fire': fire_calcs['fire_number'] - current_value,
            'monthly_savings_needed': savings_calcs['monthly_savings_needed'],
            'on_track': current_value >= (fire_calcs['fire_number'] * 0.2)  # Simple check
        }

    def calculate_goal_progress(
            self,
            goal_amount: float,
            goal_date: datetime,
            monthly_contribution: float = 0
    ) -> Dict[str, any]:
        """
        Calculate progress towards a financial goal

        Args:
            goal_amount: Target amount to reach
            goal_date: Target date to reach goal
            monthly_contribution: Monthly contribution amount

        Returns:
            Dictionary with goal progress calculations
        """
        portfolio_summary = self.get_portfolio_summary()
        current_value = portfolio_summary.total_value

        # Calculate time to goal
        years_to_goal = (goal_date - datetime.now()).days / 365.25

        if years_to_goal <= 0:
            return {
                'goal_amount': goal_amount,
                'current_value': current_value,
                'achieved': current_value >= goal_amount,
                'surplus_or_deficit': current_value - goal_amount
            }

        # Calculate required savings
        savings_needed = self.projector.calculate_required_savings(
            current_value=current_value,
            target_value=goal_amount,
            years=years_to_goal
        )

        # Run projection with current contribution
        if monthly_contribution > 0:
            # Adjust current value for contributions
            total_contributions = monthly_contribution * 12 * years_to_goal
            effective_target = goal_amount - total_contributions

            projection = self.projector.monte_carlo_projection(
                current_value=current_value,
                expected_return=0.08,
                volatility=0.15,
                years=int(years_to_goal),
                simulations=1000
            )

            probability_of_success = 1 - projection.probability_of_loss
        else:
            probability_of_success = 0.5  # Rough estimate

        return {
            'goal_amount': goal_amount,
            'current_value': current_value,
            'years_to_goal': years_to_goal,
            'monthly_savings_needed': savings_needed['monthly_savings_needed'],
            'current_monthly_contribution': monthly_contribution,
            'savings_gap': savings_needed['monthly_savings_needed'] - monthly_contribution,
            'probability_of_success': probability_of_success,
            'on_track': monthly_contribution >= savings_needed['monthly_savings_needed']
        }

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

    def _get_cached_historical_data(
            self,
            instrument_key: str,
            symbol: str,
            start_date: datetime,
            end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """Get historical data with caching"""
        cache_key = f"{instrument_key}_{start_date.date()}_{end_date.date()}"

        # Check cache
        if cache_key in self._historical_cache:
            cached_data, cache_time = self._historical_cache[cache_key]
            if datetime.now() - cache_time < self._historical_cache_timeout:
                return cached_data

        # Fetch fresh data
        hist_data = self.upstox_service.get_historical_data(
            instrument_key, start_date, end_date
        )

        # Cache the result
        if hist_data is not None:
            self._historical_cache[cache_key] = (hist_data, datetime.now())

        return hist_data

    def refresh_cache(self):
        """Force refresh of holdings cache and clear all cached data"""
        print("Refreshing portfolio cache...")
        self._holdings_cache = None
        self._cache_timestamp = None
        self._historical_cache.clear()  # Clear historical data cache too
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
