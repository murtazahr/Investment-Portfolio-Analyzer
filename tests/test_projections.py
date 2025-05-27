"""
Unit tests for portfolio projection functionality
"""

import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.projections import (
    PortfolioProjector,
    ProjectionResults,
    ScenarioResult
)


class TestPortfolioProjector(unittest.TestCase):
    """Test cases for PortfolioProjector class"""

    def setUp(self):
        """Set up test fixtures"""
        self.projector = PortfolioProjector(risk_free_rate=0.0625)  # 6.25% RBI repo rate
        self.test_portfolio_value = 1000000  # 10 lakhs

    def test_initialization(self):
        """Test projector initialization"""
        self.assertEqual(self.projector.risk_free_rate, 0.0625)

        # Test with custom risk-free rate
        custom_projector = PortfolioProjector(risk_free_rate=0.07)
        self.assertEqual(custom_projector.risk_free_rate, 0.07)

    def test_parametric_monte_carlo_basic(self):
        """Test basic parametric Monte Carlo simulation"""
        results = self.projector.monte_carlo_projection(
            current_value=self.test_portfolio_value,
            expected_return=0.13,  # 13% - Nifty historical
            volatility=0.21,  # 21% - India VIX average
            years=5,
            simulations=1000,
            method='parametric',
            random_seed=42
        )

        # Check results structure
        self.assertIsInstance(results, ProjectionResults)
        self.assertEqual(results.projection_years, 5)
        self.assertEqual(results.simulations, 1000)
        self.assertEqual(results.initial_value, self.test_portfolio_value)

        # Check percentiles exist and are ordered correctly
        self.assertLess(results.percentiles[5], results.percentiles[25])
        self.assertLess(results.percentiles[25], results.percentiles[50])
        self.assertLess(results.percentiles[50], results.percentiles[75])
        self.assertLess(results.percentiles[75], results.percentiles[95])

        # Check that results are reasonable
        self.assertGreater(results.expected_return, 0)  # Should have positive expected return
        self.assertLess(results.probability_of_loss, 0.5)  # Should have <50% chance of loss
        self.assertGreater(results.var_95, 0)  # VaR should be positive
        self.assertLessEqual(results.cvar_95, results.var_95)  # CVaR <= VaR

    def test_historical_monte_carlo(self):
        """Test historical Monte Carlo simulation"""
        # Create sample historical returns (simulating Indian market volatility)
        np.random.seed(42)
        historical_returns = pd.Series(
            np.random.normal(0.13/252, 0.21/np.sqrt(252), 252*3)  # 3 years of daily returns with Indian market params
        )

        results = self.projector.monte_carlo_projection(
            current_value=self.test_portfolio_value,
            historical_returns=historical_returns,
            years=5,
            simulations=1000,
            method='historical',
            random_seed=42
        )

        # Check results
        self.assertIsInstance(results, ProjectionResults)
        self.assertEqual(results.projection_years, 5)
        self.assertGreater(results.percentiles[50], 0)

    def test_invalid_inputs(self):
        """Test error handling for invalid inputs"""
        # Test negative portfolio value
        with self.assertRaises(ValueError):
            self.projector.monte_carlo_projection(
                current_value=-1000,
                expected_return=0.08,
                volatility=0.15,
                years=5,
                simulations=1000
            )

        # Test missing parameters for parametric method
        with self.assertRaises(ValueError):
            self.projector.monte_carlo_projection(
                current_value=self.test_portfolio_value,
                expected_return=None,
                volatility=0.15,
                years=5,
                simulations=1000,
                method='parametric'
            )

        # Test missing historical data for historical method
        with self.assertRaises(ValueError):
            self.projector.monte_carlo_projection(
                current_value=self.test_portfolio_value,
                historical_returns=None,
                years=5,
                simulations=1000,
                method='historical'
            )

    def test_scenario_analysis(self):
        """Test scenario analysis functionality"""
        scenarios = self.projector.scenario_analysis(
            current_value=self.test_portfolio_value,
            years=5
        )

        # Check that we get 4 default scenarios
        self.assertEqual(len(scenarios), 4)

        # Check scenario structure
        for scenario in scenarios:
            self.assertIsInstance(scenario, ScenarioResult)
            self.assertIn('Market', scenario.name)  # All default scenarios have 'Market' in name
            self.assertIsNotNone(scenario.description)
            self.assertIsNotNone(scenario.expected_return)
            self.assertIsNotNone(scenario.expected_volatility)
            self.assertGreater(scenario.projected_value, 0)
            self.assertGreaterEqual(scenario.probability_of_loss, 0)
            self.assertLessEqual(scenario.probability_of_loss, 1)

        # Check that scenarios are ordered by return (bull > base > bear > crash)
        returns = [s.expected_return for s in scenarios]
        self.assertEqual(returns, sorted(returns, reverse=True))

    def test_fire_calculations(self):
        """Test FIRE number calculations"""
        fire_results = self.projector.calculate_fire_number(
            annual_expenses=500000,  # 5 lakhs
            current_age=30,
            retirement_age=45,
            life_expectancy=90,
            inflation_rate=0.046,  # 4.6% India inflation
            withdrawal_rate=0.03   # 3% SWR for India
        )

        # Check results structure
        required_keys = [
            'fire_number', 'annual_expenses_today', 'annual_expenses_at_retirement',
            'years_to_retirement', 'retirement_years', 'total_retirement_needs'
        ]
        for key in required_keys:
            self.assertIn(key, fire_results)

        # Check calculations
        self.assertEqual(fire_results['years_to_retirement'], 15)
        self.assertEqual(fire_results['retirement_years'], 45)
        self.assertGreater(fire_results['annual_expenses_at_retirement'],
                           fire_results['annual_expenses_today'])
        self.assertGreater(fire_results['fire_number'], 0)

        # FIRE number should be expenses / withdrawal rate
        expected_fire = fire_results['annual_expenses_at_retirement'] / 0.03
        self.assertAlmostEqual(fire_results['fire_number'], expected_fire, places=2)

    def test_required_savings_calculation(self):
        """Test required savings calculations"""
        # Test when already have enough
        savings_results = self.projector.calculate_required_savings(
            current_value=5000000,  # 50 lakhs
            target_value=3000000,   # 30 lakhs
            years=10,
            expected_return=0.13  # 13% Nifty returns
        )

        self.assertEqual(savings_results['monthly_savings_needed'], 0)
        self.assertIn('surplus', savings_results)

        # Test when need to save
        savings_results = self.projector.calculate_required_savings(
            current_value=1000000,   # 10 lakhs
            target_value=10000000,   # 1 crore
            years=10,
            expected_return=0.13  # 13% Nifty returns
        )

        self.assertGreater(savings_results['monthly_savings_needed'], 0)
        self.assertIn('gap', savings_results)
        self.assertEqual(savings_results['current_value'], 1000000)
        self.assertEqual(savings_results['target_value'], 10000000)

    def test_projection_results_serialization(self):
        """Test that ProjectionResults can be serialized"""
        results = self.projector.monte_carlo_projection(
            current_value=self.test_portfolio_value,
            expected_return=0.08,
            volatility=0.15,
            years=5,
            simulations=100,  # Small number for speed
            method='parametric'
        )

        # Convert to dict
        results_dict = results.to_dict()

        # Check that all important fields are present
        self.assertIn('percentiles', results_dict)
        self.assertIn('expected_return', results_dict)
        self.assertIn('probability_of_loss', results_dict)
        self.assertIn('var_95', results_dict)
        self.assertIn('cvar_95', results_dict)

        # Check that values are serializable (no numpy arrays)
        import json
        json_str = json.dumps(results_dict)
        self.assertIsInstance(json_str, str)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Test with zero volatility
        results = self.projector.monte_carlo_projection(
            current_value=self.test_portfolio_value,
            expected_return=0.05,
            volatility=0.0,  # No volatility
            years=5,
            simulations=100,
            method='parametric'
        )

        # With zero volatility, all outcomes should be the same
        self.assertAlmostEqual(results.percentiles[5], results.percentiles[95], places=2)
        self.assertEqual(results.probability_of_loss, 0)

        # Test with very short time horizon
        results = self.projector.monte_carlo_projection(
            current_value=self.test_portfolio_value,
            expected_return=0.08,
            volatility=0.15,
            years=1,
            simulations=1000,
            method='parametric'
        )

        self.assertEqual(results.projection_years, 1)

        # Test retirement calculations with edge cases
        with self.assertRaises(ValueError):
            self.projector.calculate_fire_number(
                annual_expenses=500000,
                current_age=50,
                retirement_age=45,  # Retirement age less than current age
                life_expectancy=90
            )


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for realistic scenarios"""

    def setUp(self):
        self.projector = PortfolioProjector()

    def test_young_investor_scenario(self):
        """Test scenario for a young investor with long time horizon"""
        # 25 year old with 10 lakhs, planning for 40 years
        results = self.projector.monte_carlo_projection(
            current_value=1000000,
            expected_return=0.15,  # 15% - Higher for equity-heavy portfolio in India
            volatility=0.25,       # 25% - Higher volatility for Indian equities
            years=40,
            simulations=5000
        )

        # With 40 years in Indian markets, should have very high expected value
        self.assertGreater(results.percentiles[50], 50000000)  # Should exceed 5 crores
        self.assertLess(results.probability_of_loss, 0.05)     # Very low chance of loss

    def test_near_retirement_scenario(self):
        """Test scenario for someone near retirement"""
        # 55 year old with 1 crore, planning for 5 years
        results = self.projector.monte_carlo_projection(
            current_value=10000000,
            expected_return=0.08,   # 8% - Lower for debt-heavy portfolio
            volatility=0.10,        # 10% - Lower volatility for conservative portfolio
            years=5,
            simulations=5000
        )

        # Should have moderate growth with low risk
        self.assertLess(results.probability_of_loss, 0.10)
        self.assertGreater(results.expected_return, 0.06)


if __name__ == '__main__':
    unittest.main()
    