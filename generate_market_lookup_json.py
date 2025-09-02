import pandas as pd
import json
import ast
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

def load_existing_lookup(json_file):
    """Load existing market lookup JSON file if it exists."""
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r') as f:
                existing_data = json.load(f)
            print(f"📋 Loaded {len(existing_data)} existing markets from {json_file}")
            return existing_data
        except json.JSONDecodeError as e:
            print(f"⚠️  Warning: Invalid JSON in {json_file}, creating backup: {e}")
            backup_path = f"{json_file}.backup.{int(datetime.now().timestamp())}"
            shutil.copy2(json_file, backup_path)
            print(f"💾 Backup created: {backup_path}")
            return {}
        except Exception as e:
            print(f"⚠️  Warning: Could not load {json_file}: {e}")
            return {}
    else:
        print(f"📄 Creating new market lookup file: {json_file}")
        return {}

def safe_parse_tokens(tokens_str):
    """Safely parse tokens string with multiple fallback methods."""
    if pd.isna(tokens_str) or tokens_str == '':
        return []
    
    try:
        # Method 1: Direct literal_eval
        return ast.literal_eval(str(tokens_str))
    except (ValueError, SyntaxError):
        try:
            # Method 2: JSON parsing
            return json.loads(str(tokens_str))
        except json.JSONDecodeError:
            try:
                # Method 3: Handle single quotes to double quotes
                tokens_fixed = str(tokens_str).replace("'", '"')
                return json.loads(tokens_fixed)
            except json.JSONDecodeError:
                print(f"⚠️  Warning: Could not parse tokens: {tokens_str[:100]}...")
                return []

def validate_market_data(condition_id, description, market_slug, tokens):
    """Validate market data before adding to lookup."""
    issues = []
    
    # Validate condition_id
    if not condition_id or pd.isna(condition_id):
        issues.append("Missing condition_id")
    elif not str(condition_id).startswith('0x') and condition_id != 'NaN':
        issues.append(f"Invalid condition_id format: {condition_id}")
    
    # Validate description
    if not description or pd.isna(description) or len(str(description).strip()) < 10:
        issues.append("Missing or too short description")
    
    # Validate market_slug
    if not market_slug or pd.isna(market_slug):
        issues.append("Missing market_slug")
    
    # Validate tokens
    if not tokens or len(tokens) == 0:
        issues.append("No tokens found")
    else:
        for i, token in enumerate(tokens):
            if not isinstance(token, dict):
                issues.append(f"Token {i} is not a dictionary")
            elif 'token_id' not in token or 'outcome' not in token:
                issues.append(f"Token {i} missing required fields")
    
    return issues

