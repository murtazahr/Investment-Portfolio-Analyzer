from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

@dataclass
class Holding:
    """Individual stock holding data"""
    tradingsymbol: str
    quantity: int
    average_price: float
    last_price: float
    pnl: float
    close_price: float
    instrument_token: Optional[str] = None
    current_value: float = 0
    investment: float = 0
    return_percentage: float = 0
    allocation_percentage: float = 0
    day_change: float = 0  # Net change from previous close
    day_change_percentage: float = 0  # Percentage change from previous close
    day_pnl: float = 0  # P&L impact from day change
    real_time_price: float = 0  # Real-time price from market quotes
    previous_close: float = 0  # Previous day's closing price

@dataclass
class PortfolioSummary:
    """Portfolio summary data"""
    total_value: float
    total_investment: float
    total_pnl: float
    total_return_percentage: float
    holdings: List[Holding]
    total_day_change: float = 0  # Added for total 1-day change
    total_day_change_percentage: float = 0  # Added for total 1-day percentage change
    total_day_pnl: float = 0  # Added for total 1-day P&L impact

@dataclass
class PerformanceMetrics:
    """Performance metrics data"""
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    cumulative_returns: pd.Series