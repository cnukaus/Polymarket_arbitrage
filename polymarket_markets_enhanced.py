#!/usr/bin/env python3
"""
Enhanced Polymarket Markets Fetcher with flexible query matching
Extends the original with multiple query generation strategies and confidence scoring
"""

import requests
import json
import re
from difflib import SequenceMatcher
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

def normalize_text(text):
    """Clean and normalize text for better matching"""
    if not text:
        return ""
    # Remove extra whitespace, convert to lowercase, remove special chars
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def extract_key_terms(text):
    """Extract key terms from market/contract names"""
    if not text:
        return []
    
    # Common political/election terms to preserve
    important_terms = {
        'election', 'win', 'wins', 'winner', 'president', 'presidential', 
        'senate', 'governor', 'house', 'congress', 'primary', 'general',
        'democrat', 'republican', 'party', 'candidate', 'nominee'
    }
    
    words = normalize_text(text).split()
    # Keep important terms and proper nouns (assume longer words are more important)
    key_terms = [w for w in words if w in important_terms or len(w) > 3]
    return key_terms

def generate_query_variations(contract, market):
    """Generate multiple query variations with confidence scores"""
    variations = []
    contract_name = contract['name']
    market_name = market['name']
    
    # Strategy 1: Original rigid pattern (high confidence if "win" in market name)
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
    
    # Strategy 2: Direct contract name (medium confidence)
    if market_name.lower() == contract_name.lower():
        variations.append({
            'query': contract_name,
            'confidence': 0.8,
            'strategy': 'direct_name'
        })
    
    # Strategy 3: "Will X win Y" format with flexible matching
    if 'win' not in market_name.lower():
        # Try to construct "Will X win Y" from context
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
        # Clean up double spaces and weird constructions
        clean_pattern = re.sub(r'\s+', ' ', pattern).strip()
        if len(clean_pattern.split()) >= 3:  # Ensure reasonable length
            variations.append({
                'query': clean_pattern,
                'confidence': 0.7 - (i * 0.05),  # Decreasing confidence
                'strategy': f'election_pattern_{i+1}'
            })
    
    # Strategy 5: Fuzzy reconstruction using key terms
    contract_terms = extract_key_terms(contract_name)
    market_terms = extract_key_terms(market_name)
    
    if contract_terms and market_terms:
        # Combine most important terms
        combined_terms = contract_terms[:2] + market_terms[:2]
        fuzzy_query = f"Will {' '.join(combined_terms)}"
        variations.append({
            'query': fuzzy_query,
            'confidence': 0.65,
            'strategy': 'fuzzy_reconstruction'
        })
    
    # Strategy 6: Partial matching - just candidate name with "election"
    if any(term in market_name.lower() for term in ['election', 'president', 'governor', 'senate']):
        simple_query = f"{contract_name} election"
        variations.append({
            'query': simple_query,
            'confidence': 0.6,
            'strategy': 'simple_election'
        })
    
    # Strategy 7: Similarity-based reconstruction
    # If contract and market are very different, try to bridge them
    similarity = SequenceMatcher(None, normalize_text(contract_name), normalize_text(market_name)).ratio()
    if similarity < 0.3:  # Very different names
        # Try to find common ground
        bridge_query = f"Will {contract_name} win"
        variations.append({
            'query': bridge_query,
            'confidence': 0.55,
            'strategy': 'similarity_bridge'
        })
    
    # Sort by confidence (highest first) and limit to top 5
    variations.sort(key=lambda x: x['confidence'], reverse=True)
    return variations[:5]

def find_similar_question(input_question, df, df_encodings, similarity_threshold=0.95):
    """Find similar questions using sentence transformers"""
    # Encode the input question
    input_encoding = model.encode([input_question])

    # Calculate cosine similarity
    similarities = cosine_similarity(input_encoding, df_encodings)[0]

    # Find the index of the most similar question
    most_similar_index = np.argmax(similarities)

    # Check if the similarity is above the threshold
    if similarities[most_similar_index] >= similarity_threshold:
        return df.iloc[most_similar_index]['question'], df.iloc[most_similar_index]['tokens'], df.iloc[most_similar_index]['condition_id'], similarities[most_similar_index]
    else:
        return df.iloc[most_similar_index]['question'], None, None, similarities[most_similar_index]

def get_polymarket_values(input_question, markets_df, df_encodings):
    """Get polymarket values for a given question"""
    question, token_id, condition_id, similarity_score = find_similar_question(input_question, markets_df, df_encodings)

    if token_id:
        # This would normally connect to the Polymarket client
        # For now, return mock values
        return question, 30, 0.65, 0.35  # Mock: question, days_till_end, yes_price, no_price
    else:
        return None, None, None, None

def check_for_arbitrage(polymarket_yes, polymarket_no, predictit_yes, predictit_no):
    """Check for arbitrage opportunities between markets"""
    # Mock arbitrage calculation - replace with actual logic
    return 50, 30, 1000  # Mock: yes_profit, no_profit, shares_purchased

