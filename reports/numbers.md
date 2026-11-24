# 報告數字表（由 reports/make_numbers.py 自動產生，勿手改）

## 資料：覆蓋率（每月）

來源：`validation/coverage_months.parquet`

| months | min_month_coverage_tick | min_month | missing_warrant_days |
|---|---|---|---|
| 23 | 0.9921 | 2026-11 | 64 |

| min_cell_coverage_tick | min_cell |
|---|---|
| 0.9881 | 2026-11 >180 |


## 資料：成交當下報價缺失原因（全樣本）

來源：`validation/premid_missing_all.parquet`

| missing_reason | n | volume | share_n | share_volume |
|---|---|---|---|---|
| ok | 1394530 | 39927721 | 0.8916 | 0.9238 |
| no_side | 855 | 14669 | 0.000547 | 0.000339 |
| first_of_day | 39879 | 837504 | 0.0255 | 0.0194 |
| prev_stale | 99407 | 1957064 | 0.0636 | 0.0453 |
| other_side_invalid | 29328 | 483300 | 0.0188 | 0.0112 |


## 附錄 A：規則 A'' 驗證（2025）

來源：`validation/train2025/premid_*.parquet`

**premid_missing_all**

| missing_reason | n | volume | share_n | share_volume |
|---|---|---|---|---|
| ok | 552843 | 17330402 | 0.9009 | 0.9235 |
| no_side | 289 | 6227 | 0.000471 | 0.000332 |
| first_of_day | 18570 | 456951 | 0.0303 | 0.0244 |
| prev_stale | 32368 | 797527 | 0.0527 | 0.0425 |
| other_side_invalid | 9595 | 174396 | 0.0156 | 0.0093 |

**premid_other_side_agreement**

| n | share_equal |
|---|---|
| 269,515.0000 | 0.9304 |

**premid_reaction_test**

| side | n | moved | toward | against |
|---|---|---|---|---|
| buy | 11245 | 0.00649 | 0.00293 | 0.00356 |
| sell | 10840 | 0.00664 | 0.00203 | 0.00461 |

**premid_sweep_check**

| n_fills | n_below_quoted | n_worse_price | n_worse_not_above | n_quoted_nonpositive |
|---|---|---|---|---|
| 552843 | 0 | 3662 | 0 | 0 |


## 資料：可用樣本（2025）

來源：`stage3/exclusions.parquet`

| cut | group | n | share_kept_n | share_kept_notional |
|---|---|---|---|---|
| all | all | 613665 | 0.8980 | 0.9137 |
| direction | buy | 327742 | 0.9435 | 0.9410 |
| direction | sell | 285634 | 0.8467 | 0.8872 |
| direction | unflagged | 289 | 0.0000 | 0.0000 |
| dte_bucket | 1–30 | 17688 | 0.7299 | 0.7180 |
| dte_bucket | 31–90 | 109315 | 0.8886 | 0.9006 |
| dte_bucket | 91–180 | 238090 | 0.8989 | 0.9218 |
| dte_bucket | >180 | 248572 | 0.9133 | 0.9216 |
| size_bucket | 1–10 | 391584 | 0.8867 | 0.8667 |
| size_bucket | 11–50 | 140237 | 0.9124 | 0.9116 |
| size_bucket | 51–100 | 44358 | 0.9252 | 0.9208 |
| size_bucket | >100 | 37486 | 0.9302 | 0.9342 |
| tod | 09:00–09:30 | 185242 | 0.8861 | 0.9070 |
| tod | 09:30–12:30 | 303848 | 0.9030 | 0.9168 |
| tod | 12:30–13:25 | 124575 | 0.9034 | 0.9153 |


## 資料：delta 正負號

來源：`validation/delta_sign.parquet`

| kind | n | n_bad |
|---|---|---|
| call | 1223658 | 0 |
| put | 165993 | 0 |


## 資料：時鐘領先落後（合併相關峰值，100 ms 與 10 ms 格點）

來源：`validation/clock_lead_lag*.parquet`

| file | pooled_peak_lag_s | daily_peak_median_s | days_peak_negative | n_days |
|---|---|---|---|---|
| clock_lead_lag | 0.000 | 0.100 | 22 | 451 |

| file | pooled_peak_lag_s | daily_peak_median_s | days_peak_negative | n_days |
|---|---|---|---|---|
| clock_lead_lag_fine | 0.030 | 0.030 | 67 | 451 |


## H1：價差拆解與淨收益（2025，全部）

來源：`stage3/decomposition.parquet`

| value | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|
| ES | 153.1 | 5.6 | 27.2 | 1.22e-75 | 524327 | 243 |
| RS_5m | 126.3 | 5.9 | 21.4 | 1.38e-57 | 524327 | 243 |
| PI_5m | 26.8 | 1.3 | 20.3 | 3.62e-54 | 524327 | 243 |
| M_5m | 26.8 | 1.3 | 20.2 | 6.67e-54 | 524327 | 243 |
| RS_dt_5m | 127.7 | 6.0 | 21.4 | 6.78e-58 | 524327 | 243 |
| PI_dt_5m | 25.4 | 1.3 | 19.3 | 9.44e-51 | 524327 | 243 |
| M_dt_5m | 25.4 | 1.3 | 19.2 | 1.75e-50 | 524327 | 243 |
| cost_pessimistic | 207.2 | 3.5 | 59.4 | 2.53e-146 | 524327 | 243 |
| cost_neutral | 101.9 | 2.3 | 45.0 | 1.16e-119 | 524327 | 243 |
| cost_optimistic | 33.4 | 1.4 | 23.5 | 1.55e-64 | 524327 | 243 |
| net_pessimistic | -79.5 | 7.3 | -10.9 | 9.6e-23 | 524327 | 243 |
| net_neutral | 25.8 | 6.7 | 3.9 | 0.00014 | 524327 | 243 |
| net_optimistic | 94.3 | 6.3 | 15.0 | 2.73e-36 | 524327 | 243 |


## H1：按方向與四象限（中性淨收益、ES、M_dt）

來源：`stage3/decomposition.parquet`

| cut | group | value | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|---|---|
| direction | buy | ES | 175.9 | 8.3 | 21.1 | 1.1e-56 | 295955 | 243 |
| direction | buy | M_dt_5m | 23.9 | 1.8 | 13.3 | 8.18e-31 | 295955 | 243 |
| direction | buy | net_neutral | 47.7 | 9.7 | 4.9 | 1.52e-06 | 295955 | 243 |
| direction | sell | ES | 128.6 | 5.5 | 23.5 | 2.25e-64 | 228372 | 243 |
| direction | sell | M_dt_5m | 26.9 | 1.9 | 14.0 | 4.51e-33 | 228372 | 243 |
| direction | sell | net_neutral | 2.4 | 7.3 | 0.3 | 0.7451 | 228372 | 243 |
| quadrant | buy_call | ES | 180.2 | 9.8 | 18.4 | 7.48e-48 | 242901 | 243 |
| quadrant | buy_call | M_dt_5m | 21.7 | 2.1 | 10.3 | 6.73e-21 | 242901 | 243 |
| quadrant | buy_call | net_neutral | 52.3 | 11.3 | 4.7 | 5.41e-06 | 242901 | 243 |
| quadrant | buy_put | ES | 155.8 | 11.9 | 13.1 | 4.32e-30 | 53054 | 243 |
| quadrant | buy_put | M_dt_5m | 34.7 | 4.6 | 7.5 | 1.29e-12 | 53054 | 243 |
| quadrant | buy_put | net_neutral | 25.5 | 14.5 | 1.8 | 0.0801 | 53054 | 243 |
| quadrant | sell_call | ES | 124.1 | 4.9 | 25.5 | 1.44e-70 | 192505 | 243 |
| quadrant | sell_call | M_dt_5m | 26.6 | 2.2 | 11.9 | 5.27e-26 | 192505 | 243 |
| quadrant | sell_call | net_neutral | -4.0 | 6.9 | -0.6 | 0.5598 | 192505 | 243 |
| quadrant | sell_put | ES | 154.9 | 14.3 | 10.8 | 1.41e-22 | 35867 | 243 |
| quadrant | sell_put | M_dt_5m | 28.9 | 3.6 | 8.0 | 3.94e-14 | 35867 | 243 |
| quadrant | sell_put | net_neutral | 39.5 | 15.9 | 2.5 | 0.0136 | 35867 | 243 |


## H1：等權重

來源：`stage3/decomposition_equal.parquet`

| value | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|
| ES | 246.3 | 12.5 | 19.8 | 2.25e-52 | 524327 | 243 |
| M_dt_5m | 19.0 | 1.2 | 15.7 | 1.19e-38 | 524327 | 243 |
| net_neutral | 126.0 | 14.0 | 9.0 | 6.4e-17 | 524327 | 243 |


## H1：鎖死日敏感度

來源：`extension/locked_sensitivity_2025.parquet`

| sample | value | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|---|
| all | ES | 153.1 | 5.6 | 27.2 | 1.22e-75 | 524327 | 243 |
| all | RS_dt_5m | 127.7 | 6.0 | 21.4 | 6.78e-58 | 524327 | 243 |
| all | M_dt_5m | 25.4 | 1.3 | 19.2 | 1.75e-50 | 524327 | 243 |
| all | cost_pessimistic | 207.2 | 3.5 | 59.4 | 2.53e-146 | 524327 | 243 |
| all | cost_neutral | 101.9 | 2.3 | 45.0 | 1.16e-119 | 524327 | 243 |
| all | cost_optimistic | 33.4 | 1.4 | 23.5 | 1.55e-64 | 524327 | 243 |
| all | net_pessimistic | -79.5 | 7.3 | -10.9 | 9.6e-23 | 524327 | 243 |
| all | net_neutral | 25.8 | 6.7 | 3.9 | 0.00014 | 524327 | 243 |
| all | net_optimistic | 94.3 | 6.3 | 15.0 | 2.73e-36 | 524327 | 243 |
| excl_locked | ES | 149.1 | 4.9 | 30.3 | 4.9e-84 | 517311 | 241 |
| excl_locked | RS_dt_5m | 123.6 | 5.2 | 23.6 | 2.47e-64 | 517311 | 241 |
| excl_locked | M_dt_5m | 25.5 | 1.3 | 19.2 | 1.7e-50 | 517311 | 241 |
| excl_locked | cost_pessimistic | 207.4 | 3.5 | 59.2 | 3.04e-145 | 517311 | 241 |
| excl_locked | cost_neutral | 102.0 | 2.3 | 44.9 | 7.96e-119 | 517311 | 241 |
| excl_locked | cost_optimistic | 33.4 | 1.4 | 23.5 | 4.33e-64 | 517311 | 241 |
| excl_locked | net_pessimistic | -83.8 | 6.7 | -12.6 | 4.06e-28 | 517311 | 241 |
| excl_locked | net_neutral | 21.6 | 6.0 | 3.6 | 0.000397 | 517311 | 241 |
| excl_locked | net_optimistic | 90.2 | 5.6 | 16.0 | 7.87e-40 | 517311 | 241 |
| locked_only | ES | 964.6 | 32.3 | 29.9 | 0.0213 | 7016 | 2 |
| locked_only | RS_dt_5m | 964.7 | 32.3 | 29.9 | 0.0213 | 7016 | 2 |
| locked_only | M_dt_5m | 0.0 | 0.0 |  |  | 7016 | 2 |
| locked_only | cost_pessimistic | 170.8 | 7.0 | 24.5 | 0.0260 | 7016 | 2 |
| locked_only | cost_neutral | 77.9 | 11.3 | 6.9 | 0.0913 | 7016 | 2 |
| locked_only | cost_optimistic | 24.7 | 5.1 | 4.8 | 0.1304 | 7016 | 2 |
| locked_only | net_pessimistic | 793.9 | 25.3 | 31.4 | 0.0203 | 7016 | 2 |
| locked_only | net_neutral | 886.8 | 21.0 | 42.1 | 0.0151 | 7016 | 2 |
| locked_only | net_optimistic | 940.0 | 27.2 | 34.6 | 0.0184 | 7016 | 2 |


## H2：主要切法 M_dt(5m)

來源：`stage3/decomposition.parquet`

| cut | group | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|---|
| direction | buy | 23.9 | 1.8 | 13.3 | 8.18e-31 | 295955 | 243 |
| direction | sell | 26.9 | 1.9 | 14.0 | 4.51e-33 | 228372 | 243 |
| quadrant | buy_call | 21.7 | 2.1 | 10.3 | 6.73e-21 | 242901 | 243 |
| quadrant | buy_put | 34.7 | 4.6 | 7.5 | 1.29e-12 | 53054 | 243 |
| quadrant | sell_call | 26.6 | 2.2 | 11.9 | 5.27e-26 | 192505 | 243 |
| quadrant | sell_put | 28.9 | 3.6 | 8.0 | 3.94e-14 | 35867 | 243 |
| delta_bucket | <0.2 | 34.5 | 2.7 | 12.8 | 5.62e-29 | 105364 | 243 |
| delta_bucket | 0.2–0.4 | 30.8 | 1.8 | 16.9 | 6.46e-43 | 130792 | 243 |
| delta_bucket | 0.4–0.6 | 23.4 | 1.5 | 16.0 | 1.21e-39 | 168473 | 243 |
| delta_bucket | >0.6 | 19.7 | 1.4 | 14.3 | 5.14e-34 | 119698 | 243 |
| dte_bucket | 1–30 | 49.4 | 10.2 | 4.8 | 2.54e-06 | 12249 | 243 |
| dte_bucket | 31–90 | 32.9 | 2.9 | 11.4 | 2.41e-24 | 92558 | 243 |
| dte_bucket | 91–180 | 29.9 | 1.5 | 20.3 | 4.51e-54 | 202990 | 243 |
| dte_bucket | >180 | 17.0 | 1.1 | 16.1 | 5.61e-40 | 216530 | 243 |
| size_bucket | 1–10 | 20.6 | 1.1 | 17.9 | 3.49e-46 | 331035 | 243 |
| size_bucket | 11–50 | 26.7 | 1.5 | 17.9 | 2.3e-46 | 122067 | 243 |
| size_bucket | 51–100 | 26.6 | 2.3 | 11.4 | 1.88e-24 | 38417 | 243 |
| size_bucket | >100 | 26.0 | 1.8 | 14.8 | 7.09e-36 | 32808 | 243 |
| spot_1s | favourable | 26.9 | 4.3 | 6.3 | 1.27e-09 | 59561 | 239 |
| spot_1s | none | 25.1 | 1.2 | 20.4 | 1.63e-54 | 460337 | 243 |
| spot_1s | adverse | 16.1 | 13.0 | 1.2 | 0.2159 | 4379 | 199 |
| tod | 09:00–09:30 | 34.5 | 3.1 | 11.2 | 1.02e-23 | 164135 | 243 |
| tod | 09:30–12:30 | 23.8 | 1.8 | 13.3 | 1.34e-30 | 274387 | 243 |
| tod | 12:30–13:25 | 13.8 | 2.1 | 6.7 | 1.55e-10 | 85805 | 243 |


## H2：|delta| × 到期天數（M_dt 與中性淨收益）

來源：`stage3/delta_dte.parquet`

| delta_bucket | dte_bucket | value | mean_bps | se_bps | p | p_bh | n | pre_specified |
|---|---|---|---|---|---|---|---|---|
| <0.2 | 1–30 | M_dt_5m | 39.7 | 29.5 | 0.1786 | 0.1786 | 3810 | False |
| <0.2 | 1–30 | net_neutral | 665.9 | 135.8 | 1.84e-06 | 2.76e-05 | 3810 | False |
| <0.2 | 31–90 | M_dt_5m | 42.0 | 6.7 | 1.56e-09 | 2.34e-09 | 28972 | False |
| <0.2 | 31–90 | net_neutral | 151.9 | 32.4 | 4.58e-06 | 3.44e-05 | 28972 | False |
| <0.2 | 91–180 | M_dt_5m | 39.2 | 3.0 | 3.67e-30 | 1.38e-29 | 48794 | False |
| <0.2 | 91–180 | net_neutral | 64.5 | 17.9 | 0.000393 | 0.0012 | 48794 | False |
| <0.2 | >180 | M_dt_5m | 19.5 | 3.2 | 5.62e-09 | 7.66e-09 | 23788 | False |
| <0.2 | >180 | net_neutral | 101.2 | 22.2 | 8.54e-06 | 4.27e-05 | 23788 | False |
| 0.2–0.4 | 1–30 | M_dt_5m | 54.2 | 26.4 | 0.0412 | 0.0441 | 1956 | False |
| 0.2–0.4 | 1–30 | net_neutral | 50.3 | 66.8 | 0.4518 | 0.4841 | 1956 | False |
| 0.2–0.4 | 31–90 | M_dt_5m | 28.3 | 5.4 | 4.24e-07 | 5.3e-07 | 21966 | False |
| 0.2–0.4 | 31–90 | net_neutral | 83.2 | 39.1 | 0.0342 | 0.0656 | 21966 | False |
| 0.2–0.4 | 91–180 | M_dt_5m | 35.0 | 2.3 | 8.38e-38 | 6.28e-37 | 59537 | False |
| 0.2–0.4 | 91–180 | net_neutral | -12.0 | 10.6 | 0.2603 | 0.3550 | 59537 | False |
| 0.2–0.4 | >180 | M_dt_5m | 25.8 | 1.7 | 9.81e-36 | 4.9e-35 | 47333 | False |
| 0.2–0.4 | >180 | net_neutral | 39.3 | 18.5 | 0.0350 | 0.0656 | 47333 | False |
| 0.4–0.6 | 1–30 | M_dt_5m | 81.5 | 31.3 | 0.0098 |  | 1960 | True |
| 0.4–0.6 | 1–30 | net_neutral | -123.8 | 43.5 | 0.0049 |  | 1960 | True |
| 0.4–0.6 | 31–90 | M_dt_5m | 36.6 | 4.2 | 2.55e-16 | 4.24e-16 | 21005 | False |
| 0.4–0.6 | 31–90 | net_neutral | 36.0 | 28.0 | 0.1994 | 0.2991 | 21005 | False |
| 0.4–0.6 | 91–180 | M_dt_5m | 26.6 | 1.7 | 1.62e-38 | 2.43e-37 | 60182 | False |
| 0.4–0.6 | 91–180 | net_neutral | -5.0 | 10.6 | 0.6370 | 0.6370 | 60182 | False |
| 0.4–0.6 | >180 | M_dt_5m | 14.7 | 1.3 | 1.82e-25 | 5.47e-25 | 85326 | False |
| 0.4–0.6 | >180 | net_neutral | 22.6 | 8.2 | 0.0062 | 0.0154 | 85326 | False |
| >0.6 | 1–30 | M_dt_5m | 38.8 | 8.6 | 8.85e-06 | 1.02e-05 | 4523 | False |
| >0.6 | 1–30 | net_neutral | 19.8 | 21.2 | 0.3511 | 0.4389 | 4523 | False |
| >0.6 | 31–90 | M_dt_5m | 28.5 | 3.2 | 8.56e-17 | 1.6e-16 | 20615 | False |
| >0.6 | 31–90 | net_neutral | 23.7 | 12.5 | 0.0587 | 0.0979 | 20615 | False |
| >0.6 | 91–180 | M_dt_5m | 22.1 | 1.9 | 3.27e-24 | 8.17e-24 | 34477 | False |
| >0.6 | 91–180 | net_neutral | 6.8 | 7.9 | 0.3894 | 0.4493 | 34477 | False |
| >0.6 | >180 | M_dt_5m | 13.5 | 1.3 | 2.88e-21 | 6.16e-21 | 60083 | False |
| >0.6 | >180 | net_neutral | 24.0 | 6.2 | 0.000135 | 0.000507 | 60083 | False |


