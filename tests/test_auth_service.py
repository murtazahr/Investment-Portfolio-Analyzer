import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from services.auth_service import AuthService
from config import TestingConfig

class TestAuthService(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.app = Flask(__name__)
        self.app.config.from_object(TestingConfig)

        self.app_context = self.app.app_context()
        self.app_context.push()

        self.request_context = self.app.test_request_context()
        self.request_context.push()

        self.auth_service = AuthService()

    def tearDown(self):
        """Clean up test fixtures"""
        self.request_context.pop()
        self.app_context.pop()

    def test_get_auth_url(self):
        """Test authorization URL generation"""
        auth_url = self.auth_service.get_auth_url()

        self.assertIn('https://api.upstox.com/v2/login/authorization/dialog', auth_url)
        self.assertIn('client_id=', auth_url)
        self.assertIn('redirect_uri=', auth_url)
        self.assertIn('response_type=code', auth_url)

    @patch('services.auth_service.requests.post')
    def test_exchange_code_for_token_success(self, mock_post):
        """Test successful token exchange"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'test_token_123'}
        mock_post.return_value = mock_response

        result = self.auth_service.exchange_code_for_token('test_code')

        self.assertTrue(result)
        # Check that session was set (would need to import session and check)

    @patch('services.auth_service.requests.post')
    def test_exchange_code_for_token_failure(self, mock_post):
        """Test failed token exchange"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = self.auth_service.exchange_code_for_token('invalid_code')

        self.assertFalse(result)

    def test_is_authenticated_false_initially(self):
        """Test authentication status when no token present"""
        self.assertFalse(self.auth_service.is_authenticated())

if __name__ == '__main__':
    unittest.main()
