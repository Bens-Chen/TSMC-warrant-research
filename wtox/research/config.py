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


def check_unlocked(day):
    """Stage 5 lock (CLAUDE.md §10): analysis code must not read test-period days before the one run."""
    if str(day)[:10] >= TEST_START and not TEST_UNLOCKED:
        raise PermissionError(f"{day}: test period is locked (config.TEST_UNLOCKED = False, CLAUDE.md §10 stage 5)")


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

# --- stage 4 pre-registration (CLAUDE.md §10, 2026-11-21, before any stage 4 result) -----------
PLACEBO_PERMUTATIONS = 200                   # within-day shuffles of side
PLACEBO_SEED = 20261121
STALE_SPOT_MAX_AGE_S = 0.1                   # "fresh" 2330 quote: last 2330 tick <= 0.1 s before the trade
PAST_RETURN_WINDOWS = {"1m": pd.Timedelta(minutes=1), "5m": pd.Timedelta(minutes=5)}   # panel S_ret_<w>
ROBUST_EXCLUDE_TOD = ((pd.Timedelta(hours=9), pd.Timedelta(hours=9, minutes=5)),
                      (pd.Timedelta(hours=13, minutes=20), pd.Timedelta(hours=13, minutes=25)))
ROBUST_RISK_FREE = (0.010, 0.020)
ROBUST_LARGE_ORDER = (50, 100, 200)          # order_volume >= threshold
ISSUER_LIKE_SIZE_MULTIPLE = 50               # counterparty (i): displayed size a multiple of this
RETAIL_LIKE_MAX_LOTS = 9                     # counterparty (ii): 1-9 lots and spread < 50% of the warrant-day median
RETAIL_LIKE_SPREAD_RATIO = 0.5
ROBUST_MIN_DAY_COVERAGE = 0.95               # only days whose volume coverage >= 95%
H4_EXTREME_DAY_QUANTILE = 0.99               # drop days above this quantile of |2330 day return| / |flow|
H4_TAIL_EDGES = (0.0, 0.05, 0.50, 0.95, 1.0) # residual-flow quantile groups
H4_SHORT_DTE_DAYS = 90                       # flow split: <= 90 days to expiry vs longer

# --- stage 5 pre-registration (CLAUDE.md §10, 2026-11-21, before any 2026 data is read) -----------
TEST_UNLOCKED = True                         # reading any day >= TEST_START raises until this is True (one run)
DRY_RUN_SPLIT = "2025-06-30"                 # pipeline check before unlocking: fit <= this, "test" on the rest of 2025
SCORE_TARGET = f"M_dt_{MAIN_HORIZON}"
SCORE_AGE_CLIP_S = 16200                     # prev_quote_age_s clipped to one session (4.5 h), then log1p
SCORE_WINSOR_Q = (0.01, 0.99)                # half spread and momentum terms winsorised at training quantiles
SCORE_QUANTILES = 5                          # evaluation groups, cut points from training predictions
HEATMAP_NOTIONAL_EDGES = (0, 10_000, 100_000, float("inf"))     # single-trade notional, NTD
HEATMAP_NOTIONAL_LABELS = ("<1萬", "1–10萬", ">10萬")
HEATMAP_MIN_TRADES = 500                     # cells kept only if the TRAINING sample has >= 500 trades
HEATMAP_MIN_DAYS = 30                        #   and >= 30 trading days; the same cell list is used in 2026
FUTURES_CONTRACT_SHARES = 2000               # 2330 stock futures: 2,000 shares per contract
FUTURES_FEE_PER_CONTRACT = 20.0              # NTD per side (assumption)
FUTURES_TICKS = ((1000, 5.0), (500, 1.0), (100, 0.5), (50, 0.1), (10, 0.05), (0, 0.01))   # (price floor, tick)
REPLICATION_ALPHA = 0.05
WALK_FORWARD = "expanding_monthly"          # secondary result: refit every month on all earlier data (from SAMPLE_START)

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

