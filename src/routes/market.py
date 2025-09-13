"""
Market Data Routes for GrimmTrading Platform
Provides endpoints for real-time market data, quotes, charts, and news
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.services.finnhub_service import finnhub_service
from src.middleware.permissions import require_permission
from datetime import datetime
import time

market_bp = Blueprint('market', __name__)

@market_bp.route('/health', methods=['GET'])
def market_health():
    """Health check for market data service"""
    return jsonify({
        'status': 'healthy',
        'service': 'market_data',
        'timestamp': datetime.utcnow().isoformat(),
        'finnhub_configured': bool(finnhub_service.api_key)
    }), 200

@market_bp.route('/quote/<symbol>', methods=['GET'])
@jwt_required()
def get_stock_quote(symbol):
    """
    Get real-time stock quote
    Free tier access - basic quotes
    """
    try:
        symbol = symbol.upper()
        quote_data = finnhub_service.get_quote(symbol)
        
        if not quote_data:
            return jsonify({'error': 'Symbol not found or API error'}), 404
        
        return jsonify({
            'success': True,
            'data': quote_data,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/profile/<symbol>', methods=['GET'])
@jwt_required()
def get_company_profile(symbol):
    """
    Get company profile and basic info
    Includes float data for Ross Cameron filtering
    """
    try:
        symbol = symbol.upper()
        profile_data = finnhub_service.get_company_profile(symbol)
        
        if not profile_data:
            return jsonify({'error': 'Company profile not found'}), 404
        
        # Add Ross Cameron specific flags
        profile_data['is_low_float'] = profile_data.get('float', 0) <= 10_000_000
        profile_data['is_price_range'] = 2.0 <= profile_data.get('current_price', 0) <= 20.0
        
        return jsonify({
            'success': True,
            'data': profile_data,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/candles/<symbol>', methods=['GET'])
@jwt_required()
@require_permission('basic_charts')
def get_stock_candles(symbol):
    """
    Get historical candlestick data for charts
    Requires basic_charts permission (free tier)
    Supports previous=true for previous trading day data
    """
    try:
        symbol = symbol.upper()
        resolution = request.args.get('resolution', 'D')  # D, 60, 30, 15, 5, 1
        days_back = int(request.args.get('days', 30))
        previous = request.args.get('previous', 'false').lower() == 'true'
        
        # Validate resolution
        valid_resolutions = ['1', '5', '15', '30', '60', 'D', 'W', 'M']
        if resolution not in valid_resolutions:
            return jsonify({'error': 'Invalid resolution'}), 400
        
        # Get candle data with previous day support
        candle_data = finnhub_service.get_candles(symbol, resolution, days_back, previous)
        
        if not candle_data:
            return jsonify({'error': 'No candle data found'}), 404
        
        # Convert to frontend-expected format (t, o, h, l, c, v)
        formatted_data = {
            't': candle_data.get('timestamps', []),
            'o': candle_data.get('open', []),
            'h': candle_data.get('high', []),
            'l': candle_data.get('low', []),
            'c': candle_data.get('close', []),
            'v': candle_data.get('volume', []),
            'symbol': symbol
        }
        
        return jsonify({
            'success': True,
            'data': formatted_data,
            'timestamp': int(time.time()),
            'is_previous_session': previous,
            'data_type': 'previous_close' if previous else 'live',
            'resolution': resolution,
            'days_back': days_back
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/news', methods=['GET'])
@jwt_required()
@require_permission('basic_news')
def get_market_news():
    """
    Get general market news
    Requires basic_news permission (free tier)
    """
    try:
        category = request.args.get('category', 'general')
        min_id = int(request.args.get('min_id', 0))
        
        news_data = finnhub_service.get_market_news(category, min_id)
        
        return jsonify({
            'success': True,
            'data': news_data,
            'count': len(news_data),
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/news/<symbol>', methods=['GET'])
@jwt_required()
@require_permission('basic_news')
def get_company_news(symbol):
    """
    Get company-specific news
    Useful for catalyst identification
    """
    try:
        symbol = symbol.upper()
        days_back = int(request.args.get('days', 7))
        
        news_data = finnhub_service.get_company_news(symbol, days_back)
        
        return jsonify({
            'success': True,
            'data': news_data,
            'symbol': symbol,
            'count': len(news_data),
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/status', methods=['GET'])
@jwt_required()
def get_market_status():
    """
    Get market status (open/closed)
    Free access for all users
    """
    try:
        exchange = request.args.get('exchange', 'US')
        status_data = finnhub_service.get_market_status(exchange)
        
        return jsonify({
            'success': True,
            'data': status_data,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/search', methods=['GET'])
@jwt_required()
def search_symbols():
    """
    Search for stock symbols
    Free access for all users
    """
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 1:
            return jsonify({'error': 'Query parameter required'}), 400
        
        search_results = finnhub_service.search_symbols(query)
        
        return jsonify({
            'success': True,
            'data': search_results,
            'query': query,
            'count': len(search_results),
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/scanner/momentum', methods=['GET'])
@jwt_required()
@require_permission('scanners')
def get_momentum_scanner():
    """
    Ross Cameron style momentum scanner
    Requires scanners permission (premium tier)
    """
    try:
        # Get parameters for Ross Cameron filtering
        min_price = float(request.args.get('min_price', 2.0))
        max_price = float(request.args.get('max_price', 20.0))
        max_float = float(request.args.get('max_float', 10_000_000))
        min_volume = int(request.args.get('min_volume', 100000))
        min_change = float(request.args.get('min_change', 5.0))
        
        # This would require a more complex implementation
        # For now, return structure that frontend can use
        scanner_results = {
            'criteria': {
                'price_range': [min_price, max_price],
                'max_float': max_float,
                'min_volume': min_volume,
                'min_change_percent': min_change
            },
            'results': [],
            'scan_time': int(time.time()),
            'total_matches': 0
        }
        
        return jsonify({
            'success': True,
            'data': scanner_results,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/scanner/gappers', methods=['GET'])
@jwt_required()
@require_permission('scanners')
def get_premarket_gappers():
    """
    Pre-market gappers scanner
    Requires scanners permission (premium tier)
    """
    try:
        min_gap = float(request.args.get('min_gap', 10.0))  # Minimum gap %
        min_price = float(request.args.get('min_price', 2.0))
        max_price = float(request.args.get('max_price', 20.0))
        
        # Placeholder structure for gappers
        gapper_results = {
            'criteria': {
                'min_gap_percent': min_gap,
                'price_range': [min_price, max_price]
            },
            'results': [],
            'scan_time': int(time.time()),
            'total_matches': 0
        }
        
        return jsonify({
            'success': True,
            'data': gapper_results,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/batch/quotes', methods=['POST'])
@jwt_required()
@require_permission('advanced_charts')
def get_batch_quotes():
    """
    Get quotes for multiple symbols at once
    Requires advanced_charts permission (premium tier)
    """
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols or len(symbols) > 50:  # Limit batch size
            return jsonify({'error': 'Invalid symbols list (max 50)'}), 400
        
        batch_results = {}
        for symbol in symbols:
            symbol = symbol.upper()
            quote = finnhub_service.get_quote(symbol)
            if quote:
                batch_results[symbol] = quote
        
        return jsonify({
            'success': True,
            'data': batch_results,
            'requested_count': len(symbols),
            'returned_count': len(batch_results),
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@market_bp.route('/test', methods=['GET'])
@jwt_required()
def test_finnhub_connection():
    """
    Test Finnhub API connection
    Admin/development endpoint
    """
    try:
        # Test with AAPL quote
        test_quote = finnhub_service.get_quote('AAPL')
        test_profile = finnhub_service.get_company_profile('AAPL')
        
        return jsonify({
            'success': True,
            'finnhub_api_key_configured': bool(finnhub_service.api_key),
            'test_quote': test_quote,
            'test_profile': test_profile,
            'timestamp': int(time.time())
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

