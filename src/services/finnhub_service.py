"""
Finnhub API Service for GrimmTrading Platform
Provides market data integration for Ross Cameron-style momentum trading
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

class FinnhubService:
    """Service class for interacting with Finnhub API"""
    
    def __init__(self):
        self.api_key = os.getenv('FINNHUB_API_KEY')
        self.base_url = 'https://finnhub.io/api/v1'
        self.session = requests.Session()
        
        if not self.api_key:
            raise ValueError("FINNHUB_API_KEY not found in environment variables")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to Finnhub API"""
        if params is None:
            params = {}
        
        params['token'] = self.api_key
        
        try:
            response = self.session.get(f"{self.base_url}/{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Finnhub API error: {str(e)}")
            return {}
    
    def get_quote(self, symbol: str) -> Dict:
        """
        Get real-time quote for a stock symbol
        Returns: Current price, change, percent change, high, low, open, previous close
        """
        data = self._make_request('quote', {'symbol': symbol})
        
        if data and 'c' in data:
            return {
                'symbol': symbol,
                'current_price': data.get('c', 0),  # Current price
                'change': data.get('d', 0),         # Change
                'percent_change': data.get('dp', 0), # Percent change
                'high': data.get('h', 0),           # High price of the day
                'low': data.get('l', 0),            # Low price of the day
                'open': data.get('o', 0),           # Open price of the day
                'previous_close': data.get('pc', 0), # Previous close price
                'timestamp': int(time.time())
            }
        return {}
    
    def get_company_profile(self, symbol: str) -> Dict:
        """
        Get company profile including float data
        Returns: Company info, market cap, float, industry, etc.
        """
        data = self._make_request('stock/profile2', {'symbol': symbol})
        
        if data:
            return {
                'symbol': symbol,
                'name': data.get('name', ''),
                'ticker': data.get('ticker', symbol),
                'exchange': data.get('exchange', ''),
                'industry': data.get('finnhubIndustry', ''),
                'market_cap': data.get('marketCapitalization', 0),
                'shares_outstanding': data.get('shareOutstanding', 0),
                'float': data.get('shareOutstanding', 0),  # Approximate float
                'country': data.get('country', ''),
                'currency': data.get('currency', 'USD'),
                'logo': data.get('logo', ''),
                'weburl': data.get('weburl', ''),
                'ipo_date': data.get('ipo', '')
            }
        return {}
    
    def get_candles(self, symbol: str, resolution: str = 'D', days_back: int = 30) -> Dict:
        """
        Get historical candlestick data
        Args:
            symbol: Stock symbol
            resolution: 1, 5, 15, 30, 60, D, W, M
            days_back: Number of days to look back
        """
        end_time = int(time.time())
        start_time = end_time - (days_back * 24 * 60 * 60)
        
        data = self._make_request('stock/candle', {
            'symbol': symbol,
            'resolution': resolution,
            'from': start_time,
            'to': end_time
        })
        
        if data and data.get('s') == 'ok':
            return {
                'symbol': symbol,
                'resolution': resolution,
                'timestamps': data.get('t', []),
                'open': data.get('o', []),
                'high': data.get('h', []),
                'low': data.get('l', []),
                'close': data.get('c', []),
                'volume': data.get('v', [])
            }
        return {}
    
    def get_market_news(self, category: str = 'general', min_id: int = 0) -> List[Dict]:
        """
        Get market news
        Args:
            category: general, forex, crypto, merger
            min_id: Minimum news ID for pagination
        """
        data = self._make_request('news', {
            'category': category,
            'minId': min_id
        })
        
        if isinstance(data, list):
            return [{
                'id': item.get('id', 0),
                'headline': item.get('headline', ''),
                'summary': item.get('summary', ''),
                'source': item.get('source', ''),
                'url': item.get('url', ''),
                'image': item.get('image', ''),
                'datetime': item.get('datetime', 0),
                'category': item.get('category', ''),
                'related': item.get('related', '')
            } for item in data]
        return []
    
    def get_company_news(self, symbol: str, days_back: int = 7) -> List[Dict]:
        """
        Get company-specific news
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        data = self._make_request('company-news', {
            'symbol': symbol,
            'from': start_date,
            'to': end_date
        })
        
        if isinstance(data, list):
            return [{
                'headline': item.get('headline', ''),
                'summary': item.get('summary', ''),
                'source': item.get('source', ''),
                'url': item.get('url', ''),
                'image': item.get('image', ''),
                'datetime': item.get('datetime', 0),
                'category': item.get('category', ''),
                'related': item.get('related', '')
            } for item in data]
        return []
    
    def get_market_status(self, exchange: str = 'US') -> Dict:
        """
        Get market status (open/closed)
        """
        # Finnhub doesn't have a direct market status endpoint
        # We'll determine based on current time and trading hours
        now = datetime.now()
        
        # US market hours: 9:30 AM - 4:00 PM ET (Monday-Friday)
        if exchange == 'US':
            # Simplified market hours check
            weekday = now.weekday()  # 0 = Monday, 6 = Sunday
            hour = now.hour
            
            is_trading_day = weekday < 5  # Monday-Friday
            is_trading_hours = 9 <= hour < 16  # 9 AM - 4 PM (simplified)
            
            return {
                'exchange': exchange,
                'is_open': is_trading_day and is_trading_hours,
                'session': 'market' if is_trading_hours else 'closed',
                'timezone': 'America/New_York',
                'local_time': now.isoformat(),
                'next_open': None,  # Could be calculated
                'next_close': None  # Could be calculated
            }
        
        return {'exchange': exchange, 'is_open': False}
    
    def search_symbols(self, query: str) -> List[Dict]:
        """
        Search for stock symbols
        """
        data = self._make_request('search', {'q': query})
        
        if data and 'result' in data:
            return [{
                'symbol': item.get('symbol', ''),
                'description': item.get('description', ''),
                'display_symbol': item.get('displaySymbol', ''),
                'type': item.get('type', '')
            } for item in data['result']]
        return []
    
    def get_top_gainers_losers(self) -> Dict:
        """
        Get top gainers and losers (US market)
        Note: This endpoint might require premium subscription
        """
        # This is a placeholder - Finnhub's free tier might not include this
        # We would need to implement our own logic using quote data
        return {
            'gainers': [],
            'losers': [],
            'most_active': []
        }
    
    def get_momentum_stocks(self, min_price: float = 2.0, max_price: float = 20.0) -> List[Dict]:
        """
        Get momentum stocks matching Ross Cameron criteria
        This is a custom implementation using available data
        """
        # This would require multiple API calls and custom logic
        # For now, return placeholder structure
        return []
    
    def is_low_float_stock(self, symbol: str, max_float: float = 10_000_000) -> bool:
        """
        Check if stock has low float (under specified amount)
        """
        profile = self.get_company_profile(symbol)
        if profile and 'float' in profile:
            return profile['float'] <= max_float
        return False

# Create singleton instance
finnhub_service = FinnhubService()

