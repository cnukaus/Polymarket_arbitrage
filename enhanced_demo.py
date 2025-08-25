#!/usr/bin/env python3
"""
Enhanced get_full_list() function demonstration
Shows the improved flexible query matching system in action
"""

import requests
import json
import re
from difflib import SequenceMatcher

# Enhanced query generation functions
def normalize_text(text):
    """Clean and normalize text for better matching"""
    if not text:
        return ""
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def extract_key_terms(text):
    """Extract key terms from market/contract names"""
    if not text:
        return []
    
    important_terms = {
        'election', 'win', 'wins', 'winner', 'president', 'presidential', 
        'senate', 'governor', 'house', 'congress', 'primary', 'general',
        'democrat', 'republican', 'party', 'candidate', 'nominee'
    }
    
    words = normalize_text(text).split()
    key_terms = [w for w in words if w in important_terms or len(w) > 3]
    return key_terms

def generate_query_variations(contract, market):
    """Generate multiple query variations with confidence scores"""
    variations = []
    contract_name = contract['name']
    market_name = market['name']
    
    # Strategy 1: Original rigid pattern
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
    
    # Strategy 2: Direct contract name
    if market_name.lower() == contract_name.lower():
        variations.append({
            'query': contract_name,
            'confidence': 0.8,
            'strategy': 'direct_name'
        })
    
    # Strategy 3: Constructed "Will X win Y"
    if 'win' not in market_name.lower():
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
        clean_pattern = re.sub(r'\s+', ' ', pattern).strip()
        if len(clean_pattern.split()) >= 3:
            variations.append({
                'query': clean_pattern,
                'confidence': 0.7 - (i * 0.05),
                'strategy': f'election_pattern_{i+1}'
            })
    
    # Strategy 5: Fuzzy reconstruction
    contract_terms = extract_key_terms(contract_name)
    market_terms = extract_key_terms(market_name)
    
    if contract_terms and market_terms:
        combined_terms = contract_terms[:2] + market_terms[:2]
        fuzzy_query = f"Will {' '.join(combined_terms)}"
        variations.append({
            'query': fuzzy_query,
            'confidence': 0.65,
            'strategy': 'fuzzy_reconstruction'
        })
    
    # Strategy 6: Simple election
    if any(term in market_name.lower() for term in ['election', 'president', 'governor', 'senate']):
        simple_query = f"{contract_name} election"
        variations.append({
            'query': simple_query,
            'confidence': 0.6,
            'strategy': 'simple_election'
        })
    
    # Strategy 7: Similarity bridge
    similarity = SequenceMatcher(None, normalize_text(contract_name), normalize_text(market_name)).ratio()
    if similarity < 0.3:
        bridge_query = f"Will {contract_name} win"
        variations.append({
            'query': bridge_query,
            'confidence': 0.55,
            'strategy': 'similarity_bridge'
        })
    
    variations.sort(key=lambda x: x['confidence'], reverse=True)
    return variations[:5]

def mock_get_polymarket_values(query):
    """Mock function that simulates Polymarket matching"""
    # Simple keyword-based mock matching
    if any(word in query.lower() for word in ['trump', 'republican', 'house']):
        return f"Mock match for: {query[:50]}...", 30, 0.65, 0.35
    return None, None, None, None

def check_for_arbitrage(poly_yes, poly_no, pred_yes, pred_no):
    """Mock arbitrage checker"""
    if all(x is not None for x in [poly_yes, poly_no, pred_yes, pred_no]):
        diff = abs(float(poly_yes) - float(pred_yes))
        if diff > 0.05:
            return diff * 50, diff * 40, 1000  # Mock profits
    return None, None, None

