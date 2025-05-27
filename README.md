# Portfolio Dashboard

A comprehensive Flask-based web application for analyzing investment portfolio performance using the Upstox API with advanced financial projections and FIRE planning capabilities.

## 🚀 Features

### Core Portfolio Analysis
- **Real-time Portfolio Summary**: Live holdings data with day-change tracking
- **Performance Analysis**: Compare portfolio returns against Nifty 50 benchmark
- **Interactive Visualizations**: Asset allocation pie charts, performance bars, and day-change tracking
- **Risk Metrics**: Volatility, Sharpe ratio, maximum drawdown calculations

### Advanced Financial Planning
- **Monte Carlo Projections**: Parametric and historical simulation methods
- **Scenario Analysis**: Bull/Bear/Crash market scenario modeling
- **FIRE Calculator**: Financial Independence Retire Early planning tool
- **Dynamic Market Parameters**: Real-time VIX integration and market sentiment analysis

### Real-time Features
- **Live Day Change Tracking**: Real-time P&L updates using market quotes API
- **Auto-refresh Functionality**: Configurable automatic data updates
- **AJAX-based Updates**: Smooth UI updates without page reloads
- **Responsive Design**: Mobile-friendly interface with modern styling

## 🏗️ Architecture

### Design Principles
- **Separation of Concerns**: Modular service-oriented architecture
- **Dependency Injection**: Loosely coupled components
- **Comprehensive Error Handling**: Graceful degradation and fallbacks
- **Smart Caching**: Optimized API usage with configurable cache timeouts
- **Testability**: Extensive unit and integration tests

### Key Components

```
portfolio_dashboard/
├── app.py                      # Main Flask application with advanced routing
├── config.py                   # Environment-based configuration management
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development and testing dependencies
├── services/
│   ├── upstox_service.py      # Upstox API integration with market quotes
│   ├── portfolio_service.py   # Portfolio calculations and caching
│   ├── auth_service.py        # OAuth 2.0 authentication
│   └── market_data_service.py # Market parameters and VIX data
├── models/
│   └── portfolio.py           # Data models with day-change support
├── utils/
│   ├── calculations.py        # Financial calculations
│   ├── projections.py         # Monte Carlo and FIRE calculations
│   └── decorators.py          # Authentication and error handling
├── templates/
│   ├── base.html              # Base template with modern UI
│   ├── dashboard.html         # Main dashboard
│   ├── summary.html           # Portfolio summary with real-time updates
│   ├── performance.html       # Performance analysis
│   ├── projections.html       # Monte Carlo projections
│   ├── fire.html              # FIRE calculator
│   └── login.html             # OAuth login page
├── static/css/
│   └── style.css              # Modern CSS with animations
├── tests/                     # Comprehensive test suite
├── docker/                    # Docker deployment configuration
└── blueprints/                # Modular Flask blueprints
```

## 📊 Advanced Analytics

### Portfolio Projections
- **Multiple Simulation Methods**: Parametric, historical bootstrap, portfolio-aware
- **Risk Analysis**: VaR, CVaR, probability of loss calculations
- **Market Integration**: Dynamic parameters from actual Nifty 50 and India VIX data
- **Scenario Planning**: Custom scenario analysis with market sentiment integration

### FIRE Planning
- **Comprehensive FIRE Calculator**: Personalized financial independence planning
- **Inflation Adjustment**: Dynamic inflation rates from market data
- **Savings Scenarios**: Multiple pathway analysis
- **Goal Tracking**: Progress monitoring with visual indicators

### Market Intelligence
- **India VIX Integration**: Real-time volatility index analysis
- **Market Sentiment**: Dynamic risk assessment based on current conditions
- **Historical Analysis**: Up to 10 years of market data integration
- **Risk-Adjusted Returns**: Sharpe ratio and risk-free rate considerations

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- Upstox Developer Account
- Modern web browser

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd portfolio_dashboard
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your Upstox API credentials
   ```

4. **Required Environment Variables**
   ```env
   UPSTOX_API_KEY=your_api_key_here
   UPSTOX_API_SECRET=your_api_secret_here
   UPSTOX_REDIRECT_URI=http://127.0.0.1:5000/callback
   SECRET_KEY=your_secret_key_here
   FLASK_ENV=development
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the dashboard**
   - Open http://127.0.0.1:5000 in your browser
   - Click "Connect with Upstox" to authenticate

## 🐳 Docker Deployment

### Using Docker Compose
```bash
cd docker/
docker-compose up -d
```

### Manual Docker Build
```bash
docker build -f docker/Dockerfile -t portfolio-dashboard .
docker run -p 5000:5000 --env-file .env portfolio-dashboard
```

