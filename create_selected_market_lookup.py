import json
import os
from generate_market_lookup_json import create_market_lookup

def create_selected_market_lookup(selected_slugs, input_csv='./data/markets_data.csv', 
                                 temp_lookup='./data/temp_market_lookup.json',
                                 output_json='./data/selected_market_lookup.json'):
    """
    Create a filtered market lookup JSON containing only specified market slugs.
    
    Args:
        selected_slugs (list): List of market slugs to include in the filtered lookup
        input_csv (str): Path to the markets data CSV file
        temp_lookup (str): Path for temporary full market lookup file
        output_json (str): Path for the filtered output JSON file
    """
    
    # First, create the full market lookup JSON
    print("Creating temporary full market lookup...")
    create_market_lookup(input_csv, temp_lookup)
    
    # Load the full market lookup
    with open(temp_lookup, 'r') as f:
        full_lookup = json.load(f)
    
    # Filter for selected slugs
    selected_lookup = {}
    found_slugs = []
    
    for condition_id, market_data in full_lookup.items():
        if market_data['market_slug'] in selected_slugs:
            selected_lookup[condition_id] = market_data
            found_slugs.append(market_data['market_slug'])
    
    # Save the filtered lookup
    with open(output_json, 'w') as f:
        json.dump(selected_lookup, f, indent=4)
    
    # Clean up temporary file
    if os.path.exists(temp_lookup):
        os.remove(temp_lookup)
    
    # Report results
    print(f"Selected market lookup created: {output_json}")
    print(f"Found {len(selected_lookup)} markets from {len(selected_slugs)} requested slugs")
    
    missing_slugs = set(selected_slugs) - set(found_slugs)
    if missing_slugs:
        print(f"Missing slugs not found in data: {list(missing_slugs)}")
    
    print(f"Included slugs: {found_slugs}")
    
    return selected_lookup

if __name__ == "__main__":
    # Example usage with selected market slugs
    selected_market_slugs = [
        "will-trump-resign-today"
    ]
    
    # Option 1: Simple approach (assumes markets_data.csv is current)
    create_selected_market_lookup(selected_market_slugs)
    
    # Option 2: Use incremental workflow (recommended for fresh data)
    # from incremental_markets_update import update_selected_markets_workflow
    # update_selected_markets_workflow(selected_market_slugs)