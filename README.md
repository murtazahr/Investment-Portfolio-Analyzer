# Portfolio Dashboard

A Flask-based web application for analyzing investment portfolio performance using the Upstox API.

## Features

- **Portfolio Summary**: View holdings, allocation, and P&L
- **Performance Analysis**: Compare portfolio returns against Nifty 50 benchmark
- **Interactive Charts**: Visualize cumulative returns and individual stock performance
- **Risk Metrics**: Calculate volatility, Sharpe ratio, and maximum drawdown
- **Responsive Design**: Mobile-friendly interface with modern styling

## Project Structure

```
portfolio_dashboard/
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── requirements.txt            # Dependencies
├── services/
│   ├── __init__.py
│   ├── upstox_service.py      # Upstox API interactions
│   ├── portfolio_service.py   # Portfolio calculations
│   └── auth_service.py        # Authentication logic
├── models/
│   ├── __init__.py
│   └── portfolio.py           # Data models
├── utils/
│   ├── __init__.py
│   ├── calculations.py        # Financial calculations
│   └── decorators.py          # Custom decorators
├── templates/
│   ├── base.html              # Base template
│   ├── login.html             # Login page
│   ├── dashboard.html         # Dashboard
│   ├── summary.html           # Portfolio summary
│   ├── performance.html       # Performance analysis
│   └── no_data.html          # No data page
├── static/
│   └── css/
│       └── style.css          # Custom styles
└── tests/
    ├── test_portfolio_service.py
    └── test_calculations.py
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:
   ```bash
   export UPSTOX_API_KEY="your_api_key"
   export UPSTOX_API_SECRET="your_api_secret"
   export UPSTOX_REDIRECT_URI="http://127.0.0.1:5000/callback"
   export SECRET_KEY="your_secret_key"
   ```

4. Run the application:
   ```bash
   python app.py
   ```

## Architecture

### Design Principles

1. **Separation of Concerns**: Each module has a single responsibility
2. **Dependency Injection**: Services are injected rather than instantiated
3. **Error Handling**: Comprehensive error handling with graceful degradation
4. **Caching**: Smart caching to reduce API calls
5. **Testability**: Modular design allows for easy unit testing

### Key Components

- **Services Layer**: Handles business logic and external API interactions
- **Models Layer**: Defines data structures and validation
- **Utils Layer**: Common utilities and decorators
- **Templates Layer**: Jinja2 templates with inheritance
- **Static Assets**: CSS, JS, and image files

### Security Features

- OAuth 2.0 authentication with Upstox
- Session-based user management
- CSRF protection (Flask-WTF can be added)
- Environment variable configuration for sensitive data

## API Documentation

### UpstoxService
Handles all interactions with the Upstox API including authentication and data fetching.

### PortfolioService
Main business logic layer that orchestrates portfolio calculations and analysis.

### FinancialCalculator
Utility class for financial metrics calculations including risk-adjusted returns.

## Testing

Run tests with:
```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License