## 🧪 Testing

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=. --cov-report=html
```

### Test Categories
- **Unit Tests**: Service layer, calculations, projections
- **Integration Tests**: API interactions, data flow
- **Financial Model Tests**: Projection accuracy, FIRE calculations

## 📱 API Endpoints

### Core Routes
- `GET /` - Dashboard home
- `GET /summary` - Portfolio summary with real-time data
- `GET /portfolio` - Performance analysis
- `GET /projections` - Monte Carlo projections
- `GET /fire` - FIRE calculator

### AJAX API Routes
- `POST /api/refresh_day_change` - Real-time day change updates
- `GET /api/portfolio_summary` - Current portfolio data
- `GET /api/market_data` - Current market parameters

### Authentication
- `GET /login` - Upstox OAuth initiation
- `GET /callback` - OAuth callback handler
- `GET /logout` - Session termination

## 🔧 Configuration

### Cache Settings
```python
CACHE_TIMEOUT = timedelta(minutes=15)  # Holdings cache
HISTORICAL_CACHE_TIMEOUT = timedelta(hours=1)  # Historical data cache
MARKET_PARAMS_CACHE = timedelta(hours=24)  # Market parameters cache
```

### API Endpoints
```python
UPSTOX_BASE_URL = 'https://api.upstox.com'
UPSTOX_HOLDINGS_URL = f'{UPSTOX_BASE_URL}/v2/portfolio/long-term-holdings'
UPSTOX_MARKET_QUOTES_URL = f'{UPSTOX_BASE_URL}/v2/market-quote/quotes'
UPSTOX_HISTORICAL_URL = f'{UPSTOX_BASE_URL}/v3/historical-candle'
```

## 🎯 Key Features Detail

### Real-time Day Change Tracking
- Market quotes API integration for live prices
- Automatic P&L calculations
- Color-coded gainers/losers indicators
- AJAX-based updates without page refresh

### Advanced Monte Carlo Projections
- **Portfolio-Aware Method**: Considers actual holdings and correlations
- **Historical Bootstrap**: Uses actual market return distributions
- **Parametric Method**: Normal distribution with market-derived parameters
- **Risk Metrics**: VaR, CVaR, probability analysis

### Market Intelligence Integration
- **India VIX Data**: Real-time volatility index integration
- **Dynamic Parameters**: Market-derived expected returns and volatility
- **Scenario Analysis**: Market condition-aware projections
- **Risk Assessment**: Current market sentiment analysis

## 🔒 Security Features

- **OAuth 2.0 Authentication**: Secure Upstox integration
- **Session Management**: Flask session-based user handling
- **Environment Variables**: Secure credential management
- **CSRF Protection**: Ready for Flask-WTF integration
- **Input Validation**: Comprehensive data validation

## 📈 Performance Optimizations

- **Smart Caching**: Multi-level caching strategy
- **AJAX Updates**: Partial page updates for better UX
- **Lazy Loading**: On-demand chart rendering
- **API Batching**: Efficient market quotes fetching
- **Error Resilience**: Graceful fallbacks for API failures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add comprehensive tests for new functionality
4. Ensure all tests pass (`pytest tests/`)
5. Follow code style guidelines (`black`, `flake8`)
6. Submit a pull request

### Development Setup
```bash
pip install -r requirements-dev.txt
pre-commit install  # Setup git hooks
black .  # Format code
flake8 .  # Lint code
```

## 📝 Dependencies

### Core Dependencies
- **Flask 3.1.0**: Web framework
- **pandas 2.2.3**: Data manipulation
- **numpy 2.0.1**: Numerical computations
- **plotly 6.1.1**: Interactive visualizations
- **requests 2.32.3**: HTTP client

### Development Dependencies
- **pytest 7.4.0**: Testing framework
- **black 23.7.0**: Code formatting
- **flake8 6.0.0**: Code linting
- **mypy 1.5.1**: Type checking

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors**
- Verify Upstox API credentials in `.env`
- Check redirect URI matches Upstox app configuration
- Ensure API key has required permissions

**Data Loading Issues**
- Check Upstox account has holdings
- Verify market hours (BSE/NSE trading times)
- Check API rate limits

**Performance Issues**
- Reduce Monte Carlo simulations for faster results
- Clear cache using refresh buttons
- Check network connectivity for real-time updates

## 📄 License

MIT License - see LICENSE file for details.

## 🎯 Roadmap

### Upcoming Features
- [ ] Multi-broker support (Zerodha, Angel One)
- [ ] Tax calculation and optimization
- [ ] SIP planning and tracking
- [ ] Sector allocation analysis
- [ ] Goal-based investing
- [ ] Risk profiling questionnaire
- [ ] Export functionality (PDF reports)
- [ ] Mobile app companion

### Technical Improvements
- [ ] Database integration for historical tracking
- [ ] Redis caching for production scaling
- [ ] WebSocket for real-time updates
- [ ] Advanced charting with technical indicators
- [ ] Machine learning price predictions

---

**Built with ❤️ for Indian investors**

For support, create an issue on GitHub or contact the development team.