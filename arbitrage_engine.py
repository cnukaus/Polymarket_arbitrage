#!/usr/bin/env python3
"""
Arbitrage Detection Engine - Cross-venue price analysis and opportunity detection
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from enum import Enum

from event_model import Event, ContractSide
from event_matcher import MatchResult

class ArbitrageType(Enum):
    PURE_ARBITRAGE = "pure"  # Risk-free guaranteed profit
    STATISTICAL_ARBITRAGE = "statistical"  # Edge but not risk-free

@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity"""
    
    # Match information
    match_result: MatchResult
    arbitrage_type: ArbitrageType
    
    # Trade legs
    buy_venue: str
    buy_side: str  # "YES" or "NO" 
    buy_price: Decimal
    
    sell_venue: str
    sell_side: str
    sell_price: Decimal
    
    # Economics
    gross_edge: Decimal  # Before fees/costs
    net_edge: Decimal    # After all costs
    max_position_size: Decimal  # Based on liquidity constraints
    expected_profit: Decimal
    
    # Risk factors
    slippage_estimate: Decimal
    timing_risk_score: float  # 0-1, higher = more timing risk
    resolution_risk_score: float  # 0-1, higher = resolution uncertainty
    
    # Metadata
    confidence_score: float
    detected_at: datetime
    expires_at: Optional[datetime] = None