## H2：markout 曲線（未去趨勢與去趨勢）

來源：`stage3/curves.parquet`

| grp | 1s | 5s | 10s | 30s | 1m | 5m | 30m | close |
|---|---|---|---|---|---|---|---|---|
| all:all | 8.0 | 11.1 | 12.3 | 15.1 | 18.1 | 26.8 | 37.3 | 49.0 |
| delta_bucket:<0.2 | 8.1 | 12.4 | 14.3 | 18.4 | 22.8 | 36.0 | 45.5 | 56.7 |
| delta_bucket:>0.6 | 6.9 | 9.3 | 10.2 | 12.2 | 14.4 | 21.0 | 30.1 | 40.7 |
| dte_bucket:1–30 | 18.2 | 25.1 | 27.0 | 29.6 | 35.3 | 50.1 | 50.3 | 38.7 |
| dte_bucket:>180 | 5.1 | 7.1 | 8.1 | 10.0 | 12.0 | 18.0 | 24.4 | 33.5 |
| size_bucket:1–10 | 4.1 | 6.0 | 7.2 | 9.9 | 12.3 | 21.3 | 30.9 | 39.0 |
| size_bucket:>100 | 9.1 | 12.2 | 13.4 | 16.1 | 19.4 | 28.0 | 39.2 | 57.2 |
| spot_1s:favourable | 21.1 | 24.8 | 25.0 | 26.4 | 28.3 | 31.1 | 36.8 | 51.1 |
| spot_1s:none | 4.8 | 7.6 | 9.2 | 12.2 | 15.6 | 25.8 | 37.0 | 48.3 |

| grp | 1s | 5s | 10s | 30s | 1m | 5m | 30m | close |
|---|---|---|---|---|---|---|---|---|
| all:all | 8.0 | 11.0 | 12.2 | 14.9 | 17.8 | 25.4 | 29.6 | -4.7 |
| delta_bucket:<0.2 | 8.2 | 12.4 | 14.3 | 18.3 | 22.5 | 34.5 | 38.5 | -10.5 |
| delta_bucket:>0.6 | 6.8 | 9.3 | 10.2 | 12.1 | 14.1 | 19.7 | 23.4 | -2.7 |
| dte_bucket:1–30 | 18.1 | 25.0 | 26.8 | 29.3 | 35.1 | 49.4 | 46.6 | -12.5 |
| dte_bucket:>180 | 5.1 | 7.1 | 8.1 | 9.9 | 11.8 | 17.0 | 19.1 | -2.0 |
| size_bucket:1–10 | 4.1 | 6.0 | 7.2 | 9.8 | 12.2 | 20.6 | 27.5 | 3.8 |
| size_bucket:>100 | 9.0 | 12.1 | 13.3 | 16.0 | 19.0 | 26.0 | 28.6 | -6.6 |
| spot_1s:favourable | 21.0 | 24.7 | 24.9 | 25.9 | 27.4 | 26.9 | 12.1 | -93.3 |
| spot_1s:none | 4.8 | 7.6 | 9.1 | 12.2 | 15.4 | 25.1 | 33.7 | 16.6 |


## 截短（2025，可算指標的成交）

來源：`stage3/truncation.parquet`

| horizon | n | share_truncated |
|---|---|---|
| 1s | 551069 | 0.0017 |
| 5s | 551069 | 0.0107 |
| 10s | 551069 | 0.0119 |
| 30s | 551069 | 0.0162 |
| 1m | 551069 | 0.0218 |
| 5m | 551069 | 0.0485 |
| 30m | 551069 | 0.1406 |
| close | 551069 | 0.0000 |


## H3：發行商（組成控制後）

來源：`stage4/h3_issuers.parquet`

| term | coef | se | t | p | n | n_days | issuer | half_spread_bps | spearman_rho | spearman_p | base_issuer |
|---|---|---|---|---|---|---|---|---|---|---|---|
| iss_中信 | -3.8 | 3.1 | -1.3 | 0.2111 | 12816 | 243.0 | 中信 | 88.3 | 0.0110 | 0.9716 | 元大 |
| iss_元富 | 5.1 | 3.2 | 1.6 | 0.1158 | 32636 | 243.0 | 元富 | 164.1 | 0.0110 | 0.9716 | 元大 |
| iss_兆豐 | 36.2 | 10.0 | 3.6 | 0.000378 | 1352 | 243.0 | 兆豐 | 188.0 | 0.0110 | 0.9716 | 元大 |
| iss_凱基 | -6.0 | 2.3 | -2.6 | 0.0088 | 95524 | 243.0 | 凱基 | 246.8 | 0.0110 | 0.9716 | 元大 |
| iss_台新 | -3.0 | 6.7 | -0.4 | 0.6535 | 1423 | 243.0 | 台新 | 131.3 | 0.0110 | 0.9716 | 元大 |
| iss_國泰 | 19.9 | 4.1 | 4.9 | 2.14e-06 | 12487 | 243.0 | 國泰 | 103.6 | 0.0110 | 0.9716 | 元大 |
| iss_國票 | 3.7 | 4.5 | 0.8 | 0.4107 | 18714 | 243.0 | 國票 | 133.2 | 0.0110 | 0.9716 | 元大 |
| iss_富邦 | 5.8 | 5.0 | 1.2 | 0.2484 | 21257 | 243.0 | 富邦 | 249.8 | 0.0110 | 0.9716 | 元大 |
| iss_永豐 | 1.9 | 3.5 | 0.5 | 0.5904 | 41004 | 243.0 | 永豐 | 130.5 | 0.0110 | 0.9716 | 元大 |
| iss_第一 | -26.1 | 6.8 | -3.9 | 0.000145 | 170 | 243.0 | 第一 | 650.3 | 0.0110 | 0.9716 | 元大 |
| iss_統一 | -3.2 | 2.3 | -1.4 | 0.1749 | 82468 | 243.0 | 統一 | 115.2 | 0.0110 | 0.9716 | 元大 |
| iss_群益 | 1.1 | 2.5 | 0.4 | 0.6658 | 53391 | 243.0 | 群益 | 142.9 | 0.0110 | 0.9716 | 元大 |
| base | 0.0 |  |  |  | 151085 |  | 元大 | 126.3 | 0.0110 | 0.9716 | 元大 |


## H4：迴歸（2025）

來源：`stage3/h4_regressions.parquet`

| horizon | spec | term | main | coef | se | p | p_bh | n | n_days |
|---|---|---|---|---|---|---|---|---|---|
| 5m | all | F_norm | True | 23.03 | 8.64 | 0.0082 |  | 56863 | 223 |
| 5m | call_put | F_call_norm | False | 23.53 | 9.09 | 0.0103 | 0.0277 | 56863 | 223 |
| 5m | call_put | F_put_norm | False | 18.18 | 28.97 | 0.5308 | 0.5308 | 56863 | 223 |
| 1m | all | F_norm | False | 6.44 | 2.42 | 0.0084 | 0.0277 | 56863 | 223 |
| 1m | call_put | F_call_norm | False | 6.04 | 2.40 | 0.0126 | 0.0277 | 56863 | 223 |
| 1m | call_put | F_put_norm | False | 10.30 | 9.67 | 0.2879 | 0.3167 | 56863 | 223 |
| 30m | all | F_norm | False | 53.31 | 16.43 | 0.0014 | 0.0097 | 51288 | 223 |
| 30m | call_put | F_call_norm | False | 51.21 | 16.18 | 0.0018 | 0.0097 | 51288 | 223 |
| 30m | call_put | F_put_norm | False | 74.54 | 56.70 | 0.1900 | 0.2612 | 51288 | 223 |
| close | all | F_norm | False | 98.24 | 53.13 | 0.0658 | 0.1206 | 56863 | 223 |
| close | call_put | F_call_norm | False | 95.41 | 60.12 | 0.1139 | 0.1790 | 56863 | 223 |
| close | call_put | F_put_norm | False | 125.42 | 116.44 | 0.2826 | 0.3167 | 56863 | 223 |

| F_norm_sd_2025_all_grid | n |
|---|---|
| 0.0229 | 57088 |

| term | coef | se | t | p |
|---|---|---|---|---|
| const | -0.588 | 0.650 | -0.905 | 0.3663 |
| ret_past_bps | -0.141 | 0.021 | -6.695 | 1.74e-10 |
| signed_norm | 1.105 | 0.152 | 7.273 | 5.98e-12 |


## H4：流量相關

來源：`stage3/h4_flow_correlations.parquet`

| index | F_norm | ret_past | signed_norm |
|---|---|---|---|
| F_norm | 1.000 | 0.394 | 0.447 |
| ret_past | 0.394 | 1.000 | 0.554 |
| signed_norm | 0.447 | 0.554 | 1.000 |


## 散戶延遲套利上限（現貨剛有利）

來源：`stage3/retail_latency.parquet`

| direction | value | horizon | mean_bps | se_bps | n |
|---|---|---|---|---|---|
| buy | gross | 1s | -96.1 | 6.6 | 32131 |
| buy | gross_roundtrip | 1s | -214.4 | 12.3 | 32131 |
| buy | net_roundtrip | 1s | -252.9 | 12.3 | 32131 |
| sell | gross | 1s | -76.5 | 4.1 | 29001 |
| sell | gross_roundtrip | 1s | -172.8 | 7.2 | 29001 |
| sell | net_roundtrip | 1s | -211.3 | 7.2 | 29001 |
| buy | gross | 5s | -93.2 | 6.8 | 32127 |
| buy | gross_roundtrip | 5s | -211.5 | 12.3 | 32127 |
| buy | net_roundtrip | 5s | -250.0 | 12.3 | 32127 |
| sell | gross | 5s | -71.9 | 4.3 | 28893 |
| sell | gross_roundtrip | 5s | -168.3 | 7.3 | 28893 |
| sell | net_roundtrip | 5s | -206.8 | 7.3 | 28893 |
| buy | gross | 10s | -93.6 | 6.8 | 31978 |
| buy | gross_roundtrip | 10s | -211.8 | 12.4 | 31978 |
| buy | net_roundtrip | 10s | -250.3 | 12.4 | 31978 |
| sell | gross | 10s | -70.8 | 4.4 | 28880 |
| sell | gross_roundtrip | 10s | -167.2 | 7.4 | 28880 |
| sell | net_roundtrip | 10s | -205.7 | 7.4 | 28880 |
| buy | gross | 30s | -92.6 | 6.9 | 31908 |
| buy | gross_roundtrip | 30s | -210.8 | 12.3 | 31908 |
| buy | net_roundtrip | 30s | -249.3 | 12.3 | 31908 |
| sell | gross | 30s | -69.1 | 4.3 | 28835 |
| sell | gross_roundtrip | 30s | -165.5 | 7.3 | 28835 |
| sell | net_roundtrip | 30s | -204.0 | 7.3 | 28835 |
| buy | gross | 1m | -91.3 | 7.7 | 31762 |
| buy | gross_roundtrip | 1m | -209.5 | 13.0 | 31762 |
| buy | net_roundtrip | 1m | -248.0 | 13.0 | 31762 |
| sell | gross | 1m | -66.6 | 4.6 | 28615 |
| sell | gross_roundtrip | 1m | -163.1 | 7.5 | 28615 |
| sell | net_roundtrip | 1m | -201.6 | 7.5 | 28615 |
| buy | gross | 5m | -90.1 | 8.8 | 31512 |
| buy | gross_roundtrip | 5m | -208.4 | 14.0 | 31512 |
| buy | net_roundtrip | 5m | -246.9 | 14.0 | 31512 |
| sell | gross | 5m | -61.4 | 5.9 | 28049 |
| sell | gross_roundtrip | 5m | -157.5 | 8.5 | 28049 |
| sell | net_roundtrip | 5m | -196.0 | 8.5 | 28049 |
| buy | gross | 30m | -88.6 | 11.1 | 29495 |
| buy | gross_roundtrip | 30m | -206.5 | 15.6 | 29495 |
| buy | net_roundtrip | 30m | -245.0 | 15.6 | 29495 |
| sell | gross | 30m | -49.7 | 12.3 | 25723 |
| sell | gross_roundtrip | 30m | -145.5 | 14.5 | 25723 |
| sell | net_roundtrip | 30m | -184.0 | 14.5 | 25723 |
| buy | gross | close | -78.3 | 22.4 | 32135 |
| buy | gross_roundtrip | close | -196.6 | 25.0 | 32135 |
| buy | net_roundtrip | close | -235.1 | 25.0 | 32135 |
| sell | gross | close | -31.9 | 24.9 | 29005 |
| sell | gross_roundtrip | close | -128.2 | 25.7 | 29005 |
| sell | net_roundtrip | close | -166.7 | 25.7 | 29005 |


## 2330 股價與現股價差（所有 panel 成交的簡單中位數）

來源：`panel/tsmc_warrant_trades（S_mid、S_spread_bps）`

| year | n_files | median_S_mid | median_S_spread_bps |
|---|---|---|---|
| 2025 | 243 | 1,102.5 | 35.5 |
| 2026 | 210 | 2,257.5 | 22.4 |


## 表 1：敘述統計（panel 全部成交；|delta| 只計有 delta 的成交）

來源：`panel/tsmc_warrant_trades`

| item | 2025 | 2026 |
|---|---|---|
| days | 243.000 | 210.000 |
| trades | 613,665.000 | 950,334.000 |
| notional_billion_twd | 20.119 | 34.798 |
| warrants | 3,367.000 | 2,511.000 |
| issuers | 13.000 | 12.000 |
| call_share_notional | 0.834 | 0.962 |
| buy_share_notional | 0.494 | 0.472 |
| dte_1–30_share | 0.023 | 0.030 |
| dte_31–90_share | 0.160 | 0.113 |
| dte_91–180_share | 0.408 | 0.358 |
| dte_>180_share | 0.409 | 0.499 |
| delta_<0.2_share | 0.117 | 0.051 |
| delta_0.2–0.4_share | 0.242 | 0.231 |
| delta_0.4–0.6_share | 0.352 | 0.413 |
| delta_>0.6_share | 0.288 | 0.304 |


## 安慰劑：同日置換

來源：`stage4/placebo_permutation.parquet`

| actual_bps | expected_bps | perm_mean_bps | perm_p95_bps | p_one_sided | B |
|---|---|---|---|---|---|
| 25.366 | 1.914 | 1.947 | 2.651 | 0.0050 | 200 |


## 安慰劑：隨機時點

來源：`stage4/placebo_random_time.parquet`

| value | mean_bps | se_bps | t | p | n | n_days | variant |
|---|---|---|---|---|---|---|---|
| M_rand | 0.00171 | 0.370 | 0.00463 | 0.9963 | 540493 | 243 | random_time |


## 現貨剛成交（S_age ≤ 0.1 秒）

來源：`stage4/staleness.parquet`

