#!/usr/bin/env python3
"""
Realistic Integration: Enhanced subgraph analytics with actual market lookup data
Uses the existing market_lookup.json to get real Polymarket question IDs
"""

import asyncio
import requests
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from polymarket_subgraph import (
    PolymarketSubgraphClient, 
    MarketEnrichmentData, 
    MarketQualityFilter
)

class RealisticSubgraphAnalyzer:
    """Realistic integration using actual market lookup data"""
    
    def __init__(self):
        self.market_lookup = self.load_market_lookup()
        self.quality_filter = MarketQualityFilter(
            min_volume=2000.0,         # High liquidity threshold
            min_volume_24h=200.0,      # Strong 24h activity required
            min_trades=25,             # Substantial trading history
            min_trades_24h=10,         # Recent trading activity
            max_spread_percentage=0.08, # 8% - tight spreads only
            min_active_positions=10,   # Multiple active participants
            min_volume_consistency=0.3, # High data quality
            min_avg_trade_size=50.0    # Avoid dust trading
        )
    
    def load_market_lookup(self):
        """Load the actual market lookup data"""
        lookup_path = Path(__file__).parent / "data" / "market_lookup.json"
        try:
            with open(lookup_path, 'r') as f:
                data = json.load(f)
            print(f"📋 Loaded {len(data)} markets from market_lookup.json")
            return data
        except FileNotFoundError:
            print("❌ market_lookup.json not found")
            return {}
        except Exception as e:
            print(f"❌ Error loading market lookup: {e}")
            return {}
    
    def get_valid_question_ids(self, limit=30):
        """Get valid question IDs from market lookup data, prioritizing high-liquidity markets"""
        valid_ids = []
        market_info = []
        
        # Prioritize markets likely to have high liquidity based on keywords
        high_liquidity_keywords = [
            'president', 'presidential', 'election', 'trump', 'biden', 'harris',
            'senate', 'house', 'congress', 'governor', 'nfl', 'nba', 'mlb',
            'bitcoin', 'ethereum', 'crypto', 'stock', 'spy', 'federal', 'fed',
            'gdp', 'inflation', 'rate', 'war', 'ukraine', 'russia', 'china'
        ]
        
        # Sort markets by likely liquidity (high-profile topics first)
        sorted_markets = []
        for question_id, market_data in self.market_lookup.items():
            if question_id == "NaN" or not question_id.startswith("0x"):
                continue
                
            # Ensure we have valid token data
            tokens = market_data.get('tokens', [])
            if not tokens or not any(token.get('token_id') for token in tokens):
                continue
            
            description = market_data.get('description', '').lower()
            market_slug = market_data.get('market_slug', '').lower()
            
            # Calculate liquidity priority score based on keywords
            priority_score = 0
            for keyword in high_liquidity_keywords:
                if keyword in description or keyword in market_slug:
                    priority_score += 1
            
            sorted_markets.append({
                'question_id': question_id,
                'priority_score': priority_score,
                'market_data': market_data
            })
        
        # Sort by priority score (highest first)
        sorted_markets.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # Take top markets for analysis
        for market in sorted_markets[:limit]:
            question_id = market['question_id']
            market_data = market['market_data']
            
            valid_ids.append(question_id)
            market_info.append({
                'question_id': question_id,
                'description': market_data.get('description', 'No description'),
                'market_slug': market_data.get('market_slug', ''),
                'tokens': market_data.get('tokens', []),
                'priority_score': market['priority_score']
            })
        
        print(f"🎯 Selected {len(valid_ids)} high-priority markets for liquidity analysis")
        if valid_ids:
            avg_priority = sum(info['priority_score'] for info in market_info) / len(market_info)
            print(f"📊 Average priority score: {avg_priority:.1f} (higher = more likely to have liquidity)")
        
        return valid_ids, market_info
    
    async def enhanced_market_analysis(self, limit=25):
        """
        Comprehensive market analysis focusing on high-liquidity markets
        """
        print("🚀 HIGH-LIQUIDITY MARKET ANALYSIS")
        print("=" * 70)
        print("🎯 Prioritizing markets with strong trading activity and liquidity")
        print("💎 Filter settings optimized for high-quality arbitrage opportunities")
        
        # Get high-priority question IDs from market lookup
        question_ids, market_info = self.get_valid_question_ids(limit)
        if not question_ids:
            print("❌ No valid question IDs found in market lookup")
            return None
        
        # Fetch enhanced subgraph data
        async with PolymarketSubgraphClient() as client:
            print(f"\n🔍 Fetching subgraph analytics for {len(question_ids)} markets...")
            enriched_markets = await client.enrich_markets(question_ids)
            
            print(f"📊 Retrieved enriched data for {len(enriched_markets)} markets")
            
            # Apply quality filters
            print("🎯 Applying enhanced quality filters...")
            quality_markets = self.quality_filter.filter_quality_markets(enriched_markets)
            filter_stats = self.quality_filter.get_filter_statistics(enriched_markets)
            
            # Display comprehensive analytics
            self.display_analytics_summary(filter_stats, enriched_markets, quality_markets, market_info)
            
            # Detailed market analysis
            self.analyze_individual_markets(quality_markets, market_info)
            
            return {
                'total_markets': len(enriched_markets),
                'quality_markets': len(quality_markets),
                'filter_stats': filter_stats,
                'enriched_data': enriched_markets,
                'quality_data': quality_markets
            }
    
    def display_analytics_summary(self, filter_stats, enriched_markets, quality_markets, market_info):
        """Display comprehensive analytics summary"""
        print(f"\n📊 HIGH-LIQUIDITY ANALYTICS SUMMARY:")
        print("-" * 50)
        print(f"   • Total markets analyzed: {filter_stats['total_markets']}")
        print(f"   • High-liquidity markets found: {filter_stats['filtered_markets']}")
        print(f"   • Liquidity filter efficiency: {filter_stats['filtered_markets'] / max(filter_stats['total_markets'], 1):.1%}")
        
        if filter_stats['quality_metrics']['avg_volume'] > 0:
            print(f"\n💎 HIGH-LIQUIDITY METRICS (Average):")
            print(f"   • Volume: ${filter_stats['quality_metrics']['avg_volume']:,.2f}")
            print(f"   • 24h Volume: ${filter_stats['quality_metrics']['avg_24h_volume']:,.2f}")
            print(f"   • Liquidity Score: {filter_stats['quality_metrics']['avg_liquidity']:,.2f}")
            print(f"   • Spread: {filter_stats['quality_metrics']['avg_spread']:.1%}")
            print(f"   • Volume Consistency: {filter_stats['quality_metrics']['avg_consistency']:.2f}")
        
        # Display filter thresholds for transparency
        print(f"\n🎯 LIQUIDITY FILTER THRESHOLDS:")
        print(f"   • Min Volume: ${self.quality_filter.min_volume:,.0f}")
        print(f"   • Min 24h Volume: ${self.quality_filter.min_volume_24h:,.0f}")
        print(f"   • Min Total Trades: {self.quality_filter.min_trades}")
        print(f"   • Min 24h Trades: {self.quality_filter.min_trades_24h}")
        print(f"   • Max Spread: {self.quality_filter.max_spread_percentage:.1%}")
        print(f"   • Min Active Positions: {self.quality_filter.min_active_positions}")
        
        # Filter breakdown analysis
        print(f"\n🔍 FILTER BREAKDOWN:")
        breakdown = filter_stats['filter_breakdown']
        for filter_name, count in breakdown.items():
            if count > 0:
                print(f"   • {filter_name.replace('_', ' ').title()}: {count} markets filtered")
    
    def analyze_individual_markets(self, quality_markets, market_info):
        """Analyze individual high-liquidity markets in detail"""
        print(f"\n🏆 HIGH-LIQUIDITY MARKET ANALYSIS:")
        print("=" * 70)
        
        if not quality_markets:
            print("❌ No high-liquidity markets found with current strict filters")
            print("💡 Consider lowering thresholds if you need more results")
            return
        
        # Create lookup for market descriptions
        info_lookup = {info['question_id']: info for info in market_info}
        
        for i, market in enumerate(quality_markets[:5], 1):
            info = info_lookup.get(market.question_id, {})
            description = info.get('description', 'No description available')
            market_slug = info.get('market_slug', 'No slug')
            
            print(f"\n#{i} MARKET ANALYSIS:")
            print(f"   🆔 Question ID: {market.question_id}")
            print(f"   🔗 Market Slug: {market_slug}")
            print(f"   📝 Description: {description[:100]}...")
            
            # Enhanced trading metrics
            print(f"\n   📊 TRADING METRICS:")
            print(f"      💰 Total Volume: ${market.scaled_collateral_volume or 0:.2f}")
            print(f"      📈 24h Volume: ${market.normalized_volume_24h or 0:.2f}")
            print(f"      🔢 Total Trades: {market.trades_quantity or 0}")
            print(f"      ⚡ 24h Trades: {market.trades_24h or 0}")
            print(f"      📊 Avg Trade Size: ${market.avg_trade_size or 0:.2f}")
            
            # Position and liquidity data
            print(f"\n   🏛️ POSITION DATA:")
            print(f"      👥 Total Positions: {market.total_positions or 0}")
            print(f"      🔥 Active Positions: {market.active_positions or 0}")
            print(f"      💵 Position Value: ${market.position_value_usd or 0:.2f}")
            print(f"      🏦 Market Cap: ${market.market_cap or 0:.2f}")
            
            # Market quality indicators
            print(f"\n   🎯 QUALITY INDICATORS:")
            print(f"      📉 Current Spread: {market.spread_percentage or 0:.1%}")
            print(f"      💧 Liquidity Score: {market.liquidity_score or 0:.2f}")
            print(f"      🔄 Volume Consistency: {market.volume_consistency_score or 0:.2f}")
            print(f"      📈 7d Volume Trend: {market.volume_trend_7d or 1.0:.2f}x")
            print(f"      ⭐ Enrichment Confidence: {market.enrichment_confidence:.2f}")
            
            # Outcome token prices
            if market.outcome_token_prices:
                print(f"\n   💎 TOKEN PRICES:")
                for j, price in enumerate(market.outcome_token_prices):
                    outcome = info.get('tokens', [{}])[j].get('outcome', f'Token {j}') if j < len(info.get('tokens', [])) else f'Token {j}'
                    print(f"      {outcome}: ${price:.3f}")
            
            print(f"   " + "-" * 60)
    
    def export_analysis_results(self, results, filename="subgraph_analysis_results.json"):
        """Export analysis results for further processing"""
        if not results:
            return
        
        export_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_markets': results['total_markets'],
                'quality_markets': results['quality_markets'],
                'filter_efficiency': results['quality_markets'] / max(results['total_markets'], 1),
            },
            'filter_statistics': results['filter_stats'],
            'quality_markets': []
        }
        
        # Add quality market details
        for market in results['quality_data']:
            market_export = {
                'question_id': market.question_id,
                'market_id': market.market_id,
                'title': market.title,
                'trading_metrics': {
                    'scaled_collateral_volume': market.scaled_collateral_volume,
                    'normalized_volume_24h': market.normalized_volume_24h,
                    'trades_quantity': market.trades_quantity,
                    'trades_24h': market.trades_24h,
                    'avg_trade_size': market.avg_trade_size
                },
                'position_data': {
                    'total_positions': market.total_positions,
                    'active_positions': market.active_positions,
                    'position_value_usd': market.position_value_usd,
                    'market_cap': market.market_cap
                },
                'quality_indicators': {
                    'spread_percentage': market.spread_percentage,
                    'liquidity_score': market.liquidity_score,
                    'volume_consistency_score': market.volume_consistency_score,
                    'volume_trend_7d': market.volume_trend_7d,
                    'enrichment_confidence': market.enrichment_confidence
                },
                'outcome_token_prices': market.outcome_token_prices
            }
            export_data['quality_markets'].append(market_export)
        
        # Save to file
        try:
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            print(f"\n💾 Analysis results exported to {filename}")
        except Exception as e:
            print(f"❌ Error exporting results: {e}")


