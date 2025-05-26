from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from services.portfolio_service import PortfolioService
from utils.decorators import login_required

portfolio_bp = Blueprint('portfolio', __name__)
portfolio_service = PortfolioService()

@portfolio_bp.route('/summary')
@login_required
def summary():
    try:
        portfolio_summary = portfolio_service.get_portfolio_summary()
        return render_template('summary.html', portfolio=portfolio_summary)
    except Exception as e:
        return f"Error loading portfolio: {str(e)}", 500

@portfolio_bp.route('/performance')
@login_required
def performance():
    # Implementation similar to the main app route
    pass