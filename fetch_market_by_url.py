import os
import re
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

# Load environment variables
load_dotenv()
api_key = os.getenv('API_KEY')

# Initialize client
host = "https://clob.polymarket.com"
chain_id = 137
client = ClobClient(host, key=api_key, chain_id=chain_id)

def extract_market_info_from_url(url):
    """
    Extract market slug and TID from a Polymarket URL.
    
    Args:
        url (str): Polymarket URL like https://polymarket.com/event/will-trump-resign-today?tid=1756938040931
    
    Returns:
        dict: Contains 'slug', 'tid', and other extracted info
    """
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    
    result = {
        'full_url': url,
        'slug': None,
        'tid': None,
        'event_type': None,
        'path_parts': path_parts
    }
    
    # Extract slug from path
    if len(path_parts) >= 2 and path_parts[0] == 'event':
        result['slug'] = path_parts[1]
        result['event_type'] = 'event'
    elif len(path_parts) >= 2 and path_parts[0] == 'market':
        result['slug'] = path_parts[1] 
        result['event_type'] = 'market'
    
    # Extract TID from query parameters
    query_params = parse_qs(parsed.query)
    if 'tid' in query_params:
        result['tid'] = query_params['tid'][0]
    
    return result

def fetch_market_by_web_api(slug, tid=None, include_expired=True):
    """
    Fetch market data using Polymarket's web API endpoints.
    
    Args:
        slug (str): Market slug
        tid (str): Transaction ID (optional)
        include_expired (bool): Whether to search expired/archived markets
    
    Returns:
        dict: Market data if found, None otherwise
    """
    endpoints_to_try = [
        # Active markets
        f"https://gamma-api.polymarket.com/events?slug={slug}",
        f"https://gamma-api.polymarket.com/events/{slug}",
        f"https://clob.polymarket.com/events?slug={slug}",
        f"https://polymarket.com/api/events?slug={slug}",
        
        # Alternative endpoint formats
        f"https://gamma-api.polymarket.com/markets?slug={slug}",
        f"https://strapi.polymarket.com/api/markets?slug={slug}",
    ]
    
    if include_expired:
        endpoints_to_try.extend([
            # Archived/resolved markets endpoints
            f"https://gamma-api.polymarket.com/events?slug={slug}&archived=true",
            f"https://gamma-api.polymarket.com/events?slug={slug}&closed=true", 
            f"https://gamma-api.polymarket.com/events?slug={slug}&resolved=true",
            f"https://gamma-api.polymarket.com/events?slug={slug}&active=false",
            
            # Historical data endpoints
            f"https://strapi.polymarket.com/api/events?slug={slug}&archived=true",
            f"https://data.polymarket.com/events?slug={slug}",
        ])
    
    if tid:
        endpoints_to_try.extend([
            # TID-based searches
            f"https://gamma-api.polymarket.com/events?tid={tid}",
            f"https://gamma-api.polymarket.com/markets?tid={tid}",
            f"https://polymarket.com/api/events?tid={tid}",
            
            # Alternative TID formats
            f"https://gamma-api.polymarket.com/events/{tid}",
            f"https://strapi.polymarket.com/api/events?tid={tid}",
        ])
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://polymarket.com/',
        'Origin': 'https://polymarket.com'
    }
    
    for endpoint in endpoints_to_try:
        try:
            print(f"🔍 Trying endpoint: {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success! Status: {response.status_code}")
                
                # Handle different response formats
                if isinstance(data, list) and len(data) > 0:
                    return data[0]  # Return first event/market
                elif isinstance(data, dict):
                    if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                        return data['data'][0]
                    elif 'events' in data and len(data['events']) > 0:
                        return data['events'][0]
                    else:
                        return data
                        
            else:
                print(f"❌ Failed: {response.status_code} - {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Error with {endpoint}: {e}")
    
    return None

