# CMOTS-Style Financial Market Data System — Complete API Specification

> Production-grade, vendor-equivalent Indian capital markets data platform.
> Replaces CMOTS by aggregating NSE, BSE, Screener, Trendlyne, Moneycontrol,
> AMFI, and Yahoo Finance into a normalized Supabase Postgres warehouse,
> exposed via a versioned REST API.

---

## 0. Conventions

| Item | Value |
|---|---|
| Base URL (prod) | `https://api.<your-domain>.com/v1` |
| Auth | Bearer JWT (Supabase) **or** `X-API-Key` header (per-tenant) |
| Response envelope | `{"data": ..., "meta": {...}, "error": null}` |
| Pagination | `?page=1&limit=100` (max 1000), cursor optional via `?after=<id>` |
| Timestamps | ISO-8601 UTC unless field name ends in `_ist` |
| Currency | INR; fields suffixed `_cr` = ₹ crores, `_lakh` = ₹ lakhs |
| Symbol convention | NSE symbol as primary key (`RELIANCE`); BSE code as numeric alias |
| Naming | kebab-case URLs · snake_case fields · plural collections |
| Versioning | URL-prefixed `/v1/...`; breaking changes bump to `/v2/...` |
| Rate limit | 600 req/min per key (configurable) |
| HTTP codes | 200 OK · 400 Bad Request · 401 Unauthorized · 404 Not Found · 429 Rate Limited · 503 Upstream Unavailable |

---

## 1. API Catalog (Master Index)

| # | Category | Report Name | Endpoint | Freq |
|---:|---|---|---|---|
| 1 | Master | Company Master | `/company-master` | EOD |
| 2 | Master | Company Profile | `/company/{symbol}/profile` | Weekly |
| 3 | Master | Listed Securities | `/listed-securities` | EOD |
| 4 | Master | Industry Classification | `/industry-classification` | Monthly |
| 5 | Master | Board of Directors | `/company/{symbol}/directors` | Quarterly |
| 6 | Master | Key Management | `/company/{symbol}/kmp` | Quarterly |
| 7 | Master | Subsidiaries | `/company/{symbol}/subsidiaries` | Annual |
| 8 | Master | Registered Office | `/company/{symbol}/registered-office` | Annual |
| 9 | Master | Registrar (RTA) | `/company/{symbol}/rta` | Annual |
| 10 | Master | Auditor | `/company/{symbol}/auditor` | Annual |
| 11 | Prices | Live Quote NSE | `/quote/nse/{symbol}` | Real-time |
| 12 | Prices | Live Quote BSE | `/quote/bse/{symbol}` | Real-time |
| 13 | Prices | Live Quote Combined | `/quote/{symbol}` | Real-time |
| 14 | Prices | Intraday OHLC 1-min | `/ohlc/intraday/{symbol}?interval=1m` | Real-time |
| 15 | Prices | Intraday OHLC 5-min | `/ohlc/intraday/{symbol}?interval=5m` | Real-time |
| 16 | Prices | Intraday OHLC 15-min | `/ohlc/intraday/{symbol}?interval=15m` | Real-time |
| 17 | Prices | Daily OHLC History | `/ohlc/daily/{symbol}` | EOD |
| 18 | Prices | Weekly OHLC | `/ohlc/weekly/{symbol}` | EOD (Fri) |
| 19 | Prices | Monthly OHLC | `/ohlc/monthly/{symbol}` | EOD (month-end) |
| 20 | Prices | 52-Week High/Low | `/52week/{symbol}` | EOD |
| 21 | Prices | All-Time High/Low | `/ath/{symbol}` | EOD |
| 22 | Prices | Adjusted Price | `/ohlc/adjusted/{symbol}` | EOD |
| 23 | Prices | Tick Snapshot | `/tick/{symbol}` | Real-time |
| 24 | Prices | Pre-Open Session | `/pre-open` | Daily 09:00 |
| 25 | Prices | Closing Settlement | `/closing/{symbol}` | EOD |
| 26 | Indices | Index Master | `/indices` | Monthly |
| 27 | Indices | Index Live Quote | `/index/{name}/quote` | Real-time |
| 28 | Indices | Index OHLC History | `/index/{name}/ohlc` | EOD |
| 29 | Indices | Index Constituents | `/index/{name}/constituents` | Monthly |
| 30 | Indices | Constituent Weights | `/index/{name}/weights` | Monthly |
| 31 | Market | Top Gainers | `/top-gainers` | Real-time |
| 32 | Market | Top Losers | `/top-losers` | Real-time |
| 33 | Market | Most Active by Volume | `/most-active/volume` | Real-time |
| 34 | Market | Most Active by Value | `/most-active/value` | Real-time |
| 35 | Market | Market Breadth | `/market-breadth` | Real-time |
| 36 | Actions | Corporate Actions | `/corporate-actions` | EOD |
| 37 | Actions | Dividend History | `/dividends/{symbol}` | EOD |
| 38 | Actions | Bonus Issues | `/bonus/{symbol}` | EOD |
| 39 | Actions | Stock Splits | `/splits/{symbol}` | EOD |
| 40 | Actions | Rights Issues | `/rights/{symbol}` | EOD |
| 41 | Actions | Buybacks | `/buybacks/{symbol}` | EOD |
| 42 | Actions | Mergers/Demergers | `/mergers/{symbol}` | EOD |
| 43 | Actions | Board Meetings | `/board-meetings` | Daily |
| 44 | Actions | AGM/EGM Calendar | `/agm-egm` | Daily |
| 45 | Actions | Announcements | `/announcements` | 15-min |
| 46 | F&O | F&O Symbol Master | `/fno/symbols` | Daily |
| 47 | F&O | Futures Quote | `/fno/futures/{symbol}` | Real-time |
| 48 | F&O | Options Chain | `/fno/options/{symbol}/chain` | Real-time |
| 49 | F&O | Option Greeks | `/fno/options/{symbol}/greeks` | Real-time |
| 50 | F&O | Open Interest | `/fno/oi/{symbol}` | Real-time |
| 51 | F&O | OI Buildup | `/fno/oi-buildup` | 5-min |
| 52 | F&O | Most Active F&O | `/fno/most-active` | Real-time |
| 53 | F&O | Put-Call Ratio | `/fno/pcr/{symbol}` | Real-time |
| 54 | F&O | F&O Lot Size | `/fno/lot-size` | Monthly |
| 55 | F&O | Block/Bulk Deals | `/block-deals` | EOD |
| 56 | Financials | Quarterly Results | `/financials/{symbol}/quarterly` | Quarterly |
| 57 | Financials | Annual P&L | `/financials/{symbol}/profit-loss` | Annual |
| 58 | Financials | Balance Sheet | `/financials/{symbol}/balance-sheet` | Annual |
| 59 | Financials | Cash Flow | `/financials/{symbol}/cash-flow` | Annual |
| 60 | Financials | Ratios Latest | `/ratios/{symbol}` | Quarterly |
| 61 | Financials | Ratios Historical | `/ratios/{symbol}/history` | Quarterly |
| 62 | Financials | Segment Reporting | `/financials/{symbol}/segments` | Quarterly |
| 63 | Financials | Standalone vs Consol | `/financials/{symbol}/comparison` | Quarterly |
| 64 | Financials | Director Remuneration | `/financials/{symbol}/director-pay` | Annual |
| 65 | Financials | Auditor Highlights | `/financials/{symbol}/auditor-report` | Annual |
| 66 | Ownership | Shareholding Pattern | `/shareholding/{symbol}` | Quarterly |
| 67 | Ownership | Promoter Holdings | `/shareholding/{symbol}/promoter` | Quarterly |
| 68 | Ownership | Public Breakdown | `/shareholding/{symbol}/public` | Quarterly |
| 69 | Ownership | FII Holdings | `/shareholding/{symbol}/fii` | Quarterly |
| 70 | Ownership | DII Holdings | `/shareholding/{symbol}/dii` | Quarterly |
| 71 | Ownership | MF Holdings in Stock | `/shareholding/{symbol}/mf-holdings` | Monthly |
| 72 | Ownership | Insider Trading (SAST) | `/insider-trading/{symbol}` | Daily |
| 73 | MF | AMC Master | `/mf/amcs` | Monthly |
| 74 | MF | Scheme Master | `/mf/schemes` | Weekly |
| 75 | MF | NAV Daily | `/mf/nav/{scheme_code}` | EOD |
| 76 | MF | NAV History | `/mf/nav/{scheme_code}/history` | EOD |
| 77 | MF | Portfolio Holdings | `/mf/{scheme_code}/holdings` | Monthly |
| 78 | MF | Sector Allocation | `/mf/{scheme_code}/sector-allocation` | Monthly |
| 79 | MF | Asset Allocation | `/mf/{scheme_code}/asset-allocation` | Monthly |
| 80 | MF | Top Holdings | `/mf/{scheme_code}/top-holdings` | Monthly |
| 81 | MF | Returns | `/mf/{scheme_code}/returns` | Daily |
| 82 | MF | Risk Metrics | `/mf/{scheme_code}/risk` | Daily |
| 83 | MF | Expense & AUM | `/mf/{scheme_code}/expense-aum` | Monthly |
| 84 | MF | Fund Manager | `/mf/{scheme_code}/manager` | Monthly |
| 85 | MF | Benchmark Comparison | `/mf/{scheme_code}/benchmark` | Daily |
| 86 | MF | SIP Returns | `/mf/{scheme_code}/sip-returns` | Daily |
| 87 | MF | IDCW History | `/mf/{scheme_code}/idcw` | EOD |
| 88 | News | Company News | `/news/{symbol}` | 10-min |
| 89 | News | News Archive | `/news/archive` | EOD |
| 90 | Research | Brokerage Recommendations | `/research/{symbol}/recommendations` | Daily |
| 91 | Research | Target Price Consensus | `/research/{symbol}/target` | Daily |
| 92 | Research | Analyst Coverage | `/research/{symbol}/coverage` | Daily |

---

## 2. API Detailed Specifications

### Section A — Company & Master Data

---

API Number: 1
Report Name: Company Master
API URL: `/v1/company-master`
Method: GET
Frequency: EOD
Updation Time: 23:30 IST
Primary Source: BSE master file
Fallback Source: NSE equity list, Screener
Storage Table: `stocks_master`

Inputs:
- `symbol` (query, optional) → NSE symbol
- `bse_code` (query, optional) → BSE numeric security code
- `isin` (query, optional) → 12-char ISIN
- `sector` (query, optional) → Filter by sector
- `is_active` (query, optional, default true) → Currently traded
- `page`, `limit` → pagination

Outputs:
- `company_id` (int) → Internal surrogate PK
- `company_name` (string) → Full registered company name
- `short_name` (string) → Trading/brand name
- `bse_code` (int) → BSE security code
- `nse_symbol` (string) → NSE trading symbol
- `isin` (string) → International Securities Identification Number
- `face_value` (float) → Face value per share, INR
- `sector` (string) → GICS-mapped sector
- `industry` (string) → 4-digit industry classification
- `sub_industry` (string) → Granular sub-industry
- `market_cap_cr` (float) → Market capitalization in ₹ crores
- `market_cap_category` (string) → Large/Mid/Small/Micro
- `listing_date_nse` (date) → First NSE listing date
- `listing_date_bse` (date) → First BSE listing date
- `incorporation_date` (date) → Date of incorporation
- `cin` (string) → Corporate Identification Number (MCA)
- `is_active` (bool) → Currently traded
- `is_in_nifty50` (bool) → Constituent flag
- `is_in_sensex` (bool) → Constituent flag
- `is_fno_enabled` (bool) → F&O eligible
- `updated_at` (timestamp) → Last warehouse update (UTC)

---

API Number: 2
Report Name: Company Profile
API URL: `/v1/company/{symbol}/profile`
Method: GET
Frequency: Weekly
Updation Time: Sunday 02:00 IST
Primary Source: Screener
Fallback Source: Moneycontrol, BSE
Storage Table: `company_profile`

Inputs:
- `symbol` (path, required) → NSE symbol

Outputs:
- `symbol` (string) → NSE symbol (PK)
- `business_description` (text) → Long-form business summary
- `business_segments` (json[]) → Array of `{name, revenue_pct}`
- `geographic_segments` (json[]) → Array of `{region, revenue_pct}`
- `key_products` (string[]) → Top product/service names
- `competitive_position` (string) → Market leadership notes
- `website` (string) → Corporate URL
- `email` (string) → Investor relations contact
- `phone` (string) → Main switchboard
- `employee_count` (int) → Latest disclosed headcount
- `founded_year` (int) → Year of incorporation
- `headquarters_city` (string) → Registered HQ city
- `headquarters_state` (string) → State
- `headquarters_country` (string) → Country (always "India")
- `chairperson` (string) → Current chairperson name
- `managing_director` (string) → Current MD/CEO name
- `updated_at` (timestamp) → Last refresh

---

API Number: 3
Report Name: Listed Securities
API URL: `/v1/listed-securities`
Method: GET
Frequency: EOD
Updation Time: 23:45 IST
Primary Source: NSE EQUITY_L.csv + BSE Equity.csv
Storage Table: `listed_securities`

Inputs:
- `exchange` (query, optional) → NSE / BSE / BOTH
- `series` (query, optional) → EQ / BE / BZ / SM (NSE) or A/B/T/Z (BSE)
- `as_of_date` (query, optional) → Snapshot date
- `page`, `limit`

Outputs:
- `security_id` (int) → PK
- `symbol` (string) → NSE symbol or BSE scrip-id
- `bse_code` (int) → BSE numeric code (nullable)
- `nse_symbol` (string) → NSE symbol (nullable)
- `isin` (string) → ISIN
- `series` (string) → Trading series
- `exchange` (string) → NSE / BSE
- `lot_size` (int) → Marketable lot
- `face_value` (float) → Face value
- `listing_date` (date) → Date of listing on that exchange
- `delisting_date` (date) → Date of delisting (null if active)
- `is_suspended` (bool) → Currently suspended
- `circuit_band_pct` (float) → Daily price band %
- `updated_at` (timestamp)

---

API Number: 4
Report Name: Industry Classification
API URL: `/v1/industry-classification`
Method: GET
Frequency: Monthly
Updation Time: 1st of month, 02:00 IST
Primary Source: NSE industry master + Screener
Storage Table: `industry_master`

Inputs:
- `level` (query, optional) → sector / industry / sub_industry
- `parent_code` (query, optional) → Parent classification

Outputs:
- `code` (string) → Classification code (PK)
- `name` (string) → Display name
- `level` (string) → sector / industry / sub_industry
- `parent_code` (string) → Parent code (null at sector level)
- `company_count` (int) → Number of listed companies
- `total_market_cap_cr` (float) → Aggregate market cap
- `description` (text) → Industry description
- `updated_at` (timestamp)

---

API Number: 5
Report Name: Board of Directors
API URL: `/v1/company/{symbol}/directors`
Method: GET
Frequency: Quarterly
Updation Time: Within 7 days of shareholding pattern release
Primary Source: BSE filings (Form MGT-7), Screener
Storage Table: `company_directors`

Inputs:
- `symbol` (path, required) → NSE symbol
- `active_only` (query, optional, default true) → Exclude resigned directors

Outputs:
- `director_id` (int) → PK
- `symbol` (string) → Company symbol
- `name` (string) → Full name
- `din` (string) → Director Identification Number (MCA)
- `designation` (string) → MD / Chairman / Whole-Time / Independent / Nominee
- `category` (string) → Executive / Non-Executive / Independent
- `appointment_date` (date) → Appointment to current role
- `cessation_date` (date) → Date of resignation/cessation (null if active)
- `age` (int) → Age in years
- `nationality` (string) → Nationality
- `other_directorships` (int) → Count of other listed boards
- `shareholding_count` (bigint) → Shares held in company
- `shareholding_pct` (float) → % of total equity
- `updated_at` (timestamp)

---

API Number: 6
Report Name: Key Management Personnel
API URL: `/v1/company/{symbol}/kmp`
Method: GET
Frequency: Quarterly
Updation Time: With board of directors update
Primary Source: BSE filings, Annual report
Storage Table: `company_kmp`

Inputs:
- `symbol` (path, required) → NSE symbol

Outputs:
- `kmp_id` (int) → PK
- `symbol` (string) → Company symbol
- `name` (string) → Full name
- `designation` (string) → CFO / Company Secretary / CTO etc
- `appointment_date` (date) → Appointment to current role
- `qualification` (string) → Educational qualification
- `experience_years` (int) → Years of experience
- `prior_company` (string) → Previous employer
- `updated_at` (timestamp)

