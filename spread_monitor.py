#!/usr/bin/env python3
"""
Real-time Spread Monitoring for Arbitrage Timing

Monitors bid-ask spreads across multiple venues to identify optimal arbitrage timing.
Uses Polymarket Orderbook subgraph for real-time spread analysis.
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

from polymarket_subgraph import PolymarketSubgraphClient, SubgraphEndpoints

class SpreadAlertType(Enum):
    SPREAD_COMPRESSION = "compression"  # Spread narrowing (better for entry)
    SPREAD_EXPANSION = "expansion"      # Spread widening (worse for entry)
    VOLUME_SPIKE = "volume_spike"       # High volume activity
    FLOW_IMBALANCE = "flow_imbalance"   # Order flow strongly biased

@dataclass
class SpreadSnapshot:
    """Point-in-time spread data for a market"""
    market_id: str
    question_id: str
    timestamp: datetime
    
    # Spread metrics
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    spread_absolute: Optional[float] = None
    spread_percentage: Optional[float] = None
    mid_price: Optional[float] = None
    
    # Depth metrics
    bid_depth: Optional[float] = None
    ask_depth: Optional[float] = None
    total_liquidity: Optional[float] = None
    depth_imbalance: Optional[float] = None  # (bid_depth - ask_depth) / (bid_depth + ask_depth)
    
    # Flow metrics
    order_flow_imbalance: Optional[float] = None
    buy_pressure: Optional[float] = None
    sell_pressure: Optional[float] = None
    
    # Recent activity
    last_trade_price: Optional[float] = None
    last_trade_timestamp: Optional[datetime] = None
    volume_1min: Optional[float] = None

@dataclass
class SpreadAlert:
    """Alert for significant spread or liquidity changes"""
    alert_type: SpreadAlertType
    market_id: str
    question_id: str
    timestamp: datetime
    
    # Alert details
    message: str
    severity: str  # "low", "medium", "high"
    
    # Supporting data
    current_spread: Optional[float] = None
    previous_spread: Optional[float] = None
    spread_change: Optional[float] = None
    confidence: float = 0.0
    
    # Context data
    context_data: Dict[str, Any] = field(default_factory=dict)

class SpreadMonitor:
    """Real-time spread monitoring and alerting system"""
    
    def __init__(self, 
                 subgraph_client: PolymarketSubgraphClient,
                 alert_callback: Optional[Callable[[SpreadAlert], None]] = None,
                 monitoring_interval: int = 30,  # seconds
                 spread_history_size: int = 20):
        
        self.client = subgraph_client
        self.alert_callback = alert_callback or self._default_alert_handler
        self.monitoring_interval = monitoring_interval
        self.spread_history_size = spread_history_size
        
        # State tracking
        self.monitored_markets: Dict[str, str] = {}  # market_id -> question_id
        self.spread_history: Dict[str, List[SpreadSnapshot]] = {}  # market_id -> snapshots
        self.alert_cooldowns: Dict[str, datetime] = {}  # market_id -> last_alert_time
        
        # Configuration
        self.alert_thresholds = {
            "spread_compression_pct": 0.20,  # 20% spread decrease
            "spread_expansion_pct": 0.50,    # 50% spread increase
            "flow_imbalance_threshold": 0.30, # 30% flow imbalance
            "volume_spike_multiplier": 3.0,   # 3x normal volume
            "cooldown_minutes": 5             # 5 minutes between similar alerts
        }
        
        self.logger = logging.getLogger(__name__)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
    
    def add_market(self, market_id: str, question_id: str):
        """Add a market to monitoring"""
        self.monitored_markets[market_id] = question_id
        self.spread_history[market_id] = []
        self.logger.info(f"Added market {market_id} to spread monitoring")
    
    def remove_market(self, market_id: str):
        """Remove a market from monitoring"""
        self.monitored_markets.pop(market_id, None)
        self.spread_history.pop(market_id, None)
        self.alert_cooldowns.pop(market_id, None)
        self.logger.info(f"Removed market {market_id} from spread monitoring")
    
    async def _fetch_current_spreads(self) -> List[SpreadSnapshot]:
        """Fetch current spread data for all monitored markets"""
        if not self.monitored_markets:
            return []
        
        market_ids = list(self.monitored_markets.keys())
        orderbook_data = await self.client.get_orderbook_data(market_ids)
        
        snapshots = []
        current_time = datetime.utcnow()
        
        for market_id, question_id in self.monitored_markets.items():
            if market_id not in orderbook_data:
                continue
                
            ob_data = orderbook_data[market_id]
            
            # Calculate spread metrics
            spread_abs = ob_data.get("current_spread")
            spread_pct = ob_data.get("spread_percentage")
            bid_depth = ob_data.get("bid_depth")
            ask_depth = ob_data.get("ask_depth")
            
            # Calculate derived metrics
            mid_price = None
            depth_imbalance = None
            total_liquidity = None
            
            if bid_depth and ask_depth:
                total_liquidity = bid_depth + ask_depth
                depth_imbalance = (bid_depth - ask_depth) / total_liquidity
            
            # Create snapshot
            snapshot = SpreadSnapshot(
                market_id=market_id,
                question_id=question_id,
                timestamp=current_time,
                spread_absolute=spread_abs,
                spread_percentage=spread_pct,
                mid_price=mid_price,
                bid_depth=bid_depth,
                ask_depth=ask_depth,
                total_liquidity=total_liquidity,
                depth_imbalance=depth_imbalance,
                order_flow_imbalance=ob_data.get("order_flow_imbalance"),
                buy_pressure=ob_data.get("buy_flow"),
                sell_pressure=ob_data.get("sell_flow"),
                last_trade_price=ob_data.get("last_trade_price"),
                last_trade_timestamp=datetime.fromtimestamp(ob_data["last_trade_timestamp"]) if ob_data.get("last_trade_timestamp") else None
            )
            
            snapshots.append(snapshot)
        
        return snapshots
    
    def _update_spread_history(self, snapshots: List[SpreadSnapshot]):
        """Update historical spread data and trim to max size"""
        for snapshot in snapshots:
            market_id = snapshot.market_id
            
            if market_id not in self.spread_history:
                self.spread_history[market_id] = []
            
            history = self.spread_history[market_id]
            history.append(snapshot)
            
            # Trim to max size
            if len(history) > self.spread_history_size:
                history.pop(0)
    
    def _analyze_spread_changes(self, current_snapshots: List[SpreadSnapshot]) -> List[SpreadAlert]:
        """Analyze spread changes and generate alerts"""
        alerts = []
        current_time = datetime.utcnow()
        
        for snapshot in current_snapshots:
            market_id = snapshot.market_id
            
            # Check cooldown
            if market_id in self.alert_cooldowns:
                cooldown_end = self.alert_cooldowns[market_id] + timedelta(
                    minutes=self.alert_thresholds["cooldown_minutes"]
                )
                if current_time < cooldown_end:
                    continue
            
            history = self.spread_history.get(market_id, [])
            if len(history) < 2:
                continue  # Need at least 2 data points
                
            previous_snapshot = history[-2]
            
            # Analyze spread compression/expansion
            if (snapshot.spread_percentage and 
                previous_snapshot.spread_percentage and
                snapshot.spread_percentage > 0 and 
                previous_snapshot.spread_percentage > 0):
                
                spread_change = (snapshot.spread_percentage - previous_snapshot.spread_percentage) / previous_snapshot.spread_percentage
                
                # Spread compression (good for arbitrage entry)
                if spread_change <= -self.alert_thresholds["spread_compression_pct"]:
                    alert = SpreadAlert(
                        alert_type=SpreadAlertType.SPREAD_COMPRESSION,
                        market_id=market_id,
                        question_id=snapshot.question_id,
                        timestamp=current_time,
                        message=f"Spread compressed by {abs(spread_change):.1%} - better arbitrage entry opportunity",
                        severity="medium",
                        current_spread=snapshot.spread_percentage,
                        previous_spread=previous_snapshot.spread_percentage,
                        spread_change=spread_change,
                        confidence=0.8
                    )
                    alerts.append(alert)
                
                # Spread expansion (worse for arbitrage)
                elif spread_change >= self.alert_thresholds["spread_expansion_pct"]:
                    alert = SpreadAlert(
                        alert_type=SpreadAlertType.SPREAD_EXPANSION,
                        market_id=market_id,
                        question_id=snapshot.question_id,
                        timestamp=current_time,
                        message=f"Spread expanded by {spread_change:.1%} - arbitrage opportunity degrading",
                        severity="low",
                        current_spread=snapshot.spread_percentage,
                        previous_spread=previous_snapshot.spread_percentage,
                        spread_change=spread_change,
                        confidence=0.7
                    )
                    alerts.append(alert)
            
            # Analyze order flow imbalance
            if (snapshot.order_flow_imbalance and 
                abs(snapshot.order_flow_imbalance) >= self.alert_thresholds["flow_imbalance_threshold"]):
                
                direction = "buy" if snapshot.order_flow_imbalance > 0 else "sell"
                alert = SpreadAlert(
                    alert_type=SpreadAlertType.FLOW_IMBALANCE,
                    market_id=market_id,
                    question_id=snapshot.question_id,
                    timestamp=current_time,
                    message=f"Strong {direction} flow imbalance ({snapshot.order_flow_imbalance:.1%}) detected",
                    severity="medium",
                    confidence=0.7,
                    context_data={
                        "flow_imbalance": snapshot.order_flow_imbalance,
                        "buy_pressure": snapshot.buy_pressure,
                        "sell_pressure": snapshot.sell_pressure
                    }
                )
                alerts.append(alert)
            
            # Analyze volume spikes
            if len(history) >= 5:  # Need some history for volume baseline
                recent_volumes = []
                for h in history[-5:-1]:  # Last 4 snapshots excluding current
                    if h.volume_1min:
                        recent_volumes.append(h.volume_1min)
                
                if recent_volumes and snapshot.volume_1min:
                    avg_volume = statistics.mean(recent_volumes)
                    if avg_volume > 0 and snapshot.volume_1min >= avg_volume * self.alert_thresholds["volume_spike_multiplier"]:
                        alert = SpreadAlert(
                            alert_type=SpreadAlertType.VOLUME_SPIKE,
                            market_id=market_id,
                            question_id=snapshot.question_id,
                            timestamp=current_time,
                            message=f"Volume spike detected: {snapshot.volume_1min:.2f} vs avg {avg_volume:.2f}",
                            severity="high",
                            confidence=0.9,
                            context_data={
                                "current_volume": snapshot.volume_1min,
                                "average_volume": avg_volume,
                                "spike_ratio": snapshot.volume_1min / avg_volume
                            }
                        )
                        alerts.append(alert)
        
        # Update cooldowns for markets with alerts
        for alert in alerts:
            self.alert_cooldowns[alert.market_id] = current_time
        
        return alerts
    
    def _default_alert_handler(self, alert: SpreadAlert):
        """Default alert handler - logs to console"""
        self.logger.warning(f"SPREAD ALERT [{alert.severity.upper()}]: {alert.message} (Market: {alert.market_id})")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info(f"Starting spread monitoring loop (interval: {self.monitoring_interval}s)")
        
        while self._running:
            try:
                # Fetch current spread data
                current_snapshots = await self._fetch_current_spreads()
                
                if current_snapshots:
                    # Update historical data
                    self._update_spread_history(current_snapshots)
                    
                    # Analyze for alerts
                    alerts = self._analyze_spread_changes(current_snapshots)
                    
                    # Send alerts
                    for alert in alerts:
                        try:
                            self.alert_callback(alert)
                        except Exception as e:
                            self.logger.error(f"Alert callback failed: {e}")
                    
                    if alerts:
                        self.logger.info(f"Generated {len(alerts)} spread alerts")
                
                # Wait for next cycle
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(min(self.monitoring_interval, 60))  # Back off on error
    
    async def start_monitoring(self):
        """Start the spread monitoring system"""
        if self._monitoring_task and not self._monitoring_task.done():
            self.logger.warning("Monitoring already running")
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Spread monitoring started")
    
    async def stop_monitoring(self):
        """Stop the spread monitoring system"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Spread monitoring stopped")
    
    def get_current_spread_summary(self) -> Dict[str, Dict]:
        """Get current spread summary for all monitored markets"""
        summary = {}
        
        for market_id in self.monitored_markets:
            history = self.spread_history.get(market_id, [])
            if not history:
                continue
                
            latest = history[-1]
            
            # Calculate trend if we have enough history
            trend = None
            if len(history) >= 3:
                recent_spreads = [s.spread_percentage for s in history[-3:] if s.spread_percentage]
                if len(recent_spreads) >= 3:
                    trend = "decreasing" if recent_spreads[-1] < recent_spreads[0] else "increasing"
            
            summary[market_id] = {
                "question_id": latest.question_id,
                "current_spread_pct": latest.spread_percentage,
                "current_liquidity": latest.total_liquidity,
                "depth_imbalance": latest.depth_imbalance,
                "flow_imbalance": latest.order_flow_imbalance,
                "last_trade_price": latest.last_trade_price,
                "spread_trend": trend,
                "last_updated": latest.timestamp
            }
        
        return summary