def fetch_historical_markets_from_cache(slug):
    """
    Search for markets in cached historical data files.
    
    Args:
        slug (str): Market slug to search for
        
    Returns:
        dict: Market data if found, None otherwise
    """
    print(f"🗃️  Searching historical cache files for: {slug}")
    
    cache_dir = "./polymarket_cache"
    if not os.path.exists(cache_dir):
        print(f"❌ Cache directory not found: {cache_dir}")
        return None
    
    # Search through all JSON files in cache
    for filename in os.listdir(cache_dir):
        if filename.endswith('.json'):
            cache_file = os.path.join(cache_dir, filename)
            try:
                print(f"   Checking {filename}...")
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                # Handle different cache file formats
                markets_to_search = []
                if isinstance(data, list):
                    markets_to_search = data
                elif isinstance(data, dict):
                    if 'markets' in data:
                        markets_to_search = data['markets']
                    elif 'data' in data:
                        markets_to_search = data['data']
                    else:
                        markets_to_search = [data]
                
                # Search for matching slug
                for market in markets_to_search:
                    if isinstance(market, dict):
                        market_slug = market.get('market_slug', market.get('slug', ''))
                        if market_slug == slug:
                            print(f"✅ Found match in {filename}!")
                            return market
                        
                        # Fuzzy match for similar slugs
                        if slug.replace('-', ' ').lower() in market_slug.replace('-', ' ').lower():
                            print(f"✅ Found potential match in {filename}: {market_slug}")
                            return market
                            
            except Exception as e:
                print(f"   ⚠️  Error reading {filename}: {e}")
                continue
    
    print(f"❌ No matches found in cache files")
    return None

def fetch_market_by_clob_api(slug, include_archived=True):
    """
    Search for market using the CLOB API by filtering through available markets.
    
    Args:
        slug (str): Market slug to search for
        include_archived (bool): Whether to search archived markets
    
    Returns:
        dict: Market data if found, None otherwise
    """
    try:
        print(f"🔍 Searching CLOB API for slug: {slug}")
        
        # Try different API methods for active and archived markets
        api_methods = [
            ('Active Markets', lambda cursor: client.get_markets(next_cursor=cursor, limit=1000) if cursor else client.get_markets(limit=1000))
        ]
        
        # Add archived markets search if available
        if include_archived:
            try:
                # Try to get archived markets (this might not be available in all API versions)
                api_methods.append(('Archived Markets', lambda cursor: client.get_markets(next_cursor=cursor, limit=1000, active=False) if hasattr(client, 'get_markets') else None))
            except:
                pass
        
        for method_name, method_func in api_methods:
            print(f"   Trying {method_name}...")
            
            # Search through batches of markets
            next_cursor = None
            max_searches = 15  # Increase search depth for expired markets
            searches = 0
            
            while searches < max_searches:
                try:
                    response = method_func(next_cursor)
                    if not response:
                        break
                        
                    markets = response.get('data', [])
                    if not markets:
                        break
            
                    # Search for exact slug match
                    for market in markets:
                        if market.get('market_slug') == slug:
                            print(f"✅ Found exact match in {method_name}!")
                            return market
                    
                    # Search for partial matches (fuzzy search)
                    slug_words = slug.replace('-', ' ').split()
                    for market in markets:
                        market_slug = market.get('market_slug', '')
                        market_question = market.get('question', '').lower()
                        market_desc = market.get('description', '').lower()
                        
                        # Check if most words from the slug appear in the market data
                        word_matches = sum(1 for word in slug_words if 
                                         word.lower() in market_slug.lower() or 
                                         word.lower() in market_question or 
                                         word.lower() in market_desc)
                        
                        # Special handling for time-sensitive markets (today, tomorrow, etc.)
                        if 'today' in slug.lower() or 'tomorrow' in slug.lower():
                            if word_matches >= len(slug_words) * 0.6:  # Lower threshold for time-sensitive
                                print(f"✅ Found potential time-sensitive match: {market_slug}")
                                print(f"   Question: {market.get('question')}")
                                print(f"   Closed: {market.get('closed', 'Unknown')}")
                                return market
                        elif word_matches >= len(slug_words) * 0.7:  # 70% word match threshold
                            print(f"✅ Found potential match: {market_slug}")
                            print(f"   Question: {market.get('question')}")
                            return market
                    
                    next_cursor = response.get('next_cursor')
                    if not next_cursor:
                        break
                    
                    searches += 1
                    print(f"   Searched {searches * 1000} {method_name.lower()} so far...")
                    
                except Exception as e:
                    print(f"   ⚠️  Error in {method_name}: {e}")
                    break
        
            print(f"   No matches found in {method_name}")
        
        print(f"❌ No matches found in any API method")
        return None
        
    except Exception as e:
        print(f"❌ Error searching CLOB API: {e}")
        return None

