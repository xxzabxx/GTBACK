"""
Chat Routes Blueprint
Handles HTTP endpoints for chat functionality
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.database import db
from src.models.user import User
from datetime import datetime, timedelta
import uuid

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/history', methods=['GET'])
@jwt_required()
def get_chat_history():
    """Get recent chat messages for premium users"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check premium access
        if user.tier not in ['pro', 'premium']:
            return jsonify({'error': 'Premium subscription required'}), 403
        
        # Get hours parameter (default 24)
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Validate parameters
        hours = min(max(hours, 1), 168)  # 1 hour to 1 week
        limit = min(max(limit, 10), 100)  # 10 to 100 messages
        
        # Get recent messages
        result = db.session.execute(
            """SELECT id, username, message, stock_symbols, created_at, message_type
               FROM chat_messages 
               WHERE created_at > %s AND is_deleted = FALSE
               ORDER BY created_at DESC 
               LIMIT %s""",
            (datetime.utcnow() - timedelta(hours=hours), limit)
        )
        
        messages = []
        for row in result:
            messages.append({
                'id': str(row[0]),
                'username': row[1],
                'message': row[2],
                'stock_symbols': row[3] or [],
                'timestamp': row[4].isoformat(),
                'message_type': row[5]
            })
        
        # Reverse to get chronological order
        messages.reverse()
        
        return jsonify({
            'messages': messages,
            'count': len(messages),
            'hours': hours
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch chat history'}), 500

@chat_bp.route('/online-users', methods=['GET'])
@jwt_required()
def get_online_users():
    """Get count of online users in chat"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check premium access
        if user.tier not in ['pro', 'premium']:
            return jsonify({'error': 'Premium subscription required'}), 403
        
        # Get active sessions from last 5 minutes
        result = db.session.execute(
            """SELECT COUNT(DISTINCT user_id) as online_count
               FROM chat_sessions 
               WHERE is_active = TRUE 
               AND last_activity > %s""",
            (datetime.utcnow() - timedelta(minutes=5),)
        )
        
        online_count = result.fetchone()[0] or 0
        
        return jsonify({
            'online_count': online_count,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to get online users count'}), 500

@chat_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_chat_settings():
    """Get chat configuration settings"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check premium access
        if user.tier not in ['pro', 'premium']:
            return jsonify({'error': 'Premium subscription required'}), 403
        
        # Get chat settings from database
        result = db.session.execute(
            """SELECT key, value FROM system_settings 
               WHERE key LIKE 'chat_%'"""
        )
        
        settings = {}
        for row in result:
            key = row[0].replace('chat_', '')  # Remove 'chat_' prefix
            value = row[1]
            
            # Convert string values to appropriate types
            if value.lower() in ['true', 'false']:
                settings[key] = value.lower() == 'true'
            elif value.isdigit():
                settings[key] = int(value)
            else:
                settings[key] = value
        
        # Default settings if not found in database
        default_settings = {
            'enabled': True,
            'max_message_length': 1000,
            'rate_limit_messages': 5,
            'history_hours': 24,
            'premium_only': True
        }
        
        # Merge with defaults
        for key, default_value in default_settings.items():
            if key not in settings:
                settings[key] = default_value
        
        return jsonify({
            'settings': settings,
            'user_tier': user.tier
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to get chat settings'}), 500

@chat_bp.route('/health', methods=['GET'])
def chat_health():
    """Chat service health check"""
    try:
        # Test database connection
        db.session.execute("SELECT 1")
        
        return jsonify({
            'status': 'healthy',
            'service': 'chat',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

