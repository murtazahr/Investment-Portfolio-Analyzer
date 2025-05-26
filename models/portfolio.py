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

@dataclass
class PortfolioSummary:
    """Portfolio summary data"""
    total_value: float
    total_investment: float
    total_pnl: float
    total_return_percentage: float
    holdings: List[Holding]

@dataclass
class PerformanceMetrics:
    """Performance metrics data"""
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    cumulative_returns: pd.Series
    