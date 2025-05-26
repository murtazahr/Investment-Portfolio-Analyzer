import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required")

    # Upstox API Configuration
    UPSTOX_API_KEY = os.environ.get('UPSTOX_API_KEY')
    UPSTOX_API_SECRET = os.environ.get('UPSTOX_API_SECRET')
    UPSTOX_REDIRECT_URI = os.environ.get('UPSTOX_REDIRECT_URI')

    # API URLs
    UPSTOX_BASE_URL = 'https://api.upstox.com'
    UPSTOX_AUTH_URL = f'{UPSTOX_BASE_URL}/v2/login/authorization/dialog'
    UPSTOX_TOKEN_URL = f'{UPSTOX_BASE_URL}/v2/login/authorization/token'
    UPSTOX_HOLDINGS_URL = f'{UPSTOX_BASE_URL}/v2/portfolio/long-term-holdings'
    UPSTOX_HISTORICAL_URL = f'{UPSTOX_BASE_URL}/v3/historical-candle'
    UPSTOX_MARKET_QUOTES_URL = f'{UPSTOX_BASE_URL}/v2/market-quote/quotes'

    # Benchmark configuration
    BENCHMARK_SYMBOL = 'NSE_INDEX|Nifty 50'

    # Default date range
    DEFAULT_ANALYSIS_DAYS = 30

    # Cache settings
    CACHE_TIMEOUT = timedelta(minutes=15)

    # Validate required environment variables
    if not UPSTOX_API_KEY:
        raise ValueError("UPSTOX_API_KEY environment variable is required")
    if not UPSTOX_API_SECRET:
        raise ValueError("UPSTOX_API_SECRET environment variable is required")
    if not UPSTOX_REDIRECT_URI:
        raise ValueError("UPSTOX_REDIRECT_URI environment variable is required")

class DevelopmentConfig(Config):
    """Development configuration with fallbacks"""
    DEBUG = True
    # Only provide fallbacks for non-sensitive config in development
    UPSTOX_REDIRECT_URI = os.environ.get('UPSTOX_REDIRECT_URI') or 'http://127.0.0.1:5000/callback'

class ProductionConfig(Config):
    """Production configuration - no fallbacks"""
    DEBUG = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    # Use test values
    UPSTOX_API_KEY = 'test-key'
    UPSTOX_API_SECRET = 'test-secret'
    UPSTOX_REDIRECT_URI = 'http://localhost:5000/callback'

# Configuration factory
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