async def main():
    """Main execution function"""
    analyzer = RealisticSubgraphAnalyzer()
    
    print("💎 HIGH-LIQUIDITY MARKET ANALYSIS")
    print("=" * 50)
    print("🎯 Prioritizing markets with:")
    print("   • Volume > $2,000")
    print("   • 24h Volume > $200") 
    print("   • 25+ total trades")
    print("   • 10+ recent trades")
    print("   • <8% spreads")
    print("   • 10+ active positions")
    print("=" * 50)
    
    results = await analyzer.enhanced_market_analysis(limit=30)
    
    if results:
        print(f"\n🎊 ANALYSIS COMPLETE!")
        print(f"Successfully analyzed {results['total_markets']} markets")
        print(f"Found {results['quality_markets']} high-quality opportunities")
        
        # Export results
        analyzer.export_analysis_results(results)
        
        print(f"\n✨ INTEGRATION FEATURES DEMONSTRATED:")
        print(f"   ✅ Real Polymarket question IDs from market_lookup.json")
        print(f"   ✅ Enhanced volume and trading metrics via subgraph")
        print(f"   ✅ Normalized event data for market validation")
        print(f"   ✅ Position tracking and liquidity analysis")
        print(f"   ✅ Multi-tier quality filtering")
        print(f"   ✅ Comprehensive analytics reporting")
    else:
        print("❌ Analysis failed or no data available")


if __name__ == "__main__":
    asyncio.run(main())