| spot_print | direction | value | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|---|---|
| just_ticked | buy | M_dt_5m | 43.7 | 4.7 | 9.2 | 1.45e-17 | 60142 | 243 |
| just_ticked | buy | net_neutral | -21.3 | 11.2 | -1.9 | 0.0588 | 60142 | 243 |
| just_ticked | sell | M_dt_5m | 43.9 | 4.3 | 10.3 | 9.65e-21 | 46369 | 243 |
| just_ticked | sell | net_neutral | -40.9 | 8.7 | -4.7 | 4.26e-06 | 46369 | 243 |
| quiet | buy | M_dt_5m | 14.8 | 1.3 | 11.2 | 9.51e-24 | 235813 | 243 |
| quiet | buy | net_neutral | 79.6 | 11.3 | 7.1 | 1.85e-11 | 235813 | 243 |
| quiet | sell | M_dt_5m | 20.4 | 1.5 | 13.3 | 1.22e-30 | 182003 | 243 |
| quiet | sell | net_neutral | 19.0 | 7.6 | 2.5 | 0.0132 | 182003 | 243 |


## 動能

來源：`stage4/momentum.parquet`

| term | coef | se | t | p | n | n_days | group |
|---|---|---|---|---|---|---|---|
| const | 26.723 | 1.251 | 21.354 | 1.37e-57 | 488046 | 243 | all |
| own_ret_1m_bps | -0.00624 | 0.020 | -0.313 | 0.7543 | 488046 | 243 | all |
| own_ret_5m_bps | -0.070 | 0.019 | -3.767 | 0.000208 | 488046 | 243 | all |
| const | 25.599 | 1.776 | 14.412 | 2.05e-34 | 279304 | 243 | buy |
| own_ret_1m_bps | -0.013 | 0.027 | -0.485 | 0.6285 | 279304 | 243 | buy |
| own_ret_5m_bps | -0.071 | 0.021 | -3.446 | 0.000671 | 279304 | 243 | buy |
| const | 27.984 | 1.718 | 16.286 | 9.14e-41 | 208742 | 243 | sell |
| own_ret_1m_bps | 0.000932 | 0.024 | 0.039 | 0.9691 | 208742 | 243 | sell |
| own_ret_5m_bps | -0.068 | 0.023 | -2.957 | 0.0034 | 208742 | 243 | sell |


## 穩健性變體

來源：`stage4/variants.parquet`

| variant | value | delta_bucket | mean_bps | se_bps | p | base_bps | robust |
|---|---|---|---|---|---|---|---|
| exclude_open_close | M_dt_5m |  | 24.9 | 1.3 | 1.32e-49 | 25.4 | True |
| exclude_open_close | net_neutral |  | 22.0 | 6.5 | 0.000792 | 25.8 | True |
| risk_free_0.010 | M_dt_5m |  | 25.3 | 1.3 | 1.63e-50 | 25.4 | True |
| risk_free_0.010 | net_neutral |  | 26.1 | 6.7 | 0.000115 | 25.8 | True |
| risk_free_0.020 | M_dt_5m |  | 25.4 | 1.3 | 1.7e-50 | 25.4 | True |
| risk_free_0.020 | net_neutral |  | 25.0 | 6.7 | 0.00023 | 25.8 | True |
| q_unprotected | M_dt_5m |  | 25.1 | 1.3 | 1.45e-50 | 25.4 | True |
| q_unprotected | net_neutral |  | 27.5 | 6.6 | 4.7e-05 | 25.8 | True |
| spot_quote_only | M_dt_5m |  | 25.5 | 1.3 | 1.7e-50 | 25.4 | True |
| spot_quote_only | net_neutral |  | 21.6 | 6.0 | 0.000397 | 25.8 | True |
| stock_hedge_tax_0.003 | M_dt_5m |  | 25.4 | 1.3 | 1.75e-50 | 25.4 | True |
| stock_hedge_tax_0.003 | net_neutral |  | -10.4 | 6.8 | 0.1260 | 25.8 | False |
| counterparty_issuer_like | M_dt_5m |  | 15.7 | 2.9 | 1.97e-07 | 25.4 | False |
| counterparty_issuer_like | net_neutral |  | 213.6 | 47.8 | 1.21e-05 | 25.8 | False |
| counterparty_drop_retail_like | M_dt_5m |  | 25.4 | 1.3 | 2.01e-50 | 25.4 | True |
| counterparty_drop_retail_like | net_neutral |  | 26.0 | 6.7 | 0.000127 | 25.8 | True |
| coverage_days | M_dt_5m |  | 25.4 | 1.3 | 1.75e-50 | 25.4 | True |
| coverage_days | net_neutral |  | 25.8 | 6.7 | 0.00014 | 25.8 | True |
| spot_move_5s | M_dt_5m |  | 24.6 | 4.1 | 7.08e-09 | 26.9 | True |
| spot_move_5s | net_neutral |  | -20.9 | 8.1 | 0.0100 | -40.2 | False |
| spot_move_5s | M_dt_5m |  | 25.6 | 1.3 | 1.42e-53 | 25.1 | True |
| spot_move_5s | net_neutral |  | 37.1 | 7.4 | 1.09e-06 | 40.9 | True |
| spot_move_5s | M_dt_5m |  | 23.9 | 9.5 | 0.0131 | 16.1 | True |
| spot_move_5s | net_neutral |  | 88.2 | 35.8 | 0.0144 | 153.9 | True |
| equal_weight | M_dt_5m | <0.2 | 22.5 | 2.2 | 2.1e-20 | 34.5 | False |
| equal_weight | net_neutral | <0.2 | 410.4 | 30.0 | 5.41e-32 | 97.9 | False |
| equal_weight | M_dt_5m | 0.2–0.4 | 21.8 | 1.5 | 4.99e-34 | 30.8 | False |
| equal_weight | net_neutral | 0.2–0.4 | 87.1 | 16.0 | 1.31e-07 | 21.0 | False |
| equal_weight | M_dt_5m | 0.4–0.6 | 16.4 | 1.2 | 3.04e-32 | 23.4 | False |
| equal_weight | net_neutral | 0.4–0.6 | 41.5 | 8.9 | 5.86e-06 | 11.5 | False |
| equal_weight | M_dt_5m | >0.6 | 16.5 | 1.1 | 5.12e-38 | 19.7 | False |
| equal_weight | net_neutral | >0.6 | 37.3 | 5.1 | 3.15e-12 | 18.6 | False |
| large_50 | M_dt_5m |  | 24.2 | 1.3 | 1.42e-48 |  |  |
| large_50 | net_neutral |  | 29.4 | 6.8 | 2.47e-05 |  |  |
| large_50 | M_dt_5m |  | 26.0 | 1.5 | 3e-43 |  |  |
| large_50 | net_neutral |  | 23.8 | 7.6 | 0.0020 |  |  |
| large_100 | M_dt_5m |  | 25.4 | 1.5 | 4.24e-44 |  |  |
| large_100 | net_neutral |  | 29.7 | 7.1 | 3.64e-05 |  |  |
| large_100 | M_dt_5m |  | 25.3 | 1.6 | 8.11e-41 |  |  |
| large_100 | net_neutral |  | 21.5 | 7.9 | 0.0072 |  |  |
| large_200 | M_dt_5m |  | 25.4 | 1.5 | 1.18e-41 |  |  |
| large_200 | net_neutral |  | 30.3 | 7.4 | 5.97e-05 |  |  |
| large_200 | M_dt_5m |  | 25.2 | 1.8 | 6.47e-33 |  |  |
| large_200 | net_neutral |  | 14.4 | 8.5 | 0.0902 |  |  |


## H4 穩健性

來源：`stage4/h4_checks.parquet, h4_tails.parquet`

| check | term | coef | se | p |
|---|---|---|---|---|
| main | F_norm | 23.03 | 8.64 | 0.0082 |
| drop_extreme_return_days | F_norm | 23.18 | 8.68 | 0.0082 |
| drop_extreme_flow_days | F_norm | 22.37 | 8.96 | 0.0133 |
| short_vs_long | F_short_norm | 4.10 | 19.97 | 0.8374 |
| short_vs_long | F_long_norm | 29.02 | 12.77 | 0.0240 |

| tail | mean_y_bps | se_bps | n | n_days |
|---|---|---|---|---|
| 0%–5% | -1.48 | 0.65 | 2844 | 204 |
| 5%–50% | -0.36 | 0.15 | 25588 | 223 |
| 50%–95% | 0.06 | 0.16 | 25587 | 223 |
| 95%–100% | 2.59 | 0.54 | 2844 | 199 |


## 樣本外：執行紀錄

來源：`stage5/meta.parquet`

| commit | dirty_tree | dry_run | unlocked | train_first | train_last | test_first | test_last | run_at |
|---|---|---|---|---|---|---|---|---|
| deaabc04d80244d2d83bd4c5d4a53ff1aa6ebc0e | False | False | True | 2025-01-02 | 2025-12-31 | 2026-01-02 | 2026-11-18 | 2026-11-24T14:00:46.646877 |


## 樣本外：毒性分數五分位

來源：`stage5/quintiles_*.parquet, q5_minus_q1_*.parquet, r2.parquet`

| quintile | mean_bps | se_bps | n | file |
|---|---|---|---|---|
| Q1 | -2.7 | 2.0 | 104866 | quintiles_train |
| Q2 | 8.2 | 1.0 | 104867 | quintiles_train |
| Q3 | 15.2 | 1.3 | 104863 | quintiles_train |
| Q4 | 30.8 | 2.4 | 104865 | quintiles_train |
| Q5 | 62.4 | 3.1 | 104866 | quintiles_train |

| quintile | mean_bps | se_bps | n | file |
|---|---|---|---|---|
| Q1 | 2.6 | 1.8 | 198915 | quintiles_test |
| Q2 | 8.3 | 1.3 | 164900 | quintiles_test |
| Q3 | 9.2 | 1.2 | 150937 | quintiles_test |
| Q4 | 15.1 | 1.6 | 142225 | quintiles_test |
| Q5 | 38.7 | 2.2 | 158269 | quintiles_test |

| quintile | mean_bps | se_bps | n | file |
|---|---|---|---|---|
| Q1 | 2.0 | 2.0 | 185451 | wf_quintiles |
| Q2 | 8.0 | 1.2 | 165601 | wf_quintiles |
| Q3 | 8.6 | 1.3 | 158205 | wf_quintiles |
| Q4 | 16.6 | 1.5 | 153157 | wf_quintiles |
| Q5 | 41.3 | 2.3 | 152832 | wf_quintiles |

| coef | se | t | p | n | n_days | file |
|---|---|---|---|---|---|---|
| 65.06 | 3.75 | 17.37 | 1.96e-44 | 209732 | 243 | q5_minus_q1_train |

| coef | se | t | p | n | n_days | file |
|---|---|---|---|---|---|---|
| 36.09 | 2.40 | 15.03 | 4.19e-35 | 357184 | 210 | q5_minus_q1_test |

| coef | se | t | p | n | n_days | file |
|---|---|---|---|---|---|---|
| 39.29 | 2.75 | 14.28 | 9.48e-33 | 338283 | 210 | wf_q5_minus_q1 |

| r2_oos | n_test | n_train |
|---|---|---|
| 0.0074 | 815246 | 524327 |

coefficients 欄位：['term', 'coef']

| term | coef |
|---|---|
| const | 45.04 |
| log_size | 0.55 |
| spot_fav | -10.72 |
| spot_adv | -52.26 |
| spot_ticked | 46.56 |
| mom_1m | -0.12 |
| mom_5m | -0.05 |
| buy | -1.69 |
| put | -2.76 |
| half_spread | -0.01 |
| prev_in_force | 6.17 |
| log_age | 1.38 |
| no_prev | 16.29 |
| cell_0.2–0.4|31–90 | -28.87 |
| cell_0.2–0.4|91–180 | -31.74 |
| cell_0.2–0.4|>180 | -39.83 |
| cell_0.4–0.6|1–30 | 18.03 |
| cell_0.4–0.6|31–90 | -23.85 |
| cell_0.4–0.6|91–180 | -39.71 |
| cell_0.4–0.6|>180 | -49.85 |
| cell_<0.2|1–30 | -5.07 |
| cell_<0.2|31–90 | -14.19 |
| cell_<0.2|91–180 | -21.42 |
| cell_<0.2|>180 | -43.90 |
| cell_>0.6|1–30 | -23.68 |
| cell_>0.6|31–90 | -36.47 |
| cell_>0.6|91–180 | -43.75 |
| cell_>0.6|>180 | -50.13 |
| tod_09:30–12:30 | -6.67 |
| tod_12:30–13:25 | -17.59 |
| issuer_元大 | 5.66 |
| issuer_元富 | 12.02 |
| issuer_兆豐 | 41.51 |
| issuer_凱基 | 4.89 |
| issuer_台新 | 1.68 |
| issuer_國泰 | 25.75 |
| issuer_國票 | 12.03 |
| issuer_富邦 | 9.95 |
| issuer_永豐 | 8.99 |
| issuer_第一 | -11.59 |
| issuer_統一 | 1.41 |
| issuer_群益 | 9.97 |


## 樣本外：熱力圖彙總

來源：`stage5/heatmap_summary.parquet`

| pooled_gap_se_bps_test | pooled_gap_vs_train_be_bps | pooled_gap_vs_train_be_se_bps | n_cells | n_cells_with_test | share_sign_agree | n_negative_cells_train | pooled_gap_bps_test | pooled_gap_twd_test |
|---|---|---|---|---|---|---|---|---|
| 8.763 | 18.833 | 8.445 | 43 | 43 | 0.8605 | 6 | 58.832 | 38,755,398.863 |

heatmap 欄位：['delta_bucket', 'dte_bucket', 'notional_bucket', 'value', 'mean_bps', 'se_bps', 't', 'p', 'n', 'n_days', 'sample', 'gap_twd_per_lot', 'test_notional']

| wf_sign_agree_share | n_cells |
|---|---|
| 0.9535 | 43 |


## 樣本外：H4 交易

來源：`stage5/h4_trading.parquet, wf_h4_trading.parquet`

| signal | cost | main | n_trades | trigger_rate | gross_mean_bps | net_mean_bps | cost_mean_bps | daily_mean_bps | daily_sd_bps | sharpe_annual | t_daily | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| residual | futures_spread | True | 5111 | 0.10 | 0.92 | -24.04 | 24.96 | -117.02 | 111.00 | -16.67 | -15.28 | 210 |
| residual | futures_tick | False | 5111 | 0.10 | 0.92 | -47.72 | 48.64 | -232.29 | 215.85 | -17.02 | -15.60 | 210 |
| residual | stock_daytrade | False | 5111 | 0.10 | 0.92 | -67.04 | 67.97 | -326.35 | 279.37 | -18.47 | -16.93 | 210 |
| raw | futures_spread | False | 5366 | 0.10 | 0.53 | -24.69 | 25.22 | -126.18 | 114.93 | -17.36 | -15.91 | 210 |
| raw | futures_tick | False | 5366 | 0.10 | 0.53 | -48.67 | 49.19 | -248.71 | 228.35 | -17.22 | -15.78 | 210 |
| raw | stock_daytrade | False | 5366 | 0.10 | 0.53 | -67.69 | 68.22 | -345.94 | 296.14 | -18.47 | -16.93 | 210 |

| signal | cost | main | n_trades | trigger_rate | gross_mean_bps | net_mean_bps | cost_mean_bps | daily_mean_bps | daily_sd_bps | sharpe_annual | t_daily | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| residual | futures_spread | True | 4857 | 0.09 | 1.05 | -23.93 | 24.97 | -110.68 | 109.42 | -15.99 | -14.66 | 210 |
| residual | futures_tick | False | 4857 | 0.09 | 1.05 | -47.64 | 48.69 | -220.38 | 212.88 | -16.37 | -15.00 | 210 |
| residual | stock_daytrade | False | 4857 | 0.09 | 1.05 | -66.93 | 67.98 | -309.60 | 275.52 | -17.77 | -16.28 | 210 |
| raw | futures_spread | False | 4976 | 0.09 | 0.57 | -24.73 | 25.30 | -117.19 | 112.05 | -16.54 | -15.16 | 210 |
| raw | futures_tick | False | 4976 | 0.09 | 0.57 | -48.80 | 49.37 | -231.26 | 223.01 | -16.40 | -15.03 | 210 |
| raw | stock_daytrade | False | 4976 | 0.09 | 0.57 | -67.73 | 68.30 | -320.98 | 287.97 | -17.62 | -16.15 | 210 |


## 樣本外：2026 價差拆解（全部）

來源：`stage5/test_decomposition.parquet`

| value | mean_bps | se_bps | t | p | n | n_days |
|---|---|---|---|---|---|---|
| ES | 163.1 | 5.9 | 27.5 | 2.18e-71 | 815246 | 210 |
| RS_5m | 146.4 | 6.1 | 24.0 | 4.57e-62 | 815246 | 210 |
| PI_5m | 16.7 | 1.2 | 14.2 | 2.35e-32 | 815246 | 210 |
| M_5m | 16.7 | 1.2 | 14.2 | 1.62e-32 | 815246 | 210 |
| RS_dt_5m | 146.8 | 6.1 | 24.1 | 2.18e-62 | 815246 | 210 |
| PI_dt_5m | 16.2 | 1.1 | 14.3 | 5.9e-33 | 815246 | 210 |
| M_dt_5m | 16.2 | 1.1 | 14.4 | 4.14e-33 | 815246 | 210 |
| cost_pessimistic | 157.2 | 2.0 | 77.7 | 3.65e-156 | 815246 | 210 |
| cost_neutral | 65.8 | 1.1 | 57.7 | 2.55e-130 | 815246 | 210 |
| cost_optimistic | 16.6 | 0.6 | 29.2 | 8.42e-76 | 815246 | 210 |
| net_pessimistic | -10.4 | 6.2 | -1.7 | 0.0980 | 815246 | 210 |
| net_neutral | 81.0 | 6.0 | 13.4 | 4.78e-30 | 815246 | 210 |
| net_optimistic | 130.2 | 6.0 | 21.5 | 6.07e-55 | 815246 | 210 |