def fetch_by_similar_keywords(slug):
    """
    Try to find markets with similar keywords when exact match fails.
    
    Args:
        slug (str): Market slug to search for
        
    Returns:
        dict: Market data if found, None otherwise
    """
    print(f"🔍 Searching for similar markets to: {slug}")
    
    # Extract key terms from slug
    key_terms = slug.replace('-', ' ').split()
    
    # Generate alternative slug patterns for time-sensitive markets
    alternative_patterns = []
    
    if 'today' in slug.lower():
        base_slug = slug.replace('today', '').replace('--', '-').strip('-')
        alternatives = [
            base_slug + '-tomorrow',
            base_slug + '-this-week', 
            base_slug + '-january-6-2025',  # Specific date alternatives
            base_slug + '-january-2025',
            base_slug.replace('will-', 'will-') + '-2025',
            base_slug.replace('will-', 'will-') + '-by-2025',
        ]
        alternative_patterns.extend(alternatives)
    
    print(f"   Key terms: {key_terms}")
    print(f"   Alternative patterns: {alternative_patterns}")
    
    # Search for alternatives in existing CSV data
    try:
        import pandas as pd
        csv_file = './data/markets_data.csv'
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            
            # Search for alternative patterns first
            for pattern in alternative_patterns:
                matches = df[df['market_slug'].str.contains(pattern, case=False, na=False)]
                if len(matches) > 0:
                    print(f"✅ Found alternative market: {pattern}")
                    return matches.iloc[0].to_dict()
            
            # Search by key terms
            for term in key_terms:
                if len(term) > 3:  # Only search meaningful terms
                    matches = df[df['market_slug'].str.contains(term, case=False, na=False) | 
                               df['question'].str.contains(term, case=False, na=False)]
                    if len(matches) > 0:
                        print(f"✅ Found market containing '{term}': {matches.iloc[0]['market_slug']}")
                        return matches.iloc[0].to_dict()
                        
    except Exception as e:
        print(f"   ⚠️  Error searching CSV: {e}")
    
    return None

def get_market_from_url(url, search_expired=True):
    """
    Main function to fetch market data from a Polymarket URL.
    Tries multiple methods to find the market, including expired/archived markets.
    
    Args:
        url (str): Full Polymarket URL
        search_expired (bool): Whether to search expired/archived markets
    
    Returns:
        dict: Market data with standardized format
    """
    print(f"🚀 FETCHING MARKET FROM URL")
    print("=" * 60)
    print(f"URL: {url}")
    print()
    
    # Extract info from URL
    url_info = extract_market_info_from_url(url)
    print(f"📊 Extracted URL info:")
    for key, value in url_info.items():
        print(f"   {key}: {value}")
    print()
    
    if not url_info['slug']:
        print("❌ Could not extract market slug from URL")
        return None
    
    # Method 1: Try web API (including expired markets)
    print("Method 1: Trying Polymarket Web API (including archived)...")
    web_result = fetch_market_by_web_api(url_info['slug'], url_info['tid'], include_expired=search_expired)
    
    if web_result:
        print("✅ Found market via Web API!")
        print(f"   Title: {web_result.get('title', 'N/A')}")
        print(f"   Description: {web_result.get('description', 'N/A')[:100]}...")
        
        # Extract market slug and condition_id for workflow compatibility
        market_data = {
            'source': 'web_api',
            'market_slug': web_result.get('slug') or url_info['slug'],
            'condition_id': None,
            'full_data': web_result
        }
        
        # Try to find condition_id in markets array
        if 'markets' in web_result and isinstance(web_result['markets'], list):
            for market in web_result['markets']:
                if 'condition_id' in market:
                    market_data['condition_id'] = market['condition_id']
                    break
        
        return market_data
    
    # Method 2: Try CLOB API (including archived)
    print("\nMethod 2: Trying CLOB API (including archived)...")
    clob_result = fetch_market_by_clob_api(url_info['slug'], include_archived=search_expired)
    
    if clob_result:
        print("✅ Found market via CLOB API!")
        print(f"   Slug: {clob_result.get('market_slug')}")
        print(f"   Question: {clob_result.get('question')}")
        
        return {
            'source': 'clob_api',
            'market_slug': clob_result.get('market_slug'),
            'condition_id': clob_result.get('condition_id'),
            'full_data': clob_result
        }
    
    # Method 3: Try historical cache
    if search_expired:
        print("\nMethod 3: Searching historical cache files...")
        cache_result = fetch_historical_markets_from_cache(url_info['slug'])
        
        if cache_result:
            print("✅ Found market in historical cache!")
            return {
                'source': 'historical_cache',
                'market_slug': cache_result.get('market_slug') or cache_result.get('slug') or url_info['slug'],
                'condition_id': cache_result.get('condition_id'),
                'full_data': cache_result
            }
    
    # Method 4: Try similar keywords/alternatives
    print("\nMethod 4: Searching for similar markets...")
    similar_result = fetch_by_similar_keywords(url_info['slug'])
    
    if similar_result:
        print("✅ Found similar market!")
        return {
            'source': 'similar_match',
            'market_slug': similar_result.get('market_slug'),
            'condition_id': similar_result.get('condition_id'),
            'full_data': similar_result
        }
    
    print("\n❌ Could not find market using any method (including expired/archived search)")
    print("\n💡 Suggestions:")
    print("   - The market may have expired and been removed from all datasets")
    print("   - Try searching for similar markets with different time frames")
    print("   - Check if the URL slug has changed or been updated")
    return None

