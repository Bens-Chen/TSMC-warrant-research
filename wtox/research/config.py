"""Every research parameter lives here (CLAUDE.md §4). Other modules import, never hard-code.

Changing a value here changes the study: record the reason in CLAUDE.md §10.
"""

import pandas as pd

UNDERLYING = "2330"

# --- sample (CLAUDE.md §2, §5) -------------------------------------------------------------
SAMPLE_START = "2025-01-02"          # first month with pre-trade bid/ask in Shioaji
SAMPLE_END = "2026-11-18"            # 2026-11-19 has no underlying ticks
TRAIN_END = "2025-12-31"             # out-of-sample: train 2025, test 2026
TEST_START = "2026-01-02"
EXCLUDED_DAYS = frozenset({"2026-01-09"})   # Shioaji has no warrant ticks that day (CLAUDE.md §2)


def in_sample(day):
    """True for a YYYY-MM-DD day inside the study window and not excluded (⭐ CLAUDE.md §2)."""
    return SAMPLE_START <= day <= SAMPLE_END and day not in EXCLUDED_DAYS

# --- trading session -----------------------------------------------------------------------
# TWSE continuous trading 09:00-13:25; 13:25-13:30 is the closing call auction (one print at 13:30).
SESSION_OPEN = pd.Timedelta(hours=9)
CONTINUOUS_END = pd.Timedelta(hours=13, minutes=25)   # panel and labels use t < 13:25 only

# Panel columns observed right after the trade (they include the trade's own impact). Kept for
# diagnostics; never use them as model features (CLAUDE.md §4, §5.4).
POST_TRADE_COLUMNS = ("post_bid", "post_ask", "post_bid_volume", "post_ask_volume")

# --- markout horizons (CLAUDE.md §3.1) ------------------------------------------------------
# "close" = last continuous-session underlying mid (before 13:25). A horizon that runs past the
# continuous session is capped at that last quote.
HORIZONS = {
    "1s": pd.Timedelta(seconds=1),
    "5s": pd.Timedelta(seconds=5),
    "10s": pd.Timedelta(seconds=10),
    "30s": pd.Timedelta(seconds=30),
    "1m": pd.Timedelta(minutes=1),
    "5m": pd.Timedelta(minutes=5),
    "30m": pd.Timedelta(minutes=30),
    "close": None,
}

# --- pricing inputs ------------------------------------------------------------------------
RISK_FREE = 0.015                    # flat; sensitivity analysis in stage 4
DIVIDEND_YIELD = 0.0                 # q = 0 until FinMind TaiwanStockDividend is wired in
UNITS_PER_LOT = 1000                 # 1 lot = 1,000 warrants
DAYS_PER_YEAR = 365.0                # calendar-day year for time to expiry

# --- terms (wtox.research.terms) -----------------------------------------------------------
TWSE_SNAPSHOT_MARGIN_DAYS = 7        # code+strike fallback: TEJ expiry must be >= TWSE snapshot date minus this
DIVIDEND_MIN_WARRANTS = 10           # a TWSE adjustment date counts as an ex-date if >= this many warrants share it

# --- hedge-cost inputs (CLAUDE.md §3.3); scenarios are built in toxicity.py ------------------
# Statutory rates; the effective brokerage discount and spread scenarios are set in stage 3.
STOCK_TRANSACTION_TAX = 0.003        # 證交稅, stock sell side only
BROKERAGE_FEE_MAX = 0.001425         # 手續費 statutory cap, both sides, before discount
SINGLE_STOCK_FUTURES_TAX = 0.00002   # 期交稅 on stock futures, both sides

# --- backup sample rules (CLAUDE.md §2, only if coverage fails the §10 standard) -------------
# DTE buckets (DTE_BUCKET_LABELS) kept in BOTH periods: a bucket with any failing cell in either the
# training or the test period is dropped from both (CLAUDE.md §2 處理規則 3). None = not needed / not decided.
CONSISTENT_POOL_DTE_BUCKETS = None

# --- stage 2 validation (CLAUDE.md §5.1) ----------------------------------------------------
# Coverage = Shioaji whole-day tick volume / TEJ daily volume, per month x days-to-expiry bucket.
# Bucket edges are days to expiry: coverage uses TEJ days_to_expiry (剩餘期間, the only DTE TEJ-only
# warrant-days have); quotes uses calendar days from the point-in-time terms. They can differ
# (CLAUDE.md §2 expiry_conflict), so compare the two tables by bucket with that in mind.
# A "≤0" bucket keeps expiry-day rows (or a DTE source that disagrees) from silently dropping out.
DTE_BUCKET_EDGES = (float("-inf"), 0, 30, 90, 180, float("inf"))
DTE_BUCKET_LABELS = ("≤0", "1–30", "31–90", "91–180", ">180")
# Pass/fail standard: must be written into CLAUDE.md §10 BEFORE coverage results are seen (⭐ §2).
# None = not decided yet; coverage.passes() refuses to run until both are set.
COVERAGE_MIN_CELL = 0.90             # per month x DTE bucket (set 2026-11-20, before any coverage result)
COVERAGE_MIN_MONTH = 0.95            # per month, all buckets together

# Clock alignment: event series on a fixed grid, cross-correlated at lags of +-CLOCK_MAX_LAG grid steps.
CLOCK_GRID = pd.Timedelta(milliseconds=100)
CLOCK_MAX_LAG = 50                   # 50 x 100 ms = +-5 s

# Same-side IV change (issuer re-marking vol): pairs of consecutive same-side trades in one warrant
# at most this far apart; farther pairs are dropped (vol moves for other reasons over long gaps).
IV_PAIR_MAX_GAP = pd.Timedelta(minutes=30)

# Dividends (FinMind TaiwanStockDividend), stored at <data>/finmind/dividends_2330.parquet.
DIVIDEND_FILE = "finmind/dividends_2330.parquet"
