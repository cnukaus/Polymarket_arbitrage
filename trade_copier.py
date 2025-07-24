#!/usr/bin/env python3
"""
Trade Copier for Polymarket
Monitors and copies trades from specified wallet addresses using Jeremy Whittaker's logic
"""

import os
import requests
import logging
import pandas as pd
import json
import time
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
import argparse
from typing import List, Dict, Optional, Tuple
import threading
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv("keys.env")

# Constants
NEG_RISK_CTF_EXCHANGE = '0x4d97dcd97ec945f40cf65f87097ace5ea0476045'
USDC_ADDRESS = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'

class PolygonTransactionFetcher:
    """Fetches transaction data from Polygonscan API using Jeremy Whittaker's logic"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
    
    def fetch_data(self, url: str) -> Optional[Dict]:
        """Fetch data from a given URL and return the JSON response."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from URL: {url}. Exception: {e}")
            return None
    
    def fetch_all_pages(self, wallet_address: str) -> Optional[pd.DataFrame]:
        """
        Fetch all ERC-1155 transactions for a wallet address with pagination
        Based on Jeremy Whittaker's fetch_all_pages logic
        """
        page = 1
        offset = 100
        retry_attempts = 0
        all_data = []
        
        while True:
            url = (f"https://api.polygonscan.com/api"
                   f"?module=account"
                   f"&action=token1155tx"
                   f"&address={wallet_address}"
                   f"&contractaddress={NEG_RISK_CTF_EXCHANGE}"
                   f"&page={page}"
                   f"&offset={offset}"
                   f"&startblock=0"
                   f"&endblock=99999999"
                   f"&sort=desc"
                   f"&apikey={self.api_key}")
            
            logger.info(f"Fetching transaction data for wallet {wallet_address}, page: {page}")
            
            data = self.fetch_data(url)
            
            if data and data['status'] == '1':
                df = pd.DataFrame(data['result'])
                
                if df.empty:
                    logger.info("No more transactions found, ending pagination.")
                    break
                
                all_data.append(df)
                page += 1
            else:
                logger.error(f"API response error or no data found for page {page}")
                if retry_attempts < 5:
                    retry_attempts += 1
                    time.sleep(retry_attempts)
                else:
                    break
        
        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Fetched {len(final_df)} transactions across all pages.")
            return final_df
        return None

