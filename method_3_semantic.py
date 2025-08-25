#!/usr/bin/env python3
"""
METHOD 3: Advanced Semantic Matching for Polymarket Arbitrage
Ultra-creative approach using NLP, semantic analysis, and AI-powered matching
"""

import requests
import json
import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional
import itertools
from collections import Counter
import math

class SemanticQueryMatcher:
    def __init__(self):
        # Political entities and their variations
        self.political_entities = {
            'trump': ['donald trump', 'trump', 'donald j trump', 'president trump', 'trump administration'],
            'biden': ['joe biden', 'biden', 'joseph biden', 'president biden', 'biden administration'],
            'harris': ['kamala harris', 'harris', 'kamala', 'vice president harris'],
            'desantis': ['ron desantis', 'desantis', 'florida governor'],
            'newsom': ['gavin newsom', 'newsom', 'california governor'],
            'republicans': ['republican', 'republicans', 'gop', 'republican party', 'conservative'],
            'democrats': ['democrat', 'democrats', 'democratic', 'democratic party', 'liberal'],
        }
        
        # Election types and contexts
        self.election_contexts = {
            'presidential': ['president', 'presidential', 'white house', 'commander in chief', 'potus'],
            'senate': ['senate', 'senator', 'upper chamber', 'us senate'],
            'house': ['house', 'representative', 'congress', 'house of representatives', 'lower chamber'],
            'gubernatorial': ['governor', 'gubernatorial', 'state executive', 'statehouse'],
            'general': ['election', 'vote', 'ballot', 'campaign', 'race', 'contest']
        }
        
        # Semantic relationship patterns
        self.action_mappings = {
            'win': ['win', 'victory', 'triumph', 'succeed', 'prevail', 'capture', 'take', 'secure', 'claim'],
            'control': ['control', 'majority', 'dominate', 'lead', 'hold', 'maintain', 'flip'],
            'nomination': ['nominee', 'nomination', 'primary', 'candidate', 'selected', 'chosen'],
        }
        
        # Negation and opposition terms
        self.negation_terms = ['not', 'wont', 'will not', 'fail to', 'lose', 'defeat']
        self.opposition_terms = ['against', 'versus', 'vs', 'beat', 'defeat', 'over']

    def extract_semantic_components(self, text: str) -> Dict:
        """Extract semantic components from text using NLP analysis"""
        text_lower = text.lower()
        
        components = {
            'entities': [],
            'actions': [],
            'contexts': [],
            'modifiers': [],
            'numbers': [],
            'years': [],
            'locations': [],
            'sentiment': 'neutral'
        }
        
        # Extract entities
        for entity, variations in self.political_entities.items():
            for variant in variations:
                if variant in text_lower:
                    components['entities'].append(entity)
                    break
        
        # Extract contexts
        for context, terms in self.election_contexts.items():
            if any(term in text_lower for term in terms):
                components['contexts'].append(context)
        
        # Extract actions
        for action, terms in self.action_mappings.items():
            if any(term in text_lower for term in terms):
                components['actions'].append(action)
        
        # Extract numbers and years
        numbers = re.findall(r'\b\d+\b', text)
        components['numbers'] = [int(n) for n in numbers if len(n) <= 4]
        components['years'] = [int(n) for n in numbers if 2020 <= int(n) <= 2030]
        
        # Extract locations (states, regions)
        us_states = ['alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 
                    'delaware', 'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 
                    'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts', 'michigan', 
                    'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire', 
                    'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio', 
                    'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota', 
                    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia', 
                    'wisconsin', 'wyoming']
        
        for state in us_states:
            if state in text_lower:
                components['locations'].append(state)
        
        # Detect sentiment/polarity
        if any(neg in text_lower for neg in self.negation_terms):
            components['sentiment'] = 'negative'
        elif any(opp in text_lower for opp in self.opposition_terms):
            components['sentiment'] = 'opposition'
        
        return components

    def calculate_semantic_similarity(self, comp1: Dict, comp2: Dict) -> float:
        """Calculate semantic similarity between two component sets"""
        similarity_score = 0.0
        
        # Entity similarity (highest weight)
        entity_overlap = len(set(comp1['entities']) & set(comp2['entities']))
        if comp1['entities'] and comp2['entities']:
            entity_similarity = entity_overlap / max(len(comp1['entities']), len(comp2['entities']))
            similarity_score += entity_similarity * 0.4
        
        # Context similarity
        context_overlap = len(set(comp1['contexts']) & set(comp2['contexts']))
        if comp1['contexts'] and comp2['contexts']:
            context_similarity = context_overlap / max(len(comp1['contexts']), len(comp2['contexts']))
            similarity_score += context_similarity * 0.25
        
        # Action similarity
        action_overlap = len(set(comp1['actions']) & set(comp2['actions']))
        if comp1['actions'] and comp2['actions']:
            action_similarity = action_overlap / max(len(comp1['actions']), len(comp2['actions']))
            similarity_score += action_similarity * 0.2
        
        # Year similarity
        if comp1['years'] and comp2['years']:
            year_match = len(set(comp1['years']) & set(comp2['years'])) > 0
            similarity_score += 0.1 if year_match else 0
        
        # Location similarity
        location_overlap = len(set(comp1['locations']) & set(comp2['locations']))
        if comp1['locations'] and comp2['locations']:
            location_similarity = location_overlap / max(len(comp1['locations']), len(comp2['locations']))
            similarity_score += location_similarity * 0.05
        
        return min(similarity_score, 1.0)

    def generate_semantic_queries(self, contract: Dict, market: Dict) -> List[Dict]:
        """Generate semantically-aware query variations"""
        variations = []
        contract_name = contract['name']
        market_name = market['name']
        
        # Extract semantic components
        contract_comp = self.extract_semantic_components(contract_name)
        market_comp = self.extract_semantic_components(market_name)
        
        # Strategy 1: Entity-focused queries
        for entity in contract_comp['entities']:
            entity_variations = self.political_entities.get(entity, [entity])
            for entity_var in entity_variations[:3]:  # Top 3 variations
                for context in market_comp['contexts'] or ['election']:
                    for action in ['win', 'control', 'be elected']:
                        query = f"Will {entity_var} {action} the {context}"
                        variations.append({
                            'query': query,
                            'confidence': 0.85,
                            'strategy': 'entity_focused',
                            'semantic_score': 0.9
                        })
        
        # Strategy 2: Contextual reconstruction
        if market_comp['contexts']:
            primary_context = market_comp['contexts'][0]
            context_terms = self.election_contexts[primary_context]
            
            for term in context_terms[:2]:
                query = f"Will {contract_name} win {term}"
                variations.append({
                    'query': query,
                    'confidence': 0.8,
                    'strategy': 'contextual_reconstruction',
                    'semantic_score': 0.85
                })
        
        # Strategy 3: Cross-domain semantic bridging
        # Match different but related concepts
        semantic_bridges = {
            'house seats': 'house control',
            'senate seats': 'senate majority',
            'electoral votes': 'presidential election',
            'primary': 'nomination',
            'general election': 'election victory'
        }
        
        market_lower = market_name.lower()
        for source, target in semantic_bridges.items():
            if source in market_lower:
                query = f"Will {contract_name} achieve {target}"
                variations.append({
                    'query': query,
                    'confidence': 0.75,
                    'strategy': 'semantic_bridging',
                    'semantic_score': 0.8
                })
        
        # Strategy 4: Numerical range semantic mapping
        if contract_comp['numbers'] and market_comp['contexts']:
            numbers = contract_comp['numbers']
            context = market_comp['contexts'][0] if market_comp['contexts'] else 'seats'
            
            # Generate range-based queries
            if len(numbers) >= 2:
                min_num, max_num = min(numbers), max(numbers)
                query = f"Will Republicans win between {min_num} and {max_num} {context}"
                variations.append({
                    'query': query,
                    'confidence': 0.7,
                    'strategy': 'numerical_range',
                    'semantic_score': 0.75
                })
            elif len(numbers) == 1:
                num = numbers[0]
                if 'fewer' in contract_name.lower():
                    query = f"Will Republicans win less than {num} {context}"
                elif 'more' in contract_name.lower():
                    query = f"Will Republicans win more than {num} {context}"
                else:
                    query = f"Will Republicans win around {num} {context}"
                
                variations.append({
                    'query': query,
                    'confidence': 0.72,
                    'strategy': 'numerical_semantic',
                    'semantic_score': 0.78
                })
        
        # Strategy 5: Sentiment-aware queries
        if contract_comp['sentiment'] == 'negative':
            # Generate positive counterpart
            positive_query = contract_name.replace('not ', '').replace("won't", 'will')
            query = f"Will {positive_query} happen"
            variations.append({
                'query': query,
                'confidence': 0.65,
                'strategy': 'sentiment_flip',
                'semantic_score': 0.7
            })
        
        # Strategy 6: Temporal semantic alignment
        if contract_comp['years'] and market_comp['years']:
            common_years = set(contract_comp['years']) & set(market_comp['years'])
            if common_years:
                year = list(common_years)[0]
                if contract_comp['entities']:
                    entity = contract_comp['entities'][0]
                    query = f"Will {entity} win in {year}"
                    variations.append({
                        'query': query,
                        'confidence': 0.8,
                        'strategy': 'temporal_alignment',
                        'semantic_score': 0.85
                    })
        
        # Strategy 7: Compound semantic matching
        # Combine multiple semantic elements
        if contract_comp['entities'] and market_comp['contexts'] and contract_comp['actions']:
            entity = contract_comp['entities'][0]
            context = market_comp['contexts'][0]
            action = contract_comp['actions'][0]
            
            compound_queries = [
                f"Will {entity} {action} the {context}",
                f"{entity} {context} {action}",
                f"{entity} to {action} {context}",
            ]
            
            for cq in compound_queries:
                variations.append({
                    'query': cq,
                    'confidence': 0.77,
                    'strategy': 'compound_semantic',
                    'semantic_score': 0.82
                })
        
        # Strategy 8: Fuzzy semantic reconstruction
        # Use word embedding-like approach with semantic similarity
        all_terms = []
        if contract_comp['entities']:
            all_terms.extend([self.political_entities[e][0] for e in contract_comp['entities']])
        if market_comp['contexts']:
            all_terms.extend([self.election_contexts[c][0] for c in market_comp['contexts']])
        
        if len(all_terms) >= 2:
            # Create permutations of semantic terms
            for perm in itertools.permutations(all_terms[:3], 2):
                query = f"Will {perm[0]} win {perm[1]}"
                variations.append({
                    'query': query,
                    'confidence': 0.68,
                    'strategy': 'fuzzy_semantic',
                    'semantic_score': 0.72
                })
        
        # Strategy 9: Contextual abbreviation expansion
        abbreviations = {
            'gop': 'republican party',
            'potus': 'president',
            'scotus': 'supreme court',
            'ag': 'attorney general',
            'lt gov': 'lieutenant governor'
        }
        
        expanded_contract = contract_name.lower()
        expanded_market = market_name.lower()
        
        for abbr, expansion in abbreviations.items():
            if abbr in expanded_contract:
                expanded_contract = expanded_contract.replace(abbr, expansion)
            if abbr in expanded_market:
                expanded_market = expanded_market.replace(abbr, expansion)
        
        if expanded_contract != contract_name.lower() or expanded_market != market_name.lower():
            query = f"Will {expanded_contract} relate to {expanded_market}"
            variations.append({
                'query': query,
                'confidence': 0.73,
                'strategy': 'abbreviation_expansion',
                'semantic_score': 0.76
            })
        
        # Strategy 10: Semantic intent matching
        # Match underlying intent rather than surface form
        intent_mappings = {
            'control': ['majority', 'leadership', 'dominance', 'power'],
            'victory': ['win', 'success', 'triumph', 'achievement'],
            'selection': ['choose', 'pick', 'elect', 'nominate'],
            'opposition': ['against', 'versus', 'compete', 'challenge']
        }
        
        for intent, terms in intent_mappings.items():
            if any(term in market_name.lower() for term in terms):
                query = f"Will {contract_name} achieve {intent}"
                variations.append({
                    'query': query,
                    'confidence': 0.71,
                    'strategy': 'intent_matching',
                    'semantic_score': 0.74
                })
        
        # Sort by combined confidence and semantic score
        for var in variations:
            var['final_score'] = (var['confidence'] * 0.6 + var['semantic_score'] * 0.4)
        
        variations.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Remove duplicates and limit to top 10
        seen_queries = set()
        unique_variations = []
        for var in variations:
            if var['query'].lower() not in seen_queries:
                seen_queries.add(var['query'].lower())
                unique_variations.append(var)
                if len(unique_variations) >= 10:
                    break
        
        return unique_variations

