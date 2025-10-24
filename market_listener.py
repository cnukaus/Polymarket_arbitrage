#!/usr/bin/env python3
"""
Market Creation Listener for Polymarket

Real-time monitoring for newly created markets using:
1. API polling with incremental updates
2. Subgraph integration for enhanced metadata
3. Event emission for downstream processing
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
import aiohttp
import os
from dotenv import load_dotenv

# Local imports
from py_clob_client.client import ClobClient
from polymarket_subgraph import PolymarketSubgraphClient, MarketEnrichmentData

load_dotenv()

@dataclass
class NewMarketEvent:
    """Event emitted when a new market is detected"""
    market_id: str
    condition_id: str
    question: Optional[str] = None
    creator: Optional[str] = None
    creation_timestamp: Optional[int] = None
    initial_volume: Optional[float] = None
    outcome_tokens: Optional[List[str]] = field(default_factory=list)
    detection_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'market_id': self.market_id,
            'condition_id': self.condition_id,
            'question': self.question,
            'creator': self.creator,
            'creation_timestamp': self.creation_timestamp,
            'initial_volume': self.initial_volume,
            'outcome_tokens': self.outcome_tokens,
            'detection_timestamp': self.detection_timestamp
        }

class MarketListener:
    """
    Real-time market creation detector using incremental API polling
    and subgraph enrichment
    """

    def __init__(self,
                 api_key: Optional[str] = None,
                 poll_interval: int = 120,  # Increased from 30s to 2min to avoid rate limits
                 enable_subgraph: bool = False):  # Disabled by default for performance
        self.api_key = api_key or os.getenv('API_KEY')
        self.poll_interval = poll_interval
        self.enable_subgraph = enable_subgraph

        # Initialize clients
        self.client = ClobClient(
            "https://clob.polymarket.com",
            key=self.api_key,
            chain_id=137
        )

        if self.enable_subgraph:
            self.subgraph_client = PolymarketSubgraphClient()

        # State tracking
        self.known_condition_ids: Set[str] = set()
        self.last_poll_time: Optional[float] = None
        self.is_running = False

        # Error tracking for adaptive behavior
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3

        # Event handlers
        self.new_market_handlers: List[Callable[[NewMarketEvent], None]] = []

        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def add_new_market_handler(self, handler: Callable[[NewMarketEvent], None]) -> None:
        """Add a callback function to handle new market events"""
        self.new_market_handlers.append(handler)

    def remove_new_market_handler(self, handler: Callable[[NewMarketEvent], None]) -> None:
        """Remove a callback function"""
        if handler in self.new_market_handlers:
            self.new_market_handlers.remove(handler)

    async def initialize_known_markets(self, max_markets: int = 500) -> None:
        """
        Initialize baseline of existing markets to avoid false positives
        """
        self.logger.info(f"Initializing known markets baseline (max: {max_markets})...")

        try:
            # Use the same pattern as create_markets_data_csv.py (which works)
            total_loaded = 0
            next_cursor = None

            while total_loaded < max_markets:
                # Make the API call based on cursor (same as working code)
                if next_cursor is None:
                    response = self.client.get_markets()
                else:
                    response = self.client.get_markets(next_cursor=next_cursor)

                if not response or 'data' not in response:
                    break

                markets = response['data']
                next_cursor = response.get('next_cursor')

                # Add markets to known set
                for market in markets:
                    condition_id = market.get('condition_id')
                    if condition_id:
                        self.known_condition_ids.add(str(condition_id))

                total_loaded += len(markets)

                # Stop if we've loaded enough markets or no more data
                if total_loaded >= max_markets or not next_cursor:
                    break

                if total_loaded % 100 == 0:  # Log progress every 100 markets
                    self.logger.info(f"Loaded {total_loaded} existing markets...")

            self.logger.info(f"✅ Baseline established: {len(self.known_condition_ids)} known markets")
            self.last_poll_time = time.time()

        except Exception as e:
            self.logger.error(f"Failed to initialize known markets: {e}")
            raise

    async def _fetch_recent_markets(self, max_fetch: int = 50) -> List[Dict]:
        """Fetch most recent markets from API with timeout and retry logic"""
        try:
            # Use same API pattern - get_markets() without limit parameter
            self.logger.debug("Fetching recent markets from API...")

            response = self.client.get_markets()

            if response and 'data' in response:
                self.consecutive_errors = 0  # Reset error counter on success
                markets = response['data'][:max_fetch]
                self.logger.debug(f"Successfully fetched {len(markets)} markets")
                return markets
            else:
                self.logger.warning("API response missing 'data' field")
                return []

        except Exception as e:
            self.consecutive_errors += 1
            self.logger.error(f"Error fetching recent markets (attempt {self.consecutive_errors}): {e}")

            # If too many consecutive errors, increase poll interval
            if self.consecutive_errors >= self.max_consecutive_errors:
                self.poll_interval = min(self.poll_interval * 2, 600)  # Cap at 10 minutes
                self.logger.warning(f"Too many errors, increasing poll interval to {self.poll_interval}s")

            return []

    async def _enrich_with_subgraph(self, market: Dict) -> Optional[MarketEnrichmentData]:
        """Enrich market data using subgraph (if enabled)"""
        if not self.enable_subgraph:
            return None

        try:
            condition_id = market.get('condition_id')
            if not condition_id:
                return None

            # Try to get enriched data from subgraph
            enriched = await self.subgraph_client.get_market_enrichment(
                question_id=condition_id
            )
            return enriched

        except Exception as e:
            self.logger.warning(f"Subgraph enrichment failed for market {market.get('condition_id')}: {e}")
            return None

    def _create_market_event(self, market: Dict, enriched: Optional[MarketEnrichmentData] = None) -> NewMarketEvent:
        """Create a NewMarketEvent from market data"""

        # Use enriched data if available, otherwise fall back to API data
        if enriched:
            question = enriched.title or enriched.question
            creator = enriched.creator
            creation_timestamp = enriched.creation_timestamp
        else:
            question = market.get('question', market.get('description'))
            creator = market.get('market_maker_address')
            creation_timestamp = market.get('created_at')

        return NewMarketEvent(
            market_id=market.get('id', ''),
            condition_id=str(market.get('condition_id', '')),
            question=question,
            creator=creator,
            creation_timestamp=creation_timestamp,
            initial_volume=float(market.get('volume', 0)),
            outcome_tokens=market.get('tokens', []),
            detection_timestamp=time.time()
        )

    async def _emit_new_market_event(self, event: NewMarketEvent) -> None:
        """Emit new market event to all registered handlers"""
        self.logger.info(f"🆕 New market detected: {event.question} (ID: {event.condition_id})")

        for handler in self.new_market_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                self.logger.error(f"Error in market event handler: {e}")

    async def _poll_for_new_markets(self) -> None:
        """Single polling cycle to detect new markets"""
        try:
            self.logger.debug("Starting polling cycle...")

            # Fetch recent markets
            recent_markets = await self._fetch_recent_markets(max_fetch=30)  # Reduced to 30 for faster response

            if not recent_markets:
                self.logger.debug("No markets fetched, skipping cycle")
                return

            new_markets_found = 0

            for market in recent_markets:
                condition_id = str(market.get('condition_id', ''))

                if not condition_id or condition_id in self.known_condition_ids:
                    continue

                # New market detected!
                self.known_condition_ids.add(condition_id)
                new_markets_found += 1

                # Skip subgraph enrichment if disabled (for performance)
                enriched_data = None
                if self.enable_subgraph:
                    try:
                        enriched_data = await self._enrich_with_subgraph(market)
                    except Exception as e:
                        self.logger.warning(f"Subgraph enrichment failed for {condition_id}: {e}")

                # Create and emit event
                event = self._create_market_event(market, enriched_data)
                await self._emit_new_market_event(event)

            if new_markets_found > 0:
                self.logger.info(f"Polling cycle complete: {new_markets_found} new markets found")
            else:
                self.logger.debug("Polling cycle complete: no new markets")

        except Exception as e:
            self.logger.error(f"Error during polling cycle: {e}")
            self.consecutive_errors += 1

    async def start_listening(self) -> None:
        """
        Start the market listening loop
        """
        if self.is_running:
            self.logger.warning("Market listener is already running")
            return

        self.logger.info(f"🎯 Starting market listener (poll interval: {self.poll_interval}s)")

        # Initialize baseline if not done yet
        if not self.known_condition_ids:
            await self.initialize_known_markets()

        self.is_running = True

        try:
            while self.is_running:
                poll_start = time.time()

                await self._poll_for_new_markets()

                # Calculate sleep time to maintain consistent interval
                poll_duration = time.time() - poll_start
                sleep_time = max(0, self.poll_interval - poll_duration)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    self.logger.warning(f"Polling took {poll_duration:.1f}s (longer than {self.poll_interval}s interval)")

        except asyncio.CancelledError:
            self.logger.info("Market listener cancelled")
        except Exception as e:
            self.logger.error(f"Market listener crashed: {e}")
            raise
        finally:
            self.is_running = False
            self.logger.info("🛑 Market listener stopped")

    def stop_listening(self) -> None:
        """Stop the market listening loop"""
        self.is_running = False
        self.logger.info("🛑 Market listener stop requested")

    def get_stats(self) -> Dict[str, Any]:
        """Get listener statistics"""
        return {
            'is_running': self.is_running,
            'known_markets_count': len(self.known_condition_ids),
            'poll_interval': self.poll_interval,
            'last_poll_time': self.last_poll_time,
            'handlers_count': len(self.new_market_handlers),
            'subgraph_enabled': self.enable_subgraph
        }


# Example usage and handlers
async def example_new_market_handler(event: NewMarketEvent) -> None:
    """Example handler for new market events"""
    print(f"📢 NEW MARKET ALERT!")
    print(f"   Question: {event.question}")
    print(f"   ID: {event.condition_id}")
    print(f"   Creator: {event.creator}")
    print(f"   Initial Volume: ${event.initial_volume:.2f}" if event.initial_volume else "   Initial Volume: Unknown")
    print(f"   Detected: {datetime.fromtimestamp(event.detection_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

def simple_logging_handler(event: NewMarketEvent) -> None:
    """Simple synchronous logging handler"""
    logging.getLogger('market_alerts').info(
        f"New market: {event.question} | ID: {event.condition_id}"
    )

if __name__ == "__main__":
    async def main():
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Create listener with optimized settings
        listener = MarketListener(
            poll_interval=120,  # Check every 2 minutes to avoid rate limits
            enable_subgraph=False  # Disable for better performance
        )

        # Add handlers
        listener.add_new_market_handler(example_new_market_handler)
        listener.add_new_market_handler(simple_logging_handler)

        try:
            # Start listening
            await listener.start_listening()
        except KeyboardInterrupt:
            print("\nShutting down market listener...")
            listener.stop_listening()
        except Exception as e:
            print(f"Error: {e}")

        print("Final stats:", listener.get_stats())

    # Run the example
    asyncio.run(main())