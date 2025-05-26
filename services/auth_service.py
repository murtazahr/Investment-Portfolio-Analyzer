import requests
from flask import session
from config import Config

class AuthService:
    """Handle authentication with Upstox API"""

    def __init__(self):
        self.config = Config()

    def get_auth_url(self):
        """Generate authorization URL for Upstox"""
        return (f"{self.config.UPSTOX_AUTH_URL}"
                f"?client_id={self.config.UPSTOX_API_KEY}"
                f"&redirect_uri={self.config.UPSTOX_REDIRECT_URI}"
                f"&response_type=code")

    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        try:
            response = requests.post(
                self.config.UPSTOX_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "code": code,
                    "client_id": self.config.UPSTOX_API_KEY,
                    "client_secret": self.config.UPSTOX_API_SECRET,
                    "redirect_uri": self.config.UPSTOX_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )

            if response.status_code == 200:
                token_data = response.json()
                session['access_token'] = token_data['access_token']
                return True
            return False

        except Exception as e:
            print(f"Token exchange error: {str(e)}")
            return False

    @staticmethod
    def get_headers():
        """Get authorization headers for API requests"""
        access_token = session.get('access_token')
        if not access_token:
            raise ValueError("No access token available")
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    def is_authenticated():
        """Check if user is authenticated"""
        return 'access_token' in session
