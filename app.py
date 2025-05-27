import os
import json
from datetime import datetime, timedelta

import plotly.graph_objs as go
import plotly.io as pio
from flask import Flask, render_template, redirect, url_for, request, session, jsonify

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

            # Calculate gainers and losers for template
            gainers = len([h for h in portfolio_summary.holdings if getattr(h, 'day_pnl', 0) > 0])
            losers = len([h for h in portfolio_summary.holdings if getattr(h, 'day_pnl', 0) < 0])

            return render_template('summary.html',
                                   portfolio=portfolio_summary,
                                   pie_html=pie_html,
                                   bar_html=bar_html,
                                   day_change_html=day_change_html,
                                   gainers=gainers,
                                   losers=losers)
        except Exception as e:
            app.logger.error(f"Error in summary route: {str(e)}")
            return render_template('no_data.html',
                                   start_date=datetime.now().date(),
                                   end_date=datetime.now().date(),
                                   message=f"Error loading portfolio: {str(e)}")

    @app.route('/api/refresh_day_change', methods=['POST'])
    @login_required
    def api_refresh_day_change():
        """API endpoint to refresh day change data without page reload"""
        try:
            print("=== API REFRESH DAY CHANGE CALLED ===")

            # Force refresh day change data
            portfolio_service.force_refresh_day_change()

            # Get updated portfolio summary
            portfolio_summary = portfolio_service.get_portfolio_summary()

            # Prepare response data
            response_data = {
                'status': 'success',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'total_day_pnl': portfolio_summary.total_day_pnl,
                'total_day_change_percentage': portfolio_summary.total_day_change_percentage,
                'total_value': portfolio_summary.total_value,
                'holdings': []
            }

            # Add holdings data
            for holding in portfolio_summary.holdings:
                response_data['holdings'].append({
                    'tradingsymbol': holding.tradingsymbol,
                    'day_change': getattr(holding, 'day_change', 0),
                    'day_change_percentage': getattr(holding, 'day_change_percentage', 0),
                    'day_pnl': getattr(holding, 'day_pnl', 0),
                    'real_time_price': getattr(holding, 'real_time_price', holding.last_price),
                    'last_price': holding.last_price,
                    'current_value': holding.current_value,
                    'quantity': holding.quantity
                })

            # Count gainers and losers
            gainers = len([h for h in portfolio_summary.holdings if getattr(h, 'day_pnl', 0) > 0])
            losers = len([h for h in portfolio_summary.holdings if getattr(h, 'day_pnl', 0) < 0])

            response_data['gainers'] = gainers
            response_data['losers'] = losers

            app.logger.info("Day change data refreshed via API")
            return jsonify(response_data)

        except Exception as e:
            app.logger.error(f"Error in API refresh: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }), 500

    @app.route('/api/portfolio_summary')
    @login_required
    def api_portfolio_summary():
        """API endpoint to get current portfolio summary"""
        try:
            portfolio_summary = portfolio_service.get_portfolio_summary()

            # Create charts data for AJAX update
            pie_html, bar_html, day_change_html = _create_summary_charts(portfolio_summary)

            return jsonify({
                'status': 'success',
                'portfolio': {
                    'total_value': portfolio_summary.total_value,
                    'total_investment': portfolio_summary.total_investment,
                    'total_pnl': portfolio_summary.total_pnl,
                    'total_return_percentage': portfolio_summary.total_return_percentage,
                    'total_day_pnl': portfolio_summary.total_day_pnl,
                    'total_day_change_percentage': portfolio_summary.total_day_change_percentage,
                },
                'charts': {
                    'pie_html': pie_html,
                    'bar_html': bar_html,
                    'day_change_html': day_change_html
                },
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })

        except Exception as e:
            app.logger.error(f"Error getting portfolio summary: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/refresh', methods=['POST'])
    @login_required
    def refresh():
        """Traditional refresh route (fallback)"""
        try:
            portfolio_service.refresh_cache()
            return redirect(url_for('summary'))
        except Exception as e:
            app.logger.error(f"Error refreshing cache: {str(e)}")
            return f"Error refreshing data: {str(e)}", 500

    @app.route('/refresh_day_change', methods=['POST'])
    @login_required
    def refresh_day_change():
        """Traditional day change refresh (fallback)"""
        try:
            portfolio_service.force_refresh_day_change()
            return redirect(url_for('summary'))
        except Exception as e:
            app.logger.error(f"Error refreshing day change data: {str(e)}")
            return f"Error refreshing day change data: {str(e)}", 500

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
            title_text='',
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
            title_text='',
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
            title_text='',
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

    @app.route('/debug_day_change')
    @login_required
    def debug_day_change():
        """Debug endpoint to check day change data"""
        try:
            print("=== DEBUG DAY CHANGE ENDPOINT ===")

            # Get fresh data without cache
            portfolio_service.refresh_cache()
            summary = portfolio_service.get_portfolio_summary()

            debug_info = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_day_pnl': summary.total_day_pnl,
                'total_day_change_percentage': summary.total_day_change_percentage,
                'holdings_count': len(summary.holdings),
                'holdings_details': []
            }

            for holding in summary.holdings:
                debug_info['holdings_details'].append({
                    'symbol': holding.tradingsymbol,
                    'day_change': getattr(holding, 'day_change', 'N/A'),
                    'day_change_percentage': getattr(holding, 'day_change_percentage', 'N/A'),
                    'day_pnl': getattr(holding, 'day_pnl', 'N/A'),
                    'last_price': holding.last_price,
                    'quantity': holding.quantity
                })

            return f"<pre>{json.dumps(debug_info, indent=2)}</pre>"

        except Exception as e:
            return f"Debug error: {str(e)}", 500

    @app.route('/projections')
    @login_required
    def projections():
        """Portfolio projections page with Monte Carlo simulation"""

        # Get projection parameters from request
        years = int(request.args.get('years', 5))
        simulations = int(request.args.get('simulations', 10000))
        method = request.args.get('method', 'parametric')

        # Validate parameters
        years = max(1, min(30, years))  # Between 1 and 30 years
        simulations = max(1000, min(100000, simulations))  # Between 1k and 100k

        try:
            # Get projections
            projection_results = portfolio_service.get_portfolio_projections(
                years=years,
                simulations=simulations,
                method=method,
                use_historical=(method == 'historical')
            )

            # Get scenario analysis
            scenarios = portfolio_service.get_scenario_analysis(years=years)

            # Get market parameters and VIX data
            market_params = portfolio_service.market_data_service.get_market_parameters()
            vix_stats = portfolio_service.market_data_service.get_volatility_index_stats()
            market_sentiment = portfolio_service.market_data_service.get_current_market_sentiment()

            # Create visualizations
            projection_chart = _create_projection_chart(projection_results)
            scenario_chart = _create_scenario_chart(scenarios)

            # Get current portfolio summary for context
            portfolio_summary = portfolio_service.get_portfolio_summary()

            return render_template(
                'projections.html',
                projections=projection_results,
                scenarios=scenarios,
                portfolio=portfolio_summary,
                market_params=market_params,
                vix_stats=vix_stats,
                market_sentiment=market_sentiment,
                projection_chart=projection_chart,
                scenario_chart=scenario_chart,
                years=years,
                simulations=simulations,
                method=method
            )

        except ValueError as e:
            app.logger.error(f"Validation error in projections: {str(e)}")
            return render_template('no_data.html',
                                   start_date=datetime.now().date(),
                                   end_date=datetime.now().date(),
                                   message=str(e))
        except Exception as e:
            app.logger.error(f"Error in projections: {str(e)}")
            return render_template('no_data.html',
                                   start_date=datetime.now().date(),
                                   end_date=datetime.now().date(),
                                   message=f"Error generating projections: {str(e)}")

    @app.route('/api/market_data')
    @login_required
    def api_market_data():
        """API endpoint to get current market parameters"""
        try:
            market_params = portfolio_service.market_data_service.get_market_parameters()
            vix_stats = portfolio_service.market_data_service.get_volatility_index_stats()
            sentiment = portfolio_service.market_data_service.get_current_market_sentiment()

            return jsonify({
                'status': 'success',
                'market_parameters': {
                    'expected_return': market_params.get('expected_return', 0),
                    'volatility': market_params.get('volatility', 0),
                    'sharpe_ratio': market_params.get('sharpe_ratio', 0),
                    'data_source': f"{market_params.get('period_years', 0):.1f} years of data"
                },
                'vix_data': {
                    'current': vix_stats.get('current_vix', 0),
                    'average': vix_stats.get('average_vix', 0),
                    'min': vix_stats.get('min_vix', 0),
                    'max': vix_stats.get('max_vix', 0)
                },
                'market_sentiment': sentiment,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception as e:
            app.logger.error(f"Error getting market data: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/fire')
    @login_required
    def fire_calculator():
        """FIRE (Financial Independence Retire Early) calculator page"""

        # Get parameters
        annual_expenses = float(request.args.get('expenses', 500000))  # Default 5 lakhs
        current_age = int(request.args.get('current_age', 30))
        retirement_age = int(request.args.get('retirement_age', 45))
        life_expectancy = int(request.args.get('life_expectancy', 90))

        try:
            # Get FIRE projections
            fire_results = portfolio_service.get_fire_projections(
                annual_expenses=annual_expenses,
                current_age=current_age,
                retirement_age=retirement_age,
                life_expectancy=life_expectancy
            )

            # Create visualization
            fire_chart = _create_fire_progress_chart(fire_results)

            # Get portfolio summary
            portfolio_summary = portfolio_service.get_portfolio_summary()

            return render_template(
                'fire.html',
                fire=fire_results,
                portfolio=portfolio_summary,
                fire_chart=fire_chart,
                annual_expenses=annual_expenses,
                current_age=current_age,
                retirement_age=retirement_age,
                life_expectancy=life_expectancy
            )

        except Exception as e:
            app.logger.error(f"Error in FIRE calculator: {str(e)}")
            return f"Error calculating FIRE projections: {str(e)}", 500

    @app.route('/goals')
    @login_required
    def goals():
        """Financial goals tracking page"""

        # Get parameters from request with defaults
        goal_amount = float(request.args.get('goal_amount', 10000000))  # Default: 1 crore
        goal_years = int(request.args.get('goal_years', 10))           # Default: 10 years
        monthly_contribution = float(request.args.get('monthly_contribution', 50000))  # Default: 50k/month

        # Validate inputs
        goal_amount = max(100000, goal_amount)  # Minimum 1 lakh
        goal_years = max(1, min(40, goal_years))  # Between 1-40 years
        monthly_contribution = max(0, monthly_contribution)

        # Calculate goal date
        goal_date = datetime.now() + timedelta(days=goal_years * 365)

        try:
            # Calculate goal progress
            goal_progress = portfolio_service.calculate_goal_progress(
                goal_amount=goal_amount,
                goal_date=goal_date,
                monthly_contribution=monthly_contribution
            )

            # Get portfolio summary for context
            portfolio_summary = portfolio_service.get_portfolio_summary()

            return render_template(
                'goals.html',
                goal=goal_progress,
                portfolio=portfolio_summary,
                goal_amount=goal_amount,
                goal_years=goal_years,
                monthly_contribution=monthly_contribution
            )

        except Exception as e:
            app.logger.error(f"Error in goals: {str(e)}")
            return render_template('no_data.html',
                                   start_date=datetime.now().date(),
                                   end_date=datetime.now().date(),
                                   message=f"Error calculating goal progress: {str(e)}")

    def _create_projection_chart(projections):
        """Create projection distribution visualization"""

        import plotly.graph_objs as go
        import plotly.io as pio

        # Create histogram of final values
        fig = go.Figure()

        # Add histogram
        fig.add_trace(go.Histogram(
            x=projections.final_values,
            nbinsx=50,
            name='Projected Values',
            marker_color='rgba(102, 126, 234, 0.6)',
            hovertemplate='<b>Portfolio Value</b>: ₹%{x:,.0f}<br><b>Count</b>: %{y}<extra></extra>'
        ))

        # Add percentile lines with annotations
        percentile_info = [
            (5, 'red', '5th percentile (Worst case)'),
            (25, 'orange', '25th percentile'),
            (50, 'green', '50th percentile (Expected)'),
            (75, 'orange', '75th percentile'),
            (95, 'red', '95th percentile (Best case)')
        ]

        for percentile, color, label in percentile_info:
            value = projections.percentiles[percentile]
            fig.add_vline(
                x=value,
                line_dash="dash",
                line_color=color,
                annotation_text=f"{label}<br>₹{value:,.0f}",
                annotation_position="top right" if percentile > 50 else "top left"
            )

        # Calculate some statistics for the title
        expected_annual_return = projections.expected_return * 100

        fig.update_layout(
            title={
                'text': f'Portfolio Value Distribution after {projections.projection_years} Years<br>' +
                        f'<sub>Expected Annual Return: {expected_annual_return:.1f}% | ' +
                        f'Risk of Loss: {projections.probability_of_loss*100:.1f}%</sub>',
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title='Portfolio Value (₹)',
            yaxis_title='Frequency',
            showlegend=False,
            height=500,
            template='plotly_white',
            hovermode='x'
        )

        # Format x-axis for Indian currency
        fig.update_xaxis(
            tickformat=',.0f',
            tickprefix='₹'
        )

        return pio.to_html(fig, full_html=False)

    def _create_scenario_chart(scenarios):
        """Create scenario analysis visualization"""

        import plotly.graph_objs as go
        import plotly.io as pio

        # Prepare data
        scenario_names = [s.name for s in scenarios]
        projected_values = [s.projected_value for s in scenarios]
        probabilities_of_loss = [s.probability_of_loss * 100 for s in scenarios]

        # Create figure with secondary y-axis
        fig = go.Figure()

        # Add bar chart for projected values
        fig.add_trace(go.Bar(
            name='Projected Value',
            x=scenario_names,
            y=projected_values,
            text=[f'₹{v:,.0f}' for v in projected_values],
            textposition='outside',
            marker_color=['#28a745', '#17a2b8', '#ffc107', '#dc3545'],
            hovertemplate='<b>%{x}</b><br>Projected Value: ₹%{y:,.0f}<extra></extra>'
        ))

        # Add line chart for probability of loss
        fig.add_trace(go.Scatter(
            name='Risk of Loss',
            x=scenario_names,
            y=probabilities_of_loss,
            mode='lines+markers+text',
            text=[f'{p:.1f}%' for p in probabilities_of_loss],
            textposition='top center',
            line=dict(color='red', width=3),
            marker=dict(size=10),
            yaxis='y2',
            hovertemplate='<b>%{x}</b><br>Risk of Loss: %{y:.1f}%<extra></extra>'
        ))

        # Update layout
        fig.update_layout(
            title='Scenario Analysis: Projected Portfolio Values',
            xaxis_title='Market Scenario',
            yaxis_title='Projected Portfolio Value (₹)',
            yaxis2=dict(
                title='Probability of Loss (%)',
                overlaying='y',
                side='right',
                range=[0, max(probabilities_of_loss) * 1.2]
            ),
            height=400,
            template='plotly_white',
            hovermode='x',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Format y-axis
        fig.update_yaxes(tickformat=',.0f', tickprefix='₹', secondary_y=False)
        fig.update_yaxes(tickformat='.1f', ticksuffix='%', secondary_y=True)

        return pio.to_html(fig, full_html=False)

    def _create_fire_progress_chart(fire_results):
        """Create FIRE progress visualization"""

        import plotly.graph_objs as go
        import plotly.io as pio

        # Create gauge chart for progress
        current_value = fire_results['current_portfolio_value']
        fire_number = fire_results['fire_number']
        progress_percentage = min(100, (current_value / fire_number) * 100)

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=progress_percentage,
            title={'text': f"Progress to FIRE<br><sub>Current: ₹{current_value:,.0f} | Target: ₹{fire_number:,.0f}</sub>"},
            delta={'reference': 25, 'increasing': {'color': "green"}},
            gauge={
                'axis': {'range': [None, 100], 'ticksuffix': '%'},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 25], 'color': "lightgray"},
                    {'range': [25, 50], 'color': "gray"},
                    {'range': [50, 75], 'color': "lightgreen"},
                    {'range': [75, 100], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))

        fig.update_layout(
            height=400,
            font={'size': 16}
        )

        return pio.to_html(fig, full_html=False)

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
