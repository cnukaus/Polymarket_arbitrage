#!/usr/bin/env python3
"""
Event Matching Engine - Cross-venue event linking and similarity detection
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib

from event_model import Event

@dataclass
class MatchResult:
    """Result of cross-venue event matching"""
    event_a: Event
    event_b: Event
    confidence_score: float
    match_strategies: List[str]  # Which strategies contributed to the match
    risk_factors: List[str]  # Potential issues with this match
    human_review_required: bool

class EventMatcher:
    """Matches events across venues using multiple strategies"""
    
    def __init__(self, confidence_threshold: float = 0.75):
        self.confidence_threshold = confidence_threshold
        self.match_strategies = {
            "exact_title": self._exact_title_match,
            "fuzzy_title": self._fuzzy_title_match,
            "entity_overlap": self._entity_overlap_match,
            "semantic_embedding": self._semantic_embedding_match,
            "resolution_criteria": self._resolution_criteria_match,
            "temporal_alignment": self._temporal_alignment_check,
        }
    
    def find_matches(self, events_a: List[Event], events_b: List[Event]) -> List[MatchResult]:
        """Find all potential matches between two event lists"""
        matches = []
        
        for event_a in events_a:
            for event_b in events_b:
                if event_a.venue == event_b.venue:
                    continue  # Skip same-venue comparisons
                
                match_result = self._evaluate_match(event_a, event_b)
                if match_result and match_result.confidence_score >= self.confidence_threshold:
                    matches.append(match_result)
        
        return matches
    
    def _evaluate_match(self, event_a: Event, event_b: Event) -> Optional[MatchResult]:
        """Evaluate if two events represent the same underlying prediction"""
        
        scores = {}
        strategies_used = []
        risk_factors = []
        
        # Run all matching strategies
        for strategy_name, strategy_func in self.match_strategies.items():
            try:
                score = strategy_func(event_a, event_b)
                if score > 0:
                    scores[strategy_name] = score
                    strategies_used.append(strategy_name)
            except Exception as e:
                # Log strategy failure but continue
                pass
        
        if not scores:
            return None
        
        # Weighted combination of scores
        weights = {
            "exact_title": 0.3,
            "fuzzy_title": 0.2,
            "entity_overlap": 0.2,
            "semantic_embedding": 0.15,
            "resolution_criteria": 0.1,
            "temporal_alignment": 0.05,
        }
        
        final_score = sum(scores.get(strategy, 0) * weight 
                         for strategy, weight in weights.items())
        
        # Risk factor detection
        risk_factors.extend(self._detect_risk_factors(event_a, event_b))
        
        # Determine if human review needed
        human_review_required = (
            final_score < 0.9 or  # Lower confidence matches
            len(risk_factors) > 0 or  # Any risk factors
            abs((event_a.deadline - event_b.deadline).days) > 1  # Different deadlines
        )
        
        return MatchResult(
            event_a=event_a,
            event_b=event_b,
            confidence_score=final_score,
            match_strategies=strategies_used,
            risk_factors=risk_factors,
            human_review_required=human_review_required
        )
    
    def _exact_title_match(self, event_a: Event, event_b: Event) -> float:
        """Check for exact title matches"""
        # TODO: Implement exact string matching with normalization
        pass
    
    def _fuzzy_title_match(self, event_a: Event, event_b: Event) -> float:
        """Fuzzy string matching on titles"""
        # TODO: Implement fuzzy matching (Levenshtein, etc.)
        pass
    
    def _entity_overlap_match(self, event_a: Event, event_b: Event) -> float:
        """Check overlap in named entities"""
        # TODO: Implement entity overlap scoring
        pass
    
    def _semantic_embedding_match(self, event_a: Event, event_b: Event) -> float:
        """Semantic similarity using embeddings"""
        # TODO: Implement embedding-based similarity
        pass
    
    def _resolution_criteria_match(self, event_a: Event, event_b: Event) -> float:
        """Compare resolution criteria text"""
        # TODO: Implement resolution criteria matching
        pass
    
    def _temporal_alignment_check(self, event_a: Event, event_b: Event) -> float:
        """Check if deadlines are aligned"""
        # TODO: Implement temporal alignment scoring
        pass
    
    def _detect_risk_factors(self, event_a: Event, event_b: Event) -> List[str]:
        """Detect potential risks in the match"""
        risks = []
        
        # Different resolution sources
        if (event_a.resolution_source_url and event_b.resolution_source_url and 
            event_a.resolution_source_url != event_b.resolution_source_url):
            risks.append("different_resolution_sources")
        
        # Significant deadline mismatch
        deadline_diff = abs((event_a.deadline - event_b.deadline).days)
        if deadline_diff > 7:
            risks.append("deadline_mismatch_gt_week")
        
        # Different market types
        if event_a.market_type != event_b.market_type:
            risks.append("different_market_types")
        
        # TODO: Add more risk detection logic
        
        return risks

class HumanReviewQueue:
    """Manages human review queue for low-confidence matches"""
    
    def __init__(self):
        self.pending_reviews: List[MatchResult] = []
    
    def add_for_review(self, match_result: MatchResult):
        """Add a match result to human review queue"""
        self.pending_reviews.append(match_result)
    
    def get_next_review(self) -> Optional[MatchResult]:
        """Get next item requiring human review"""
        if self.pending_reviews:
            return self.pending_reviews.pop(0)
        return None
    
    def approve_match(self, match_result: MatchResult):
        """Human approves the match"""
        # TODO: Store approved match and update confidence models
        pass
    
    def reject_match(self, match_result: MatchResult, reason: str):
        """Human rejects the match"""
        # TODO: Store rejection and update confidence models
        pass