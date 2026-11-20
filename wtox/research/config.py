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

# --- stage 3 pre-registration (CLAUDE.md §10, 2026-11-20, before any stage 3 result) -----------
STAGE3_DAYS = "train"                        # stage 3 uses 2025 only; 2026 is untouched until stage 5
MAIN_HORIZON = "5m"                          # H1/H2 tests; other horizons only as markout curves
WEIGHT = "notional"                          # main aggregation: notional-weighted (= issuer P&L per NTD);
                                             # equal-weighted is a robustness check
DELTA_BUCKET_EDGES = (0, 0.2, 0.4, 0.6, float("inf"))     # |delta| per share
DELTA_BUCKET_LABELS = ("<0.2", "0.2–0.4", "0.4–0.6", ">0.6")
SIZE_BUCKET_EDGES = (0, 10, 50, 100, float("inf"))        # order_volume, lots
SIZE_BUCKET_LABELS = ("1–10", "11–50", "51–100", ">100")
SPOT_MOVE_WINDOW = "1s"                      # main; "5s" robustness (panel S_chg_1s / S_chg_5s)
SPOT_MOVE_WINDOWS = {"1s": pd.Timedelta(seconds=1), "5s": pd.Timedelta(seconds=5)}
TOD_EDGES = (pd.Timedelta(hours=9), pd.Timedelta(hours=9, minutes=30), pd.Timedelta(hours=12, minutes=30),
             pd.Timedelta(hours=13, minutes=25))
TOD_LABELS = ("09:00–09:30", "09:30–12:30", "12:30–13:25")
HIGH_GAMMA_CELL = ("0.4–0.6", "1–30")        # pre-specified |delta| x DTE cell; other cross cells exploratory
DETREND_HORIZONS = ("5m", "30m", "close")    # main de-trended; shorter ones de-trended only as robustness

# Hedge cost c per one-way trade, as a fraction of underlying notional (§3.3). Spot half spread is
# measured per trade (panel S_spread_bps). Netting scales each trade's cost by |net delta| / gross |delta|
# within the group: none (every trade hedged alone), warrant_day (each warrant's daily net), issuer_day
# (the issuer's whole 2330 book for the day). c covers the initial delta hedge only: gamma re-hedging and
# vega P&L from re-marking IV are NOT included, so short-dated ATM warrants cost more than this.
HEDGE_SCENARIOS = {
    "pessimistic": {"instrument": "stock", "tax": STOCK_TRANSACTION_TAX / 2, "fee": BROKERAGE_FEE_MAX,
                    "netting": "none"},
    "neutral": {"instrument": "stock", "tax": STOCK_TRANSACTION_TAX / 2, "fee": 0.3 * BROKERAGE_FEE_MAX,
                "netting": "warrant_day"},
    "optimistic": {"instrument": "stock_futures", "tax": SINGLE_STOCK_FUTURES_TAX, "fee": 0.0,
                   "netting": "issuer_day"},
}
WARRANT_TAX = 0.001                          # 權證證交稅, sell side (retail view §3.6 b)

# --- H4: warrant flow predicts 2330 (CLAUDE.md §3.7); main settings pre-registered 2026-11-20 --------
H4_GRID = pd.Timedelta(minutes=1)            # τ grid spacing
H4_FLOW_WINDOW = pd.Timedelta(minutes=5)     # k: flow summed over [τ - k, τ)
H4_MAIN_HORIZON = "5m"                       # main target: 2330 mid-to-mid return [τ, τ + h]
H4_EXPLORATORY_HORIZONS = ("1m", "30m", "close")   # BH-FDR, labelled exploratory
H4_FIRST_TAU = pd.Timedelta(hours=9, minutes=5)    # first full flow window ends 09:05
H4_LAST_TAU = pd.Timedelta(hours=13, minutes=20)   # last τ for any h (close too); also τ + h <= 13:25
H4_NORM_LOOKBACK_DAYS = 20                   # denominator: mean 2330 shares traded in the same 5-min
                                             # time-of-day window over the previous 20 trading days
H4_TOD_DUMMY = pd.Timedelta(minutes=30)      # time-of-day dummies
H4_SIGNAL = "residual"                       # stage 5 signal: flow minus its training-fitted projection on
                                             # the controls; "raw" normalised flow reported for comparison
H4_THRESHOLD_QUANTILE = 0.05                 # static training-period top / bottom 5%
H4_OVERLAP = "parallel"                      # each triggered τ opens a 1/5 position held 5 min
H4_INSTRUMENT = "stock_futures"              # main: 2330 stock futures; stock (day-trade tax) as reference
STOCK_DAYTRADE_TAX = 0.0015                  # 現股當沖賣出證交稅 (reduced rate), reference only

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
# Fine pass (decides whether the 1s/5s windows stay, CLAUDE.md §10): 10 ms grid, +-0.5 s.
CLOCK_FINE_GRID = pd.Timedelta(milliseconds=10)
CLOCK_FINE_MAX_LAG = 50

# Same-side IV change (issuer re-marking vol): pairs of consecutive same-side trades in one warrant
# at most this far apart; farther pairs are dropped (vol moves for other reasons over long gaps).
IV_PAIR_MAX_GAP = pd.Timedelta(minutes=30)

# Dividends (FinMind TaiwanStockDividend), stored at <data>/finmind/dividends_2330.parquet.
DIVIDEND_FILE = "finmind/dividends_2330.parquet"
