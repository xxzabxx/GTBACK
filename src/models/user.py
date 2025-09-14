from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from src.database import db
import uuid

class User(db.Model):
    __tablename__ = 'users'
    
    # Match the complete schema we just created
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    subscription_tier = Column(String(20), default='free')
    subscription_expires = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255))
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime(timezone=True))
    timezone = Column(String(50), default='America/New_York')
    preferred_language = Column(String(10), default='en')
    avatar_url = Column(Text)
    bio = Column(Text)
    default_watchlist_id = Column(UUID(as_uuid=True))
    notification_preferences = Column(JSON, default={'email': True, 'push': True, 'sms': False})
    trading_preferences = Column(JSON, default={'risk_level': 'medium', 'position_size': 'small'})

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    payments = relationship("Payment", back_populates="user")
    billing_addresses = relationship("BillingAddress", back_populates="user")

    @staticmethod
    def create_user(username, email, password, first_name=None, last_name=None):
        """Create a new user with hashed password"""
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name
        )
        db.session.add(user)
        db.session.commit()
        return user

    def check_password(self, password):
        """Check if provided password matches the hash"""
        return check_password_hash(self.password_hash, password)

    def set_password(self, password):
        """Set user password with hashing"""
        self.password_hash = generate_password_hash(password)

    @staticmethod
    def find_by_username_or_email(identifier):
        """Find user by username or email"""
        return User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

    @staticmethod
    def find_by_id(user_id):
        """Find user by ID"""
        return User.query.filter(User.id == user_id).first()

    def update_last_login(self):
        """Update the last login timestamp"""
        from datetime import datetime
        self.last_login = datetime.utcnow()
        db.session.commit()

    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary for JSON responses"""
        result = {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'subscription_tier': self.subscription_tier,
            'subscription_expires': self.subscription_expires.isoformat() if self.subscription_expires else None,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'email_verified': self.email_verified,
            'timezone': self.timezone,
            'preferred_language': self.preferred_language,
            'avatar_url': self.avatar_url,
            'bio': self.bio
        }
        
        if include_sensitive:
            result.update({
                'notification_preferences': self.notification_preferences,
                'trading_preferences': self.trading_preferences
            })
        
        return result

    def has_permission(self, feature):
        """Check if user has permission for a specific feature based on tier"""
        if not self.is_active:
            return False
            
        if self.is_admin:
            return True
            
        tier_permissions = {
            'free': ['basic_charts', 'basic_news'],
            'premium': ['basic_charts', 'basic_news', 'advanced_charts', 'scanners', 'alerts'],
            'pro': ['basic_charts', 'basic_news', 'advanced_charts', 'scanners', 'alerts', 'chat', 'premium_data', 'api_access']
        }
        
        return feature in tier_permissions.get(self.subscription_tier, [])

    def is_subscription_active(self):
        """Check if user's subscription is currently active"""
        if self.subscription_tier == 'free':
            return True
        if not self.subscription_expires:
            return False
        from datetime import datetime
        return datetime.utcnow() < self.subscription_expires

    def __repr__(self):
        return f'<User {self.username}>'

