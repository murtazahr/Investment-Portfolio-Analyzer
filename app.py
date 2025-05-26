from datetime import datetime, timedelta
from functools import wraps

import numpy as np
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
import requests
from flask import Flask, redirect, request, url_for

app = Flask(__name__)

API_KEY = 'f94093c1-ed94-4ee0-8519-6017bffa9bc8'
API_SECRET = 'ay8014g0iq'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

AUTH_URL = f"https://api.upstox.com/v2/login/authorization/dialog?client_id={API_KEY}&redirect_uri={REDIRECT_URI}&response_type=code"
TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"

access_token = None
holdings_cache = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global access_token
        if not access_token:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def calculate_metrics(returns_series):
    """Calculate financial metrics for a returns series"""
    if returns_series.empty or returns_series.std() == 0:
        return {
            'volatility': 0,
            'sharpe': 0,
            'max_drawdown': 0,
            'total_return': 0
        }

    # Calculate cumulative returns for drawdown
    cumulative = (1 + returns_series).cumprod()

    return {
        'volatility': returns_series.std() * np.sqrt(252),
        'sharpe': (returns_series.mean() / returns_series.std() * np.sqrt(252)),
        'max_drawdown': (cumulative / cumulative.cummax() - 1).min(),
        'total_return': cumulative.iloc[-1] - 1 if len(cumulative) > 0 else 0
    }