# Example usage
async def example_spread_monitoring():
    """Example of real-time spread monitoring"""
    
    def custom_alert_handler(alert: SpreadAlert):
        """Custom alert handler"""
        print(f"\n🚨 {alert.alert_type.value.upper()} ALERT 🚨")
        print(f"Market: {alert.question_id}")
        print(f"Message: {alert.message}")
        print(f"Severity: {alert.severity}")
        print(f"Confidence: {alert.confidence:.2f}")
        if alert.current_spread:
            print(f"Current Spread: {alert.current_spread:.2%}")
        print("-" * 50)
    
    # Initialize components
    endpoints = SubgraphEndpoints()
    async with PolymarketSubgraphClient(endpoints) as client:
        monitor = SpreadMonitor(
            subgraph_client=client,
            alert_callback=custom_alert_handler,
            monitoring_interval=30  # Check every 30 seconds
        )
        
        # Add some markets to monitor
        market_examples = [
            ("market_id_1", "question_id_1"),
            ("market_id_2", "question_id_2"),
        ]
        
        for market_id, question_id in market_examples:
            monitor.add_market(market_id, question_id)
        
        # Start monitoring
        await monitor.start_monitoring()
        
        # Let it run for a bit
        try:
            await asyncio.sleep(300)  # Monitor for 5 minutes
            
            # Print summary
            summary = monitor.get_current_spread_summary()
            print("\n📊 SPREAD SUMMARY:")
            for market_id, data in summary.items():
                print(f"Market {market_id}: {data['current_spread_pct']:.2%} spread, "
                      f"${data['current_liquidity']:.2f} liquidity")
        
        finally:
            await monitor.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(example_spread_monitoring())