class MarketDataManager:
    """Manages market lookup data and token information"""
    
    def __init__(self, market_lookup_path: str = './data/market_lookup.json'):
        self.market_lookup_path = market_lookup_path
        self.market_lookup = self.load_market_lookup()
    
    def load_market_lookup(self) -> Dict:
        """Load market lookup data from JSON file"""
        try:
            with open(self.market_lookup_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            logger.error(f"Market lookup file not found: {self.market_lookup_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing market lookup JSON: {e}")
            return {}
    
    def find_market_info(self, token_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Find market_slug and outcome based on tokenID"""
        token_id = str(token_id)
        if not token_id or token_id == 'nan':
            logger.warning("Token ID is NaN or empty. Skipping lookup.")
            return None, None
        
        for market in self.market_lookup.values():
            for token in market['tokens']:
                if str(token['token_id']) == token_id:
                    return market['market_slug'], token['outcome']
        
        logger.warning(f"No market info found for tokenID: {token_id}")
        return None, None
    
    def validate_token_ids(self, token_ids: List[str]) -> List[str]:
        """Validate token IDs against market lookup"""
        valid_token_ids = []
        invalid_token_ids = []
        
        for token_id in token_ids:
            market_slug, outcome = self.find_market_info(token_id)
            if market_slug and outcome:
                valid_token_ids.append(token_id)
            else:
                invalid_token_ids.append(token_id)
        
        logger.info(f"Valid token IDs: {valid_token_ids}")
        if invalid_token_ids:
            logger.warning(f"Invalid or missing market info for token IDs: {invalid_token_ids}")
        
        return valid_token_ids

class TradeCopier:
    """Main trade copying class that monitors addresses and replicates trades"""
    
    def __init__(self, private_key: str, api_key: str, secret: str, passphrase: str, polygonscan_api_key: str):
        self.private_key = private_key
        self.polygonscan_api_key = polygonscan_api_key
        
        # Initialize Polymarket client
        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=api_key,
            secret=secret,
            passphrase=passphrase,
            chain_id=POLYGON,
            signature_type=2,
            funder=private_key
        )
        
        # Initialize components
        self.transaction_fetcher = PolygonTransactionFetcher(polygonscan_api_key)
        self.market_data_manager = MarketDataManager()
        
        # Track processed transactions to avoid duplicates
        self.processed_transactions = set()
        
        # Copy settings
        self.copy_percentage = 1.0  # Default: copy 100% of trade size
        self.min_trade_size = 10.0  # Minimum trade size in USDC
        self.max_trade_size = 1000.0  # Maximum trade size in USDC
        
    def set_copy_parameters(self, copy_percentage: float = 1.0, min_trade_size: float = 10.0, max_trade_size: float = 1000.0):
        """Set parameters for trade copying"""
        self.copy_percentage = copy_percentage
        self.min_trade_size = min_trade_size
        self.max_trade_size = max_trade_size
        logger.info(f"Copy parameters set: {copy_percentage*100}% of trades, min: ${min_trade_size}, max: ${max_trade_size}")
    
    def get_latest_transactions(self, wallet_address: str, lookback_minutes: int = 10) -> pd.DataFrame:
        """Get latest transactions for a wallet address within lookback period"""
        df = self.transaction_fetcher.fetch_all_pages(wallet_address)
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Convert timestamp to datetime
        df['timeStamp'] = pd.to_numeric(df['timeStamp'], errors='coerce')
        df['datetime'] = pd.to_datetime(df['timeStamp'], unit='s', errors='coerce')
        
        # Filter for recent transactions
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        recent_df = df[df['datetime'] > cutoff_time].copy()
        
        # Filter out already processed transactions
        if not recent_df.empty:
            recent_df = recent_df[~recent_df['hash'].isin(self.processed_transactions)]
        
        return recent_df
    
    def analyze_trade(self, transaction_row: pd.Series) -> Dict:
        """Analyze a transaction to determine trade details"""
        try:
            token_id = str(transaction_row['tokenID'])
            value = float(transaction_row['value']) / 10**6  # Convert from wei to USDC
            token_value = float(transaction_row['tokenValue'])
            
            # Determine if it's a buy or sell
            wallet_address = transaction_row.get('wallet_address', '').lower()
            to_address = transaction_row['to'].lower()
            from_address = transaction_row['from'].lower()
            
            if to_address == wallet_address:
                trade_type = 'buy'
            elif from_address == wallet_address:
                trade_type = 'sell'
            else:
                trade_type = 'unknown'
            
            # Get market information
            market_slug, outcome = self.market_data_manager.find_market_info(token_id)
            
            if not market_slug or not outcome:
                return {'valid': False, 'reason': 'Market info not found'}
            
            # Calculate price per token
            price_per_token = value / token_value if token_value > 0 else 0
            
            trade_info = {
                'valid': True,
                'token_id': token_id,
                'market_slug': market_slug,
                'outcome': outcome,
                'trade_type': trade_type,
                'value_usdc': value,
                'token_amount': token_value,
                'price_per_token': price_per_token,
                'transaction_hash': transaction_row['hash'],
                'timestamp': transaction_row['datetime']
            }
            
            return trade_info
            
        except Exception as e:
            logger.error(f"Error analyzing trade: {e}")
            return {'valid': False, 'reason': str(e)}
    
    def calculate_copy_size(self, original_value: float) -> float:
        """Calculate the size of the copied trade based on settings"""
        copy_value = original_value * self.copy_percentage
        
        # Apply min/max limits
        copy_value = max(copy_value, self.min_trade_size)
        copy_value = min(copy_value, self.max_trade_size)
        
        return copy_value
    
    def get_token_price(self, token_id: str) -> Optional[float]:
        """Get current price for a token"""
        try:
            # Get the last trade price for this token
            price_response = self.client.get_last_trade_price(token_id)
            if price_response and 'price' in price_response:
                return float(price_response['price'])
        except Exception as e:
            logger.error(f"Error getting token price for {token_id}: {e}")
        
        return None
    
    def place_copy_trade(self, trade_info: Dict) -> bool:
        """Place a copy trade based on the analyzed trade information"""
        try:
            token_id = trade_info['token_id']
            trade_type = trade_info['trade_type']
            original_value = trade_info['value_usdc']
            
            # Calculate copy trade size
            copy_value = self.calculate_copy_size(original_value)
            
            # Get current token price
            current_price = self.get_token_price(token_id)
            if current_price is None:
                logger.error(f"Could not get price for token {token_id}")
                return False
            
            # Calculate number of shares to trade
            shares_to_trade = copy_value / current_price
            
            logger.info(f"Copying {trade_type} trade:")
            logger.info(f"  Market: {trade_info['market_slug']} - {trade_info['outcome']}")
            logger.info(f"  Original value: ${original_value:.2f}")
            logger.info(f"  Copy value: ${copy_value:.2f}")
            logger.info(f"  Price: ${current_price:.4f}")
            logger.info(f"  Shares: {shares_to_trade:.2f}")
            
            # Place the trade based on type
            if trade_type == 'buy':
                # Place a buy order (market or limit)
                response = self.client.post_order(
                    token_id=token_id,
                    price=current_price * 1.01,  # Slightly above market for quick fill
                    size=shares_to_trade,
                    side='BUY',
                    order_type='LIMIT'
                )
            elif trade_type == 'sell':
                # Place a sell order
                response = self.client.post_order(
                    token_id=token_id,
                    price=current_price * 0.99,  # Slightly below market for quick fill
                    size=shares_to_trade,
                    side='SELL',
                    order_type='LIMIT'
                )
            else:
                logger.warning(f"Unknown trade type: {trade_type}")
                return False
            
            if response and 'orderId' in response:
                logger.info(f"Copy trade placed successfully. Order ID: {response['orderId']}")
                return True
            else:
                logger.error(f"Failed to place copy trade. Response: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error placing copy trade: {e}")
            return False
    
    def monitor_address(self, wallet_address: str, check_interval: int = 60):
        """Monitor a single address for new trades"""
        logger.info(f"Starting to monitor address: {wallet_address}")
        
        while True:
            try:
                # Get latest transactions
                recent_transactions = self.get_latest_transactions(wallet_address, lookback_minutes=check_interval//60 + 5)
                
                if not recent_transactions.empty:
                    logger.info(f"Found {len(recent_transactions)} recent transactions for {wallet_address}")
                    
                    for _, transaction in recent_transactions.iterrows():
                        # Add wallet address to transaction for analysis
                        transaction['wallet_address'] = wallet_address
                        
                        # Analyze the trade
                        trade_info = self.analyze_trade(transaction)
                        
                        if trade_info['valid'] and trade_info['value_usdc'] >= self.min_trade_size:
                            logger.info(f"Valid trade found: {trade_info['market_slug']} - {trade_info['outcome']}")
                            
                            # Place copy trade
                            success = self.place_copy_trade(trade_info)
                            
                            if success:
                                logger.info(f"Successfully copied trade from {wallet_address}")
                            else:
                                logger.error(f"Failed to copy trade from {wallet_address}")
                        
                        # Mark transaction as processed
                        self.processed_transactions.add(transaction['hash'])
                
                # Wait before next check
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring address {wallet_address}: {e}")
                time.sleep(check_interval)
    
    def monitor_multiple_addresses(self, wallet_addresses: List[str], check_interval: int = 60):
        """Monitor multiple addresses concurrently"""
        logger.info(f"Starting to monitor {len(wallet_addresses)} addresses")
        
        threads = []
        for address in wallet_addresses:
            thread = threading.Thread(
                target=self.monitor_address,
                args=(address, check_interval),
                daemon=True
            )
            threads.append(thread)
            thread.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Stopping trade copier...")
    
    def copy_historical_trades(self, wallet_address: str, lookback_hours: int = 24, dry_run: bool = True):
        """Copy historical trades from an address (for backtesting or catch-up)"""
        logger.info(f"Copying historical trades from {wallet_address} (last {lookback_hours} hours)")
        
        # Get historical transactions
        df = self.transaction_fetcher.fetch_all_pages(wallet_address)
        
        if df is None or df.empty:
            logger.info("No transactions found")
            return
        
        # Convert timestamp and filter by lookback period
        df['timeStamp'] = pd.to_numeric(df['timeStamp'], errors='coerce')
        df['datetime'] = pd.to_datetime(df['timeStamp'], unit='s', errors='coerce')
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        historical_df = df[df['datetime'] > cutoff_time].copy()
        
        logger.info(f"Found {len(historical_df)} historical transactions")
        
        for _, transaction in historical_df.iterrows():
            transaction['wallet_address'] = wallet_address
            trade_info = self.analyze_trade(transaction)
            
            if trade_info['valid'] and trade_info['value_usdc'] >= self.min_trade_size:
                logger.info(f"Historical trade: {trade_info['market_slug']} - {trade_info['outcome']} (${trade_info['value_usdc']:.2f})")
                
                if not dry_run:
                    success = self.place_copy_trade(trade_info)
                    if success:
                        logger.info("Historical trade copied successfully")
                    else:
                        logger.error("Failed to copy historical trade")
                    
                    # Add delay to avoid rate limiting
                    time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description='Copy trades from Polymarket addresses')
    parser.add_argument('--addresses', nargs='+', required=True, 
                       help='Wallet addresses to monitor')
    parser.add_argument('--copy-percentage', type=float, default=1.0,
                       help='Percentage of original trade size to copy (default: 1.0 = 100%%)')
    parser.add_argument('--min-trade-size', type=float, default=10.0,
                       help='Minimum trade size in USDC (default: 10.0)')
    parser.add_argument('--max-trade-size', type=float, default=1000.0,
                       help='Maximum trade size in USDC (default: 1000.0)')
    parser.add_argument('--check-interval', type=int, default=60,
                       help='Check interval in seconds (default: 60)')
    parser.add_argument('--historical', action='store_true',
                       help='Copy historical trades instead of monitoring')
    parser.add_argument('--lookback-hours', type=int, default=24,
                       help='Hours to look back for historical trades (default: 24)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode - analyze but don\'t place trades')
    
    args = parser.parse_args()
    
    # Load environment variables
    private_key = os.getenv('PK')
    api_key = os.getenv('API_KEY')
    secret = os.getenv('SECRET')
    passphrase = os.getenv('PASSPHRASE')
    polygonscan_api_key = os.getenv('POLYGONSCAN_API_KEY')
    
    if not all([private_key, api_key, secret, passphrase, polygonscan_api_key]):
        logger.error("Missing required environment variables. Check your keys.env file.")
        return
    
    # Initialize trade copier
    copier = TradeCopier(private_key, api_key, secret, passphrase, polygonscan_api_key)
    
    # Set copy parameters
    copier.set_copy_parameters(
        copy_percentage=args.copy_percentage,
        min_trade_size=args.min_trade_size,
        max_trade_size=args.max_trade_size
    )
    
    if args.historical:
        # Copy historical trades
        for address in args.addresses:
            copier.copy_historical_trades(
                address, 
                lookback_hours=args.lookback_hours,
                dry_run=args.dry_run
            )
    else:
        # Monitor addresses for new trades
        if args.dry_run:
            logger.info("DRY RUN MODE: Trades will be analyzed but not placed")
        
        copier.monitor_multiple_addresses(args.addresses, args.check_interval)

if __name__ == "__main__":
    main()
