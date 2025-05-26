import os
from datetime import datetime, timedelta

import plotly.graph_objs as go
import plotly.io as pio
from flask import Flask, render_template, redirect, url_for, request, session

from config import config
from services.auth_service import AuthService
from services.portfolio_service import PortfolioService
from utils.decorators import login_required


def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)

    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app.config.from_object(config[config_name])

    # Initialize services
    auth_service = AuthService()
    portfolio_service = PortfolioService()

    # Add utility functions to Jinja2 globals
    @app.template_global()
    def get_date_offset(base_date, days):
        """Calculate date offset for templates"""
        return (base_date - timedelta(days=days)).strftime('%Y-%m-%d')

    @app.template_global()
    def format_currency(value):
        """Format currency for templates"""
        return f"₹{value:,.0f}"

    @app.template_global()
    def format_percentage(value):
        """Format percentage for templates"""
        return f"{value:.1f}%"

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
        """Portfolio summary page with enhanced visualizations and day change"""
        try:
            portfolio_summary = portfolio_service.get_portfolio_summary()

            # Check if we have valid data
            if not portfolio_summary or not portfolio_summary.holdings:
                return render_template('no_data.html',
                                       start_date=datetime.now().date(),
                                       end_date=datetime.now().date(),
                                       message="No portfolio holdings found. Please check your Upstox connection.")

            # Create enhanced visualizations including day change
            pie_html, bar_html, day_change_html = _create_summary_charts(portfolio_summary)

            return render_template('summary.html',
                                   portfolio=portfolio_summary,
                                   pie_html=pie_html,
                                   bar_html=bar_html,
                                   day_change_html=day_change_html)
        except Exception as e:
            app.logger.error(f"Error in summary route: {str(e)}")
            return render_template('no_data.html',
                                   start_date=datetime.now().date(),
                                   end_date=datetime.now().date(),
                                   message=f"Error loading portfolio: {str(e)}")

    def _create_summary_charts(portfolio_summary):
        """Create enhanced visualizations for portfolio summary including day change"""

        # Check if we have holdings
        if not portfolio_summary.holdings:
            # Return empty charts
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title="No data available",
                height=400,
                annotations=[dict(text="No holdings data available",
                                  showarrow=False,
                                  x=0.5, y=0.5,
                                  xref="paper", yref="paper")]
            )
            empty_html = pio.to_html(empty_fig, full_html=False)
            return empty_html, empty_html, empty_html

        # Enhanced colors matching original
        colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7']

        # Pie chart with custom colors and styling
        pie_fig = go.Figure(data=[go.Pie(
            labels=[holding.tradingsymbol for holding in portfolio_summary.holdings],
            values=[holding.current_value for holding in portfolio_summary.holdings],
            hole=0.4,
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Value: ₹%{value:,.0f}<br>Percentage: %{percent}<extra></extra>',
            marker=dict(
                colors=colors[:len(portfolio_summary.holdings)],
                line=dict(color='white', width=2)
            )
        )])

        pie_fig.update_layout(
            title_text='Asset Allocation',
            height=500,
            font=dict(size=12),
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.05
            ),
            margin=dict(t=40, b=20, l=20, r=120)
        )

        # Enhanced bar chart with conditional coloring for overall returns
        return_percentages = [holding.return_percentage for holding in portfolio_summary.holdings]
        symbols = [holding.tradingsymbol for holding in portfolio_summary.holdings]

        bar_fig = go.Figure([go.Bar(
            x=symbols,
            y=return_percentages,
            marker_color=[('#28a745' if val >= 0 else '#dc3545') for val in return_percentages],
            hovertemplate='<b>%{x}</b><br>Return: %{y:.1f}%<extra></extra>',
            text=[f"{val:.1f}%" for val in return_percentages],
            textposition='outside'
        )])

        bar_fig.update_layout(
            title_text='Individual Stock Performance',
            yaxis_title='Return (%)',
            xaxis_title='Stock',
            height=500,
            font=dict(size=12),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=40, b=60, l=60, r=20)
        )
        bar_fig.update_yaxes(gridcolor='rgba(0,0,0,0.1)')

        # New day change chart
        day_change_percentages = [getattr(holding, 'day_change_percentage', 0) for holding in portfolio_summary.holdings]
        day_change_fig = go.Figure([go.Bar(
            x=symbols,
            y=day_change_percentages,
            marker_color=[('#28a745' if val >= 0 else '#dc3545') for val in day_change_percentages],
            hovertemplate='<b>%{x}</b><br>Day Change: %{y:.1f}%<extra></extra>',
            text=[f"{val:.1f}%" for val in day_change_percentages],
            textposition='outside'
        )])

        day_change_fig.update_layout(
            title_text='Today\'s Performance by Stock',
            yaxis_title='Day Change (%)',
            xaxis_title='Stock',
            height=400,
            font=dict(size=12),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=40, b=60, l=60, r=20)
        )
        day_change_fig.update_yaxes(gridcolor='rgba(0,0,0,0.1)')

        # Convert to HTML
        pie_html = pio.to_html(pie_fig, full_html=False)
        bar_html = pio.to_html(bar_fig, full_html=False)
        day_change_html = pio.to_html(day_change_fig, full_html=False)

        return pie_html, bar_html, day_change_html

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

            # Calculate preset date ranges for quick selection
            today = end_date
            date_presets = {
                '1M': (today - timedelta(days=30), today),
                '3M': (today - timedelta(days=90), today),
                '6M': (today - timedelta(days=180), today),
                '1Y': (today - timedelta(days=365), today),
                '3Y': (today - timedelta(days=1095), today),
                '5Y': (today - timedelta(days=1825), today),
                '10Y': (today - timedelta(days=3650), today),
            }

            return render_template('performance.html',
                                   portfolio_metrics=portfolio_metrics,
                                   benchmark_metrics=benchmark_metrics,
                                   chart_html=chart_html,
                                   start_date=start_date,
                                   end_date=end_date,
                                   date_presets=date_presets)

        except ValueError as e:
            app.logger.error(f"Date validation error: {str(e)}")
            return f"Invalid date format: {str(e)}", 400
        except Exception as e:
            app.logger.error(f"Error in portfolio route: {str(e)}")
            return f"Error loading performance data: {str(e)}", 500

    @app.route('/refresh', methods=['POST'])
    @login_required
    def refresh():
        """Refresh portfolio cache"""
        try:
            portfolio_service.refresh_cache()
            return redirect(url_for('summary'))
        except Exception as e:
            app.logger.error(f"Error refreshing cache: {str(e)}")
            return f"Error refreshing data: {str(e)}", 500

    def _generate_summary_charts(portfolio_summary):
        """Generate chart data for portfolio summary page"""
        # Enhanced colors matching original
        colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7']

        # Pie chart data
        pie_data = {
            'values': [holding.current_value for holding in portfolio_summary.holdings],
            'labels': [holding.tradingsymbol for holding in portfolio_summary.holdings],
            'colors': colors[:len(portfolio_summary.holdings)]
        }

        # Bar chart data
        bar_data = {
            'symbols': [holding.tradingsymbol for holding in portfolio_summary.holdings],
            'returns': [holding.return_percentage for holding in portfolio_summary.holdings]
        }

        return {
            'pie': pie_data,
            'bar': bar_data
        }

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
