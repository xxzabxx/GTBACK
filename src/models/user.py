from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    subscription_tier = db.Column(db.String(20), default='free')  # free, premium, pro
    subscription_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    watchlists = db.relationship('Watchlist', backref='user', lazy=True, cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        """Hash and set password"""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    def check_password(self, password):
        """Check if provided password matches hash"""
        password_bytes = password.encode('utf-8')
        hash_bytes = self.password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)

    def has_permission(self, feature):
        """Check if user has permission for a specific feature"""
        if self.is_admin:
            return True
            
        # Check if subscription is expired
        if self.subscription_expires and self.subscription_expires < datetime.utcnow():
            return feature in TIER_PERMISSIONS['free']
            
        return feature in TIER_PERMISSIONS.get(self.subscription_tier, [])

    def is_subscription_active(self):
        """Check if user's subscription is active"""
        if self.subscription_tier == 'free':
            return True
        return self.subscription_expires and self.subscription_expires > datetime.utcnow()

    def get_tier_info(self):
        """Get detailed tier information"""
        return {
            'tier': self.subscription_tier,
            'expires': self.subscription_expires.isoformat() if self.subscription_expires else None,
            'is_active': self.is_subscription_active(),
            'permissions': TIER_PERMISSIONS.get(self.subscription_tier, [])
        }

    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary"""
        user_dict = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'is_admin': self.is_admin,
            'subscription_tier': self.subscription_tier,
            'subscription_expires': self.subscription_expires.isoformat() if self.subscription_expires else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'tier_info': self.get_tier_info()
        }
        
        if include_sensitive:
            user_dict['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
            
        return user_dict

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()

class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    symbols = db.Column(db.Text, nullable=True)  # JSON string of symbols
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_symbols_list(self):
        """Get symbols as a list"""
        if self.symbols:
            try:
                return json.loads(self.symbols)
            except:
                return []
        return []

    def set_symbols_list(self, symbols_list):
        """Set symbols from a list"""
        self.symbols = json.dumps(symbols_list)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'symbols': self.get_symbols_list(),
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    alert_type = db.Column(db.String(20), nullable=False)  # price, volume, percent_change
    condition = db.Column(db.String(10), nullable=False)  # above, below, equals
    target_value = db.Column(db.Float, nullable=False)
    current_value = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_triggered = db.Column(db.Boolean, default=False)
    triggered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'alert_type': self.alert_type,
            'condition': self.condition,
            'target_value': self.target_value,
            'current_value': self.current_value,
            'is_active': self.is_active,
            'is_triggered': self.is_triggered,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Tier permissions configuration
TIER_PERMISSIONS = {
    'free': [
        'basic_dashboard',
        'basic_charts',
        'limited_scanners',  # 1-2 scanners
        'basic_watchlist'    # 1 watchlist, 10 symbols max
    ],
    'premium': [
        'basic_dashboard',
        'basic_charts',
        'advanced_charts',
        'all_scanners',      # All scanner types
        'advanced_watchlist', # 5 watchlists, 50 symbols each
        'price_alerts',      # Basic price alerts
        'news_feed',         # Real-time news
        'chat_access'        # Trading room chat
    ],
    'pro': [
        'basic_dashboard',
        'basic_charts',
        'advanced_charts',
        'professional_charts',
        'all_scanners',
        'custom_scanners',   # Create custom scanner criteria
        'unlimited_watchlist', # Unlimited watchlists and symbols
        'advanced_alerts',   # Volume, momentum, custom alerts
        'news_feed',
        'chat_access',
        'priority_support',
        'api_access',        # API access for external tools
        'export_data'        # Export scanner results, watchlists
    ]
}
