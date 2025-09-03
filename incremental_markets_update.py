import os
import csv
import json
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from generate_market_lookup_json import create_market_lookup_incremental

# Load environment variables
load_dotenv()
api_key = os.getenv('API_KEY')

# Initialize client
host = "https://clob.polymarket.com"
chain_id = 137
client = ClobClient(host, key=api_key, chain_id=chain_id)

def load_existing_markets(csv_file):
    """Load existing markets from CSV and return as dict by condition_id."""
    if not os.path.exists(csv_file):
        print(f"📄 No existing markets file found: {csv_file}")
        return {}, set()
    
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 Loaded {len(df)} existing markets from {csv_file}")
        
        # Convert to dict indexed by condition_id
        existing_markets = {}
        condition_ids = set()
        
        for _, row in df.iterrows():
            condition_id = str(row.get('condition_id', ''))
            if condition_id and condition_id != 'nan':
                existing_markets[condition_id] = row.to_dict()
                condition_ids.add(condition_id)
        
        print(f"📋 Found {len(condition_ids)} unique condition IDs")
        return existing_markets, condition_ids
        
    except Exception as e:
        print(f"⚠️  Error loading existing markets: {e}")
        return {}, set()

def fetch_markets_batch(next_cursor=None, limit=100):
    """Fetch a batch of markets from API."""
    try:
        if next_cursor is None:
            response = client.get_markets(limit=limit)
        else:
            response = client.get_markets(next_cursor=next_cursor, limit=limit)
        
        if 'data' not in response:
            return [], None
            
        return response['data'], response.get('next_cursor')
        
    except Exception as e:
        print(f"⚠️  Error fetching markets batch: {e}")
        return [], None

def incremental_update_markets(csv_file="./data/markets_data.csv", 
                              max_new_markets=1000,
                              backup=True):
    """
    Incrementally update markets data CSV by only adding new markets.
    
    Args:
        csv_file: Path to markets CSV file
        max_new_markets: Maximum number of new markets to fetch (prevents runaway API calls)
        backup: Whether to create backup of existing file
    """
    print("🚀 INCREMENTAL MARKETS UPDATE")
    print("=" * 50)
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)
    
    # Create backup if requested
    if backup and os.path.exists(csv_file):
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_path = f"{csv_file}.backup.{timestamp}"
        try:
            import shutil
            shutil.copy2(csv_file, backup_path)
            print(f"💾 Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠️  Warning: Could not create backup: {e}")
    
    # Load existing markets
    existing_markets, existing_condition_ids = load_existing_markets(csv_file)
    
    # Fetch new markets incrementally
    print("🔄 Fetching new markets from API...")
    all_markets = list(existing_markets.values())
    new_markets_count = 0
    next_cursor = None
    
    while new_markets_count < max_new_markets:
        # Fetch batch
        batch_markets, next_cursor = fetch_markets_batch(next_cursor)
        
        if not batch_markets:
            print("✅ No more markets to fetch")
            break
        
        # Filter for new markets only
        new_batch_markets = []
        for market in batch_markets:
            condition_id = str(market.get('condition_id', ''))
            if condition_id and condition_id not in existing_condition_ids:
                new_batch_markets.append(market)
                existing_condition_ids.add(condition_id)
                new_markets_count += 1
        
        if new_batch_markets:
            all_markets.extend(new_batch_markets)
            print(f"   Added {len(new_batch_markets)} new markets (total new: {new_markets_count})")
        else:
            print(f"   No new markets in this batch")
        
        # Stop if we've reached the limit
        if new_markets_count >= max_new_markets:
            print(f"⚠️  Reached maximum new markets limit: {max_new_markets}")
            break
            
        # Stop if no more pages
        if not next_cursor:
            print("✅ Reached end of available markets")
            break
    
    # Save updated CSV
    if new_markets_count > 0:
        print(f"💾 Saving {len(all_markets)} total markets...")
        save_markets_to_csv(all_markets, csv_file)
        print(f"✅ Successfully added {new_markets_count} new markets")
    else:
        print("✅ No new markets found - CSV is up to date")
    
    return new_markets_count

def save_markets_to_csv(markets_list, csv_file):
    """Save markets list to CSV file."""
    # Get all possible columns
    csv_columns = set()
    for market in markets_list:
        csv_columns.update(market.keys())
        if 'tokens' in market:
            for token in market.get('tokens', []):
                csv_columns.update({f"token_{key}" for key in token.keys()})
    
    csv_columns = sorted(csv_columns)
    
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            
            for market in markets_list:
                row = {}
                for key in csv_columns:
                    if key.startswith("token_"):
                        token_key = key[len("token_"):]
                        tokens = market.get('tokens', [])
                        if tokens:
                            row[key] = ', '.join([str(token.get(token_key, 'N/A')) for token in tokens])
                        else:
                            row[key] = 'N/A'
                    else:
                        row[key] = market.get(key, 'N/A')
                writer.writerow(row)
                
        print(f"💾 Markets data saved to: {csv_file}")
        
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        raise

def update_selected_markets_workflow(selected_slugs, 
                                   markets_csv="./data/markets_data.csv",
                                   selected_json="./data/selected_market_lookup.json"):
    """
    Complete workflow: incremental update markets CSV, then create selected lookup.
    
    Args:
        selected_slugs: List of market slugs to include in selected lookup
        markets_csv: Path to markets CSV file
        selected_json: Path to output selected markets JSON
    """
    print("🔄 COMPLETE SELECTED MARKETS WORKFLOW")
    print("=" * 60)
    
    # Step 1: Incremental update of markets CSV
    print("Step 1: Incremental markets update...")
    new_markets_count = incremental_update_markets(markets_csv)
    
    # Step 2: Update full market lookup JSON (incremental)
    print("\nStep 2: Updating market lookup JSON...")
    temp_lookup = "./data/market_lookup.json"
    success = create_market_lookup_incremental(markets_csv, temp_lookup)
    
    if not success:
        print("❌ Failed to create market lookup")
        return False
    
    # Step 3: Create selected market lookup
    print("\nStep 3: Creating selected market lookup...")
    from create_selected_market_lookup import create_selected_market_lookup
    
    try:
        selected_lookup = create_selected_market_lookup(
            selected_slugs, 
            input_csv=markets_csv,
            temp_lookup=temp_lookup,
            output_json=selected_json
        )
        
        print(f"\n✅ WORKFLOW COMPLETE!")
        print(f"   • New markets added: {new_markets_count}")
        print(f"   • Selected markets: {len(selected_lookup)}")
        print(f"   • Output file: {selected_json}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in workflow: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    selected_market_slugs = [
        "will-trump-resign-today"
    ]
    
    # Run complete workflow
    success = update_selected_markets_workflow(selected_market_slugs)
    
    if success:
        print("\n🎉 Selected markets lookup successfully created!")
    else:
        print("\n❌ Workflow failed")