def create_market_lookup_incremental(csv_file, output_json_file, backup=True):
    """
    Create/update a JSON lookup from a CSV file incrementally.
    Only adds new markets or updates changed ones.
    """
    print("🚀 INCREMENTAL MARKET LOOKUP GENERATOR")
    print("=" * 60)
    
    # Validate input files
    if not os.path.exists(csv_file):
        print(f"❌ Error: CSV file not found: {csv_file}")
        return False
    
    # Create output directory if it doesn't exist
    output_dir = Path(output_json_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create backup if requested and file exists
    if backup and os.path.exists(output_json_file):
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_path = f"{output_json_file}.backup.{timestamp}"
        try:
            shutil.copy2(output_json_file, backup_path)
            print(f"💾 Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠️  Warning: Could not create backup: {e}")
    
    # Load existing lookup
    existing_lookup = load_existing_lookup(output_json_file)
    
    try:
        # Read the CSV file
        print(f"📊 Reading CSV file: {csv_file}")
        df = pd.read_csv(csv_file)
        print(f"📈 Found {len(df)} total records in CSV")
        
        # Validate required columns
        required_columns = ['condition_id', 'description', 'market_slug', 'tokens']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"❌ Error: Missing required columns: {missing_columns}")
            return False
        
        # Remove duplicates, keeping the most recent (last) occurrence
        print("🔍 Removing duplicates...")
        df_dedup = df.drop_duplicates(subset='condition_id', keep='last')
        print(f"📉 After deduplication: {len(df_dedup)} records")
        
        # Process markets incrementally
        new_markets = 0
        updated_markets = 0
        failed_markets = 0
        
        print("🔄 Processing markets...")
        
        for index, row in df_dedup.iterrows():
            condition_id = str(row['condition_id'])
            description = str(row['description'])
            market_slug = str(row['market_slug'])
            tokens_str = row['tokens']
            
            # Parse tokens safely
            tokens_list = safe_parse_tokens(tokens_str)
            
            # Validate market data
            validation_issues = validate_market_data(condition_id, description, market_slug, tokens_list)
            if validation_issues:
                print(f"⚠️  Skipping market {condition_id}: {'; '.join(validation_issues)}")
                failed_markets += 1
                continue
            
            # Extract token information
            try:
                tokens_info = []
                for token in tokens_list:
                    if isinstance(token, dict) and 'token_id' in token and 'outcome' in token:
                        tokens_info.append({
                            "token_id": str(token["token_id"]),
                            "outcome": str(token["outcome"])
                        })
                
                if not tokens_info:
                    print(f"⚠️  Skipping market {condition_id}: No valid tokens")
                    failed_markets += 1
                    continue
                
            except Exception as e:
                print(f"⚠️  Error processing tokens for {condition_id}: {e}")
                failed_markets += 1
                continue
            
            # Create market entry
            market_entry = {
                "description": description,
                "market_slug": market_slug,
                "tokens": tokens_info,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            # Check if this is new or updated
            if condition_id not in existing_lookup:
                existing_lookup[condition_id] = market_entry
                new_markets += 1
                if (new_markets + updated_markets) % 100 == 0:
                    print(f"   Processed {new_markets + updated_markets} markets...")
            else:
                # Check if data has changed (excluding timestamp)
                existing_entry = existing_lookup[condition_id].copy()
                existing_entry.pop('last_updated', None)
                new_entry_compare = market_entry.copy()
                new_entry_compare.pop('last_updated', None)
                
                if existing_entry != new_entry_compare:
                    existing_lookup[condition_id] = market_entry
                    updated_markets += 1
                    if (new_markets + updated_markets) % 100 == 0:
                        print(f"   Processed {new_markets + updated_markets} markets...")
        
        # Save the updated lookup
        print("💾 Saving updated lookup...")
        try:
            # Write to temporary file first for atomicity
            temp_file = f"{output_json_file}.tmp"
            with open(temp_file, 'w') as json_file:
                json.dump(existing_lookup, json_file, indent=2, sort_keys=True)
            
            # Atomically replace the original file
            os.replace(temp_file, output_json_file)
            
            print(f"✅ Successfully updated market lookup!")
            print(f"📊 SUMMARY:")
            print(f"   • Total markets in lookup: {len(existing_lookup)}")
            print(f"   • New markets added: {new_markets}")
            print(f"   • Markets updated: {updated_markets}")
            print(f"   • Failed to process: {failed_markets}")
            print(f"   • Output file: {output_json_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving lookup file: {e}")
            # Clean up temp file if it exists
            if os.path.exists(f"{output_json_file}.tmp"):
                os.remove(f"{output_json_file}.tmp")
            return False
            
    except Exception as e:
        print(f"❌ Error processing CSV file: {e}")
        return False

# Wrapper for backward compatibility
def create_market_lookup(csv_file, output_json_file):
    """Backward compatibility wrapper."""
    print("⚠️  Using legacy function name. Consider using create_market_lookup_incremental()")
    return create_market_lookup_incremental(csv_file, output_json_file)



def query_description_by_keyword(lookup_json, keyword):
    with open(lookup_json, 'r') as json_file:
        lookup_dict = json.load(json_file)

    results = {cond_id: info for cond_id, info in lookup_dict.items() if keyword.lower() in info['description'].lower()}
    return results


def get_market_slug_by_condition_id(lookup_json, condition_id):
    with open(lookup_json, 'r') as json_file:
        lookup_dict = json.load(json_file)

    return lookup_dict.get(condition_id, {}).get('market_slug')



if __name__ == "__main__":
    # Configuration
    csv_file = './data/markets_data.csv'
    output_json_file = './data/market_lookup.json'
    
    # Run incremental update
    success = create_market_lookup_incremental(csv_file, output_json_file, backup=True)
    
    if success:
        print("\n🎉 Market lookup successfully updated!")
        
        # Example usage of query functions
        try:
            example_condition_id = '0x84dfb8b5cac6356d4ac7bb1da55bb167d0ef65d06afc2546389630098cc467e9'
            market_slug = get_market_slug_by_condition_id(output_json_file, example_condition_id)
            if market_slug:
                print(f"\n📍 Example query result:")
                print(f"   Condition ID: {example_condition_id}")
                print(f"   Market Slug: {market_slug}")
            
            # Example keyword search
            trump_markets = query_description_by_keyword(output_json_file, 'Trump')
            if trump_markets:
                print(f"\n🔍 Found {len(trump_markets)} markets containing 'Trump'")
            
        except Exception as e:
            print(f"⚠️  Warning: Error running examples: {e}")
    else:
        print("\n❌ Failed to update market lookup")
