New Features:
  - Confidence Score Calculation: Formula automatically calculates daily liquidity × cubic probability multiplier
  - Smart Score Formatting: Displays as 1.5k for large values, 12.3 for medium, 0.045 for small
  - New Sort Option: --sort-by confidence_score to rank by highest scoring markets
  - Enhanced Display: Added Score column showing the confidence metric

  Updated Display Format:
  Yes%  | Odds  | Days | Volume    | Score   | Question
   92.1%| 1.09  | 12d  | $125,430  |  2.1k   | Will Bitcoin reach...
   88.5%| 1.13  | 25d  | $45,230   |   987   | Will Trump win...
   65.2%| 1.54  | 8d   | $89,500   |  2.456  | Will rate cut happen...

  Usage Examples:
  # Rank by confidence score (highest first)
  python polymarket_markets.py --date-range-cache --start 202507 --end 202508 --odds-ranking --sort-by confidence_score

  # Show all available sorting options
  python polymarket_markets.py --odds-ranking --sort-by confidence_score --limit 10

  The formula now identifies high-confidence, liquid markets perfect for "slam dunk" betting opportunities!

New Features:
  - Odds extraction: Parses outcomePrices and outcomes to find Yes/No
  probabilities
  - Smart outcome detection: Handles explicit "Yes/No" or uses first two
  options
  - Multiple ranking criteria: Sort by probability, odds, volume, or
  liquidity
  - Rich odds data: Calculates decimal odds, probabilities, and includes
  volume/liquidity

  New Parameters:
  - --odds-ranking - Enable odds-based ranking instead of date sorting
  - --sort-by - Choose ranking criterion: yes_probability,
  yes_odds_decimal, volume, liquidity

  Usage Examples:
  # Rank cached markets by highest Yes probability
  python polymarket_markets.py --date-range-cache --start 202507 --end 202508 --odds-ranking

  # Sort by lowest odds (highest probability)
  python polymarket_markets.py --use-cache 2025-07 --odds-ranking --sort-by
   yes_odds_decimal

  # Rank by volume with odds data
  python polymarket_markets.py --odds-ranking --sort-by volume --limit 20


New Features:
  - Pagination: fetch_all_markets() gets ALL markets with 100-market
  batches
  - JSON caching: Markets organized by year-month files
  (markets_2025-07.json, etc.)
  - Earliest markets priority: When caching, shows earliest month markets
  first
  - Cache management: Load/list cached data without API calls

New Parameters:
  - --start YYYYMM - Start date for market closing period (e.g., 202501)
  - --end YYYYMM - End date for market closing period (e.g., 202512)
  - --date-range-cache - Use cached data for specified date range

  Usage Examples:
  # Download and cache markets closing between Jan-Dec 2025
  python polymarket_markets.py --cache --start 202501 --end 202512

  # Load cached markets for specific date range
  python polymarket_markets.py --date-range-cache --start 202501 --end
  202503

  # Fetch live markets closing in specific period
  python polymarket_markets.py --start 202507 --end 202508 --limit 100

  # Load single month cache with additional date filtering
  python polymarket_markets.py --use-cache 2025-07 --start 202507 --end
  202507

  Key Features:
  - YYYYMM parsing: Converts 202501 → January 1, 2025 (start of month)
  - End month handling: 202512 includes all of December 2025
  - Cache range loading: Automatically loads multiple month files
  (2025-01.json, 2025-02.json, etc.)
  - Precise filtering: Double-filters for exact date precision

