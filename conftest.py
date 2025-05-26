import pytest
from flask import Flask
from config import TestingConfig

@pytest.fixture
def app():
    """Create application for testing"""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    return app

@pytest.fixture
def client(app):
    """Test client for making requests"""
    return app.test_client()

@pytest.fixture
def app_context(app):
    """Application context for tests"""
    with app.app_context():
        yield app