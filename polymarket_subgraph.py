#!/usr/bin/env python3
"""
Polymarket Subgraph Analytics Integration

Provides cross-subgraph market enrichment using:
1. Names Subgraph - Human-readable market titles
2. Main Subgraph - Volume, trading metrics, positions  
3. Orderbook Subgraph - Real-time spreads, depth, liquidity
4. Activity/PnL Subgraphs - Market lifecycle and performance data
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

@dataclass
class SubgraphEndpoints:
    """Polymarket subgraph endpoint configuration"""
    names_subgraph: str = "https://api.thegraph.com/subgraphs/id/22CoTbEtpv6fURB6moTNfJPWNUPXtiFGRA8h1zajMha3"
    main_subgraph: str = "https://api.thegraph.com/subgraphs/id/QmdyCguLEisTtQFveEkvMhTH7UzjyhnrF9kpvhYeG4QX8a"
    orderbook_subgraph: str = "https://api.thegraph.com/subgraphs/id/QmTBKKxgZwCMoa9swcHCwK29BdQ9oVaZhczUC9XJ6FLpFL"
    open_interest_subgraph: str = "https://api.thegraph.com/subgraphs/id/QmbxydtB3MF2yNriAHhsrBmqTx44aaw44jjNFwZNWaW7R6"

@dataclass
class MarketEnrichmentData:
    """Enriched market data from multiple subgraphs"""
    # Core identification
    question_id: str
    market_id: Optional[str] = None
    
    # Human-readable names (Names Subgraph)
    title: Optional[str] = None
    question: Optional[str] = None
    creator: Optional[str] = None
    creation_timestamp: Optional[int] = None
    
    # Trading metrics (Main Subgraph) - Enhanced with normalized event data
    scaled_collateral_volume: Optional[float] = None
    normalized_volume_24h: Optional[float] = None  # Volume normalized for market validation
    trades_quantity: Optional[int] = None
    trades_24h: Optional[int] = None  # Recent trading activity
    outcome_token_prices: List[float] = field(default_factory=list)
    fee_rate: Optional[float] = None
    last_active_day: Optional[int] = None
    
    # Position and liquidity metrics
    total_positions: Optional[int] = None
    active_positions: Optional[int] = None
    position_value_usd: Optional[float] = None
    market_cap: Optional[float] = None
    
    # Volume validation metrics
    volume_consistency_score: Optional[float] = None  # Cross-validation score
    volume_trend_7d: Optional[float] = None  # 7-day volume trend
    avg_trade_size: Optional[float] = None
    
    # Real-time orderbook (Orderbook Subgraph)
    current_spread: Optional[float] = None
    spread_percentage: Optional[float] = None
    bid_depth: Optional[float] = None
    ask_depth: Optional[float] = None
    liquidity_score: Optional[float] = None
    order_flow_imbalance: Optional[float] = None
    last_trade_price: Optional[float] = None
    last_trade_timestamp: Optional[int] = None
    
    # Quality indicators
    enrichment_confidence: float = 0.0
    enrichment_timestamp: datetime = field(default_factory=datetime.utcnow)

class PolymarketSubgraphClient:
    """Client for querying multiple Polymarket subgraphs"""
    
    def __init__(self, endpoints: Optional[SubgraphEndpoints] = None):
        self.endpoints = endpoints or SubgraphEndpoints()
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _query_subgraph(self, endpoint: str, query: str, variables: Dict = None) -> Dict:
        """Execute GraphQL query against a subgraph"""
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        try:
            async with self.session.post(endpoint, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                
                if "errors" in result:
                    self.logger.error(f"Subgraph query errors: {result['errors']}")
                    return {}
                
                return result.get("data", {})
        
        except Exception as e:
            self.logger.error(f"Subgraph query failed: {e}")
            return {}
    
    async def get_market_names(self, question_ids: List[str]) -> Dict[str, Dict]:
        """Get human-readable market names from Names subgraph"""
        query = """
        query GetMarketNames($questionIDs: [Bytes!]) {
            markets(where: { questionID_in: $questionIDs }) {
                questionID
                question
                creator
                timestamp
                rewardToken
                reward
            }
        }
        """
        
        variables = {"questionIDs": question_ids}
        data = await self._query_subgraph(self.endpoints.names_subgraph, query, variables)
        
        # Convert to lookup dict
        names_lookup = {}
        for market in data.get("markets", []):
            names_lookup[market["questionID"].lower()] = {
                "title": market["question"],
                "creator": market["creator"],
                "creation_timestamp": int(market["timestamp"])
            }
        
        return names_lookup
    
    async def get_market_trading_data(self, question_ids: List[str]) -> Dict[str, Dict]:
        """Get enhanced trading metrics from Main subgraph with normalized event data"""
        query = """
        query GetMarketTradingData($conditions: [Bytes!], $daysSince: Int!) {
            fixedProductMarketMakers(where: { conditions_contains: $conditions }) {
                id
                conditions
                scaledCollateralVolume
                tradesQuantity
                outcomeTokenPrices
                fee
                lastActiveDay
                buysQuantity
                sellsQuantity
                collateralVolume
                outcomeTokenAmounts
                runningDailyVolume(where: { period_gte: $daysSince })
            }
            
            # Recent trading activity for validation
            fpmmTrades(
                where: { 
                    fpmm_: { conditions_contains: $conditions }
                    creationTimestamp_gte: $daysSince
                }
                orderBy: creationTimestamp
                orderDirection: desc
                first: 1000
            ) {
                fpmm { conditions }
                outcomeTokensTraded
                collateralTokenTraded
                creationTimestamp
                creator
            }
            
            # Position data for market validation
            fpmmParticipations(
                where: { fpmm_: { conditions_contains: $conditions } }
                first: 1000
            ) {
                fpmm { conditions }
                title
                collateralTokenAmount
                outcomeTokenAmounts
                creationTimestamp
            }
        }
        """
        
        # Calculate timestamp for 24h and 7d lookbacks
        current_timestamp = int(datetime.utcnow().timestamp())
        day_24h_ago = current_timestamp - (24 * 3600)
        day_7d_ago = current_timestamp - (7 * 24 * 3600)
        
        variables = {
            "conditions": question_ids,
            "daysSince": day_24h_ago
        }
        data = await self._query_subgraph(self.endpoints.main_subgraph, query, variables)
        
        # Process market makers data
        trading_lookup = {}
        trades_by_market = {}
        positions_by_market = {}
        
        # Group trades and positions by question ID
        for trade in data.get("fpmmTrades", []):
            if trade["fpmm"]["conditions"]:
                question_id = trade["fpmm"]["conditions"][0].lower()
                if question_id not in trades_by_market:
                    trades_by_market[question_id] = []
                trades_by_market[question_id].append(trade)
        
        for position in data.get("fpmmParticipations", []):
            if position["fpmm"]["conditions"]:
                question_id = position["fpmm"]["conditions"][0].lower()
                if question_id not in positions_by_market:
                    positions_by_market[question_id] = []
                positions_by_market[question_id].append(position)
        
        # Build enhanced trading data
        for market in data.get("fixedProductMarketMakers", []):
            if market["conditions"]:
                question_id = market["conditions"][0].lower()
                
                # Calculate 24h metrics from recent trades
                recent_trades = trades_by_market.get(question_id, [])
                trades_24h = len([t for t in recent_trades if int(t["creationTimestamp"]) >= day_24h_ago])
                volume_24h = sum([float(t["collateralTokenTraded"]) for t in recent_trades 
                                if int(t["creationTimestamp"]) >= day_24h_ago])
                
                # Calculate average trade size
                total_volume = float(market["scaledCollateralVolume"])
                total_trades = int(market["tradesQuantity"])
                avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
                
                # Position metrics
                market_positions = positions_by_market.get(question_id, [])
                total_positions = len(market_positions)
                active_positions = len([p for p in market_positions 
                                      if int(p["creationTimestamp"]) >= day_7d_ago])
                position_value = sum([float(p["collateralTokenAmount"]) for p in market_positions])
                
                # Volume consistency score (normalized volume vs raw volume)
                raw_volume = float(market.get("collateralVolume", 0))
                scaled_volume = float(market["scaledCollateralVolume"])
                consistency_score = scaled_volume / raw_volume if raw_volume > 0 else 0
                
                # Calculate 7-day volume trend (simplified)
                daily_volumes = market.get("runningDailyVolume", [])
                recent_volumes = [float(v.get("volume", 0)) for v in daily_volumes[-7:]]
                volume_trend = sum(recent_volumes[-3:]) / sum(recent_volumes[:4]) if len(recent_volumes) >= 7 else 1.0
                
                # Calculate market cap from outcome token amounts
                outcome_amounts = [float(amt) for amt in market.get("outcomeTokenAmounts", [])]
                market_cap = sum(outcome_amounts) if outcome_amounts else None
                
                trading_lookup[question_id] = {
                    "market_id": market["id"],
                    "scaled_collateral_volume": scaled_volume,
                    "normalized_volume_24h": volume_24h,
                    "trades_quantity": total_trades,
                    "trades_24h": trades_24h,
                    "outcome_token_prices": [float(p) for p in market["outcomeTokenPrices"]],
                    "fee_rate": float(market["fee"]),
                    "last_active_day": int(market["lastActiveDay"]) if market["lastActiveDay"] else None,
                    "buys_quantity": int(market["buysQuantity"]),
                    "sells_quantity": int(market["sellsQuantity"]),
                    "total_positions": total_positions,
                    "active_positions": active_positions,
                    "position_value_usd": position_value,
                    "market_cap": market_cap,
                    "volume_consistency_score": consistency_score,
                    "volume_trend_7d": volume_trend,
                    "avg_trade_size": avg_trade_size
                }
        
        return trading_lookup
    
    async def get_orderbook_data(self, market_ids: List[str]) -> Dict[str, Dict]:
        """Get real-time orderbook data from Orderbook subgraph"""
        query = """
        query GetOrderbookData($marketIds: [String!]) {
            orderBooks(where: { marketId_in: $marketIds }) {
                id
                marketId
                bestBid
                bestAsk
                spread
                spreadPercentage
                totalBidDepth
                totalAskDepth
                lastUpdate
            }
            spreads(where: { marketId_in: $marketIds }) {
                id
                marketId
                currentSpread
                currentSpreadPercentage
                avgSpread
                lastUpdate
            }
            orderFlows(where: { marketId_in: $marketIds }) {
                id
                marketId
                buyFlow
                sellFlow
                orderFlowImbalance
                lastUpdate
            }
            orderFills(
                where: { marketId_in: $marketIds }
                orderBy: timestamp
                orderDirection: desc
                first: 1
            ) {
                id
                marketId
                price
                timestamp
            }
        }
        """
        
        variables = {"marketIds": market_ids}
        data = await self._query_subgraph(self.endpoints.orderbook_subgraph, query, variables)
        
        # Combine all orderbook metrics
        orderbook_lookup = {}
        
        # Add orderbook depth data
        for ob in data.get("orderBooks", []):
            market_id = ob["marketId"]
            orderbook_lookup[market_id] = {
                "current_spread": float(ob["spread"]) if ob["spread"] else None,
                "spread_percentage": float(ob["spreadPercentage"]) if ob["spreadPercentage"] else None,
                "bid_depth": float(ob["totalBidDepth"]) if ob["totalBidDepth"] else None,
                "ask_depth": float(ob["totalAskDepth"]) if ob["totalAskDepth"] else None,
                "last_update": int(ob["lastUpdate"])
            }
        
        # Add spread analytics
        for spread in data.get("spreads", []):
            market_id = spread["marketId"]
            if market_id not in orderbook_lookup:
                orderbook_lookup[market_id] = {}
            orderbook_lookup[market_id].update({
                "avg_spread": float(spread["avgSpread"]) if spread["avgSpread"] else None
            })
        
        # Add order flow data
        for flow in data.get("orderFlows", []):
            market_id = flow["marketId"]
            if market_id not in orderbook_lookup:
                orderbook_lookup[market_id] = {}
            orderbook_lookup[market_id].update({
                "order_flow_imbalance": float(flow["orderFlowImbalance"]) if flow["orderFlowImbalance"] else None,
                "buy_flow": float(flow["buyFlow"]) if flow["buyFlow"] else None,
                "sell_flow": float(flow["sellFlow"]) if flow["sellFlow"] else None
            })
        
        # Add latest trade data
        for fill in data.get("orderFills", []):
            market_id = fill["marketId"]
            if market_id not in orderbook_lookup:
                orderbook_lookup[market_id] = {}
            if "last_trade_price" not in orderbook_lookup[market_id]:  # Only take the most recent
                orderbook_lookup[market_id].update({
                    "last_trade_price": float(fill["price"]),
                    "last_trade_timestamp": int(fill["timestamp"])
                })
        
        return orderbook_lookup
    
    async def enrich_markets(self, question_ids: List[str]) -> List[MarketEnrichmentData]:
        """
        Cross-subgraph market enrichment
        
        Args:
            question_ids: List of Polymarket question IDs to enrich
            
        Returns:
            List of enriched market data combining all subgraphs
        """
        self.logger.info(f"Enriching {len(question_ids)} markets with cross-subgraph data")
        
        # Parallel queries to all subgraphs
        names_task = self.get_market_names(question_ids)
        trading_task = self.get_market_trading_data(question_ids)
        
        # Wait for initial data to get market IDs for orderbook query
        names_data, trading_data = await asyncio.gather(names_task, trading_task)
        
        # Extract market IDs for orderbook queries
        market_ids = []
        for trading_info in trading_data.values():
            if trading_info.get("market_id"):
                market_ids.append(trading_info["market_id"])
        
        # Query orderbook data if we have market IDs
        orderbook_data = {}
        if market_ids:
            orderbook_data = await self.get_orderbook_data(market_ids)
        
        # Combine all data sources
        enriched_markets = []
        for question_id in question_ids:
            question_id_lower = question_id.lower()
            
            # Start with base data
            enriched = MarketEnrichmentData(question_id=question_id)
            confidence_factors = []
            
            # Add names data
            if question_id_lower in names_data:
                names_info = names_data[question_id_lower]
                enriched.title = names_info["title"]
                enriched.creator = names_info["creator"]
                enriched.creation_timestamp = names_info["creation_timestamp"]
                confidence_factors.append(0.4)  # High confidence for names match
            
            # Add enhanced trading data
            if question_id_lower in trading_data:
                trading_info = trading_data[question_id_lower]
                enriched.market_id = trading_info["market_id"]
                enriched.scaled_collateral_volume = trading_info["scaled_collateral_volume"]
                enriched.normalized_volume_24h = trading_info["normalized_volume_24h"]
                enriched.trades_quantity = trading_info["trades_quantity"]
                enriched.trades_24h = trading_info["trades_24h"]
                enriched.outcome_token_prices = trading_info["outcome_token_prices"]
                enriched.fee_rate = trading_info["fee_rate"]
                enriched.last_active_day = trading_info["last_active_day"]
                enriched.total_positions = trading_info["total_positions"]
                enriched.active_positions = trading_info["active_positions"]
                enriched.position_value_usd = trading_info["position_value_usd"]
                enriched.market_cap = trading_info["market_cap"]
                enriched.volume_consistency_score = trading_info["volume_consistency_score"]
                enriched.volume_trend_7d = trading_info["volume_trend_7d"]
                enriched.avg_trade_size = trading_info["avg_trade_size"]
                confidence_factors.append(0.3)  # Medium confidence for trading match
            
            # Add orderbook data if market ID available
            if enriched.market_id and enriched.market_id in orderbook_data:
                ob_info = orderbook_data[enriched.market_id]
                enriched.current_spread = ob_info.get("current_spread")
                enriched.spread_percentage = ob_info.get("spread_percentage")
                enriched.bid_depth = ob_info.get("bid_depth")
                enriched.ask_depth = ob_info.get("ask_depth")
                enriched.order_flow_imbalance = ob_info.get("order_flow_imbalance")
                enriched.last_trade_price = ob_info.get("last_trade_price")
                enriched.last_trade_timestamp = ob_info.get("last_trade_timestamp")
                
                # Calculate liquidity score
                if enriched.bid_depth and enriched.ask_depth:
                    enriched.liquidity_score = (enriched.bid_depth + enriched.ask_depth) / 2
                
                confidence_factors.append(0.3)  # Medium confidence for orderbook match
            
            # Calculate overall enrichment confidence
            enriched.enrichment_confidence = sum(confidence_factors)
            enriched_markets.append(enriched)
        
        self.logger.info(f"Enriched {len(enriched_markets)} markets (avg confidence: {sum(m.enrichment_confidence for m in enriched_markets) / len(enriched_markets):.2f})")
        return enriched_markets

class MarketQualityFilter:
    """Enhanced filter for markets based on liquidity, volume, and trading quality metrics"""
    
    def __init__(self, 
                 min_volume: float = 1000.0,
                 min_volume_24h: float = 100.0,
                 min_liquidity_score: float = 500.0,
                 max_spread_percentage: float = 0.05,  # 5%
                 min_trades: int = 10,
                 min_trades_24h: int = 5,
                 min_active_positions: int = 3,
                 min_volume_consistency: float = 0.1,
                 min_avg_trade_size: float = 10.0):
        self.min_volume = min_volume
        self.min_volume_24h = min_volume_24h
        self.min_liquidity_score = min_liquidity_score  
        self.max_spread_percentage = max_spread_percentage
        self.min_trades = min_trades
        self.min_trades_24h = min_trades_24h
        self.min_active_positions = min_active_positions
        self.min_volume_consistency = min_volume_consistency
        self.min_avg_trade_size = min_avg_trade_size
    
    def filter_quality_markets(self, enriched_markets: List[MarketEnrichmentData]) -> List[MarketEnrichmentData]:
        """Enhanced filter for arbitrage quality based on comprehensive trading metrics"""
        quality_markets = []
        
        for market in enriched_markets:
            # Total volume filter
            if market.scaled_collateral_volume and market.scaled_collateral_volume < self.min_volume:
                continue
            
            # Recent volume activity filter
            if market.normalized_volume_24h is not None and market.normalized_volume_24h < self.min_volume_24h:
                continue
            
            # Trading activity filter  
            if market.trades_quantity and market.trades_quantity < self.min_trades:
                continue
            
            # Recent trading activity filter
            if market.trades_24h is not None and market.trades_24h < self.min_trades_24h:
                continue
            
            # Liquidity filter
            if market.liquidity_score and market.liquidity_score < self.min_liquidity_score:
                continue
            
            # Spread filter (tighter spreads preferred)
            if market.spread_percentage and market.spread_percentage > self.max_spread_percentage:
                continue
            
            # Position activity filter (market validation)
            if market.active_positions is not None and market.active_positions < self.min_active_positions:
                continue
            
            # Volume consistency filter (data quality)
            if market.volume_consistency_score is not None and market.volume_consistency_score < self.min_volume_consistency:
                continue
            
            # Trade size filter (avoid dust trading)
            if market.avg_trade_size is not None and market.avg_trade_size < self.min_avg_trade_size:
                continue
            
            quality_markets.append(market)
        
        return quality_markets
    
    def get_filter_statistics(self, enriched_markets: List[MarketEnrichmentData]) -> Dict[str, Any]:
        """Get detailed statistics on filter performance for market validation"""
        stats = {
            "total_markets": len(enriched_markets),
            "filtered_markets": 0,
            "filter_breakdown": {
                "volume_filter": 0,
                "volume_24h_filter": 0,
                "trades_filter": 0,
                "trades_24h_filter": 0,
                "liquidity_filter": 0,
                "spread_filter": 0,
                "positions_filter": 0,
                "consistency_filter": 0,
                "trade_size_filter": 0
            },
            "quality_metrics": {
                "avg_volume": 0.0,
                "avg_24h_volume": 0.0,
                "avg_liquidity": 0.0,
                "avg_spread": 0.0,
                "avg_consistency": 0.0
            }
        }
        
        quality_markets = self.filter_quality_markets(enriched_markets)
        stats["filtered_markets"] = len(quality_markets)
        
        # Calculate filter breakdown
        for market in enriched_markets:
            if market.scaled_collateral_volume and market.scaled_collateral_volume < self.min_volume:
                stats["filter_breakdown"]["volume_filter"] += 1
            if market.normalized_volume_24h is not None and market.normalized_volume_24h < self.min_volume_24h:
                stats["filter_breakdown"]["volume_24h_filter"] += 1
            if market.trades_quantity and market.trades_quantity < self.min_trades:
                stats["filter_breakdown"]["trades_filter"] += 1
            if market.trades_24h is not None and market.trades_24h < self.min_trades_24h:
                stats["filter_breakdown"]["trades_24h_filter"] += 1
            if market.liquidity_score and market.liquidity_score < self.min_liquidity_score:
                stats["filter_breakdown"]["liquidity_filter"] += 1
            if market.spread_percentage and market.spread_percentage > self.max_spread_percentage:
                stats["filter_breakdown"]["spread_filter"] += 1
            if market.active_positions is not None and market.active_positions < self.min_active_positions:
                stats["filter_breakdown"]["positions_filter"] += 1
            if market.volume_consistency_score is not None and market.volume_consistency_score < self.min_volume_consistency:
                stats["filter_breakdown"]["consistency_filter"] += 1
            if market.avg_trade_size is not None and market.avg_trade_size < self.min_avg_trade_size:
                stats["filter_breakdown"]["trade_size_filter"] += 1
        
        # Calculate quality metrics for passing markets
        if quality_markets:
            stats["quality_metrics"]["avg_volume"] = sum(m.scaled_collateral_volume or 0 for m in quality_markets) / len(quality_markets)
            stats["quality_metrics"]["avg_24h_volume"] = sum(m.normalized_volume_24h or 0 for m in quality_markets) / len(quality_markets)
            stats["quality_metrics"]["avg_liquidity"] = sum(m.liquidity_score or 0 for m in quality_markets) / len(quality_markets)
            stats["quality_metrics"]["avg_spread"] = sum(m.spread_percentage or 0 for m in quality_markets) / len(quality_markets)
            stats["quality_metrics"]["avg_consistency"] = sum(m.volume_consistency_score or 0 for m in quality_markets) / len(quality_markets)
        
        return stats

# Example usage and testing
async def example_usage():
    """Example of cross-subgraph market enrichment"""
    question_ids = [
        "0x71f8dbd344d612f63a2cdfab1549dc5dd69d8153ac122d8640fa505b24726e2c",
        "0x123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0"
    ]
    
    async with PolymarketSubgraphClient() as client:
        enriched_markets = await client.enrich_markets(question_ids)
        
        # Apply quality filters
        quality_filter = MarketQualityFilter(
            min_volume=500.0,
            min_liquidity_score=100.0,
            max_spread_percentage=0.10  # 10%
        )
        
        quality_markets = quality_filter.filter_quality_markets(enriched_markets)
        filter_stats = quality_filter.get_filter_statistics(enriched_markets)
        
        print(f"Enhanced Analytics Results:")
        print(f"  Total markets analyzed: {filter_stats['total_markets']}")
        print(f"  Quality markets found: {filter_stats['filtered_markets']}")
        print(f"  Filter efficiency: {filter_stats['filtered_markets'] / filter_stats['total_markets']:.1%}")
        
        print(f"\nQuality Metrics (Average):")
        print(f"  Volume: ${filter_stats['quality_metrics']['avg_volume']:.2f}")
        print(f"  24h Volume: ${filter_stats['quality_metrics']['avg_24h_volume']:.2f}")
        print(f"  Liquidity Score: {filter_stats['quality_metrics']['avg_liquidity']:.2f}")
        print(f"  Spread: {filter_stats['quality_metrics']['avg_spread']:.1%}")
        print(f"  Volume Consistency: {filter_stats['quality_metrics']['avg_consistency']:.2f}")
        
        print(f"\nTop Quality Markets:")
        for market in quality_markets[:5]:
            print(f"Market: {market.title}")
            volume = market.scaled_collateral_volume or 0
            volume_24h = market.normalized_volume_24h or 0
            trades = market.trades_quantity or 0
            trades_24h = market.trades_24h or 0
            positions = market.total_positions or 0
            active_positions = market.active_positions or 0
            
            print(f"  Volume: ${volume:.2f} (24h: ${volume_24h:.2f})")
            print(f"  Trades: {trades} (24h: {trades_24h})")
            print(f"  Positions: {positions} (Active: {active_positions})")
            print(f"  Spread: {market.spread_percentage:.1%}" if market.spread_percentage else "  Spread: N/A")
            print(f"  Consistency Score: {market.volume_consistency_score:.2f}" if market.volume_consistency_score else "  Consistency: N/A")
            print(f"  Enrichment Confidence: {market.enrichment_confidence:.2f}")
            print()

if __name__ == "__main__":
    asyncio.run(example_usage())