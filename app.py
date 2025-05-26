from flask import Flask, render_template, redirect, url_for, request, session
from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly.io as pio

from config import Config
from services.auth_service import AuthService
from services.portfolio_service import PortfolioService
from utils.decorators import login_required

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize services
    auth_service = AuthService()
    portfolio_service = PortfolioService()

    @app.route('/')
    def home():
        """Home page - dashboard or login prompt"""
        if auth_service.is_authenticated():
            return render_template('dashboard.html')
        return render_template('login.html')

    @app.route('/login')
    def login():
        """Redirect to Upstox authorization"""
        auth_url = auth_service.get_auth_url()
        return redirect(auth_url)

    @app.route('/callback')
    def callback():
        """Handle OAuth callback from Upstox"""
        code = request.args.get('code')
        if not code:
            return "Authorization failed.", 400

        if auth_service.exchange_code_for_token(code):
            return redirect(url_for('home'))
        else:
            return "Token exchange failed.", 400

    @app.route('/logout')
    def logout():
        """Clear session and logout"""
        session.clear()
        return redirect(url_for('home'))

    @app.route('/summary')
    @login_required
    def summary():
        """Portfolio summary page"""
        try:
            portfolio_summary = portfolio_service.get_portfolio_summary()
            return render_template('summary.html',
                                   portfolio=portfolio_summary,
                                   format_currency=lambda x: f"₹{x:,.0f}",
                                   format_percentage=lambda x: f"{x:.1f}%")
        except Exception as e:
            return f"Error loading portfolio: {str(e)}", 500

    @app.route('/portfolio')
    @login_required
    def portfolio():
        """Portfolio performance analysis page"""
        # Parse date parameters
        start_param = request.args.get('start')
        end_param = request.args.get('end')

        try:
            end_date = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            if end_param:
                end_date = datetime.strptime(end_param, '%Y-%m-%d')

            start_date = end_date - timedelta(days=30)
            if start_param:
                start_date = datetime.strptime(start_param, '%Y-%m-%d')

            # Ensure proper date ordering
            if start_date > end_date:
                start_date, end_date = end_date, start_date

            # Get performance data
            portfolio_metrics, benchmark_metrics, returns_df = portfolio_service.get_performance_analysis(
                start_date, end_date
            )

            if portfolio_metrics is None:
                return render_template('no_data.html',
                                       start_date=start_date.date(),
                                       end_date=end_date.date())

            # Create visualization
            chart_html = _create_performance_chart(portfolio_metrics, benchmark_metrics)

            return render_template('performance.html',
                                   portfolio_metrics=portfolio_metrics,
                                   benchmark_metrics=benchmark_metrics,
                                   chart_html=chart_html,
                                   start_date=start_date,
                                   end_date=end_date)

        except ValueError as e:
            return f"Invalid date format: {str(e)}", 400
        except Exception as e:
            return f"Error loading performance data: {str(e)}", 500

    @app.route('/refresh', methods=['POST'])
    @login_required
    def refresh():
        """Refresh portfolio cache"""
        portfolio_service.refresh_cache()
        return redirect(url_for('summary'))

    def _create_performance_chart(portfolio_metrics, benchmark_metrics):
        """Create performance comparison chart"""
        fig = go.Figure()

        # Portfolio line
        fig.add_trace(go.Scatter(
            x=portfolio_metrics.cumulative_returns.index,
            y=portfolio_metrics.cumulative_returns * 100,
            mode='lines',
            name='Your Portfolio',
            line=dict(width=3, color='#667eea'),
            hovertemplate='<b>Portfolio</b><br>Date: %{x}<br>Cumulative Return: %{y:.2f}%<extra></extra>'
        ))

        # Benchmark line
        if benchmark_metrics:
            fig.add_trace(go.Scatter(
                x=benchmark_metrics.cumulative_returns.index,
                y=benchmark_metrics.cumulative_returns * 100,
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

        return pio.to_html(fig, full_html=False)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
    