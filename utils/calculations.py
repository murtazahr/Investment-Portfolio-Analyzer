import numpy as np
import pandas as pd

class FinancialCalculator:
    """Financial calculations and metrics"""

    @staticmethod
    def calculate_metrics(returns_series):
        """Calculate comprehensive financial metrics for a returns series"""
        if returns_series.empty or returns_series.std() == 0:
            return {
                'volatility': 0,
                'sharpe': 0,
                'max_drawdown': 0,
                'total_return': 0,
                'cumulative_returns': pd.Series(dtype=float)
            }

        # Calculate cumulative returns for drawdown
        cumulative = (1 + returns_series).cumprod()

        # Calculate maximum drawdown
        rolling_max = cumulative.cummax()
        drawdown = (cumulative / rolling_max - 1)
        max_drawdown = drawdown.min()

        return {
            'volatility': returns_series.std() * np.sqrt(252),  # Annualized
            'sharpe': (returns_series.mean() / returns_series.std() * np.sqrt(252)) if returns_series.std() != 0 else 0,
            'max_drawdown': max_drawdown,
            'total_return': cumulative.iloc[-1] - 1 if len(cumulative) > 0 else 0,
            'cumulative_returns': cumulative - 1
        }

    @staticmethod
    def calculate_portfolio_value(holdings_df):
        """Calculate portfolio value from holdings DataFrame"""
        holdings_df['current_value'] = holdings_df['quantity'] * holdings_df['last_price']
        holdings_df['investment'] = holdings_df['quantity'] * holdings_df['average_price']
        holdings_df['return_%'] = ((holdings_df['last_price'] - holdings_df['average_price']) / holdings_df['average_price'] * 100).round(2)

        total_value = holdings_df['current_value'].sum()
        holdings_df['allocation_%'] = (holdings_df['current_value'] / total_value * 100).round(2)

        return holdings_df

    @staticmethod
    def format_currency(value):
        """Format currency values for display"""
        return f"₹{value:,.0f}"

    @staticmethod
    def format_percentage(value):
        """Format percentage values for display"""
        return f"{value:.1f}%"
