"""2330 cash dividends from FinMind ``TaiwanStockDividend`` (CLAUDE.md §2 已知缺口「股利」).

Taiwan warrants are dividend-protected: on the ex-date the issuer adjusts strike and ratio (TWSE
event 除權息調整), which keeps the warrant's moneyness roughly unchanged. Pricing a protected
warrant with q = 0 is therefore the main specification; the dividends here serve to

* check the ex-dates against the TWSE adjustment dates the terms use (``compare_ex_dates``),
* tag warrant-days near ex-dates for the separate §5.1 check (ivcheck.iv_vs_tej), and
* build an unprotected-warrant q for the sensitivity analysis (``effective_q``): the continuous
  yield with the same present value as the cash dividends going ex in (day, expiry].

    python -m wtox.research.dividends --data ../data          # download and store
"""

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from wtox.research import config

API = "https://api.finmindtrade.com/api/v4/data"
CASH_COLUMNS = ("CashEarningsDistribution", "CashStatutorySurplus")


def fetch(stock_id=config.UNDERLYING, start="2024-01-01", token=None, timeout=60):
    """Raw FinMind rows. Public data; a token only raises the rate limit."""
    params = {"dataset": "TaiwanStockDividend", "data_id": stock_id, "start_date": start}
    if token:
        params["token"] = token
    with urllib.request.urlopen(f"{API}?{urllib.parse.urlencode(params)}", timeout=timeout) as resp:
        body = json.load(resp)
    if body.get("status") != 200:
        raise RuntimeError(f"FinMind error: {body.get('msg')}")
    return pd.DataFrame(body["data"])


def parse(raw):
    """One row per cash ex-date: ex_date, cash (TWD per share), pay_date."""
    need = {"CashExDividendTradingDate", *CASH_COLUMNS}
    missing = need - set(raw.columns)
    if missing:
        raise ValueError(f"FinMind columns missing: {sorted(missing)}")
    d = raw.copy()
    d["ex_date"] = pd.to_datetime(d["CashExDividendTradingDate"], errors="coerce")
    d["cash"] = sum(pd.to_numeric(d[c], errors="coerce").fillna(0) for c in CASH_COLUMNS)
    d["pay_date"] = pd.to_datetime(d.get("CashDividendPaymentDate"), errors="coerce")
    d = d[d["ex_date"].notna() & (d["cash"] > 0)]
    d = d.drop_duplicates(["ex_date", "cash"])       # a re-published announcement must not double the cash
    d = d.groupby("ex_date", as_index=False).agg(cash=("cash", "sum"), pay_date=("pay_date", "max"))
    return d.sort_values("ex_date").reset_index(drop=True)


def load(data_dir):
    return pd.read_parquet(Path(data_dir) / config.DIVIDEND_FILE)


def ex_dates(divs):
    return list(pd.to_datetime(divs["ex_date"]))


def compare_ex_dates(divs, twse_dates, start=config.SAMPLE_START, end=config.SAMPLE_END):
    """Ex-dates in the sample from FinMind vs TWSE warrant adjustment dates; both sides listed."""
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    fm = {d for d in pd.to_datetime(divs["ex_date"]) if lo <= d <= hi}
    tw = {d for d in pd.to_datetime(list(twse_dates)) if lo <= d <= hi}
    rows = [(d, d in fm, d in tw) for d in sorted(fm | tw)]
    return pd.DataFrame(rows, columns=["date", "finmind", "twse_adjustment"])


def effective_q(day, S, T, divs, r=config.RISK_FREE):
    """Continuous yield equal in PV to cash dividends going ex in (day, day + T]. Arrays OK."""
    day = pd.Timestamp(day)
    S, T = np.broadcast_arrays(np.asarray(S, float), np.asarray(T, float))
    t_ex = ((pd.to_datetime(divs["ex_date"]) - day).dt.days / config.DAYS_PER_YEAR).to_numpy()
    cash = divs["cash"].to_numpy(float)
    live = (t_ex[None, :] > 0) & (t_ex[None, :] <= T.reshape(-1, 1))
    pv = (live * cash * np.exp(-r * t_ex)).sum(axis=1).reshape(S.shape)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.where(T > 0, -np.log1p(-pv / S) / T, 0.0)
    return q


def main(argv=None):
    p = argparse.ArgumentParser(description="Download 2330 cash dividends from FinMind")
    p.add_argument("--data", default="../data")
    p.add_argument("--start", default="2024-01-01")
    a = p.parse_args(argv)
    d = parse(fetch(start=a.start))
    path = Path(a.data) / config.DIVIDEND_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(path, index=False)
    print(f"{len(d)} ex-dates -> {path}")


if __name__ == "__main__":
    main()
