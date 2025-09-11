from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt
import json
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    # Use UUID type that matches your Supabase schema
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    
    # Subscription and permissions - match your database exactly
    subscription_tier = db.Column(db.String(20), default='free')  # free, premium, pro
    subscription_expires = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Tracking fields - match your database column names
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)  # Use actual column name
    email_verification_token = db.Column(db.String(255), nullable=True)
    password_reset_token = db.Column(db.String(255), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    
    # Profile fields
    timezone = db.Column(db.String(50), default='America/New_York')
    preferred_language = db.Column(db.String(10), default='en')
    avatar_url = db.Column(db.Text, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Trading preferences
    default_watchlist_id = db.Column(db.String(36), nullable=True)
    notification_preferences = db.Column(db.JSON, default=lambda: {"email": True, "push": True, "sms": False})
    trading_preferences = db.Column(db.JSON, default=lambda: {"risk_level": "medium", "position_size": "small"})

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        """Hash and set password"""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password):
        """Check if provided password matches hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def to_dict(self):
        """Convert user to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'email_verified': self.email_verified,
            'subscription_tier': self.subscription_tier,
            'subscription_expires': self.subscription_expires.isoformat() if self.subscription_expires else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'timezone': self.timezone,
            'preferred_language': self.preferred_language,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'notification_preferences': self.notification_preferences,
            'trading_preferences': self.trading_preferences
        }

    def get_tier_info(self):
        """Get tier information and permissions"""
        tier_info = {
            'free': {
                'name': 'Free',
                'features': ['basic_scanners', 'basic_charts', 'basic_news'],
                'limits': {'watchlists': 1, 'symbols_per_watchlist': 10, 'alerts': 5}
            },
            'premium': {
                'name': 'Premium',
                'features': ['basic_scanners', 'basic_charts', 'basic_news', 'advanced_scanners', 
                           'real_time_data', 'unlimited_watchlists', 'trading_room'],
                'limits': {'watchlists': 5, 'symbols_per_watchlist': 50, 'alerts': 25}
            },
            'pro': {
                'name': 'Pro',
                'features': ['basic_scanners', 'basic_charts', 'basic_news', 'advanced_scanners',
                           'real_time_data', 'unlimited_watchlists', 'trading_room', 'level_2_data',
                           'options_flow', 'ai_alerts', 'api_access'],
                'limits': {'watchlists': -1, 'symbols_per_watchlist': -1, 'alerts': -1}
            }
        }
        
        return tier_info.get(self.subscription_tier, tier_info['free'])

    def has_permission(self, feature):
        """Check if user has permission for a specific feature"""
        tier_info = self.get_tier_info()
        return feature in tier_info['features']

    def is_subscription_active(self):
        """Check if subscription is still active"""
        if self.subscription_tier == 'free':
            return True
        if not self.subscription_expires:
            return False
        return datetime.utcnow() < self.subscription_expires

    def get_usage_limits(self):
        """Get usage limits for current tier"""
        tier_info = self.get_tier_info()
        return tier_info['limits']

    def can_create_watchlist(self, current_count):
        """Check if user can create another watchlist"""
        limits = self.get_usage_limits()
        max_watchlists = limits['watchlists']
        return max_watchlists == -1 or current_count < max_watchlists

    def can_add_symbol_to_watchlist(self, current_count):
        """Check if user can add another symbol to watchlist"""
        limits = self.get_usage_limits()
        max_symbols = limits['symbols_per_watchlist']
        return max_symbols == -1 or current_count < max_symbols

    def can_create_alert(self, current_count):
        """Check if user can create another alert"""
        limits = self.get_usage_limits()
        max_alerts = limits['alerts']
        return max_alerts == -1 or current_count < max_alerts

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()

    def upgrade_subscription(self, new_tier, expires_at=None):
        """Upgrade user subscription"""
        valid_tiers = ['free', 'premium', 'pro']
        if new_tier in valid_tiers:
            self.subscription_tier = new_tier
            self.subscription_expires = expires_at
            return True
        return False

    def downgrade_to_free(self):
        """Downgrade user to free tier"""
        self.subscription_tier = 'free'
        self.subscription_expires = None

    @staticmethod
    def find_by_username_or_email(identifier):
        """Find user by username or email"""
        return User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

    @staticmethod
    def create_user(username, email, password, **kwargs):
        """Create a new user"""
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            **kwargs
        )
        user.set_password(password)
        return user


# Simplified models for the other tables (we'll expand these later)
class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_default = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(7), default='#3B82F6')
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    alert_type = db.Column(db.String(20), nullable=False)  # price, volume, percentage, technical
    condition_type = db.Column(db.String(20), nullable=False)  # above, below, crosses_above, crosses_below
    target_value = db.Column(db.Numeric(10, 4), nullable=False)
    current_value = db.Column(db.Numeric(10, 4))
    message = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_triggered = db.Column(db.Boolean, default=False)
    triggered_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notification_methods = db.Column(db.JSON, default=lambda: ["email"])
    trigger_count = db.Column(db.Integer, default=0)
    max_triggers = db.Column(db.Integer, default=1)

