"""Point-in-time warrant terms that cover delisted warrants (CLAUDE.md §2 代號對應).

Two sources, neither complete on its own:

* TWSE open data (``twse/terms_2330.parquet``) lists only warrants still listed at the snapshot date,
  but its event history (issue, dividend adjustments, resets) is current.
* TEJ (``tej/terms_all.parquet``) covers delisted warrants too, but its export can be stale: some
  warrants lack the latest dividend adjustments. TEJ ids carry an extra letter when an exchange code
  was reused (``086717U`` -> ``086717``). TEJ's ``strike``/``ratio`` columns are the *latest* values
  (look-ahead); the point-in-time values are ``strike_event``/``ratio_event``.

Rule: a warrant found in TWSE takes its events from TWSE; any other warrant takes them from TEJ.
TWSE has no listing date, so each TWSE warrant is matched to its TEJ record for ``tej_id`` and
``listing_date``: first on (exchange code, expiry); failing that, on code alone with the same
issue strike (TEJ and TWSE sometimes disagree on expiry; such rows get ``expiry_conflict`` and keep
the TWSE expiry). A TEJ-sourced warrant that has no event on a dividend adjustment date it lived
through is flagged ``terms_stale`` from that day on.
"""

from pathlib import Path

import pandas as pd

from wtox.data.backfill import exchange_code
from wtox.research import config

COLUMNS = ["warrant_id", "tej_id", "event_date", "event_seq", "kind", "issuer", "strike", "ratio",
           "listing_date", "expiry_date", "last_trade_date", "terms_source", "expiry_conflict"]


def _from_tej(tej, underlying):
    t = tej[tej["underlying_id"] == underlying]
    out = pd.DataFrame({
        "warrant_id": t["warrant_id"].map(exchange_code), "tej_id": t["warrant_id"],
        "event_date": t["event_date"], "event_seq": t["event_seq"].astype("int64"),
        "kind": t["kind"], "issuer": t["issuer"], "strike": t["strike_event"], "ratio": t["ratio_event"],
        "listing_date": t["listing_date"], "expiry_date": t["expiry_date"],
        "last_trade_date": t["last_trade_date"], "terms_source": "tej", "expiry_conflict": False,
    })
    # TEJ sometimes splits one warrant across two ids (041993T, then 041993); use one id per
    # (exchange code, expiry) so tej_id does not change mid-life. Join TEJ daily data on
    # (exchange code, date), not on tej_id.
    key = ["warrant_id", "expiry_date"]
    assert (out.groupby("tej_id")["expiry_date"].nunique() <= 1).all(), "a TEJ id spans two expiries"
    assert (out.groupby(key)[["listing_date", "issuer"]].nunique() <= 1).all().all(), \
        "one (code, expiry) holds warrants with different listing dates or issuers"
    canon = (out.sort_values(["listing_date", "tej_id"], kind="mergesort")
                .drop_duplicates(["warrant_id", "expiry_date"]).set_index(["warrant_id", "expiry_date"])["tej_id"])
    out["tej_id"] = canon.reindex(pd.MultiIndex.from_frame(out[["warrant_id", "expiry_date"]])).to_numpy()
    return out