def add_market_to_workflow(url, workflow_file_path=None, force_add_expired=False):
    """
    Fetch market from URL and add it to the workflow.
    
    Args:
        url (str): Polymarket URL
        workflow_file_path (str): Optional path to save the market data
        force_add_expired (bool): Force add expired markets to CSV data
    
    Returns:
        bool: Success status
    """
    market_data = get_market_from_url(url, search_expired=True)
    
    if not market_data:
        return False
    
    market_slug = market_data['market_slug']
    if not market_slug:
        print("❌ No market slug found")
        return False
    
    print(f"\n🎯 RUNNING WORKFLOW WITH FOUND MARKET")
    print("=" * 60)
    print(f"Market slug: {market_slug}")
    print(f"Source: {market_data.get('source', 'unknown')}")
    
    # If market is from historical/expired sources, we may need to add it manually
    if market_data.get('source') in ['historical_cache', 'similar_match'] and force_add_expired:
        print("📝 Adding expired/historical market to current dataset...")
        try:
            # Add the market data to the CSV if it's not already there
            import pandas as pd
            csv_file = './data/markets_data.csv'
            
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                
                # Check if market already exists
                if market_slug not in df['market_slug'].values:
                    print(f"   Adding {market_slug} to markets CSV...")
                    
                    # Create a new row with the found market data
                    market_full_data = market_data['full_data']
                    new_row = {}
                    
                    # Map fields from found data to CSV columns
                    for col in df.columns:
                        if col in market_full_data:
                            new_row[col] = market_full_data[col]
                        else:
                            new_row[col] = 'N/A'  # Default for missing fields
                    
                    # Ensure required fields are present
                    new_row['market_slug'] = market_slug
                    new_row['condition_id'] = market_data.get('condition_id', 'historical_market')
                    
                    # Add to dataframe
                    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    new_df.to_csv(csv_file, index=False)
                    print(f"✅ Added market to CSV dataset")
                else:
                    print(f"   Market {market_slug} already exists in CSV")
                    
        except Exception as e:
            print(f"⚠️  Warning: Could not add to CSV dataset: {e}")
    
    try:
        from incremental_markets_update import update_selected_markets_workflow
        
        # Run the workflow with the found market slug
        success = update_selected_markets_workflow([market_slug])
        
        if success:
            print(f"\n✅ Successfully added market '{market_slug}' to workflow!")
            return True
        else:
            print(f"\n❌ Workflow failed for market '{market_slug}'")
            
            # If workflow failed but we found the market, suggest manual approach
            if market_data:
                print(f"\n💡 Alternative: Market data was found but workflow failed.")
                print(f"   Market slug: {market_slug}")
                print(f"   Condition ID: {market_data.get('condition_id', 'N/A')}")
                print(f"   Source: {market_data.get('source', 'unknown')}")
                print(f"   You can try manually adding this to your selected markets.")
            
            return False
            
    except Exception as e:
        print(f"❌ Error running workflow: {e}")
        return False