## 樣本外：重現

來源：`stage5/replication.parquet`

| n_items | sig_2025 | reproduced | stable_all | stable_among_sig |
|---|---|---|---|---|
| 153 | 140 | 120 | 0.314 | 0.329 |

| value | mean_bps_train | se_bps_train | mean_bps_test | se_bps_test | z_diff | stable |
|---|---|---|---|---|---|---|
| ES | 153.1 | 5.6 | 163.1 | 5.9 | 1.2 | True |
| RS_dt_5m | 127.7 | 6.0 | 146.8 | 6.1 | 2.2 | False |
| M_dt_5m | 25.4 | 1.3 | 16.2 | 1.1 | -5.3 | False |
| net_pessimistic | -79.5 | 7.3 | -10.4 | 6.2 | 7.2 | False |
| net_neutral | 25.8 | 6.7 | 81.0 | 6.0 | 6.1 | False |
| net_optimistic | 94.3 | 6.3 | 130.2 | 6.0 | 4.1 | False |

| cut | group | value | mean_bps_train | mean_bps_test | z_diff | stable | sign_and_significance |
|---|---|---|---|---|---|---|---|
| dte_bucket | 1–30 | ES | 335.0 | 343.4 | 0.3 | True | 1.0 |
| dte_bucket | 1–30 | RS_dt_5m | 285.5 | 296.1 | 0.3 | True | 1.0 |
| dte_bucket | 1–30 | M_dt_5m | 49.4 | 47.1 | -0.2 | True | 1.0 |
| dte_bucket | 1–30 | net_pessimistic | -140.3 | -26.4 | 3.0 | False | 0.0 |
| dte_bucket | 1–30 | net_neutral | 38.6 | 129.9 | 2.7 | False |  |
| dte_bucket | 1–30 | net_optimistic | 209.9 | 252.5 | 1.2 | True | 1.0 |
| dte_bucket | 31–90 | ES | 245.8 | 271.1 | 1.1 | True | 1.0 |
| dte_bucket | 31–90 | RS_dt_5m | 212.8 | 251.4 | 1.6 | True | 1.0 |
| dte_bucket | 31–90 | M_dt_5m | 32.9 | 19.7 | -3.4 | False | 1.0 |
| dte_bucket | 31–90 | net_pessimistic | -101.2 | 8.7 | 4.4 | False | 0.0 |
| dte_bucket | 31–90 | net_neutral | 58.9 | 138.9 | 3.3 | False | 1.0 |
| dte_bucket | 31–90 | net_optimistic | 161.2 | 224.9 | 2.6 | False | 1.0 |
| dte_bucket | 91–180 | ES | 143.0 | 174.2 | 2.5 | False | 1.0 |
| dte_bucket | 91–180 | RS_dt_5m | 113.0 | 154.4 | 3.4 | False | 1.0 |
| dte_bucket | 91–180 | M_dt_5m | 29.9 | 19.8 | -4.6 | False | 1.0 |
| dte_bucket | 91–180 | net_pessimistic | -104.9 | -22.8 | 6.6 | False | 1.0 |
| dte_bucket | 91–180 | net_neutral | 5.8 | 81.3 | 6.2 | False |  |
| dte_bucket | 91–180 | net_optimistic | 78.3 | 136.2 | 4.7 | False | 1.0 |
| dte_bucket | >180 | ES | 120.1 | 124.5 | 0.5 | True | 1.0 |
| dte_bucket | >180 | RS_dt_5m | 103.0 | 112.9 | 1.0 | True | 1.0 |
| dte_bucket | >180 | M_dt_5m | 17.0 | 11.6 | -3.7 | False | 1.0 |
| dte_bucket | >180 | net_pessimistic | -43.5 | -5.0 | 3.9 | False | 0.0 |
| dte_bucket | >180 | net_neutral | 32.5 | 66.5 | 3.5 | False | 1.0 |
| dte_bucket | >180 | net_optimistic | 79.8 | 100.6 | 2.2 | False | 1.0 |
| high_gamma | cell | M_dt_5m | 81.5 | 43.8 | -1.1 | True | 1.0 |
| high_gamma | cell | net_neutral | -123.8 | 192.6 | 2.7 | False | 0.0 |
| h4 | all | F_norm | 23.0 | 22.2 | -0.1 | True | 1.0 |

**2025 顯著但未重現的項目**

| cut | group | value | mean_bps_train | mean_bps_test | p_test |
|---|---|---|---|---|---|
| all |  | net_pessimistic | -79.5 | -10.4 | 0.0980 |
| direction | buy | net_pessimistic | -58.2 | -10.0 | 0.3604 |
| direction | sell | net_pessimistic | -102.3 | -10.7 | 0.0930 |
| quadrant | buy_call | net_pessimistic | -57.0 | -13.3 | 0.2372 |
| quadrant | buy_put | net_pessimistic | -63.8 | 65.8 | 0.0199 |
| quadrant | sell_call | net_pessimistic | -111.0 | -11.1 | 0.0821 |
| quadrant | sell_put | net_pessimistic | -51.7 | -0.2 | 0.9912 |
| delta_bucket | <0.2 | net_pessimistic | -64.7 | 75.4 | 0.1587 |
| delta_bucket | 0.2–0.4 | net_pessimistic | -94.1 | -12.6 | 0.3607 |
| delta_bucket | >0.6 | net_pessimistic | -62.4 | 9.6 | 0.1894 |
| dte_bucket | 1–30 | net_pessimistic | -140.3 | -26.4 | 0.3631 |
| dte_bucket | 31–90 | net_pessimistic | -101.2 | 8.7 | 0.6397 |
| dte_bucket | >180 | net_pessimistic | -43.5 | -5.0 | 0.4728 |
| size_bucket | 1–10 | net_pessimistic | -51.4 | 36.3 | 7.74e-07 |
| size_bucket | >100 | net_pessimistic | -94.1 | -19.5 | 0.0835 |
| spot_1s | favourable | net_neutral | -40.2 | 21.6 | 0.000102 |
| spot_1s | none | net_pessimistic | -65.7 | 9.5 | 0.1907 |
| tod | 09:00–09:30 | net_pessimistic | -40.6 | 35.1 | 0.0101 |
| tod | 12:30–13:25 | net_pessimistic | -100.6 | -5.2 | 0.7888 |
| high_gamma | cell | net_neutral | -123.8 | 192.6 | 0.0799 |


## 經濟規模（2025）

來源：`report/magnitude_2025.parquet`

| group_set | group | share_notional | share_trades | ES_bps | M_dt_bps | net_neutral_bps | contribution_bps | net_ntd | overall_net_bps |
|---|---|---|---|---|---|---|---|---|---|
| cell | <0.2|1–30 | 0.0012 | 0.0073 | 1,113.304 | 39.742 | 665.860 | 0.804 | 1,398,742.084 | 25.813 |
| cell | <0.2|31–90 | 0.0229 | 0.0553 | 386.379 | 41.956 | 151.870 | 3.476 | 6,043,430.797 | 25.813 |
| cell | <0.2|91–180 | 0.0603 | 0.0931 | 247.458 | 39.200 | 64.458 | 3.890 | 6,763,910.288 | 25.813 |
| cell | <0.2|>180 | 0.0309 | 0.0454 | 212.225 | 19.482 | 101.183 | 3.125 | 5,433,444.376 | 25.813 |
| cell | 0.2–0.4|1–30 | 0.0021 | 0.0037 | 400.564 | 54.231 | 50.322 | 0.106 | 185,050.322 | 25.813 |
| cell | 0.2–0.4|31–90 | 0.0339 | 0.0419 | 278.381 | 28.281 | 83.214 | 2.824 | 4,909,567.734 | 25.813 |
| cell | 0.2–0.4|91–180 | 0.1151 | 0.1135 | 138.838 | 35.031 | -11.968 | -1.378 | -2,395,635.920 | 25.813 |
| cell | 0.2–0.4|>180 | 0.0886 | 0.0903 | 154.330 | 25.838 | 39.328 | 3.485 | 6,059,024.922 | 25.813 |
| cell | 0.4–0.6|1–30 | 0.0036 | 0.0037 | 235.277 | 81.532 | -123.809 | -0.443 | -770,781.589 | 25.813 |
| cell | 0.4–0.6|31–90 | 0.0494 | 0.0401 | 223.548 | 36.596 | 36.003 | 1.778 | 3,092,107.564 | 25.813 |
| cell | 0.4–0.6|91–180 | 0.1479 | 0.1148 | 117.039 | 26.570 | -4.994 | -0.739 | -1,284,415.753 | 25.813 |
| cell | 0.4–0.6|>180 | 0.1537 | 0.1627 | 105.242 | 14.681 | 22.584 | 3.471 | 6,034,700.457 | 25.813 |
| cell | >0.6|1–30 | 0.0108 | 0.0086 | 267.898 | 38.836 | 19.826 | 0.213 | 370,682.411 | 25.813 |
| cell | >0.6|31–90 | 0.0518 | 0.0393 | 183.428 | 28.491 | 23.671 | 1.226 | 2,131,088.250 | 25.813 |
| cell | >0.6|91–180 | 0.0865 | 0.0658 | 119.818 | 22.061 | 6.816 | 0.590 | 1,025,028.172 | 25.813 |
| cell | >0.6|>180 | 0.1413 | 0.1146 | 94.552 | 13.499 | 23.958 | 3.386 | 5,886,681.564 | 25.813 |
| spot_1s | favourable | 0.2004 | 0.1136 | 108.254 | 26.920 | -40.211 | -8.058 | -14,010,895.147 | 25.813 |
| spot_1s | none | 0.7901 | 0.8780 | 162.818 | 25.072 | 40.893 | 32.308 | 56,176,652.493 | 25.813 |
| spot_1s | adverse | 0.0095 | 0.0084 | 279.292 | 16.080 | 153.936 | 1.462 | 2,541,387.453 | 25.813 |
| spot_print | just_ticked | 0.2979 | 0.2031 | 126.651 | 43.771 | -30.086 | -8.963 | -15,585,449.284 | 25.813 |
| spot_print | quiet | 0.7021 | 0.7969 | 164.321 | 17.556 | 49.534 | 34.776 | 60,468,074.964 | 25.813 |
| tod | 09:00–09:30 | 0.2970 | 0.3130 | 199.389 | 34.520 | 65.147 | 19.348 | 33,642,317.837 | 25.813 |
| tod | 09:30–12:30 | 0.5393 | 0.5233 | 136.725 | 23.844 | 10.221 | 5.512 | 9,584,965.257 | 25.813 |
| tod | 12:30–13:25 | 0.1637 | 0.1636 | 123.057 | 13.773 | 5.816 | 0.952 | 1,655,342.585 | 25.813 |


## 經濟規模（2026）

來源：`report/magnitude_2026.parquet`

| group_set | group | share_notional | share_trades | ES_bps | M_dt_bps | net_neutral_bps | contribution_bps | net_ntd | overall_net_bps |
|---|---|---|---|---|---|---|---|---|---|
| cell | <0.2|1–30 | 0.000597 | 0.0094 | 1,082.335 | 40.179 | 712.598 | 0.425 | 1,288,119.260 | 81.044 |
| cell | <0.2|31–90 | 0.0091 | 0.0283 | 478.635 | 26.847 | 306.385 | 2.798 | 8,478,842.858 | 81.044 |
| cell | <0.2|91–180 | 0.0327 | 0.0697 | 369.296 | 27.093 | 245.699 | 8.036 | 24,351,436.540 | 81.044 |
| cell | <0.2|>180 | 0.0088 | 0.0202 | 244.803 | 20.494 | 141.735 | 1.248 | 3,781,570.777 | 81.044 |
| cell | 0.2–0.4|1–30 | 0.0013 | 0.0024 | 718.920 | 47.383 | 398.591 | 0.503 | 1,522,939.014 | 81.044 |
| cell | 0.2–0.4|31–90 | 0.0257 | 0.0319 | 307.357 | 20.370 | 168.898 | 4.347 | 13,172,332.268 | 81.044 |
| cell | 0.2–0.4|91–180 | 0.0931 | 0.1162 | 201.881 | 25.705 | 95.801 | 8.917 | 27,018,905.239 | 81.044 |
| cell | 0.2–0.4|>180 | 0.1111 | 0.1152 | 168.111 | 14.036 | 93.445 | 10.384 | 31,465,638.091 | 81.044 |
| cell | 0.4–0.6|1–30 | 0.0032 | 0.0026 | 442.339 | 43.801 | 192.571 | 0.611 | 1,851,702.236 | 81.044 |
| cell | 0.4–0.6|31–90 | 0.0277 | 0.0248 | 291.660 | 23.660 | 155.694 | 4.305 | 13,045,184.992 | 81.044 |
| cell | 0.4–0.6|91–180 | 0.1556 | 0.1280 | 125.828 | 17.190 | 42.561 | 6.621 | 20,061,695.067 | 81.044 |
| cell | 0.4–0.6|>180 | 0.2261 | 0.1954 | 98.368 | 12.184 | 41.069 | 9.287 | 28,142,312.739 | 81.044 |
| cell | >0.6|1–30 | 0.0172 | 0.0097 | 272.057 | 47.887 | 78.441 | 1.350 | 4,089,465.135 | 81.044 |
| cell | >0.6|31–90 | 0.0456 | 0.0313 | 196.652 | 15.430 | 78.227 | 3.566 | 10,804,823.578 | 81.044 |
| cell | >0.6|91–180 | 0.0777 | 0.0573 | 155.801 | 14.857 | 72.169 | 5.605 | 16,985,137.074 | 81.044 |
| cell | >0.6|>180 | 0.1646 | 0.1577 | 124.454 | 8.627 | 79.240 | 13.041 | 39,516,997.302 | 81.044 |
| spot_1s | favourable | 0.2565 | 0.1434 | 108.943 | 13.695 | 21.581 | 5.535 | 16,771,928.432 | 81.044 |
| spot_1s | none | 0.7327 | 0.8437 | 179.711 | 17.188 | 99.506 | 72.906 | 220,917,264.833 | 81.044 |
| spot_1s | adverse | 0.0107 | 0.0127 | 304.276 | 7.745 | 227.417 | 2.432 | 7,367,954.237 | 81.044 |
| spot_print | just_ticked | 0.3498 | 0.2349 | 124.276 | 24.768 | 29.247 | 10.232 | 31,003,947.155 | 81.044 |
| spot_print | quiet | 0.6502 | 0.7651 | 183.921 | 11.583 | 108.916 | 70.812 | 214,573,155.014 | 81.044 |
| tod | 09:00–09:30 | 0.2638 | 0.2843 | 213.783 | 21.099 | 129.398 | 34.135 | 103,435,828.277 | 81.044 |
| tod | 09:30–12:30 | 0.5857 | 0.5644 | 139.952 | 15.259 | 58.380 | 34.192 | 103,606,219.181 | 81.044 |
| tod | 12:30–13:25 | 0.1505 | 0.1513 | 164.045 | 11.246 | 84.484 | 12.717 | 38,535,054.711 | 81.044 |


## B 短天期缺報價（2025）

來源：`extension/b_estimate_2025.parquet, b_validation_2025.parquet`

| scope | estimate | mean_bps | se_bps | n | n_days | share_notional | proxy_validated |
|---|---|---|---|---|---|---|---|
| dte_1-30 | quoted_only | 49.46 | 10.25 | 12249 | 243.00 | 0.7139 | True |
| dte_1-30 | missing_proxy | -0.52 | 16.61 | 2205 | 222.00 | 0.1360 | True |
| dte_1-30 | combined | 41.46 | 9.09 | 14454 | 243.00 | 0.8499 | True |
| dte_1-30 | missing_unestimable |  |  | 2337 |  | 0.1501 | True |
| all | quoted_only | 25.50 | 1.32 | 524327 | 243.00 | 0.9130 | True |
| all | missing_proxy | -21.55 | 2.77 | 48624 | 243.00 | 0.0711 | True |
| all | combined | 22.10 | 1.21 | 572951 | 243.00 | 0.9841 | True |
| all | missing_unestimable |  |  | 10949 |  | 0.0159 | True |

| group_set | group | mean_bps | ci_lo_bps | ci_hi_bps | within_margin | criterion |
|---|---|---|---|---|---|---|
| dte_1-30 | all | -0.14 | -0.50 | 0.23 | True | True |
| all | all | -0.02 | -0.04 | 0.01 | True | False |
| dte_1-30_delta<0.2 | all | 1.04 | -1.41 | 3.49 | True | False |
| price<=0.05 | all | 2.02 | -2.65 | 6.68 | False | False |
| direction | buy | -0.02 | -0.06 | 0.01 | True | False |
| direction | sell | -0.00502 | -0.04 | 0.03 | True | False |
| iv_age | <5分 | -0.03 | -0.07 | 0.01 | True | False |
| iv_age | 5–60分 | -0.01 | -0.04 | 0.02 | True | False |
| iv_age | >60分 | 0.00143 | -0.05 | 0.05 | True | False |
| dte_1-30_iv_age | <5分 | -0.09 | -0.43 | 0.26 | True | False |
| dte_1-30_iv_age | 5–60分 | 0.07 | -0.34 | 0.48 | True | False |
| dte_1-30_iv_age | >60分 | -0.35 | -1.22 | 0.52 | True | False |


