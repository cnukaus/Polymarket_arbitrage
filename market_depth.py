#!/usr/bin/env python3
"""
Market Depth Analysis and Slippage Calculator

Analyzes orderbook depth to calculate price impact and slippage for arbitrage trades.
Uses Polymarket Orderbook subgraph data to estimate execution costs.
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import math
import logging

from polymarket_subgraph import PolymarketSubgraphClient, SubgraphEndpoints

@dataclass 
class PriceLevel:
    """Individual price level in the orderbook"""
    price: float
    size: float
    cumulative_size: float = 0.0  # Running total from best price

@dataclass
class OrderbookDepth:
    """Complete orderbook depth analysis"""
    market_id: str
    question_id: str
    
    # Best quotes
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    spread_percentage: Optional[float] = None
    mid_price: Optional[float] = None
    
    # Depth levels
    bid_levels: List[PriceLevel] = field(default_factory=list)
    ask_levels: List[PriceLevel] = field(default_factory=list)
    
    # Aggregate depth metrics
    total_bid_depth: float = 0.0
    total_ask_depth: float = 0.0
    depth_imbalance: Optional[float] = None  # (bids - asks) / (bids + asks)
    
    # Depth at specific percentages from mid
    depth_1pct: Optional[float] = None  # Depth within 1% of mid
    depth_5pct: Optional[float] = None  # Depth within 5% of mid
    depth_10pct: Optional[float] = None  # Depth within 10% of mid

@dataclass
class SlippageEstimate:
    """Slippage calculation for a specific trade size and direction"""
    market_id: str
    side: str  # "buy" or "sell"
    nominal_size: float
    
    # Execution estimates
    average_fill_price: Optional[float] = None
    expected_fill_price: Optional[float] = None  # Without slippage
    slippage_absolute: Optional[float] = None
    slippage_percentage: Optional[float] = None
    
    # Impact metrics
    price_impact: Optional[float] = None  # Price movement from trade
    liquidity_consumed: Optional[float] = None  # % of available liquidity used
    
    # Feasibility
    can_execute: bool = False
    max_executable_size: Optional[float] = None
    depth_exhausted: bool = False
    
    # Breakdown
    levels_consumed: List[Tuple[float, float]] = field(default_factory=list)  # (price, size) pairs

class MarketDepthAnalyzer:
    """Analyzes market depth and calculates slippage for arbitrage sizing"""
    
    def __init__(self, subgraph_client: PolymarketSubgraphClient):
        self.client = subgraph_client
        self.logger = logging.getLogger(__name__)
        
        # Configuration for depth analysis
        self.config = {
            "max_price_levels": 20,  # Max levels to analyze per side
            "min_level_size": 10.0,   # Minimum size to consider a level
            "depth_percentages": [0.01, 0.05, 0.10],  # 1%, 5%, 10% from mid
        }
    
    async def get_market_depth(self, market_id: str, question_id: str) -> OrderbookDepth:
        """
        Get comprehensive orderbook depth analysis for a market
        
        Args:
            market_id: Market identifier
            question_id: Question identifier for context
            
        Returns:
            OrderbookDepth with full depth analysis
        """
        # Query orderbook data from subgraph
        orderbook_data = await self.client.get_orderbook_data([market_id])
        
        if market_id not in orderbook_data:
            self.logger.warning(f"No orderbook data found for market {market_id}")
            return OrderbookDepth(market_id=market_id, question_id=question_id)
        
        ob_data = orderbook_data[market_id]
        
        # Get additional price level data
        price_levels = await self._get_price_levels(market_id)
        
        # Build depth analysis
        depth = OrderbookDepth(
            market_id=market_id,
            question_id=question_id,
            best_bid=ob_data.get("best_bid"),
            best_ask=ob_data.get("best_ask"),
            spread=ob_data.get("current_spread"),
            spread_percentage=ob_data.get("spread_percentage"),
            total_bid_depth=ob_data.get("bid_depth", 0.0),
            total_ask_depth=ob_data.get("ask_depth", 0.0)
        )
        
        # Calculate mid price
        if depth.best_bid and depth.best_ask:
            depth.mid_price = (depth.best_bid + depth.best_ask) / 2
        
        # Calculate depth imbalance
        if depth.total_bid_depth > 0 or depth.total_ask_depth > 0:
            total_depth = depth.total_bid_depth + depth.total_ask_depth
            depth.depth_imbalance = (depth.total_bid_depth - depth.total_ask_depth) / total_depth
        
        # Process price levels if available
        if price_levels:
            depth.bid_levels, depth.ask_levels = self._process_price_levels(
                price_levels, depth.mid_price
            )
            
            # Calculate depth at specific percentages
            if depth.mid_price:
                depth.depth_1pct = self._calculate_depth_within_percentage(
                    depth, 0.01
                )
                depth.depth_5pct = self._calculate_depth_within_percentage(
                    depth, 0.05
                )
                depth.depth_10pct = self._calculate_depth_within_percentage(
                    depth, 0.10
                )
        
        return depth
    
    async def _get_price_levels(self, market_id: str) -> List[Dict]:
        """Get detailed price levels from subgraph"""
        query = """
        query GetPriceLevels($marketId: String!) {
            priceLevels(
                where: { marketId: $marketId }
                orderBy: price
                orderDirection: asc
                first: 40
            ) {
                id
                marketId
                price
                side
                totalSize
                orderCount
                lastUpdate
            }
        }
        """
        
        variables = {"marketId": market_id}
        try:
            data = await self.client._query_subgraph(
                self.client.endpoints.orderbook_subgraph,
                query,
                variables
            )
            return data.get("priceLevels", [])
        except Exception as e:
            self.logger.warning(f"Failed to get price levels for {market_id}: {e}")
            return []
    
    def _process_price_levels(self, price_levels: List[Dict], mid_price: Optional[float]) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """Process raw price levels into organized bid/ask levels"""
        bid_levels = []
        ask_levels = []
        
        for level in price_levels:
            price = float(level["price"])
            size = float(level["totalSize"])
            
            # Filter out tiny levels
            if size < self.config["min_level_size"]:
                continue
            
            price_level = PriceLevel(price=price, size=size)
            
            # Classify as bid or ask
            if level["side"] == "BUY":
                bid_levels.append(price_level)
            elif level["side"] == "SELL":
                ask_levels.append(price_level)
        
        # Sort levels (bids descending, asks ascending)
        bid_levels.sort(key=lambda x: x.price, reverse=True)
        ask_levels.sort(key=lambda x: x.price)
        
        # Calculate cumulative sizes
        self._calculate_cumulative_sizes(bid_levels)
        self._calculate_cumulative_sizes(ask_levels)
        
        return bid_levels, ask_levels
    
    def _calculate_cumulative_sizes(self, levels: List[PriceLevel]):
        """Calculate running cumulative sizes for price levels"""
        cumulative = 0.0
        for level in levels:
            cumulative += level.size
            level.cumulative_size = cumulative
    
    def _calculate_depth_within_percentage(self, depth: OrderbookDepth, percentage: float) -> Optional[float]:
        """Calculate total depth within percentage of mid price"""
        if not depth.mid_price:
            return None
        
        total_depth = 0.0
        threshold_range = depth.mid_price * percentage
        
        # Count bid depth within range
        for level in depth.bid_levels:
            if depth.mid_price - level.price <= threshold_range:
                total_depth += level.size
        
        # Count ask depth within range
        for level in depth.ask_levels:
            if level.price - depth.mid_price <= threshold_range:
                total_depth += level.size
        
        return total_depth
    
    def calculate_slippage(self, depth: OrderbookDepth, side: str, size: float) -> SlippageEstimate:
        """
        Calculate slippage estimate for a trade of given size and direction
        
        Args:
            depth: OrderbookDepth analysis
            side: "buy" or "sell"
            size: Nominal trade size
            
        Returns:
            SlippageEstimate with execution analysis
        """
        estimate = SlippageEstimate(
            market_id=depth.market_id,
            side=side,
            nominal_size=size
        )
        
        # Get the appropriate levels to consume
        if side == "buy":
            levels = depth.ask_levels  # Buy from asks
            expected_price = depth.best_ask
        else:
            levels = depth.bid_levels  # Sell to bids  
            expected_price = depth.best_bid
        
        if not levels or expected_price is None:
            self.logger.warning(f"No {side} levels available for {depth.market_id}")
            return estimate
        
        estimate.expected_fill_price = expected_price
        
        # Walk through price levels to calculate execution
        remaining_size = size
        total_cost = 0.0
        levels_consumed = []
        
        for level in levels:
            if remaining_size <= 0:
                break
                
            # Determine how much we can fill at this level
            fill_at_level = min(remaining_size, level.size)
            
            # Add to cost calculation
            total_cost += fill_at_level * level.price
            levels_consumed.append((level.price, fill_at_level))
            
            remaining_size -= fill_at_level
        
        # Calculate results
        if total_cost > 0:
            filled_size = size - remaining_size
            estimate.average_fill_price = total_cost / filled_size
            estimate.levels_consumed = levels_consumed
            estimate.can_execute = remaining_size == 0
            estimate.max_executable_size = filled_size
            estimate.depth_exhausted = remaining_size > 0
            
            # Calculate slippage
            if estimate.expected_fill_price:
                estimate.slippage_absolute = abs(estimate.average_fill_price - estimate.expected_fill_price)
                estimate.slippage_percentage = estimate.slippage_absolute / estimate.expected_fill_price
            
            # Calculate price impact (movement from mid)
            if depth.mid_price:
                estimate.price_impact = abs(estimate.average_fill_price - depth.mid_price) / depth.mid_price
            
            # Calculate liquidity consumed
            total_available = depth.total_ask_depth if side == "buy" else depth.total_bid_depth
            if total_available > 0:
                estimate.liquidity_consumed = filled_size / total_available
        
        return estimate
    
    def calculate_arbitrage_slippage(self, 
                                   depth_a: OrderbookDepth, 
                                   depth_b: OrderbookDepth,
                                   size: float) -> Dict[str, SlippageEstimate]:
        """
        Calculate slippage for both legs of an arbitrage trade
        
        Args:
            depth_a: Orderbook depth for venue A
            depth_b: Orderbook depth for venue B  
            size: Trade size for both legs
            
        Returns:
            Dictionary with slippage estimates for both legs
        """
        # For arbitrage, we typically:
        # - Buy on the venue with lower price (better value)
        # - Sell on the venue with higher price (better exit)
        
        results = {}
        
        # Determine which venue has better pricing
        mid_a = depth_a.mid_price or (depth_a.best_bid + depth_a.best_ask) / 2 if depth_a.best_bid and depth_a.best_ask else None
        mid_b = depth_b.mid_price or (depth_b.best_bid + depth_b.best_ask) / 2 if depth_b.best_bid and depth_b.best_ask else None
        
        if mid_a is None or mid_b is None:
            self.logger.error("Cannot calculate arbitrage slippage without mid prices")
            return results
        
        if mid_a < mid_b:
            # Buy on A (cheaper), sell on B (more expensive)
            results["buy_leg"] = self.calculate_slippage(depth_a, "buy", size)
            results["sell_leg"] = self.calculate_slippage(depth_b, "sell", size)
            results["buy_venue"] = depth_a.market_id
            results["sell_venue"] = depth_b.market_id
        else:
            # Buy on B (cheaper), sell on A (more expensive)
            results["buy_leg"] = self.calculate_slippage(depth_b, "buy", size)
            results["sell_leg"] = self.calculate_slippage(depth_a, "sell", size)
            results["buy_venue"] = depth_b.market_id
            results["sell_venue"] = depth_a.market_id
        
        return results
    
    def assess_arbitrage_feasibility(self, 
                                   slippage_results: Dict[str, SlippageEstimate],
                                   target_edge: float = 0.02,
                                   max_slippage: float = 0.01) -> Dict[str, any]:
        """
        Assess if arbitrage is feasible given slippage constraints
        
        Args:
            slippage_results: Results from calculate_arbitrage_slippage()
            target_edge: Minimum edge required after costs
            max_slippage: Maximum acceptable slippage per leg
            
        Returns:
            Feasibility assessment with recommendations
        """
        assessment = {
            "feasible": False,
            "max_size": 0.0,
            "total_slippage": 0.0,
            "net_edge_after_slippage": 0.0,
            "constraints": []
        }
        
        if "buy_leg" not in slippage_results or "sell_leg" not in slippage_results:
            assessment["constraints"].append("Missing slippage calculations")
            return assessment
        
        buy_leg = slippage_results["buy_leg"]
        sell_leg = slippage_results["sell_leg"]
        
        # Check if both legs can execute
        if not buy_leg.can_execute:
            assessment["constraints"].append(f"Buy leg cannot execute full size (max: {buy_leg.max_executable_size})")
        
        if not sell_leg.can_execute:
            assessment["constraints"].append(f"Sell leg cannot execute full size (max: {sell_leg.max_executable_size})")
        
        # Calculate maximum executable size
        if buy_leg.max_executable_size and sell_leg.max_executable_size:
            assessment["max_size"] = min(buy_leg.max_executable_size, sell_leg.max_executable_size)
        
        # Check slippage constraints
        buy_slippage = buy_leg.slippage_percentage or 0.0
        sell_slippage = sell_leg.slippage_percentage or 0.0
        total_slippage = buy_slippage + sell_slippage
        
        assessment["total_slippage"] = total_slippage
        
        if buy_slippage > max_slippage:
            assessment["constraints"].append(f"Buy leg slippage too high: {buy_slippage:.2%} > {max_slippage:.2%}")
        
        if sell_slippage > max_slippage:
            assessment["constraints"].append(f"Sell leg slippage too high: {sell_slippage:.2%} > {max_slippage:.2%}")
        
        # Calculate theoretical edge after slippage
        if buy_leg.average_fill_price and sell_leg.average_fill_price:
            gross_edge = (sell_leg.average_fill_price - buy_leg.average_fill_price) / buy_leg.average_fill_price
            net_edge = gross_edge - total_slippage
            assessment["net_edge_after_slippage"] = net_edge
            
            if net_edge < target_edge:
                assessment["constraints"].append(f"Net edge too low: {net_edge:.2%} < {target_edge:.2%}")
        
        # Final feasibility determination
        assessment["feasible"] = (
            len(assessment["constraints"]) == 0 and
            assessment["max_size"] > 0 and
            total_slippage <= max_slippage * 2  # Total for both legs
        )
        
        return assessment

# Example usage and testing
async def example_depth_analysis():
    """Example of market depth analysis and slippage calculation"""
    
    endpoints = SubgraphEndpoints()
    async with PolymarketSubgraphClient(endpoints) as client:
        analyzer = MarketDepthAnalyzer(client)
        
        # Example market IDs (would be real IDs in practice)
        market_a_id = "example_market_a"
        market_b_id = "example_market_b"
        question_id = "example_question"
        
        print("Analyzing market depth and slippage...")
        
        # Get depth analysis for both markets
        depth_a = await analyzer.get_market_depth(market_a_id, question_id)
        depth_b = await analyzer.get_market_depth(market_b_id, question_id)
        
        print(f"\nMarket A Depth:")
        print(f"  Best Bid/Ask: {depth_a.best_bid}/{depth_a.best_ask}")
        print(f"  Spread: {depth_a.spread_percentage:.2%}" if depth_a.spread_percentage else "  Spread: N/A")
        print(f"  Total Depth: ${depth_a.total_bid_depth:.2f} bids / ${depth_a.total_ask_depth:.2f} asks")
        print(f"  Depth Imbalance: {depth_a.depth_imbalance:.2%}" if depth_a.depth_imbalance else "  Depth Imbalance: N/A")
        
        print(f"\nMarket B Depth:")
        print(f"  Best Bid/Ask: {depth_b.best_bid}/{depth_b.best_ask}")
        print(f"  Spread: {depth_b.spread_percentage:.2%}" if depth_b.spread_percentage else "  Spread: N/A")
        print(f"  Total Depth: ${depth_b.total_bid_depth:.2f} bids / ${depth_b.total_ask_depth:.2f} asks")
        print(f"  Depth Imbalance: {depth_b.depth_imbalance:.2%}" if depth_b.depth_imbalance else "  Depth Imbalance: N/A")
        
        # Calculate arbitrage slippage
        trade_size = 1000.0  # $1000 trade
        slippage_results = analyzer.calculate_arbitrage_slippage(depth_a, depth_b, trade_size)
        
        if slippage_results:
            print(f"\nArbitrage Slippage Analysis (${trade_size} trade):")
            
            buy_leg = slippage_results.get("buy_leg")
            sell_leg = slippage_results.get("sell_leg")
            
            if buy_leg:
                print(f"  Buy Leg ({slippage_results.get('buy_venue')}):")
                print(f"    Expected Price: {buy_leg.expected_fill_price:.4f}")
                print(f"    Average Fill: {buy_leg.average_fill_price:.4f}")
                print(f"    Slippage: {buy_leg.slippage_percentage:.2%}" if buy_leg.slippage_percentage else "    Slippage: N/A")
                print(f"    Can Execute: {buy_leg.can_execute}")
            
            if sell_leg:
                print(f"  Sell Leg ({slippage_results.get('sell_venue')}):")
                print(f"    Expected Price: {sell_leg.expected_fill_price:.4f}")
                print(f"    Average Fill: {sell_leg.average_fill_price:.4f}")
                print(f"    Slippage: {sell_leg.slippage_percentage:.2%}" if sell_leg.slippage_percentage else "    Slippage: N/A")
                print(f"    Can Execute: {sell_leg.can_execute}")
            
            # Feasibility assessment
            assessment = analyzer.assess_arbitrage_feasibility(
                slippage_results,
                target_edge=0.02,  # 2% target
                max_slippage=0.01  # 1% max slippage per leg
            )
            
            print(f"\nArbitrage Feasibility:")
            print(f"  Feasible: {assessment['feasible']}")
            print(f"  Max Size: ${assessment['max_size']:.2f}")
            print(f"  Total Slippage: {assessment['total_slippage']:.2%}")
            print(f"  Net Edge After Slippage: {assessment['net_edge_after_slippage']:.2%}")
            if assessment['constraints']:
                print(f"  Constraints: {', '.join(assessment['constraints'])}")

if __name__ == "__main__":
    asyncio.run(example_depth_analysis())