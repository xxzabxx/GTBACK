"""
Efficient Ross Cameron-Style Stock Scanner Service
Uses market screening APIs instead of individual quote fetching to prevent rate limiting
Implements momentum, gappers, and low float scanners based on Warrior Trading methodology
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.services.finnhub_service import FinnhubService
from src.services.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)

class EfficientScannerService:
    def __init__(self):
        self.finnhub = FinnhubService()
        self.cache = CacheService()
        
        # Ross Cameron's exact criteria
        self.PRICE_MIN = 2.00  # Avoid penny stocks
        self.PRICE_MAX = 20.00  # Small account focus
        self.MIN_RELATIVE_VOLUME = 5.0  # 5x above average minimum
        self.MIN_PERCENT_CHANGE = 10.0  # 10% minimum daily gain
        self.MAX_FLOAT = 10_000_000  # 10M shares maximum
        self.MIN_VOLUME = 100_000  # Minimum daily volume
        
        # Scanner refresh intervals (seconds) - Optimized for API efficiency
        self.CACHE_TTL = 300  # 5 minutes to reduce rate limiting
        
    async def get_momentum_scanner(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ross Cameron Momentum Scanner - Uses market screening API
        Finds stocks with high relative volume, strong % gains, and momentum
        """
        cache_key = f"scanner:momentum:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Use market screening API instead of individual quotes
            momentum_candidates = self.finnhub.get_momentum_stocks(
                min_price=self.PRICE_MIN,
                max_price=self.PRICE_MAX,
                min_change=self.MIN_PERCENT_CHANGE
            )
            
            momentum_stocks = []
            
            # Process the pre-screened results
            for stock in momentum_candidates[:50]:  # Limit processing to top 50
                try:
                    symbol = stock['symbol']
                    price = stock['price']
                    change_pct = stock['change_percentage']
                    volume = stock.get('volume', 0)
                    
                    # Apply Ross Cameron criteria to pre-screened results
                    if (self.PRICE_MIN <= price <= self.PRICE_MAX and 
                        change_pct >= self.MIN_PERCENT_CHANGE and
                        volume >= self.MIN_VOLUME):
                        
                        # Only fetch additional data for qualifying stocks
                        profile = await self._get_cached_profile(symbol)
                        float_shares = profile.get('shareOutstanding', float('inf')) if profile else float('inf')
                        
                        if float_shares <= self.MAX_FLOAT:
                            momentum_data = {
                                'symbol': symbol,
                                'company_name': profile.get('name', '') if profile else '',
                                'price': price,
                                'change': stock.get('change', 0),
                                'percent_change': change_pct,
                                'volume': volume,
                                'relative_volume': self._estimate_relative_volume(volume),
                                'float': float_shares,
                                'market_cap': stock.get('market_cap', 0),
                                'ross_score': self._calculate_ross_score_from_data(price, change_pct, volume, float_shares),
                                'timestamp': datetime.utcnow().isoformat()
                            }
                            momentum_stocks.append(momentum_data)
                            
                except Exception as e:
                    logger.warning(f"Error processing momentum stock {stock.get('symbol', 'unknown')}: {e}")
                    continue
            
            # Sort by Ross score (highest first)
            momentum_stocks.sort(key=lambda x: x['ross_score'], reverse=True)
            result = momentum_stocks[:limit]
            
            # Cache the results
            self.cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"Error in momentum scanner: {e}")
            return []
    
    async def get_gappers_scanner(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ross Cameron Gappers Scanner - Uses premarket movers API
        Finds pre-market gap stocks with catalyst potential
        """
        cache_key = f"scanner:gappers:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Use premarket movers API instead of individual quotes
            premarket_candidates = self.finnhub.get_premarket_movers(min_gap=5.0)
            
            gapper_stocks = []
            
            for stock in premarket_candidates[:50]:  # Limit processing
                try:
                    symbol = stock['symbol']
                    price = stock['price']
                    change_pct = stock['change_percentage']
                    volume = stock.get('volume', 0)
                    
                    # Apply gapper criteria
                    if (self.PRICE_MIN <= price <= self.PRICE_MAX and 
                        change_pct >= 5.0 and  # Lower threshold for gappers
                        volume >= self.MIN_VOLUME):
                        
                        # Only fetch profile for qualifying stocks
                        profile = await self._get_cached_profile(symbol)
                        float_shares = profile.get('shareOutstanding', float('inf')) if profile else float('inf')
                        
                        if float_shares <= self.MAX_FLOAT:
                            gap_data = {
                                'symbol': symbol,
                                'company_name': profile.get('name', '') if profile else '',
                                'price': price,
                                'previous_close': stock.get('previous_close', 0),
                                'gap_percent': change_pct,
                                'change': stock.get('change', 0),
                                'percent_change': change_pct,
                                'volume': volume,
                                'relative_volume': self._estimate_relative_volume(volume),
                                'float': float_shares,
                                'gap_score': self._calculate_gap_score_from_data(price, change_pct, volume, float_shares),
                                'timestamp': datetime.utcnow().isoformat()
                            }
                            gapper_stocks.append(gap_data)
                            
                except Exception as e:
                    logger.warning(f"Error processing gapper {stock.get('symbol', 'unknown')}: {e}")
                    continue
            
            # Sort by gap score
            gapper_stocks.sort(key=lambda x: x['gap_score'], reverse=True)
            result = gapper_stocks[:limit]
            
            # Cache the results
            self.cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"Error in gappers scanner: {e}")
            return []
    
    async def get_low_float_scanner(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Ross Cameron Low Float Scanner - Uses high volume screening
        Finds explosive low float candidates with volume surges
        """
        cache_key = f"scanner:low_float:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Use high volume screening API
            high_volume_candidates = self.finnhub.get_high_volume_stocks(min_volume=500000)
            
            low_float_stocks = []
            
            for stock in high_volume_candidates[:50]:  # Limit processing
                try:
                    symbol = stock['symbol']
                    price = stock['price']
                    volume = stock['volume']
                    change_pct = stock.get('change_percentage', 0)
                    
                    # Apply low float criteria
                    if (self.PRICE_MIN <= price <= self.PRICE_MAX and 
                        change_pct >= 5.0 and  # Lower threshold for low float
                        volume >= 500000):  # High volume requirement
                        
                        # Check float requirement
                        profile = await self._get_cached_profile(symbol)
                        float_shares = profile.get('shareOutstanding', float('inf')) if profile else float('inf')
                        
                        if float_shares <= self.MAX_FLOAT:
                            float_data = {
                                'symbol': symbol,
                                'company_name': profile.get('name', '') if profile else '',
                                'price': price,
                                'change': change_pct * price / 100,  # Estimate change
                                'percent_change': change_pct,
                                'volume': volume,
                                'relative_volume': self._estimate_relative_volume(volume),
                                'float': float_shares,
                                'float_turnover': self._calculate_float_turnover(volume, float_shares),
                                'market_cap': profile.get('marketCapitalization', 0) if profile else 0,
                                'explosive_score': self._calculate_explosive_score_from_data(price, change_pct, volume, float_shares),
                                'timestamp': datetime.utcnow().isoformat()
                            }
                            low_float_stocks.append(float_data)
                            
                except Exception as e:
                    logger.warning(f"Error processing low float stock {stock.get('symbol', 'unknown')}: {e}")
                    continue
            
            # Sort by explosive score
            low_float_stocks.sort(key=lambda x: x['explosive_score'], reverse=True)
            result = low_float_stocks[:limit]
            
            # Cache the results
            self.cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL)
            return result
            
        except Exception as e:
            logger.error(f"Error in low float scanner: {e}")
            return []
    
    async def _get_cached_profile(self, symbol: str) -> Optional[Dict]:
        """Get company profile with caching to minimize API calls"""
        try:
            # Check cache first
            cached_profile = self.cache.get_profile(symbol)
            if cached_profile:
                return cached_profile
            
            # Only fetch if not cached
            profile = self.finnhub.get_company_profile(symbol)
            if profile:
                self.cache.cache_profile(symbol, profile)
            return profile
        except Exception as e:
            logger.warning(f"Error getting profile for {symbol}: {e}")
            return None
    
    def _estimate_relative_volume(self, current_volume: int) -> float:
        """Estimate relative volume (simplified calculation)"""
        # This is a simplified estimation - in production you'd use historical averages
        avg_volume = 1_000_000  # Rough average
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    
    def _calculate_ross_score_from_data(self, price: float, change_pct: float, volume: int, float_shares: float) -> float:
        """Calculate Ross Cameron momentum score from available data"""
        try:
            # Price score (prefer $2-$20 range)
            if 2 <= price <= 20:
                price_score = 1.0
            elif price < 2:
                price_score = 0.3
            else:
                price_score = 0.7
            
            # Change score (higher % change = higher score)
            change_score = min(change_pct / 20.0, 1.0)  # Cap at 20%
            
            # Volume score (simplified)
            volume_score = min(volume / 1_000_000, 1.0)  # Cap at 1M volume
            
            # Float score (lower float = higher score)
            float_score = max(0, (20_000_000 - float_shares) / 20_000_000)
            
            # Weighted combination
            ross_score = (
                price_score * 0.2 +
                change_score * 0.4 +
                volume_score * 0.2 +
                float_score * 0.2
            ) * 100
            
            return round(ross_score, 2)
        except:
            return 0.0
    
    def _calculate_gap_score_from_data(self, price: float, gap_pct: float, volume: int, float_shares: float) -> float:
        """Calculate gap score from available data"""
        try:
            gap_score = (
                min(gap_pct / 15.0, 1.0) * 0.4 +  # Gap percentage
                min(volume / 500_000, 1.0) * 0.3 +  # Volume
                max(0, (15_000_000 - float_shares) / 15_000_000) * 0.3  # Float
            ) * 100
            return round(gap_score, 2)
        except:
            return 0.0
    
    def _calculate_explosive_score_from_data(self, price: float, change_pct: float, volume: int, float_shares: float) -> float:
        """Calculate explosive potential score for low float stocks"""
        try:
            explosive_score = (
                min(change_pct / 25.0, 1.0) * 0.3 +  # Change percentage
                min(volume / 1_000_000, 1.0) * 0.3 +  # Volume
                max(0, (10_000_000 - float_shares) / 10_000_000) * 0.4  # Float (most important)
            ) * 100
            return round(explosive_score, 2)
        except:
            return 0.0
    
    def _calculate_float_turnover(self, volume: int, float_shares: float) -> float:
        """Calculate what percentage of float traded"""
        try:
            if float_shares > 0:
                return round((volume / float_shares) * 100, 2)
            return 0.0
        except:
            return 0.0