def combine(twse, tej, underlying=config.UNDERLYING):
    """One event table: TWSE events for warrants TWSE knows, TEJ events for the rest."""
    tj = _from_tej(tej, underlying)
    first_ev = tj.sort_values(["tej_id", "event_date", "event_seq"], kind="mergesort").drop_duplicates("tej_id")
    assert not first_ev.duplicated(["warrant_id", "expiry_date"]).any(), "TEJ ids not unique per (code, expiry)"
    ids = first_ev[["warrant_id", "expiry_date", "tej_id", "listing_date", "last_trade_date", "strike"]]
    ids = ids.rename(columns={"strike": "issue_strike"})
    tw = twse.drop(columns=[c for c in ("listing_date", "tej_id") if c in twse])
    tw_issue = (tw.sort_values(["warrant_id", "expiry_date", "event_seq"], kind="mergesort")
                  .drop_duplicates(["warrant_id", "expiry_date"])[["warrant_id", "expiry_date", "strike"]]
                  .rename(columns={"strike": "issue_strike"}))
    # 1) exact (code, expiry) match
    m = tw_issue.merge(ids.drop(columns="issue_strike"), on=["warrant_id", "expiry_date"], how="left")
    m["expiry_conflict"] = False
    # 2) code + issue strike, for TWSE warrants whose expiry TEJ records differently
    miss = m["tej_id"].isna()
    if miss.any():
        used = set(m["tej_id"].dropna())
        cand = ids[~ids["tej_id"].isin(used)].rename(columns={"expiry_date": "tej_expiry"})
        fb = m.loc[miss, ["warrant_id", "expiry_date", "issue_strike"]].merge(
            cand, on=["warrant_id", "issue_strike"], how="inner")
        # the TEJ warrant must still be alive at the TWSE snapshot (TWSE lists only live warrants);
        # otherwise an old warrant that used the same code and a round strike would be matched
        snap = pd.Timestamp(twse["snapshot_date"].max()) - pd.Timedelta(days=config.TWSE_SNAPSHOT_MARGIN_DAYS)
        fb = fb[(fb["tej_expiry"] >= snap) & (fb["listing_date"] <= fb["expiry_date"])]
        fb = fb.sort_values("listing_date", kind="mergesort").drop_duplicates(["warrant_id", "expiry_date"], keep="last")
        fb = fb.set_index(["warrant_id", "expiry_date"])
        key = pd.MultiIndex.from_frame(m[["warrant_id", "expiry_date"]])
        hit = miss & key.isin(fb.index)
        for c in ("tej_id", "listing_date", "last_trade_date"):
            m.loc[hit, c] = fb.loc[key[hit], c].to_numpy()
        m.loc[hit, "expiry_conflict"] = True
    m = m.drop(columns="issue_strike")
    tw = tw.merge(m, on=["warrant_id", "expiry_date"], how="left", suffixes=("", "_tej"))
    if "last_trade_date_tej" in tw:
        tw["last_trade_date"] = tw["last_trade_date"].fillna(tw.pop("last_trade_date_tej"))
    tw = tw.assign(terms_source="twse", event_seq=tw["event_seq"].astype("int64"))
    keep = ~tj["tej_id"].isin(set(tw["tej_id"].dropna()))
    in_twse = pd.MultiIndex.from_frame(tw[["warrant_id", "expiry_date"]].drop_duplicates())
    keep &= ~pd.MultiIndex.from_frame(tj[["warrant_id", "expiry_date"]]).isin(in_twse)
    out = pd.concat([tw[COLUMNS], tj.loc[keep, COLUMNS]], ignore_index=True)
    return out.sort_values(["warrant_id", "expiry_date", "event_date", "event_seq"], na_position="first",
                           kind="mergesort").reset_index(drop=True)


def dividend_dates(twse, min_warrants=config.DIVIDEND_MIN_WARRANTS):
    """Ex-dividend adjustment dates, as the most common TWSE adjustment date per quarter."""
    adj = twse[(twse["event"] == "除權息調整") & twse["event_date"].notna()]
    counts = adj.groupby(adj["event_date"].dt.to_period("Q"))["event_date"].agg(
        lambda s: (s.mode().iloc[0], int((s == s.mode().iloc[0]).sum())))
    return sorted(d for d, n in counts if n >= min_warrants)


def terms_on(terms, day, div_dates=()):
    """Terms valid on `day`, one row per exchange code (latest event on or before the day)."""
    day = pd.Timestamp(day)
    alive = terms[(terms["listing_date"].isna() | (terms["listing_date"] <= day)) & (terms["expiry_date"] >= day)
                  & (terms["event_date"].isna() | (terms["event_date"] <= day))]
    alive = alive.sort_values(["warrant_id", "expiry_date", "event_date", "event_seq"], na_position="first",
                              kind="mergesort")
    t = alive.groupby(["warrant_id", "expiry_date"], sort=False).tail(1)
    # a reused code: only one warrant can trade under it on a given day; keep the latest listing
    # (an unknown listing date counts as the oldest, so it never displaces a dated warrant)
    t = t.sort_values("listing_date", na_position="first", kind="mergesort").drop_duplicates("warrant_id", keep="last")
    stale = pd.Series(False, index=t.index)
    born = t["listing_date"].fillna(t["event_date"])
    for d in pd.to_datetime(list(div_dates)):
        if d > day:
            continue
        adjusted = alive.loc[alive["event_date"] == d, ["warrant_id", "expiry_date"]]
        has = pd.MultiIndex.from_frame(t[["warrant_id", "expiry_date"]]).isin(pd.MultiIndex.from_frame(adjusted))
        stale |= (born < d) & ~has
    t = t.assign(terms_stale=(t["terms_source"] == "tej") & stale)
    return t.reset_index(drop=True)


def load(data_dir, underlying=config.UNDERLYING):
    """(terms, div_dates) from ``<data>/twse/terms_2330.parquet`` and ``<data>/tej/terms_all.parquet``."""
    data_dir = Path(data_dir)
    twse = pd.read_parquet(data_dir / "twse" / f"terms_{underlying}.parquet")
    tej = pd.read_parquet(data_dir / "tej" / "terms_all.parquet")
    return combine(twse, tej, underlying), dividend_dates(twse)
