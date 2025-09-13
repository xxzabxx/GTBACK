"""
Cache Service for GrimmTrading Platform
Provides Redis-based caching for market data to optimize API usage and performance
"""

import os
import json
import redis
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import hashlib

class CacheService:
    """Redis-based caching service for market data"""
    
    def __init__(self):
        # Try to connect to Redis (Railway add-on or local)
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
            print("✅ Redis cache connected successfully")
        except Exception as e:
            print(f"⚠️  Redis not available, using in-memory cache: {str(e)}")
            self.redis_available = False
            self.memory_cache = {}
            self.cache_timestamps = {}
    
    def _generate_key(self, prefix: str, identifier: str, **kwargs) -> str:
        """Generate a consistent cache key"""
        key_parts = [prefix, identifier]
        
        # Add any additional parameters to the key
        if kwargs:
            sorted_params = sorted(kwargs.items())
            param_str = "_".join([f"{k}:{v}" for k, v in sorted_params])
            key_parts.append(param_str)
        
        return ":".join(key_parts)
    
    def _is_expired(self, timestamp: float, ttl_seconds: int) -> bool:
        """Check if cached data is expired"""
        return time.time() - timestamp > ttl_seconds
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """
        Set a value in cache with TTL
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default 5 minutes)
        """
        try:
            cache_data = {
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl_seconds
            }
            
            if self.redis_available:
                self.redis_client.setex(key, ttl_seconds, json.dumps(cache_data))
            else:
                # In-memory fallback
                self.memory_cache[key] = cache_data
                self.cache_timestamps[key] = time.time()
            
            return True
        except Exception as e:
            print(f"Cache set error: {str(e)}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache
        Returns None if key doesn't exist or is expired
        """
        try:
            if self.redis_available:
                cached_data = self.redis_client.get(key)
                if cached_data:
                    data = json.loads(cached_data)
                    return data['value']
            else:
                # In-memory fallback
                if key in self.memory_cache:
                    cached_data = self.memory_cache[key]
                    if not self._is_expired(cached_data['timestamp'], cached_data['ttl']):
                        return cached_data['value']
                    else:
                        # Clean up expired data
                        del self.memory_cache[key]
                        if key in self.cache_timestamps:
                            del self.cache_timestamps[key]
            
            return None
        except Exception as e:
            print(f"Cache get error: {str(e)}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            if self.redis_available:
                self.redis_client.delete(key)
            else:
                if key in self.memory_cache:
                    del self.memory_cache[key]
                if key in self.cache_timestamps:
                    del self.cache_timestamps[key]
            return True
        except Exception as e:
            print(f"Cache delete error: {str(e)}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern"""
        try:
            if self.redis_available:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
            else:
                # In-memory fallback - simple pattern matching
                keys_to_delete = [k for k in self.memory_cache.keys() if pattern.replace('*', '') in k]
                for key in keys_to_delete:
                    del self.memory_cache[key]
                    if key in self.cache_timestamps:
                        del self.cache_timestamps[key]
                return len(keys_to_delete)
            return 0
        except Exception as e:
            print(f"Cache clear pattern error: {str(e)}")
            return 0
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            if self.redis_available:
                info = self.redis_client.info()
                return {
                    'type': 'redis',
                    'connected': True,
                    'used_memory': info.get('used_memory_human', 'N/A'),
                    'total_keys': self.redis_client.dbsize(),
                    'hits': info.get('keyspace_hits', 0),
                    'misses': info.get('keyspace_misses', 0)
                }
            else:
                return {
                    'type': 'memory',
                    'connected': True,
                    'total_keys': len(self.memory_cache),
                    'memory_usage': f"{len(str(self.memory_cache))} bytes"
                }
        except Exception as e:
            return {
                'type': 'error',
                'connected': False,
                'error': str(e)
            }

class MarketDataCache:
    """Specialized cache for market data with appropriate TTL values"""
    
    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        
        # Cache TTL settings (in seconds) - Increased to reduce rate limiting
        self.TTL_SETTINGS = {
            'quote': 120,          # Stock quotes - 2 minutes (reduced API calls)
            'profile': 3600,       # Company profiles - 1 hour (rarely changes)
            'news': 300,           # Market news - 5 minutes
            'company_news': 600,   # Company news - 10 minutes
            'candles': 900,        # Historical candles - 15 minutes
            'search': 1800,        # Symbol search - 30 minutes
            'market_status': 60,   # Market status - 1 minute
            'scanner': 300,        # Scanner results - 5 minutes (reduced API calls)
            'batch_quotes': 120    # Batch quotes - 2 minutes (reduced API calls)
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache using the underlying cache service"""
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set a value in cache using the underlying cache service"""
        return self.cache.set(key, value, ttl_seconds)
    
    def cache_quote(self, symbol: str, quote_data: Dict) -> bool:
        """Cache stock quote data"""
        key = self._generate_key('quote', symbol)
        return self.cache.set(key, quote_data, self.TTL_SETTINGS['quote'])
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get cached stock quote"""
        key = self._generate_key('quote', symbol)
        return self.cache.get(key)
    
    def cache_profile(self, symbol: str, profile_data: Dict) -> bool:
        """Cache company profile data"""
        key = self._generate_key('profile', symbol)
        return self.cache.set(key, profile_data, self.TTL_SETTINGS['profile'])
    
    def get_profile(self, symbol: str) -> Optional[Dict]:
        """Get cached company profile"""
        key = self._generate_key('profile', symbol)
        return self.cache.get(key)
    
    def cache_news(self, category: str, news_data: List[Dict], min_id: int = 0) -> bool:
        """Cache market news data"""
        key = self._generate_key('news', category, min_id=min_id)
        return self.cache.set(key, news_data, self.TTL_SETTINGS['news'])
    
    def get_news(self, category: str, min_id: int = 0) -> Optional[List[Dict]]:
        """Get cached market news"""
        key = self._generate_key('news', category, min_id=min_id)
        return self.cache.get(key)
    
    def cache_company_news(self, symbol: str, news_data: List[Dict], days_back: int = 7) -> bool:
        """Cache company-specific news"""
        key = self._generate_key('company_news', symbol, days=days_back)
        return self.cache.set(key, news_data, self.TTL_SETTINGS['company_news'])
    
    def get_company_news(self, symbol: str, days_back: int = 7) -> Optional[List[Dict]]:
        """Get cached company news"""
        key = self._generate_key('company_news', symbol, days=days_back)
        return self.cache.get(key)
    
    def cache_candles(self, symbol: str, resolution: str, days_back: int, candle_data: Dict, cache_key_suffix: str = "") -> bool:
        """Cache historical candle data"""
        key = self._generate_key('candles', symbol, resolution=resolution, days=days_back, suffix=cache_key_suffix)
        return self.cache.set(key, candle_data, self.TTL_SETTINGS['candles'])
    
    def get_candles(self, symbol: str, resolution: str, days_back: int, cache_key_suffix: str = "") -> Optional[Dict]:
        """Get cached candle data"""
        key = self._generate_key('candles', symbol, resolution=resolution, days=days_back, suffix=cache_key_suffix)
        return self.cache.get(key)
    
    def cache_search(self, query: str, search_results: List[Dict]) -> bool:
        """Cache symbol search results"""
        # Create a hash of the query for consistent keys
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()[:8]
        key = self._generate_key('search', query_hash)
        return self.cache.set(key, search_results, self.TTL_SETTINGS['search'])
    
    def get_search(self, query: str) -> Optional[List[Dict]]:
        """Get cached search results"""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()[:8]
        key = self._generate_key('search', query_hash)
        return self.cache.get(key)
    
    def cache_market_status(self, exchange: str, status_data: Dict) -> bool:
        """Cache market status"""
        key = self._generate_key('market_status', exchange)
        return self.cache.set(key, status_data, self.TTL_SETTINGS['market_status'])
    
    def get_market_status(self, exchange: str) -> Optional[Dict]:
        """Get cached market status"""
        key = self._generate_key('market_status', exchange)
        return self.cache.get(key)
    
    def cache_scanner_results(self, scanner_type: str, params: Dict, results: Dict) -> bool:
        """Cache scanner results"""
        # Create a hash of parameters for consistent keys
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        key = self._generate_key('scanner', scanner_type, params=params_hash)
        return self.cache.set(key, results, self.TTL_SETTINGS['scanner'])
    
    def get_scanner_results(self, scanner_type: str, params: Dict) -> Optional[Dict]:
        """Get cached scanner results"""
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        key = self._generate_key('scanner', scanner_type, params=params_hash)
        return self.cache.get(key)
    
    def cache_batch_quotes(self, symbols: List[str], quotes_data: Dict) -> bool:
        """Cache batch quote results"""
        # Sort symbols for consistent key
        symbols_key = "_".join(sorted(symbols))
        symbols_hash = hashlib.md5(symbols_key.encode()).hexdigest()[:8]
        key = self._generate_key('batch_quotes', symbols_hash)
        return self.cache.set(key, quotes_data, self.TTL_SETTINGS['batch_quotes'])
    
    def get_batch_quotes(self, symbols: List[str]) -> Optional[Dict]:
        """Get cached batch quotes"""
        symbols_key = "_".join(sorted(symbols))
        symbols_hash = hashlib.md5(symbols_key.encode()).hexdigest()[:8]
        key = self._generate_key('batch_quotes', symbols_hash)
        return self.cache.get(key)
    
    def _generate_key(self, prefix: str, identifier: str, **kwargs) -> str:
        """Generate cache key for market data"""
        return self.cache._generate_key(f"market:{prefix}", identifier, **kwargs)
    
    def clear_symbol_cache(self, symbol: str) -> int:
        """Clear all cached data for a specific symbol"""
        pattern = f"market:*:{symbol}*"
        return self.cache.clear_pattern(pattern)
    
    def clear_expired_cache(self) -> Dict:
        """Clear expired cache entries (for memory cache)"""
        if not self.cache.redis_available:
            cleared = 0
            current_time = time.time()
            
            keys_to_delete = []
            for key, cached_data in self.cache.memory_cache.items():
                if self.cache._is_expired(cached_data['timestamp'], cached_data['ttl']):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                self.cache.delete(key)
                cleared += 1
            
            return {'cleared_entries': cleared, 'remaining_entries': len(self.cache.memory_cache)}
        
        return {'message': 'Redis handles expiration automatically'}

# Create singleton instances
cache_service = CacheService()
market_cache = MarketDataCache(cache_service)


    def cache_screener_data(self, screener_key: str, data: Any, ttl_seconds: int = 300) -> bool:
        """Cache market screener data"""
        key = self._generate_key('screener', screener_key)
        return self.cache.set(key, data, ttl_seconds)
    
    def get_screener_data(self, screener_key: str) -> Optional[Any]:
        """Get cached market screener data"""
        key = self._generate_key('screener', screener_key)
        return self.cache.get(key)
    
    def set_screener_data(self, screener_key: str, data: Any, ttl_seconds: int = 300) -> bool:
        """Set market screener data in cache"""
        return self.cache_screener_data(screener_key, data, ttl_seconds)