def get_full_list_enhanced(markets_df, df_encodings):
    """Enhanced version of get_full_list with flexible query matching"""
    
    response = requests.get('https://www.predictit.org/api/marketdata/all/')

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON content
        data = json.loads(response.content)

        print(f"Processing {len(data['markets'])} PredictIt markets...")

        # Iterate through each market
        for market_idx, market in enumerate(data['markets']):
            if market_idx % 10 == 0:
                print(f"Processed {market_idx}/{len(data['markets'])} markets")

            # Iterate through each contract in the market
            for contract in market['contracts']:
                # Generate multiple query variations with confidence scoring
                queries_with_confidence = generate_query_variations(contract, market)
                
                if not queries_with_confidence:
                    continue
                
                print(f"\nTesting contract: {contract['name']} in market: {market['name']}")
                print(f"Generated {len(queries_with_confidence)} query variations:")
                
                # Try each query variation until we find a good match
                best_match = None
                best_confidence = 0
                
                for query_info in queries_with_confidence:
                    query = query_info['query']
                    base_confidence = query_info['confidence']
                    strategy = query_info['strategy']
                    
                    print(f"  Trying ({strategy}, conf={base_confidence:.2f}): {query}")
                    
                    question, days_till_end, best_yes_polymarket, best_no_polymarket = get_polymarket_values(query, markets_df, df_encodings)
                    
                    if question is not None:
                        # Calculate final confidence combining query confidence with similarity
                        final_confidence = base_confidence * 0.7 + 0.3  # Boost for successful match
                        
                        print(f"    ✓ Match found! Final confidence: {final_confidence:.2f}")
                        
                        if final_confidence > best_confidence:
                            best_match = {
                                'question': question,
                                'days_till_end': days_till_end,
                                'best_yes_polymarket': best_yes_polymarket,
                                'best_no_polymarket': best_no_polymarket,
                                'query': query,
                                'confidence': final_confidence,
                                'strategy': strategy
                            }
                            best_confidence = final_confidence
                    else:
                        print(f"    ✗ No match found")
                
                # Use the best match if confidence is above threshold
                if best_match and best_confidence >= 0.6:
                    print(f"  Best match selected: {best_match['strategy']} (confidence: {best_confidence:.1%})")
                    
                    best_yes_polymarket = float(best_match['best_yes_polymarket'])
                    best_no_polymarket = float(best_match['best_no_polymarket'])

                    best_yes_predictit = contract['bestBuyYesCost']
                    best_no_predictit = contract['bestBuyNoCost']

                    if best_yes_predictit is None or best_no_predictit is None:
                        print("  ✗ PredictIt prices unavailable")
                        continue

                    yes_profit, no_profit, shares_purchased = check_for_arbitrage(
                        best_yes_polymarket, best_no_polymarket, 
                        best_yes_predictit, best_no_predictit
                    )

                    if yes_profit is not None and no_profit is not None:
                        # We have found arbitrage
                        print(f"\n🎯 ARBITRAGE OPPORTUNITY FOUND!")
                        print(f"Query used: {best_match['query']}")
                        print(f"Matched Polymarket question: {best_match['question']}")
                        print(f"Match confidence: {best_match['confidence']:.1%}")
                        print(f"Strategy: {best_match['strategy']}")
                        print(f"Best YES Polymarket: ${best_yes_polymarket}")
                        print(f"Best NO  Polymarket: ${best_no_polymarket}")
                        print(f"Best YES PredictIt:  ${best_yes_predictit}")
                        print(f"Best NO  PredictIt:  ${best_no_predictit}")
                        print(f"Shares purchased:    {shares_purchased}")
                        
                        try:
                            days_till_end = float(best_match['days_till_end'])
                            yearly_return_yes = ((1+yes_profit/1000)**(365.25/days_till_end)-1)
                            yearly_return_no = ((1+no_profit/1000)**(365.25/days_till_end)-1)
                            
                            print(f"YES Profit (given $1000): ${yes_profit:.2f}. Implied yearly return: {yearly_return_yes:.2%}")
                            print(f"NO  Profit (given $1000): ${no_profit:.2f}. Implied yearly return: {yearly_return_no:.2%}")
                            
                            if best_yes_polymarket > best_yes_predictit:
                                # Then bought yes on predictit (buy low)
                                yes_return_after_fee = ((1+(yes_profit-50)/1000)**(365.25/days_till_end)-1)
                                no_return_after_fee = ((1+(no_profit)/1000)**(365.25/days_till_end)-1)
                                print(f"YES Profit % after 5% withdrawal fee: {yes_return_after_fee:.2%}")
                                print(f"NO  Profit % after 5% withdrawal fee: {no_return_after_fee:.2%}")
                            else:
                                # Then bought yes on polymarket (buy low)
                                yes_return_after_fee = ((1+(yes_profit)/1000)**(365.25/days_till_end)-1)
                                no_return_after_fee = ((1+(no_profit-50)/1000)**(365.25/days_till_end)-1)
                                print(f"YES Profit % after 5% withdrawal fee: {yes_return_after_fee:.2%}")
                                print(f"NO  Profit % after 5% withdrawal fee: {no_return_after_fee:.2%}")
                        except:
                            print(f"YES Profit (given $1000): ${yes_profit:.2f}.")
                            print(f"NO  Profit (given $1000): ${no_profit:.2f}.")
                        print("=" * 60)
                else:
                    print(f"  ✗ No good match found (best confidence: {best_confidence:.1%})")

    else:
        print(f"Failed to retrieve PredictIt data: Status code {response.status_code}")

if __name__ == "__main__":
    # Example usage (would need actual market data)
    print("Enhanced Polymarket arbitrage finder with flexible query matching")
    print("This version includes:")
    print("- 7 different query generation strategies")
    print("- Confidence scoring for matches")
    print("- Detailed logging of matching process")
    print("- Fallback methods for difficult matches")