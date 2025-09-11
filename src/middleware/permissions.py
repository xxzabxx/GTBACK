from functools import wraps
from flask import request, jsonify, g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from src.database import db
from src.models.user import User

def require_permission(feature):
    """Decorator to require specific permission for a route"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Verify JWT token
                verify_jwt_in_request()
                current_user_id = get_jwt_identity()
                
                # Get user from database
                user = User.query.filter_by(id=current_user_id).first()
                if not user:
                    return jsonify({'error': 'User not found'}), 404
                
                # Check if user is active
                if not user.is_active:
                    return jsonify({'error': 'Account is deactivated'}), 403
                
                # Check permission
                if not user.has_permission(feature):
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'required_feature': feature,
                        'current_tier': user.subscription_tier,
                        'upgrade_required': True
                    }), 403
                
                # Store user in g for use in the route
                g.current_user = user
                
                return f(*args, **kwargs)
                
            except Exception as e:
                return jsonify({'error': 'Authentication failed'}), 401
                
        return decorated_function
    return decorator

def require_admin():
    """Decorator to require admin privileges"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Verify JWT token
                verify_jwt_in_request()
                current_user_id = get_jwt_identity()
                
                # Get user from database
                user = User.query.filter_by(id=current_user_id).first()
                if not user:
                    return jsonify({'error': 'User not found'}), 404
                
                # Check if user is admin
                if not user.is_admin:
                    return jsonify({'error': 'Admin privileges required'}), 403
                
                # Store user in g for use in the route
                g.current_user = user
                
                return f(*args, **kwargs)
                
            except Exception as e:
                return jsonify({'error': 'Authentication failed'}), 401
                
        return decorated_function
    return decorator

def get_current_user():
    """Helper function to get current authenticated user"""
    try:
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        return User.query.filter_by(id=current_user_id).first()
    except:
        return None

def check_feature_access(user, feature):
    """Helper function to check if user has access to a feature"""
    if not user:
        return False
    return user.has_permission(feature)

def get_user_permissions(user):
    """Get all permissions for a user"""
    if not user:
        return []
    return user.get_tier_info()['permissions']

def validate_tier_limits(user, resource_type, current_count):
    """Validate if user can create more resources based on tier limits"""
    tier = user.subscription_tier
    
    limits = {
        'free': {
            'watchlists': 1,
            'symbols_per_watchlist': 10,
            'alerts': 5
        },
        'premium': {
            'watchlists': 5,
            'symbols_per_watchlist': 50,
            'alerts': 25
        },
        'pro': {
            'watchlists': -1,  # Unlimited
            'symbols_per_watchlist': -1,  # Unlimited
            'alerts': -1  # Unlimited
        }
    }
    
    if user.is_admin:
        return True
    
    tier_limits = limits.get(tier, limits['free'])
    resource_limit = tier_limits.get(resource_type, 0)
    
    # -1 means unlimited
    if resource_limit == -1:
        return True
    
    return current_count < resource_limit

