"""
Finnhub API Service for GrimmTrading Platform
Provides market data integration for Ross Cameron-style momentum trading
Now with intelligent caching to optimize API usage
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

class FinnhubService:
    """Service class for interacting with Finnhub API with caching support"""
    
    def __init__(self):
        self.api_key = os.getenv('FINNHUB_API_KEY')
        self.base_url = 'https://finnhub.io/api/v1'
        self.session = requests.Session()
        
        # Import cache after initialization to avoid circular imports
        from src.services.cache_service import market_cache
        self.cache = market_cache
        
        if not self.api_key:
            raise ValueError("FINNHUB_API_KEY not found in environment variables")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to Finnhub API with rate limiting"""
        if params is None:
            params = {}
        
        params['token'] = self.api_key
        
        try:
            # Add delay to respect rate limits - Increased to reduce 429 errors
            time.sleep(0.5)  # 500ms delay between requests to prevent rate limiting
            
            response = self.session.get(f"{self.base_url}/{endpoint}", params=params)
            
            if response.status_code == 429:
                print(f"Finnhub API rate limit hit for {endpoint}, using cached data if available")
                return {}
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Finnhub API error: {str(e)}")
            return {}
    
    def get_quote(self, symbol: str) -> Dict:
        """
        Get real-time quote for a stock symbol with caching
        Returns: Current price, change, percent change, high, low, open, previous close
        """
        # Try cache first
        cached_quote = self.cache.get_quote(symbol)
        if cached_quote:
            return cached_quote
        
        # Fetch from API
        data = self._make_request('quote', {'symbol': symbol})
        
        if data and 'c' in data:
            quote_data = {
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
            
            # Cache the result
            self.cache.cache_quote(symbol, quote_data)
            return quote_data
        
        return {}
    
    def get_company_profile(self, symbol: str) -> Dict:
        """
        Get company profile including float data with caching
        Returns: Company info, market cap, float, industry, etc.
        """
        # Try cache first
        cached_profile = self.cache.get_profile(symbol)
        if cached_profile:
            return cached_profile
        
        # Fetch from API
        data = self._make_request('stock/profile2', {'symbol': symbol})
        
        if data:
            profile_data = {
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
            
            # Cache the result
            self.cache.cache_profile(symbol, profile_data)
            return profile_data
        
        return {}
    
    def get_candles(self, symbol: str, resolution: str = 'D', days_back: int = 30, previous: bool = False) -> Dict:
        """
        Get historical candlestick data with caching
        Args:
            symbol: Stock symbol
            resolution: 1, 5, 15, 30, 60, D, W, M
            days_back: Number of days to look back
            previous: If True, get previous trading day data
        """
        # Try cache first
        cache_key_suffix = "_prev" if previous else ""
        cached_candles = self.cache.get_candles(symbol, resolution, days_back, cache_key_suffix)
        if cached_candles:
            return cached_candles
        
        # Calculate time range based on previous parameter
        if previous:
            # Get previous trading day data
            end_time = int(time.time()) - (24 * 60 * 60)  # Yesterday
            # Skip weekends - if it's Monday, go back to Friday
            end_date = datetime.fromtimestamp(end_time)
            while end_date.weekday() > 4:  # 0=Monday, 4=Friday
                end_time -= (24 * 60 * 60)
                end_date = datetime.fromtimestamp(end_time)
            start_time = end_time - (days_back * 24 * 60 * 60)
        else:
            # Get current/recent data
            end_time = int(time.time())
            start_time = end_time - (days_back * 24 * 60 * 60)
        
        data = self._make_request('stock/candle', {
            'symbol': symbol,
            'resolution': resolution,
            'from': start_time,
            'to': end_time
        })
        
        if data and data.get('s') == 'ok':
            candle_data = {
                'symbol': symbol,
                'resolution': resolution,
                'timestamps': data.get('t', []),
                'open': data.get('o', []),
                'high': data.get('h', []),
                'low': data.get('l', []),
                'close': data.get('c', []),
                'volume': data.get('v', [])
            }
            
            # Cache the result
            self.cache.cache_candles(symbol, resolution, days_back, candle_data, cache_key_suffix)
            return candle_data
        
        return {}
    
    def get_market_news(self, category: str = 'general', min_id: int = 0) -> List[Dict]:
        """
        Get market news with caching
        Args:
            category: general, forex, crypto, merger
            min_id: Minimum news ID for pagination
        """
        # Try cache first
        cached_news = self.cache.get_news(category, min_id)
        if cached_news:
            return cached_news
        
        # Fetch from API
        data = self._make_request('news', {
            'category': category,
            'minId': min_id
        })
        
        if isinstance(data, list):
            news_data = [{
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
            
            # Cache the result
            self.cache.cache_news(category, news_data, min_id)
            return news_data
        
        return []
    
    def get_company_news(self, symbol: str, days_back: int = 7) -> List[Dict]:
        """
        Get company-specific news with caching
        """
        # Try cache first
        cached_news = self.cache.get_company_news(symbol, days_back)
        if cached_news:
            return cached_news
        
        # Fetch from API
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        data = self._make_request('company-news', {
            'symbol': symbol,
            'from': start_date,
            'to': end_date
        })
        
        if isinstance(data, list):
            news_data = [{
                'headline': item.get('headline', ''),
                'summary': item.get('summary', ''),
                'source': item.get('source', ''),
                'url': item.get('url', ''),
                'image': item.get('image', ''),
                'datetime': item.get('datetime', 0),
                'category': item.get('category', ''),
                'related': item.get('related', '')
            } for item in data]
            
            # Cache the result
            self.cache.cache_company_news(symbol, news_data, days_back)
            return news_data
        
        return []
    
    def get_market_status(self, exchange: str = 'US') -> Dict:
        """
        Get market status (open/closed) with caching
        """
        # Try cache first
        cached_status = self.cache.get_market_status(exchange)
        if cached_status:
            return cached_status
        
        # Calculate market status
        now = datetime.now()
        
        # US market hours: 9:30 AM - 4:00 PM ET (Monday-Friday)
        if exchange == 'US':
            # Simplified market hours check
            weekday = now.weekday()  # 0 = Monday, 6 = Sunday
            hour = now.hour
            
            is_trading_day = weekday < 5  # Monday-Friday
            is_trading_hours = 9 <= hour < 16  # 9 AM - 4 PM (simplified)
            
            status_data = {
                'exchange': exchange,
                'is_open': is_trading_day and is_trading_hours,
                'session': 'market' if is_trading_hours else 'closed',
                'timezone': 'America/New_York',
                'local_time': now.isoformat(),
                'next_open': None,  # Could be calculated
                'next_close': None  # Could be calculated
            }
            
            # Cache the result
            self.cache.cache_market_status(exchange, status_data)
            return status_data
        
        return {'exchange': exchange, 'is_open': False}
    
    def search_symbols(self, query: str) -> List[Dict]:
        """
        Search for stock symbols with caching
        """
        # Try cache first
        cached_results = self.cache.get_search(query)
        if cached_results:
            return cached_results
        
        # Fetch from API
        data = self._make_request('search', {'q': query})
        
        if data and 'result' in data:
            search_results = [{
                'symbol': item.get('symbol', ''),
                'description': item.get('description', ''),
                'display_symbol': item.get('displaySymbol', ''),
                'type': item.get('type', '')
            } for item in data['result']]
            
            # Cache the result
            self.cache.cache_search(query, search_results)
            return search_results
        
        return []
    
    def get_batch_quotes(self, symbols: List[str]) -> Dict:
        """
        Get quotes for multiple symbols with intelligent caching
        """
        # Try cache first
        cached_batch = self.cache.get_batch_quotes(symbols)
        if cached_batch:
            return cached_batch
        
        # Fetch individual quotes (some may be cached)
        batch_results = {}
        uncached_symbols = []
        
        # Check cache for each symbol
        for symbol in symbols:
            cached_quote = self.cache.get_quote(symbol)
            if cached_quote:
                batch_results[symbol] = cached_quote
            else:
                uncached_symbols.append(symbol)
        
        # Fetch uncached symbols from API
        for symbol in uncached_symbols:
            quote = self.get_quote(symbol)  # This will cache individual quotes
            if quote:
                batch_results[symbol] = quote
        
        # Cache the batch result
        if batch_results:
            self.cache.cache_batch_quotes(symbols, batch_results)
        
        return batch_results
    
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
        Uses cached profile data when available
        """
        profile = self.get_company_profile(symbol)  # Uses cache
        if profile and 'float' in profile:
            return profile['float'] <= max_float
        return False
    
    def clear_symbol_cache(self, symbol: str) -> int:
        """Clear all cached data for a specific symbol"""
        return self.cache.clear_symbol_cache(symbol)
    
    def get_stock_symbols(self, exchange: str = 'US') -> List[Dict]:
        """
        Get list of stock symbols for a given exchange
        Returns: List of stock symbols with metadata
        """
        cache_key = f"stock_symbols_{exchange}"
        cached_symbols = self.cache.get(cache_key)
        if cached_symbols:
            return cached_symbols
        
        endpoint = "stock/symbol"
        params = {"exchange": exchange}
        
        symbols_data = self._make_request(endpoint, params)
        
        if symbols_data:
            # Cache for 1 hour (symbols don't change frequently)
            self.cache.set(cache_key, symbols_data, 3600)
        
        return symbols_data if symbols_data else []
    
    def get_cache_stats(self) -> Dict:
        return self.cache.cache.get_cache_stats()

# Create singleton instance
finnhub_service = FinnhubService()

