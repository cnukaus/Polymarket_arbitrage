#!/usr/bin/env python3
"""
Trade Copier Setup and Management Script
Easy interface for setting up and managing Polymarket trade copying
"""

import os
import json
import argparse
import subprocess
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradeCopierManager:
    """Helper class to manage trade copying operations"""
    
    def __init__(self):
        self.config_file = './data/trade_copier_config.json'
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Invalid config file, creating new one")
        
        # Default configuration
        return {
            'watched_addresses': [],
            'copy_settings': {
                'copy_percentage': 1.0,
                'min_trade_size': 10.0,
                'max_trade_size': 1000.0,
                'check_interval': 60
            },
            'filters': {
                'min_original_trade_size': 50.0,
                'excluded_markets': [],
                'included_outcomes': ['Yes', 'No']
            }
        }
    
    def save_config(self):
        """Save configuration to file"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"Configuration saved to {self.config_file}")
    
    def add_address(self, address: str, nickname: str = None):
        """Add an address to watch list"""
        if not address.startswith('0x') or len(address) != 42:
            logger.error("Invalid Ethereum address format")
            return False
        
        # Check if address already exists
        for watched in self.config['watched_addresses']:
            if watched['address'].lower() == address.lower():
                logger.warning(f"Address {address} is already being watched")
                return False
        
        address_info = {
            'address': address,
            'nickname': nickname or address[:10] + '...',
            'added_date': str(datetime.now()),
            'active': True
        }
        
        self.config['watched_addresses'].append(address_info)
        self.save_config()
        logger.info(f"Added address {address} with nickname '{address_info['nickname']}'")
        return True
    
    def remove_address(self, address: str):
        """Remove an address from watch list"""
        original_count = len(self.config['watched_addresses'])
        self.config['watched_addresses'] = [
            addr for addr in self.config['watched_addresses'] 
            if addr['address'].lower() != address.lower()
        ]
        
        if len(self.config['watched_addresses']) < original_count:
            self.save_config()
            logger.info(f"Removed address {address}")
            return True
        else:
            logger.warning(f"Address {address} not found in watch list")
            return False
    
    def list_addresses(self):
        """List all watched addresses"""
        if not self.config['watched_addresses']:
            print("No addresses are currently being watched.")
            return
        
        print("\nWatched Addresses:")
        print("-" * 80)
        for i, addr in enumerate(self.config['watched_addresses'], 1):
            status = "✓ Active" if addr['active'] else "✗ Inactive"  
            print(f"{i}. {addr['nickname']}")
            print(f"   Address: {addr['address']}")
            print(f"   Status: {status}")
            print(f"   Added: {addr['added_date']}")
            print()
    
    def update_copy_settings(self, **kwargs):
        """Update copy settings"""
        valid_settings = ['copy_percentage', 'min_trade_size', 'max_trade_size', 'check_interval']
        
        for key, value in kwargs.items():
            if key in valid_settings:
                self.config['copy_settings'][key] = value
                logger.info(f"Updated {key} to {value}")
            else:
                logger.warning(f"Unknown setting: {key}")
        
        self.save_config()
    
    def show_settings(self):
        """Display current settings"""
        print("\nCurrent Trade Copier Settings:")
        print("-" * 40)
        print(f"Copy Percentage: {self.config['copy_settings']['copy_percentage']*100}%")
        print(f"Min Trade Size: ${self.config['copy_settings']['min_trade_size']}")
        print(f"Max Trade Size: ${self.config['copy_settings']['max_trade_size']}")
        print(f"Check Interval: {self.config['copy_settings']['check_interval']} seconds")
        print(f"Min Original Trade Size: ${self.config['filters']['min_original_trade_size']}")
        print()
    
    def start_monitoring(self, dry_run: bool = False):
        """Start monitoring all active addresses"""
        active_addresses = [
            addr['address'] for addr in self.config['watched_addresses'] 
            if addr['active']
        ]
        
        if not active_addresses:
            logger.error("No active addresses to monitor")
            return False
        
        logger.info(f"Starting to monitor {len(active_addresses)} addresses")
        
        # Build command
        cmd = ['python3', 'trade_copier.py']
        cmd.extend(['--addresses'] + active_addresses)
        cmd.extend(['--copy-percentage', str(self.config['copy_settings']['copy_percentage'])])
        cmd.extend(['--min-trade-size', str(self.config['copy_settings']['min_trade_size'])])
        cmd.extend(['--max-trade-size', str(self.config['copy_settings']['max_trade_size'])])
        cmd.extend(['--check-interval', str(self.config['copy_settings']['check_interval'])])
        
        if dry_run:
            cmd.append('--dry-run')
        
        # Execute command
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error during monitoring: {e}")
        
        return True
    
    def analyze_address(self, address: str, hours: int = 24):
        """Analyze historical trades for an address"""
        logger.info(f"Analyzing trades from {address} (last {hours} hours)")
        
        cmd = [
            'python3', 'trade_copier.py',
            '--addresses', address,
            '--historical',
            '--lookback-hours', str(hours),
            '--dry-run'
        ]
        
        try:
            subprocess.run(cmd)
        except Exception as e:
            logger.error(f"Error during analysis: {e}")

def main():
    parser = argparse.ArgumentParser(description='Manage Polymarket Trade Copier')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add address command
    add_parser = subparsers.add_parser('add', help='Add address to watch list')
    add_parser.add_argument('address', help='Ethereum address to watch')
    add_parser.add_argument('--nickname', help='Nickname for the address')
    
    # Remove address command
    remove_parser = subparsers.add_parser('remove', help='Remove address from watch list')
    remove_parser.add_argument('address', help='Ethereum address to remove')
    
    # List addresses command
    subparsers.add_parser('list', help='List all watched addresses')
    
    # Settings command
    settings_parser = subparsers.add_parser('settings', help='View or update settings')
    settings_parser.add_argument('--copy-percentage', type=float, help='Percentage of trade to copy (0.1-1.0)')
    settings_parser.add_argument('--min-trade-size', type=float, help='Minimum trade size in USDC')
    settings_parser.add_argument('--max-trade-size', type=float, help='Maximum trade size in USDC')
    settings_parser.add_argument('--check-interval', type=int, help='Check interval in seconds')
    
    # Start monitoring command
    start_parser = subparsers.add_parser('start', help='Start monitoring addresses')
    start_parser.add_argument('--dry-run', action='store_true', help='Analyze trades without placing orders')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze historical trades from an address')
    analyze_parser.add_argument('address', help='Address to analyze')
    analyze_parser.add_argument('--hours', type=int, default=24, help='Hours to look back (default: 24)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = TradeCopierManager()
    
    if args.command == 'add':
        manager.add_address(args.address, args.nickname)
    
    elif args.command == 'remove':
        manager.remove_address(args.address)
    
    elif args.command == 'list':
        manager.list_addresses()
    
    elif args.command == 'settings':
        if any([args.copy_percentage, args.min_trade_size, args.max_trade_size, args.check_interval]):
            # Update settings
            kwargs = {}
            if args.copy_percentage is not None:
                kwargs['copy_percentage'] = args.copy_percentage
            if args.min_trade_size is not None:
                kwargs['min_trade_size'] = args.min_trade_size
            if args.max_trade_size is not None:
                kwargs['max_trade_size'] = args.max_trade_size
            if args.check_interval is not None:
                kwargs['check_interval'] = args.check_interval
            
            manager.update_copy_settings(**kwargs)
        
        # Always show current settings
        manager.show_settings()
    
    elif args.command == 'start':
        manager.start_monitoring(dry_run=args.dry_run)
    
    elif args.command == 'analyze':
        manager.analyze_address(args.address, args.hours)

if __name__ == "__main__":
    from datetime import datetime
    main()