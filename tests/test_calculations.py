import unittest

import pandas as pd

from utils.calculations import FinancialCalculator


class TestFinancialCalculator(unittest.TestCase):

    def setUp(self):
        self.calculator = FinancialCalculator()

    def test_calculate_metrics_with_valid_data(self):
        # Create sample returns data
        returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005])

        metrics = self.calculator.calculate_metrics(returns)

        # Test that all metrics are calculated
        self.assertIn('volatility', metrics)
        self.assertIn('sharpe', metrics)
        self.assertIn('max_drawdown', metrics)
        self.assertIn('total_return', metrics)

        # Test that values are reasonable
        self.assertGreater(metrics['volatility'], 0)
        self.assertIsInstance(metrics['sharpe'], float)

    def test_calculate_metrics_with_empty_data(self):
        returns = pd.Series(dtype=float)

        metrics = self.calculator.calculate_metrics(returns)

        # Should return zero metrics for empty data
        self.assertEqual(metrics['volatility'], 0)
        self.assertEqual(metrics['sharpe'], 0)
        self.assertEqual(metrics['max_drawdown'], 0)
        self.assertEqual(metrics['total_return'], 0)
