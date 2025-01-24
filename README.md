
# Polymarket CLOB Toolkit

This repository contains Python scripts and utilities to interact with the Polymarket Central Limit Order Book (CLOB) API on Polygon Mainnet (chain ID 137). The scripts address:

- Generating/fetching API keys
- Fetching real-time or historical market data (prices, volumes, order books)
- Searching and analyzing markets
- Calculating arbitrage opportunities
- Scraping leaderboards
- Managing user trades (fetching, storing, analyzing)
- Automated or semi-automated trading logic

**Important**: All sensitive data (private key, secrets, passphrases) must be stored in environment variables (`keys.env` or `.env`). **Never** commit private keys to source control.

---

## Table of Contents
1. [Installation and Dependencies](#installation-and-dependencies)
2. [Environment Setup](#environment-setup)
3. [Project Structure](#project-structure)
4. [Script Descriptions](#script-descriptions)
5. [Usage Examples](#usage-examples)
6. [Outdated / Duplicate Scripts](#outdated--duplicate-scripts)
7. [Recommendations and Best Practices](#recommendations-and-best-practices)
8. [Disclaimer](#disclaimer)
9. [License](#license)

---

## Installation and Dependencies

1. **Python Version**: Python 3.9+ recommended.
2. **Create and Activate a Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate   # Linux/Mac
    # or
    venv\Scripts\activate      # Windows
    ```
3. **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4. **ChromeDriver** (For scripts using Selenium):
    - You may need to download a matching [ChromeDriver](https://sites.google.com/chromium.org/driver/) for your Chrome version.

---

## Environment Setup

1. **`keys.env` / `.env`**:
    Store your sensitive data:
    ```bash
    PK=<YOUR_PRIVATE_KEY>
    API_KEY=<YOUR_API_KEY>
    SECRET=<YOUR_API_SECRET>
    PASSPHRASE=<YOUR_API_PASSPHRASE>
    POLYGONSCAN_API_KEY=<YOUR_POLYGONSCAN_KEY>
    ```
    - Always add `.env` and `keys.env` to your `.gitignore`.
2. **Run**:
    - `source keys.env` or load via `dotenv`.

---

## Project Structure

```bash
.
├── data/
│   ├── markets_data.csv
│   ├── market_lookup.json
│   ├── user_trades/
│   ├── historical/
│   ├── book_data/
│   ├── polymarket_trades/
│   ├── ...
├── old/
│   └── condition_id_question_mapping.json
├── plots/
│   └── # HTML/visual outputs from Plotly
├── strategies/
│   └── # Arbitrage strategies or multi-trade definitions
├── create_markets_data_csv.py
├── derive_api_key.py
├── generate_api_key.py
├── generate_market_lookup_json.py
├── generate_markets_data_csv.py
├── get_all_historical_data.py
├── get_api_key.py
├── get_leaderboard_wallet_ids.py
├── get_live_price.py
├── get_market_book_and_live_arb.py
├── get_order_book.py
├── get_polygon_data.py
├── get_polygon_latest_trade_price.py
├── get_presidential_state_odds.py
├── get_trade_slugs_to_parquet.py
├── get_user_profile.py
├── get_user_trade_prices.py
├── goldsky.py
├── live_trade.py
├── plot_arb.py
├── rcp_poller.py
├── strategies.py
├── keys.env
├── .env
└── README.md
```

---

## Script Descriptions

**Brief overview of scripts:**
- `create_markets_data_csv.py`: Fetch all Polymarket CLOB markets and store as CSV.
- `derive_api_key.py`: Derive API key from private key.
- `generate_api_key.py`: Create or derive API credentials.
- `generate_market_lookup_json.py`: Generate lookup JSON from market data CSV.
- `generate_markets_data_csv.py`: Robust market-fetching script with additional logic.
- `get_all_historical_data.py`: Pull minute-level historical prices for each market token.
- `get_api_key.py`: Fetch existing API keys linked to your Polymarket account.
- `get_leaderboard_wallet_ids.py`: Scrape Polymarket’s leaderboard for top addresses.
- `get_live_price.py`: Fetch the last-trade price of a token ID.
- `get_market_book_and_live_arb.py`: Calculate arbitrage opportunities.
- `get_order_book.py`: Fetch order books for relevant trades.
- `get_polygon_data.py`: Fetch user trade data and calculate P/L.
- `get_polygon_latest_trade_price.py`: Retrieve the latest transaction prices for markets.
- `get_presidential_state_odds.py`: Fetch U.S. presidential election odds by state.
- `get_trade_slugs_to_parquet.py`: Fetch minute-level timeseries from Polymarket.
- `get_user_profile.py`: Scrape user profile pages for metadata.
- `get_user_trade_prices.py`: Orchestrate user trades and strategies.
- `goldsky.py`: Download Parquet from S3 and load into DataFrame.
- `live_trade.py`: Example script for placing live trades.
- `plot_arb.py`: Aggregate and plot trade data for visualization.
- `rcp_poller.py`: Poll RealClearPolitics and send alerts on updates.
- `strategies.py`: Define multi-leg trades or arbitrage strategies.

---

## Usage Examples

1. **Generate or Derive API Key**:
    ```bash
    python generate_api_key.py
    # or
    python derive_api_key.py
    ```

2. **Fetch All Markets → CSV**:
    ```bash
    python generate_markets_data_csv.py
    # or
    python create_markets_data_csv.py
    ```

3. **Pull Historical Data**:
    ```bash
    python get_all_historical_data.py
    ```

---

## Disclaimer

- This toolkit is provided **as-is**, without warranty.
- Polymarket or third-party endpoints can change or break at any time.
- Use at your own risk, especially with real funds.

---

## License

(Insert your preferred license text, e.g., MIT.)
