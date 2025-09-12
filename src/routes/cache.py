"""
Cache Management Routes for GrimmTrading Platform
Provides endpoints for cache monitoring, management, and optimization
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.middleware.permissions import require_admin
from src.services.cache_service import cache_service, market_cache
from src.services.finnhub_service import finnhub_service
from datetime import datetime
import time

cache_bp = Blueprint('cache', __name__)

@cache_bp.route('/health', methods=['GET'])
@jwt_required()
@require_admin()
def cache_health():
    """
    Cache system health check
    Admin only endpoint
    """
    try:
        cache_stats = cache_service.get_cache_stats()
        
        return jsonify({
            'success': True,
            'cache_system': cache_stats,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/stats', methods=['GET'])
@jwt_required()
@require_admin()
def get_cache_stats():
    """
    Get detailed cache statistics
    Admin only endpoint
    """
    try:
        cache_stats = cache_service.get_cache_stats()
        
        # Add market cache specific stats
        market_stats = {
            'ttl_settings': market_cache.TTL_SETTINGS,
            'cache_type': cache_stats.get('type', 'unknown')
        }
        
        return jsonify({
            'success': True,
            'data': {
                'cache_system': cache_stats,
                'market_cache': market_stats,
                'timestamp': int(time.time())
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/clear', methods=['POST'])
@jwt_required()
@require_admin()
def clear_cache():
    """
    Clear cache entries
    Admin only endpoint
    """
    try:
        data = request.get_json() or {}
        pattern = data.get('pattern', '*')
        
        if pattern == '*':
            # Clear all cache
            cleared_count = cache_service.clear_pattern('*')
            message = f"Cleared all cache entries ({cleared_count} items)"
        else:
            # Clear specific pattern
            cleared_count = cache_service.clear_pattern(pattern)
            message = f"Cleared cache pattern '{pattern}' ({cleared_count} items)"
        
        return jsonify({
            'success': True,
            'message': message,
            'cleared_count': cleared_count,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/clear/symbol/<symbol>', methods=['DELETE'])
@jwt_required()
@require_admin()
def clear_symbol_cache(symbol):
    """
    Clear all cached data for a specific symbol
    Admin only endpoint
    """
    try:
        symbol = symbol.upper()
        cleared_count = market_cache.clear_symbol_cache(symbol)
        
        return jsonify({
            'success': True,
            'message': f"Cleared all cache for symbol {symbol}",
            'symbol': symbol,
            'cleared_count': cleared_count,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/cleanup', methods=['POST'])
@jwt_required()
@require_admin()
def cleanup_expired_cache():
    """
    Clean up expired cache entries (for memory cache)
    Admin only endpoint
    """
    try:
        cleanup_result = market_cache.clear_expired_cache()
        
        return jsonify({
            'success': True,
            'data': cleanup_result,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/test', methods=['GET'])
@jwt_required()
@require_admin()
def test_cache_performance():
    """
    Test cache performance with sample data
    Admin only endpoint
    """
    try:
        test_symbol = 'AAPL'
        
        # Test 1: Cache miss (API call)
        start_time = time.time()
        quote_data = finnhub_service.get_quote(test_symbol)
        api_time = time.time() - start_time
        
        # Test 2: Cache hit (no API call)
        start_time = time.time()
        cached_quote = finnhub_service.get_quote(test_symbol)
        cache_time = time.time() - start_time
        
        # Calculate performance improvement
        if api_time > 0:
            speed_improvement = round((api_time - cache_time) / api_time * 100, 2)
        else:
            speed_improvement = 0
        
        return jsonify({
            'success': True,
            'test_results': {
                'symbol': test_symbol,
                'api_call_time': round(api_time * 1000, 2),  # ms
                'cache_hit_time': round(cache_time * 1000, 2),  # ms
                'speed_improvement_percent': speed_improvement,
                'cache_working': cached_quote == quote_data
            },
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/warm-up', methods=['POST'])
@jwt_required()
@require_admin()
def warm_up_cache():
    """
    Pre-populate cache with popular symbols
    Admin only endpoint
    """
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'AMZN'])
        
        warmed_up = []
        failed = []
        
        for symbol in symbols:
            try:
                # Get quote and profile to warm up cache
                quote = finnhub_service.get_quote(symbol)
                profile = finnhub_service.get_company_profile(symbol)
                
                if quote and profile:
                    warmed_up.append(symbol)
                else:
                    failed.append(symbol)
                    
            except Exception as e:
                failed.append(f"{symbol}: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f"Cache warm-up completed for {len(warmed_up)} symbols",
            'warmed_up': warmed_up,
            'failed': failed,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/settings', methods=['GET'])
@jwt_required()
@require_admin()
def get_cache_settings():
    """
    Get current cache TTL settings
    Admin only endpoint
    """
    try:
        return jsonify({
            'success': True,
            'data': {
                'ttl_settings': market_cache.TTL_SETTINGS,
                'cache_type': 'redis' if cache_service.redis_available else 'memory',
                'description': {
                    'quote': 'Stock quotes - real-time data',
                    'profile': 'Company profiles - rarely changes',
                    'news': 'Market news - moderate frequency',
                    'company_news': 'Company-specific news',
                    'candles': 'Historical price data',
                    'search': 'Symbol search results',
                    'market_status': 'Market open/closed status',
                    'scanner': 'Scanner results - frequent updates',
                    'batch_quotes': 'Multiple symbol quotes'
                }
            },
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/monitor', methods=['GET'])
@jwt_required()
@require_admin()
def monitor_cache_usage():
    """
    Monitor cache usage patterns
    Admin only endpoint
    """
    try:
        cache_stats = cache_service.get_cache_stats()
        
        # Calculate hit rate if available
        hits = cache_stats.get('hits', 0)
        misses = cache_stats.get('misses', 0)
        total_requests = hits + misses
        
        hit_rate = round((hits / total_requests * 100), 2) if total_requests > 0 else 0
        
        monitoring_data = {
            'cache_stats': cache_stats,
            'performance_metrics': {
                'hit_rate_percent': hit_rate,
                'total_requests': total_requests,
                'cache_hits': hits,
                'cache_misses': misses
            },
            'recommendations': []
        }
        
        # Add recommendations based on performance
        if hit_rate < 50:
            monitoring_data['recommendations'].append("Low cache hit rate - consider increasing TTL values")
        if hit_rate > 90:
            monitoring_data['recommendations'].append("Excellent cache performance")
        if total_requests == 0:
            monitoring_data['recommendations'].append("No cache activity detected")
        
        return jsonify({
            'success': True,
            'data': monitoring_data,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