## C1（2025）

來源：`extension/c1_*_2025.parquet`

| term | coef | se | t | p | n | n_days | name | ci_lo | ci_hi | reading |
|---|---|---|---|---|---|---|---|---|---|---|
| signed_norm | 4.47 | 0.41 | 10.79 | 4.35e-22 | 56863 | 223 | lambda | 3.65 | 5.28 | delayed hedging cannot fully explain H4 |
| F_norm | 23.03 | 8.64 | 2.67 | 0.0082 | 56863 | 223 | beta_controls | 6.10 | 39.95 | delayed hedging cannot fully explain H4 |
| F_norm | 26.98 | 6.98 | 3.87 | 0.000144 | 56863 | 223 | beta_no_controls | 13.31 | 40.65 | delayed hedging cannot fully explain H4 |

| n_windows | median | p90 | p99 | pooled |
|---|---|---|---|---|
| 12393 | 0.00514 | 0.0263 | 0.1009 | 0.00903 |


## C2（2025）

來源：`extension/c2_*_2025.parquet`

| group | version | horizon | mean_bps | se_bps | n | n_days | diff_bps | diff_se_bps | diff_ci_lo | diff_ci_hi | reversion_share | reading |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | detrended | 5m | 26.6 | 1.5 | 473604 | 243 |  |  |  |  |  |  |
| all | detrended | 30m | 29.6 | 3.2 | 473604 | 243 | 3.0 | 2.7 | -2.3 | 8.2 | -0.1115 | no marked reversion |
| all | detrended | close | -8.2 | 5.0 | 473604 | 243 | -34.9 | 5.4 | -45.5 | -24.2 | 1.3082 | reversion |
| all | raw | 5m | 28.1 | 1.5 | 473604 | 243 |  |  |  |  |  |  |
| all | raw | 30m | 37.3 | 3.3 | 473604 | 243 | 9.1 | 2.8 | 3.6 | 14.6 | -0.3246 | no marked reversion |
| all | raw | close | 54.3 | 8.7 | 473604 | 243 | 26.2 | 8.6 | 9.3 | 43.2 | -0.9321 | no marked reversion |
| buy | detrended | 5m | 24.8 | 2.0 | 263657 | 243 |  |  |  |  |  |  |
| buy | detrended | 30m | 24.8 | 3.4 | 263657 | 243 | -0.1 | 3.1 | -6.1 | 5.9 | 0.0025 | no marked reversion |
| buy | detrended | close | -33.7 | 13.3 | 263657 | 243 | -58.5 | 13.8 | -85.5 | -31.5 | 2.3554 | reversion |
| buy | raw | 5m | 26.8 | 2.1 | 263657 | 243 |  |  |  |  |  |  |
| buy | raw | 30m | 33.9 | 4.8 | 263657 | 243 | 7.1 | 4.2 | -1.2 | 15.4 | -0.2665 | no marked reversion |
| buy | raw | close | 48.0 | 20.7 | 263657 | 243 | 21.3 | 20.5 | -18.9 | 61.5 | -0.7948 | inconclusive |
| sell | detrended | 5m | 28.5 | 2.1 | 209947 | 243 |  |  |  |  |  |  |
| sell | detrended | 30m | 34.7 | 5.9 | 209947 | 243 | 6.2 | 4.8 | -3.2 | 15.5 | -0.2159 | no marked reversion |
| sell | detrended | close | 18.6 | 15.0 | 209947 | 243 | -10.0 | 15.9 | -41.2 | 21.2 | 0.3489 | inconclusive |
| sell | raw | 5m | 29.6 | 2.5 | 209947 | 243 |  |  |  |  |  |  |
| sell | raw | 30m | 40.8 | 7.5 | 209947 | 243 | 11.2 | 5.8 | -0.0 | 22.5 | -0.3799 | no marked reversion |
| sell | raw | close | 61.0 | 26.6 | 209947 | 243 | 31.4 | 25.6 | -18.8 | 81.6 | -1.0630 | inconclusive |

| horizon | coef | se | n | diff | diff_se | diff_ci_lo | diff_ci_hi | reading |
|---|---|---|---|---|---|---|---|---|
| 5m | 24.6 | 8.9 | 51288 |  |  |  |  |  |
| 1m | 6.9 | 2.4 | 51288 | -17.7 | 6.8 | -30.9 | -4.5 | n/a (shorter than 5m) |
| 30m | 53.3 | 16.4 | 51288 | 28.8 | 12.7 | 3.9 | 53.6 | no marked reversion |
| close | 96.7 | 54.9 | 51288 | 72.2 | 50.1 | -26.1 | 170.4 | inconclusive |


## B 短天期缺報價（2026）

來源：`extension/b_estimate_2026.parquet, b_validation_2026.parquet`

| scope | estimate | mean_bps | se_bps | n | n_days | share_notional | proxy_validated |
|---|---|---|---|---|---|---|---|
| dte_1-30 | quoted_only | 47.66 | 7.65 | 19597 | 210.00 | 0.6590 | True |
| dte_1-30 | missing_proxy | -7.13 | 12.32 | 5676 | 207.00 | 0.1907 | True |
| dte_1-30 | combined | 35.36 | 7.38 | 25273 | 210.00 | 0.8497 | True |
| dte_1-30 | missing_unestimable |  |  | 5948 |  | 0.1503 | True |
| all | quoted_only | 16.18 | 1.12 | 815246 | 210.00 | 0.8945 | True |
| all | missing_proxy | -10.77 | 2.04 | 89479 | 210.00 | 0.0860 | True |
| all | combined | 13.81 | 1.05 | 904725 | 210.00 | 0.9805 | True |
| all | missing_unestimable |  |  | 17928 |  | 0.0195 | True |

| group_set | group | mean_bps | ci_lo_bps | ci_hi_bps | within_margin | criterion |
|---|---|---|---|---|---|---|
| dte_1-30 | all | 1.81 | -0.09 | 3.71 | True | True |
| all | all | 0.08 | 0.002 | 0.15 | True | False |
| dte_1-30_delta<0.2 | all | -1.12 | -4.51 | 2.27 | True | False |
| price<=0.05 | all | 2.19 | -1.21 | 5.59 | False | False |
| direction | buy | 0.07 | -0.02 | 0.17 | True | False |
| direction | sell | 0.08 | -0.03 | 0.19 | True | False |
| iv_age | <5分 | 0.07 | -0.03 | 0.17 | True | False |
| iv_age | 5–60分 | 0.10 | -0.06 | 0.25 | True | False |
| iv_age | >60分 | 0.06 | 0.00358 | 0.12 | True | False |
| dte_1-30_iv_age | <5分 | 0.06 | -0.31 | 0.43 | True | False |
| dte_1-30_iv_age | 5–60分 | 4.64 | -0.87 | 10.14 | False | False |
| dte_1-30_iv_age | >60分 | 0.80 | -0.38 | 1.98 | True | False |


## C1（2026）

來源：`extension/c1_*_2026.parquet`

| term | coef | se | t | p | n | n_days | name | ci_lo | ci_hi | reading |
|---|---|---|---|---|---|---|---|---|---|---|
| signed_norm | 8.74 | 0.53 | 16.55 | 7.06e-40 | 53550 | 210 | lambda | 7.71 | 9.78 | inconclusive (intervals overlap) |
| F_norm | 22.16 | 8.92 | 2.48 | 0.0138 | 53550 | 210 | beta_controls | 4.68 | 39.64 | inconclusive (intervals overlap) |
| F_norm | 28.03 | 8.48 | 3.31 | 0.0011 | 53550 | 210 | beta_no_controls | 11.42 | 44.64 | inconclusive (intervals overlap) |

| n_windows | median | p90 | p99 | pooled |
|---|---|---|---|---|
| 10710 | 0.00478 | 0.0222 | 0.0810 | 0.00795 |


## C2（2026）

來源：`extension/c2_*_2026.parquet`

| group | version | horizon | mean_bps | se_bps | n | n_days | diff_bps | diff_se_bps | diff_ci_lo | diff_ci_hi | reversion_share | reading |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | detrended | 5m | 17.1 | 1.2 | 746908 | 210 |  |  |  |  |  |  |
| all | detrended | 30m | 16.0 | 2.8 | 746908 | 210 | -1.1 | 2.3 | -5.7 | 3.5 | 0.0658 | no marked reversion |
| all | detrended | close | -7.1 | 4.5 | 746908 | 210 | -24.3 | 4.7 | -33.5 | -15.0 | 1.4151 | reversion |
| all | raw | 5m | 17.7 | 1.3 | 746908 | 210 |  |  |  |  |  |  |
| all | raw | 30m | 18.9 | 3.2 | 746908 | 210 | 1.3 | 2.6 | -3.9 | 6.4 | -0.0716 | no marked reversion |
| all | raw | close | 13.6 | 7.0 | 746908 | 210 | -4.0 | 6.7 | -17.2 | 9.1 | 0.2278 | inconclusive |
| buy | detrended | 5m | 18.1 | 1.9 | 427080 | 210 |  |  |  |  |  |  |
| buy | detrended | 30m | 17.4 | 5.1 | 427080 | 210 | -0.7 | 4.2 | -9.0 | 7.6 | 0.0392 | no marked reversion |
| buy | detrended | close | -70.1 | 18.7 | 427080 | 210 | -88.2 | 19.8 | -127.0 | -49.4 | 4.8798 | reversion |
| buy | raw | 5m | 20.0 | 2.5 | 427080 | 210 |  |  |  |  |  |  |
| buy | raw | 30m | 28.4 | 8.6 | 427080 | 210 | 8.5 | 6.9 | -5.0 | 21.9 | -0.4240 | no marked reversion |
| buy | raw | close | 5.9 | 26.8 | 427080 | 210 | -14.1 | 25.7 | -64.5 | 36.2 | 0.7064 | inconclusive |
| sell | detrended | 5m | 16.2 | 1.6 | 319828 | 210 |  |  |  |  |  |  |
| sell | detrended | 30m | 14.7 | 5.4 | 319828 | 210 | -1.5 | 4.8 | -11.0 | 7.9 | 0.0946 | inconclusive |
| sell | detrended | close | 54.2 | 18.8 | 319828 | 210 | 38.0 | 19.4 | 0.0 | 75.9 | -2.3392 | no marked reversion |
| sell | raw | 5m | 15.4 | 2.1 | 319828 | 210 |  |  |  |  |  |  |
| sell | raw | 30m | 9.7 | 8.2 | 319828 | 210 | -5.7 | 6.9 | -19.2 | 7.7 | 0.3732 | inconclusive |
| sell | raw | close | 21.2 | 30.0 | 319828 | 210 | 5.8 | 29.1 | -51.2 | 62.8 | -0.3763 | inconclusive |

| horizon | coef | se | n | diff | diff_se | diff_ci_lo | diff_ci_hi | reading |
|---|---|---|---|---|---|---|---|---|
| 5m | 21.6 | 9.1 | 48300 |  |  |  |  |  |
| 1m | 7.8 | 2.5 | 48300 | -13.8 | 7.4 | -28.3 | 0.8 | n/a (shorter than 5m) |
| 30m | 23.7 | 31.7 | 48300 | 2.1 | 28.7 | -54.2 | 58.5 | inconclusive |
| close | -52.3 | 92.1 | 48300 | -74.0 | 88.9 | -248.1 | 100.2 | inconclusive |


## D 合併部位

來源：`extension/d_netting.parquet`

| period | signal | cost | n_trades | turnover_ratio | gross_mean_bps | cost_per_trade_bps | net_mean_bps | unnetted_cost_bps | lower_bound_cost_bps | daily_mean_bps | daily_sd_bps | sharpe_annual | t_daily | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025_in_sample | residual | futures_spread | 5688 | 0.83 | 2.04 | 28.20 | -26.16 | 33.96 | 6.79 | -133.47 | 107.26 | -19.67 | -18.58 | 223 |
| 2025_in_sample | residual | futures_tick | 5688 | 0.83 | 2.04 | 55.68 | -53.64 | 66.95 | 13.39 | -273.65 | 209.49 | -20.65 | -19.51 | 223 |
| 2025_in_sample | residual | stock_daytrade | 5688 | 0.83 | 2.04 | 63.71 | -61.67 | 76.89 | 15.38 | -314.60 | 208.19 | -23.89 | -22.57 | 223 |
| 2025_in_sample | raw | futures_spread | 5688 | 0.82 | 2.04 | 27.92 | -25.88 | 34.00 | 6.80 | -132.03 | 99.67 | -20.94 | -19.78 | 223 |
| 2025_in_sample | raw | futures_tick | 5688 | 0.82 | 2.04 | 55.14 | -53.10 | 67.00 | 13.40 | -270.87 | 196.27 | -21.82 | -20.61 | 223 |
| 2025_in_sample | raw | stock_daytrade | 5688 | 0.82 | 2.04 | 63.01 | -60.97 | 76.93 | 15.39 | -311.01 | 185.42 | -26.52 | -25.05 | 223 |
| 2026_static | residual | futures_spread | 5111 | 0.83 | 0.92 | 20.53 | -19.61 | 24.96 | 4.99 | -95.47 | 79.77 | -18.92 | -17.34 | 210 |
| 2026_static | residual | futures_tick | 5111 | 0.83 | 0.92 | 40.06 | -39.14 | 48.64 | 9.73 | -190.52 | 151.22 | -19.92 | -18.26 | 210 |
| 2026_static | residual | stock_daytrade | 5111 | 0.83 | 0.92 | 56.09 | -55.17 | 67.97 | 13.59 | -268.55 | 194.94 | -21.78 | -19.96 | 210 |
| 2026_static | raw | futures_spread | 5366 | 0.83 | 0.53 | 20.75 | -20.22 | 25.22 | 5.04 | -103.34 | 84.82 | -19.26 | -17.66 | 210 |
| 2026_static | raw | futures_tick | 5366 | 0.83 | 0.53 | 40.51 | -39.98 | 49.19 | 9.84 | -204.32 | 163.65 | -19.74 | -18.09 | 210 |
| 2026_static | raw | stock_daytrade | 5366 | 0.83 | 0.53 | 56.29 | -55.76 | 68.22 | 13.64 | -284.97 | 211.16 | -21.34 | -19.56 | 210 |
| 2026_walk_forward | residual | futures_spread | 4857 | 0.83 | 1.05 | 20.57 | -19.53 | 24.97 | 4.99 | -90.32 | 78.86 | -18.11 | -16.60 | 210 |
| 2026_walk_forward | residual | futures_tick | 4857 | 0.83 | 1.05 | 40.17 | -39.12 | 48.69 | 9.74 | -180.96 | 149.58 | -19.13 | -17.53 | 210 |
| 2026_walk_forward | residual | stock_daytrade | 4857 | 0.83 | 1.05 | 56.18 | -55.14 | 67.98 | 13.60 | -255.05 | 193.03 | -20.89 | -19.15 | 210 |
| 2026_walk_forward | raw | futures_spread | 4976 | 0.83 | 0.57 | 20.78 | -20.21 | 25.30 | 5.06 | -95.76 | 83.22 | -18.19 | -16.67 | 210 |
| 2026_walk_forward | raw | futures_tick | 4976 | 0.83 | 0.57 | 40.59 | -40.02 | 49.37 | 9.87 | -189.66 | 160.84 | -18.65 | -17.09 | 210 |
| 2026_walk_forward | raw | stock_daytrade | 4976 | 0.83 | 0.57 | 56.26 | -55.69 | 68.30 | 13.66 | -263.92 | 207.07 | -20.15 | -18.47 | 210 |


## E 動態避險（2025，全部成交）

來源：`extension/e_main_2025.parquet`

