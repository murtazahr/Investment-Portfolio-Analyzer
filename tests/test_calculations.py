import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.calculations import FinancialCalculator

class TestFinancialCalculator(unittest.TestCase):

    def setUp(self):
        self.calculator = FinancialCalculator()

    def test_calculate_metrics_with_valid_data(self):
        """Test financial metrics calculation with valid data"""
        # Create sample returns data with known characteristics
        np.random.seed(42)  # For reproducible results
        returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005, -0.005, 0.008, 0.012])

        metrics = self.calculator.calculate_metrics(returns)

        # Test that all required metrics are present
        required_keys = ['volatility', 'sharpe', 'max_drawdown', 'total_return', 'cumulative_returns']
        for key in required_keys:
            self.assertIn(key, metrics)

        # Test that values are reasonable
        self.assertGreater(metrics['volatility'], 0)
        self.assertIsInstance(metrics['sharpe'], float)
        self.assertLessEqual(metrics['max_drawdown'], 0)  # Drawdown should be negative or zero
        self.assertIsInstance(metrics['total_return'], float)
        self.assertIsInstance(metrics['cumulative_returns'], pd.Series)

    def test_calculate_metrics_with_empty_data(self):
        """Test metrics calculation with empty data"""
        returns = pd.Series(dtype=float)

        metrics = self.calculator.calculate_metrics(returns)

        # Should return zero metrics for empty data
        self.assertEqual(metrics['volatility'], 0)
        self.assertEqual(metrics['sharpe'], 0)
        self.assertEqual(metrics['max_drawdown'], 0)
        self.assertEqual(metrics['total_return'], 0)
        self.assertIsInstance(metrics['cumulative_returns'], pd.Series)

    def test_calculate_metrics_with_zero_std(self):
        """Test metrics calculation when standard deviation is zero"""
        # All returns are the same (zero volatility)
        returns = pd.Series([0.01, 0.01, 0.01, 0.01])

        metrics = self.calculator.calculate_metrics(returns)

        # Should handle zero standard deviation gracefully
        self.assertEqual(metrics['volatility'], 0)
        self.assertEqual(metrics['sharpe'], 0)
        self.assertGreaterEqual(metrics['total_return'], 0)

    def test_calculate_portfolio_value(self):
        """Test portfolio value calculations"""
        # Create test holdings DataFrame
        holdings_df = pd.DataFrame({
            'quantity': [10, 5, 20],
            'last_price': [100, 200, 50],
            'average_price': [90, 180, 55],
            'pnl': [100, 100, -100]
        })

        result_df = self.calculator.calculate_portfolio_value(holdings_df)

        # Test calculated columns exist
        self.assertIn('current_value', result_df.columns)
        self.assertIn('investment', result_df.columns)
        self.assertIn('return_%', result_df.columns)
        self.assertIn('allocation_%', result_df.columns)

        # Test calculations are correct
        expected_current_values = [1000, 1000, 1000]  # quantity * last_price
        expected_investments = [900, 900, 1100]       # quantity * average_price

        for i, (current, investment) in enumerate(zip(expected_current_values, expected_investments)):
            self.assertEqual(result_df.iloc[i]['current_value'], current)
            self.assertEqual(result_df.iloc[i]['investment'], investment)

        # Test allocation percentages sum to 100
        total_allocation = result_df['allocation_%'].sum()
        self.assertAlmostEqual(total_allocation, 100.0, places=1)

    def test_format_currency(self):
        """Test currency formatting"""
        self.assertEqual(self.calculator.format_currency(1000), "₹1,000")
        self.assertEqual(self.calculator.format_currency(1000.50), "₹1,000")
        self.assertEqual(self.calculator.format_currency(1234567), "₹1,234,567")

    def test_format_percentage(self):
        """Test percentage formatting"""
        self.assertEqual(self.calculator.format_percentage(15.678), "15.7%")
        self.assertEqual(self.calculator.format_percentage(0), "0.0%")
        self.assertEqual(self.calculator.format_percentage(-5.432), "-5.4%")
        