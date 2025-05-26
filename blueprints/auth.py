from flask import Blueprint, redirect, url_for, request, session
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()

@auth_bp.route('/login')
def login():
    auth_url = auth_service.get_auth_url()
    return redirect(auth_url)

@auth_bp.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "Authorization failed.", 400

    if auth_service.exchange_code_for_token(code):
        return redirect(url_for('main.home'))
    else:
        return "Token exchange failed.", 400

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))