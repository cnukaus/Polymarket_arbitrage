#!/usr/bin/env python3
"""
Enhanced Polymarket Markets Fetcher with flexible query matching.

This module now re-exports the merged functionality from polymarket_markets.py
so existing imports keep working after the merge.
"""

from polymarket_markets import (
    DEFAULT_SENTENCE_MODEL,
    encode_market_questions,
    normalize_text,
    extract_key_terms,
    generate_query_variations,
    find_similar_question,
    get_polymarket_values,
    check_for_arbitrage,
    get_full_list_enhanced,
    get_full_list,
    test_get_full_list_limited,
    run_enhanced_demo,
)

__all__ = [
    'DEFAULT_SENTENCE_MODEL',
    'encode_market_questions',
    'normalize_text',
    'extract_key_terms',
    'generate_query_variations',
    'find_similar_question',
    'get_polymarket_values',
    'check_for_arbitrage',
    'get_full_list_enhanced',
    'get_full_list',
    'test_get_full_list_limited',
    'run_enhanced_demo',
]


def main():
    """Run the enhanced demo directly from the compatibility wrapper."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Enhanced Polymarket query-matching demo (compatibility wrapper)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=15,
        help='Number of PredictIt contracts to scan in the demo (default: 15)',
    )
    args = parser.parse_args()
    run_enhanced_demo(limit=args.limit)


if __name__ == '__main__':
    main()
