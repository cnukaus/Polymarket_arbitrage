#!/usr/bin/env python3
"""
Quick test for market listener functionality
"""

import asyncio
import logging
from market_listener import MarketListener, NewMarketEvent

def simple_handler(event: NewMarketEvent) -> None:
    """Simple test handler"""
    print(f"TEST: New market detected - {event.condition_id}")
    print(f"      Question: {event.question}")
    print(f"      Volume: ${event.initial_volume:.2f}" if event.initial_volume else "      Volume: Unknown")

async def test_basic_functionality():
    """Test basic market listener functionality without long initialization"""

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create listener with minimal settings
    listener = MarketListener(
        poll_interval=60,  # 1 minute
        enable_subgraph=False
    )

    # Add test handler
    listener.add_new_market_handler(simple_handler)

    print("Testing market listener basic functionality...")
    print("This will run for 3 minutes maximum or until a new market is found")
    print("-" * 60)

    try:
        # Quick baseline with fewer markets to avoid long wait
        await listener.initialize_known_markets(max_markets=100)

        print(f"Baseline: {len(listener.known_condition_ids)} known markets")
        print("Starting polling for new markets...")

        # Run for limited time for testing
        start_time = asyncio.get_event_loop().time()
        max_test_time = 180  # 3 minutes

        listener.is_running = True

        while listener.is_running and (asyncio.get_event_loop().time() - start_time) < max_test_time:
            await listener._poll_for_new_markets()

            # Wait for poll interval
            await asyncio.sleep(listener.poll_interval)

            # Show we're still alive
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            print(f"[{elapsed}s] Polling... (known markets: {len(listener.known_condition_ids)})")

        print("Test completed successfully!")

    except KeyboardInterrupt:
        print("Test interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        listener.stop_listening()

    return listener.get_stats()

if __name__ == "__main__":
    stats = asyncio.run(test_basic_functionality())
    print("\nFinal test stats:", stats)