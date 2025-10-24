#!/usr/bin/env python3
"""
Polymarket Markets Fetcher
Fetches Polymarket betting markets sorted by closest closing date
"""
# JeremyWhittaker/Polymarket_arbitrage 



import requests
import json
import os
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import sys
from collections import defaultdict

class PolymarketClient:
    def __init__(self):
        self.base_url = "https://gamma-api.polymarket.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolymarketMarketsFetcher/1.0'
        })

    def fetch_all_markets(self) -> List[Dict]:
        """Fetch all open markets from Polymarket API with pagination"""
        url = f"{self.base_url}/markets"
        all_markets = []
        offset = 0
        batch_size = 100
        
        while True:
            params = {
                "active": True,
                "closed": False,
                "archived": False,
                "limit": batch_size,
                "offset": offset
            }
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                market_batch = response.json()
                
                if not market_batch:
                    break
                    
                all_markets.extend(market_batch)
                print(f"Fetched {len(market_batch)} markets (total: {len(all_markets)})")
                
                if len(market_batch) < batch_size:
                    break
                    
                offset += batch_size
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching markets: {e}")
                break
                
        return all_markets

    def extract_market_odds(self, market: Dict) -> Optional[Dict]:
        """Extract odds information from market data"""
        try:
            outcome_prices = market.get('outcomePrices')
            if not outcome_prices:
                return None
                
            # Parse string if needed
            if isinstance(outcome_prices, str):
                outcome_prices = json.loads(outcome_prices)
                
            if not isinstance(outcome_prices, list) or len(outcome_prices) < 2:
                return None
                
            outcomes = market.get('outcomes', [])
            if len(outcomes) < 2:
                return None
                
            # Find Yes/No outcomes
            yes_price = None
            no_price = None
            yes_outcome = None
            no_outcome = None
            
            for i, outcome in enumerate(outcomes):
                outcome_text = outcome.lower() if isinstance(outcome, str) else str(outcome).lower()
                if i < len(outcome_prices):
                    price = float(outcome_prices[i])
                    if 'yes' in outcome_text or outcome_text == '1':
                        yes_price = price
                        yes_outcome = outcome
                    elif 'no' in outcome_text or outcome_text == '0':
                        no_price = price  
                        no_outcome = outcome
            
            # If no explicit Yes/No, use first two outcomes
            if yes_price is None and len(outcome_prices) >= 2:
                yes_price = float(outcome_prices[0])
                yes_outcome = outcomes[0] if outcomes else "Option 1"
                no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else (1.0 - yes_price)
                no_outcome = outcomes[1] if len(outcomes) > 1 else "Option 2"
            
            if yes_price is None:
                return None
                
            # Calculate probabilities and odds
            yes_probability = yes_price * 100  # Convert to percentage
            no_probability = (no_price * 100) if no_price else (100 - yes_probability)
            
            # Calculate odds ratios
            yes_odds_decimal = 1 / yes_price if yes_price > 0 else float('inf')
            implied_probability = yes_price
            
            # Get volume and calculate confidence score
            volume = float(market.get('volume', 0)) if market.get('volume') else 0
            liquidity = float(market.get('liquidity', 0)) if market.get('liquidity') else 0
            
            # Calculate days until end date
            end_date = self.parse_end_date(market.get('endDate'))
            days_remaining = 1  # Default to 1 to avoid division by zero
            if end_date:
                current_time = datetime.now(timezone.utc)
                days_remaining = max(1, (end_date - current_time).days)
            
            # Calculate confidence score: (volume / days) × (yes%)³
            daily_volume = volume / days_remaining
            confidence_multiplier = (yes_probability / 100) ** 3
            intuitive_score = daily_volume * confidence_multiplier

            # Capture recent price movement (24h change in percentage points)
            raw_change = market.get('oneDayPriceChange')
            try:
                price_change_24h = float(raw_change) * 100 if raw_change is not None else 0.0
            except (TypeError, ValueError):
                price_change_24h = 0.0

            
            return {
                'yes_price': yes_price,
                'no_price': no_price,
                'yes_probability': yes_probability,
                'no_probability': no_probability,
                'yes_odds_decimal': yes_odds_decimal,
                'implied_probability': implied_probability,
                'yes_outcome': yes_outcome,
                'no_outcome': no_outcome,
                'volume': volume,
                'liquidity': liquidity,
                'days_remaining': days_remaining,
                'daily_volume': daily_volume,
                'intuitive_score': intuitive_score,
                'price_change_24h': price_change_24h
            }
            
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return None

    def rank_markets_by_odds(self, markets: List[Dict], sort_by: str = 'yes_probability') -> List[Dict]:
        """Rank markets by odds, adding odds data to each market"""
        markets_with_odds = []
        
        for market in markets:
            odds_data = self.extract_market_odds(market)
            if odds_data:
                market_copy = market.copy()
                market_copy['odds_data'] = odds_data
                markets_with_odds.append(market_copy)
        
        # Add rank scores to all markets
        markets_with_odds = self.add_rank_scores(markets_with_odds)
        
        # Sort by specified criteria
        reverse_sort = True  # Higher values first
        if sort_by == 'yes_probability':
            markets_with_odds.sort(key=lambda m: m['odds_data']['yes_probability'], reverse=reverse_sort)
        elif sort_by == 'yes_odds_decimal':
            markets_with_odds.sort(key=lambda m: m['odds_data']['yes_odds_decimal'], reverse=False)  # Lower odds = higher probability
        elif sort_by == 'volume':
            markets_with_odds.sort(key=lambda m: m['odds_data']['volume'], reverse=reverse_sort)
        elif sort_by == 'liquidity':
            markets_with_odds.sort(key=lambda m: m['odds_data']['liquidity'], reverse=reverse_sort)
        elif sort_by == 'intuitive_score':
            markets_with_odds.sort(key=lambda m: m['odds_data']['intuitive_score'], reverse=reverse_sort)
        elif sort_by == 'rank_score':
            markets_with_odds.sort(key=lambda m: m['odds_data']['rank_score'], reverse=reverse_sort)
        elif sort_by in ('recent_change', 'price_change_24h'):
            markets_with_odds.sort(key=lambda m: m['odds_data'].get('price_change_24h', 0), reverse=reverse_sort)
            
        return markets_with_odds

    def calculate_max_volume(self, markets: List[Dict]) -> float:
        """Calculate maximum volume across all markets for normalization"""
        max_vol = 0
        for market in markets:
            odds_data = self.extract_market_odds(market)
            if odds_data:
                volume = odds_data.get('volume', 0)
                max_vol = max(max_vol, volume)
        return max_vol if max_vol > 0 else 1  # Avoid division by zero

    def calculate_rank_score(self, yes_percent: float, odds: float, days: int, volume: float, max_volume: float) -> float:
        """Calculate rank score using EPM, risk adjustment, volume and time factors"""
        # Convert Yes% from percentage to decimal
        yes_decimal = yes_percent / 100.0
        
        # Calculate Expected Profit Margin (EPM)
        epm = yes_decimal - (1.0 / odds)
        
        # Calculate Risk Adjustment: e^(-((Yes% - 0.915)^2) / (2 * 0.05^2))
        risk_adjustment = math.exp(-((yes_decimal - 0.915) ** 2) / (2 * 0.05 ** 2))
        
        # Calculate Volume Factor
        volume_factor = volume / max_volume if max_volume > 0 else 0
        
        # Calculate Time Factor
        time_factor = 1.0 / days if days > 0 else 0
        
        # Calculate RankScore
        rank_score = epm * risk_adjustment * volume_factor * time_factor
        
        return rank_score

    def add_rank_scores(self, markets_with_odds: List[Dict]) -> List[Dict]:
        """Add rank scores to markets with odds data"""
        if not markets_with_odds:
            return markets_with_odds
            
        # Calculate max volume for normalization
        max_volume = max(m['odds_data']['volume'] for m in markets_with_odds)
        
        for market in markets_with_odds:
            odds_data = market['odds_data']
            rank_score = self.calculate_rank_score(
                yes_percent=odds_data['yes_probability'],
                odds=odds_data['yes_odds_decimal'],
                days=odds_data['days_remaining'],
                volume=odds_data['volume'],
                max_volume=max_volume
            )
            odds_data['rank_score'] = rank_score
            
        return markets_with_odds

    def format_odds_display(self, market: Dict) -> str:
        """Format market with odds for display"""
        question = market.get('question', 'No question')[:55]
        if len(market.get('question', '')) > 55:
            question += "..."
            
        odds_data = market.get('odds_data', {})
        yes_prob = odds_data.get('yes_probability', 0)
        yes_odds = odds_data.get('yes_odds_decimal', 0)
        volume = odds_data.get('volume', 0)
        confidence_score = odds_data.get('intuitive_score', 0)
        rank_score = odds_data.get('rank_score', 0)
        days_remaining = odds_data.get('days_remaining', 0)
        
        # Handle volume conversion from string to float
        try:
            if isinstance(volume, str):
                volume = float(volume) if volume else 0
            elif volume is None:
                volume = 0
            volume = float(volume)
        except (ValueError, TypeError):
            volume = 0
        
        volume_str = f"${volume:,.0f}" if volume > 0 else "$0"
        
        # Format scores with appropriate scaling
        if confidence_score >= 1000:
            intuit_str = f"{confidence_score/1000:.1f}k"
        elif confidence_score >= 1:
            intuit_str = f"{confidence_score:.1f}"
        else:
            intuit_str = f"{confidence_score:.3f}"
            
        # Format rank score (scientific notation for very small values)
        if abs(rank_score) >= 0.001:
            rank_str = f"{rank_score:.4f}"
        elif rank_score != 0:
            rank_str = f"{rank_score:.2e}"
        else:
            rank_str = "0.0000"
        
        price_change = odds_data.get('price_change_24h', 0)
        try:
            price_change = float(price_change)
        except (TypeError, ValueError):
            price_change = 0.0
        change_str = f"{price_change:+5.1f}pp"
        return f"{yes_prob:5.1f}% | {yes_odds:5.2f} | {days_remaining:3}d | {volume_str:9} | {intuit_str:>6} | {rank_str:>8} | {change_str:>7} | {question}"
        
    def fetch_markets(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch open markets from Polymarket API using their filtering"""
        if limit is None:
            return self.fetch_all_markets()
            
        url = f"{self.base_url}/markets"
        params = {
            "active": True,
            "closed": False,
            "archived": False,
            "limit": limit
        }
            
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching markets: {e}")
            return []

    def parse_end_date(self, end_date_str: str) -> Optional[datetime]:
        """Parse end date string to datetime object"""
        if not end_date_str:
            return None
        try:
            # Handle various datetime formats
            if end_date_str.endswith('Z'):
                return datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(end_date_str)
        except (ValueError, TypeError):
            return None

    def filter_open_markets(self, markets: List[Dict]) -> List[Dict]:
        """Filter for markets that are still open"""
        open_markets = []
        current_time = datetime.now(timezone.utc)
        
        for market in markets:
            # Skip already closed markets
            if market.get('closed', False):
                continue
                
            end_date = self.parse_end_date(market.get('endDate'))
            if end_date and end_date > current_time:
                open_markets.append(market)
                
        return open_markets

    def sort_by_closing_date(self, markets: List[Dict]) -> List[Dict]:
        """Sort markets by end date (closest first)"""
        def get_sort_key(market):
            end_date = self.parse_end_date(market.get('endDate'))
            if end_date:
                return end_date
            # Put markets without end dates at the end
            return datetime.max.replace(tzinfo=timezone.utc)
        
        return sorted(markets, key=get_sort_key)

    def format_market_display(self, market: Dict) -> str:
        """Format market for display"""
        question = market.get('question', 'No question')[:80]
        if len(market.get('question', '')) > 80:
            question += "..."
            
        end_date = self.parse_end_date(market.get('endDate'))
        if end_date:
            # Calculate days until closing
            current_time = datetime.now(timezone.utc)
            days_left = (end_date - current_time).days
            time_str = f"{days_left}d" if days_left > 0 else "Closing soon"
            date_str = end_date.strftime("%Y-%m-%d %H:%M UTC")
        else:
            time_str = "No end date"
            date_str = "Unknown"
        
        volume = market.get('volume', 0)
        if isinstance(volume, (int, float)):
            volume_str = f"${volume:,.0f}" if volume > 0 else "$0"
        else:
            volume_str = "$0"
            
        return f"{time_str:12} | {date_str:20} | {volume_str:12} | {question}"

    def get_market_year_month(self, market: Dict) -> Optional[str]:
        """Get year-month string for market end date (YYYY-MM format)"""
        end_date = self.parse_end_date(market.get('endDate'))
        if end_date:
            return end_date.strftime("%Y-%m")
        return None

    def organize_markets_by_month(self, markets: List[Dict]) -> Dict[str, List[Dict]]:
        """Organize markets by their ending year-month"""
        markets_by_month = defaultdict(list)
        
        for market in markets:
            year_month = self.get_market_year_month(market)
            if year_month:
                markets_by_month[year_month].append(market)
            else:
                # Put markets without end dates in 'unknown' category
                markets_by_month['unknown'].append(market)
                
        return dict(markets_by_month)

    def save_markets_to_cache(self, markets: List[Dict], cache_dir: str = "polymarket_cache") -> None:
        """Save markets to JSON files organized by year-month"""
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        markets_by_month = self.organize_markets_by_month(markets)
        
        # Sort month keys to prioritize earliest months
        sorted_months = sorted(markets_by_month.keys())
        
        for year_month in sorted_months:
            month_markets = markets_by_month[year_month]
            
            # Sort markets within each month by end date
            month_markets = self.sort_by_closing_date(month_markets)
            
            filename = f"{cache_dir}/markets_{year_month}.json"
            
            cache_data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "year_month": year_month,
                "market_count": len(month_markets),
                "markets": month_markets
            }
            
            with open(filename, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            print(f"Saved {len(month_markets)} markets to {filename}")

    def load_markets_from_cache(self, year_month: str, cache_dir: str = "polymarket_cache") -> List[Dict]:
        """Load markets from cache file for specific year-month"""
        filename = f"{cache_dir}/markets_{year_month}.json"
        
        if not os.path.exists(filename):
            return []
            
        try:
            with open(filename, 'r') as f:
                cache_data = json.load(f)
                return cache_data.get('markets', [])
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading cache file {filename}: {e}")
            return []

    def get_cached_months(self, cache_dir: str = "polymarket_cache") -> List[str]:
        """Get list of available cached year-month files"""
        if not os.path.exists(cache_dir):
            return []
            
        cached_files = []
        for filename in os.listdir(cache_dir):
            if filename.startswith('markets_') and filename.endswith('.json'):
                year_month = filename.replace('markets_', '').replace('.json', '')
                cached_files.append(year_month)
                
        return sorted(cached_files)

    def parse_yyyymm_to_datetime(self, yyyymm: str) -> Optional[datetime]:
        """Parse YYYYMM string to datetime object (first day of month)"""
        try:
            if len(yyyymm) != 6 or not yyyymm.isdigit():
                return None
            year = int(yyyymm[:4])
            month = int(yyyymm[4:])
            if month < 1 or month > 12:
                return None
            return datetime(year, month, 1, tzinfo=timezone.utc)
        except ValueError:
            return None

    def get_last_day_of_month(self, dt: datetime) -> datetime:
        """Get the last day of the month for given datetime"""
        if dt.month == 12:
            next_month = dt.replace(year=dt.year + 1, month=1, day=1)
        else:
            next_month = dt.replace(month=dt.month + 1, day=1)
        return next_month - timezone.utc.localize(datetime(1970, 1, 1)).replace(tzinfo=None).replace(microsecond=0) + timezone.utc.localize(datetime(1970, 1, 1, 23, 59, 59, 999999)).replace(tzinfo=None)

    def filter_markets_by_date_range(self, markets: List[Dict], start_yyyymm: Optional[str] = None, end_yyyymm: Optional[str] = None) -> List[Dict]:
        """Filter markets by their end date within specified YYYYMM range"""
        if not start_yyyymm and not end_yyyymm:
            return markets
            
        filtered_markets = []
        
        start_date = None
        end_date = None
        
        if start_yyyymm:
            start_date = self.parse_yyyymm_to_datetime(start_yyyymm)
            if not start_date:
                print(f"Invalid start date format: {start_yyyymm}. Use YYYYMM format (e.g., 202501)")
                return []
                
        if end_yyyymm:
            end_month_start = self.parse_yyyymm_to_datetime(end_yyyymm)
            if not end_month_start:
                print(f"Invalid end date format: {end_yyyymm}. Use YYYYMM format (e.g., 202512)")
                return []
            # Set to last day of the month (23:59:59)
            if end_month_start.month == 12:
                end_date = end_month_start.replace(year=end_month_start.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                end_date = end_month_start.replace(month=end_month_start.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            # Subtract 1 microsecond to get end of previous day (last day of target month)
            end_date = end_date - timedelta(microseconds=1)
        
        for market in markets:
            market_end_date = self.parse_end_date(market.get('endDate'))
            if not market_end_date:
                continue
                
            # Check if market end date is within range
            if start_date and market_end_date < start_date:
                continue
            if end_date and market_end_date > end_date:
                continue
                
            filtered_markets.append(market)
            
        return filtered_markets

    def get_markets_in_date_range(self, start_yyyymm: str, end_yyyymm: str, cache_dir: str = "polymarket_cache") -> List[Dict]:
        """Get all markets from cache files within specified date range"""
        all_markets = []
        
        start_date = self.parse_yyyymm_to_datetime(start_yyyymm)
        end_date = self.parse_yyyymm_to_datetime(end_yyyymm)
        
        if not start_date or not end_date:
            return []
            
        # Generate all year-month combinations in range
        current_date = start_date
        year_months = []
        
        while current_date <= end_date:
            year_month = current_date.strftime("%Y-%m")
            year_months.append(year_month)
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Load markets from each month's cache file
        for year_month in year_months:
            month_markets = self.load_markets_from_cache(year_month, cache_dir)
            if month_markets:
                print(f"Loaded {len(month_markets)} markets from {year_month}")
                all_markets.extend(month_markets)
        
        return all_markets

def main():
    """Main function to fetch and display markets"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Polymarket Markets Fetcher')
    parser.add_argument('--limit', type=int, help='Limit number of markets to display')
    parser.add_argument('--cache', action='store_true', help='Cache all markets to JSON files')
    parser.add_argument('--use-cache', type=str, help='Use cached markets from specific year-month (YYYY-MM)')
    parser.add_argument('--list-cache', action='store_true', help='List available cached months')
    parser.add_argument('--start', type=str, help='Start date for market closing period (YYYYMM format, e.g., 202501)')
    parser.add_argument('--end', type=str, help='End date for market closing period (YYYYMM format, e.g., 202512)')
    parser.add_argument('--date-range-cache', action='store_true', help='Use cached data for date range specified by --start and --end')
    parser.add_argument('--odds-ranking', action='store_true', help='Rank markets by odds instead of closing date')
    parser.add_argument('--sort-by', type=str, choices=['yes_probability', 'yes_odds_decimal', 'volume', 'liquidity', 'intuitive_score', 'rank_score', 'recent_change', 'price_change_24h'], 
                       default='yes_probability', help='Sort criterion for odds ranking (default: yes_probability). Use recent_change for 24h yes% gainers.')
    
    args = parser.parse_args()
    
    client = PolymarketClient()
    
    if args.list_cache:
        cached_months = client.get_cached_months()
        if cached_months:
            print("Available cached months:")
            for month in cached_months:
                print(f"  {month}")
        else:
            print("No cached data found")
        return

    # Handle date range from cache
    if args.date_range_cache:
        if not args.start or not args.end:
            print("Error: --date-range-cache requires both --start and --end parameters")
            return
        
        print(f"Loading markets from cache for date range: {args.start} to {args.end}")
        markets = client.get_markets_in_date_range(args.start, args.end)
        if not markets:
            print(f"No cached markets found for date range {args.start} to {args.end}")
            return
        print(f"Loaded {len(markets)} markets from cache")
        
        # Apply additional date filtering to ensure precision
        markets = client.filter_markets_by_date_range(markets, args.start, args.end)
        print(f"Filtered to {len(markets)} markets within exact date range")
        
    elif args.use_cache:
        print(f"Loading markets from cache: {args.use_cache}")
        markets = client.load_markets_from_cache(args.use_cache)
        if not markets:
            print(f"No cached data found for {args.use_cache}")
            return
        print(f"Loaded {len(markets)} markets from cache")
        
        # Apply date range filtering if specified
        if args.start or args.end:
            markets = client.filter_markets_by_date_range(markets, args.start, args.end)
            print(f"Filtered to {len(markets)} markets within date range")
            
    else:
        print("Fetching Polymarket markets...")
        if args.cache:
            print("Fetching ALL markets for caching...")
            markets = client.fetch_all_markets()
            if markets:
                print(f"Fetched {len(markets)} total markets")
                
                # SAVE TO CACHE FIRST - don't waste the download effort
                client.save_markets_to_cache(markets)
                print("Markets cached successfully!")
                
                # THEN apply date range filtering for display only
                if args.start or args.end:
                    print(f"Filtering markets for display by date range: {args.start or 'start'} to {args.end or 'end'}")
                    markets = client.filter_markets_by_date_range(markets, args.start, args.end)
                    print(f"Filtered to {len(markets)} markets within date range for display")
                else:
                    # Get earliest month for display if no date range specified
                    markets_by_month = client.organize_markets_by_month(markets)
                    earliest_month = min(markets_by_month.keys()) if markets_by_month else None
                    if earliest_month and earliest_month != 'unknown':
                        print(f"\nShowing earliest month ({earliest_month}) markets:")
                        markets = markets_by_month[earliest_month]
                    else:
                        print("\nShowing first 50 markets:")
                        markets = markets[:50]
            else:
                print("No markets fetched")
                return
        else:
            limit = args.limit if args.limit else 50
            markets = client.fetch_markets(limit)
            if not markets:
                print("No markets fetched")
                return
            print(f"Fetched {len(markets)} open markets")
            
            # Apply date range filtering if specified
            if args.start or args.end:
                markets = client.filter_markets_by_date_range(markets, args.start, args.end)
                print(f"Filtered to {len(markets)} markets within date range")
    
    # Handle odds ranking vs date sorting
    if args.odds_ranking:
        print(f"\nRanking markets by odds ({args.sort_by})...")
        ranked_markets = client.rank_markets_by_odds(markets, args.sort_by)
        
        if not ranked_markets:
            print("No markets with valid odds data found")
            return
            
        print(f"Found {len(ranked_markets)} markets with odds data")
        
        # Display results with odds
        print(f"\nMarkets ranked by {args.sort_by}:")
        print("-" * 155)
        print(f"{'Yes%':<6} | {'Odds':<5} | {'Days':<4} | {'Volume':<9} | {'Intuit':<6} | {'Rank':<8} | {'Chg24h':<7} | Question")
        print("-" * 155)
        
        for market in ranked_markets:
            print(client.format_odds_display(market))
    else:
        # Sort by closing date (markets are already filtered as open)
        sorted_markets = client.sort_by_closing_date(markets)
        
        # Display results
        print("\nMarkets sorted by closest closing date:")
        print("-" * 120)
        print(f"{'Time Left':<12} | {'End Date':<20} | {'Volume':<12} | Question")
        print("-" * 120)
        
        for market in sorted_markets:
            print(client.format_market_display(market))


# https://github.com/fyre87/Political-betting-market-arbitrage-finder/blob/main/Political_Scraper.ipynb
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

# Encode the questions outside of the function so that you don't have to do it every time
full_df_encodings = model.encode(markets['question'].tolist())

def find_similar_question(input_question, df, df_encodings, similarity_threshold=0.95):
    # Encode the input question
    input_encoding = model.encode([input_question])

    # Calculate cosine similarity
    similarities = cosine_similarity(input_encoding, df_encodings)[0]

    # Find the index of the most similar question
    most_similar_index = np.argmax(similarities)

    # Check if the similarity is above the threshold
    if similarities[most_similar_index] >= similarity_threshold:
        return df.iloc[most_similar_index]['question'], df.iloc[most_similar_index]['tokens'], df.iloc[most_similar_index]['condition_id'], similarities[most_similar_index]
    else:
        return df.iloc[most_similar_index]['question'], None, None, similarities[most_similar_index]



from datetime import datetime, timezone
# Get time until market ends
def time_difference_from_now(date_string):
    # Parse the input string to a datetime object
    target_date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    # Get the current time in UTC
    current_time = datetime.now(timezone.utc)

    # Calculate the time difference
    time_difference = current_time - target_date

    # Calculate days, hours, minutes
    days = time_difference.days
    hours, remainder = divmod(time_difference.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    # Determine if the date is in the past or future
    if time_difference.total_seconds() > 0:
        tense = "ago"
    else:
        tense = "in the future"
        days, hours, minutes = abs(days), abs(hours), abs(minutes)

    return days #, f"{days} days, {hours} hours, and {minutes} minutes {tense}"

from py_clob_client.clob_types import BookParams


# Get the polymarket buy yes and stuff
def get_polymarket_values(input_question, markets_df, df_encodings):
  # input_question = "Will Kamala Harris win the 2024 US presidential election?"
  question, token_id, condition_id, similarity_score = find_similar_question(input_question, markets_df, df_encodings)

  if token_id:
      pass
      # print(f"  Most similar question: {question}")
      # print(f"Most similar question ID: {token_id}")
      # print(f"Similarity score: {similarity_score}")
  else:
      # print(f"  No similar question found. Highest similarity score: {similarity_score}. Most similar question: {question}")
      return None, None, None, None


  for i in range(0, len(token_id)):
    if token_id[i]['outcome'] == 'Yes':
      # buy_yes  = BookParams(token_id=token_id[i]['token_id'],side="BUY")
      best_sell_yes = client.get_price(token_id=token_id[i]['token_id'],side="SELL")['price'] #BookParams(token_id=token_id[i]['token_id'],side="SELL")
    else:
      # buy_no  = BookParams(token_id=token_id[i]['token_id'],side="BUY")
      best_sell_no = client.get_price(token_id=token_id[i]['token_id'],side="SELL")['price']

  days_till_end = None
  try:
    days_till_end = time_difference_from_now(client.get_market(condition_id)['end_date_iso'])
  except:
    pass
  return question, days_till_end, best_sell_yes, best_sell_no

import requests
import json
import re
from difflib import SequenceMatcher

def normalize_text(text):
    """Clean and normalize text for better matching"""
    if not text:
        return ""
    # Remove extra whitespace, convert to lowercase, remove special chars
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def extract_key_terms(text):
    """Extract key terms from market/contract names"""
    if not text:
        return []
    
    # Common political/election terms to preserve
    important_terms = {
        'election', 'win', 'wins', 'winner', 'president', 'presidential', 
        'senate', 'governor', 'house', 'congress', 'primary', 'general',
        'democrat', 'republican', 'party', 'candidate', 'nominee'
    }
    
    words = normalize_text(text).split()
    # Keep important terms and proper nouns (assume longer words are more important)
    key_terms = [w for w in words if w in important_terms or len(w) > 3]
    return key_terms

def generate_query_variations(contract, market):
    """Generate multiple query variations with confidence scores"""
    variations = []
    contract_name = contract['name']
    market_name = market['name']
    
    # Strategy 1: Original rigid pattern (high confidence if "win" in market name)
    if 'win' in market_name.lower() and market_name.lower() != contract_name.lower():
        try:
            query = "Will " + contract_name + " " + market_name[market_name.lower().index("win"):]
            variations.append({
                'query': query,
                'confidence': 0.9,
                'strategy': 'original_pattern'
            })
        except:
            pass
    
    # Strategy 2: Direct contract name (medium confidence)
    if market_name.lower() == contract_name.lower():
        variations.append({
            'query': contract_name,
            'confidence': 0.8,
            'strategy': 'direct_name'
        })
    
    # Strategy 3: "Will X win Y" format with flexible matching
    if 'win' not in market_name.lower():
        # Try to construct "Will X win Y" from context
        key_terms = extract_key_terms(market_name)
        if key_terms:
            query = f"Will {contract_name} win {' '.join(key_terms[:3])}"
            variations.append({
                'query': query,
                'confidence': 0.75,
                'strategy': 'constructed_win'
            })
    
    # Strategy 4: Election-specific patterns
    election_patterns = [
        f"Will {contract_name} win the {market_name}",
        f"{contract_name} to win {market_name}",
        f"Will {contract_name} be elected",
        f"{contract_name} {market_name}",
    ]
    
    for i, pattern in enumerate(election_patterns):
        # Clean up double spaces and weird constructions
        clean_pattern = re.sub(r'\s+', ' ', pattern).strip()
        if len(clean_pattern.split()) >= 3:  # Ensure reasonable length
            variations.append({
                'query': clean_pattern,
                'confidence': 0.7 - (i * 0.05),  # Decreasing confidence
                'strategy': f'election_pattern_{i+1}'
            })
    
    # Strategy 5: Fuzzy reconstruction using key terms
    contract_terms = extract_key_terms(contract_name)
    market_terms = extract_key_terms(market_name)
    
    if contract_terms and market_terms:
        # Combine most important terms
        combined_terms = contract_terms[:2] + market_terms[:2]
        fuzzy_query = f"Will {' '.join(combined_terms)}"
        variations.append({
            'query': fuzzy_query,
            'confidence': 0.65,
            'strategy': 'fuzzy_reconstruction'
        })
    
    # Strategy 6: Partial matching - just candidate name with "election"
    if any(term in market_name.lower() for term in ['election', 'president', 'governor', 'senate']):
        simple_query = f"{contract_name} election"
        variations.append({
            'query': simple_query,
            'confidence': 0.6,
            'strategy': 'simple_election'
        })
    
    # Strategy 7: Similarity-based reconstruction
    # If contract and market are very different, try to bridge them
    similarity = SequenceMatcher(None, normalize_text(contract_name), normalize_text(market_name)).ratio()
    if similarity < 0.3:  # Very different names
        # Try to find common ground
        bridge_query = f"Will {contract_name} win"
        variations.append({
            'query': bridge_query,
            'confidence': 0.55,
            'strategy': 'similarity_bridge'
        })
    
    # Sort by confidence (highest first) and limit to top 5
    variations.sort(key=lambda x: x['confidence'], reverse=True)
    return variations[:5]

def test_get_full_list_limited(markets_df, df_encodings, limit=20):
    """Test version of get_full_list with limited PredictIt data"""
    
    response = requests.get('https://www.predictit.org/api/marketdata/all/')

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON content
        data = json.loads(response.content)
        
        print(f"🔍 TESTING Enhanced Query Matching (Limited to {limit} items)")
        print("=" * 70)

        # Limit to first few markets for testing
        test_markets = data['markets'][:3]  # Only test first 3 markets
        
        total_contracts_tested = 0
        matches_found = 0

        # Iterate through each market
        for market_idx, market in enumerate(test_markets):
            print(f"\n📊 MARKET {market_idx + 1}: {market['name']}")
            print("-" * 50)
            
            # Limit contracts per market
            contracts_to_test = market['contracts'][:min(7, len(market['contracts']))]  # Max 7 contracts per market
            
            # Iterate through each contract in the market
            for contract_idx, contract in enumerate(contracts_to_test):
                total_contracts_tested += 1
                if total_contracts_tested > limit:
                    print(f"\n⏹️  Reached limit of {limit} contracts tested")
                    break
                    
                print(f"\n  📋 Contract {contract_idx + 1}: {contract['name']}")
                
                # Generate multiple query variations with confidence scoring
                queries_with_confidence = generate_query_variations(contract, market)
                
                if not queries_with_confidence:
                    print("    ❌ No query variations generated")
                    continue
                
                print(f"    🔄 Generated {len(queries_with_confidence)} query variations:")
                
                # Try each query variation until we find a good match
                best_match = None
                best_confidence = 0
                
                for query_info in queries_with_confidence:
                    query = query_info['query']
                    base_confidence = query_info['confidence']
                    strategy = query_info['strategy']
                    
                    print(f"       • {strategy} (conf={base_confidence:.2f}): '{query}'")
                    
                    question, days_till_end, best_yes_polymarket, best_no_polymarket = get_polymarket_values(query, markets_df, df_encodings)
                    
                    if question is not None:
                        # Calculate final confidence combining query confidence with similarity
                        final_confidence = base_confidence * 0.7 + 0.3  # Boost for successful match
                        
                        print(f"         ✅ MATCH FOUND! Final confidence: {final_confidence:.2f}")
                        print(f"         📄 Matched: {question[:60]}...")
                        
                        if final_confidence > best_confidence:
                            best_match = {
                                'question': question,
                                'days_till_end': days_till_end,
                                'best_yes_polymarket': best_yes_polymarket,
                                'best_no_polymarket': best_no_polymarket,
                                'query': query,
                                'confidence': final_confidence,
                                'strategy': strategy
                            }
                            best_confidence = final_confidence
                    else:
                        print(f"         ❌ No match")
                
                # Use the best match if confidence is above threshold
                if best_match and best_confidence >= 0.6:
                    matches_found += 1
                    print(f"    🎯 BEST MATCH SELECTED:")
                    print(f"       Strategy: {best_match['strategy']}")
                    print(f"       Confidence: {best_match['confidence']:.1%}")
                    print(f"       Query: '{best_match['query']}'")
                    print(f"       Polymarket Question: {best_match['question'][:80]}...")
                    
                    # Check for arbitrage (simplified for testing)
                    best_yes_predictit = contract.get('bestBuyYesCost')
                    best_no_predictit = contract.get('bestBuyNoCost')
                    
                    if best_yes_predictit is not None and best_no_predictit is not None:
                        print(f"       💰 PredictIt Prices: YES=${best_yes_predictit}, NO=${best_no_predictit}")
                        print(f"       💰 Polymarket Prices: YES=${best_match['best_yes_polymarket']}, NO=${best_match['best_no_polymarket']}")
                    else:
                        print(f"       ⚠️  PredictIt prices unavailable")
                        
                else:
                    print(f"    ❌ No good match found (best confidence: {best_confidence:.1%})")
                
                # Break if we've reached the limit
                if total_contracts_tested >= limit:
                    break
            
            if total_contracts_tested >= limit:
                break
        
        print(f"\n" + "=" * 70)
        print(f"📈 TEST SUMMARY:")
        print(f"   • Total contracts tested: {total_contracts_tested}")
        print(f"   • Matches found: {matches_found}")
        print(f"   • Success rate: {(matches_found/total_contracts_tested*100):.1f}%")
        print(f"   • Markets processed: {len(test_markets)}")
        print("=" * 70)

    else:
        print(f"❌ Failed to retrieve PredictIt data: Status code {response.status_code}")

def check_for_arbitrage(polymarket_yes, polymarket_no, predictit_yes, predictit_no):
    """
    Check for arbitrage opportunities between Polymarket and PredictIt
    Returns yes_profit, no_profit, shares_purchased or None values if no arbitrage
    """
    # Simple arbitrage check - can be enhanced with actual calculation logic
    # This is a placeholder that should be replaced with real arbitrage calculations
    
    try:
        # Convert to float if string
        poly_yes = float(polymarket_yes) if polymarket_yes else 0
        poly_no = float(polymarket_no) if polymarket_no else 0
        pred_yes = float(predictit_yes) if predictit_yes else 0
        pred_no = float(predictit_no) if predictit_no else 0
        
        # Simple check: look for price differences that could indicate arbitrage
        yes_diff = abs(poly_yes - pred_yes)
        no_diff = abs(poly_no - pred_no)
        
        # If there's a significant price difference, assume arbitrage opportunity
        if yes_diff > 0.05 or no_diff > 0.05:
            # Mock calculation - replace with real arbitrage logic
            yes_profit = yes_diff * 100  # Mock profit calculation
            no_profit = no_diff * 100
            shares_purchased = 1000  # Mock shares
            return yes_profit, no_profit, shares_purchased
        else:
            return None, None, None
            
    except (ValueError, TypeError):
        return None, None, None

def get_full_list(markets_df, df_encodings):

  response = requests.get('https://www.predictit.org/api/marketdata/all/')

  # Check if the request was successful
  if response.status_code == 200:
    # Parse the JSON content
    data = json.loads(response.content)

    # Iterate through each market
    for market in data['markets']:

      # Iterate through each contract in the market
      for contract in market['contracts']:
        # Generate multiple query variations with confidence scoring
        queries_with_confidence = generate_query_variations(contract, market)
        
        # Try each query variation until we find a good match
        best_match = None
        best_confidence = 0
        
        for query_info in queries_with_confidence:
          query = query_info['query']
          base_confidence = query_info['confidence']
          
          question, days_till_end, best_yes_polymarket, best_no_polymarket = get_polymarket_values(query, markets_df, df_encodings)
          
          if question is not None:
            # Calculate final confidence combining query confidence with similarity
            final_confidence = base_confidence * 0.7 + 0.3  # Boost for successful match
            
            if final_confidence > best_confidence:
              best_match = {
                'question': question,
                'days_till_end': days_till_end,
                'best_yes_polymarket': best_yes_polymarket,
                'best_no_polymarket': best_no_polymarket,
                'query': query,
                'confidence': final_confidence
              }
              best_confidence = final_confidence
        
        # Use the best match if confidence is above threshold
        if best_match and best_confidence >= 0.6:
          question = best_match['question']
          days_till_end = best_match['days_till_end']
          best_yes_polymarket = best_match['best_yes_polymarket']
          best_no_polymarket = best_match['best_no_polymarket']
        else:
          # No good match found
          continue


        if question != None:

          best_yes_polymarket = float(best_yes_polymarket)
          best_no_polymarket = float(best_no_polymarket)

          best_yes_predictit = contract['bestBuyYesCost']
          best_no_predictit = contract['bestBuyNoCost']

          if best_yes_predictit == None or best_no_predictit == None:
            continue

          yes_profit, no_profit, shares_purchased = check_for_arbitrage(best_yes_polymarket, best_no_polymarket, best_yes_predictit, best_no_predictit)

          if yes_profit != None and no_profit != None:
            # We have found arbitrage
            print(f"Found arbitrage in: {q}")
            print(f"  Best YES Polymarket: ${best_yes_polymarket}")
            print(f"  Best NO  Polymarket: ${best_no_polymarket}")
            print(f"  Best YES Predictit:  ${best_yes_predictit}")
            print(f"  Best NO  Predictit:  ${best_no_predictit}")
            print(f"  Shares   Purchased:   {shares_purchased}")
            try:
              days_till_end = float(days_till_end)
              print(f"YES Profit (given {yes_profit:.2f}. Implied yearly return: {((1+yes_profit/1000)**(365.25/days_till_end-1)-1):.2%}")
              print(f"  NO  Profit (given {no_profit:.2f}. Implied yearly return: {((1+no_profit/1000)**(365.25/days_till_end-1)-1):.2%}")
              if best_yes_polymarket > best_yes_predictit:
                # Then bought yes on predictit (buy low)
                print(f"    YES Profit % after 5% withdrawl fee: {((1+(yes_profit-50)/1000)**(365.25/days_till_end-1)-1):.2%}")
                print(f"    NO  Profit % after 5% withdrawl fee: {((1+(no_profit)/1000)**(365.25/days_till_end-1)-1):.2%}")
              else:
                # Then bought yes on polymarket (buy low)
                print(f"    YES Profit % after 5% withdrawl fee: {((1+(yes_profit)/1000)**(365.25/days_till_end-1)-1):.2%}")
                print(f"    NO  Profit % after 5% withdrawl fee: {((1+(no_profit-50)/1000)**(365.25/days_till_end-1)-1):.2%}")
            except:
              print(f"  YES Profit (given 
{yes_profit:.2f}.")
              print(f"  NO Profit (given 
{no_profit:.2f}.")
            print(f" ")

  else:
    print(f"Failed to retrieve data: Status code {response.status_code}")

if __name__ == "__main__":
    # Test the enhanced query matching functionality
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test-enhanced":
        print("🧪 Testing Enhanced Query Matching System")
        print("=" * 60)
        
        # Create mock data for testing
        mock_questions = [
            "Will Donald Trump win the 2024 US presidential election?",
            "Will Joe Biden win the 2024 US presidential election?", 
            "Will the Republicans control the US House after the 2024 election?",
            "Will Democrats control the US Senate after the 2024 election?",
        ]
        
        mock_data = []
        for i, question in enumerate(mock_questions):
            mock_data.append({
                'question': question,
                'tokens': [{'outcome': 'Yes', 'token_id': f'token_yes_{i}'}, 
                          {'outcome': 'No', 'token_id': f'token_no_{i}'}],
                'condition_id': f'condition_{i}'
            })
        
        markets_df = pd.DataFrame(mock_data)
        df_encodings = model.encode(markets_df['question'].tolist())
        
        print(f"📊 Using mock Polymarket database with {len(markets_df)} questions")
        
        # Test the enhanced query matching with limited data
        test_get_full_list_limited(markets_df, df_encodings, limit=15)
        
    else:
        # Original main functionality
        main()
