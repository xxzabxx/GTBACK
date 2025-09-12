"""
Stock Scanner Routes with Admin Controls and Tier Restrictions
Implements Ross Cameron-style scanners with permission system
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import User
from src.services.scanner_service import ScannerService
from src.middleware.permissions import require_permission
import psycopg2
import os
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection using environment variables"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    return psycopg2.connect(database_url)

scanners_bp = Blueprint('scanners', __name__)
scanner_service = ScannerService()

# Admin toggle settings for each scanner
SCANNER_SETTINGS = {
    'momentum': {
        'enabled': True,
        'free_limit': 5,
        'premium_limit': 15,
        'pro_limit': 25,
        'refresh_rate': 30  # seconds
    },
    'gappers': {
        'enabled': True,
        'free_limit': 3,
        'premium_limit': 10,
        'pro_limit': 20,
        'refresh_rate': 30
    },
    'low_float': {
        'enabled': True,
        'free_limit': 0,  # Premium feature only
        'premium_limit': 10,
        'pro_limit': 20,
        'refresh_rate': 30
    }
}

def get_scanner_settings(scanner_type: str) -> dict:
    """Get scanner settings from database or default"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT value FROM system_settings 
            WHERE key = %s
        """, (f'scanner_{scanner_type}_settings',))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            import json
            return json.loads(result[0])
        else:
            return SCANNER_SETTINGS.get(scanner_type, {})
            
    except Exception as e:
        logger.warning(f"Error getting scanner settings: {e}")
        return SCANNER_SETTINGS.get(scanner_type, {})

def update_scanner_settings(scanner_type: str, settings: dict):
    """Update scanner settings in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        import json
        cursor.execute("""
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) 
            DO UPDATE SET value = %s, updated_at = NOW()
        """, (f'scanner_{scanner_type}_settings', json.dumps(settings), json.dumps(settings)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating scanner settings: {e}")

def get_user_scanner_limit(user: User, scanner_type: str) -> int:
    """Get scanner result limit based on user tier"""
    settings = get_scanner_settings(scanner_type)
    
    if user.subscription_tier == 'pro':
        return settings.get('pro_limit', 20)
    elif user.subscription_tier == 'premium':
        return settings.get('premium_limit', 10)
    else:  # free
        return settings.get('free_limit', 5)

def is_scanner_enabled(scanner_type: str) -> bool:
    """Check if scanner is enabled by admin"""
    settings = get_scanner_settings(scanner_type)
    return settings.get('enabled', False)

@scanners_bp.route('/momentum', methods=['GET'])
@jwt_required()
def get_momentum_scanner():
    """
    Ross Cameron Momentum Scanner
    Finds high relative volume stocks with strong % gains
    """
    try:
        # Check if scanner is enabled
        if not is_scanner_enabled('momentum'):
            return jsonify({
                'error': 'Momentum scanner is currently disabled',
                'enabled': False
            }), 403
        
        # Get current user
        current_user_id = get_jwt_identity()
        user = User.find_by_id(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's limit based on tier
        limit = get_user_scanner_limit(user, 'momentum')
        
        if limit == 0:
            return jsonify({
                'error': 'Momentum scanner requires premium subscription',
                'upgrade_required': True,
                'current_tier': user.subscription_tier
            }), 403
        
        # Get scanner results
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                scanner_service.get_momentum_scanner(limit=limit)
            )
        finally:
            loop.close()
        
        settings = get_scanner_settings('momentum')
        
        return jsonify({
            'scanner_type': 'momentum',
            'results': results,
            'count': len(results),
            'limit': limit,
            'user_tier': user.subscription_tier,
            'refresh_rate': settings.get('refresh_rate', 30),
            'criteria': {
                'price_range': '$1.00 - $20.00',
                'min_percent_change': '10%+',
                'min_relative_volume': '5x+',
                'max_float': '20M shares',
                'description': 'Ross Cameron momentum stocks with high volume and strong gains'
            },
            'timestamp': results[0]['timestamp'] if results else None
        })
        
    except Exception as e:
        logger.error(f"Error in momentum scanner: {e}")
        return jsonify({'error': 'Scanner temporarily unavailable'}), 500

@scanners_bp.route('/gappers', methods=['GET'])
@jwt_required()
def get_gappers_scanner():
    """
    Ross Cameron Pre-Market Gappers Scanner
    Finds stocks gapping up with news catalysts
    """
    try:
        if not is_scanner_enabled('gappers'):
            return jsonify({
                'error': 'Gappers scanner is currently disabled',
                'enabled': False
            }), 403
        
        current_user_id = get_jwt_identity()
        user = User.find_by_id(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        limit = get_user_scanner_limit(user, 'gappers')
        
        if limit == 0:
            return jsonify({
                'error': 'Gappers scanner requires premium subscription',
                'upgrade_required': True,
                'current_tier': user.subscription_tier
            }), 403
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                scanner_service.get_gappers_scanner(limit=limit)
            )
        finally:
            loop.close()
        
        settings = get_scanner_settings('gappers')
        
        return jsonify({
            'scanner_type': 'gappers',
            'results': results,
            'count': len(results),
            'limit': limit,
            'user_tier': user.subscription_tier,
            'refresh_rate': settings.get('refresh_rate', 30),
            'criteria': {
                'price_range': '$1.00 - $20.00',
                'min_gap_percent': '5%+',
                'min_relative_volume': '3x+',
                'max_float': '20M shares',
                'description': 'Pre-market gappers with news catalysts and high volume'
            },
            'timestamp': results[0]['timestamp'] if results else None
        })
        
    except Exception as e:
        logger.error(f"Error in gappers scanner: {e}")
        return jsonify({'error': 'Scanner temporarily unavailable'}), 500

@scanners_bp.route('/low-float', methods=['GET'])
@jwt_required()
def get_low_float_scanner():
    """
    Ross Cameron Low Float Scanner
    Finds stocks with <10M float and explosive potential
    """
    try:
        if not is_scanner_enabled('low_float'):
            return jsonify({
                'error': 'Low float scanner is currently disabled',
                'enabled': False
            }), 403
        
        current_user_id = get_jwt_identity()
        user = User.find_by_id(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        limit = get_user_scanner_limit(user, 'low_float')
        
        if limit == 0:
            return jsonify({
                'error': 'Low float scanner requires premium subscription',
                'upgrade_required': True,
                'current_tier': user.subscription_tier
            }), 403
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                scanner_service.get_low_float_scanner(limit=limit)
            )
        finally:
            loop.close()
        
        settings = get_scanner_settings('low_float')
        
        return jsonify({
            'scanner_type': 'low_float',
            'results': results,
            'count': len(results),
            'limit': limit,
            'user_tier': user.subscription_tier,
            'refresh_rate': settings.get('refresh_rate', 30),
            'criteria': {
                'price_range': '$1.00 - $20.00',
                'min_percent_change': '5%+',
                'min_relative_volume': '2x+',
                'max_float': '10M shares',
                'description': 'Low float stocks with explosive potential for big moves'
            },
            'timestamp': results[0]['timestamp'] if results else None
        })
        
    except Exception as e:
        logger.error(f"Error in low float scanner: {e}")
        return jsonify({'error': 'Scanner temporarily unavailable'}), 500

@scanners_bp.route('/status', methods=['GET'])
@jwt_required()
def get_scanners_status():
    """Get status of all scanners for current user"""
    try:
        current_user_id = get_jwt_identity()
        user = User.find_by_id(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        status = {}
        
        for scanner_type in ['momentum', 'gappers', 'low_float']:
            settings = get_scanner_settings(scanner_type)
            limit = get_user_scanner_limit(user, scanner_type)
            
            status[scanner_type] = {
                'enabled': settings.get('enabled', False),
                'available': limit > 0,
                'limit': limit,
                'refresh_rate': settings.get('refresh_rate', 30),
                'requires_upgrade': limit == 0 and user.subscription_tier == 'free'
            }
        
        return jsonify({
            'user_tier': user.subscription_tier,
            'scanners': status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting scanner status: {e}")
        return jsonify({'error': 'Unable to get scanner status'}), 500

# Admin routes for scanner management
@scanners_bp.route('/admin/settings/<scanner_type>', methods=['GET'])
@jwt_required()
@require_permission('admin')
def get_admin_scanner_settings(scanner_type):
    """Get scanner settings for admin panel"""
    try:
        if scanner_type not in ['momentum', 'gappers', 'low_float']:
            return jsonify({'error': 'Invalid scanner type'}), 400
        
        settings = get_scanner_settings(scanner_type)
        
        return jsonify({
            'scanner_type': scanner_type,
            'settings': settings
        })
        
    except Exception as e:
        logger.error(f"Error getting admin scanner settings: {e}")
        return jsonify({'error': 'Unable to get settings'}), 500

@scanners_bp.route('/admin/settings/<scanner_type>', methods=['PUT'])
@jwt_required()
@require_permission('admin')
def update_admin_scanner_settings(scanner_type):
    """Update scanner settings from admin panel"""
    try:
        if scanner_type not in ['momentum', 'gappers', 'low_float']:
            return jsonify({'error': 'Invalid scanner type'}), 400
        
        data = request.get_json()
        
        # Validate settings
        required_fields = ['enabled', 'free_limit', 'premium_limit', 'pro_limit', 'refresh_rate']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Update settings
        update_scanner_settings(scanner_type, data)
        
        return jsonify({
            'message': f'{scanner_type.title()} scanner settings updated successfully',
            'scanner_type': scanner_type,
            'settings': data
        })
        
    except Exception as e:
        logger.error(f"Error updating admin scanner settings: {e}")
        return jsonify({'error': 'Unable to update settings'}), 500

@scanners_bp.route('/admin/toggle/<scanner_type>', methods=['POST'])
@jwt_required()
@require_permission('admin')
def toggle_scanner(scanner_type):
    """Toggle scanner on/off from admin panel"""
    try:
        if scanner_type not in ['momentum', 'gappers', 'low_float']:
            return jsonify({'error': 'Invalid scanner type'}), 400
        
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        # Get current settings and update enabled status
        settings = get_scanner_settings(scanner_type)
        settings['enabled'] = enabled
        
        update_scanner_settings(scanner_type, settings)
        
        return jsonify({
            'message': f'{scanner_type.title()} scanner {"enabled" if enabled else "disabled"}',
            'scanner_type': scanner_type,
            'enabled': enabled
        })
        
    except Exception as e:
        logger.error(f"Error toggling scanner: {e}")
        return jsonify({'error': 'Unable to toggle scanner'}), 500

@scanners_bp.route('/admin/overview', methods=['GET'])
@jwt_required()
@require_permission('admin')
def get_admin_scanners_overview():
    """Get overview of all scanners for admin dashboard"""
    try:
        overview = {}
        
        for scanner_type in ['momentum', 'gappers', 'low_float']:
            settings = get_scanner_settings(scanner_type)
            overview[scanner_type] = {
                'enabled': settings.get('enabled', False),
                'limits': {
                    'free': settings.get('free_limit', 0),
                    'premium': settings.get('premium_limit', 0),
                    'pro': settings.get('pro_limit', 0)
                },
                'refresh_rate': settings.get('refresh_rate', 30)
            }
        
        return jsonify({
            'scanners': overview,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting admin overview: {e}")
        return jsonify({'error': 'Unable to get overview'}), 500

