
# Polymarket Arbitrage

This is a project I worked on in 2024 to find arbitrage in Polymarket.com specifically as it pertained to the Presidential elections. My original writeup on this an be found here. https://jeremywhittaker.com/index.php/2024/09/24/arbitrage-in-polymarket-com/

- Generating/fetching API keys
- Fetching real-time or historical market data (prices, volumes, order books)
- Searching and analyzing markets
- Calculating arbitrage opportunities
- Scraping leaderboards
- Managing user trades (fetching, storing, analyzing)
- Automated or semi-automated trading logic

**Important**: All sensitive data (private key, secrets, passphrases) must be stored in environment variables (`keys.env` or `.env`). 

---

## Table of Contents
1. [Installation and Dependencies](#installation-and-dependencies)
2. [Environment Setup](#environment-setup)
3. [Project Structure](#project-structure)
4. [Script Descriptions](#script-descriptions)
    - `create_markets_data_csv.py`
    - `derive_api_key.py`
    - `generate_api_key.py`
    - `generate_market_lookup_json.py`
    - `generate_markets_data_csv.py`
    - `get_all_historical_data.py`
    - `get_api_key.py`
    - `get_leaderboard_wallet_ids.py`
    - `get_live_price.py`
    - `get_market_book_and_live_arb.py`
    - `get_order_book.py`
    - `get_polygon_data.py`
    - `get_polygon_latest_trade_price.py`
    - `get_presidential_state_odds.py`
    - `get_trade_slugs_to_parquet.py`
    - `get_user_profile.py`
    - `get_user_trade_prices.py`
    - `goldsky.py`
    - `live_trade.py`
    - `plot_arb.py`
    - `rcp_poller.py`
    - `strategies.py`
5. [Usage Examples](#usage-examples)
6. [Outdated / Duplicate Scripts](#outdated--duplicate-scripts)
7. [Recommendations and Best Practices](#recommendations-and-best-practices)
8. [Disclaimer](#disclaimer)
9. [License](#license)

---

## Installation and Dependencies

### Python Version
Python 3.9+ recommended.

### Create and Activate a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
# or
venv\Scripts\activate      # Windows
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### ChromeDriver (For scripts using Selenium)
You may need to download a matching [ChromeDriver](https://sites.google.com/chromium.org/driver/) for your Chrome version.

---

## Environment Setup

### `keys.env` / `.env`
Store your sensitive data:
```bash
PK=<YOUR_PRIVATE_KEY>
API_KEY=<YOUR_API_KEY>
SECRET=<YOUR_API_SECRET>
PASSPHRASE=<YOUR_API_PASSPHRASE>
POLYGONSCAN_API_KEY=<YOUR_POLYGONSCAN_KEY>
```
Always add `.env` and `keys.env` to your `.gitignore`.

### Run
```bash
source keys.env  # Or use dotenv
```

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

### `create_markets_data_csv.py`
- **Purpose**: Fetch all Polymarket CLOB markets and store as CSV.
- **Notes**: Potentially replaced by `generate_markets_data_csv.py`.

...

### `strategies.py`
- **Purpose**: Defines a Python list of multi-leg trades or arbitrage strategies.

...

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
    ```

...

---

## Disclaimer

- This toolkit is provided **as-is**, without warranty.
- Use at your own risk.

---

## License
(Insert license text)
