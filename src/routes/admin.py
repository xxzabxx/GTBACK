from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
from models.user import User, Watchlist, Alert, db, TIER_PERMISSIONS
from middleware.permissions import require_admin

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@require_admin()
def get_all_users():
    """Get all users with pagination and filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        tier_filter = request.args.get('tier', '')
        status_filter = request.args.get('status', '')
        
        # Build query
        query = User.query
        
        # Apply search filter
        if search:
            query = query.filter(
                (User.username.ilike(f'%{search}%')) |
                (User.email.ilike(f'%{search}%')) |
                (User.first_name.ilike(f'%{search}%')) |
                (User.last_name.ilike(f'%{search}%'))
            )
        
        # Apply tier filter
        if tier_filter:
            query = query.filter(User.subscription_tier == tier_filter)
        
        # Apply status filter
        if status_filter == 'active':
            query = query.filter(User.is_active == True)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active == False)
        elif status_filter == 'admin':
            query = query.filter(User.is_admin == True)
        
        # Order by creation date (newest first)
        query = query.order_by(User.created_at.desc())
        
        # Paginate
        users = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            'users': [user.to_dict(include_sensitive=True) for user in users.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': users.total,
                'pages': users.pages,
                'has_next': users.has_next,
                'has_prev': users.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@require_admin()
def get_user_details(user_id):
    """Get detailed user information"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Get user's watchlists and alerts
        watchlists = [wl.to_dict() for wl in user.watchlists]
        alerts = [alert.to_dict() for alert in user.alerts]
        
        user_data = user.to_dict(include_sensitive=True)
        user_data['watchlists'] = watchlists
        user_data['alerts'] = alerts
        user_data['stats'] = {
            'watchlists_count': len(watchlists),
            'alerts_count': len(alerts),
            'active_alerts_count': len([a for a in alerts if a['is_active']])
        }
        
        return jsonify(user_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>/tier', methods=['PUT'])
@require_admin()
def update_user_tier(user_id):
    """Update user's subscription tier"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        new_tier = data.get('tier')
        expires_in_days = data.get('expires_in_days', 30)
        
        if new_tier not in ['free', 'premium', 'pro']:
            return jsonify({'error': 'Invalid tier'}), 400
        
        # Update tier
        user.subscription_tier = new_tier
        
        # Set expiration date for paid tiers
        if new_tier != 'free':
            user.subscription_expires = datetime.utcnow() + timedelta(days=expires_in_days)
        else:
            user.subscription_expires = None
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': f'User tier updated to {new_tier}',
            'user': user.to_dict(include_sensitive=True)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>/status', methods=['PUT'])
@require_admin()
def update_user_status(user_id):
    """Update user's active status"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        is_active = data.get('is_active')
        if is_active is None:
            return jsonify({'error': 'is_active field is required'}), 400
        
        user.is_active = bool(is_active)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'activated' if is_active else 'deactivated'
        return jsonify({
            'message': f'User {status} successfully',
            'user': user.to_dict(include_sensitive=True)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>/admin', methods=['PUT'])
@require_admin()
def update_admin_status(user_id):
    """Grant or revoke admin privileges"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        is_admin = data.get('is_admin')
        if is_admin is None:
            return jsonify({'error': 'is_admin field is required'}), 400
        
        user.is_admin = bool(is_admin)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'granted' if is_admin else 'revoked'
        return jsonify({
            'message': f'Admin privileges {status} successfully',
            'user': user.to_dict(include_sensitive=True)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/stats', methods=['GET'])
@require_admin()
def get_admin_stats():
    """Get platform statistics"""
    try:
        # User statistics
        total_users = User.query.count()
        active_users = User.query.filter(User.is_active == True).count()
        admin_users = User.query.filter(User.is_admin == True).count()
        
        # Tier statistics
        free_users = User.query.filter(User.subscription_tier == 'free').count()
        premium_users = User.query.filter(User.subscription_tier == 'premium').count()
        pro_users = User.query.filter(User.subscription_tier == 'pro').count()
        
        # Recent activity
        recent_users = User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        recent_logins = User.query.filter(
            User.last_login >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        # Content statistics
        total_watchlists = Watchlist.query.count()
        total_alerts = Alert.query.count()
        active_alerts = Alert.query.filter(Alert.is_active == True).count()
        
        return jsonify({
            'users': {
                'total': total_users,
                'active': active_users,
                'admins': admin_users,
                'recent_signups': recent_users,
                'recent_logins': recent_logins
            },
            'tiers': {
                'free': free_users,
                'premium': premium_users,
                'pro': pro_users
            },
            'content': {
                'watchlists': total_watchlists,
                'alerts': total_alerts,
                'active_alerts': active_alerts
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/tiers', methods=['GET'])
@require_admin()
def get_tier_info():
    """Get information about all subscription tiers"""
    try:
        return jsonify({
            'tiers': {
                'free': {
                    'name': 'Free',
                    'price': 0,
                    'features': TIER_PERMISSIONS['free'],
                    'limits': {
                        'watchlists': 1,
                        'symbols_per_watchlist': 10,
                        'alerts': 5
                    }
                },
                'premium': {
                    'name': 'Premium',
                    'price': 29.99,
                    'features': TIER_PERMISSIONS['premium'],
                    'limits': {
                        'watchlists': 5,
                        'symbols_per_watchlist': 50,
                        'alerts': 25
                    }
                },
                'pro': {
                    'name': 'Professional',
                    'price': 99.99,
                    'features': TIER_PERMISSIONS['pro'],
                    'limits': {
                        'watchlists': 'unlimited',
                        'symbols_per_watchlist': 'unlimited',
                        'alerts': 'unlimited'
                    }
                }
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin()
def delete_user(user_id):
    """Delete a user account (soft delete by deactivating)"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent deleting admin users
        if user.is_admin:
            return jsonify({'error': 'Cannot delete admin users'}), 403
        
        # Soft delete by deactivating
        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'User deactivated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

