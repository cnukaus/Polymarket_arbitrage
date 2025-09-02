Here’s a tight, systems-first design doc for a “news-to-markets” arbitrage scout that (a) searches Stacker News for signals and (b) scans multiple prediction markets—initially Polymarket and Predyx—to detect and (optionally) execute cross-venue arbitrage.

---

# Goal

Continuously discover event overlaps across markets, normalize them into a common schema, detect price inconsistencies large enough to cover fees/slippage, and (optionally) place hedged orders to lock in risk-free or near-risk-free spreads.

---

# High-level architecture

**1) Connectors & Ingestion**

- **Stacker News (signal feed):** Query Stacker News’ **GraphQL** endpoint (`/api/graphql`) to pull fresh posts/titles/links and search by keywords/entities (e.g., “BTC ETF,” “US CPI,” “Elon”). We use this both to discover *new* events and to enrich/validate event metadata (dates, named entities). ([Stacker News](https://stacker.news/items/701535?utm_source=chatgpt.com), [GitHub](https://github.com/stackernews/stacker.news?utm_source=chatgpt.com))
- **Polymarket (market/prices):** Use the **Gamma Markets REST API** (`get-markets`) for market metadata + status and the **Data API (trades)** for recent fills and depth proxies; upgrade to the CLOB when executing. ([docs.polymarket.com](https://docs.polymarket.com/developers/gamma-markets-api/overview?utm_source=chatgpt.com))
- **Predyx (market/prices):** As of now, public API docs aren’t published; scrape the markets index and detail pages (stable CSS selectors) and/or consume any internal JSON the site exposes. Confirm Lightning node identity for due diligence and settlement characteristics. Plan to swap in an official API when released. ([predyx](https://beta.predyx.com/?utm_source=chatgpt.com), [thunderlytics.net](https://www.thunderlytics.net/node/03b465d6fcd7305c9fbfac523ec6c4a179756ad03e0400ed220ee303161bedbbf4/predyx-com-predict-the-future.html?utm_source=chatgpt.com))

**2) Normalization Layer (Canonical Event Model)**

- Transform each venue’s market into a **canonical Event**:
    - `event_id` (internal), `source_ids` (per venue), `title`, `entities` (people, orgs, assets), `category`, `resolution_criteria` (plain text + URL), `deadline` (ISO), `venue`, `contract_sides` (YES/NO, multi-outcome), `price_yes`, `price_no`, `fees`, `min_tick`, `lot_size`, `liquidity`.
- Stacker News posts are mapped to candidate **events** if they contain overlapping entities or exact matches on known market titles/slugs; used to (a) discover new tickers/topics and (b) validate **resolution criteria**/timelines when venues differ.

**3) Event Matching (Cross-venue linking)**

- **String + semantic matching**: title normalization, acronym expansion, named-entity extraction, fuzzy ratios; embedding similarity to catch “BTC monthly close > $X” vs “Bitcoin ends month above $X”.
- **Constraint checks**: event window overlap, same adjudicator/criteria when available (e.g., “official BLS CPI for Aug 2025”).
- **Human-in-the-loop queue** for low-confidence pairs (thresholded cosine similarity + rule checks).

**4) Pricing & Arbitrage Engine**

- For binary YES/NO markets A (venue i) and B (venue j), compute:
    - **Cross-venue sure-thing test**:
        
        Buy YES on A at pAp_A and buy NO on B at 1−pB1 - p_B. If
        
        pA+(1−pB)+fees+slippage<1p_A + (1 - p_B) + \text{fees} + \text{slippage} < 1 ⇒ *guaranteed* edge.
        
    - Include **per-venue fees**, **trade size caps**, **tick sizes**, **withdrawal costs**, and **FX** (e.g., sats vs USDC).
    - Use **order book/trade prints** (Polymarket Data API; Predyx scraped bid/ask if shown) to estimate fill price/impact. ([docs.polymarket.com](https://docs.polymarket.com/developers/CLOB/trades/trades-data-api?utm_source=chatgpt.com))
- For multi-outcome markets, reduce to complementary bundles (e.g., buy a set across venues that sums to 100% outcome coverage) and check net cost vs 1 minus fees.

**5) Execution Layer (optional, pluggable)**

- **Polymarket:** place orders via their trading/CLOB stack once keys and headers are configured; route with price-time priority and partial fills, with kill-switch on adverse drift. (Docs provide the on-ramp to trading APIs.) ([docs.polymarket.com](https://docs.polymarket.com/quickstart/introduction/main?utm_source=chatgpt.com))
- **Predyx:** until an API exists, keep **semi-automatic**: alert + deep link to the exact market/side and the recommended stake sized to the hedge leg; use LN wallets for fast settlement. Automate once Predyx exposes endpoints. ([predyx](https://beta.predyx.com/?utm_source=chatgpt.com), [Stacker News](https://stacker.news/items/701885?utm_source=chatgpt.com))

**6) Treasury, Wallets & Settlement**

- Maintain per-venue wallets/balances (**USDC/USDT** on Polymarket; **sats** via LN for Predyx). Keep a **buffer** on each to avoid transfer latency during short-lived spreads. LN node due diligence for counterpart risk/fees. ([thunderlytics.net](https://www.thunderlytics.net/node/03b465d6fcd7305c9fbfac523ec6c4a179756ad03e0400ed220ee303161bedbbf4/predyx-com-predict-the-future.html?utm_source=chatgpt.com))

**7) Monitoring, Risk & Compliance**

- **Geo/ToS filters:** Polymarket has jurisdictional limitations; detect the operator’s residency and block automated execution where restricted.
- **Market halts / rule changes:** subscribe to market updates (status, resolution rule edits) and auto-de-risk.
- **PnL attribution:** per spread, per venue; include carry, fees, and failed hedge incidents.

---

# Data flows

1. **Pull signals** from Stacker News (GraphQL search by entities/topics; incremental since last cursor). Store raw + parsed. ([Stacker News](https://stacker.news/items/701535?utm_source=chatgpt.com))
2. **Pull markets** from Polymarket (paged `get-markets`, then snapshot key fields; augment with `trades` to infer spread/impact). ([docs.polymarket.com](https://docs.polymarket.com/developers/gamma-markets-api/get-markets?utm_source=chatgpt.com))
3. **Pull markets** from Predyx (scrape `/market` and detail pages; parse title, chance %, bid/ask if shown, volume in sats, close date). ([predyx](https://beta.predyx.com/market?utm_source=chatgpt.com))
4. **Normalize → match** into cross-venue event clusters.
5. **Run arbitrage scans** continuously; when edge ≥ threshold, create **actionables**:
    - “Pure arb” (YES here / NO there), or
    - “Stat-arb” (edge but not fully risk-free; mark as such).
6. **(Optional) Execute** and log fills; back-off on slippage; mark hedged pairs; monitor PnL until resolution.

---

# Key design choices & why

1. **GraphQL for Stacker News**
    - SN exposes a first-party GraphQL endpoint (`/api/graphql`), making structured search feasible (titles, tags, territories, recency) and more robust than scraping HTML. It’s also future-proof for richer filters as SN evolves. ([Stacker News](https://stacker.news/items/701535?utm_source=chatgpt.com))
2. **Polymarket Gamma + Data APIs first**
    - Official, documented REST endpoints for market discovery and trade history give us clean, rate-limited, *stable* integrations; we only drop to the CLOB for live execution once needed. This lowers integration risk and accelerates MVP. ([docs.polymarket.com](https://docs.polymarket.com/developers/gamma-markets-api/overview?utm_source=chatgpt.com))
3. **Predyx via scraping (for now)**
    - Predyx is Lightning-native and in active iteration, but public API docs aren’t yet published. HTML scraping of the market list/detail pages provides workable data today; we design the connector behind an interface so we can swap in an official API later without touching downstream code. The LN node intel informs fees/throughput expectations. ([predyx](https://beta.predyx.com/?utm_source=chatgpt.com), [thunderlytics.net](https://www.thunderlytics.net/node/03b465d6fcd7305c9fbfac523ec6c4a179756ad03e0400ed220ee303161bedbbf4/predyx-com-predict-the-future.html?utm_source=chatgpt.com))
4. **Canonical Event Model**
    - Every venue models outcomes differently (YES/NO vs probabilities, different resolution text). A strict canonical schema lets us compare apples to apples, improving both matching precision and risk calculations, and simplifies storage, backtesting, and alerting.
5. **Human-in-the-loop for low-confidence matches**
    - Title wording and resolution criteria often differ subtly; a quick operator check on ambiguous pairs prevents *false arbitrage* (where two markets look similar but resolve differently), which is a major real-world failure mode.
6. **Separation of “Detection” and “Execution”**
    - Compliance and geo issues vary. Many users just want alerts. Keeping execution pluggable lets you run purely informational in restricted regions and flip on trading only where allowed.

---

# Matching & risk logic (condensed)

- **Binary arb test** (fee-aware):
    
    If pYES,A+(1−pYES,B)+fA+fB+slippage<1p_{\text{YES},A} + (1 - p_{\text{YES},B}) + f_A + f_B + \text{slippage} < 1 ⇒ lock spread by buying YES on A and NO on B.
    
    Size by the tighter of available depth at quoted prices and your per-venue bankroll, with a reserve for adverse move tolerance.
    
- **Multi-outcome**: construct a complete outcome cover (across or within venues), compute cost vs 1; accept only if cost + frictions < 1 − buffer.
- **Liquidity filters**: require min displayed size or recent prints at or better than target prices (Polymarket `trades`). If Predyx shows only “chance %” without book transparency, apply stricter buffers. ([docs.polymarket.com](https://docs.polymarket.com/developers/CLOB/trades/trades-data-api?utm_source=chatgpt.com))
- **Timing risk**: ensure identical or overlapping resolution windows; penalize edges where one venue can resolve materially earlier (cash-flow / information asymmetry).
- **Resolution text parity**: hash or store normalized resolution statements and link to sources (e.g., “BLS CPI” vs “any CPI headline”); reject mismatches.

---

# MVP vs Production

**MVP (2–3 weeks of build time, depending on polish)**

- Connectors: SN GraphQL (read-only), Polymarket (markets + trades), Predyx (scrape).
- Event model + basic fuzzy matching (Levenshtein + embeddings).
- Fee/slippage-aware arb calculator.
- Alerting (Discord/Telegram) with deep links; optional manual trade checklists.

**Production**

- Add **execution adapters** (Polymarket CLOB), balance manager, and a funding optimizer across USDC/LN.
- Confidence-scored matching (hybrid rules + embeddings + weak supervision).
- Latency-optimized polling or websockets (where available).
- Full observability (Prom, Grafana), incident runbooks, kill-switches, and compliance guardrails.

---

# Storage & schema sketch (conceptual)

- **Tables/Collections**
    - `raw_sn_posts`, `raw_markets_polymarket`, `raw_markets_predyx`
    - `events_canonical` (one row per event, latest snapshot)
    - `event_links` (venue→event_id mappings with confidence)
    - `quotes` (time-series of normalized prices, depth)
    - `signals` (arbitrage detections with parameters, size, status)
    - `trades` / `fills` (if executing)

Partition by day; index on `deadline`, `entities[]`, and `title_vector` for fast matching.

---

# Ops & reliability

- **Backfill & replay:** nightly backfills of Polymarket/Predyx snapshots; keep 30–90 days for backtests.
- **Scrape hardening (Predyx):** rotating user agents, ETag/If-Modified-Since, and randomized intervals; fall back to cached data on transient failures.
- **Rate limits:** honor official limits (Polymarket), exponential backoff; cache decoded responses.

---

# Security & compliance

- **API keys & signatures** (Polymarket trading) in an HSM/secret manager; per-role credentials.
- **Geo-fencing and user consent** before enabling any automated execution.
- **Audit trail**: immutable logs of signals, decisions, orders.

---

# Why Stacker News in the loop?

Stacker News is Bitcoin-native and often surfaces **alpha** on crypto-relevant events (protocol upgrades, ETF flows, exchange incidents) that later appear as markets; using its GraphQL search to track entities/keywords gives **earlier detection** and **cleaner entity extraction** than generic web search. ([Stacker News](https://stacker.news/items/701535?utm_source=chatgpt.com))

---

# Known gaps & how we handle them

- **Predyx API immaturity:** start with scraping; design a clean interface to switch to an official API at first opportunity. ([predyx](https://beta.predyx.com/market?utm_source=chatgpt.com))
- **Resolution mismatches:** strict text/URL matching with human review queue.
- **Lightning vs USDC bankrolls:** treasury module keeps venue-local buffers; adds funding cost into edge threshold.
- **Jurisdictional constraints:** ship alert-only by default; require explicit enablement + config for execution.

---

# Quick source appendix

- **Stacker News GraphQL endpoint evidence** and community posts referencing `/api/graphql`. ([Stacker News](https://stacker.news/items/701535?utm_source=chatgpt.com))
- **Polymarket docs**: Gamma Markets API (`get-markets`), Data API (`/trades`), dev quickstart. ([docs.polymarket.com](https://docs.polymarket.com/developers/gamma-markets-api/get-markets?utm_source=chatgpt.com))
- **Predyx**: lightning-powered markets site & market list; independent LN node intel. ([predyx](https://beta.predyx.com/?utm_source=chatgpt.com), [thunderlytics.net](https://www.thunderlytics.net/node/03b465d6fcd7305c9fbfac523ec6c4a179756ad03e0400ed220ee303161bedbbf4/predyx-com-predict-the-future.html?utm_source=chatgpt.com))

---

If you want, I can tailor the entity/keyword watchlist for SN (e.g., BTC macro, AI releases, sports) and define exact alert thresholds (e.g., “edge > 2.5% after fees with ≥ $1k notional liquidity”).