def quick_fetch_market(url_or_slug, run_workflow=False, force_expired=False):
    """
    Quick utility function to fetch market info from URL or slug.
    
    Args:
        url_or_slug (str): Either a full Polymarket URL or just the slug
        run_workflow (bool): Whether to automatically run the workflow
        force_expired (bool): Force search in expired/archived markets
    
    Returns:
        dict: Market information or None
    """
    # Determine if input is URL or slug
    if url_or_slug.startswith('http'):
        url = url_or_slug
    else:
        # Assume it's a slug, construct URL
        url = f"https://polymarket.com/event/{url_or_slug}"
    
    print(f"🔍 Quick fetch for: {url_or_slug}")
    print("=" * 40)
    
    market_data = get_market_from_url(url, search_expired=True)
    
    if market_data:
        print(f"\n📊 MARKET FOUND:")
        print(f"   Slug: {market_data.get('market_slug', 'N/A')}")
        print(f"   Condition ID: {market_data.get('condition_id', 'N/A')}")
        print(f"   Source: {market_data.get('source', 'unknown')}")
        
        if 'full_data' in market_data:
            full_data = market_data['full_data']
            if 'question' in full_data:
                print(f"   Question: {full_data['question']}")
            if 'closed' in full_data:
                print(f"   Closed: {full_data['closed']}")
            if 'active' in full_data:
                print(f"   Active: {full_data['active']}")
        
        if run_workflow:
            print(f"\n🔄 Running workflow...")
            success = add_market_to_workflow(url, force_add_expired=force_expired)
            return market_data if success else None
            
        return market_data
    else:
        print(f"\n❌ Market not found")
        return None

if __name__ == "__main__":
    # Example usage
    test_url = "https://polymarket.com/event/will-trump-resign-today?tid=1756938040931"
    
    print("🚀 ENHANCED POLYMARKET MARKET FETCHER")
    print("=" * 60)
    print("This script can:")
    print("  1. Find active markets")
    print("  2. Search expired/archived markets")
    print("  3. Search historical cache files")
    print("  4. Find similar markets by keywords")
    print("  5. Run the arbitrage workflow automatically")
    print()
    
    # Method 1: Just fetch market info (including expired)
    print("🔍 Method 1: Comprehensive search (including expired markets)")
    market_info = quick_fetch_market(test_url, run_workflow=False, force_expired=True)
    
    if market_info:
        # Method 2: Try to run workflow with found market
        print(f"\n🔄 Method 2: Attempting workflow with found market...")
        success = add_market_to_workflow(test_url, force_add_expired=True)
        
        if not success:
            print("\n💡 MANUAL ALTERNATIVE:")
            print("If the workflow failed, you can manually use the found market:")
            print(f"from incremental_markets_update import update_selected_markets_workflow")
            print(f"selected_slugs = ['{market_info.get('market_slug')}']")
            print(f"update_selected_markets_workflow(selected_slugs)")
    else:
        print(f"\n❌ Could not find market anywhere (including expired/archived datasets)")
        print(f"\n🔍 Trying alternative Trump resignation markets...")
        
        # Try some known alternatives
        alternatives = [
            "will-trump-resign-in-2025",
            "will-trump-resign-by-december-31-2026", 
            "will-trump-resign"  # Basic pattern
        ]
        
        for alt in alternatives:
            print(f"\n   Trying: {alt}")
            alt_result = quick_fetch_market(alt, run_workflow=False)
            if alt_result:
                print(f"✅ Found alternative market: {alt}")
                print(f"   Use this slug instead: {alt}")
                break
            else:
                print(f"❌ Not found: {alt}")
    
    print(f"\n" + "=" * 60)
    print("📚 USAGE EXAMPLES:")
    print("# Quick fetch without workflow:")
    print("python3 fetch_market_by_url.py")
    print()
    print("# In Python script:")
    print("from fetch_market_by_url import quick_fetch_market, add_market_to_workflow")
    print("market = quick_fetch_market('https://polymarket.com/event/your-market')")
    print("add_market_to_workflow('https://polymarket.com/event/your-market', force_add_expired=True)")