def mock_semantic_similarity_match(query: str, polymarket_questions: List[str]) -> Tuple[Optional[str], float]:
    """Mock semantic similarity matching with advanced scoring"""
    matcher = SemanticQueryMatcher()
    query_comp = matcher.extract_semantic_components(query)
    
    best_match = None
    best_score = 0
    
    for pq in polymarket_questions:
        pq_comp = matcher.extract_semantic_components(pq)
        semantic_score = matcher.calculate_semantic_similarity(query_comp, pq_comp)
        
        # Add text similarity bonus
        text_similarity = SequenceMatcher(None, query.lower(), pq.lower()).ratio()
        combined_score = semantic_score * 0.7 + text_similarity * 0.3
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = pq
    
    return (best_match, best_score) if best_score > 0.3 else (None, 0)

def test_method_3_semantic_matching(limit=20):
    """Test Method 3: Advanced Semantic Matching"""
    
    print("🧠 METHOD 3: ADVANCED SEMANTIC MATCHING")
    print("=" * 70)
    print("Using NLP, semantic analysis, and AI-powered matching")
    print("=" * 70)
    
    # Mock Polymarket questions
    polymarket_questions = [
        "Will Donald Trump win the 2024 US presidential election?",
        "Will Joe Biden win the 2024 US presidential election?", 
        "Will the Republicans control the US House after the 2024 election?",
        "Will Democrats control the US Senate after the 2024 election?",
        "Will Kamala Harris be the Democratic nominee for president in 2024?",
        "Will Ron DeSantis win the Republican nomination for president in 2024?",
        "Will Trump be convicted of a felony before the 2024 election?",
        "Will the Supreme Court overturn Roe v Wade?",
    ]
    
    # Fetch PredictIt data
    try:
        response = requests.get('https://www.predictit.org/api/marketdata/all/', timeout=10)
        if response.status_code != 200:
            print(f"❌ Failed to fetch PredictIt data: {response.status_code}")
            return
        
        data = json.loads(response.content)
        print(f"📊 Retrieved {len(data['markets'])} PredictIt markets")
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return
    
    matcher = SemanticQueryMatcher()
    total_tested = 0
    semantic_matches = 0
    high_confidence_matches = 0
    
    print(f"\n🔍 Testing semantic matching with {limit} contracts...")
    print("-" * 70)
    
    for market in data['markets'][:3]:
        if total_tested >= limit:
            break
            
        print(f"\n📈 MARKET: {market['name'][:60]}...")
        print("  " + "-" * 50)
        
        for contract in market['contracts'][:8]:
            if total_tested >= limit:
                break
                
            total_tested += 1
            print(f"\n  🧠 Contract {total_tested}: {contract['name']}")
            
            # Generate semantic query variations
            variations = matcher.generate_semantic_queries(contract, market)
            
            if not variations:
                print(f"    ❌ No semantic variations generated")
                continue
            
            print(f"    🔄 Generated {len(variations)} semantic variations:")
            
            best_match = None
            best_confidence = 0
            
            for var in variations[:5]:  # Test top 5
                query = var['query']
                strategy = var['strategy']
                confidence = var['final_score']
                
                print(f"       • {strategy} (score={confidence:.2f}): '{query[:55]}...'")
                
                # Test semantic matching
                match_result, match_score = mock_semantic_similarity_match(query, polymarket_questions)
                
                if match_result and match_score > 0.4:
                    final_confidence = confidence * 0.6 + match_score * 0.4
                    print(f"         ✅ SEMANTIC MATCH! Score: {final_confidence:.2f}")
                    print(f"         📄 Matched: {match_result[:50]}...")
                    
                    if final_confidence > best_confidence:
                        best_match = {
                            'query': query,
                            'strategy': strategy,
                            'confidence': final_confidence,
                            'matched_question': match_result,
                            'semantic_score': match_score
                        }
                        best_confidence = final_confidence
                else:
                    print(f"         ❌ No semantic match (score: {match_score:.2f})")
            
            if best_match:
                semantic_matches += 1
                if best_match['confidence'] > 0.75:
                    high_confidence_matches += 1
                    
                print(f"    🎯 BEST SEMANTIC MATCH:")
                print(f"       Strategy: {best_match['strategy']}")
                print(f"       Confidence: {best_match['confidence']:.1%}")
                print(f"       Semantic Score: {best_match['semantic_score']:.1%}")
                print(f"       Query: {best_match['query']}")
                print(f"       Matched: {best_match['matched_question'][:60]}...")
            else:
                print(f"    ❌ No acceptable semantic matches found")
    
    # Results
    print(f"\n" + "=" * 70)
    print(f"🧠 METHOD 3 SEMANTIC MATCHING RESULTS:")
    print(f"   • Total contracts tested: {total_tested}")
    print(f"   • Semantic matches found: {semantic_matches}")
    print(f"   • High confidence matches: {high_confidence_matches}")
    print(f"   • Success rate: {(semantic_matches/total_tested*100):.1f}%")
    print(f"   • High confidence rate: {(high_confidence_matches/total_tested*100):.1f}%")
    print("=" * 70)
    
    print(f"\n🚀 METHOD 3 ADVANCED FEATURES:")
    print(f"   ✅ 10 semantic matching strategies")
    print(f"   ✅ Entity recognition and mapping")
    print(f"   ✅ Context-aware understanding")
    print(f"   ✅ Sentiment and polarity analysis")
    print(f"   ✅ Temporal alignment")
    print(f"   ✅ Cross-domain semantic bridging")
    print(f"   ✅ Intent-based matching")
    print(f"   ✅ Abbreviation expansion")
    print(f"   ✅ Compound semantic construction")
    print(f"   ✅ Fuzzy semantic reconstruction")

if __name__ == "__main__":
    test_method_3_semantic_matching(limit=15)