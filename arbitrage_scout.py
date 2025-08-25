#!/usr/bin/env python3
"""
Main orchestrator for the news-to-markets arbitrage scout system
"""

import asyncio
from typing import List
from datetime import datetime, timedelta
import logging

from connectors import StackerNewsConnector, PolymarketConnector, PredyxConnector
from event_model import EventNormalizer
from event_matcher import EventMatcher, HumanReviewQueue
from arbitrage_engine import ArbitrageDetector

class ArbitrageScout:
    """Main orchestrator for multi-venue arbitrage detection"""
    
    def __init__(self, config: dict):
        # Initialize connectors
        self.sn_connector = StackerNewsConnector(config.get('stacker_news_endpoint'))
        self.polymarket_connector = PolymarketConnector(config.get('polymarket_api_base'))
        self.predyx_connector = PredyxConnector(config.get('predyx_base_url'))
        
        # Initialize processing components
        self.normalizer = EventNormalizer()
        self.matcher = EventMatcher(confidence_threshold=config.get('match_threshold', 0.75))
        self.arbitrage_detector = ArbitrageDetector(
            min_edge_threshold=config.get('min_edge', 0.02),
            max_slippage_tolerance=config.get('max_slippage', 0.01)
        )
        self.review_queue = HumanReviewQueue()
        
        # Configuration
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def run_discovery_cycle(self):
        """Run one complete discovery and analysis cycle"""
        self.logger.info("Starting arbitrage discovery cycle")
        
        try:
            # Step 1: Fetch signals from Stacker News
            sn_posts = await self._fetch_stacker_news_signals()
            
            # Step 2: Fetch markets from prediction venues
            polymarket_markets = await self._fetch_polymarket_markets()
            predyx_markets = await self._fetch_predyx_markets()
            
            # Step 3: Normalize all data to canonical events
            events = await self._normalize_all_events(sn_posts, polymarket_markets, predyx_markets)
            
            # Step 4: Match events across venues
            matches = await self._match_cross_venue_events(events)
            
            # Step 5: Detect arbitrage opportunities
            opportunities = await self._detect_arbitrage_opportunities(matches)
            
            # Step 6: Process and alert on opportunities
            await self._process_opportunities(opportunities)
            
            self.logger.info(f"Cycle completed. Found {len(opportunities)} opportunities")
            
        except Exception as e:
            self.logger.error(f"Error in discovery cycle: {e}")
            raise
    
    async def _fetch_stacker_news_signals(self):
        """Fetch signals from Stacker News"""
        # TODO: Implement entity/keyword search
        self.logger.info("Fetching Stacker News signals")
        return []
    
    async def _fetch_polymarket_markets(self):
        """Fetch markets from Polymarket"""
        self.logger.info("Fetching Polymarket markets")
        return await self.polymarket_connector.fetch_markets()
    
    async def _fetch_predyx_markets(self):
        """Fetch markets from Predyx"""
        self.logger.info("Fetching Predyx markets")
        return await self.predyx_connector.fetch_markets()
    
    async def _normalize_all_events(self, sn_posts, polymarket_markets, predyx_markets):
        """Normalize all venue data to canonical events"""
        events = []
        
        # Normalize Polymarket markets
        for market in polymarket_markets or []:
            event = self.normalizer.normalize_polymarket_market(market)
            if event:
                events.append(event)
        
        # Normalize Predyx markets
        for market in predyx_markets or []:
            event = self.normalizer.normalize_predyx_market(market)
            if event:
                events.append(event)
        
        # Extract events from Stacker News posts (if predictive)
        for post in sn_posts or []:
            event = self.normalizer.normalize_stackernews_post(post)
            if event:
                events.append(event)
        
        self.logger.info(f"Normalized {len(events)} total events")
        return events
    
    async def _match_cross_venue_events(self, events):
        """Find matching events across venues"""
        # Group events by venue
        events_by_venue = {}
        for event in events:
            venue = event.venue.value
            if venue not in events_by_venue:
                events_by_venue[venue] = []
            events_by_venue[venue].append(event)
        
        # Find matches between venue pairs
        all_matches = []
        venues = list(events_by_venue.keys())
        
        for i in range(len(venues)):
            for j in range(i + 1, len(venues)):
                venue_a, venue_b = venues[i], venues[j]
                matches = self.matcher.find_matches(
                    events_by_venue[venue_a], 
                    events_by_venue[venue_b]
                )
                all_matches.extend(matches)
        
        # Queue low-confidence matches for human review
        for match in all_matches:
            if match.human_review_required:
                self.review_queue.add_for_review(match)
        
        self.logger.info(f"Found {len(all_matches)} potential matches")
        return all_matches
    
    async def _detect_arbitrage_opportunities(self, matches):
        """Detect arbitrage opportunities from matches"""
        opportunities = self.arbitrage_detector.scan_for_arbitrage(matches)
        self.logger.info(f"Detected {len(opportunities)} arbitrage opportunities")
        return opportunities
    
    async def _process_opportunities(self, opportunities):
        """Process and alert on opportunities"""
        for opp in opportunities:
            if opp.net_edge >= self.config.get('alert_threshold', 0.03):  # 3% threshold
                await self._send_alert(opp)
    
    async def _send_alert(self, opportunity):
        """Send alert for arbitrage opportunity"""
        # TODO: Implement alerting (Discord, Telegram, etc.)
        self.logger.info(f"ARBITRAGE ALERT: {opportunity.expected_profit:.2f} profit opportunity")
    
    async def run_continuous(self, cycle_interval_seconds: int = 300):
        """Run continuous monitoring with specified interval"""
        self.logger.info(f"Starting continuous monitoring (interval: {cycle_interval_seconds}s)")
        
        while True:
            try:
                await self.run_discovery_cycle()
                await asyncio.sleep(cycle_interval_seconds)
            except KeyboardInterrupt:
                self.logger.info("Shutting down continuous monitoring")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous cycle: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)

# Example usage and configuration
DEFAULT_CONFIG = {
    'stacker_news_endpoint': 'https://stacker.news/api/graphql',
    'polymarket_api_base': 'https://gamma-api.polymarket.com',
    'predyx_base_url': 'https://beta.predyx.com',
    'match_threshold': 0.75,
    'min_edge': 0.02,  # 2% minimum edge
    'max_slippage': 0.01,  # 1% max slippage
    'alert_threshold': 0.03,  # 3% profit threshold for alerts
}

async def main():
    """Example main function"""
    scout = ArbitrageScout(DEFAULT_CONFIG)
    
    # Run single cycle
    await scout.run_discovery_cycle()
    
    # Or run continuous monitoring
    # await scout.run_continuous(cycle_interval_seconds=300)

if __name__ == "__main__":
    asyncio.run(main())