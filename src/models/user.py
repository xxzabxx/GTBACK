from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from src.config import db
import uuid

class User(db.Model):
    __tablename__ = 'users'
    
    # Only include columns that definitely exist in the database
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

    def to_dict(self):
        """Convert user to dictionary for JSON responses"""
        return {
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
            'email_verified': self.email_verified
        }

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

