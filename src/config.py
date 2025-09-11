import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'grimm-trading-secret-key-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'grimm-trading-jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Database Configuration - Use PostgreSQL if DATABASE_URL is provided (Railway), otherwise SQLite
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgresql'):
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # For local development, use SQLite in a writable location
        db_path = os.path.join(os.path.expanduser('~'), 'grimm_trading.db')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')
    
    # API Keys
    FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Ensure we're using PostgreSQL in production
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgresql'):
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        raise ValueError("PostgreSQL DATABASE_URL is required for production")

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