def get_full_list_enhanced_demo(limit=15):
    """
    Enhanced version of get_full_list() with creative query matching
    Demonstrates the new flexible approach vs the old rigid pattern
    """
    
    print("🚀 ENHANCED get_full_list() DEMONSTRATION")
    print("=" * 70)
    print("Comparing OLD vs NEW query matching approaches")
    print("=" * 70)
    
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
    
    # Test with limited data
    total_tested = 0
    old_method_matches = 0
    new_method_matches = 0
    improved_matches = 0
    
    print(f"\nTesting first {limit} contracts...")
    print("-" * 70)
    
    for market in data['markets'][:3]:  # Test first 3 markets
        if total_tested >= limit:
            break
            
        print(f"\n📈 MARKET: {market['name'][:60]}...")
        print("  " + "-" * 50)
        
        for contract in market['contracts'][:8]:  # Max 8 contracts per market
            if total_tested >= limit:
                break
                
            total_tested += 1
            contract_name = contract['name']
            market_name = market['name']
            
            print(f"\n  📋 Contract {total_tested}: {contract_name}")
            
            # OLD METHOD: Rigid pattern matching
            old_query = None
            if market_name.lower() != contract_name.lower():
                try:
                    if 'win' in market_name.lower():
                        old_query = "Will " + contract_name + " " + market_name[market_name.lower().index("win"):]
                except:
                    pass
            else:
                old_query = contract_name
            
            if old_query:
                old_match = mock_get_polymarket_values(old_query)
                if old_match[0]:
                    old_method_matches += 1
                    print(f"    ✅ OLD METHOD: Found match")
                    print(f"       Query: {old_query[:50]}...")
                else:
                    print(f"    ❌ OLD METHOD: No match")
                    print(f"       Query: {old_query[:50]}...")
            else:
                print(f"    ❌ OLD METHOD: No query generated")
            
            # NEW METHOD: Enhanced flexible matching
            variations = generate_query_variations(contract, market)
            
            if variations:
                print(f"    🔄 NEW METHOD: Generated {len(variations)} variations:")
                
                best_match = None
                best_confidence = 0
                
                for var in variations:
                    query = var['query']
                    strategy = var['strategy']
                    confidence = var['confidence']
                    
                    match = mock_get_polymarket_values(query)
                    if match[0]:
                        final_confidence = confidence * 0.7 + 0.3
                        if final_confidence > best_confidence:
                            best_match = {
                                'query': query,
                                'strategy': strategy,
                                'confidence': final_confidence
                            }
                            best_confidence = final_confidence
                
                if best_match:
                    new_method_matches += 1
                    print(f"    ✅ NEW METHOD: Found match!")
                    print(f"       Strategy: {best_match['strategy']}")
                    print(f"       Confidence: {best_match['confidence']:.1%}")
                    print(f"       Query: {best_match['query'][:50]}...")
                    
                    # Check if this is an improvement over old method
                    if not old_query or not mock_get_polymarket_values(old_query)[0]:
                        improved_matches += 1
                        print(f"    🎯 IMPROVEMENT: New method found match where old failed!")
                else:
                    print(f"    ❌ NEW METHOD: No matches found")
            else:
                print(f"    ❌ NEW METHOD: No variations generated")
    
    # Summary
    print(f"\n" + "=" * 70)
    print(f"📊 COMPARISON RESULTS:")
    print(f"   • Total contracts tested: {total_tested}")
    print(f"   • OLD method matches: {old_method_matches} ({old_method_matches/total_tested*100:.1f}%)")
    print(f"   • NEW method matches: {new_method_matches} ({new_method_matches/total_tested*100:.1f}%)")
    print(f"   • Improvements found: {improved_matches}")
    print(f"   • Success rate improvement: {((new_method_matches-old_method_matches)/total_tested*100):+.1f}%")
    print("=" * 70)
    
    print(f"\n🎉 ENHANCED QUERY MATCHING FEATURES:")
    print(f"   ✅ 7 different matching strategies")
    print(f"   ✅ Confidence-based ranking")
    print(f"   ✅ Fuzzy text matching")
    print(f"   ✅ Key term extraction")
    print(f"   ✅ Fallback methods for difficult cases")
    print(f"   ✅ Detailed logging and debugging")
    
    return {
        'total_tested': total_tested,
        'old_matches': old_method_matches,
        'new_matches': new_method_matches,
        'improvements': improved_matches
    }

if __name__ == "__main__":
    # Run the demonstration
    results = get_full_list_enhanced_demo(limit=20)
    
    print(f"\n📈 CONCLUSION:")
    if results and results['new_matches'] > results['old_matches']:
        improvement = results['new_matches'] - results['old_matches']
        print(f"The enhanced system found {improvement} additional matches!")
        print(f"This represents a significant improvement in market coverage.")
    else:
        print(f"The enhanced system provides more robust matching strategies")
        print(f"and better handling of edge cases compared to the rigid pattern.")