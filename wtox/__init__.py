"""wtox: pricing core and research pipeline for the Taiwan warrant flow-toxicity study.

Vectorised Black-Scholes / CRR pricing, Greeks and implied volatility (scalars or arrays),
with warrant helpers that scale by the exercise ratio. Adapted from the author's
Option-Analysis-System `optcore` package.
"""

from wtox.pricing import bs_price, crr_price
from wtox.greeks import bs_greeks
from wtox.iv import implied_vol
from wtox.warrant import warrant_price, warrant_iv, warrant_greeks

__all__ = [
    "bs_price",
    "crr_price",
    "bs_greeks",
    "implied_vol",
    "warrant_price",
    "warrant_iv",
    "warrant_greeks",
]
