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
POST_TRADE_COLUMNS = ("post_bid", "post_ask")

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
CONSISTENT_POOL_MIN_DAYS_TO_EXPIRY = None   # re-derived after the backfill coverage check