| sample | level | horizon | latency | rebalance | ladder | ES | cost | gamma | net | theta | vega |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | book | close | 1s | 0 | 1 | 151.7 | 65.8 | -14.3 | 71.7 | 0.0 | 0.0 |
| all | book | close | 1s | 0 | 2 | 151.7 | 66.4 | -14.8 | 70.6 | 0.0 | 0.0 |
| all | book | close | 1s | 0 | 3 | 151.7 | 66.7 | -14.6 | -20.6 | 0.1 | -91.0 |
| all | trade | 5m | 10s | 1 | 1 | 153.1 | 207.5 | -12.7 | -67.0 | 0.00823 | 0.0 |
| all | trade | 5m | 10s | 1 | 3 | 153.1 | 209.0 | -12.7 | -104.2 | 0.00894 | -35.6 |
| all | trade | 5m | 1m | 1 | 1 | 153.1 | 207.4 | -18.4 | -72.7 | 0.00822 | 0.0 |
| all | trade | 5m | 1m | 1 | 3 | 153.1 | 208.6 | -18.4 | -109.5 | 0.0089 | -35.6 |
| all | trade | 5m | 1s | 1 | 1 | 153.1 | 207.5 | -8.4 | -62.8 | 0.00823 | 0.0 |
| all | trade | 5m | 1s | 1 | 2 | 153.1 | 208.5 | -8.4 | -63.8 | 0.00823 | 0.0 |
| all | trade | 5m | 1s | 1 | 3 | 153.1 | 209.1 | -8.4 | -100.1 | 0.00894 | -35.6 |
| all | trade | close | 10s | 5 | 1 | 152.4 | 207.8 | -12.1 | -67.5 | 0.0 | 0.0 |
| all | trade | close | 10s | 5 | 3 | 152.4 | 222.0 | -12.4 | -174.6 | 0.1 | -92.7 |
| all | trade | close | 1m | 5 | 1 | 152.2 | 207.6 | -17.9 | -73.3 | 0.0 | 0.0 |
| all | trade | close | 1m | 5 | 3 | 152.2 | 221.7 | -18.2 | -181.1 | 0.1 | -93.5 |
| all | trade | close | 1s | 1 | 2 | 151.7 | 222.5 | -8.2 | -79.0 | 0.0 | 0.0 |
| all | trade | close | 1s | 1 | 3 | 151.7 | 225.9 | -8.2 | -173.4 | 0.1 | -91.0 |
| all | trade | close | 1s | 5 | 1 | 151.7 | 207.7 | -7.8 | -63.8 | 0.0 | 0.0 |
| all | trade | close | 1s | 5 | 2 | 151.7 | 219.3 | -8.1 | -75.7 | 0.0 | 0.0 |
| all | trade | close | 1s | 5 | 3 | 151.7 | 221.7 | -8.1 | -169.1 | 0.1 | -91.1 |
| excl_locked | book | close | 1s | 0 | 1 | 147.9 | 65.8 | -14.3 | 67.7 | 0.0 | 0.0 |
| excl_locked | book | close | 1s | 0 | 2 | 147.9 | 66.4 | -14.8 | 66.7 | 0.0 | 0.0 |
| excl_locked | book | close | 1s | 0 | 3 | 147.9 | 66.7 | -14.7 | -20.5 | 0.1 | -87.1 |
| excl_locked | trade | 5m | 10s | 1 | 1 | 149.1 | 207.4 | -12.7 | -71.0 | 0.00793 | 0.0 |
| excl_locked | trade | 5m | 10s | 1 | 3 | 149.1 | 208.9 | -12.7 | -106.0 | 0.00862 | -33.4 |
| excl_locked | trade | 5m | 1m | 1 | 1 | 149.1 | 207.4 | -18.5 | -76.7 | 0.00792 | 0.0 |
| excl_locked | trade | 5m | 1m | 1 | 3 | 149.1 | 208.5 | -18.5 | -111.3 | 0.00858 | -33.4 |
| excl_locked | trade | 5m | 1s | 1 | 1 | 149.1 | 207.4 | -8.5 | -66.7 | 0.00793 | 0.0 |
| excl_locked | trade | 5m | 1s | 1 | 2 | 149.1 | 208.4 | -8.5 | -67.8 | 0.00793 | 0.0 |
| excl_locked | trade | 5m | 1s | 1 | 3 | 149.1 | 209.0 | -8.5 | -101.8 | 0.00862 | -33.4 |
| excl_locked | trade | close | 10s | 5 | 1 | 148.5 | 207.7 | -12.2 | -71.3 | 0.0 | 0.0 |
| excl_locked | trade | close | 10s | 5 | 3 | 148.5 | 221.8 | -12.5 | -174.3 | 0.1 | -88.7 |
| excl_locked | trade | close | 1m | 5 | 1 | 148.3 | 207.5 | -18.0 | -77.2 | 0.0 | 0.0 |
| excl_locked | trade | close | 1m | 5 | 3 | 148.3 | 221.4 | -18.3 | -180.8 | 0.1 | -89.4 |
| excl_locked | trade | close | 1s | 1 | 2 | 147.9 | 222.5 | -8.3 | -82.9 | 0.0 | 0.0 |
| excl_locked | trade | close | 1s | 1 | 3 | 147.9 | 225.6 | -8.2 | -173.0 | 0.1 | -87.1 |
| excl_locked | trade | close | 1s | 5 | 1 | 147.9 | 207.6 | -7.9 | -67.5 | 0.0 | 0.0 |
| excl_locked | trade | close | 1s | 5 | 2 | 147.9 | 219.3 | -8.2 | -79.6 | 0.0 | 0.0 |
| excl_locked | trade | close | 1s | 5 | 3 | 147.9 | 221.5 | -8.1 | -168.8 | 0.1 | -87.1 |

| cut | group | level | horizon | rebalance | ladder | ES | cost | gamma | net | theta | vega |
|---|---|---|---|---|---|---|---|---|---|---|---|
| direction | buy | book | close | 0 | 1 | 174.6 | 66.9 | -20.9 | 93.3 | 6.5 | 0.0 |
| direction | buy | book | close | 0 | 2 | 174.6 | 67.7 | -22.3 | 91.1 | 6.5 | 0.0 |
| direction | buy | book | close | 0 | 3 | 174.6 | 68.2 | -22.2 | -52.1 | 6.6 | -143.0 |
| direction | buy | trade | 5m | 1 | 1 | 175.9 | 210.4 | -10.1 | -44.3 | 0.2 | 0.0 |
| direction | buy | trade | 5m | 1 | 2 | 175.9 | 211.4 | -10.1 | -45.4 | 0.2 | 0.0 |
| direction | buy | trade | 5m | 1 | 3 | 175.9 | 212.1 | -10.1 | -87.2 | 0.2 | -41.1 |
| direction | buy | trade | close | 1 | 2 | 174.6 | 225.6 | -16.2 | -60.6 | 6.5 | 0.0 |
| direction | buy | trade | close | 1 | 3 | 174.6 | 229.4 | -16.1 | -207.2 | 6.6 | -143.0 |
| direction | buy | trade | close | 5 | 1 | 174.6 | 210.7 | -14.9 | -44.5 | 6.5 | 0.0 |
| direction | buy | trade | close | 5 | 2 | 174.6 | 222.2 | -15.8 | -56.9 | 6.5 | 0.0 |
| direction | buy | trade | close | 5 | 3 | 174.6 | 224.9 | -15.8 | -202.5 | 6.6 | -143.0 |
| direction | sell | book | close | 0 | 1 | 127.9 | 64.6 | -7.4 | 49.2 | -6.7 | 0.0 |
| direction | sell | book | close | 0 | 2 | 127.9 | 64.9 | -7.0 | 49.3 | -6.7 | 0.0 |
| direction | sell | book | close | 0 | 3 | 127.9 | 65.2 | -6.8 | 12.0 | -6.6 | -37.3 |
| direction | sell | trade | 5m | 1 | 1 | 128.6 | 204.3 | -6.7 | -82.6 | -0.2 | 0.0 |
| direction | sell | trade | 5m | 1 | 2 | 128.6 | 205.3 | -6.6 | -83.6 | -0.2 | 0.0 |
| direction | sell | trade | 5m | 1 | 3 | 128.6 | 205.9 | -6.6 | -113.9 | -0.2 | -29.7 |
| direction | sell | trade | close | 1 | 2 | 127.9 | 219.4 | 0.1 | -98.1 | -6.7 | 0.0 |
| direction | sell | trade | close | 1 | 3 | 127.9 | 222.4 | 0.1 | -138.3 | -6.6 | -37.3 |
| direction | sell | trade | close | 5 | 1 | 127.9 | 204.5 | -0.5 | -83.7 | -6.7 | 0.0 |
| direction | sell | trade | close | 5 | 2 | 127.9 | 216.3 | -0.1 | -95.2 | -6.7 | 0.0 |
| direction | sell | trade | close | 5 | 3 | 127.9 | 218.4 | -0.1 | -134.6 | -6.6 | -37.3 |
| high_gamma | cell | book | close | 0 | 1 | 246.9 | 168.3 | -38.1 | 44.8 | 4.3 | 0.0 |
| high_gamma | cell | book | close | 0 | 2 | 246.9 | 172.1 | -37.3 | 41.9 | 4.3 | 0.0 |
| high_gamma | cell | book | close | 0 | 3 | 246.9 | 171.7 | -36.5 | -15.1 | 4.4 | -58.2 |
| high_gamma | cell | trade | 5m | 1 | 1 | 235.3 | 470.8 | -26.9 | -262.4 | 0.1 | 0.0 |
| high_gamma | cell | trade | 5m | 1 | 2 | 235.3 | 474.4 | -26.4 | -265.4 | 0.1 | 0.0 |
| high_gamma | cell | trade | 5m | 1 | 3 | 235.3 | 474.6 | -26.3 | -283.3 | 0.1 | -17.7 |
| high_gamma | cell | trade | close | 1 | 2 | 246.9 | 529.7 | -25.6 | -304.1 | 4.3 | 0.0 |
| high_gamma | cell | trade | close | 1 | 3 | 246.9 | 530.7 | -25.4 | -362.9 | 4.4 | -58.2 |
| high_gamma | cell | trade | close | 5 | 1 | 246.9 | 469.6 | -24.4 | -242.9 | 4.3 | 0.0 |
| high_gamma | cell | trade | close | 5 | 2 | 246.9 | 514.0 | -26.0 | -288.9 | 4.3 | 0.0 |
| high_gamma | cell | trade | close | 5 | 3 | 246.9 | 514.7 | -25.8 | -347.4 | 4.4 | -58.1 |
| high_gamma | other | book | close | 0 | 1 | 151.3 | 65.4 | -14.2 | 71.8 | 0.0 | 0.0 |
| high_gamma | other | book | close | 0 | 2 | 151.3 | 66.0 | -14.7 | 70.7 | 0.0 | 0.0 |
| high_gamma | other | book | close | 0 | 3 | 151.3 | 66.3 | -14.6 | -20.6 | 0.1 | -91.2 |
| high_gamma | other | trade | 5m | 1 | 1 | 152.8 | 206.5 | -8.4 | -62.1 | 0.00792 | 0.0 |
| high_gamma | other | trade | 5m | 1 | 2 | 152.8 | 207.5 | -8.4 | -63.1 | 0.00792 | 0.0 |
| high_gamma | other | trade | 5m | 1 | 3 | 152.8 | 208.2 | -8.4 | -99.4 | 0.00863 | -35.7 |
| high_gamma | other | trade | close | 1 | 2 | 151.3 | 221.4 | -8.2 | -78.2 | 0.0 | 0.0 |
| high_gamma | other | trade | close | 1 | 3 | 151.3 | 224.8 | -8.1 | -172.7 | 0.1 | -91.2 |
| high_gamma | other | trade | close | 5 | 1 | 151.3 | 206.7 | -7.8 | -63.1 | 0.0 | 0.0 |
| high_gamma | other | trade | close | 5 | 2 | 151.3 | 218.2 | -8.1 | -74.9 | 0.0 | 0.0 |
| high_gamma | other | trade | close | 5 | 3 | 151.3 | 220.7 | -8.0 | -168.5 | 0.1 | -91.2 |


## E 動態避險（2026，全部成交）

來源：`extension/e_main_2026.parquet`

| sample | level | horizon | latency | rebalance | ladder | ES | cost | gamma | net | theta | vega |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | book | close | 1s | 0 | 1 | 162.6 | 34.9 | -9.4 | 118.0 | -0.2 | 0.0 |
| all | book | close | 1s | 0 | 2 | 162.6 | 35.0 | -9.7 | 117.7 | -0.2 | 0.0 |
| all | book | close | 1s | 0 | 3 | 162.6 | 35.2 | -9.6 | 19.9 | -0.2 | -97.6 |
| all | trade | 5m | 10s | 1 | 1 | 163.1 | 157.2 | -8.0 | -2.2 | -0.00246 | 0.0 |
| all | trade | 5m | 10s | 1 | 3 | 163.1 | 158.6 | -8.0 | -48.0 | -0.00189 | -44.4 |
| all | trade | 5m | 1m | 1 | 1 | 163.1 | 157.2 | -11.8 | -6.0 | -0.00247 | 0.0 |
| all | trade | 5m | 1m | 1 | 3 | 163.1 | 158.3 | -11.8 | -51.5 | -0.00192 | -44.4 |
| all | trade | 5m | 1s | 1 | 1 | 163.1 | 157.2 | -5.2 | 0.6 | -0.00246 | 0.0 |
| all | trade | 5m | 1s | 1 | 2 | 163.1 | 158.1 | -5.2 | -0.3 | -0.00246 | 0.0 |
| all | trade | 5m | 1s | 1 | 3 | 163.1 | 158.7 | -5.2 | -45.3 | -0.00189 | -44.4 |
| all | trade | close | 10s | 5 | 1 | 162.5 | 157.2 | -7.9 | -2.8 | -0.2 | 0.0 |
| all | trade | close | 10s | 5 | 3 | 162.5 | 172.6 | -7.9 | -116.0 | -0.2 | -97.8 |
| all | trade | close | 1m | 5 | 1 | 162.6 | 157.2 | -11.7 | -6.6 | -0.2 | 0.0 |
| all | trade | close | 1m | 5 | 3 | 162.6 | 172.5 | -11.8 | -120.1 | -0.2 | -98.3 |
| all | trade | close | 1s | 1 | 2 | 162.6 | 175.8 | -5.2 | -18.6 | -0.2 | 0.0 |
| all | trade | close | 1s | 1 | 3 | 162.6 | 179.9 | -5.2 | -120.3 | -0.2 | -97.6 |
| all | trade | close | 1s | 5 | 1 | 162.6 | 157.2 | -5.1 | -0.00869 | -0.2 | 0.0 |
| all | trade | close | 1s | 5 | 2 | 162.6 | 170.2 | -5.2 | -13.0 | -0.2 | 0.0 |
| all | trade | close | 1s | 5 | 3 | 162.6 | 172.7 | -5.2 | -113.0 | -0.2 | -97.6 |
| excl_locked | book | close | 1s | 0 | 1 | 162.6 | 34.9 | -9.4 | 118.0 | -0.2 | 0.0 |
| excl_locked | book | close | 1s | 0 | 2 | 162.6 | 35.0 | -9.7 | 117.7 | -0.2 | 0.0 |
| excl_locked | book | close | 1s | 0 | 3 | 162.6 | 35.2 | -9.6 | 19.9 | -0.2 | -97.6 |
| excl_locked | trade | 5m | 10s | 1 | 1 | 163.1 | 157.2 | -8.0 | -2.2 | -0.00246 | 0.0 |
| excl_locked | trade | 5m | 10s | 1 | 3 | 163.1 | 158.6 | -8.0 | -48.0 | -0.00189 | -44.4 |
| excl_locked | trade | 5m | 1m | 1 | 1 | 163.1 | 157.2 | -11.8 | -6.0 | -0.00247 | 0.0 |
| excl_locked | trade | 5m | 1m | 1 | 3 | 163.1 | 158.3 | -11.8 | -51.5 | -0.00192 | -44.4 |
| excl_locked | trade | 5m | 1s | 1 | 1 | 163.1 | 157.2 | -5.2 | 0.6 | -0.00246 | 0.0 |
| excl_locked | trade | 5m | 1s | 1 | 2 | 163.1 | 158.1 | -5.2 | -0.3 | -0.00246 | 0.0 |
| excl_locked | trade | 5m | 1s | 1 | 3 | 163.1 | 158.7 | -5.2 | -45.3 | -0.00189 | -44.4 |
| excl_locked | trade | close | 10s | 5 | 1 | 162.5 | 157.2 | -7.9 | -2.8 | -0.2 | 0.0 |
| excl_locked | trade | close | 10s | 5 | 3 | 162.5 | 172.6 | -7.9 | -116.0 | -0.2 | -97.8 |
| excl_locked | trade | close | 1m | 5 | 1 | 162.6 | 157.2 | -11.7 | -6.6 | -0.2 | 0.0 |
| excl_locked | trade | close | 1m | 5 | 3 | 162.6 | 172.5 | -11.8 | -120.1 | -0.2 | -98.3 |
| excl_locked | trade | close | 1s | 1 | 2 | 162.6 | 175.8 | -5.2 | -18.6 | -0.2 | 0.0 |
| excl_locked | trade | close | 1s | 1 | 3 | 162.6 | 179.9 | -5.2 | -120.3 | -0.2 | -97.6 |
| excl_locked | trade | close | 1s | 5 | 1 | 162.6 | 157.2 | -5.1 | -0.00869 | -0.2 | 0.0 |
| excl_locked | trade | close | 1s | 5 | 2 | 162.6 | 170.2 | -5.2 | -13.0 | -0.2 | 0.0 |
| excl_locked | trade | close | 1s | 5 | 3 | 162.6 | 172.7 | -5.2 | -113.0 | -0.2 | -97.6 |

