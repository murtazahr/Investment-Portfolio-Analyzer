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

@app.route('/')
def home():
    global access_token
    if not access_token:
        return '<h1>Portfolio Dashboard</h1><a href="/login">Login with Upstox</a>'
    return '''
    <h1>Portfolio Dashboard</h1>
    <ul>
      <li><a href="/portfolio">Cumulative Returns</a></li>
      <li><a href="/summary">Holdings Summary</a></li>
    </ul>
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
    df['allocation_%'] = (df['current_value'] / total_value * 100).round(2)

    # Create visualizations
    pie_fig = go.Figure(data=[go.Pie(
        labels=df['tradingsymbol'],
        values=df['current_value'],
        hole=0.3,
        textinfo='percent+label',
        hoverinfo='value+percent'
    )])
    pie_fig.update_layout(title_text='Asset Allocation', height=500)
    pie_html = pio.to_html(pie_fig, full_html=False)

    bar_fig = go.Figure([go.Bar(
        x=df['tradingsymbol'],
        y=df['return_%'],
        marker_color=np.where(df['return_%'] >= 0, 'green', 'red')
    )])
    bar_fig.update_layout(
        title_text='Individual Returns (%)',
        yaxis_title='Return %',
        xaxis_title='Stock',
        height=500
    )
    bar_html = pio.to_html(bar_fig, full_html=False)

    html_table = df.to_html(index=False, classes='dataframe table table-striped table-bordered', border=0)

    return f'''
    <html>
        <head>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <style>
                body {{ padding: 20px; }}
                .chart-container {{ margin: 30px 0; }}
                .dataframe td, .dataframe th {{ text-align: center; }}
                .metrics-box {{ 
                    background: #f8f9fa;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,.1);
                }}
                .metric {{ margin: 10px 0; }}
            </style>
        </head>
        <body>
            <h2>Portfolio Summary</h2>
            <div class="metrics-box">
                <h4>Key Metrics</h4>
                <div class="row">
                    <div class="col metric">
                        <strong>Total Value:</strong> ₹{total_value:,.2f}
                    </div>
                    <div class="col metric">
                        <strong>Total P&L:</strong> ₹{df['pnl'].sum():,.2f}
                    </div>
                </div>
            </div>
            
            <div class="chart-container">
                <h4>Asset Allocation</h4>
                {pie_html}
            </div>
            
            <div class="chart-container">
                <h4>Individual Performance</h4>
                {bar_html}
            </div>
            
            <h4>Detailed Holdings</h4>
            {html_table}
            
            <div class="mt-4">
                <a href="/portfolio" class="btn btn-primary">Performance Analysis</a>
                <form action="/refresh" method="post" style="display: inline-block; margin-left: 10px;">
                    <button type="submit" class="btn btn-secondary">Refresh Data</button>
                </form>
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

    # Add debug output for holdings
    print(f"Processing {len(holdings_cache)} holdings")

    # Benchmark data (Nifty 50)
    BENCHMARK_ID = 'NSE_INDEX|Nifty 50'  # Verify this instrument key
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
                # Sort the DataFrame by date in ascending order
                bench_df.sort_index(inplace=True)
                benchmark_returns = bench_df['close'].pct_change().fillna(0)
                print("Successfully fetched benchmark data")
    except Exception as e:
        print(f"Error fetching benchmark data: {str(e)}")

    # Process each holding
    for holding in holdings_cache:
        symbol = holding.get('tradingsymbol', 'Unknown')
        qty = holding.get('quantity', 0)
        instrument_key = holding.get('instrument_token')  # Verify key name in API response

        if not instrument_key:
            print(f"Skipping {symbol} - missing instrument key")
            continue

        try:
            # Historical data API call
            hist_url = f"https://api.upstox.com/v3/historical-candle/{instrument_key}/days/1/{end_date.date()}/{start_date.date()}"
            print(f"Fetching data for {symbol} from {hist_url}")

            hist_resp = requests.get(hist_url, headers=headers)
            hist_resp.raise_for_status()  # Raises HTTPError for bad responses

            hist_data = hist_resp.json().get('data', {})
            candles = hist_data.get('candles', [])

            if not candles:
                print(f"No candle data found for {symbol}")
                continue

            # Process candle data
            df = pd.DataFrame(candles,
                              columns=['date', 'open', 'high', 'low', 'close', 'volume', 'unknown'])
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            # Sort the DataFrame by date in ascending order
            df.sort_index(inplace=True)
            df = df[~df.index.duplicated()]  # Remove duplicate dates
            df[symbol] = df['close'] * qty

            # Merge with main dataframe
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

    # Calculate metrics
    cumulative_returns = (1 + portfolio_returns).cumprod() - 1
    volatility = portfolio_returns.std() * np.sqrt(252)
    sharpe = (portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)) if portfolio_returns.std() != 0 else 0
    max_drawdown = (returns_df['Portfolio Value'] / returns_df['Portfolio Value'].cummax() - 1).min()

    # Create visualizations
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cumulative_returns.index,
        y=cumulative_returns,
        mode='lines',
        name='Portfolio',
        line=dict(width=2)
    ))

    if not benchmark_returns.empty:
        benchmark_cumulative = (1 + benchmark_returns).cumprod() - 1
    fig.add_trace(go.Scatter(
        x=benchmark_cumulative.index,
        y=benchmark_cumulative,
        mode='lines',
        name='Nifty 50',
        line=dict(dash='dot')
    ))

    fig.update_layout(
        title='Cumulative Returns vs Benchmark',
        xaxis_title='Date',
        yaxis_title='Returns',
        template='plotly_dark',
        hovermode='x unified'
    )

    # Generate HTML
    plot_html = pio.to_html(fig, full_html=False)

    return f'''
    <html>
        <head>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <style>
                .metrics-container {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; }}
                .metric-item {{ margin: 10px 0; }}
                .date-preset {{ margin-right: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="my-4">Portfolio Performance</h2>
                
                <!-- Date Selection Form -->
                <div class="card mb-4">
                    <div class="card-body">
                        <form method="GET" action="/portfolio">
                            <div class="row g-3">
                                <div class="col-md-3">
                                    <label class="form-label">Start Date</label>
                                    <input type="date" name="start" value="{start_date.date()}" class="form-control">
                                </div>
                                <div class="col-md-3">
                                    <label class="form-label">End Date</label>
                                    <input type="date" name="end" value="{end_date.date()}" class="form-control">
                                </div>
                                <div class="col-md-6 d-flex align-items-end">
                                    <button type="submit" class="btn btn-primary">Update</button>
                                    <div class="btn-group ms-3">
                                        <a href="/portfolio?start={(end_date - timedelta(days=30)).date()}&end={end_date.date()}" 
                                           class="btn btn-outline-secondary date-preset">1M</a>
                                        <a href="/portfolio?start={(end_date - timedelta(days=90)).date()}&end={end_date.date()}" 
                                           class="btn btn-outline-secondary date-preset">3M</a>
                                        <a href="/portfolio?start={(end_date - timedelta(days=365)).date()}&end={end_date.date()}" 
                                           class="btn btn-outline-secondary date-preset">1Y</a>
                                    </div>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Metrics -->
                <div class="metrics-container">
                    <div class="row">
                        <div class="col-md-4 metric-item">
                            <h5>Annual Volatility</h5>
                            <div class="display-4">{volatility*100:.1f}%</div>
                        </div>
                        <div class="col-md-4 metric-item">
                            <h5>Sharpe Ratio</h5>
                            <div class="display-4">{sharpe:.2f}</div>
                        </div>
                        <div class="col-md-4 metric-item">
                            <h5>Max Drawdown</h5>
                            <div class="display-4">{max_drawdown*100:.1f}%</div>
                        </div>
                    </div>
                </div>

                <!-- Main Chart -->
                {plot_html}

                <!-- Navigation -->
                <div class="mt-4">
                    <a href="/" class="btn btn-secondary">Back to Dashboard</a>
                    <form action="/refresh" method="post" style="display: inline-block; margin-left: 10px;">
                        <button type="submit" class="btn btn-outline-danger">Refresh All Data</button>
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