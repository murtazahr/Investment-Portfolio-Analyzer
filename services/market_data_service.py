"""
Market data service for fetching and calculating market parameters dynamically
"""

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config import Config
from services.upstox_service import UpstoxService

logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for fetching and calculating market parameters from actual data"""

    def __init__(self):
        self.upstox_service = UpstoxService()
        self.config = Config()
        self._cache_timeout = timedelta(hours=24)  # Cache market data for 24 hours
        self._last_cache_time = None
        self._cached_parameters = None

    @lru_cache(maxsize=1)
    def get_market_parameters(self, force_refresh: bool = False) -> Dict[str, float]:
        """
        Get market parameters calculated from actual historical data
        
        Returns:
            Dictionary with market parameters:
            - expected_return: Historical CAGR
            - volatility: Historical annualized volatility
            - risk_free_rate: Current repo rate (or fallback)
            - inflation_rate: Recent inflation (or fallback)
        """
        # Check cache
        if not force_refresh and self._cached_parameters and self._last_cache_time:
            if datetime.now() - self._last_cache_time < self._cache_timeout:
                logger.info("Returning cached market parameters")
                return self._cached_parameters

        logger.info("Calculating fresh market parameters from historical data")

        try:
            # Get benchmark historical data
            end_date = datetime.now()

            # Try different time periods for robustness
            parameters = {}

            # Calculate 20-year parameters (if available)
            twenty_year_params = self._calculate_historical_parameters(
                end_date - timedelta(days=365 * 20), end_date, "20-year"
            )

            # Calculate 10-year parameters
            ten_year_params = self._calculate_historical_parameters(
                end_date - timedelta(days=365 * 10), end_date, "10-year"
            )

            # Calculate 5-year parameters
            five_year_params = self._calculate_historical_parameters(
                end_date - timedelta(days=365 * 5), end_date, "5-year"
            )

            # Calculate 3-year parameters (minimum recommended)
            three_year_params = self._calculate_historical_parameters(
                end_date - timedelta(days=365 * 3), end_date, "3-year"
            )

            # Use the longest available period with valid data
            if twenty_year_params:
                parameters = twenty_year_params
                logger.info("Using 20-year historical parameters")
            elif ten_year_params:
                parameters = ten_year_params
                logger.info("Using 10-year historical parameters")
            elif five_year_params:
                parameters = five_year_params
                logger.info("Using 5-year historical parameters")
            elif three_year_params:
                parameters = three_year_params
                logger.info("Using 3-year historical parameters")
            else:
                # Fallback to conservative defaults if no data available
                logger.warning("No historical data available, using conservative defaults")
                parameters = self._get_fallback_parameters()

            # Add current market conditions
            parameters.update(self._get_current_market_conditions())

            # Cache the results
            self._cached_parameters = parameters
            self._last_cache_time = datetime.now()

            logger.info(f"Market parameters calculated: {parameters}")
            return parameters

        except Exception as e:
            logger.error(f"Error calculating market parameters: {str(e)}")
            return self._get_fallback_parameters()

    def _calculate_historical_parameters(
            self,
            start_date: datetime,
            end_date: datetime,
            period_name: str
    ) -> Optional[Dict[str, float]]:
        """
        Calculate market parameters from historical data
        
        Returns:
            Dictionary with calculated parameters or None if insufficient data
        """
        try:
            # Get benchmark (Nifty 50) historical data
            benchmark_data = self.upstox_service.get_benchmark_data(start_date, end_date)

            if benchmark_data is None or len(benchmark_data) < 250:  # At least 1 year of daily data
                logger.warning(f"Insufficient data for {period_name} calculation")
                return None

            # Calculate daily returns
            daily_returns = benchmark_data['close'].pct_change().dropna()

            # Calculate annualized return (CAGR)
            total_return = (benchmark_data['close'].iloc[-1] / benchmark_data['close'].iloc[0]) - 1
            years = (end_date - start_date).days / 365.25
            cagr = (1 + total_return) ** (1 / years) - 1

            # Calculate annualized volatility
            # Annualize daily volatility (assuming 252 trading days)
            annual_volatility = daily_returns.std() * np.sqrt(252)

            # Get VIX-based volatility for comparison
            vix_stats = self.get_volatility_index_stats(days_back=int(years * 365))

            # Use VIX average if available and reliable
            if vix_stats['data_points'] > 100:
                # Convert VIX to decimal (VIX of 20 = 20% volatility)
                vix_based_volatility = vix_stats['average_vix'] / 100

                # Take weighted average of calculated and VIX-based volatility
                # Give more weight to VIX as it's forward-looking
                annual_volatility = (0.4 * annual_volatility + 0.6 * vix_based_volatility)

                logger.info(f"Using VIX-adjusted volatility: {annual_volatility:.2%}")

            # Calculate Sharpe ratio (for reference)
            # Assuming risk-free rate of 6% for India
            risk_free_daily = 0.06 / 252
            excess_returns = daily_returns - risk_free_daily
            sharpe_ratio = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252)

            # Calculate maximum drawdown
            cumulative_returns = (1 + daily_returns).cumprod()
            running_max = cumulative_returns.cummax()
            drawdown = (cumulative_returns - running_max) / running_max
            max_drawdown = drawdown.min()

            return {
                'expected_return': cagr,
                'volatility': annual_volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'data_points': len(daily_returns),
                'period_years': years,
                'vix_adjusted': vix_stats['data_points'] > 100
            }

        except Exception as e:
            logger.error(f"Error calculating {period_name} parameters: {str(e)}")
            return None

    @staticmethod
    def _get_current_market_conditions() -> Dict[str, float]:
        """
        Get current market conditions (risk-free rate, inflation)
        
        For now, returns sensible defaults for India
        In production, could integrate with RBI API or other data sources
        """
        return {
            'risk_free_rate': 0.0625,  # Current repo rate
            'inflation_rate': 0.046    # Current CPI inflation
        }

    @staticmethod
    def _get_fallback_parameters() -> Dict[str, float]:
        """
        Get fallback parameters when historical data is not available
        
        Conservative estimates based on Indian market characteristics
        """
        return {
            'expected_return': 0.10,   # 10% - Conservative estimate
            'volatility': 0.25,        # 25% - Higher for safety
            'risk_free_rate': 0.0625,  # 6.25% - Current repo rate
            'inflation_rate': 0.05,    # 5% - Slightly above current
            'sharpe_ratio': 0.4,       # Conservative Sharpe
            'max_drawdown': -0.5       # 50% max drawdown assumption
        }

    def get_volatility_index_stats(self, days_back: int = 365) -> Dict[str, float]:
        """
        Get India VIX statistics from actual data
        
        Args:
            days_back: Number of days of historical VIX data to analyze
            
        Returns:
            Dictionary with VIX statistics
        """
        try:
            # India VIX instrument token on NSE
            vix_instrument_token = "NSE_INDEX|India VIX"

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            logger.info(f"Fetching India VIX data from {start_date.date()} to {end_date.date()}")

            # Fetch VIX historical data using existing upstox service
            vix_data = self.upstox_service.get_historical_data(
                vix_instrument_token,
                start_date,
                end_date
            )

            if vix_data is not None and len(vix_data) > 0:
                # Calculate VIX statistics
                current_vix = vix_data['close'].iloc[-1]
                average_vix = vix_data['close'].mean()
                min_vix = vix_data['close'].min()
                max_vix = vix_data['close'].max()
                percentile_75 = vix_data['close'].quantile(0.75)
                percentile_25 = vix_data['close'].quantile(0.25)

                logger.info(f"VIX Stats - Current: {current_vix:.2f}, Average: {average_vix:.2f}")

                return {
                    'current_vix': float(current_vix),
                    'average_vix': float(average_vix),
                    'min_vix': float(min_vix),
                    'max_vix': float(max_vix),
                    'percentile_25': float(percentile_25),
                    'percentile_75': float(percentile_75),
                    'data_points': len(vix_data)
                }
            else:
                logger.warning("No VIX data available, using fallback values")
                return self._get_fallback_vix_stats()

        except Exception as e:
            logger.error(f"Error fetching VIX data: {str(e)}")
            return self._get_fallback_vix_stats()

    @staticmethod
    def _get_fallback_vix_stats() -> Dict[str, float]:
        """Fallback VIX statistics based on historical averages"""
        return {
            'current_vix': 15.0,
            'average_vix': 21.18,   # Historical average
            'min_vix': 8.60,
            'max_vix': 86.64,
            'percentile_25': 15.0,
            'percentile_75': 25.0,
            'data_points': 0
        }

    def get_scenario_parameters(self) -> Dict[str, Dict[str, float]]:
        """
        Get scenario analysis parameters based on historical data and current VIX
        
        Returns:
            Dictionary of scenarios with their parameters
        """
        base_params = self.get_market_parameters()
        base_return = base_params['expected_return']
        base_volatility = base_params['volatility']

        # Get current VIX for dynamic adjustment
        vix_stats = self.get_volatility_index_stats(days_back=30)
        current_vix = vix_stats['current_vix']
        vix_adjustment = current_vix / vix_stats['average_vix']  # Ratio to historical average

        # Adjust scenarios based on current market conditions
        if vix_adjustment > 1.5:  # High VIX environment
            # More conservative scenarios during high volatility
            return {
                'bull': {
                    'name': 'Bull Market',
                    'description': 'Recovery from high volatility',
                    'return': base_return * 1.3,  # Lower bull returns
                    'volatility': base_volatility * 1.2  # Higher volatility even in bull
                },
                'base': {
                    'name': 'Base Case',
                    'description': 'Volatile market conditions',
                    'return': base_return * 0.8,  # Lower base returns
                    'volatility': base_volatility * vix_adjustment  # Adjusted for current VIX
                },
                'bear': {
                    'name': 'Bear Market',
                    'description': 'Continued high volatility',
                    'return': base_return * 0.2,
                    'volatility': base_volatility * 2.0
                },
                'crash': {
                    'name': 'Market Crash',
                    'description': 'Extreme volatility scenario',
                    'return': -0.30,  # Deeper crash in high VIX
                    'volatility': base_volatility * 3.0
                }
            }
        elif vix_adjustment < 0.8:  # Low VIX environment
            # More optimistic scenarios during calm markets
            return {
                'bull': {
                    'name': 'Bull Market',
                    'description': 'Strong growth in calm markets',
                    'return': base_return * 1.8,  # Higher bull returns
                    'volatility': base_volatility * 0.7  # Lower volatility
                },
                'base': {
                    'name': 'Base Case',
                    'description': 'Stable market conditions',
                    'return': base_return * 1.1,  # Slightly higher base
                    'volatility': base_volatility * vix_adjustment
                },
                'bear': {
                    'name': 'Bear Market',
                    'description': 'Mild correction',
                    'return': base_return * 0.5,  # Less severe bear
                    'volatility': base_volatility * 1.3
                },
                'crash': {
                    'name': 'Market Crash',
                    'description': 'Sharp but brief correction',
                    'return': -0.15,  # Milder crash
                    'volatility': base_volatility * 2.0
                }
            }
        else:  # Normal VIX environment
            return {
                'bull': {
                    'name': 'Bull Market',
                    'description': 'Strong economic growth, positive reforms',
                    'return': base_return * 1.5,
                    'volatility': base_volatility * 0.8
                },
                'base': {
                    'name': 'Base Case',
                    'description': 'Normal market conditions based on historical average',
                    'return': base_return,
                    'volatility': base_volatility
                },
                'bear': {
                    'name': 'Bear Market',
                    'description': 'Economic slowdown, global headwinds',
                    'return': base_return * 0.3,
                    'volatility': base_volatility * 1.5
                },
                'crash': {
                    'name': 'Market Crash',
                    'description': 'Severe recession, systemic crisis',
                    'return': -0.20,
                    'volatility': base_volatility * 2.5
                }
            }

    def calculate_rolling_statistics(
            self,
            window_years: int = 1
    ) -> pd.DataFrame:
        """
        Calculate rolling statistics for different time windows
        
        Args:
            window_years: Rolling window in years
            
        Returns:
            DataFrame with rolling statistics
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * (window_years + 5))  # Extra data for rolling

            benchmark_data = self.upstox_service.get_benchmark_data(start_date, end_date)

            if benchmark_data is None:
                return pd.DataFrame()

            # Calculate rolling returns and volatility
            daily_returns = benchmark_data['close'].pct_change().dropna()
            trading_days = 252 * window_years

            rolling_returns = daily_returns.rolling(window=trading_days).apply(
                lambda x: (1 + x).prod() ** (252 / len(x)) - 1
            )

            rolling_volatility = daily_returns.rolling(window=trading_days).std() * np.sqrt(252)

            return pd.DataFrame({
                'rolling_return': rolling_returns,
                'rolling_volatility': rolling_volatility
            })

        except Exception as e:
            logger.error(f"Error calculating rolling statistics: {str(e)}")
            return pd.DataFrame()

    def get_current_market_sentiment(self) -> Dict[str, any]:
        """
        Get current market sentiment based on VIX levels

        Returns:
            Dictionary with market sentiment indicators
        """
        vix_stats = self.get_volatility_index_stats(days_back=30)  # Last 30 days
        current_vix = vix_stats['current_vix']

        # Determine market sentiment based on VIX levels
        if current_vix < 15:
            sentiment = "Low Volatility - Calm Markets"
            risk_level = "Low"
        elif current_vix < 20:
            sentiment = "Normal Volatility"
            risk_level = "Moderate"
        elif current_vix < 30:
            sentiment = "Elevated Volatility - Caution Advised"
            risk_level = "High"
        else:
            sentiment = "High Volatility - Extreme Caution"
            risk_level = "Very High"

        # Calculate VIX percentile rank (where current VIX stands historically)
        historical_vix = self.get_volatility_index_stats(days_back=365 * 3)  # 3 years

        return {
            'current_vix': current_vix,
            'sentiment': sentiment,
            'risk_level': risk_level,
            'vix_percentile': self._calculate_vix_percentile(current_vix, historical_vix),
            'recommendation': self._get_investment_recommendation(current_vix, risk_level)
        }

    @staticmethod
    def _calculate_vix_percentile(current_vix: float, historical_stats: Dict) -> float:
        """Calculate where current VIX stands in historical distribution"""
        if current_vix <= historical_stats['min_vix']:
            return 0.0
        elif current_vix >= historical_stats['max_vix']:
            return 100.0
        elif current_vix <= historical_stats['percentile_25']:
            return 25.0 * (current_vix - historical_stats['min_vix']) / (historical_stats['percentile_25'] - historical_stats['min_vix'])
        elif current_vix <= historical_stats['average_vix']:
            return 25.0 + 25.0 * (current_vix - historical_stats['percentile_25']) / (historical_stats['average_vix'] - historical_stats['percentile_25'])
        elif current_vix <= historical_stats['percentile_75']:
            return 50.0 + 25.0 * (current_vix - historical_stats['average_vix']) / (historical_stats['percentile_75'] - historical_stats['average_vix'])
        else:
            return 75.0 + 25.0 * (current_vix - historical_stats['percentile_75']) / (historical_stats['max_vix'] - historical_stats['percentile_75'])

    @staticmethod
    def _get_investment_recommendation(vix_level: float, risk_level: str) -> str:
        """Get investment recommendation based on VIX level"""
        if vix_level < 15:
            return "Markets are calm. Good time for systematic investments."
        elif vix_level < 20:
            return "Normal market conditions. Continue with regular investment plan."
        elif vix_level < 30:
            return "Volatility is elevated. Consider defensive positions or wait for better entry points."
        else:
            return "Extreme volatility. Consider reducing exposure or hedging positions."
