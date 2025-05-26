from functools import wraps

from flask import redirect, url_for, session


def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('access_token'):
            return redirect(url_for('login'))  # Updated to match app.py route
        return f(*args, **kwargs)
    return decorated_function

def handle_api_errors(f):
    """Decorator to handle API errors gracefully"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Log the error
            print(f"API Error in {f.__name__}: {str(e)}")
            return {"error": str(e)}, 500
    return decorated_function
