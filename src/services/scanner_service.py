"""
Ross Cameron-Style Stock Scanner Service
Implements momentum, gappers, and low float scanners based on Warrior Trading methodology
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.services.finnhub_service import FinnhubService
from src.services.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)

class ScannerService:
    def __init__(self):
        self.finnhub = FinnhubService()
        self.cache = CacheService()
        
        # Ross Cameron's exact criteria
        self.PRICE_MIN = 1.00  # Avoid penny stocks
        self.PRICE_MAX = 20.00  # Small account focus
        self.MIN_RELATIVE_VOLUME = 5.0  # 5x above average minimum
        self.MIN_PERCENT_CHANGE = 10.0  # 10% minimum daily gain
        self.MAX_FLOAT = 20_000_000  # 20M shares maximum
        self.PREFERRED_MAX_FLOAT = 10_000_000  # 10M preferred
        
        # Scanner refresh intervals (seconds)
        self.CACHE_TTL = 30  # 30 seconds for real-time feel
        
    async def get_momentum_scanner(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ross Cameron Momentum Scanner
        Finds stocks with high relative volume, strong % gains, and momentum
        """
        cache_key = f"scanner:momentum:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Get market movers and filter by Ross Cameron criteria
            stocks = await self._get_market_movers()
            momentum_stocks = []
            
            for stock in stocks:
                try:
                    # Get detailed stock data
                    quote = await self._get_stock_quote(stock['symbol'])
                    profile = await self._get_stock_profile(stock['symbol'])
                    
                    if not quote or not profile:
                        continue
                        
                    # Apply Ross Cameron momentum criteria
                    if self._is_momentum_candidate(quote, profile):
                        momentum_data = {
                            'symbol': stock['symbol'],
                            'company_name': profile.get('name', ''),
                            'price': quote.get('c', 0),
                            'change': quote.get('d', 0),
                            'percent_change': quote.get('dp', 0),
                            'volume': quote.get('v', 0),
                            'relative_volume': self._calculate_relative_volume(quote, profile),
                            'float': profile.get('shareOutstanding', 0),
                            'market_cap': profile.get('marketCapitalization', 0),
                            'news_catalyst': await self._has_recent_news(stock['symbol']),
                            'ross_score': self._calculate_ross_score(quote, profile),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        momentum_stocks.append(momentum_data)
                        
                except Exception as e:
                    logger.warning(f"Error processing {stock['symbol']}: {e}")
                    continue
                    
            # Sort by Ross score (highest first)
            momentum_stocks.sort(key=lambda x: x['ross_score'], reverse=True)
            result = momentum_stocks[:limit]
            
            # Cache for 30 seconds
            self.cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"Error in momentum scanner: {e}")
            return []
    
    async def get_gappers_scanner(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ross Cameron Pre-Market Gappers Scanner
        Finds stocks gapping up with high volume and news catalysts
        """
        cache_key = f"scanner:gappers:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Get pre-market movers
            stocks = await self._get_premarket_movers()
            gapper_stocks = []
            
            for stock in stocks:
                try:
                    quote = await self._get_stock_quote(stock['symbol'])
                    profile = await self._get_stock_profile(stock['symbol'])
                    
                    if not quote or not profile:
                        continue
                        
                    # Apply gapper criteria
                    if self._is_gapper_candidate(quote, profile):
                        gap_data = {
                            'symbol': stock['symbol'],
                            'company_name': profile.get('name', ''),
                            'price': quote.get('c', 0),
                            'previous_close': quote.get('pc', 0),
                            'gap_percent': self._calculate_gap_percent(quote),
                            'change': quote.get('d', 0),
                            'percent_change': quote.get('dp', 0),
                            'volume': quote.get('v', 0),
                            'relative_volume': self._calculate_relative_volume(quote, profile),
                            'float': profile.get('shareOutstanding', 0),
                            'news_catalyst': await self._has_recent_news(stock['symbol']),
                            'gap_score': self._calculate_gap_score(quote, profile),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        gapper_stocks.append(gap_data)
                        
                except Exception as e:
                    logger.warning(f"Error processing gapper {stock['symbol']}: {e}")
                    continue
                    
            # Sort by gap score
            gapper_stocks.sort(key=lambda x: x['gap_score'], reverse=True)
            result = gapper_stocks[:limit]
            
            self.cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"Error in gappers scanner: {e}")
            return []
    
    async def get_low_float_scanner(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ross Cameron Low Float Scanner
        Finds stocks with <10M float, high volume, and momentum potential
        """
        cache_key = f"scanner:low_float:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Get market movers and filter for low float
            stocks = await self._get_market_movers()
            low_float_stocks = []
            
            for stock in stocks:
                try:
                    quote = await self._get_stock_quote(stock['symbol'])
                    profile = await self._get_stock_profile(stock['symbol'])
                    
                    if not quote or not profile:
                        continue
                        
                    # Apply low float criteria
                    if self._is_low_float_candidate(quote, profile):
                        float_data = {
                            'symbol': stock['symbol'],
                            'company_name': profile.get('name', ''),
                            'price': quote.get('c', 0),
                            'change': quote.get('d', 0),
                            'percent_change': quote.get('dp', 0),
                            'volume': quote.get('v', 0),
                            'relative_volume': self._calculate_relative_volume(quote, profile),
                            'float': profile.get('shareOutstanding', 0),
                            'float_turnover': self._calculate_float_turnover(quote, profile),
                            'market_cap': profile.get('marketCapitalization', 0),
                            'news_catalyst': await self._has_recent_news(stock['symbol']),
                            'explosive_score': self._calculate_explosive_score(quote, profile),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        low_float_stocks.append(float_data)
                        
                except Exception as e:
                    logger.warning(f"Error processing low float {stock['symbol']}: {e}")
                    continue
                    
            # Sort by explosive score
            low_float_stocks.sort(key=lambda x: x['explosive_score'], reverse=True)
            result = low_float_stocks[:limit]
            
            self.cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"Error in low float scanner: {e}")
            return []
    
    def _is_momentum_candidate(self, quote: Dict, profile: Dict) -> bool:
        """Check if stock meets Ross Cameron momentum criteria"""
        price = quote.get('c', 0)
        percent_change = quote.get('dp', 0)
        volume = quote.get('v', 0)
        float_shares = profile.get('shareOutstanding', float('inf'))
        
        return (
            self.PRICE_MIN <= price <= self.PRICE_MAX and
            percent_change >= self.MIN_PERCENT_CHANGE and
            volume > 100_000 and  # Minimum volume threshold
            float_shares <= self.MAX_FLOAT and
            self._calculate_relative_volume(quote, profile) >= self.MIN_RELATIVE_VOLUME
        )
    
    def _is_gapper_candidate(self, quote: Dict, profile: Dict) -> bool:
        """Check if stock meets gapper criteria"""
        price = quote.get('c', 0)
        gap_percent = self._calculate_gap_percent(quote)
        volume = quote.get('v', 0)
        float_shares = profile.get('shareOutstanding', float('inf'))
        
        return (
            self.PRICE_MIN <= price <= self.PRICE_MAX and
            gap_percent >= 5.0 and  # 5% minimum gap
            volume > 100_000 and
            float_shares <= self.MAX_FLOAT and
            self._calculate_relative_volume(quote, profile) >= 3.0  # Lower threshold for gappers
        )
    
    def _is_low_float_candidate(self, quote: Dict, profile: Dict) -> bool:
        """Check if stock meets low float criteria"""
        price = quote.get('c', 0)
        percent_change = quote.get('dp', 0)
        volume = quote.get('v', 0)
        float_shares = profile.get('shareOutstanding', float('inf'))
        
        return (
            self.PRICE_MIN <= price <= self.PRICE_MAX and
            percent_change >= 5.0 and  # Lower % threshold for low float
            volume > 50_000 and  # Lower volume threshold
            float_shares <= self.PREFERRED_MAX_FLOAT and  # Strict 10M limit
            self._calculate_relative_volume(quote, profile) >= 2.0  # 2x minimum
        )
    
    def _calculate_relative_volume(self, quote: Dict, profile: Dict) -> float:
        """Calculate relative volume ratio"""
        current_volume = quote.get('v', 0)
        avg_volume = profile.get('avgVolume10Day', 1)
        
        if avg_volume == 0:
            return 0
        return current_volume / avg_volume
    
    def _calculate_gap_percent(self, quote: Dict) -> float:
        """Calculate gap percentage from previous close"""
        current_price = quote.get('c', 0)
        previous_close = quote.get('pc', 0)
        
        if previous_close == 0:
            return 0
        return ((current_price - previous_close) / previous_close) * 100
    
    def _calculate_float_turnover(self, quote: Dict, profile: Dict) -> float:
        """Calculate what percentage of float has traded"""
        volume = quote.get('v', 0)
        float_shares = profile.get('shareOutstanding', 1)
        
        if float_shares == 0:
            return 0
        return (volume / float_shares) * 100
    
    def _calculate_ross_score(self, quote: Dict, profile: Dict) -> float:
        """
        Calculate Ross Cameron quality score
        Higher score = better momentum candidate
        """
        price = quote.get('c', 0)
        percent_change = quote.get('dp', 0)
        relative_volume = self._calculate_relative_volume(quote, profile)
        float_shares = profile.get('shareOutstanding', float('inf'))
        
        score = 0
        
        # Percent change score (0-40 points)
        score += min(percent_change * 2, 40)
        
        # Relative volume score (0-30 points)
        score += min(relative_volume * 3, 30)
        
        # Float score (0-20 points) - lower float = higher score
        if float_shares <= 5_000_000:
            score += 20
        elif float_shares <= 10_000_000:
            score += 15
        elif float_shares <= 20_000_000:
            score += 10
        
        # Price range score (0-10 points)
        if 2 <= price <= 10:
            score += 10
        elif 1 <= price <= 20:
            score += 5
        
        return round(score, 2)
    
    def _calculate_gap_score(self, quote: Dict, profile: Dict) -> float:
        """Calculate gapper quality score"""
        gap_percent = self._calculate_gap_percent(quote)
        relative_volume = self._calculate_relative_volume(quote, profile)
        float_shares = profile.get('shareOutstanding', float('inf'))
        
        score = 0
        
        # Gap percentage score
        score += min(gap_percent * 3, 50)
        
        # Relative volume score
        score += min(relative_volume * 2, 30)
        
        # Float score
        if float_shares <= 10_000_000:
            score += 20
        
        return round(score, 2)
    
    def _calculate_explosive_score(self, quote: Dict, profile: Dict) -> float:
        """Calculate low float explosive potential score"""
        percent_change = quote.get('dp', 0)
        relative_volume = self._calculate_relative_volume(quote, profile)
        float_turnover = self._calculate_float_turnover(quote, profile)
        float_shares = profile.get('shareOutstanding', float('inf'))
        
        score = 0
        
        # Float size score (smaller = higher score)
        if float_shares <= 2_000_000:
            score += 40
        elif float_shares <= 5_000_000:
            score += 30
        elif float_shares <= 10_000_000:
            score += 20
        
        # Float turnover score
        score += min(float_turnover * 2, 30)
        
        # Relative volume score
        score += min(relative_volume * 2, 20)
        
        # Percent change score
        score += min(percent_change, 10)
        
        return round(score, 2)
    
    async def _get_market_movers(self) -> List[Dict]:
        """Get market movers from Finnhub"""
        try:
            # Use Finnhub's stock symbols and filter for US stocks
            symbols = await self._get_active_symbols()
            return [{'symbol': symbol} for symbol in symbols[:100]]  # Top 100 active
        except Exception as e:
            logger.error(f"Error getting market movers: {e}")
            return []
    
    async def _get_premarket_movers(self) -> List[Dict]:
        """Get pre-market movers"""
        # For now, use same as market movers
        # In production, would use pre-market specific data
        return await self._get_market_movers()
    
    async def _get_active_symbols(self) -> List[str]:
        """Get list of active US stock symbols"""
        # Common active symbols for testing
        # In production, would fetch from Finnhub stock symbols endpoint
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'AMD', 'INTC', 'CRM', 'ORCL', 'ADBE', 'PYPL', 'UBER', 'LYFT',
            'SNAP', 'TWTR', 'SQ', 'ROKU', 'ZM', 'PTON', 'DOCU', 'SHOP'
        ]
    
    async def _get_stock_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time stock quote"""
        try:
            # Use synchronous method since FinnhubService is not async
            return self.finnhub.get_quote(symbol)
        except Exception as e:
            logger.warning(f"Error getting quote for {symbol}: {e}")
            return None
    
    async def _get_stock_profile(self, symbol: str) -> Optional[Dict]:
        """Get stock company profile"""
        try:
            # Use synchronous method since FinnhubService is not async
            return self.finnhub.get_company_profile(symbol)
        except Exception as e:
            logger.warning(f"Error getting profile for {symbol}: {e}")
            return None
    
    async def _has_recent_news(self, symbol: str) -> bool:
        """Check if stock has recent news catalyst"""
        try:
            # Check for news in last 24 hours
            news = self.finnhub.get_company_news(symbol, days=1)
            return len(news) > 0
        except Exception:
            return False

