fatal: detected dubious ownership in repository at '/home/space/github/trading_repos/Polymarket_arbitrage'
To add an exception for this directory, call:

	git config --global --add safe.directory /home/space/github/trading_repos/Polymarket_arbitrage


# Polymarket Trade Copier

A comprehensive tool to monitor and copy trades from any Polymarket address using Jeremy Whittaker's transaction analysis logic.

## Features

- **Real-time Trade Monitoring**: Monitor multiple Polymarket addresses simultaneously
- **Intelligent Trade Copying**: Copy trades with customizable size limits and percentages
- **Historical Analysis**: Analyze past trades for backtesting and strategy evaluation
- **Risk Management**: Built-in position sizing, minimum/maximum trade limits
- **Easy Management**: Simple CLI interface for managing watched addresses
- **Dry Run Mode**: Test strategies without placing actual trades

## Installation

Ensure you have the required dependencies:

```bash
pip install pandas requests python-dotenv py-clob-client plotly beautifulsoup4
```

## Setup

1. **Environment Variables**: Make sure your `keys.env` file contains:
   ```bash
   PK=<YOUR_PRIVATE_KEY>
   API_KEY=<YOUR_POLYMARKET_API_KEY>
   SECRET=<YOUR_API_SECRET>
   PASSPHRASE=<YOUR_API_PASSPHRASE>
   POLYGONSCAN_API_KEY=<YOUR_POLYGONSCAN_KEY>
   ```

2. **Market Data**: Ensure you have the market lookup data:
   ```bash
   python generate_market_lookup_json.py
   ```

## Quick Start

### 1. Add addresses to watch
```bash
python manage_copier.py add 0x1234567890123456789012345678901234567890 --nickname "Profitable Trader"
python manage_copier.py add 0xabcdefabcdefabcdefabcdefabcdefabcdefabcdef --nickname "Volume Leader"
```

### 2. Configure copy settings
```bash
python3 manage_copier.py settings --copy-percentage 0.5 --min-trade-size 25 --max-trade-size 50
```

### 3. Start monitoring (dry run first)
```bash
python3 manage_copier.py start --dry-run
```

### 4. Start live copying
```bash
python manage_copier.py start
```

## Usage Examples

### Direct Monitoring
Monitor specific addresses directly:
```bash
python trade_copier.py --addresses 0x1234... 0xabcd... --copy-percentage 0.3 --min-trade-size 50
```

### Historical Analysis
Analyze past trades from an address:
```bash
python manage_copier.py analyze 0x1234567890123456789012345678901234567890 --hours 48
```

### Copy Historical Trades
Copy trades from the last 24 hours (for backtesting):
```bash
python trade_copier.py --addresses 0x1234... --historical --lookback-hours 24 --dry-run
```

### Custom Parameters
```bash
python trade_copier.py \
  --addresses 0x1234567890123456789012345678901234567890 \
  --copy-percentage 0.25 \
  --min-trade-size 100 \
  --max-trade-size 1000 \
  --check-interval 30
```

## Management Commands

### List Watched Addresses
```bash
python manage_copier.py list
```

### View Current Settings
```bash
python manage_copier.py settings
```

### Update Settings
```bash
python manage_copier.py settings --copy-percentage 0.4 --min-trade-size 20
```

### Remove Address
```bash
python manage_copier.py remove 0x1234567890123456789012345678901234567890
```

## Configuration

The trade copier uses the following parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `copy_percentage` | Percentage of original trade size to copy (0.1-1.0) | 1.0 (100%) |
| `min_trade_size` | Minimum trade size in USDC | 10.0 |
| `max_trade_size` | Maximum trade size in USDC | 1000.0 |
| `check_interval` | How often to check for new trades (seconds) | 60 |

### Risk Management
- **Position Sizing**: Automatically calculates trade size based on `copy_percentage`
- **Size Limits**: Enforces minimum and maximum trade sizes
- **Price Protection**: Uses slightly off-market prices for quick fills
- **Duplicate Prevention**: Tracks processed transactions to avoid double-copying

## How It Works

### 1. Transaction Fetching
Uses Jeremy Whittaker's logic from `get_polygon_data.py`:
- Fetches ERC-1155 transactions from Etherscan API v2 (Polygon chain)
- Paginates through all transaction pages
- Filters for Polymarket contract interactions

### 2. Trade Analysis
- Determines if transaction is a buy or sell
- Extracts token ID, market slug, and outcome
- Calculates trade value and price per token
- Validates against market lookup data

### 3. Trade Copying
- Calculates appropriate copy size based on settings
- Gets current market price from Polymarket API
- Places limit orders slightly off-market for quick execution
- Logs all trade activities for monitoring

### 4. Market Data Integration
- Uses existing `market_lookup.json` for token/market mapping
- Validates all token IDs against known markets
- Filters out invalid or unknown market data

## Safety Features

### Dry Run Mode
Test your strategy without risking capital:
```bash
python manage_copier.py start --dry-run
```

### Transaction Tracking
- Prevents duplicate trade copying
- Maintains history of processed transactions
- Logs all activities for audit trail

### Error Handling
- Graceful handling of API failures
- Retry logic for network issues
- Comprehensive logging for debugging

## Monitoring and Logs

All activities are logged with timestamps and details:
- Trade analysis results
- Copy trade executions
- API errors and retries
- Configuration changes

Example log output:
```
2024-01-15 10:30:45 - INFO - Found 3 recent transactions for 0x1234...
2024-01-15 10:30:46 - INFO - Valid trade found: will-trump-win-2024 - Yes
2024-01-15 10:30:46 - INFO - Copying buy trade:
2024-01-15 10:30:46 - INFO -   Market: will-trump-win-2024 - Yes
2024-01-15 10:30:46 - INFO -   Original value: $250.00
2024-01-15 10:30:46 - INFO -   Copy value: $125.00
2024-01-15 10:30:46 - INFO -   Price: $0.6534
2024-01-15 10:30:46 - INFO -   Shares: 191.27
2024-01-15 10:30:47 - INFO - Copy trade placed successfully. Order ID: abc123
```

## Finding Profitable Addresses

Use the existing leaderboard scraper to find good addresses to copy:
```bash
python get_leaderboard_wallet_ids.py --top-profit
```

Then analyze their historical performance:
```bash 
python get_polygon_data.py --wallets 0x1234567890123456789012345678901234567890
```

## Troubleshooting

### Common Issues

1. **"Market info not found"**: Update market lookup data
   ```bash
   python generate_market_lookup_json.py
   ```

3. **API rate limits**: Increase `check_interval` or add delays
4. **Failed trades**: Check account balance and token allowances
5. **Missing transactions**: Verify Polygonscan API key is valid (now works with Etherscan v2 API)

### Debug Mode
Add detailed logging for troubleshooting:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Integration with Existing Tools

The trade copier integrates seamlessly with existing Polymarket arbitrage tools:
- Uses same market data from `generate_market_lookup_json.py`
- Compatible with user analysis from `get_polygon_data.py`  
- Leverages price data from `get_live_price.py`
- Works with leaderboard data from `get_leaderboard_wallet_ids.py`

## Disclaimer

This tool is for educational and research purposes. Always:
- Test with small amounts first
- Use dry-run mode extensively  
- Understand the risks of automated trading
- Comply with applicable regulations
- Monitor your trades actively

**Trading cryptocurrencies and prediction markets involves substantial risk of loss.**