| cut | group | level | horizon | rebalance | ladder | ES | cost | gamma | net | theta | vega |
|---|---|---|---|---|---|---|---|---|---|---|---|
| direction | buy | book | close | 0 | 1 | 163.7 | 34.5 | -14.9 | 119.5 | 5.2 | 0.0 |
| direction | buy | book | close | 0 | 2 | 163.7 | 34.7 | -16.9 | 117.3 | 5.2 | 0.0 |
| direction | buy | book | close | 0 | 3 | 163.7 | 35.0 | -16.7 | -49.3 | 5.3 | -166.6 |
| direction | buy | trade | 5m | 1 | 1 | 165.4 | 158.9 | -5.0 | 1.8 | 0.2 | 0.0 |
| direction | buy | trade | 5m | 1 | 2 | 165.4 | 159.8 | -5.0 | 0.8 | 0.2 | 0.0 |
| direction | buy | trade | 5m | 1 | 3 | 165.4 | 160.5 | -5.0 | -57.4 | 0.2 | -57.5 |
| direction | buy | trade | close | 1 | 2 | 163.7 | 177.7 | -11.9 | -20.7 | 5.2 | 0.0 |
| direction | buy | trade | close | 1 | 3 | 163.7 | 181.9 | -11.8 | -191.2 | 5.3 | -166.6 |
| direction | buy | trade | close | 5 | 1 | 163.7 | 158.8 | -10.7 | -0.6 | 5.2 | 0.0 |
| direction | buy | trade | close | 5 | 2 | 163.7 | 171.9 | -11.1 | -14.2 | 5.2 | 0.0 |
| direction | buy | trade | close | 5 | 3 | 163.7 | 174.4 | -11.1 | -183.1 | 5.3 | -166.6 |
| direction | sell | book | close | 0 | 1 | 161.5 | 35.3 | -4.0 | 116.6 | -5.6 | 0.0 |
| direction | sell | book | close | 0 | 2 | 161.5 | 35.4 | -2.6 | 118.0 | -5.6 | 0.0 |
| direction | sell | book | close | 0 | 3 | 161.5 | 35.5 | -2.6 | 87.9 | -5.6 | -29.9 |
| direction | sell | trade | 5m | 1 | 1 | 160.7 | 155.6 | -5.4 | -0.5 | -0.2 | 0.0 |
| direction | sell | trade | 5m | 1 | 2 | 160.7 | 156.5 | -5.4 | -1.3 | -0.2 | 0.0 |
| direction | sell | trade | 5m | 1 | 3 | 160.7 | 156.9 | -5.4 | -33.4 | -0.2 | -31.6 |
| direction | sell | trade | close | 1 | 2 | 161.5 | 173.9 | 1.4 | -16.6 | -5.6 | 0.0 |
| direction | sell | trade | close | 1 | 3 | 161.5 | 178.0 | 1.4 | -50.6 | -5.6 | -29.9 |
| direction | sell | trade | close | 5 | 1 | 161.5 | 155.7 | 0.3 | 0.6 | -5.6 | 0.0 |
| direction | sell | trade | close | 5 | 2 | 161.5 | 168.4 | 0.6 | -11.9 | -5.6 | 0.0 |
| direction | sell | trade | close | 5 | 3 | 161.5 | 170.9 | 0.6 | -44.2 | -5.6 | -29.8 |
| high_gamma | cell | book | close | 0 | 1 | 442.9 | 132.0 | -34.2 | 280.6 | 3.8 | 0.0 |
| high_gamma | cell | book | close | 0 | 2 | 442.9 | 141.9 | -42.6 | 262.2 | 3.8 | 0.0 |
| high_gamma | cell | book | close | 0 | 3 | 442.9 | 141.0 | -39.8 | -82.9 | 6.3 | -351.4 |
| high_gamma | cell | trade | 5m | 1 | 1 | 442.3 | 439.1 | -20.7 | -17.4 | 0.1 | 0.0 |
| high_gamma | cell | trade | 5m | 1 | 2 | 442.3 | 444.3 | -20.8 | -22.7 | 0.1 | 0.0 |
| high_gamma | cell | trade | 5m | 1 | 3 | 442.3 | 444.6 | -20.7 | -249.6 | 0.1 | -226.7 |
| high_gamma | cell | trade | close | 1 | 2 | 442.9 | 548.4 | -34.1 | -135.8 | 3.8 | 0.0 |
| high_gamma | cell | trade | close | 1 | 3 | 442.9 | 544.3 | -31.0 | -477.4 | 6.3 | -351.4 |
| high_gamma | cell | trade | close | 5 | 1 | 442.9 | 438.1 | -27.6 | -19.1 | 3.8 | 0.0 |
| high_gamma | cell | trade | close | 5 | 2 | 442.9 | 520.3 | -31.8 | -105.4 | 3.8 | 0.0 |
| high_gamma | cell | trade | close | 5 | 3 | 442.9 | 516.0 | -29.5 | -447.8 | 6.3 | -351.5 |
| high_gamma | other | book | close | 0 | 1 | 161.7 | 34.6 | -9.4 | 117.5 | -0.2 | 0.0 |
| high_gamma | other | book | close | 0 | 2 | 161.7 | 34.7 | -9.5 | 117.2 | -0.2 | 0.0 |
| high_gamma | other | book | close | 0 | 3 | 161.7 | 34.9 | -9.5 | 20.3 | -0.2 | -96.8 |
| high_gamma | other | trade | 5m | 1 | 1 | 162.2 | 156.3 | -5.2 | 0.7 | -0.00284 | 0.0 |
| high_gamma | other | trade | 5m | 1 | 2 | 162.2 | 157.2 | -5.2 | -0.2 | -0.00284 | 0.0 |
| high_gamma | other | trade | 5m | 1 | 3 | 162.2 | 157.8 | -5.2 | -44.6 | -0.00234 | -43.9 |
| high_gamma | other | trade | close | 1 | 2 | 161.7 | 174.6 | -5.1 | -18.3 | -0.2 | 0.0 |
| high_gamma | other | trade | close | 1 | 3 | 161.7 | 178.7 | -5.1 | -119.1 | -0.2 | -96.8 |
| high_gamma | other | trade | close | 5 | 1 | 161.7 | 156.4 | -5.1 | 0.1 | -0.2 | 0.0 |
| high_gamma | other | trade | close | 5 | 2 | 161.7 | 169.1 | -5.1 | -12.7 | -0.2 | 0.0 |
| high_gamma | other | trade | close | 5 | 3 | 161.7 | 171.6 | -5.1 | -111.9 | -0.2 | -96.8 |


## 誰賺誰虧：當日（2025，整體與 16 格）

來源：`extension/retail_map_2025.parquet`

| group_set | group | trader_5m | trader_raw_5m | trader_close | mm_neutral_5m | leakage |
|---|---|---|---|---|---|---|
| all | all | -365.5 | -363.6 | -412.7 | 47.7 | 142.5 |
| cell | 0.2–0.4|1–30 | -750.6 | -750.7 | -921.7 | 24.2 | 335.1 |
| cell | 0.2–0.4|31–90 | -621.9 | -618.9 | -712.7 | 109.6 | 209.3 |
| cell | 0.2–0.4|91–180 | -310.3 | -308.1 | -363.5 | -0.3 | 158.1 |
| cell | 0.2–0.4|>180 | -384.0 | -383.3 | -419.7 | 68.2 | 130.5 |
| cell | 0.4–0.6|1–30 | -212.0 | -209.6 | -513.4 | -254.8 | 311.3 |
| cell | 0.4–0.6|31–90 | -563.8 | -560.1 | -661.1 | 89.0 | 194.2 |
| cell | 0.4–0.6|91–180 | -278.0 | -276.0 | -309.0 | 9.1 | 137.4 |
| cell | 0.4–0.6|>180 | -263.3 | -261.7 | -291.1 | 35.1 | 109.0 |
| cell | <0.2|1–30 | -2,135.5 | -2,125.4 | -2,324.0 | 691.9 | 417.2 |
| cell | <0.2|31–90 | -853.0 | -855.3 | -903.9 | 199.7 | 223.9 |
| cell | <0.2|91–180 | -608.4 | -606.9 | -653.1 | 112.9 | 188.9 |
| cell | <0.2|>180 | -522.4 | -521.9 | -537.9 | 135.4 | 134.9 |
| cell | >0.6|1–30 | -317.5 | -313.3 | -528.2 | -102.3 | 256.0 |
| cell | >0.6|31–90 | -394.7 | -391.2 | -494.4 | 31.8 | 171.8 |
| cell | >0.6|91–180 | -298.9 | -296.3 | -347.4 | 31.1 | 129.0 |
| cell | >0.6|>180 | -258.5 | -256.7 | -291.2 | 48.5 | 95.0 |
| chase | against | -355.0 | -358.9 | -295.8 | 49.2 | 128.4 |
| chase | flat | -361.7 | -360.2 | -372.4 | 44.4 | 144.9 |
| chase | na | -607.0 | -605.6 | -700.5 | 155.3 | 149.3 |
| chase | with | -331.9 | -327.0 | -482.6 | 32.9 | 142.9 |
| spot_1s | adverse | -804.8 | -804.0 | -791.5 | 255.3 | 156.4 |
| spot_1s | favourable | -250.9 | -246.0 | -405.0 | -30.6 | 164.0 |
| spot_1s | none | -392.0 | -390.9 | -410.5 | 66.7 | 136.7 |
| tod | 09:00–09:30 | -579.7 | -578.3 | -651.4 | 151.4 | 141.8 |
| tod | 09:30–12:30 | -301.5 | -299.3 | -365.1 | 15.0 | 143.4 |
| tod | 12:30–13:25 | -256.8 | -255.3 | -250.9 | 0.3 | 141.2 |

| quadrant | count |
|---|---|
| 造市商不確定／交易者虧 | 42 |
| 造市商賺／交易者虧 | 32 |
| 造市商虧／交易者虧 | 15 |


## 誰賺誰虧：當日（2026，整體與 16 格）

來源：`extension/retail_map_2026.parquet`

| group_set | group | trader_5m | trader_raw_5m | trader_close | mm_neutral_5m | leakage |
|---|---|---|---|---|---|---|
| all | all | -351.1 | -349.4 | -426.6 | 83.0 | 104.3 |
| cell | 0.2–0.4|1–30 | -879.2 | -869.5 | -1,111.6 | 151.0 | 283.5 |
| cell | 0.2–0.4|31–90 | -572.2 | -566.6 | -784.1 | 138.4 | 154.0 |
| cell | 0.2–0.4|91–180 | -427.2 | -425.2 | -523.0 | 100.2 | 119.5 |
| cell | 0.2–0.4|>180 | -415.2 | -414.7 | -462.5 | 122.5 | 98.8 |
| cell | 0.4–0.6|1–30 | -416.6 | -403.5 | -845.4 | -67.7 | 270.1 |
| cell | 0.4–0.6|31–90 | -605.9 | -601.6 | -743.9 | 158.0 | 153.3 |
| cell | 0.4–0.6|91–180 | -277.3 | -275.8 | -350.6 | 44.4 | 105.1 |
| cell | 0.4–0.6|>180 | -229.6 | -228.8 | -281.5 | 43.2 | 84.6 |
| cell | <0.2|1–30 | -1,904.0 | -1,901.0 | -2,127.5 | 622.8 | 331.7 |
| cell | <0.2|31–90 | -967.8 | -965.8 | -1,065.4 | 303.4 | 185.7 |
| cell | <0.2|91–180 | -936.9 | -933.6 | -997.5 | 338.8 | 138.7 |
| cell | <0.2|>180 | -574.0 | -575.9 | -530.6 | 171.7 | 127.2 |
| cell | >0.6|1–30 | -373.5 | -365.0 | -594.0 | -30.3 | 214.6 |
| cell | >0.6|31–90 | -390.8 | -387.2 | -515.6 | 61.2 | 147.1 |
| cell | >0.6|91–180 | -355.4 | -352.3 | -461.2 | 85.0 | 106.5 |
| cell | >0.6|>180 | -225.2 | -223.9 | -283.4 | 54.8 | 72.9 |
| chase | against | -310.6 | -312.8 | -274.8 | 59.7 | 102.6 |
| chase | flat | -323.1 | -321.9 | -361.4 | 71.2 | 103.0 |
| chase | na | -819.1 | -818.6 | -894.3 | 308.7 | 103.5 |
| chase | with | -348.6 | -344.1 | -529.5 | 81.6 | 106.9 |
| spot_1s | adverse | -1,072.7 | -1,071.8 | -1,151.4 | 440.9 | 112.1 |
| spot_1s | favourable | -232.8 | -230.2 | -362.5 | 16.6 | 113.3 |
| spot_1s | none | -383.6 | -382.1 | -440.5 | 101.7 | 101.2 |
| tod | 09:00–09:30 | -624.0 | -622.2 | -707.5 | 216.8 | 101.5 |
| tod | 09:30–12:30 | -259.8 | -257.8 | -354.8 | 36.5 | 105.1 |
| tod | 12:30–13:25 | -314.2 | -313.4 | -320.0 | 71.3 | 105.0 |

| quadrant | count |
|---|---|
| 造市商賺／交易者虧 | 56 |
| 造市商不確定／交易者虧 | 32 |
| 造市商虧／交易者虧 | 1 |


## 誰賺誰虧：跨日（2025）

來源：`extension/retail_multiday_*_2025.parquet`

| hold | hold_dir_1 | hold_dir_3 | hold_dir_5 | hold_dt_1 | hold_dt_3 | hold_dt_5 | hold_raw_1 | hold_raw_3 | hold_raw_5 | hold_resid_1 | hold_resid_3 | hold_resid_5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 105.3 |  |  | -245.3 |  |  | -179.7 |  |  | -285.0 |  |  |
| 3 |  | 187.8 |  |  | -391.8 |  |  | -193.8 |  |  | -381.6 |  |
| 5 |  |  | 150.0 |  |  | -661.5 |  |  | -332.2 |  |  | -482.3 |

| group | hold_dt_5 | hold_resid_5 |
|---|---|---|
| 0.2–0.4|1–30 | -6,774.3 | -1,114.6 |
| 0.2–0.4|31–90 | -2,284.8 | -928.5 |
| 0.2–0.4|91–180 | -585.2 | -496.3 |
| 0.2–0.4|>180 | -683.7 | -407.0 |
| 0.4–0.6|1–30 | -3,341.4 | -2,334.7 |
| 0.4–0.6|31–90 | -848.3 | -667.3 |
| 0.4–0.6|91–180 | -629.7 | -371.7 |
| 0.4–0.6|>180 | -210.9 | -285.9 |
| <0.2|1–30 | -6,749.4 | -7,084.4 |
| <0.2|31–90 | -3,154.3 | -1,654.1 |
| <0.2|91–180 | -1,258.0 | -945.7 |
| <0.2|>180 | -504.6 | -630.2 |
| >0.6|1–30 | 408.3 | -730.8 |
| >0.6|31–90 | -749.7 | -576.9 |
| >0.6|91–180 | -203.4 | -307.7 |
| >0.6|>180 | -253.5 | -241.0 |

| sig_pos | sig_neg |
|---|---|
| 0 | 172 |

| hold | scope | obs_share | expired_share | settled_gap_share | unobs_near_expiry_share | s_bid_fallback_share | bid_age_median_s | fresh_share_of_obs | dt_all_bps | dt_all_se_bps | dt_fresh_bps | dt_fresh_se_bps | resid_all_bps | resid_all_se_bps | resid_fresh_bps | resid_fresh_se_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | all | 0.9278 | 0.0000 | 0.000126 | 0.0012 | 7.7e-06 | 1,018.390 | 0.5681 | -245.320 | 53.589 | -270.743 | 63.249 | -284.989 | 14.527 | -272.244 | 20.632 |
| 1 | dte_1-30 | 0.8227 | 0.0000 | 0.0102 | 0.0938 | 0.0000 | 1,630.515 | 0.4877 | -594.829 | 286.617 | -789.027 | 411.447 | -579.671 | 142.461 | -405.905 | 183.402 |
| 3 | all | 0.8345 | 0.000322 | 0.000262 | 0.0019 | 1.29e-06 | 1,069.956 | 0.5400 | -391.770 | 143.759 | -411.544 | 180.455 | -381.588 | 33.036 | -354.096 | 39.263 |
| 3 | dte_1-30 | 0.6486 | 0.0261 | 0.0212 | 0.1575 | 0.0000 | 1,614.398 | 0.4757 | -1,280.092 | 717.459 | -926.023 | 1,232.700 | -1,055.985 | 266.734 | -530.948 | 422.596 |
| 5 | all | 0.8026 | 0.0010 | 0.000557 | 0.0024 | 7.83e-07 | 1,173.559 | 0.5249 | -661.513 | 212.534 | -823.973 | 231.889 | -482.269 | 54.827 | -492.083 | 69.695 |
| 5 | dte_1-30 | 0.6403 | 0.0849 | 0.0451 | 0.1917 | 0.0000 | 2,766.825 | 0.4829 | -2,336.561 | 920.308 | -3,577.720 | 988.711 | -1,723.920 | 454.008 | -1,671.795 | 808.647 |

| quadrant | count |
|---|---|
| 造市商不確定／交易者虧 | 28 |
| 造市商賺／交易者虧 | 22 |
| 造市商不確定／交易者不確定 | 12 |
| 造市商賺／交易者不確定 | 10 |
| 造市商虧／交易者虧 | 8 |
| 造市商虧／交易者不確定 | 6 |


## 誰賺誰虧：跨日（2026）

來源：`extension/retail_multiday_*_2026.parquet`

| hold | hold_dir_1 | hold_dir_3 | hold_dir_5 | hold_dt_1 | hold_dt_3 | hold_dt_5 | hold_raw_1 | hold_raw_3 | hold_raw_5 | hold_resid_1 | hold_resid_3 | hold_resid_5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 148.2 |  |  | -125.0 |  |  | -48.1 |  |  | -196.3 |  |  |
| 3 |  | 270.1 |  |  | -234.9 |  |  | -4.1 |  |  | -274.3 |  |
| 5 |  |  | 419.9 |  |  | -336.4 |  |  | 48.2 |  |  | -371.6 |

| group | hold_dt_5 | hold_resid_5 |
|---|---|---|
| 0.2–0.4|1–30 | -3,391.0 | -3,639.9 |
| 0.2–0.4|31–90 | -1,052.7 | -893.1 |
| 0.2–0.4|91–180 | -806.4 | -537.3 |
| 0.2–0.4|>180 | -171.8 | -336.6 |
| 0.4–0.6|1–30 | -90.2 | -712.7 |
| 0.4–0.6|31–90 | -88.2 | -493.3 |
| 0.4–0.6|91–180 | -522.5 | -365.5 |
| 0.4–0.6|>180 | -151.9 | -250.1 |
| <0.2|1–30 | -5,298.6 | -5,871.8 |
| <0.2|31–90 | -603.2 | -1,660.8 |
| <0.2|91–180 | -108.6 | -685.3 |
| <0.2|>180 | -165.6 | -436.1 |
| >0.6|1–30 | 125.8 | -682.5 |
| >0.6|31–90 | -398.7 | -490.3 |
| >0.6|91–180 | -418.1 | -269.2 |
| >0.6|>180 | -224.2 | -208.3 |