# --- extension analyses B-D (docs/decisions.md, 2026-11-21, pre-registered before any result) ---------
EXT_PROXY_IV_BOUNDS = (1.01e-4, 4.95)        # solver bounds are 1e-4 / 5.0 (wtox.iv): IVs at the edge are invalid
EXT_PROXY_EQUIV_MARGIN_BPS = 5.0             # B: proxy used only if the paired-bias CI lies inside +-5 bps
EXT_PROXY_CI = 0.90                          #    (90% CI, DTE 1-30 group)
EXT_TRADING_DAY_EDGES = (-1, 5, 10, 15, 20, 30)          # B: trading days to expiry (approx. business days)
EXT_TRADING_DAY_LABELS = ("0–5", "6–10", "11–15", "16–20", "21–30")
EXT_PRICE_EDGES = (0, 0.05, 0.5, float("inf"))           # B: fill price P, NTD
EXT_PRICE_LABELS = ("≤0.05", "0.05–0.5", ">0.5")
EXT_IV_AGE_EDGES = (-1, 300, 3600, float("inf"))         # B: seconds since the proxy IV was observed
EXT_IV_AGE_LABELS = ("<5分", "5–60分", ">60分")
EXT_C2_LAST_TRADE = pd.Timedelta(hours=12, minutes=55)   # C2: fixed sample, every horizon untruncated
EXT_C2_HORIZONS = ("30m", "close")                       # compared with 5m
EXT_C2_H4_HORIZONS = ("1m", "30m", "close")
EXT_REVERSION_SHARE = 0.5                    # C2: "no marked reversion" = CI lower bound above -50% of M(5m)

# --- extension E: issuer dynamic hedging (docs/decisions.md, 2026-11-21, before any result) ----------
E_LATENCY = "1s"                             # initial hedge fills at S_mid(t + L); labels S_mid_<L>
E_LATENCY_SENSITIVITY = ("10s", "1m")        # trade level, ladders 1 and 3
E_HORIZONS = {"5m": 1, "close": 5}           # holding period -> trade-level rebalancing every n minutes
E_REBALANCE_SENSITIVITY = 1                  # close, trade level, ladders 2 and 3: every minute
E_BOOK_BAND_SHARES = 2000                    # issuer book (close only): re-hedge when |net delta - hedge| > band
E_TRADE_COSTS = "pessimistic"                # HEDGE_SCENARIOS key for the trade level
E_BOOK_COSTS = "optimistic"                  # and for the issuer book

# --- post-hoc sensitivity (docs/decisions.md, 2026-11-21 audit) --------------------------------------
# 2330 locked at a price limit: no valid 2330 quote all day, S_mid frozen at the last print. Found by the
# audit after the results (2025-04-07, 2025-04-10); reported as a disclosed sensitivity, not a new main sample.
LOCKED_DAY_TRADE_MID_SHARE = 0.5             # day is "locked" if >= 50% of its trades have S_mid from a trade price

# --- extension: who wins / who loses, phase 1 intraday (docs/decisions.md 2026-11-22, before any result) ---
RETAIL_HORIZONS = ("5m", "close")            # retail holding periods (intraday); multi-day is phase 2
RETAIL_FEE = BROKERAGE_FEE_MAX               # per side, statutory cap (conservative)
RETAIL_ROUND_TRIP_TAX = WARRANT_TAX          # warrant transaction tax on the sell leg
RETAIL_RV_DAYS = 20                          # 2330 realised vol: previous 20 trading days, close-to-close (13:25 mid)
RETAIL_FLAT_BPS = 1.0                        # |past 5m return| below this = "flat" (chase / futures conditions)
RETAIL_TX_FILE = "futures_continuous/TX_continuous_1m_post_latest.parquet"
RETAIL_TX_BAR = pd.Timedelta(minutes=1)      # a bar stamped ts is used only from ts + 1 min (no look-ahead either way)
RETAIL_TX_MAX_STALE = pd.Timedelta(minutes=3)    # TAIEX futures bar older than this (or from an earlier day) -> no value

# --- who wins / who loses, phase 2 multi-day (docs/decisions.md 2026-11-22, before any result) -------
RETAIL_HOLD_DAYS = (1, 3, 5)                 # exit at the close of the k-th in-sample trading day after entry
RETAIL_MAIN_HOLD = 5                         # quadrant classification horizon (arbitrary, stated)
RETAIL_MAX_BID_AGE = pd.Timedelta(minutes=30)    # sensitivity: exit bid quoted at most this long before 13:25
RETAIL_LAST_TRADE_GAP = 1                    # <= this many trading days in (exit day, expiry]: past the last trading day

# --- extension: cross-issuer comparison (docs/decisions.md, 2026-11-22, before any result) ----------
CMP_MIN_PEERS = 3                            # peer group (day, kind, |delta| bucket, DTE bucket) needs >= 3 warrants with d-1 data
CMP_MIN_ISSUER_SHARE = 0.01                  # issuers below 1% of 2025 retail-buy notional pooled as "其他"