---

API Number: 7
Report Name: Subsidiaries & Associates
API URL: `/v1/company/{symbol}/subsidiaries`
Method: GET
Frequency: Annual
Updation Time: Within 30 days of AGM
Primary Source: Annual report, BSE filings
Storage Table: `company_subsidiaries`

Inputs:
- `symbol` (path, required) → NSE symbol
- `relation_type` (query, optional) → subsidiary / joint_venture / associate

Outputs:
- `subsidiary_id` (int) → PK
- `parent_symbol` (string) → Parent company
- `subsidiary_name` (string) → Legal name
- `cin` (string) → Subsidiary CIN
- `relation_type` (string) → subsidiary / joint_venture / associate
- `ownership_pct` (float) → Parent's ownership %
- `country` (string) → Country of incorporation
- `business_activity` (string) → Primary business
- `is_listed` (bool) → Independently listed
- `consolidated` (bool) → Included in consolidated statements
- `incorporation_date` (date)
- `updated_at` (timestamp)

---

API Number: 8
Report Name: Registered Office
API URL: `/v1/company/{symbol}/registered-office`
Method: GET
Frequency: Annual
Updation Time: With profile refresh
Primary Source: MCA / annual report
Storage Table: `company_addresses`

Inputs:
- `symbol` (path, required) → NSE symbol

Outputs:
- `symbol` (string) → Company symbol
- `address_line_1` (string)
- `address_line_2` (string)
- `city` (string)
- `state` (string)
- `pincode` (string)
- `country` (string)
- `phone` (string)
- `fax` (string)
- `email` (string)
- `website` (string)
- `updated_at` (timestamp)

---

API Number: 9
Report Name: Registrar & Share Transfer Agent
API URL: `/v1/company/{symbol}/rta`
Method: GET
Frequency: Annual
Updation Time: With annual filings
Primary Source: BSE / Annual report
Storage Table: `company_rta`

Inputs:
- `symbol` (path, required)

Outputs:
- `symbol` (string)
- `rta_name` (string) → e.g. KFin Technologies, Link Intime
- `rta_address` (string)
- `rta_phone` (string)
- `rta_email` (string)
- `rta_website` (string)
- `effective_from` (date)
- `updated_at` (timestamp)

---

API Number: 10
Report Name: Auditor Information
API URL: `/v1/company/{symbol}/auditor`
Method: GET
Frequency: Annual
Updation Time: With annual filings
Primary Source: Annual report
Storage Table: `company_auditors`

Inputs:
- `symbol` (path, required)

Outputs:
- `auditor_id` (int) → PK
- `symbol` (string)
- `auditor_name` (string) → e.g. Deloitte, BSR & Co
- `firm_registration_no` (string) → ICAI registration
- `appointment_date` (date) → Appointed as statutory auditor
- `term_end_date` (date) → End of current term
- `audit_fee_lakh` (float) → Annual audit fee
- `is_current` (bool)
- `updated_at` (timestamp)

---

### Section B — Real-Time & Historical Prices

---

API Number: 11
Report Name: Live Quote NSE
API URL: `/v1/quote/nse/{symbol}`
Method: GET
Frequency: Real-time (5-sec poll)
Updation Time: During market hours 09:15–15:30 IST
Primary Source: NSE `/api/quote-equity` + `/api/equity-stockIndices`
Storage Table: `stock_prices` (latest snapshot served from cache)

Inputs:
- `symbol` (path, required) → NSE symbol

Outputs:
- `symbol` (string) → NSE symbol
- `company_name` (string)
- `ltp` (float) → Last traded price
- `change` (float) → Absolute change vs prev close
- `change_pct` (float) → Percentage change
- `open` (float) → Today's open
- `high` (float) → Day high
- `low` (float) → Day low
- `prev_close` (float) → Previous day close
- `volume` (bigint) → Total traded quantity
- `value_cr` (float) → Total traded value ₹ crores
- `vwap` (float) → Volume-weighted average price
- `bid_price` (float) → Best buy price
- `bid_qty` (int) → Best buy quantity
- `ask_price` (float) → Best sell price
- `ask_qty` (int) → Best sell quantity
- `circuit_upper` (float) → Upper circuit limit
- `circuit_lower` (float) → Lower circuit limit
- `52w_high` (float)
- `52w_low` (float)
- `face_value` (float)
- `exchange` (string) → "NSE"
- `last_trade_time_ist` (timestamp) → Last tick time
- `updated_at` (timestamp)

---

API Number: 12
Report Name: Live Quote BSE
API URL: `/v1/quote/bse/{symbol}`
Method: GET
Frequency: Real-time
Updation Time: During market hours
Primary Source: BSE
Storage Table: `stock_prices`

Inputs:
- `symbol` (path, required) → BSE code or symbol

Outputs:
- (Identical fields to Live Quote NSE, with `exchange="BSE"` and `bse_code`)

---

API Number: 13
Report Name: Live Quote Combined (best of NSE+BSE)
API URL: `/v1/quote/{symbol}`
Method: GET
Frequency: Real-time
Primary Source: NSE + BSE merged
Storage Table: derived view `v_quote_combined`

Inputs:
- `symbol` (path, required) → NSE symbol

Outputs:
- All fields from Live Quote NSE +
- `bse_ltp` (float) → BSE last price
- `nse_ltp` (float) → NSE last price
- `spread_bps` (float) → NSE-BSE spread in basis points
- `preferred_exchange` (string) → NSE/BSE based on volume

---

API Number: 14
Report Name: Intraday OHLC (1-minute)
API URL: `/v1/ohlc/intraday/{symbol}?interval=1m`
Method: GET
Frequency: Real-time, rolling 1-min bars
Updation Time: Every minute during market hours
Primary Source: NSE WebSocket / aggregated ticks
Storage Table: `stock_ohlc_intraday` (partitioned by date)

Inputs:
- `symbol` (path, required)
- `interval` (query, required) → 1m / 5m / 15m
- `from` (query, optional) → ISO datetime
- `to` (query, optional) → ISO datetime

Outputs:
- `symbol` (string)
- `timestamp_ist` (timestamp) → Bar open time
- `open` (float)
- `high` (float)
- `low` (float)
- `close` (float)
- `volume` (bigint)
- `vwap` (float)
- `trade_count` (int)
- `interval` (string)

---

