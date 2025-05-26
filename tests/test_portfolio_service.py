import unittest
from unittest.mock import patch

from models.portfolio import Holding, PortfolioSummary
from services.portfolio_service import PortfolioService


class TestPortfolioService(unittest.TestCase):

    def setUp(self):
        self.portfolio_service = PortfolioService()

    @patch('services.portfolio_service.UpstoxService')
    def test_get_portfolio_summary(self, mock_upstox_service):
        # Mock holdings data
        mock_holdings = [
            Holding(
                tradingsymbol='RELIANCE',
                quantity=10,
                average_price=2000.0,
                last_price=2100.0,
                pnl=1000.0,
                close_price=2100.0
            )
        ]

        mock_upstox_service.return_value.get_holdings.return_value = mock_holdings

        # Test
        summary = self.portfolio_service.get_portfolio_summary()

        # Assertions
        self.assertIsInstance(summary, PortfolioSummary)
        self.assertEqual(len(summary.holdings), 1)
        self.assertEqual(summary.holdings[0].tradingsymbol, 'RELIANCE')