class ArbitrageDetector:
    """Detects and analyzes arbitrage opportunities from matched events"""
    
    def __init__(self, 
                 min_edge_threshold: Decimal = Decimal("0.02"),  # 2% minimum edge
                 max_slippage_tolerance: Decimal = Decimal("0.01")):  # 1% max slippage
        self.min_edge_threshold = min_edge_threshold
        self.max_slippage_tolerance = max_slippage_tolerance
        
        # Venue-specific fee structures
        self.venue_fees = {
            "polymarket": {
                "trading_fee": Decimal("0.02"),  # 2% on winnings
                "withdrawal_fee": Decimal("0.0"),
                "gas_estimate": Decimal("0.005"),  # ~$5 in gas
            },
            "predyx": {
                "trading_fee": Decimal("0.01"),  # 1% estimated
                "withdrawal_fee": Decimal("0.0"),  # Lightning withdrawal
                "network_fee": Decimal("0.0001"),  # Lightning routing
            }
        }
    
    def scan_for_arbitrage(self, matches: List[MatchResult]) -> List[ArbitrageOpportunity]:
        """Scan matched events for arbitrage opportunities"""
        opportunities = []
        
        for match in matches:
            if match.confidence_score < 0.7:  # Skip low-confidence matches
                continue
                
            # For binary markets, check both directions
            if (match.event_a.market_type.value == "binary" and 
                match.event_b.market_type.value == "binary"):
                
                # Check YES_A + NO_B arbitrage
                opp_1 = self._check_binary_arbitrage(
                    match, "YES", "NO"
                )
                if opp_1:
                    opportunities.append(opp_1)
                
                # Check NO_A + YES_B arbitrage  
                opp_2 = self._check_binary_arbitrage(
                    match, "NO", "YES"
                )
                if opp_2:
                    opportunities.append(opp_2)
        
        # Sort by net edge descending
        opportunities.sort(key=lambda x: x.net_edge, reverse=True)
        return opportunities
    
    def _check_binary_arbitrage(self, 
                               match: MatchResult, 
                               side_a: str, 
                               side_b: str) -> Optional[ArbitrageOpportunity]:
        """Check for arbitrage between two binary market sides"""
        
        event_a, event_b = match.event_a, match.event_b
        
        # Find the relevant contract sides
        side_a_contract = self._find_contract_side(event_a, side_a)
        side_b_contract = self._find_contract_side(event_b, side_b)
        
        if not side_a_contract or not side_b_contract:
            return None
        
        # Calculate costs including fees
        cost_a = self._calculate_total_cost(
            side_a_contract.price, event_a.venue.value, "buy"
        )
        cost_b = self._calculate_total_cost(
            side_b_contract.price, event_b.venue.value, "buy"
        )
        
        total_cost = cost_a + cost_b
        
        # For binary arbitrage: if total cost < 1, we have guaranteed profit
        if total_cost >= Decimal("1.0"):
            return None  # No arbitrage
        
        gross_edge = Decimal("1.0") - total_cost
        
        if gross_edge < self.min_edge_threshold:
            return None  # Edge too small
        
        # Estimate slippage based on liquidity
        slippage_a = self._estimate_slippage(side_a_contract)
        slippage_b = self._estimate_slippage(side_b_contract)
        total_slippage = slippage_a + slippage_b
        
        if total_slippage > self.max_slippage_tolerance:
            return None  # Too much slippage
        
        net_edge = gross_edge - total_slippage
        
        # Calculate position sizing
        max_size_a = self._calculate_max_position(side_a_contract)
        max_size_b = self._calculate_max_position(side_b_contract)
        max_position_size = min(max_size_a, max_size_b)
        
        expected_profit = net_edge * max_position_size
        
        # Risk scoring
        timing_risk = self._calculate_timing_risk(event_a, event_b)
        resolution_risk = self._calculate_resolution_risk(match)
        
        return ArbitrageOpportunity(
            match_result=match,
            arbitrage_type=ArbitrageType.PURE_ARBITRAGE,
            
            buy_venue=event_a.venue.value,
            buy_side=side_a,
            buy_price=Decimal(str(side_a_contract.price)),
            
            sell_venue=event_b.venue.value,
            sell_side=side_b,
            sell_price=Decimal(str(side_b_contract.price)),
            
            gross_edge=gross_edge,
            net_edge=net_edge,
            max_position_size=max_position_size,
            expected_profit=expected_profit,
            
            slippage_estimate=total_slippage,
            timing_risk_score=timing_risk,
            resolution_risk_score=resolution_risk,
            
            confidence_score=match.confidence_score,
            detected_at=datetime.utcnow()
        )
    
    def _find_contract_side(self, event: Event, side: str) -> Optional[ContractSide]:
        """Find the contract side matching the given side name"""
        for contract_side in event.contract_sides:
            if contract_side.name.upper() == side.upper():
                return contract_side
        return None
    
    def _calculate_total_cost(self, base_price: float, venue: str, action: str) -> Decimal:
        """Calculate total cost including fees for a trade"""
        price = Decimal(str(base_price))
        fees = self.venue_fees.get(venue, {})
        
        # Add trading fees (typically on winnings, but approximate as % of trade)
        trading_fee = fees.get("trading_fee", Decimal("0"))
        total_cost = price * (Decimal("1") + trading_fee)
        
        # Add fixed costs (gas, network fees)
        gas_cost = fees.get("gas_estimate", Decimal("0"))
        network_fee = fees.get("network_fee", Decimal("0"))
        total_cost += gas_cost + network_fee
        
        return total_cost
    
    def _estimate_slippage(self, contract_side: ContractSide) -> Decimal:
        """Estimate slippage based on liquidity"""
        # TODO: Implement sophisticated slippage estimation
        # For now, use simple heuristic based on liquidity
        if not contract_side.liquidity:
            return Decimal("0.005")  # 0.5% default slippage
        
        # Lower slippage for higher liquidity
        liquidity = Decimal(str(contract_side.liquidity))
        if liquidity > 10000:
            return Decimal("0.001")  # 0.1%
        elif liquidity > 1000:
            return Decimal("0.003")  # 0.3%
        else:
            return Decimal("0.01")   # 1.0%
    
    def _calculate_max_position(self, contract_side: ContractSide) -> Decimal:
        """Calculate maximum position size based on liquidity"""
        # TODO: Implement based on order book depth
        if not contract_side.liquidity:
            return Decimal("100")  # Conservative default
        
        # Use fraction of available liquidity
        liquidity = Decimal(str(contract_side.liquidity))
        return min(liquidity * Decimal("0.1"), Decimal("10000"))  # Max 10% of liquidity, cap at $10k
    
    def _calculate_timing_risk(self, event_a: Event, event_b: Event) -> float:
        """Calculate timing risk based on deadline differences"""
        deadline_diff = abs((event_a.deadline - event_b.deadline).days)
        # Higher score = more risk
        return min(deadline_diff / 7.0, 1.0)  # Normalize to 0-1, week = 1.0 risk
    
    def _calculate_resolution_risk(self, match: MatchResult) -> float:
        """Calculate resolution risk based on match quality"""
        # Higher risk for lower confidence matches
        base_risk = 1.0 - match.confidence_score
        
        # Add risk for each risk factor
        risk_penalty = len(match.risk_factors) * 0.1
        
        return min(base_risk + risk_penalty, 1.0)