API Number: 15
Report Name: Intraday OHLC (5-minute)
API URL: `/v1/ohlc/intraday/{symbol}?interval=5m`
(Same structure as #14 with `interval=5m`)

---

API Number: 16
Report Name: Intraday OHLC (15-minute)
API URL: `/v1/ohlc/intraday/{symbol}?interval=15m`
(Same structure as #14 with `interval=15m`)

---

API Number: 17
Report Name: Daily OHLC History
API URL: `/v1/ohlc/daily/{symbol}`
Method: GET
Frequency: EOD
Updation Time: 18:30 IST
Primary Source: NSE Bhavcopy (CM_DDMMYYYYbhav.csv)
Fallback: Yahoo Finance (`/v7/finance/download`)
Storage Table: `stock_ohlc_daily`

Inputs:
- `symbol` (path, required)
- `from` (query, optional) → YYYY-MM-DD
- `to` (query, optional) → YYYY-MM-DD
- `adjusted` (query, optional, default false) → Split/bonus adjusted

Outputs:
- `symbol` (string)
- `trade_date` (date)
- `open` (float)
- `high` (float)
- `low` (float)
- `close` (float)
- `volume` (bigint)
- `value_cr` (float)
- `delivery_qty` (bigint) → Quantity actually delivered
- `delivery_pct` (float) → Delivery as % of total volume
- `adjustment_factor` (float) → Cumulative split/bonus factor
- `prev_close` (float)
- `vwap` (float)
- `trade_count` (int)

---

API Number: 18
Report Name: Weekly OHLC
API URL: `/v1/ohlc/weekly/{symbol}`
Frequency: EOD (Friday close)
Storage Table: materialized view `mv_ohlc_weekly`

Inputs:
- `symbol`, `from`, `to`, `adjusted`

Outputs:
- `symbol`, `week_start_date` (date), `week_end_date` (date), OHLC, volume, value_cr

---

API Number: 19
Report Name: Monthly OHLC
API URL: `/v1/ohlc/monthly/{symbol}`
Frequency: EOD (month-end)
Storage Table: materialized view `mv_ohlc_monthly`

Inputs:
- `symbol`, `from`, `to`, `adjusted`

Outputs:
- `symbol`, `month_start_date`, `month_end_date`, OHLC, volume, value_cr

---

API Number: 20
Report Name: 52-Week High/Low
API URL: `/v1/52week/{symbol}`
Frequency: EOD
Primary Source: derived from `stock_ohlc_daily`
Storage Table: materialized view `mv_52week`

Inputs:
- `symbol` (path, required)

Outputs:
- `symbol` (string)
- `high_52w` (float) → 52-week high
- `high_52w_date` (date) → Date achieved
- `low_52w` (float)
- `low_52w_date` (date)
- `current_to_high_pct` (float) → % distance from 52w high
- `current_to_low_pct` (float)
- `updated_at` (timestamp)

---

API Number: 21
Report Name: All-Time High/Low
API URL: `/v1/ath/{symbol}`
Frequency: EOD
Storage Table: materialized view `mv_ath`

Inputs:
- `symbol`
- `adjusted` (query, optional) → Use adjusted prices

Outputs:
- `symbol`, `ath` (float), `ath_date` (date), `atl` (float), `atl_date` (date), `current_to_ath_pct` (float)

---

API Number: 22
Report Name: Adjusted Price
API URL: `/v1/ohlc/adjusted/{symbol}`
Frequency: EOD
Primary Source: derived from `stock_ohlc_daily` + `corporate_actions`
Storage Table: `stock_ohlc_adjusted`

Inputs:
- `symbol`, `from`, `to`

Outputs:
- `symbol`, `trade_date`, OHLC (adjusted), volume, `adjustment_factor`, `raw_close` (float)

---

API Number: 23
Report Name: Tick Snapshot (5 best bid/ask)
API URL: `/v1/tick/{symbol}`
Method: GET
Frequency: Real-time
Primary Source: NSE depth API
Storage Table: in-memory cache only (Redis 30s TTL)

Inputs:
- `symbol` (path, required)

Outputs:
- `symbol` (string)
- `timestamp_ist` (timestamp)
- `ltp` (float)
- `bids` (json[]) → Array of 5 `{price, qty, orders}`
- `asks` (json[]) → Array of 5 `{price, qty, orders}`
- `total_buy_qty` (bigint)
- `total_sell_qty` (bigint)

---

API Number: 24
Report Name: Pre-Open Session Data
API URL: `/v1/pre-open`
Method: GET
Frequency: Daily 09:00–09:08 IST
Primary Source: NSE pre-open API
Storage Table: `pre_open_session`

Inputs:
- `symbol` (query, optional) → Filter
- `index` (query, optional) → NIFTY50 / NIFTYBANK etc

Outputs:
- `symbol` (string)
- `iep` (float) → Indicative Equilibrium Price
- `change` (float)
- `change_pct` (float)
- `final_price` (float)
- `final_qty` (bigint)
- `total_buy_qty` (bigint)
- `total_sell_qty` (bigint)
- `atc_buy_qty` (bigint) → At-cost buy quantity
- `atc_sell_qty` (bigint)
- `session_date` (date)

---

API Number: 25
Report Name: Closing Settlement Price
API URL: `/v1/closing/{symbol}`
Method: GET
Frequency: EOD
Updation Time: 16:00 IST
Primary Source: NSE settlement file
Storage Table: `stock_closing` (overlaps stock_ohlc_daily but stores settlement-specific fields)

Inputs:
- `symbol` (path)
- `from`, `to`

Outputs:
- `symbol`, `trade_date`, `settlement_price` (float), `close_price` (float), `weighted_avg_price` (float), `total_traded_value_cr` (float)

---

### Section C — Indices & Market Stats

---

API Number: 26
Report Name: Index Master
API URL: `/v1/indices`
Method: GET
Frequency: Monthly
Primary Source: NSE indices list, BSE indices list
Storage Table: `indices_master`

Inputs:
- `exchange` (query, optional) → NSE / BSE
- `index_type` (query, optional) → broad / sectoral / thematic / strategy

Outputs:
- `index_id` (int) → PK
- `index_name` (string) → Display name
- `index_symbol` (string) → e.g. NIFTY 50, NIFTY BANK
- `exchange` (string)
- `index_type` (string) → broad / sectoral / thematic / strategy
- `base_date` (date) → Inception date
- `base_value` (float) → Index base value
- `constituent_count` (int)
- `calculation_methodology` (string) → free-float / equal-weight / etc
- `rebalance_frequency` (string) → semi-annual / quarterly
- `last_rebalance_date` (date)
- `is_tradeable` (bool) → Has F&O
- `updated_at` (timestamp)

---

API Number: 27
Report Name: Index Live Quote
API URL: `/v1/index/{name}/quote`
Method: GET
Frequency: Real-time
Primary Source: NSE
Storage Table: `index_quotes` (latest)

Inputs:
- `name` (path, required) → NIFTY50 / SENSEX etc

Outputs:
- `index_name` (string)
- `ltp` (float)
- `change` (float)
- `change_pct` (float)
- `open`, `high`, `low`, `prev_close` (float)
- `year_high` (float), `year_low` (float)
- `pe_ratio` (float) → Index P/E
- `pb_ratio` (float)
- `dividend_yield` (float)
- `advances` (int), `declines` (int), `unchanged` (int)
- `total_traded_value_cr` (float)
- `timestamp_ist` (timestamp)

---

API Number: 28
Report Name: Index OHLC History
API URL: `/v1/index/{name}/ohlc`
Frequency: EOD
Storage Table: `index_ohlc_daily`

Inputs:
- `name`, `from`, `to`, `interval` (daily/weekly/monthly)

Outputs:
- `index_name`, `trade_date`, OHLC, `volume`, `value_cr`, `turnover_cr`

---

API Number: 29
Report Name: Index Constituents
API URL: `/v1/index/{name}/constituents`
Frequency: Monthly
Primary Source: NSE indices file
Storage Table: `index_constituents`

Inputs:
- `name` (path)
- `as_of_date` (query, optional)

Outputs:
- `index_name` (string)
- `symbol` (string)
- `company_name` (string)
- `weight_pct` (float) → Weight in index
- `free_float_market_cap_cr` (float)
- `effective_from` (date)
- `effective_to` (date) → null if current

---

API Number: 30
Report Name: Constituent Weights History
API URL: `/v1/index/{name}/weights`
Frequency: Monthly (rebalance)
Storage Table: `index_weights_history`

Inputs:
- `name`, `from`, `to`

Outputs:
- `index_name`, `symbol`, `weight_pct`, `effective_date` (date)

---

API Number: 31
Report Name: Top Gainers
API URL: `/v1/top-gainers`
Method: GET
Frequency: Real-time
Primary Source: NSE `/api/live-analysis-variations?index=gainers`
Storage Table: `top_gainers_losers`

Inputs:
- `index` (query, optional, default NIFTY50) → NIFTY50 / NIFTYBANK / NIFTYNEXT50
- `limit` (query, optional, default 10)
- `series` (query, optional) → EQ / BE

Outputs:
- `rank` (int)
- `symbol` (string)
- `company_name` (string)
- `ltp` (float)
- `change` (float)
- `change_pct` (float)
- `volume` (bigint)
- `value_cr` (float)
- `index` (string)
- `timestamp_ist` (timestamp)

---

API Number: 32
Report Name: Top Losers
API URL: `/v1/top-losers`
(Same schema as Top Gainers with `change_pct` descending)

---

API Number: 33
Report Name: Most Active by Volume
API URL: `/v1/most-active/volume`
Frequency: Real-time
Storage Table: `most_active_volume`

Inputs:
- `index`, `limit`

Outputs:
- `rank`, `symbol`, `company_name`, `ltp`, `change_pct`, `volume`, `value_cr`, `timestamp_ist`

---

API Number: 34
Report Name: Most Active by Value
API URL: `/v1/most-active/value`
(Same schema, ranked by `value_cr` desc)

---

API Number: 35
Report Name: Market Breadth
API URL: `/v1/market-breadth`
Frequency: Real-time
Storage Table: `market_breadth`

Inputs:
- `exchange` (query, default NSE)
- `index` (query, optional)

Outputs:
- `exchange` (string)
- `index` (string) → e.g. ALL / NIFTY500
- `advances` (int)
- `declines` (int)
- `unchanged` (int)
- `advance_decline_ratio` (float)
- `52w_high_count` (int)
- `52w_low_count` (int)
- `upper_circuit_count` (int)
- `lower_circuit_count` (int)
- `total_traded` (int)
- `timestamp_ist` (timestamp)

---

### Section D — Corporate Actions & Announcements

---

API Number: 36
Report Name: Corporate Actions (all events)
API URL: `/v1/corporate-actions`
Method: GET
Frequency: EOD
Updation Time: 22:00 IST
Primary Source: NSE corporate actions feed, BSE corp actions
Storage Table: `corporate_actions`

Inputs:
- `symbol` (query, optional)
- `action_type` (query, optional) → DIVIDEND / BONUS / SPLIT / RIGHTS / BUYBACK / MERGER / DEMERGER / NAME_CHANGE
- `from_date`, `to_date`

Outputs:
- `action_id` (int) → PK
- `symbol` (string)
- `action_type` (string)
- `announcement_date` (date)
- `record_date` (date)
- `ex_date` (date)
- `payment_date` (date) → null if N/A
- `description` (text) → Full description
- `ratio` (string) → e.g. "1:1", "5:1"
- `dividend_per_share` (float) → null unless DIVIDEND
- `dividend_type` (string) → Interim / Final / Special
- `face_value_old` (float) → For splits
- `face_value_new` (float)
- `rights_price` (float) → For rights issues
- `buyback_price` (float)
- `buyback_size_cr` (float)
- `purpose` (string)
- `updated_at` (timestamp)

---

API Number: 37
Report Name: Dividend History
API URL: `/v1/dividends/{symbol}`
Frequency: EOD
Storage Table: `dividends`

Inputs:
- `symbol`, `from_date`, `to_date`

Outputs:
- `dividend_id` (int)
- `symbol`
- `announcement_date`, `ex_date`, `record_date`, `payment_date` (date)
- `dividend_type` (string) → Interim / Final / Special / DRIP
- `dividend_per_share` (float)
- `face_value` (float)
- `dividend_yield_at_announcement_pct` (float)
- `total_payout_cr` (float)
- `currency` (string, default "INR")

---

API Number: 38
Report Name: Bonus Issues
API URL: `/v1/bonus/{symbol}`
Frequency: EOD
Storage Table: `bonus_issues`

Inputs:
- `symbol`, `from_date`, `to_date`

Outputs:
- `bonus_id`, `symbol`, `announcement_date`, `ex_date`, `record_date`, `ratio` (string), `ratio_decimal` (float), `face_value` (float)

---

API Number: 39
Report Name: Stock Splits
API URL: `/v1/splits/{symbol}`
Frequency: EOD
Storage Table: `stock_splits`

Inputs:
- `symbol`, `from_date`, `to_date`

Outputs:
- `split_id`, `symbol`, `announcement_date`, `ex_date`, `record_date`, `old_face_value` (float), `new_face_value` (float), `split_ratio` (string)

---

API Number: 40
Report Name: Rights Issues
API URL: `/v1/rights/{symbol}`
Frequency: EOD
Storage Table: `rights_issues`

Inputs:
- `symbol`, `from_date`, `to_date`

Outputs:
- `rights_id`, `symbol`, `announcement_date`, `ex_date`, `record_date`, `issue_open_date`, `issue_close_date` (date)
- `ratio` (string), `rights_price` (float), `issue_size_cr` (float), `purpose` (string)

---

API Number: 41
Report Name: Buybacks
API URL: `/v1/buybacks/{symbol}`
Frequency: EOD
Storage Table: `buybacks`

Inputs:
- `symbol`, `from_date`, `to_date`

Outputs:
- `buyback_id`, `symbol`, `announcement_date`, `record_date`, `open_date`, `close_date` (date)
- `method` (string) → Tender / Open Market
- `buyback_price` (float), `total_size_cr` (float), `shares_offered` (bigint)
- `acceptance_ratio_pct` (float) → Final acceptance %
- `status` (string) → Announced / Open / Completed

---

API Number: 42
Report Name: Mergers & Demergers
API URL: `/v1/mergers/{symbol}`
Frequency: EOD
Storage Table: `mergers_demergers`

Inputs:
- `symbol`, `from_date`, `to_date`

Outputs:
- `event_id`, `symbol`, `event_type` (merger/demerger/amalgamation/scheme_of_arrangement)
- `counterparty_symbol`, `counterparty_name` (string)
- `announcement_date`, `effective_date`, `record_date` (date)
- `share_swap_ratio` (string) → e.g. "5:1"
- `status` (string) → Announced / Court_Approved / Effective
- `description` (text)

---

API Number: 43
Report Name: Board Meetings Calendar
API URL: `/v1/board-meetings`
Frequency: Daily
Storage Table: `board_meetings`

Inputs:
- `symbol` (query, optional)
- `from_date`, `to_date`
- `purpose` (query, optional) → results / dividend / fund_raise / other

Outputs:
- `meeting_id`, `symbol`, `meeting_date` (date), `purpose` (string), `description` (text), `announcement_date`, `source` (BSE/NSE)

---

API Number: 44
Report Name: AGM/EGM Calendar
API URL: `/v1/agm-egm`
Frequency: Daily
Storage Table: `agm_egm`

Inputs:
- `symbol`, `from_date`, `to_date`, `meeting_type` (AGM/EGM)

Outputs:
- `id`, `symbol`, `meeting_type`, `meeting_date`, `record_date`, `venue` (string), `agenda` (text), `voting_period_start`, `voting_period_end` (date)

---

API Number: 45
Report Name: Announcements
API URL: `/v1/announcements`
Method: GET
Frequency: 15-min
Primary Source: BSE filings, NSE corporate filings
Storage Table: `announcements`

Inputs:
- `symbol` (query, optional)
- `category` (query, optional) → financial / management_change / strategic / regulatory
- `from_datetime`, `to_datetime`
- `page`, `limit`

Outputs:
- `announcement_id` (int)
- `symbol`
- `bse_code` (int)
- `subject` (string) → One-line subject
- `category` (string)
- `sub_category` (string)
- `description` (text) → Full body
- `attachment_url` (string) → PDF link
- `submitted_at_ist` (timestamp)
- `disseminated_at_ist` (timestamp)
- `is_price_sensitive` (bool)
- `exchange` (string)
- `url_hash` (string) → Idempotency key

---

### Section E — F&O / Derivatives

---

API Number: 46
Report Name: F&O Symbol Master
API URL: `/v1/fno/symbols`
Method: GET
Frequency: Daily
Updation Time: 09:00 IST
Primary Source: NSE F&O master
Storage Table: `fno_symbols`

Inputs:
- `instrument_type` (query, optional) → FUTSTK / FUTIDX / OPTSTK / OPTIDX
- `underlying` (query, optional) → Underlying symbol

Outputs:
- `instrument_id` (int) → PK
- `instrument_type` (string)
- `underlying` (string) → e.g. RELIANCE, NIFTY
- `expiry_date` (date)
- `strike_price` (float) → null for futures
- `option_type` (string) → CE / PE / null for futures
- `lot_size` (int)
- `tick_size` (float)
- `is_active` (bool)
- `last_trade_date` (date)

---

API Number: 47
Report Name: Futures Quote
API URL: `/v1/fno/futures/{symbol}`
Frequency: Real-time
Storage Table: `fno_futures_quotes`

Inputs:
- `symbol` (path) → Underlying
- `expiry` (query, optional, default near-month) → YYYY-MM-DD

Outputs:
- `instrument_id`, `symbol`, `expiry_date`
- `ltp`, `change`, `change_pct`, `open`, `high`, `low`, `prev_close` (float)
- `volume` (bigint), `value_cr` (float)
- `open_interest` (bigint), `oi_change` (bigint), `oi_change_pct` (float)
- `bid_price`, `ask_price` (float), `bid_qty`, `ask_qty` (int)
- `basis` (float) → futures – spot
- `cost_of_carry_pct` (float)
- `timestamp_ist` (timestamp)

---

API Number: 48
Report Name: Options Chain
API URL: `/v1/fno/options/{symbol}/chain`
Frequency: Real-time
Storage Table: `fno_options_quotes`

Inputs:
- `symbol` (path)
- `expiry` (query, optional, default nearest)

Outputs:
- `symbol`, `expiry_date`, `spot_price` (float)
- `strikes` (json[]) — array of:
  - `strike_price` (float)
  - `ce_ltp`, `ce_change_pct`, `ce_oi`, `ce_oi_change`, `ce_volume`, `ce_iv` (float)
  - `pe_ltp`, `pe_change_pct`, `pe_oi`, `pe_oi_change`, `pe_volume`, `pe_iv` (float)
- `pcr` (float) → Total PE OI / total CE OI
- `max_pain_strike` (float)
- `timestamp_ist` (timestamp)

---

API Number: 49
Report Name: Option Greeks
API URL: `/v1/fno/options/{symbol}/greeks`
Frequency: Real-time
Primary Source: derived (Black-Scholes) from option chain
Storage Table: `fno_option_greeks`

Inputs:
- `symbol`, `expiry`, `strike`, `option_type`

Outputs:
- `instrument_id`, `delta`, `gamma`, `theta`, `vega`, `rho`, `iv`, `theoretical_price` (float)

---

API Number: 50
Report Name: Open Interest
API URL: `/v1/fno/oi/{symbol}`
Frequency: Real-time
Storage Table: `fno_oi_history`

Inputs:
- `symbol`, `expiry`, `from_datetime`, `to_datetime`

Outputs:
- `instrument_id`, `timestamp_ist`, `oi` (bigint), `oi_change` (bigint), `oi_change_pct` (float), `volume` (bigint), `price` (float)

---

API Number: 51
Report Name: OI Buildup
API URL: `/v1/fno/oi-buildup`
Frequency: 5-min
Storage Table: materialized view `mv_oi_buildup`

Inputs:
- `signal_type` (query) → long_buildup / short_buildup / long_unwinding / short_covering
- `instrument_type` (query) → FUT / OPT

Outputs:
- `symbol`, `signal_type`, `price_change_pct`, `oi_change_pct`, `volume`, `oi` (bigint), `timestamp_ist`

---

API Number: 52
Report Name: Most Active F&O
API URL: `/v1/fno/most-active`
Frequency: Real-time

Inputs:
- `metric` (query) → volume / value / oi
- `instrument_type` (query) → FUTSTK / OPTSTK / FUTIDX / OPTIDX
- `limit`

Outputs:
- `rank`, `symbol`, `expiry_date`, `ltp`, `change_pct`, `volume`, `value_cr`, `oi`, `oi_change_pct`

---

API Number: 53
Report Name: Put-Call Ratio
API URL: `/v1/fno/pcr/{symbol}`
Frequency: Real-time
Storage Table: `pcr_history`

Inputs:
- `symbol`, `expiry`, `from_datetime`, `to_datetime`

Outputs:
- `symbol`, `expiry_date`, `pcr_oi` (float), `pcr_volume` (float), `timestamp_ist`

---

API Number: 54
Report Name: F&O Lot Size
API URL: `/v1/fno/lot-size`
Frequency: Monthly (NSE revisions)
Storage Table: `fno_lot_size_history`

Inputs:
- `symbol`, `as_of_date`

Outputs:
- `symbol`, `lot_size` (int), `effective_from` (date), `effective_to` (date)

---

API Number: 55
Report Name: Block & Bulk Deals
API URL: `/v1/block-deals`
Frequency: EOD
Storage Table: `block_bulk_deals`

Inputs:
- `symbol` (query, optional)
- `deal_type` (query) → block / bulk
- `from_date`, `to_date`
- `client_name` (query, optional) → Match-substring search

Outputs:
- `deal_id` (int)
- `trade_date` (date)
- `symbol`
- `deal_type` (string) → block / bulk
- `client_name` (string)
- `action` (string) → BUY / SELL
- `quantity` (bigint)
- `price` (float)
- `value_cr` (float)
- `exchange` (string)

---

### Section F — Financial Statements

---

API Number: 56
Report Name: Quarterly Results
API URL: `/v1/financials/{symbol}/quarterly`
Method: GET
Frequency: Quarterly (within 45 days of quarter-end)
Primary Source: Screener, BSE financials, NSE results
Storage Table: `financials_quarterly`

Inputs:
- `symbol` (path)
- `from_period`, `to_period` → YYYY-Q1/Q2/Q3/Q4
- `consolidated` (query, optional, default true)

Outputs:
- `result_id` (int)
- `symbol`
- `period` (string) → e.g. "FY2025-Q3"
- `period_end_date` (date)
- `consolidated` (bool)
- `revenue_cr` (float) → Total revenue
- `other_income_cr` (float)
- `total_income_cr` (float)
- `raw_material_cost_cr` (float)
- `employee_cost_cr` (float)
- `finance_cost_cr` (float)
- `depreciation_cr` (float)
- `other_expense_cr` (float)
- `total_expense_cr` (float)
- `ebitda_cr` (float)
- `ebitda_margin_pct` (float)
- `ebit_cr` (float)
- `pbt_cr` (float) → Profit before tax
- `tax_cr` (float)
- `pat_cr` (float) → Profit after tax
- `net_profit_margin_pct` (float)
- `eps_basic` (float)
- `eps_diluted` (float)
- `interim_dividend_per_share` (float)
- `result_date` (date) → Date of board meeting
- `auditor_status` (string) → audited / unaudited / limited_review
- `yoy_revenue_growth_pct` (float)
- `yoy_pat_growth_pct` (float)
- `qoq_revenue_growth_pct` (float)
- `qoq_pat_growth_pct` (float)

---

API Number: 57
Report Name: Annual Profit & Loss
API URL: `/v1/financials/{symbol}/profit-loss`
Frequency: Annual (within 60 days of FY-end)
Storage Table: `financials_pl_annual`

Inputs:
- `symbol`, `from_fy`, `to_fy`, `consolidated`

Outputs:
- All fields from Quarterly Results, plus:
- `fy_year` (int) → e.g. 2025
- `dividend_per_share_total` (float)
- `book_value_per_share` (float)
- `cash_eps` (float) → PAT + Depreciation per share
- `effective_tax_rate_pct` (float)

---

API Number: 58
Report Name: Balance Sheet
API URL: `/v1/financials/{symbol}/balance-sheet`
Frequency: Annual
Storage Table: `financials_balance_sheet`

Inputs:
- `symbol`, `from_fy`, `to_fy`, `consolidated`

Outputs:
- `bs_id`, `symbol`, `fy_year`, `period_end_date`, `consolidated`
- **Equity & Liabilities:**
  - `equity_share_capital_cr` (float)
  - `reserves_surplus_cr` (float)
  - `total_shareholders_equity_cr` (float)
  - `minority_interest_cr` (float)
  - `long_term_debt_cr` (float)
  - `short_term_debt_cr` (float)
  - `total_debt_cr` (float)
  - `deferred_tax_liability_cr` (float)
  - `trade_payables_cr` (float)
  - `other_current_liabilities_cr` (float)
  - `total_liabilities_cr` (float)
- **Assets:**
  - `fixed_assets_cr` (float)
  - `capital_work_in_progress_cr` (float)
  - `intangible_assets_cr` (float)
  - `investments_long_term_cr` (float)
  - `investments_short_term_cr` (float)
  - `inventories_cr` (float)
  - `trade_receivables_cr` (float)
  - `cash_equivalents_cr` (float)
  - `other_current_assets_cr` (float)
  - `total_current_assets_cr` (float)
  - `total_non_current_assets_cr` (float)
  - `total_assets_cr` (float)
- `working_capital_cr` (float)
- `net_worth_cr` (float)
- `debt_to_equity` (float)

---

API Number: 59
Report Name: Cash Flow Statement
API URL: `/v1/financials/{symbol}/cash-flow`
Frequency: Annual
Storage Table: `financials_cash_flow`

Inputs:
- `symbol`, `from_fy`, `to_fy`, `consolidated`

Outputs:
- `cf_id`, `symbol`, `fy_year`, `period_end_date`, `consolidated`
- `cash_from_operations_cr` (float)
- `cash_from_investing_cr` (float)
- `cash_from_financing_cr` (float)
- `net_change_in_cash_cr` (float)
- `opening_cash_cr` (float)
- `closing_cash_cr` (float)
- `capex_cr` (float)
- `free_cash_flow_cr` (float)
- `dividend_paid_cr` (float)
- `interest_paid_cr` (float)
- `taxes_paid_cr` (float)

---

API Number: 60
Report Name: Financial Ratios (Latest)
API URL: `/v1/ratios/{symbol}`
Frequency: Quarterly (refresh after results)
Storage Table: `financial_ratios_latest`

Inputs:
- `symbol` (path)

Outputs:
- `symbol`
- `as_of_date` (date)
- **Valuation:**
  - `pe_ratio` (float)
  - `pb_ratio` (float)
  - `ps_ratio` (float)
  - `ev_to_ebitda` (float)
  - `peg_ratio` (float)
  - `dividend_yield_pct` (float)
- **Profitability:**
  - `roe_pct` (float)
  - `roce_pct` (float)
  - `roa_pct` (float)
  - `net_profit_margin_pct` (float)
  - `operating_margin_pct` (float)
  - `gross_margin_pct` (float)
- **Solvency:**
  - `debt_to_equity` (float)
  - `interest_coverage` (float)
  - `current_ratio` (float)
  - `quick_ratio` (float)
- **Efficiency:**
  - `inventory_turnover` (float)
  - `receivables_days` (int)
  - `payables_days` (int)
  - `cash_conversion_cycle` (int)
  - `asset_turnover` (float)
- **Growth (TTM):**
  - `revenue_growth_ttm_pct` (float)
  - `pat_growth_ttm_pct` (float)
  - `eps_growth_ttm_pct` (float)
- **Per-Share:**
  - `eps_ttm` (float)
  - `book_value_per_share` (float)
  - `cash_per_share` (float)
  - `revenue_per_share` (float)
- **Market:**
  - `market_cap_cr` (float)
  - `enterprise_value_cr` (float)
  - `beta_1y` (float)
- `updated_at` (timestamp)

---

API Number: 61
Report Name: Ratios History
API URL: `/v1/ratios/{symbol}/history`
Frequency: Quarterly
Storage Table: `financial_ratios_history`

Inputs:
- `symbol`, `from_period`, `to_period`, `metric` (query, optional)

Outputs:
- `symbol`, `period`, `period_end_date`, all ratio fields from #60

---

API Number: 62
Report Name: Segment Reporting
API URL: `/v1/financials/{symbol}/segments`
Frequency: Quarterly
Storage Table: `financials_segments`

Inputs:
- `symbol`, `period`, `segment_type` (business/geographic)

Outputs:
- `segment_id`, `symbol`, `period`, `period_end_date`
- `segment_name` (string), `segment_type` (string)
- `revenue_cr`, `revenue_pct`, `ebit_cr`, `ebit_margin_pct`, `capital_employed_cr`, `assets_cr` (float)

---

API Number: 63
Report Name: Standalone vs Consolidated
API URL: `/v1/financials/{symbol}/comparison`
Frequency: Quarterly
Storage Table: derived view

Inputs:
- `symbol`, `period`

Outputs:
- Side-by-side fields from `financials_quarterly` with `consolidated=true` and `consolidated=false`

---

API Number: 64
Report Name: Director Remuneration
API URL: `/v1/financials/{symbol}/director-pay`
Frequency: Annual
Storage Table: `director_remuneration`

Inputs:
- `symbol`, `fy_year`

Outputs:
- `id`, `symbol`, `fy_year`, `director_name`, `designation`
- `salary_lakh`, `commission_lakh`, `perquisites_lakh`, `total_remuneration_lakh` (float)
- `pay_to_median_ratio` (float)

---

API Number: 65
Report Name: Auditor Report Highlights
API URL: `/v1/financials/{symbol}/auditor-report`
Frequency: Annual
Storage Table: `auditor_reports`

Inputs:
- `symbol`, `fy_year`

Outputs:
- `id`, `symbol`, `fy_year`, `auditor_name`
- `opinion_type` (string) → unqualified / qualified / adverse / disclaimer
- `key_audit_matters` (json[]) → Array of {topic, description}
- `material_weakness_flag` (bool)
- `going_concern_flag` (bool)
- `report_date` (date)
- `attachment_url` (string)

---

### Section G — Shareholding & Ownership

---

API Number: 66
Report Name: Shareholding Pattern
API URL: `/v1/shareholding/{symbol}`
Method: GET
Frequency: Quarterly
Updation Time: Within 21 days of quarter-end
Primary Source: BSE / NSE shareholding filings
Storage Table: `shareholding_pattern`

Inputs:
- `symbol` (path)
- `from_period`, `to_period`

Outputs:
- `sp_id`, `symbol`, `period`, `period_end_date` (date)
- `promoter_holding_pct` (float)
- `promoter_pledged_pct` (float)
- `fii_holding_pct` (float)
- `dii_holding_pct` (float)
- `mf_holding_pct` (float)
- `insurance_holding_pct` (float)
- `government_holding_pct` (float)
- `retail_holding_pct` (float) → Individuals < ₹2 lakh
- `hni_holding_pct` (float) → Individuals > ₹2 lakh
- `bodies_corporate_pct` (float)
- `others_pct` (float)
- `total_shareholders` (int)
- `shares_outstanding` (bigint)

---

API Number: 67
Report Name: Promoter Holdings Detail
API URL: `/v1/shareholding/{symbol}/promoter`
Frequency: Quarterly
Storage Table: `promoter_holdings`

Inputs:
- `symbol`, `period`

Outputs:
- `id`, `symbol`, `period`, `promoter_name`, `promoter_category` (Individual/HUF/Body Corporate)
- `shares_held` (bigint), `holding_pct` (float)
- `pledged_shares` (bigint), `pledged_pct` (float)
- `encumbered_shares` (bigint)
- `change_from_prev_period_pct` (float)

---

API Number: 68
Report Name: Public Shareholding Breakdown
API URL: `/v1/shareholding/{symbol}/public`
Frequency: Quarterly
Storage Table: `public_shareholding_breakdown`

Inputs:
- `symbol`, `period`

Outputs:
- `symbol`, `period`
- `category` (string) → MF / FII / Insurance / Banks / NBFC / Retail / HNI / Bodies Corporate / Trusts / Foreign Bodies / NRI
- `shares_held` (bigint), `holding_pct` (float), `shareholder_count` (int)

---

API Number: 69
Report Name: FII Holdings
API URL: `/v1/shareholding/{symbol}/fii`
Frequency: Quarterly (top holders); FPI flow daily
Primary Source: Trendlyne, NSE FPI data
Storage Table: `fii_holdings`

Inputs:
- `symbol`, `from_period`, `to_period`

Outputs:
- `id`, `symbol`, `period`
- `fii_name` (string) → e.g. "Vanguard Total International"
- `category` (string) → Cat I / Cat II
- `shares_held` (bigint), `holding_pct` (float)
- `market_value_cr` (float)
- `change_from_prev_period_shares` (bigint)
- `change_from_prev_period_pct` (float)

---

API Number: 70
Report Name: DII Holdings
API URL: `/v1/shareholding/{symbol}/dii`
Frequency: Quarterly
Primary Source: Trendlyne, Moneycontrol, AMFI portfolios
Storage Table: `dii_holdings`

Inputs:
- `symbol`, `from_period`, `to_period`

Outputs:
- `id`, `symbol`, `period`
- `dii_name` (string) → e.g. "HDFC Mutual Fund", "LIC of India"
- `dii_category` (string) → MF / Insurance / Bank / NBFC / Pension
- `shares_held` (bigint), `holding_pct` (float), `market_value_cr` (float)
- `change_from_prev_period_pct` (float)

---

API Number: 71
Report Name: Mutual Fund Holdings in Stock
API URL: `/v1/shareholding/{symbol}/mf-holdings`
Frequency: Monthly (portfolio disclosures)
Primary Source: AMFI monthly portfolios + Trendlyne
Storage Table: `stock_mf_holdings`

Inputs:
- `symbol` (path)
- `as_of_month` (query, optional) → YYYY-MM
- `top_n` (query, optional, default 50)

Outputs:
- `id`, `symbol`, `as_of_month` (date)
- `scheme_code` (string), `scheme_name` (string), `amc_name` (string)
- `shares_held` (bigint), `holding_pct_of_scheme` (float), `holding_pct_of_stock` (float)
- `market_value_cr` (float)
- `month_over_month_change_shares` (bigint)
- `is_new_addition` (bool), `is_complete_exit` (bool)

---

API Number: 72
Report Name: Insider Trading (SAST)
API URL: `/v1/insider-trading/{symbol}`
Frequency: Daily
Primary Source: BSE SAST disclosures
Storage Table: `insider_trades`

Inputs:
- `symbol`, `from_date`, `to_date`, `transaction_type` (buy/sell)

Outputs:
- `trade_id`, `symbol`, `acquirer_name`, `acquirer_category` (Promoter/KMP/Director/Connected)
- `transaction_type` (BUY/SELL/PLEDGE/INVOKED)
- `transaction_date`, `intimation_date` (date)
- `quantity` (bigint), `value_cr` (float), `avg_price` (float)
- `pre_transaction_holding_pct` (float), `post_transaction_holding_pct` (float)
- `mode` (string) → Market Purchase / Off Market / Bonus / Gift / ESOP

---

### Section H — Mutual Funds

---

API Number: 73
Report Name: AMC Master
API URL: `/v1/mf/amcs`
Frequency: Monthly
Primary Source: AMFI
Storage Table: `mf_amcs`

Inputs:
- `is_active` (query, default true)

Outputs:
- `amc_id` (int)
- `amc_name` (string) → e.g. "HDFC Asset Management Co. Ltd"
- `short_code` (string) → e.g. "HDFC"
- `registration_no` (string) → SEBI registration
- `incorporation_date` (date)
- `aum_cr` (float) → Latest disclosed AUM
- `scheme_count` (int) → Active scheme count
- `website` (string), `email` (string), `phone` (string)
- `is_active` (bool)
- `updated_at` (timestamp)

---

API Number: 74
Report Name: Scheme Master
API URL: `/v1/mf/schemes`
Frequency: Weekly
Primary Source: AMFI scheme codes file
Storage Table: `mf_schemes`

Inputs:
- `amc_id` (query, optional)
- `category` (query, optional) → Equity / Debt / Hybrid / Solution / Other
- `sub_category` (query, optional) → Large Cap / Mid Cap / Liquid / etc
- `is_direct` (query, optional) → Direct vs Regular plan
- `is_active`, `page`, `limit`

Outputs:
- `scheme_id` (int)
- `scheme_code` (string) → AMFI code
- `scheme_name` (string)
- `amc_id`, `amc_name`
- `isin_growth` (string), `isin_payout` (string), `isin_reinvest` (string)
- `category` (string), `sub_category` (string)
- `plan_type` (string) → Direct / Regular
- `option_type` (string) → Growth / IDCW / IDCW-Reinvestment
- `launch_date` (date)
- `closure_date` (date) → null if open-ended
- `min_investment_amount` (float)
- `min_sip_amount` (float)
- `exit_load_pct` (float)
- `exit_load_period_days` (int)
- `benchmark_index` (string)
- `riskometer` (string) → Low / Low to Moderate / Moderate / Moderately High / High / Very High
- `is_active` (bool)

---

API Number: 75
Report Name: NAV Daily
API URL: `/v1/mf/nav/{scheme_code}`
Frequency: EOD
Updation Time: 23:00 IST
Primary Source: AMFI NAVAll.txt
Storage Table: `mutual_funds` (latest) / `mf_nav_history`

Inputs:
- `scheme_code` (path)
- `nav_date` (query, optional, default latest)

Outputs:
- `scheme_code`, `scheme_name`, `amc_name`
- `nav` (float)
- `nav_date` (date)
- `change_1d` (float)
- `change_1d_pct` (float)
- `repurchase_price` (float)
- `sale_price` (float)
- `last_updated` (timestamp)

---

API Number: 76
Report Name: NAV History
API URL: `/v1/mf/nav/{scheme_code}/history`
Frequency: EOD
Storage Table: `mf_nav_history`

Inputs:
- `scheme_code`, `from_date`, `to_date`

Outputs:
- `scheme_code`, `nav_date`, `nav`, `change_pct` (vs prev day)

---

API Number: 77
Report Name: Portfolio Holdings
API URL: `/v1/mf/{scheme_code}/holdings`
Frequency: Monthly (mandatory by SEBI)
Primary Source: AMC monthly portfolio disclosures + Trendlyne
Storage Table: `mf_holdings`

Inputs:
- `scheme_code` (path)
- `as_of_month` (query, optional, default latest)
- `top_n` (query, optional)

Outputs:
- `holding_id`, `scheme_code`, `as_of_month` (date)
- `instrument_name` (string)
- `instrument_type` (string) → Equity / Debt / Cash / Derivative / REIT
- `isin` (string)
- `symbol` (string) → For equity holdings
- `sector` (string) → For equity
- `rating` (string) → For debt (AAA/AA+/etc)
- `shares_held` (bigint), `face_value_cr` (float)
- `market_value_cr` (float)
- `weight_pct` (float) → % of scheme AUM

---

API Number: 78
Report Name: Sector Allocation
API URL: `/v1/mf/{scheme_code}/sector-allocation`
Frequency: Monthly
Storage Table: materialized view from `mf_holdings`

Inputs:
- `scheme_code`, `as_of_month`

Outputs:
- `scheme_code`, `as_of_month`, `sector`, `weight_pct`, `market_value_cr`, `holdings_count`

---

API Number: 79
Report Name: Asset Allocation
API URL: `/v1/mf/{scheme_code}/asset-allocation`
Frequency: Monthly

Inputs:
- `scheme_code`, `as_of_month`

Outputs:
- `scheme_code`, `as_of_month`
- `equity_pct`, `debt_pct`, `cash_pct`, `derivative_pct`, `reit_pct`, `commodity_pct` (float)
- `large_cap_pct`, `mid_cap_pct`, `small_cap_pct` (float) → For equity funds
- `sovereign_pct`, `aaa_pct`, `aa_pct`, `below_aa_pct` (float) → For debt funds
- `modified_duration_years`, `ytm_pct`, `avg_maturity_years` (float) → For debt funds

---

API Number: 80
Report Name: Top Holdings
API URL: `/v1/mf/{scheme_code}/top-holdings`
Frequency: Monthly

Inputs:
- `scheme_code`, `as_of_month`, `n` (default 10)

Outputs:
- Top-N rows from #77 ordered by `weight_pct` desc

---

API Number: 81
Report Name: Returns
API URL: `/v1/mf/{scheme_code}/returns`
Frequency: Daily
Primary Source: derived from `mf_nav_history`
Storage Table: materialized view `mv_mf_returns`

Inputs:
- `scheme_code`, `as_of_date`

Outputs:
- `scheme_code`, `as_of_date`
- `returns_1d_pct`, `returns_1w_pct`, `returns_1m_pct`, `returns_3m_pct`, `returns_6m_pct` (float)
- `returns_1y_pct`, `returns_3y_cagr_pct`, `returns_5y_cagr_pct`, `returns_10y_cagr_pct` (float)
- `returns_since_inception_cagr_pct` (float)
- `returns_ytd_pct` (float)

---

API Number: 82
Report Name: Risk Metrics
API URL: `/v1/mf/{scheme_code}/risk`
Frequency: Daily (calculated on rolling 3Y data)
Storage Table: materialized view `mv_mf_risk`

Inputs:
- `scheme_code`, `as_of_date`, `lookback_years` (default 3)

Outputs:
- `scheme_code`, `as_of_date`
- `standard_deviation_pct` (float) → Annualized volatility
- `beta` (float) → vs benchmark
- `alpha_pct` (float) → Jensen's alpha
- `sharpe_ratio` (float)
- `sortino_ratio` (float)
- `treynor_ratio` (float)
- `r_squared` (float)
- `information_ratio` (float)
- `max_drawdown_pct` (float)
- `max_drawdown_date` (date)
- `tracking_error_pct` (float)

---

API Number: 83
Report Name: Expense & AUM
API URL: `/v1/mf/{scheme_code}/expense-aum`
Frequency: Monthly
Storage Table: `mf_expense_aum`

Inputs:
- `scheme_code`, `from_month`, `to_month`

Outputs:
- `scheme_code`, `as_of_month`
- `aum_cr` (float)
- `total_expense_ratio_pct` (float)
- `management_fee_pct` (float)
- `other_expenses_pct` (float)
- `gst_pct` (float)
- `folio_count` (int)
- `unitholders_count` (int)

---

API Number: 84
Report Name: Fund Manager
API URL: `/v1/mf/{scheme_code}/manager`
Frequency: Monthly
Storage Table: `mf_fund_managers`

Inputs:
- `scheme_code`

Outputs:
- `id`, `scheme_code`, `manager_name`, `designation`
- `managing_since` (date)
- `experience_years` (int)
- `qualification` (string)
- `other_schemes_managed` (int)
- `total_aum_managed_cr` (float)

---

API Number: 85
Report Name: Benchmark Comparison
API URL: `/v1/mf/{scheme_code}/benchmark`
Frequency: Daily
Storage Table: materialized view

Inputs:
- `scheme_code`, `as_of_date`, `lookback_period`

Outputs:
- `scheme_code`, `benchmark_index`
- `scheme_return_pct`, `benchmark_return_pct` (float)
- `outperformance_pct` (float)
- `lookback_period` (string) → 1y / 3y / 5y / since_inception

---

API Number: 86
Report Name: SIP Returns
API URL: `/v1/mf/{scheme_code}/sip-returns`
Frequency: Daily

Inputs:
- `scheme_code`, `sip_amount` (default 5000), `frequency` (monthly/quarterly), `from_date`, `to_date`

Outputs:
- `scheme_code`, `sip_amount`, `frequency`, `from_date`, `to_date`
- `total_invested` (float)
- `current_value` (float)
- `absolute_return_pct` (float)
- `xirr_pct` (float) → Annualized

---

API Number: 87
Report Name: IDCW (Dividend) History
API URL: `/v1/mf/{scheme_code}/idcw`
Frequency: EOD
Storage Table: `mf_idcw_history`

Inputs:
- `scheme_code`, `from_date`, `to_date`

Outputs:
- `id`, `scheme_code`, `announcement_date`, `record_date`, `payment_date`
- `idcw_per_unit` (float)
- `idcw_type` (string) → Income / Capital Gains
- `face_value` (float)

---

### Section I — News, Research, Recommendations

---

API Number: 88
Report Name: Company News
API URL: `/v1/news/{symbol}`
Method: GET
Frequency: 10-min
Primary Source: Moneycontrol, BSE/NSE announcements
Storage Table: `company_news`

Inputs:
- `symbol` (path, optional — omit for market-wide)
- `from_datetime`, `to_datetime`
- `category` (query, optional) → results / management / regulatory / m_a / general
- `sentiment` (query, optional) → positive / neutral / negative
- `min_relevance_score` (query, optional, default 0.5)
- `page`, `limit`

Outputs:
- `news_id`
- `symbol`
- `headline` (string)
- `summary` (text)
- `body` (text)
- `source` (string) → moneycontrol / bse / nse / etc
- `published_at_ist` (timestamp)
- `url` (string)
- `url_hash` (string) → Idempotency key
- `category` (string)
- `sentiment` (string) → positive / neutral / negative
- `sentiment_score` (float) → -1 to +1
- `relevance_score` (float) → 0 to 1
- `tags` (string[])

---

API Number: 89
Report Name: News Archive
API URL: `/v1/news/archive`
Frequency: EOD
(Same fields as #88 but with historical filtering)

---

API Number: 90
Report Name: Brokerage Recommendations
API URL: `/v1/research/{symbol}/recommendations`
Method: GET
Frequency: Daily
Primary Source: Moneycontrol, Trendlyne
Storage Table: `brokerage_recommendations`

Inputs:
- `symbol` (path)
- `from_date`, `to_date`
- `broker` (query, optional)
- `rating` (query, optional) → BUY / SELL / HOLD / ADD / REDUCE

Outputs:
- `rec_id`, `symbol`, `broker_name`
- `analyst_name` (string)
- `rating` (string) → BUY / SELL / HOLD / ADD / REDUCE / NEUTRAL
- `target_price` (float)
- `previous_target_price` (float)
- `target_change_pct` (float)
- `current_price_at_rec` (float)
- `upside_pct` (float)
- `recommendation_date` (date)
- `report_url` (string)
- `summary` (text)

---

API Number: 91
Report Name: Target Price Consensus
API URL: `/v1/research/{symbol}/target`
Frequency: Daily
Storage Table: materialized view from `brokerage_recommendations`

Inputs:
- `symbol`

Outputs:
- `symbol`
- `as_of_date`
- `consensus_rating` (string) → Strong Buy / Buy / Hold / Sell / Strong Sell
- `consensus_target_price` (float) → Mean
- `target_price_high` (float)
- `target_price_low` (float)
- `target_price_median` (float)
- `analyst_count` (int)
- `buy_count`, `hold_count`, `sell_count` (int)
- `upside_to_consensus_pct` (float)
- `last_30d_target_change_pct` (float)

---

API Number: 92
Report Name: Analyst Coverage
API URL: `/v1/research/{symbol}/coverage`
Frequency: Daily
Storage Table: materialized view

Inputs:
- `symbol`

Outputs:
- `symbol`
- `analyst_count_total` (int)
- `analyst_count_active_90d` (int)
- `brokers` (json[]) → Array of {broker_name, latest_rating, latest_target, latest_date}
- `coverage_started_date` (date)

---

## 3. Database Schema (Supabase Postgres DDL)

```sql
-- ═══════════════════════════════════════════════════════════════════
--  CMOTS-Equivalent Warehouse — normalized for 100M+ row scale
-- ═══════════════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────────────────────────
-- 1. MASTER DATA
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE stocks_master (
    company_id          BIGSERIAL PRIMARY KEY,
    nse_symbol          TEXT UNIQUE,
    bse_code            INTEGER UNIQUE,
    isin                CHAR(12) UNIQUE,
    company_name        TEXT NOT NULL,
    short_name          TEXT,
    cin                 CHAR(21),
    face_value          NUMERIC(10,2),
    sector              TEXT,
    industry            TEXT,
    sub_industry        TEXT,
    market_cap_cr       NUMERIC(18,2),
    market_cap_category TEXT CHECK (market_cap_category IN ('Large','Mid','Small','Micro')),
    listing_date_nse    DATE,
    listing_date_bse    DATE,
    incorporation_date  DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    is_in_nifty50       BOOLEAN DEFAULT FALSE,
    is_in_sensex        BOOLEAN DEFAULT FALSE,
    is_fno_enabled      BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_stocks_sector ON stocks_master(sector) WHERE is_active;
CREATE INDEX idx_stocks_isin ON stocks_master(isin);
CREATE INDEX idx_stocks_mcap ON stocks_master(market_cap_cr DESC) WHERE is_active;

CREATE TABLE company_profile (
    symbol              TEXT PRIMARY KEY REFERENCES stocks_master(nse_symbol),
    business_description TEXT,
    business_segments   JSONB,
    geographic_segments JSONB,
    key_products        TEXT[],
    website             TEXT,
    email               TEXT,
    phone               TEXT,
    employee_count      INTEGER,
    founded_year        SMALLINT,
    headquarters_city   TEXT,
    headquarters_state  TEXT,
    headquarters_country TEXT DEFAULT 'India',
    chairperson         TEXT,
    managing_director   TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE listed_securities (
    security_id     BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    bse_code        INTEGER,
    nse_symbol      TEXT,
    isin            CHAR(12),
    series          TEXT,
    exchange        TEXT NOT NULL CHECK (exchange IN ('NSE','BSE')),
    lot_size        INTEGER,
    face_value      NUMERIC(10,2),
    listing_date    DATE,
    delisting_date  DATE,
    is_suspended    BOOLEAN DEFAULT FALSE,
    circuit_band_pct NUMERIC(5,2),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (exchange, symbol, series)
);

CREATE TABLE industry_master (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    level           TEXT CHECK (level IN ('sector','industry','sub_industry')),
    parent_code     TEXT REFERENCES industry_master(code),
    description     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE company_directors (
    director_id     BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    name            TEXT NOT NULL,
    din             CHAR(8),
    designation     TEXT,
    category        TEXT,
    appointment_date DATE,
    cessation_date  DATE,
    age             SMALLINT,
    nationality     TEXT,
    other_directorships SMALLINT,
    shareholding_count BIGINT,
    shareholding_pct NUMERIC(8,4),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, din, appointment_date)
);
CREATE INDEX idx_directors_symbol ON company_directors(symbol) WHERE cessation_date IS NULL;

CREATE TABLE company_kmp (
    kmp_id          BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    name            TEXT NOT NULL,
    designation     TEXT,
    appointment_date DATE,
    qualification   TEXT,
    experience_years SMALLINT,
    prior_company   TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE company_subsidiaries (
    subsidiary_id   BIGSERIAL PRIMARY KEY,
    parent_symbol   TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    subsidiary_name TEXT NOT NULL,
    cin             CHAR(21),
    relation_type   TEXT CHECK (relation_type IN ('subsidiary','joint_venture','associate')),
    ownership_pct   NUMERIC(7,4),
    country         TEXT,
    business_activity TEXT,
    is_listed       BOOLEAN DEFAULT FALSE,
    consolidated    BOOLEAN DEFAULT TRUE,
    incorporation_date DATE,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (parent_symbol, subsidiary_name)
);

CREATE TABLE company_addresses (
    symbol          TEXT PRIMARY KEY REFERENCES stocks_master(nse_symbol),
    address_line_1  TEXT,
    address_line_2  TEXT,
    city            TEXT,
    state           TEXT,
    pincode         TEXT,
    country         TEXT DEFAULT 'India',
    phone           TEXT,
    fax             TEXT,
    email           TEXT,
    website         TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE company_rta (
    symbol          TEXT PRIMARY KEY REFERENCES stocks_master(nse_symbol),
    rta_name        TEXT,
    rta_address     TEXT,
    rta_phone       TEXT,
    rta_email       TEXT,
    rta_website     TEXT,
    effective_from  DATE,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE company_auditors (
    auditor_id      BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    auditor_name    TEXT NOT NULL,
    firm_registration_no TEXT,
    appointment_date DATE,
    term_end_date   DATE,
    audit_fee_lakh  NUMERIC(12,2),
    is_current      BOOLEAN DEFAULT TRUE,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, firm_registration_no, appointment_date)
);

-- ──────────────────────────────────────────────────────────────────
-- 2. PRICES (partitioned for scale)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE stock_prices (
    id                  BIGSERIAL,
    symbol              TEXT NOT NULL,
    exchange            TEXT NOT NULL,
    ltp                 NUMERIC(14,4),
    change_pct          NUMERIC(10,4),
    open                NUMERIC(14,4),
    high                NUMERIC(14,4),
    low                 NUMERIC(14,4),
    close               NUMERIC(14,4),
    prev_close          NUMERIC(14,4),
    volume              BIGINT,
    value_cr            NUMERIC(18,4),
    vwap                NUMERIC(14,4),
    bid_price           NUMERIC(14,4),
    bid_qty             INTEGER,
    ask_price           NUMERIC(14,4),
    ask_qty             INTEGER,
    timestamp           TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (symbol, exchange, timestamp)
) PARTITION BY RANGE (timestamp);
-- Create monthly partitions in deploy script:
--   CREATE TABLE stock_prices_2026_05 PARTITION OF stock_prices
--     FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE INDEX idx_prices_symbol_ts ON stock_prices (symbol, timestamp DESC);

CREATE TABLE stock_ohlc_daily (
    symbol              TEXT NOT NULL,
    trade_date          DATE NOT NULL,
    open                NUMERIC(14,4),
    high                NUMERIC(14,4),
    low                 NUMERIC(14,4),
    close               NUMERIC(14,4),
    volume              BIGINT,
    value_cr            NUMERIC(18,4),
    delivery_qty        BIGINT,
    delivery_pct        NUMERIC(7,4),
    adjustment_factor   NUMERIC(12,8) DEFAULT 1.0,
    prev_close          NUMERIC(14,4),
    vwap                NUMERIC(14,4),
    trade_count         INTEGER,
    PRIMARY KEY (symbol, trade_date)
);
CREATE INDEX idx_ohlc_date ON stock_ohlc_daily USING BRIN (trade_date);

CREATE TABLE stock_ohlc_intraday (
    symbol              TEXT NOT NULL,
    interval            TEXT NOT NULL CHECK (interval IN ('1m','5m','15m','30m','1h')),
    timestamp           TIMESTAMPTZ NOT NULL,
    open                NUMERIC(14,4),
    high                NUMERIC(14,4),
    low                 NUMERIC(14,4),
    close               NUMERIC(14,4),
    volume              BIGINT,
    vwap                NUMERIC(14,4),
    trade_count         INTEGER,
    PRIMARY KEY (symbol, interval, timestamp)
) PARTITION BY RANGE (timestamp);

CREATE TABLE pre_open_session (
    symbol              TEXT NOT NULL,
    session_date        DATE NOT NULL,
    iep                 NUMERIC(14,4),
    change              NUMERIC(14,4),
    change_pct          NUMERIC(10,4),
    final_price         NUMERIC(14,4),
    final_qty           BIGINT,
    total_buy_qty       BIGINT,
    total_sell_qty      BIGINT,
    atc_buy_qty         BIGINT,
    atc_sell_qty        BIGINT,
    PRIMARY KEY (symbol, session_date)
);

-- ──────────────────────────────────────────────────────────────────
-- 3. INDICES
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE indices_master (
    index_id            SERIAL PRIMARY KEY,
    index_name          TEXT NOT NULL UNIQUE,
    index_symbol        TEXT,
    exchange            TEXT,
    index_type          TEXT CHECK (index_type IN ('broad','sectoral','thematic','strategy')),
    base_date           DATE,
    base_value          NUMERIC(14,4),
    constituent_count   SMALLINT,
    calculation_methodology TEXT,
    rebalance_frequency TEXT,
    last_rebalance_date DATE,
    is_tradeable        BOOLEAN DEFAULT FALSE,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE index_ohlc_daily (
    index_name          TEXT NOT NULL,
    trade_date          DATE NOT NULL,
    open                NUMERIC(14,4),
    high                NUMERIC(14,4),
    low                 NUMERIC(14,4),
    close               NUMERIC(14,4),
    volume              BIGINT,
    value_cr            NUMERIC(18,4),
    pe_ratio            NUMERIC(8,2),
    pb_ratio            NUMERIC(8,2),
    dividend_yield      NUMERIC(7,4),
    PRIMARY KEY (index_name, trade_date)
);

CREATE TABLE index_constituents (
    id                  BIGSERIAL PRIMARY KEY,
    index_name          TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    weight_pct          NUMERIC(8,4),
    free_float_market_cap_cr NUMERIC(18,2),
    effective_from      DATE NOT NULL,
    effective_to        DATE,
    UNIQUE (index_name, symbol, effective_from)
);
CREATE INDEX idx_constituents_active ON index_constituents (index_name) WHERE effective_to IS NULL;

CREATE TABLE market_indices (
    id                  BIGSERIAL PRIMARY KEY,
    index_name          TEXT NOT NULL,
    open                NUMERIC(14,4),
    high                NUMERIC(14,4),
    low                 NUMERIC(14,4),
    close               NUMERIC(14,4),
    change_pct          NUMERIC(10,4),
    advances            INTEGER,
    declines            INTEGER,
    timestamp           TIMESTAMPTZ NOT NULL,
    UNIQUE (index_name, timestamp)
);

CREATE TABLE top_gainers_losers (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    type                TEXT NOT NULL CHECK (type IN ('gainer','losers')),
    ltp                 NUMERIC(14,4),
    change_pct          NUMERIC(10,4),
    volume              BIGINT,
    index               TEXT,
    timestamp           TIMESTAMPTZ NOT NULL,
    UNIQUE (symbol, type, timestamp)
);

CREATE TABLE market_breadth (
    id                  BIGSERIAL PRIMARY KEY,
    exchange            TEXT NOT NULL,
    index               TEXT,
    advances            INTEGER,
    declines            INTEGER,
    unchanged           INTEGER,
    advance_decline_ratio NUMERIC(8,4),
    high_52w_count      INTEGER,
    low_52w_count       INTEGER,
    upper_circuit_count INTEGER,
    lower_circuit_count INTEGER,
    timestamp           TIMESTAMPTZ NOT NULL,
    UNIQUE (exchange, index, timestamp)
);

-- ──────────────────────────────────────────────────────────────────
-- 4. CORPORATE ACTIONS
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE corporate_actions (
    action_id           BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    action_type         TEXT NOT NULL CHECK (action_type IN (
        'DIVIDEND','BONUS','SPLIT','RIGHTS','BUYBACK','MERGER','DEMERGER','NAME_CHANGE','FACE_VALUE_CHANGE'
    )),
    announcement_date   DATE,
    record_date         DATE,
    ex_date             DATE,
    payment_date        DATE,
    description         TEXT,
    ratio               TEXT,
    dividend_per_share  NUMERIC(10,4),
    dividend_type       TEXT,
    face_value_old      NUMERIC(10,2),
    face_value_new      NUMERIC(10,2),
    rights_price        NUMERIC(14,4),
    buyback_price       NUMERIC(14,4),
    buyback_size_cr     NUMERIC(14,2),
    purpose             TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, action_type, ex_date)
);
CREATE INDEX idx_corp_actions_ex_date ON corporate_actions (ex_date DESC);
CREATE INDEX idx_corp_actions_symbol_type ON corporate_actions (symbol, action_type);

CREATE TABLE announcements (
    announcement_id     BIGSERIAL PRIMARY KEY,
    symbol              TEXT,
    bse_code            INTEGER,
    subject             TEXT,
    category            TEXT,
    sub_category        TEXT,
    description         TEXT,
    attachment_url      TEXT,
    submitted_at_ist    TIMESTAMP,
    disseminated_at_ist TIMESTAMP,
    is_price_sensitive  BOOLEAN DEFAULT FALSE,
    exchange            TEXT,
    url_hash            CHAR(64) NOT NULL UNIQUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ann_symbol_time ON announcements (symbol, disseminated_at_ist DESC);

CREATE TABLE board_meetings (
    meeting_id          BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    meeting_date        DATE NOT NULL,
    purpose             TEXT,
    description         TEXT,
    announcement_date   DATE,
    source              TEXT,
    UNIQUE (symbol, meeting_date, purpose)
);

CREATE TABLE agm_egm (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    meeting_type        TEXT CHECK (meeting_type IN ('AGM','EGM')),
    meeting_date        DATE NOT NULL,
    record_date         DATE,
    venue               TEXT,
    agenda              TEXT,
    voting_period_start DATE,
    voting_period_end   DATE,
    UNIQUE (symbol, meeting_type, meeting_date)
);

-- ──────────────────────────────────────────────────────────────────
-- 5. F&O / DERIVATIVES
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE fno_symbols (
    instrument_id       BIGSERIAL PRIMARY KEY,
    instrument_type     TEXT NOT NULL,
    underlying          TEXT NOT NULL,
    expiry_date         DATE NOT NULL,
    strike_price        NUMERIC(14,4),
    option_type         TEXT CHECK (option_type IN ('CE','PE')),
    lot_size            INTEGER,
    tick_size           NUMERIC(8,4),
    is_active           BOOLEAN DEFAULT TRUE,
    UNIQUE (instrument_type, underlying, expiry_date, strike_price, option_type)
);
CREATE INDEX idx_fno_underlying_expiry ON fno_symbols (underlying, expiry_date);

CREATE TABLE fno_quotes (
    instrument_id       BIGINT NOT NULL REFERENCES fno_symbols(instrument_id),
    timestamp           TIMESTAMPTZ NOT NULL,
    ltp                 NUMERIC(14,4),
    open                NUMERIC(14,4),
    high                NUMERIC(14,4),
    low                 NUMERIC(14,4),
    volume              BIGINT,
    value_cr            NUMERIC(18,4),
    open_interest       BIGINT,
    oi_change           BIGINT,
    iv                  NUMERIC(10,4),
    PRIMARY KEY (instrument_id, timestamp)
) PARTITION BY RANGE (timestamp);

CREATE TABLE fno_option_greeks (
    instrument_id       BIGINT NOT NULL REFERENCES fno_symbols(instrument_id),
    timestamp           TIMESTAMPTZ NOT NULL,
    delta               NUMERIC(10,6),
    gamma               NUMERIC(10,8),
    theta               NUMERIC(12,6),
    vega                NUMERIC(12,6),
    rho                 NUMERIC(12,6),
    iv                  NUMERIC(10,4),
    theoretical_price   NUMERIC(14,4),
    PRIMARY KEY (instrument_id, timestamp)
);

CREATE TABLE block_bulk_deals (
    deal_id             BIGSERIAL PRIMARY KEY,
    trade_date          DATE NOT NULL,
    symbol              TEXT NOT NULL,
    deal_type           TEXT CHECK (deal_type IN ('block','bulk')),
    client_name         TEXT,
    action              TEXT CHECK (action IN ('BUY','SELL')),
    quantity            BIGINT,
    price               NUMERIC(14,4),
    value_cr            NUMERIC(18,4),
    exchange            TEXT,
    UNIQUE (trade_date, symbol, client_name, action, quantity, price)
);
CREATE INDEX idx_deals_symbol_date ON block_bulk_deals (symbol, trade_date DESC);

-- ──────────────────────────────────────────────────────────────────
-- 6. FINANCIAL STATEMENTS
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE financials_quarterly (
    result_id           BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    period              TEXT NOT NULL,
    period_end_date     DATE NOT NULL,
    consolidated        BOOLEAN NOT NULL DEFAULT TRUE,
    revenue_cr          NUMERIC(18,2),
    other_income_cr     NUMERIC(18,2),
    total_income_cr     NUMERIC(18,2),
    raw_material_cost_cr NUMERIC(18,2),
    employee_cost_cr    NUMERIC(18,2),
    finance_cost_cr     NUMERIC(18,2),
    depreciation_cr     NUMERIC(18,2),
    other_expense_cr    NUMERIC(18,2),
    total_expense_cr    NUMERIC(18,2),
    ebitda_cr           NUMERIC(18,2),
    ebitda_margin_pct   NUMERIC(8,4),
    ebit_cr             NUMERIC(18,2),
    pbt_cr              NUMERIC(18,2),
    tax_cr              NUMERIC(18,2),
    pat_cr              NUMERIC(18,2),
    net_profit_margin_pct NUMERIC(8,4),
    eps_basic           NUMERIC(12,4),
    eps_diluted         NUMERIC(12,4),
    auditor_status      TEXT,
    result_date         DATE,
    yoy_revenue_growth_pct NUMERIC(10,4),
    yoy_pat_growth_pct  NUMERIC(10,4),
    qoq_revenue_growth_pct NUMERIC(10,4),
    qoq_pat_growth_pct  NUMERIC(10,4),
    raw_payload         JSONB,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, period, consolidated)
);

CREATE TABLE financials_balance_sheet (
    bs_id                       BIGSERIAL PRIMARY KEY,
    symbol                      TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    fy_year                     SMALLINT NOT NULL,
    period_end_date             DATE,
    consolidated                BOOLEAN NOT NULL DEFAULT TRUE,
    equity_share_capital_cr     NUMERIC(18,2),
    reserves_surplus_cr         NUMERIC(18,2),
    total_shareholders_equity_cr NUMERIC(18,2),
    minority_interest_cr        NUMERIC(18,2),
    long_term_debt_cr           NUMERIC(18,2),
    short_term_debt_cr          NUMERIC(18,2),
    total_debt_cr               NUMERIC(18,2),
    deferred_tax_liability_cr   NUMERIC(18,2),
    trade_payables_cr           NUMERIC(18,2),
    other_current_liabilities_cr NUMERIC(18,2),
    total_liabilities_cr        NUMERIC(18,2),
    fixed_assets_cr             NUMERIC(18,2),
    capital_work_in_progress_cr NUMERIC(18,2),
    intangible_assets_cr        NUMERIC(18,2),
    investments_long_term_cr    NUMERIC(18,2),
    investments_short_term_cr   NUMERIC(18,2),
    inventories_cr              NUMERIC(18,2),
    trade_receivables_cr        NUMERIC(18,2),
    cash_equivalents_cr         NUMERIC(18,2),
    other_current_assets_cr     NUMERIC(18,2),
    total_current_assets_cr     NUMERIC(18,2),
    total_non_current_assets_cr NUMERIC(18,2),
    total_assets_cr             NUMERIC(18,2),
    working_capital_cr          NUMERIC(18,2),
    net_worth_cr                NUMERIC(18,2),
    debt_to_equity              NUMERIC(10,4),
    raw_payload                 JSONB,
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, fy_year, consolidated)
);

CREATE TABLE financials_cash_flow (
    cf_id               BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    fy_year             SMALLINT NOT NULL,
    period_end_date     DATE,
    consolidated        BOOLEAN NOT NULL DEFAULT TRUE,
    cash_from_operations_cr NUMERIC(18,2),
    cash_from_investing_cr  NUMERIC(18,2),
    cash_from_financing_cr  NUMERIC(18,2),
    net_change_in_cash_cr   NUMERIC(18,2),
    opening_cash_cr     NUMERIC(18,2),
    closing_cash_cr     NUMERIC(18,2),
    capex_cr            NUMERIC(18,2),
    free_cash_flow_cr   NUMERIC(18,2),
    dividend_paid_cr    NUMERIC(18,2),
    interest_paid_cr    NUMERIC(18,2),
    taxes_paid_cr       NUMERIC(18,2),
    raw_payload         JSONB,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, fy_year, consolidated)
);

CREATE TABLE financial_ratios (
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    as_of_date          DATE NOT NULL,
    pe_ratio            NUMERIC(10,4),
    pb_ratio            NUMERIC(10,4),
    ps_ratio            NUMERIC(10,4),
    ev_to_ebitda        NUMERIC(10,4),
    peg_ratio           NUMERIC(10,4),
    dividend_yield_pct  NUMERIC(8,4),
    roe_pct             NUMERIC(10,4),
    roce_pct            NUMERIC(10,4),
    roa_pct             NUMERIC(10,4),
    net_profit_margin_pct NUMERIC(10,4),
    operating_margin_pct NUMERIC(10,4),
    gross_margin_pct    NUMERIC(10,4),
    debt_to_equity      NUMERIC(10,4),
    interest_coverage   NUMERIC(10,4),
    current_ratio       NUMERIC(10,4),
    quick_ratio         NUMERIC(10,4),
    inventory_turnover  NUMERIC(10,4),
    receivables_days    INTEGER,
    payables_days       INTEGER,
    cash_conversion_cycle INTEGER,
    asset_turnover      NUMERIC(10,4),
    revenue_growth_ttm_pct NUMERIC(10,4),
    pat_growth_ttm_pct  NUMERIC(10,4),
    eps_growth_ttm_pct  NUMERIC(10,4),
    eps_ttm             NUMERIC(12,4),
    book_value_per_share NUMERIC(14,4),
    cash_per_share      NUMERIC(14,4),
    revenue_per_share   NUMERIC(14,4),
    market_cap_cr       NUMERIC(18,2),
    enterprise_value_cr NUMERIC(18,2),
    beta_1y             NUMERIC(8,4),
    PRIMARY KEY (symbol, as_of_date)
);

CREATE TABLE financials_segments (
    segment_id          BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    period              TEXT NOT NULL,
    period_end_date     DATE,
    segment_name        TEXT NOT NULL,
    segment_type        TEXT CHECK (segment_type IN ('business','geographic')),
    revenue_cr          NUMERIC(18,2),
    revenue_pct         NUMERIC(8,4),
    ebit_cr             NUMERIC(18,2),
    ebit_margin_pct     NUMERIC(8,4),
    capital_employed_cr NUMERIC(18,2),
    assets_cr           NUMERIC(18,2),
    UNIQUE (symbol, period, segment_type, segment_name)
);

-- ──────────────────────────────────────────────────────────────────
-- 7. OWNERSHIP & SHAREHOLDING
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE shareholding_pattern (
    sp_id               BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    period              TEXT NOT NULL,
    period_end_date     DATE,
    promoter_holding_pct NUMERIC(8,4),
    promoter_pledged_pct NUMERIC(8,4),
    fii_holding_pct     NUMERIC(8,4),
    dii_holding_pct     NUMERIC(8,4),
    mf_holding_pct      NUMERIC(8,4),
    insurance_holding_pct NUMERIC(8,4),
    government_holding_pct NUMERIC(8,4),
    retail_holding_pct  NUMERIC(8,4),
    hni_holding_pct     NUMERIC(8,4),
    bodies_corporate_pct NUMERIC(8,4),
    others_pct          NUMERIC(8,4),
    total_shareholders  INTEGER,
    shares_outstanding  BIGINT,
    UNIQUE (symbol, period)
);

CREATE TABLE promoter_holdings (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    period              TEXT NOT NULL,
    promoter_name       TEXT NOT NULL,
    promoter_category   TEXT,
    shares_held         BIGINT,
    holding_pct         NUMERIC(8,4),
    pledged_shares      BIGINT,
    pledged_pct         NUMERIC(8,4),
    encumbered_shares   BIGINT,
    change_from_prev_period_pct NUMERIC(10,4),
    UNIQUE (symbol, period, promoter_name)
);

CREATE TABLE fii_holdings (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    period              TEXT NOT NULL,
    fii_name            TEXT,
    category            TEXT,
    shares_held         BIGINT,
    holding_pct         NUMERIC(8,4),
    market_value_cr     NUMERIC(18,2),
    change_from_prev_period_shares BIGINT,
    change_from_prev_period_pct NUMERIC(10,4),
    UNIQUE (symbol, period, fii_name)
);

CREATE TABLE dii_holdings (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    period              TEXT NOT NULL,
    dii_name            TEXT,
    dii_category        TEXT,
    shares_held         BIGINT,
    holding_pct         NUMERIC(8,4),
    market_value_cr     NUMERIC(18,2),
    change_from_prev_period_pct NUMERIC(10,4),
    UNIQUE (symbol, period, dii_name)
);

CREATE TABLE stock_mf_holdings (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    as_of_month         DATE NOT NULL,
    scheme_code         TEXT NOT NULL,
    scheme_name         TEXT,
    amc_name            TEXT,
    shares_held         BIGINT,
    holding_pct_of_scheme NUMERIC(8,4),
    holding_pct_of_stock NUMERIC(8,4),
    market_value_cr     NUMERIC(18,2),
    month_over_month_change_shares BIGINT,
    is_new_addition     BOOLEAN DEFAULT FALSE,
    is_complete_exit    BOOLEAN DEFAULT FALSE,
    UNIQUE (symbol, as_of_month, scheme_code)
);
CREATE INDEX idx_stockmf_symbol_month ON stock_mf_holdings (symbol, as_of_month DESC);

CREATE TABLE insider_trades (
    trade_id            BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    acquirer_name       TEXT,
    acquirer_category   TEXT,
    transaction_type    TEXT,
    transaction_date    DATE,
    intimation_date     DATE,
    quantity            BIGINT,
    value_cr            NUMERIC(18,4),
    avg_price           NUMERIC(14,4),
    pre_transaction_holding_pct NUMERIC(8,4),
    post_transaction_holding_pct NUMERIC(8,4),
    mode                TEXT,
    UNIQUE (symbol, acquirer_name, transaction_date, quantity, transaction_type)
);

-- ──────────────────────────────────────────────────────────────────
-- 8. MUTUAL FUNDS
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE mf_amcs (
    amc_id              SERIAL PRIMARY KEY,
    amc_name            TEXT NOT NULL UNIQUE,
    short_code          TEXT,
    registration_no     TEXT,
    incorporation_date  DATE,
    aum_cr              NUMERIC(18,2),
    scheme_count        SMALLINT,
    website             TEXT,
    email               TEXT,
    phone               TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE mf_schemes (
    scheme_id           BIGSERIAL PRIMARY KEY,
    scheme_code         TEXT NOT NULL UNIQUE,
    scheme_name         TEXT NOT NULL,
    amc_id              INTEGER REFERENCES mf_amcs(amc_id),
    amc_name            TEXT,
    isin_growth         CHAR(12),
    isin_payout         CHAR(12),
    isin_reinvest       CHAR(12),
    category            TEXT,
    sub_category        TEXT,
    plan_type           TEXT CHECK (plan_type IN ('Direct','Regular')),
    option_type         TEXT,
    launch_date         DATE,
    closure_date        DATE,
    min_investment_amount NUMERIC(12,2),
    min_sip_amount      NUMERIC(12,2),
    exit_load_pct       NUMERIC(6,4),
    exit_load_period_days INTEGER,
    benchmark_index     TEXT,
    riskometer          TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_schemes_amc_category ON mf_schemes (amc_id, category);

CREATE TABLE mf_nav_history (
    scheme_code         TEXT NOT NULL,
    nav_date            DATE NOT NULL,
    nav                 NUMERIC(14,4) NOT NULL,
    repurchase_price    NUMERIC(14,4),
    sale_price          NUMERIC(14,4),
    PRIMARY KEY (scheme_code, nav_date)
) PARTITION BY RANGE (nav_date);
-- Yearly partitions:
--   CREATE TABLE mf_nav_history_2026 PARTITION OF mf_nav_history
--     FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE mutual_funds (
    id                  BIGSERIAL PRIMARY KEY,
    scheme_code         TEXT NOT NULL,
    scheme_name         TEXT,
    isin_payout         CHAR(12),
    isin_growth         CHAR(12),
    amc_name            TEXT,
    category            TEXT,
    sub_category        TEXT,
    nav                 NUMERIC(14,4),
    nav_date            DATE NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (scheme_code, nav_date)
);

CREATE TABLE mf_holdings (
    holding_id          BIGSERIAL PRIMARY KEY,
    scheme_code         TEXT NOT NULL,
    as_of_month         DATE NOT NULL,
    instrument_name     TEXT,
    instrument_type     TEXT,
    isin                CHAR(12),
    symbol              TEXT,
    sector              TEXT,
    rating              TEXT,
    shares_held         BIGINT,
    face_value_cr       NUMERIC(18,4),
    market_value_cr     NUMERIC(18,4),
    weight_pct          NUMERIC(8,4),
    UNIQUE (scheme_code, as_of_month, isin, instrument_name)
);
CREATE INDEX idx_mfh_scheme_month ON mf_holdings (scheme_code, as_of_month DESC);
CREATE INDEX idx_mfh_isin_month ON mf_holdings (isin, as_of_month DESC) WHERE isin IS NOT NULL;

CREATE TABLE mf_expense_aum (
    scheme_code         TEXT NOT NULL,
    as_of_month         DATE NOT NULL,
    aum_cr              NUMERIC(18,2),
    total_expense_ratio_pct NUMERIC(6,4),
    management_fee_pct  NUMERIC(6,4),
    other_expenses_pct  NUMERIC(6,4),
    gst_pct             NUMERIC(6,4),
    folio_count         INTEGER,
    unitholders_count   INTEGER,
    PRIMARY KEY (scheme_code, as_of_month)
);

CREATE TABLE mf_fund_managers (
    id                  BIGSERIAL PRIMARY KEY,
    scheme_code         TEXT NOT NULL,
    manager_name        TEXT NOT NULL,
    designation         TEXT,
    managing_since      DATE,
    experience_years    SMALLINT,
    qualification       TEXT,
    other_schemes_managed INTEGER,
    total_aum_managed_cr NUMERIC(18,2),
    is_current          BOOLEAN DEFAULT TRUE,
    UNIQUE (scheme_code, manager_name, managing_since)
);

CREATE TABLE mf_idcw_history (
    id                  BIGSERIAL PRIMARY KEY,
    scheme_code         TEXT NOT NULL,
    announcement_date   DATE,
    record_date         DATE,
    payment_date        DATE,
    idcw_per_unit       NUMERIC(10,4),
    idcw_type           TEXT,
    face_value          NUMERIC(10,2),
    UNIQUE (scheme_code, record_date, idcw_type)
);

-- ──────────────────────────────────────────────────────────────────
-- 9. NEWS & RESEARCH
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE company_news (
    news_id             BIGSERIAL PRIMARY KEY,
    symbol              TEXT,
    headline            TEXT NOT NULL,
    summary             TEXT,
    body                TEXT,
    source              TEXT,
    published_at_ist    TIMESTAMP,
    url                 TEXT,
    url_hash            CHAR(64) NOT NULL UNIQUE,
    category            TEXT,
    sentiment           TEXT,
    sentiment_score     NUMERIC(5,4),
    relevance_score     NUMERIC(5,4),
    tags                TEXT[],
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_news_symbol_time ON company_news (symbol, published_at_ist DESC) WHERE symbol IS NOT NULL;

CREATE TABLE brokerage_recommendations (
    rec_id              BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL REFERENCES stocks_master(nse_symbol),
    broker_name         TEXT NOT NULL,
    analyst_name        TEXT,
    rating              TEXT,
    target_price        NUMERIC(14,4),
    previous_target_price NUMERIC(14,4),
    target_change_pct   NUMERIC(10,4),
    current_price_at_rec NUMERIC(14,4),
    upside_pct          NUMERIC(10,4),
    recommendation_date DATE NOT NULL,
    report_url          TEXT,
    summary             TEXT,
    UNIQUE (symbol, broker_name, recommendation_date, target_price)
);

-- ──────────────────────────────────────────────────────────────────
-- 10. OPERATIONAL (ETL bookkeeping)
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE scraper_run_log (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT NOT NULL,
    task                TEXT,
    status              TEXT,
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    duration_seconds    NUMERIC(10,4),
    records_inserted    INTEGER,
    records_skipped     INTEGER,
    error_msg           TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_run_log_source_time ON scraper_run_log (source, started_at DESC);

CREATE TABLE scraper_checkpoints (
    source              TEXT PRIMARY KEY,
    last_run_at         TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    last_checkpoint     JSONB
);

CREATE TABLE data_quality_log (
    id                  BIGSERIAL PRIMARY KEY,
    table_name          TEXT,
    check_name          TEXT,
    severity            TEXT CHECK (severity IN ('info','warning','error','critical')),
    failed_count        INTEGER,
    sample_keys         JSONB,
    checked_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────────
-- 11. ROW-LEVEL SECURITY (Supabase)
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE stocks_master ENABLE ROW LEVEL SECURITY;
CREATE POLICY public_read_stocks ON stocks_master FOR SELECT TO anon, authenticated USING (true);

ALTER TABLE stock_ohlc_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY public_read_ohlc ON stock_ohlc_daily FOR SELECT TO anon, authenticated USING (true);

ALTER TABLE mutual_funds ENABLE ROW LEVEL SECURITY;
CREATE POLICY public_read_mf ON mutual_funds FOR SELECT TO anon, authenticated USING (true);

-- Operational tables: service-role-only (no policy = no anon/authenticated access)
ALTER TABLE scraper_run_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_checkpoints ENABLE ROW LEVEL SECURITY;

-- Repeat for all read-public market tables.

-- ──────────────────────────────────────────────────────────────────
-- 12. MATERIALIZED VIEWS
-- ──────────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW mv_52week AS
SELECT
    symbol,
    MAX(high) FILTER (WHERE trade_date >= CURRENT_DATE - INTERVAL '364 days') AS high_52w,
    (ARRAY_AGG(trade_date ORDER BY high DESC))[1] FILTER (
        WHERE trade_date >= CURRENT_DATE - INTERVAL '364 days'
    ) AS high_52w_date,
    MIN(low) FILTER (WHERE trade_date >= CURRENT_DATE - INTERVAL '364 days') AS low_52w,
    (ARRAY_AGG(trade_date ORDER BY low ASC))[1] FILTER (
        WHERE trade_date >= CURRENT_DATE - INTERVAL '364 days'
    ) AS low_52w_date
FROM stock_ohlc_daily
GROUP BY symbol;
CREATE UNIQUE INDEX ON mv_52week (symbol);

CREATE MATERIALIZED VIEW mv_mf_returns AS
WITH nav_snapshots AS (
    SELECT
        scheme_code,
        nav AS current_nav,
        nav_date AS as_of_date,
        LAG(nav, 5)   OVER w AS nav_1w,
        LAG(nav, 22)  OVER w AS nav_1m,
        LAG(nav, 66)  OVER w AS nav_3m,
        LAG(nav, 132) OVER w AS nav_6m,
        LAG(nav, 252) OVER w AS nav_1y,
        LAG(nav, 756) OVER w AS nav_3y,
        LAG(nav, 1260) OVER w AS nav_5y
    FROM mf_nav_history
    WINDOW w AS (PARTITION BY scheme_code ORDER BY nav_date)
)
SELECT
    scheme_code,
    as_of_date,
    (current_nav / NULLIF(nav_1w,0) - 1) * 100 AS returns_1w_pct,
    (current_nav / NULLIF(nav_1m,0) - 1) * 100 AS returns_1m_pct,
    (current_nav / NULLIF(nav_3m,0) - 1) * 100 AS returns_3m_pct,
    (current_nav / NULLIF(nav_6m,0) - 1) * 100 AS returns_6m_pct,
    (current_nav / NULLIF(nav_1y,0) - 1) * 100 AS returns_1y_pct,
    (POWER(current_nav / NULLIF(nav_3y,0), 1.0/3) - 1) * 100 AS returns_3y_cagr_pct,
    (POWER(current_nav / NULLIF(nav_5y,0), 1.0/5) - 1) * 100 AS returns_5y_cagr_pct
FROM nav_snapshots
WHERE as_of_date = (SELECT MAX(nav_date) FROM mf_nav_history);
CREATE UNIQUE INDEX ON mv_mf_returns (scheme_code);

-- Refresh schedule (pg_cron):
-- SELECT cron.schedule('refresh-52week', '15 18 * * 1-5', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_52week');
-- SELECT cron.schedule('refresh-mf-returns', '0 23 * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_mf_returns');
```

---

## 4. Source Mapping

| Dataset | Primary | Fallback | Notes |
|---|---|---|---|
| Company master | BSE Equity.csv | NSE EQUITY_L.csv, Screener | Cross-reference by ISIN |
| Company profile | Screener | Moneycontrol, BSE | Long-form description |
| Listed securities | NSE + BSE master files | — | Daily merge |
| Industry classification | NSE industry mapping | Screener | Update monthly |
| Directors | BSE filings (MGT-7) | Screener Concall | DIN dedup |
| Subsidiaries | Annual report (BSE) | MCA data | Manual reconciliation |
| Live quote (NSE) | NSE quote-equity API | — | Cookie-warmed |
| Live quote (BSE) | BSE quote API | — | |
| Intraday OHLC | NSE WebSocket | aggregated ticks | Real-time |
| Daily OHLC | NSE Bhavcopy | Yahoo Finance | Cross-validate close prices |
| Adjusted price | derived | corporate_actions table | Cumulative split/bonus factor |
| Pre-open | NSE pre-open API | — | 09:00–09:08 IST |
| Indices | NSE indices API | BSE indices | Real-time |
| Index constituents | NSE indices file | NSE PDF | Monthly rebalance |
| Top gainers/losers | NSE variations API | — | Real-time |
| Market breadth | NSE/BSE direct | — | |
| Corporate actions | BSE corporate actions feed | NSE corporate actions | Dedup by (symbol, action_type, ex_date) |
| Dividends | BSE dividend XLS | NSE | |
| Bonus/splits | BSE corporate actions | NSE | |
| Buybacks | BSE buyback page | NSE | |
| Mergers | BSE filings | — | Manual tag from announcements |
| Board meetings | BSE board meetings | NSE | |
| Announcements | BSE corp filings | NSE corp announcements | 15-min poll |
| F&O symbols | NSE F&O master | — | Daily |
| Futures quote | NSE F&O API | — | Real-time |
| Options chain | NSE option chain API | — | Real-time |
| Option Greeks | derived (Black-Scholes) | — | Calculated server-side |
| OI history | NSE F&O API | — | Real-time |
| Block/bulk deals | NSE block deals + BSE | — | Merge by trade_date |
| Quarterly results | Screener | Moneycontrol, BSE results PDF | Use raw_payload for full data |
| Annual P&L | Screener | Moneycontrol, BSE annual | |
| Balance sheet | Screener | Annual report (PDF parse) | |
| Cash flow | Screener | Annual report | |
| Ratios | derived | Screener ratios | Recompute from PL+BS |
| Segments | Screener notes | Annual report | |
| Shareholding pattern | BSE | NSE | Quarterly |
| Promoter holdings | BSE shareholding | NSE | Pledge data from BSE |
| FII holdings | Trendlyne | NSDL FPI data | Quarterly top holders |
| DII holdings | Trendlyne | AMFI portfolios | Aggregated from MF holdings |
| MF holdings in stock | AMFI portfolios | Trendlyne, Moneycontrol | Monthly |
| Insider trading | BSE SAST filings | NSE | Daily |
| AMC master | AMFI | — | Monthly |
| Scheme master | AMFI scheme codes | — | Weekly |
| NAV daily | AMFI NAVAll.txt | — | EOD |
| MF holdings | AMC websites (PDF) | Trendlyne, Value Research | Monthly mandatory disclosure |
| Sector allocation | derived | AMC factsheet | Computed from holdings |
| Returns | derived | Value Research, AMC factsheet | Computed from NAV history |
| Risk metrics | derived | Value Research | Computed from NAV history |
| Expense ratio | AMC factsheet | Value Research | Monthly |
| Company news | Moneycontrol | BSE/NSE announcements | 10-min |
| Brokerage recos | Moneycontrol | Trendlyne | Daily |
| Target consensus | derived | Trendlyne | Aggregated |

---

## 5. Data Refresh Strategy

| Layer | Frequency | Trigger | Job ID | Window |
|---|---|---|---|---|
| Real-time prices (NSE/BSE) | 5-second poll | APScheduler interval | `realtime_prices` | 09:15–15:30 IST Mon–Fri |
| Intraday OHLC 1m aggregation | Continuous | streaming aggregator | `agg_1m` | Market hours |
| Intraday OHLC 5m/15m | Continuous | derived from 1m | `agg_5m`, `agg_15m` | Market hours |
| Top gainers/losers | 5-min | interval | `gainers_losers` | Market hours |
| Indices snapshot | 5-min | interval | `indices_snapshot` | Market hours |
| Pre-open session | One-shot 09:00 IST | cron | `pre_open` | Mon–Fri |
| Daily Bhavcopy ingest | 18:30 IST | cron | `bhavcopy_eod` | Mon–Fri |
| Corporate actions | 22:00 IST | cron | `corp_actions_eod` | Mon–Fri |
| BSE announcements poll | 15-min | interval | `bse_announcements` | 09:00–18:00 IST |
| NSE announcements poll | 15-min | interval | `nse_announcements` | 09:00–18:00 IST |
| Moneycontrol news | 10-min | interval | `mc_news` | 24/7 |
| Insider trading filings | Hourly | interval | `insider_trades` | 09:00–18:00 IST |
| Block/bulk deals | 18:45 IST | cron | `block_deals_eod` | Mon–Fri |
| BSE master refresh | 01:00 IST | cron | `bse_master` | Daily |
| NSE security list | 01:30 IST | cron | `nse_master` | Daily |
| Screener financials (full) | 02:00 IST | cron | `screener_fin` | Daily |
| Screener (results delta) | Hourly | interval | `screener_results` | During results season |
| AMFI NAV ingest | 07:00 IST | cron | `amfi_nav` | Daily |
| AMFI historical NAV (gap-fill) | 07:15 IST | cron | `amfi_nav_backfill` | Daily |
| MF portfolio disclosures | 7th of month, 03:00 IST | cron | `mf_holdings_monthly` | Monthly |
| Shareholding pattern | 21 days post quarter-end | event-triggered | `shareholding_quarterly` | Quarterly |
| Industry classification refresh | 1st of month, 02:00 IST | cron | `industry_master` | Monthly |
| Index constituents | 1st & 15th, 02:30 IST | cron | `index_constituents` | Semi-monthly |
| Brokerage recommendations | 18:00 IST | cron | `brokerage_recos` | Daily |
| Materialized view refresh (52w) | 18:35 IST | pg_cron | `refresh_mv_52week` | Mon–Fri |
| Materialized view refresh (MF returns) | 23:00 IST | pg_cron | `refresh_mv_mf_returns` | Daily |
| Materialized view refresh (ratios) | 18:45 IST | pg_cron | `refresh_mv_ratios` | Mon–Fri |
| Yahoo Finance historical backup | Sunday 01:00 IST | cron | `yahoo_backfill` | Weekly |
| Data quality checks | 23:30 IST | cron | `dq_nightly` | Daily |

---

## 6. Deduplication & Validation Logic

### Idempotency keys (one per table)

| Table | Natural key | Strategy |
|---|---|---|
| stocks_master | `isin` (unique) or `nse_symbol` | `ON CONFLICT DO UPDATE` |
| listed_securities | `(exchange, symbol, series)` | UPSERT |
| stock_prices | `(symbol, exchange, timestamp)` | INSERT only (immutable) |
| stock_ohlc_daily | `(symbol, trade_date)` | UPSERT |
| stock_ohlc_intraday | `(symbol, interval, timestamp)` | INSERT |
| corporate_actions | `(symbol, action_type, ex_date)` | UPSERT |
| announcements | `url_hash` (SHA256 of URL) | INSERT, ignore on conflict |
| financials_quarterly | `(symbol, period, consolidated)` | UPSERT (latest revision wins) |
| financials_balance_sheet | `(symbol, fy_year, consolidated)` | UPSERT |
| shareholding_pattern | `(symbol, period)` | UPSERT |
| mutual_funds (NAV) | `(scheme_code, nav_date)` | UPSERT |
| mf_holdings | `(scheme_code, as_of_month, isin, instrument_name)` | UPSERT |
| company_news | `url_hash` (SHA256 of URL) | INSERT, skip on conflict |
| brokerage_recommendations | `(symbol, broker_name, recommendation_date, target_price)` | UPSERT |
| block_bulk_deals | `(trade_date, symbol, client_name, action, quantity, price)` | UPSERT |

### Validation rules (enforced in `normalize()` before save)

```python
VALIDATION_RULES = {
    "stocks_master": [
        ("nse_symbol",   "match(/^[A-Z][A-Z0-9&-]{0,19}$/)"),
        ("isin",         "len == 12 and isalnum"),
        ("face_value",   ">= 1.0 and <= 1000.0"),
        ("market_cap_cr", ">= 0"),
        ("listing_date_nse", "<= today and > 1990-01-01"),
    ],
    "stock_ohlc_daily": [
        ("high",  ">= low"),
        ("high",  ">= open and >= close"),
        ("low",   "<= open and <= close"),
        ("volume", ">= 0"),
        ("trade_date", "is weekday and <= today"),
    ],
    "financials_quarterly": [
        ("revenue_cr",   ">= 0"),
        ("ebitda_cr",    "<= total_income_cr"),
        ("pat_cr",       "<= ebitda_cr (warn only)"),
        ("eps_basic",    "abs <= 10000"),  # sanity bound
        ("period_end_date", "is quarter-end"),
    ],
    "mutual_funds": [
        ("nav",         "> 0 and < 100000"),
        ("nav_date",    "<= today and > 1990-01-01"),
        ("scheme_code", "numeric, len in (5,6)"),
    ],
    "shareholding_pattern": [
        ("sum of all pct fields", "between 99.0 and 101.0"),  # tolerance
        ("promoter_holding_pct",  "0 <= x <= 100"),
        ("promoter_pledged_pct",  "0 <= x <= promoter_holding_pct"),
    ],
    "corporate_actions": [
        ("ex_date", "<= record_date if record_date present"),
        ("announcement_date", "<= ex_date"),
    ],
}
```

### Cross-source reconciliation

```python
def reconcile_close_price(symbol: str, trade_date: date) -> float:
    """When NSE and Yahoo disagree on close price, prefer NSE if delta < 0.5%,
    else flag in data_quality_log and use median."""
    nse = nse_close(symbol, trade_date)
    yhf = yahoo_close(symbol, trade_date)
    if nse and yhf:
        delta_pct = abs(nse - yhf) / nse * 100
        if delta_pct > 0.5:
            log_dq("stock_ohlc_daily", "nse_yahoo_disagreement",
                   severity="warning", failed_count=1,
                   sample={"symbol": symbol, "date": trade_date, "nse": nse, "yahoo": yhf})
        return nse
    return nse or yhf
```

### Nightly DQ checks

1. **Coverage** — every active NSE symbol must have OHLC for the last trading day.
2. **Continuity** — no gap > 5 trading days in OHLC history per active symbol.
3. **Sum constraints** — shareholding pattern percentages sum to ~100.
4. **Referential** — every `mf_holdings.symbol` matches `stocks_master.nse_symbol` (FK soft check).
5. **Freshness** — every source's `last_success_at` within expected SLA.
6. **Volume sanity** — NSE total turnover within 30-day moving average ±50%.

Failures land in `data_quality_log` with severity. Critical issues page on-call via Alertmanager.

---

## 7. Gaps vs CMOTS (what we cannot replicate from free sources)

| CMOTS feature | Status | Workaround |
|---|---|---|
| Real-time L2 market depth (full order book) | ❌ Not free | Use NSE 5-best from `/tick`, or paid Truedata/Zerodha Kite |
| Tick-by-tick data (every print) | ❌ Not free | Aggregate to 1-min from NSE polling |
| Currency derivatives (USD-INR, EUR-INR futures) | ⚠️ Partial | NSE currency segment scraper to add |
| Commodity (MCX) data | ❌ Not in scope | Add MCX scraper if required |
| Bond/G-sec yields and trades | ⚠️ Partial | NDS-OM scraper for G-sec; corporate bond data via BSE |
| Pre-merger historical price stitching | ⚠️ Manual | Maintain `historical_alias` table for symbol changes |
| Bloomberg-level fundamental detail (footnotes, accounting policies) | ❌ | Parse annual report PDFs (Tesseract OCR on scanned pages) |
| Ratings agency data (CRISIL, ICRA) | ❌ | Direct partnerships required |
| Analyst earnings estimates (forward EPS) | ⚠️ Limited | Trendlyne consensus; not all coverage available |
| Detailed insider transactions across all listed cos | ✅ | BSE SAST disclosures cover all |
| Institutional ownership history (10-year) | ⚠️ | Quarterly snapshots only; no daily flow |
| Smart Beta / Factor exposures (value, momentum, quality scores) | ❌ | Compute in-house from ratio history |
| Corporate governance scores | ❌ | Compute from board composition + audit + related-party transactions |
| ESG ratings | ❌ | Partner with Sustainalytics/MSCI or build internal score |
| Real-time news sentiment (sub-second) | ⚠️ | Moneycontrol 10-min polling is the practical floor |

---

## 8. Python ETL Architecture

### Folder layout

```
indian-market-pipeline/
├── api/
│   ├── main.py                     # FastAPI + middleware + DI
│   ├── dependencies.py             # auth, db, cache wiring
│   └── routers/
│       ├── company.py              # /v1/company/* (APIs 1-10)
│       ├── prices.py               # /v1/quote/*, /v1/ohlc/* (APIs 11-25)
│       ├── indices.py              # /v1/index/*, /v1/top-*, breadth (26-35)
│       ├── corporate_actions.py    # /v1/corporate-actions/*, dividends, etc (36-45)
│       ├── derivatives.py          # /v1/fno/* (46-55)
│       ├── financials.py           # /v1/financials/*, /v1/ratios/* (56-65)
│       ├── ownership.py            # /v1/shareholding/*, insider (66-72)
│       ├── mutual_funds.py         # /v1/mf/* (73-87)
│       ├── news.py                 # /v1/news/* (88-89)
│       ├── research.py             # /v1/research/* (90-92)
│       └── admin.py                # /v1/admin/trigger/*
├── core/
│   ├── config.py                   # Pydantic Settings (12-factor)
│   ├── logging.py                  # structlog JSON config
│   └── exceptions.py
├── models/
│   ├── enums.py                    # Source, Exchange, Status enums
│   └── schemas.py                  # Pydantic v2 In/Out per table
├── scrapers/
│   ├── base.py                     # Abstract BaseScraper
│   ├── nse/
│   │   ├── prices.py
│   │   ├── ohlc.py
│   │   ├── indices.py
│   │   ├── pre_open.py
│   │   ├── fno.py
│   │   ├── corporate_actions.py
│   │   ├── announcements.py
│   │   ├── block_deals.py
│   │   └── bhavcopy.py
│   ├── bse/
│   │   ├── master.py
│   │   ├── filings.py
│   │   ├── shareholding.py
│   │   ├── insider.py
│   │   └── corporate_actions.py
│   ├── screener/
│   │   ├── profile.py
│   │   ├── financials.py
│   │   └── ratios.py
│   ├── trendlyne/
│   │   ├── fii_dii.py
│   │   ├── mf_holdings.py
│   │   └── brokerage.py
│   ├── moneycontrol/
│   │   ├── news.py
│   │   └── ratios.py
│   ├── amfi/
│   │   ├── nav.py
│   │   ├── schemes.py
│   │   └── holdings.py
│   └── yahoo/
│       └── historical.py
├── services/
│   ├── storage.py                  # Storage protocol
│   ├── db_service.py               # asyncpg Postgres
│   ├── sqlite_storage.py
│   ├── cache_service.py            # Redis async
│   ├── circuit_breaker.py
│   ├── scheduler.py                # APScheduler job factory
│   ├── normalization.py            # symbol, date, currency normalizers
│   ├── reconciliation.py           # cross-source merge logic
│   ├── data_quality.py             # nightly DQ runner
│   ├── greeks_calculator.py        # Black-Scholes
│   ├── returns_calculator.py       # XIRR / CAGR / SIP
│   └── notification.py             # Slack/Telegram on failures
├── database/
│   ├── schema.sql                  # full DDL above
│   ├── schema_sqlite.sql           # SQLite-compatible subset
│   ├── partitions.sql              # partition management
│   ├── materialized_views.sql
│   └── migrations/                 # Alembic versions
├── scripts/
│   ├── init_local_db.py
│   ├── ingest_once.py              # CLI: python -m scripts.ingest_once nse --task prices
│   ├── backfill.py                 # date-range historical ingest
│   ├── create_partitions.py        # monthly partition pre-creator
│   └── reconcile_close_prices.py
├── tests/
│   ├── unit/
│   │   ├── test_normalization.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_validators.py
│   │   └── test_greeks.py
│   ├── integration/
│   │   ├── test_amfi_e2e.py
│   │   └── test_nse_session.py
│   └── api/
│       └── test_routers.py
├── observability/
│   ├── prometheus.yml
│   ├── grafana_dashboards/
│   │   ├── scrapers.json
│   │   ├── api.json
│   │   └── data_quality.json
│   └── alertmanager.yml
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── docker-compose.yml
├── docker-compose.prod.yml
├── pyproject.toml
└── requirements.txt
```

### Class hierarchy

```
BaseScraper (abstract)
 ├── HTTPScraper                       # adds httpx + cookie warmup
 │    ├── NSEPricesScraper
 │    ├── NSEIndicesScraper
 │    ├── NSEOHLCScraper
 │    ├── NSEFNOScraper
 │    ├── NSEBhavcopyScraper
 │    ├── BSEMasterScraper
 │    ├── BSEFilingsScraper
 │    ├── BSEShareholdingScraper
 │    └── AMFIScraper / AMFISchemesScraper / AMFIHoldingsScraper
 ├── PlaywrightScraper                 # adds Chromium + stealth
 │    ├── ScreenerFinancialsScraper
 │    ├── ScreenerRatiosScraper
 │    ├── MoneycontrolNewsScraper
 │    └── TrendlyneScraper
 └── FileScraper                       # local/uploaded files
      └── AMFIHistoricalScraper
```

### Concurrency model

```
┌──────────────────────────────────────────────────────────────────┐
│ Single Python process (uvicorn worker + APScheduler in-process)  │
│                                                                  │
│  asyncio event loop                                              │
│  ├── FastAPI request handlers (read-side, no scraping)          │
│  ├── APScheduler async jobs (write-side)                        │
│  │     └── scrapers run concurrently per source                 │
│  │         (one client per source, lazily started)              │
│  │                                                               │
│  Shared:                                                         │
│  ├── asyncpg connection pool (10–30 conns)                      │
│  ├── Redis async client                                         │
│  ├── per-source circuit breakers (module-level singletons)      │
│  └── per-source rate limiters                                   │
└──────────────────────────────────────────────────────────────────┘
```

For horizontal scale:
- API workers: stateless, scale to N uvicorn workers behind nginx
- Scheduler: deploy as a **separate single-instance worker** to avoid duplicate jobs
- Real-time price ingestor: separate single-instance worker
- Heavy backfills: dedicated worker reading from a Redis queue (RQ or arq)

### Failure handling matrix

| Failure | Detection | Recovery |
|---|---|---|
| Upstream 5xx | httpx exception | Tenacity exponential backoff, max 5 retries |
| Upstream 429 | status code | Sleep proportional to `Retry-After`, max 60s |
| Upstream Cloudflare 403 | text match | Rotate UA + proxy, sleep 30s, retry once |
| Upstream session expired (NSE 401) | status code | Re-warm cookies, retry once |
| Upstream layout change | parser exception | Mark run FAILED, alert via Slack |
| Schema validation failure | Pydantic exception | Drop record, log to `data_quality_log` |
| DB connection lost | asyncpg `InterfaceError` | Reconnect via pool, retry transaction |
| Constraint violation | Postgres unique error | Use ON CONFLICT clause; if not idempotent, alert |
| Job overrun (still running at next tick) | APScheduler `max_instances=1` | Skip new fire; coalesce missed ticks |
| Partition missing | Postgres "no partition for value" | Auto-create monthly partition at 23:55 IST |
| Circuit open | `CircuitOpenException` | Skip run, schedule retry after `reset_seconds` |

### Observability triangle

1. **Metrics (Prometheus)**
   - `scraper_requests_total{source, endpoint, status}`
   - `scraper_records_total{source, table, outcome}`
   - `scraper_duration_seconds{source, task}` (histogram)
   - `scraper_failures_total{source, reason}`
   - `api_request_duration_seconds{path, method, status}`
   - `db_pool_utilization`
   - `cache_hit_ratio{cache}`
   - `circuit_state{source}` (gauge: 0=closed, 1=open, 2=half-open)
2. **Logs (structlog → JSON → Loki/CloudWatch)**
   - Every scraper run emits 1 line at start, 1 at end with full result
   - Every API request logs path, status, latency, user
   - Every DQ failure logs table, check, severity, sample
3. **Traces (OpenTelemetry → Tempo/Jaeger, optional)**
   - One trace per API request, spans for cache + DB
   - One trace per scraper run, spans for fetch/normalize/save

### Deployment topology

```
                            ┌──────────────┐
                            │  CloudFront  │  CDN
                            └───────┬──────┘
                                    │
                            ┌───────▼──────┐
                            │  Nginx /ALB  │
                            └───────┬──────┘
                  ┌─────────────────┼──────────────────┐
            ┌─────▼─────┐    ┌──────▼─────┐    ┌──────▼─────┐
            │ API w1    │    │ API w2     │    │ API w3     │  N uvicorn
            └─────┬─────┘    └──────┬─────┘    └──────┬─────┘
                  └─────────────────┼──────────────────┘
                      ┌─────────────┼──────────────┐
                ┌─────▼──────┐ ┌────▼─────┐  ┌────▼──────┐
                │  Supabase  │ │  Redis   │  │ Prometheus│
                │  Postgres  │ │  Cluster │  │  + Grafana│
                └─────┬──────┘ └──────────┘  └───────────┘
                      │
              ┌───────┴────────┐
              │  Scheduler     │  single instance
              │  Worker        │  (APScheduler + scrapers)
              └────────────────┘

         ┌──────────────────────┐
         │ Real-time Ingestor   │  single instance
         │ (NSE WebSocket / poll)│
         └──────────────────────┘
```

### Performance / scale targets

| Dimension | Target |
|---|---|
| API p99 latency | < 200 ms (cached) / < 800 ms (uncached) |
| Real-time price freshness | < 6 sec lag |
| Daily OHLC ingest completion | < 5 min after Bhavcopy release (18:30 IST) |
| AMFI NAV ingest | < 30 sec for 22k schemes |
| Concurrent API users | 1000 RPS sustained |
| Storage: 5y daily OHLC | ~50M rows for 5000 symbols → ~5 GB compressed |
| Storage: 5y intraday 1m | ~5B rows → use partitioning + retention (90d hot, archive to S3) |
| Storage: 5y NAV history | ~40M rows → ~2 GB |

### CI/CD

- **Pre-commit**: ruff lint + format, mypy strict, pytest unit
- **CI (GitHub Actions)**: full test suite, schema migration dry-run, coverage > 80%
- **Staging deploy**: every merge to `main`, runs against shadow Supabase
- **Prod deploy**: tag-based via Railway/Render/AWS ECS
- **DB migrations**: Alembic, applied in pre-deploy step with `alembic upgrade head`

---

## 9. Appendix — Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `INVALID_SYMBOL` | 400 | Symbol does not exist in `stocks_master` |
| `INVALID_DATE_RANGE` | 400 | from_date > to_date or > 5y range |
| `MISSING_PARAM` | 400 | Required input missing |
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `RATE_LIMITED` | 429 | Per-key rate limit hit |
| `NO_DATA` | 404 | Query valid but no rows |
| `UPSTREAM_UNAVAILABLE` | 503 | Source scraper circuit open |
| `STALE_DATA` | 200 (with `meta.stale=true`) | Data older than SLA |

---

## 10. Sample Response Envelope

```json
{
  "data": [
    {
      "symbol": "RELIANCE",
      "ltp": 2945.20,
      "change_pct": 1.24,
      "volume": 5832110,
      "timestamp_ist": "2026-05-18T14:15:30+05:30"
    }
  ],
  "meta": {
    "count": 1,
    "page": 1,
    "limit": 100,
    "source": "NSE",
    "cached": false,
    "cache_ttl_remaining_s": null,
    "data_as_of": "2026-05-18T14:15:30+05:30",
    "stale": false
  },
  "error": null
}
```

---

**End of specification — 92 APIs, 38 tables, complete refresh/dedup/architecture spec.**