| sig_pos | sig_neg |
|---|---|
| 0 | 2 |

| hold | scope | obs_share | expired_share | settled_gap_share | unobs_near_expiry_share | s_bid_fallback_share | bid_age_median_s | fresh_share_of_obs | dt_all_bps | dt_all_se_bps | dt_fresh_bps | dt_fresh_se_bps | resid_all_bps | resid_all_se_bps | resid_fresh_bps | resid_fresh_se_bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | all | 0.9559 | 0.0000 | 0.000389 | 0.00064 | 9.22e-06 | 753.647 | 0.6067 | -125.026 | 94.063 | -136.045 | 104.682 | -196.281 | 13.366 | -176.942 | 16.610 |
| 1 | dte_1-30 | 0.9125 | 0.0000 | 0.0266 | 0.0438 | 0.0000 | 727.711 | 0.4860 | -267.489 | 402.202 | -395.631 | 559.370 | -471.933 | 85.471 | -505.590 | 126.605 |
| 3 | all | 0.8965 | 0.000634 | 0.00055 | 0.0015 | 2.58e-05 | 797.064 | 0.5945 | -234.857 | 170.358 | -270.531 | 176.366 | -274.253 | 21.767 | -255.183 | 24.573 |
| 3 | dte_1-30 | 0.7965 | 0.0434 | 0.0376 | 0.1013 | 0.000625 | 632.742 | 0.5408 | -80.569 | 774.551 | -733.218 | 941.833 | -787.083 | 141.674 | -788.416 | 165.734 |
| 5 | all | 0.8734 | 0.0017 | 0.000464 | 0.0019 | 1.12e-05 | 813.800 | 0.5789 | -336.424 | 264.993 | -383.867 | 262.450 | -371.637 | 30.426 | -366.420 | 30.968 |
| 5 | dte_1-30 | 0.7956 | 0.1163 | 0.0317 | 0.1264 | 0.0000 | 628.744 | 0.5434 | -372.464 | 1,031.626 | -670.754 | 890.447 | -1,078.319 | 180.943 | -1,255.806 | 166.972 |

| quadrant | count |
|---|---|
| 造市商賺／交易者不確定 | 55 |
| 造市商不確定／交易者不確定 | 29 |
| 造市商賺／交易者虧 | 1 |
| 造市商不確定／交易者虧 | 1 |


## 跨發行商比價（2025）

來源：`extension/compare_*_2025.parquet`

| outcome | ranking | spec | cheap_minus_expensive_bps | se_bps | t | p | n | n_days | p_bh | ranked_share | spread_tie_share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ES | iv_prem | base | 65.9 | 17.6 | 3.8 | 0.00022 | 257551 | 242 | 0.000659 | 0.8077 | 0.0290 |
| ES | iv_prem | controls | 54.6 | 18.2 | 3.0 | 0.0029 | 257551 | 242 | 0.0044 | 0.8077 | 0.0290 |
| ES | spread_prem | base | -27.1 | 20.3 | -1.3 | 0.1827 | 257551 | 242 | 0.2192 | 0.8077 | 0.0290 |
| ES | spread_prem | controls | -20.1 | 20.7 | -1.0 | 0.3319 | 257551 | 242 | 0.3319 | 0.8077 | 0.0290 |
| ES | iv_prem_z | joint_per_1sd | -32.6 | 7.4 | -4.4 | 1.42e-05 | 257551 | 242 | 8.55e-05 | 0.8077 | 0.0290 |
| ES | spread_prem_z | joint_per_1sd | 29.8 | 9.2 | 3.2 | 0.0015 | 257551 | 242 | 0.0029 | 0.8077 | 0.0290 |
| trader_5m | iv_prem | base | -134.2 | 36.3 | -3.7 | 0.000275 | 246514 | 242 | 0.000824 | 0.8077 | 0.0290 |
| trader_5m | iv_prem | controls | -111.8 | 37.5 | -3.0 | 0.0032 | 246514 | 242 | 0.0048 | 0.8077 | 0.0290 |
| trader_5m | spread_prem | base | 54.3 | 42.0 | 1.3 | 0.1972 | 246514 | 242 | 0.2367 | 0.8077 | 0.0290 |
| trader_5m | spread_prem | controls | 39.9 | 42.7 | 0.9 | 0.3512 | 246514 | 242 | 0.3512 | 0.8077 | 0.0290 |
| trader_5m | iv_prem_z | joint_per_1sd | 64.4 | 15.2 | 4.2 | 3.2e-05 | 246514 | 242 | 0.000192 | 0.8077 | 0.0290 |
| trader_5m | spread_prem_z | joint_per_1sd | -52.0 | 17.5 | -3.0 | 0.0032 | 246514 | 242 | 0.0048 | 0.8077 | 0.0290 |
| hold_resid_1 | iv_prem | base | -13.2 | 26.4 | -0.5 | 0.6178 | 245938 | 242 | 0.7413 | 0.8077 | 0.0290 |
| hold_resid_1 | iv_prem | controls | -5.5 | 27.0 | -0.2 | 0.8388 | 245938 | 242 | 0.8388 | 0.8077 | 0.0290 |
| hold_resid_1 | spread_prem | base | 141.1 | 39.2 | 3.6 | 0.000384 | 245938 | 242 | 0.000937 | 0.8077 | 0.0290 |
| hold_resid_1 | spread_prem | controls | 136.4 | 38.4 | 3.5 | 0.000468 | 245938 | 242 | 0.000937 | 0.8077 | 0.0290 |
| hold_resid_1 | iv_prem_z | joint_per_1sd | 9.0 | 10.1 | 0.9 | 0.3726 | 245938 | 242 | 0.5589 | 0.8077 | 0.0290 |
| hold_resid_1 | spread_prem_z | joint_per_1sd | -54.5 | 11.6 | -4.7 | 4.05e-06 | 245938 | 242 | 2.43e-05 | 0.8077 | 0.0290 |
| hold_resid_5 | iv_prem | base | 50.4 | 41.6 | 1.2 | 0.2263 | 225645 | 242 | 0.2263 | 0.8077 | 0.0290 |
| hold_resid_5 | iv_prem | controls | 62.4 | 38.2 | 1.6 | 0.1037 | 225645 | 242 | 0.1556 | 0.8077 | 0.0290 |
| hold_resid_5 | spread_prem | base | 151.6 | 24.5 | 6.2 | 2.45e-09 | 225645 | 242 | 7.34e-09 | 0.8077 | 0.0290 |
| hold_resid_5 | spread_prem | controls | 146.3 | 23.2 | 6.3 | 1.29e-09 | 225645 | 242 | 7.34e-09 | 0.8077 | 0.0290 |
| hold_resid_5 | iv_prem_z | joint_per_1sd | -22.9 | 18.2 | -1.3 | 0.2096 | 225645 | 242 | 0.2263 | 0.8077 | 0.0290 |
| hold_resid_5 | spread_prem_z | joint_per_1sd | -45.3 | 9.6 | -4.7 | 3.93e-06 | 225645 | 242 | 7.85e-06 | 0.8077 | 0.0290 |

| spearman_iv_vs_spread_prem | n_warrant_peer_days |
|---|---|
| 0.017 | 59818 |

| issuer | ES | hold_resid_1 | hold_resid_5 | trader_5m | share_notional | mean_iv_prem_pts | mean_spread_prem_bps |
|---|---|---|---|---|---|---|---|
| 中信 | -70.5 | 58.3 | 39.5 | 151.3 | 0.0136 | 5.7 | 24.4 |
| 元大 | -68.9 | 38.8 | 22.1 | 140.7 | 0.3068 | 2.0 | -1.2 |
| 元富 | -32.4 | -119.8 | -145.4 | 67.2 | 0.0764 | -0.9 | 61.8 |
| 其他 | -14.2 | -108.1 | -186.8 | 49.2 | 0.0045 | -3.7 | 120.9 |
| 凱基 | 209.5 | -19.8 | 6.3 | -435.1 | 0.1680 | -1.4 | 97.8 |
| 國泰 | -97.7 | -48.8 | -29.8 | 215.2 | 0.0417 | -4.5 | -7.4 |
| 國票 | -34.8 | -1.6 | 2.0 | 75.0 | 0.0274 | -5.0 | -21.9 |
| 富邦 | 173.1 | -248.1 | -162.9 | -344.5 | 0.0269 | -3.1 | 115.8 |
| 永豐 | -6.9 | 38.0 | 47.8 | 11.6 | 0.1039 | -3.7 | 43.4 |
| 統一 | 0.8 | -32.4 | -64.5 | -1.7 | 0.1178 | 5.6 | 34.3 |
| 群益 | -84.9 | 74.7 | 100.9 | 170.7 | 0.1129 | -1.8 | 12.6 |

| issuer | ES | hold_resid_1 | hold_resid_5 | trader_5m |
|---|---|---|---|---|
| 中信 | 0.00149 | 0.138 | 0.525 | 0.00102 |
| 元大 | 3.24e-06 | 0.039 | 0.366 | 5.89e-06 |
| 元富 | 0.262 | 0.253 | 0.024 | 0.254 |
| 其他 | 0.820 | 0.138 | 0.028 | 0.726 |
| 凱基 | 9.42e-11 | 0.482 | 0.810 | 8.1e-11 |
| 國泰 | 5.14e-05 | 0.200 | 0.731 | 2.93e-05 |
| 國票 | 0.548 | 0.989 | 0.967 | 0.543 |
| 富邦 | 0.026 | 0.019 | 0.039 | 0.039 |
| 永豐 | 0.820 | 0.038 | 0.00752 | 0.809 |
| 統一 | 0.933 | 0.253 | 0.00169 | 0.934 |
| 群益 | 3.24e-06 | 3.32e-08 | 0.00169 | 6.32e-06 |


## 跨發行商比價（2026）

來源：`extension/compare_*_2026.parquet`

| outcome | ranking | spec | cheap_minus_expensive_bps | se_bps | t | p | n | n_days | p_bh | ranked_share | spread_tie_share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ES | iv_prem | base | 93.9 | 31.1 | 3.0 | 0.0028 | 438614 | 210 | 0.0162 | 0.8970 | 0.0240 |
| ES | iv_prem | controls | 56.4 | 26.0 | 2.2 | 0.0313 | 438614 | 210 | 0.0402 | 0.8970 | 0.0240 |
| ES | spread_prem | base | -73.4 | 27.8 | -2.6 | 0.0089 | 438614 | 210 | 0.0178 | 0.8970 | 0.0240 |
| ES | spread_prem | controls | -52.9 | 25.5 | -2.1 | 0.0391 | 438614 | 210 | 0.0402 | 0.8970 | 0.0240 |
| ES | iv_prem_z | joint_per_1sd | -40.9 | 14.6 | -2.8 | 0.0054 | 438614 | 210 | 0.0162 | 0.8970 | 0.0240 |
| ES | spread_prem_z | joint_per_1sd | 44.3 | 21.5 | 2.1 | 0.0402 | 438614 | 210 | 0.0402 | 0.8970 | 0.0240 |
| trader_5m | iv_prem | base | -188.3 | 63.3 | -3.0 | 0.0033 | 425934 | 210 | 0.0123 | 0.8970 | 0.0240 |
| trader_5m | iv_prem | controls | -118.9 | 51.2 | -2.3 | 0.0211 | 425934 | 210 | 0.0316 | 0.8970 | 0.0240 |
| trader_5m | spread_prem | base | 147.6 | 55.8 | 2.6 | 0.0088 | 425934 | 210 | 0.0175 | 0.8970 | 0.0240 |
| trader_5m | spread_prem | controls | 108.7 | 51.4 | 2.1 | 0.0354 | 425934 | 210 | 0.0425 | 0.8970 | 0.0240 |
| trader_5m | iv_prem_z | joint_per_1sd | 84.7 | 29.2 | 2.9 | 0.0041 | 425934 | 210 | 0.0123 | 0.8970 | 0.0240 |
| trader_5m | spread_prem_z | joint_per_1sd | -87.9 | 43.2 | -2.0 | 0.0431 | 425934 | 210 | 0.0431 | 0.8970 | 0.0240 |
| hold_resid_1 | iv_prem | base | 13.1 | 12.7 | 1.0 | 0.3043 | 424693 | 209 | 0.3043 | 0.8970 | 0.0240 |
| hold_resid_1 | iv_prem | controls | 19.3 | 14.8 | 1.3 | 0.1953 | 424693 | 209 | 0.2929 | 0.8970 | 0.0240 |
| hold_resid_1 | spread_prem | base | 81.6 | 11.5 | 7.1 | 2.23e-11 | 424693 | 209 | 6.7e-11 | 0.8970 | 0.0240 |
| hold_resid_1 | spread_prem | controls | 79.6 | 11.0 | 7.2 | 9.79e-12 | 424693 | 209 | 5.88e-11 | 0.8970 | 0.0240 |
| hold_resid_1 | iv_prem_z | joint_per_1sd | -7.0 | 6.4 | -1.1 | 0.2707 | 424693 | 209 | 0.3043 | 0.8970 | 0.0240 |
| hold_resid_1 | spread_prem_z | joint_per_1sd | -39.4 | 7.8 | -5.0 | 1.13e-06 | 424693 | 209 | 2.25e-06 | 0.8970 | 0.0240 |
| hold_resid_5 | iv_prem | base | 27.1 | 18.1 | 1.5 | 0.1368 | 396334 | 205 | 0.1368 | 0.8970 | 0.0240 |
| hold_resid_5 | iv_prem | controls | 46.4 | 17.1 | 2.7 | 0.0071 | 396334 | 205 | 0.0106 | 0.8970 | 0.0240 |
| hold_resid_5 | spread_prem | base | 96.1 | 21.1 | 4.6 | 8.86e-06 | 396334 | 205 | 5.32e-05 | 0.8970 | 0.0240 |
| hold_resid_5 | spread_prem | controls | 83.3 | 19.8 | 4.2 | 3.83e-05 | 396334 | 205 | 0.000115 | 0.8970 | 0.0240 |
| hold_resid_5 | iv_prem_z | joint_per_1sd | -15.9 | 8.6 | -1.9 | 0.0642 | 396334 | 205 | 0.0770 | 0.8970 | 0.0240 |
| hold_resid_5 | spread_prem_z | joint_per_1sd | -56.2 | 15.1 | -3.7 | 0.000248 | 396334 | 205 | 0.000497 | 0.8970 | 0.0240 |

| spearman_iv_vs_spread_prem | n_warrant_peer_days |
|---|---|
| -0.048 | 63109 |

| issuer | ES | hold_resid_1 | hold_resid_5 | trader_5m | share_notional | mean_iv_prem_pts | mean_spread_prem_bps |
|---|---|---|---|---|---|---|---|
| 中信 | -27.2 | -22.2 | -11.5 | 65.4 | 0.0135 | 1.6 | 108.1 |
| 元大 | -45.2 | 32.3 | 30.5 | 89.6 | 0.3677 | 4.1 | 34.9 |
| 元富 | 43.0 | -56.0 | -47.0 | -78.9 | 0.0516 | -2.8 | 95.0 |
| 其他 | 47.3 | 17.1 | 36.2 | -96.4 | 0.0525 | -2.1 | -0.6 |
| 凱基 | 137.3 | -61.6 | -23.1 | -286.4 | 0.1016 | -0.7 | 77.8 |
| 國泰 | -32.5 | -250.7 | -417.3 | 68.9 | 0.0158 | -7.9 | -40.2 |
| 國票 | 2.3 | 45.0 | 7.5 | -41.4 | 0.0155 | -1.3 | 7.4 |
| 富邦 | 50.4 | -26.9 | -9.0 | -95.8 | 0.0750 | -3.2 | 63.6 |
| 永豐 | 6.3 | -7.8 | 23.4 | -4.6 | 0.1098 | -2.8 | 25.5 |
| 統一 | -13.7 | 5.1 | -4.5 | 25.6 | 0.0829 | 10.1 | -3.4 |
| 群益 | -39.7 | 17.9 | -35.5 | 82.8 | 0.1142 | -1.9 | 33.3 |

| issuer | ES | hold_resid_1 | hold_resid_5 | trader_5m |
|---|---|---|---|---|
| 中信 | 0.392 | 0.203 | 0.653 | 0.292 |
| 元大 | 0.000131 | 5.11e-05 | 0.114 | 0.000206 |
| 元富 | 0.607 | 0.059 | 0.341 | 0.623 |
| 其他 | 0.334 | 0.203 | 0.300 | 0.292 |
| 凱基 | 0.00101 | 0.012 | 0.300 | 0.000578 |
| 國泰 | 0.244 | 0.076 | 0.114 | 0.242 |
| 國票 | 0.958 | 0.276 | 0.894 | 0.623 |
| 富邦 | 0.033 | 0.203 | 0.832 | 0.050 |
| 永豐 | 0.607 | 0.529 | 0.158 | 0.833 |
| 統一 | 0.189 | 0.568 | 0.832 | 0.242 |
| 群益 | 0.013 | 0.203 | 0.114 | 0.014 |