@app.route('/')
def home():
    global access_token
    if not access_token:
        return '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Portfolio Dashboard</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <style>
                body {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                }
                .hero-section {
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .hero-card {
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    padding: 3rem;
                    text-align: center;
                    max-width: 500px;
                }
                .btn-primary {
                    background: linear-gradient(45deg, #667eea, #764ba2);
                    border: none;
                    border-radius: 50px;
                    padding: 12px 30px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    transition: all 0.3s ease;
                }
                .btn-primary:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                }
            </style>
        </head>
        <body>
            <div class="hero-section">
                <div class="hero-card">
                    <i class="fas fa-chart-line fa-4x text-primary mb-4"></i>
                    <h1 class="display-4 mb-3">Portfolio Dashboard</h1>
                    <p class="lead mb-4">Connect your Upstox account to analyze your investment performance</p>
                    <a href="/login" class="btn btn-primary btn-lg">
                        <i class="fas fa-sign-in-alt me-2"></i>Connect with Upstox
                    </a>
                </div>
            </div>
        </body>
        </html>
        '''

    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .navbar {
                background: rgba(255, 255, 255, 0.95) !important;
                backdrop-filter: blur(10px);
                box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            }
            .dashboard-card {
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                border: none;
            }
            .dashboard-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            }
            .card-icon {
                width: 70px;
                height: 70px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 1rem;
                font-size: 2rem;
            }
            .performance-icon {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
            }
            .holdings-icon {
                background: linear-gradient(45deg, #f093fb, #f5576c);
                color: white;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-light">
            <div class="container">
                <a class="navbar-brand fw-bold" href="/">
                    <i class="fas fa-chart-line me-2"></i>Portfolio Dashboard
                </a>
            </div>
        </nav>
        
        <div class="container my-5">
            <div class="row justify-content-center">
                <div class="col-md-6 mb-4">
                    <div class="card dashboard-card h-100">
                        <div class="card-body text-center p-4">
                            <div class="card-icon performance-icon">
                                <i class="fas fa-chart-area"></i>
                            </div>
                            <h4 class="card-title">Performance Analysis</h4>
                            <p class="card-text text-muted">Analyze cumulative returns, volatility, and compare against Nifty 50 benchmark</p>
                            <a href="/portfolio" class="btn btn-primary">
                                <i class="fas fa-chart-line me-2"></i>View Performance
                            </a>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card dashboard-card h-100">
                        <div class="card-body text-center p-4">
                            <div class="card-icon holdings-icon">
                                <i class="fas fa-pie-chart"></i>
                            </div>
                            <h4 class="card-title">Holdings Summary</h4>
                            <p class="card-text text-muted">View asset allocation, individual stock performance, and detailed portfolio breakdown</p>
                            <a href="/summary" class="btn btn-primary">
                                <i class="fas fa-list me-2"></i>View Holdings
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/login')
def login():
    return redirect(AUTH_URL)

@app.route('/callback')
def callback():
    global access_token
    code = request.args.get('code')
    if not code:
        return "Authorization failed."

    response = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "code": code,
            "client_id": API_KEY,
            "client_secret": API_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
    )

    if response.status_code != 200:
        return f"Token exchange failed: {response.text}"

    access_token = response.json()['access_token']
    return redirect('/')

@app.route('/summary')
@login_required
def summary():
    global access_token
    headers = {"Authorization": f"Bearer {access_token}"}
    holdings_resp = requests.get("https://api.upstox.com/v2/portfolio/long-term-holdings", headers=headers)

    if holdings_resp.status_code != 200:
        return f"Failed to fetch holdings: {holdings_resp.text}"

    holdings = holdings_resp.json().get('data', [])
    if not holdings:
        return "No holdings found."

    df = pd.DataFrame(holdings)
    df = df[['tradingsymbol', 'quantity', 'average_price', 'last_price', 'pnl', 'close_price']].copy()
    df['current_value'] = df['quantity'] * df['last_price']
    df['investment'] = df['quantity'] * df['average_price']
    df['return_%'] = ((df['last_price'] - df['average_price']) / df['average_price'] * 100).round(2)
    total_value = df['current_value'].sum()
    total_investment = df['investment'].sum()
    total_pnl = df['pnl'].sum()
    df['allocation_%'] = (df['current_value'] / total_value * 100).round(2)

    # Create enhanced visualizations
    colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7']

    # Pie chart with custom colors
    pie_fig = go.Figure(data=[go.Pie(
        labels=df['tradingsymbol'],
        values=df['current_value'],
        hole=0.4,
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Value: ₹%{value:,.0f}<br>Percentage: %{percent}<extra></extra>',
        marker=dict(colors=colors[:len(df)], line=dict(color='white', width=2))
    )])
    pie_fig.update_layout(
        title_text='Asset Allocation',
        height=500,
        font=dict(size=12),
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05)
    )
    pie_html = pio.to_html(pie_fig, full_html=False)

    # Enhanced bar chart
    bar_fig = go.Figure([go.Bar(
        x=df['tradingsymbol'],
        y=df['return_%'],
        marker_color=np.where(df['return_%'] >= 0, '#28a745', '#dc3545'),
        hovertemplate='<b>%{x}</b><br>Return: %{y:.1f}%<extra></extra>',
        text=df['return_%'].round(1).astype(str) + '%',
        textposition='outside'
    )])
    bar_fig.update_layout(
        title_text='Individual Stock Performance',
        yaxis_title='Return (%)',
        xaxis_title='Stock',
        height=500,
        font=dict(size=12),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    bar_fig.update_yaxes(gridcolor='rgba(0,0,0,0.1)')
    bar_html = pio.to_html(bar_fig, full_html=False)

    # Format table data
    df_display = df.copy()
    df_display['current_value'] = df_display['current_value'].apply(lambda x: f"₹{x:,.0f}")
    df_display['investment'] = df_display['investment'].apply(lambda x: f"₹{x:,.0f}")
    df_display['pnl'] = df_display['pnl'].apply(lambda x: f"₹{x:,.0f}")
    df_display['return_%'] = df_display['return_%'].apply(lambda x: f"{x:.1f}%")
    df_display['allocation_%'] = df_display['allocation_%'].apply(lambda x: f"{x:.1f}%")

    html_table = df_display.to_html(index=False, classes='dataframe table table-hover', border=0)

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Summary</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            .navbar {{
                background: rgba(255, 255, 255, 0.95) !important;
                backdrop-filter: blur(10px);
                box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            }}
            .metrics-card {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                border: none;
                transition: all 0.3s ease;
            }}
            .metrics-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 15px 35px rgba(0,0,0,0.15);
            }}
            .metric-value {{
                font-size: 2rem;
                font-weight: 700;
                margin: 0;
            }}
            .metric-label {{
                color: #6c757d;
                font-size: 0.9rem;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .chart-container {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                padding: 2rem;
                margin: 2rem 0;
            }}
            .table-container {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .table {{
                margin: 0;
            }}
            .table th {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 0.8rem;
                padding: 1rem;
            }}
            .table td {{
                padding: 1rem;
                vertical-align: middle;
                border-color: rgba(0,0,0,0.05);
            }}
            .positive {{ color: #28a745; font-weight: 600; }}
            .negative {{ color: #dc3545; font-weight: 600; }}
            .btn-custom {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                border: none;
                border-radius: 50px;
                padding: 10px 25px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                transition: all 0.3s ease;
            }}
            .btn-custom:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                background: linear-gradient(45deg, #5a67d8, #6b46c1);
            }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-light">
            <div class="container">
                <a class="navbar-brand fw-bold" href="/">
                    <i class="fas fa-chart-line me-2"></i>Portfolio Dashboard
                </a>
            </div>
        </nav>

        <div class="container my-4">
            <h2 class="mb-4 text-center">
                <i class="fas fa-pie-chart me-2"></i>Portfolio Summary
            </h2>
            
            <!-- Key Metrics -->
            <div class="row mb-4">
                <div class="col-md-4 mb-3">
                    <div class="card metrics-card h-100">
                        <div class="card-body text-center">
                            <div class="metric-label">Total Portfolio Value</div>
                            <div class="metric-value text-primary">₹{total_value:,.0f}</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-3">
                    <div class="card metrics-card h-100">
                        <div class="card-body text-center">
                            <div class="metric-label">Total Investment</div>
                            <div class="metric-value text-info">₹{total_investment:,.0f}</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-3">
                    <div class="card metrics-card h-100">
                        <div class="card-body text-center">
                            <div class="metric-label">Total P&L</div>
                            <div class="metric-value {'text-success' if total_pnl >= 0 else 'text-danger'}">
                                ₹{total_pnl:,.0f}
                            </div>
                            <small class="{'text-success' if total_pnl >= 0 else 'text-danger'}">
                                ({((total_pnl/total_investment)*100):+.1f}%)
                            </small>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Charts -->
            <div class="row">
                <div class="col-lg-6">
                    <div class="chart-container">
                        <h5 class="text-center mb-3">
                            <i class="fas fa-chart-pie me-2"></i>Asset Allocation
                        </h5>
                        {pie_html}
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="chart-container">
                        <h5 class="text-center mb-3">
                            <i class="fas fa-chart-bar me-2"></i>Individual Performance
                        </h5>
                        {bar_html}
                    </div>
                </div>
            </div>
            
            <!-- Detailed Table -->
            <div class="table-container">
                <h5 class="p-3 mb-0">
                    <i class="fas fa-table me-2"></i>Detailed Holdings
                </h5>
                {html_table}
            </div>
            
            <!-- Action Buttons -->
            <div class="text-center mt-4">
                <a href="/portfolio" class="btn btn-custom me-3">
                    <i class="fas fa-chart-area me-2"></i>Performance Analysis
                </a>
                <form action="/refresh" method="post" style="display: inline-block;">
                    <button type="submit" class="btn btn-outline-secondary">
                        <i class="fas fa-sync-alt me-2"></i>Refresh Data
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/portfolio')
@login_required
def portfolio():
    global access_token, holdings_cache
    start_param = request.args.get('start')
    end_param = request.args.get('end')

    # Date handling with validation
    end_date = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    if end_param:
        try:
            end_date = datetime.strptime(end_param, '%Y-%m-%d')
        except ValueError:
            return "Invalid end date format. Use YYYY-MM-DD", 400

    start_date = end_date - timedelta(days=30)
    if start_param:
        try:
            start_date = datetime.strptime(start_param, '%Y-%m-%d')
        except ValueError:
            return "Invalid start date format. Use YYYY-MM-DD", 400

    # Ensure proper date ordering
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch holdings if not cached
    if not holdings_cache:
        holdings_resp = requests.get("https://api.upstox.com/v2/portfolio/long-term-holdings", headers=headers)
        if holdings_resp.status_code != 200:
            return f"Failed to fetch holdings: {holdings_resp.text}"
        holdings_cache = holdings_resp.json().get('data', [])
        if not holdings_cache:
            return "No holdings found in portfolio"

    returns_df = pd.DataFrame()
    benchmark_returns = pd.Series(dtype=float)

    print(f"Processing {len(holdings_cache)} holdings")

    # Enhanced Benchmark data (Nifty 50)
    BENCHMARK_ID = 'NSE_INDEX|Nifty 50'
    benchmark_metrics = None
    try:
        bench_resp = requests.get(
            f"https://api.upstox.com/v3/historical-candle/{BENCHMARK_ID}/days/1/{end_date.date()}/{start_date.date()}",
            headers=headers
        )
        if bench_resp.status_code == 200:
            bench_data = bench_resp.json().get('data', {})
            if 'candles' in bench_data:
                bench_df = pd.DataFrame(bench_data['candles'],
                                        columns=['date', 'open', 'high', 'low', 'close', 'volume', 'unknown'])
                bench_df['date'] = pd.to_datetime(bench_df['date'])
                bench_df.set_index('date', inplace=True)
                bench_df.sort_index(inplace=True)
                benchmark_returns = bench_df['close'].pct_change().fillna(0)
                benchmark_metrics = calculate_metrics(benchmark_returns)
                print("Successfully fetched benchmark data")
    except Exception as e:
        print(f"Error fetching benchmark data: {str(e)}")

    # Process each holding (same as before)
    for holding in holdings_cache:
        symbol = holding.get('tradingsymbol', 'Unknown')
        qty = holding.get('quantity', 0)
        instrument_key = holding.get('instrument_token')

        if not instrument_key:
            print(f"Skipping {symbol} - missing instrument key")
            continue

        try:
            hist_url = f"https://api.upstox.com/v3/historical-candle/{instrument_key}/days/1/{end_date.date()}/{start_date.date()}"
            print(f"Fetching data for {symbol} from {hist_url}")

            hist_resp = requests.get(hist_url, headers=headers)
            hist_resp.raise_for_status()

            hist_data = hist_resp.json().get('data', {})
            candles = hist_data.get('candles', [])

            if not candles:
                print(f"No candle data found for {symbol}")
                continue

            df = pd.DataFrame(candles,
                              columns=['date', 'open', 'high', 'low', 'close', 'volume', 'unknown'])
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            df = df[~df.index.duplicated()]
            df[symbol] = df['close'] * qty

            if returns_df.empty:
                returns_df = df[[symbol]]
            else:
                returns_df = returns_df.join(df[[symbol]], how='outer')

            print(f"Added data for {symbol} with {len(df)} records")

        except requests.exceptions.HTTPError as e:
            print(f"HTTP error for {symbol} ({instrument_key}): {e.response.status_code} - {e.response.text[:200]}")
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

    if returns_df.empty:
        return f'''
        <div class="alert alert-warning">
            <h4>No Historical Data Found</h4>
            <p>Possible reasons:</p>
            <ul>
                <li>New holdings with no trading history</li>
                <li>Market holidays in selected date range</li>
                <li>Insufficient data permissions (check Upstox API access)</li>
            </ul>
            <p>Debug info:</p>
            <ul>
                <li>Date range: {start_date.date()} to {end_date.date()}</li>
                <li>Holdings processed: {len(holdings_cache)}</li>
            </ul>
            <a href="/" class="btn btn-secondary">Back to Dashboard</a>
        </div>
        '''

    # Data processing
    returns_df = returns_df.sort_index()
    returns_df = returns_df.ffill().fillna(0)
    returns_df['Portfolio Value'] = returns_df.sum(axis=1)
    portfolio_returns = returns_df['Portfolio Value'].pct_change().fillna(0)

    # Calculate portfolio metrics
    portfolio_metrics = calculate_metrics(portfolio_returns)

    # Calculate cumulative returns
    cumulative_returns = (1 + portfolio_returns).cumprod() - 1

    # Create enhanced visualization
    fig = go.Figure()

    # Portfolio line
    fig.add_trace(go.Scatter(
        x=cumulative_returns.index,
        y=cumulative_returns * 100,  # Convert to percentage
        mode='lines',
        name='Your Portfolio',
        line=dict(width=3, color='#667eea'),
        hovertemplate='<b>Portfolio</b><br>Date: %{x}<br>Cumulative Return: %{y:.2f}%<extra></extra>'
    ))

    # Benchmark line
    if not benchmark_returns.empty:
        benchmark_cumulative = (1 + benchmark_returns).cumprod() - 1
        fig.add_trace(go.Scatter(
            x=benchmark_cumulative.index,
            y=benchmark_cumulative * 100,  # Convert to percentage
            mode='lines',
            name='Nifty 50 (Benchmark)',
            line=dict(dash='dot', width=2, color='#f5576c'),
            hovertemplate='<b>Nifty 50</b><br>Date: %{x}<br>Cumulative Return: %{y:.2f}%<extra></extra>'
        ))

    fig.update_layout(
        title='Cumulative Returns: Portfolio vs Benchmark',
        xaxis_title='Date',
        yaxis_title='Cumulative Return (%)',
        template='plotly_white',
        hovermode='x unified',
        height=500,
        font=dict(size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    plot_html = pio.to_html(fig, full_html=False)

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Performance</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            .navbar {{
                background: rgba(255, 255, 255, 0.95) !important;
                backdrop-filter: blur(10px);
                box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            }}
            .metrics-card {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                border: none;
                transition: all 0.3s ease;
                height: 100%;
            }}
            .metrics-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 15px 35px rgba(0,0,0,0.15);
            }}
            .metric-value {{
                font-size: 1.8rem;
                font-weight: 700;
                margin: 0;
            }}
            .metric-label {{
                color: #6c757d;
                font-size: 0.85rem;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 0.5rem;
            }}
            .chart-container {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                padding: 2rem;
                margin: 2rem 0;
            }}
            .date-form {{
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                padding: 1.5rem;
            }}
            .btn-custom {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                border: none;
                border-radius: 50px;
                padding: 8px 20px;
                font-weight: 600;
                color: white;
                transition: all 0.3s ease;
            }}
            .btn-custom:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 16px rgba(0,0,0,0.2);
                background: linear-gradient(45deg, #5a67d8, #6b46c1);
                color: white;
            }}
            .btn-outline-custom {{
                border: 2px solid #667eea;
                color: #667eea;
                border-radius: 50px;
                padding: 6px 15px;
                font-weight: 600;
                transition: all 0.3s ease;
            }}
            .btn-outline-custom:hover {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                transform: translateY(-1px);
            }}
            .comparison-section {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 15px;
                padding: 2rem;
                margin: 2rem 0;
            }}
            .vs-badge {{
                background: rgba(255,255,255,0.2);
                backdrop-filter: blur(10px);
                border-radius: 50px;
                padding: 0.5rem 1rem;
                font-weight: 600;
                text-align: center;
            }}
            .help-tooltip {{
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 10px;
                padding: 1rem;
                margin-top: 1rem;
                font-size: 0.9rem;
            }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-light">
            <div class="container">
                <a class="navbar-brand fw-bold" href="/">
                    <i class="fas fa-chart-line me-2"></i>Portfolio Dashboard
                </a>
            </div>
        </nav>

        <div class="container my-4">
            <h2 class="mb-4 text-center">
                <i class="fas fa-chart-area me-2"></i>Portfolio Performance Analysis
            </h2>
            
            <!-- Date Selection Form -->
            <div class="date-form mb-4">
                <form method="GET" action="/portfolio">
                    <div class="row g-3 align-items-end">
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">
                                <i class="fas fa-calendar-alt me-1"></i>Start Date
                            </label>
                            <input type="date" name="start" value="{start_date.date()}" class="form-control">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">
                                <i class="fas fa-calendar-alt me-1"></i>End Date
                            </label>
                            <input type="date" name="end" value="{end_date.date()}" class="form-control">
                        </div>
                        <div class="col-md-6">
                            <button type="submit" class="btn btn-custom me-2">
                                <i class="fas fa-sync me-1"></i>Update
                            </button>
                            <div class="btn-group">
                                <a href="/portfolio?start={(end_date - timedelta(days=30)).date()}&end={end_date.date()}" 
                                   class="btn btn-outline-custom btn-sm">1M</a>
                                <a href="/portfolio?start={(end_date - timedelta(days=90)).date()}&end={end_date.date()}" 
                                   class="btn btn-outline-custom btn-sm">3M</a>
                                <a href="/portfolio?start={(end_date - timedelta(days=180)).date()}&end={end_date.date()}" 
                                   class="btn btn-outline-custom btn-sm">6M</a>
                                <a href="/portfolio?start={(end_date - timedelta(days=365)).date()}&end={end_date.date()}" 
                                   class="btn btn-outline-custom btn-sm">1Y</a>
                            </div>
                        </div>
                    </div>
                </form>
            </div>

            <!-- Performance Comparison Section -->
            <div class="comparison-section">
                <div class="row text-center">
                    <div class="col-md-5">
                        <h5><i class="fas fa-user me-2"></i>Your Portfolio</h5>
                        <div class="row mt-3">
                            <div class="col-6">
                                <div class="metric-label text-white-50">Total Return</div>
                                <div class="metric-value">
                                    {portfolio_metrics['total_return']*100:+.2f}%
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="metric-label text-white-50">Volatility</div>
                                <div class="metric-value">
                                    {portfolio_metrics['volatility']*100:.1f}%
                                </div>
                            </div>
                            <div class="col-6 mt-2">
                                <div class="metric-label text-white-50">Sharpe Ratio</div>
                                <div class="metric-value">
                                    {portfolio_metrics['sharpe']:.2f}
                                </div>
                            </div>
                            <div class="col-6 mt-2">
                                <div class="metric-label text-white-50">Max Drawdown</div>
                                <div class="metric-value">
                                    {portfolio_metrics['max_drawdown']*100:.1f}%
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-2 d-flex align-items-center justify-content-center">
                        <div class="vs-badge">
                            <i class="fas fa-balance-scale fa-2x"></i>
                            <div class="mt-2">VS</div>
                        </div>
                    </div>
                    
                    <div class="col-md-5">
                        <h5><i class="fas fa-chart-line me-2"></i>Nifty 50 Benchmark</h5>
                        <div class="row mt-3">
                            {"" if not benchmark_metrics else f'''
                            <div class="col-6">
                                <div class="metric-label text-white-50">Total Return</div>
                                <div class="metric-value">
                                    {benchmark_metrics['total_return']*100:+.2f}%
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="metric-label text-white-50">Volatility</div>
                                <div class="metric-value">
                                    {benchmark_metrics['volatility']*100:.1f}%
                                </div>
                            </div>
                            <div class="col-6 mt-2">
                                <div class="metric-label text-white-50">Sharpe Ratio</div>
                                <div class="metric-value">
                                    {benchmark_metrics['sharpe']:.2f}
                                </div>
                            </div>
                            <div class="col-6 mt-2">
                                <div class="metric-label text-white-50">Max Drawdown</div>
                                <div class="metric-value">
                                    {benchmark_metrics['max_drawdown']*100:.1f}%
                                </div>
                            </div>
                            '''}
                        </div>
                        {"<div class='text-white-50 mt-3'><i class='fas fa-exclamation-triangle me-1'></i>Benchmark data unavailable</div>" if not benchmark_metrics else ""}
                    </div>
                </div>
                
                <!-- Help Section -->
                <div class="help-tooltip">
                    <h6><i class="fas fa-info-circle me-2"></i>How to Read This Chart:</h6>
                    <ul class="mb-0">
                        <li><strong>Y-axis shows cumulative returns (%)</strong> - Total percentage gain/loss since start date</li>
                        <li><strong>Total Return:</strong> Overall performance for the selected period</li>
                        <li><strong>Volatility:</strong> Annual price fluctuation (lower = more stable)</li>
                        <li><strong>Sharpe Ratio:</strong> Risk-adjusted returns (higher = better risk/reward)</li>
                        <li><strong>Max Drawdown:</strong> Largest peak-to-trough decline (lower = better)</li>
                    </ul>
                </div>
            </div>

            <!-- Main Chart -->
            <div class="chart-container">
                <h5 class="text-center mb-3">
                    <i class="fas fa-chart-area me-2"></i>Cumulative Returns Comparison
                </h5>
                {plot_html}
            </div>

            <!-- Navigation -->
            <div class="text-center mt-4">
                <a href="/" class="btn btn-outline-secondary me-2">
                    <i class="fas fa-home me-1"></i>Dashboard
                </a>
                <a href="/summary" class="btn btn-custom me-2">
                    <i class="fas fa-list me-1"></i>Holdings Summary
                </a>
                <form action="/refresh" method="post" style="display: inline-block;">
                    <button type="submit" class="btn btn-outline-danger">
                        <i class="fas fa-sync-alt me-1"></i>Refresh Data
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/refresh', methods=['POST'])
@login_required
def refresh():
    global holdings_cache
    holdings_cache = None
    return redirect(url_for('summary'))

if __name__ == '__main__':
    app.run(debug=True)
