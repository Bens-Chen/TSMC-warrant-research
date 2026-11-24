# 散戶流量毒性、避險成本與權證造市：以台積電權證逐筆資料為例

站在權證發行商的角度，用 2330（台積電）認購與認售權證的逐筆成交與成交當下報價，回答三個問題：

1. 接散戶的單，賺到的價差扣掉避險成本後，夠不夠彌補被資訊交易打到的損失？
2. 哪些單有毒？毒性來自發行商報價太慢，還是對方真的有資訊？
3. 反過來看，散戶買權證的成本有多高，選哪一檔比較便宜？

完整論文：[`reports/report.pdf`](reports/report.pdf)（原稿 [`reports/report_draft.md`](reports/report_draft.md)）。

## 資料與樣本

| 項目 | 內容 |
|---|---|
| 樣本期 | 2025-01-02 至 2026-11-18，453 個交易日（排除 Shioaji 無權證逐筆的 2026-01-09） |
| 訓練期／測試期 | 2025 年（243 天）／2026 年（210 天），測試期只執行一次 |
| 逐筆資料 | 永豐金 Shioaji API：權證與 2330 現貨逐筆，含成交後報價與內外盤旗標 |
| 權證條款 | 臺灣證券交易所與 TEJ，依「代號＋日期」點時對應 |
| 存活偏誤 | API 只列出仍掛牌的權證。以自建合約補抓已下市權證共 212,380 個權證 × 日，每月成交量覆蓋率 ≥ 99.2% |

原始資料（TEJ、Shioaji、TWSE）受授權限制，不包含在本 repo。repo 只有程式碼與彙總結果。

## 方法

- **價差拆解**：有效價差 ES = 已實現價差 RS + 價格衝擊 PI。現貨 markout M(h) 以 delta 與行使比例換算為權證成交金額的比例，h 由 1 秒到收盤，主要期間為 5 分鐘。
- **成交當下報價**：Shioaji 只記錄成交後報價。以交易所內外盤旗標與同一委託的成交序列重建成交當下的買賣價。
- **避險成本**：以悲觀、中性、樂觀三種情境呈現區間（現股或個股期貨，逐筆、單檔或整本抵銷）。
- **推論**：標準誤按交易日群聚，跨日持有用 Newey-West，探索性切法以 BH-FDR 校正。
- **事前登記**：主要設定、門檻與判定標準在看到結果前寫入 [`docs/decisions.md`](docs/decisions.md)，每次設計變更也記錄於此。

## 主要結果（2025 年，bps，相對權證成交金額）

| 指標 | 結果 |
|---|---|
| 有效價差 | 153.1 |
| 五分鐘價格衝擊（去趨勢） | 25.4 |
| 發行商淨收益：悲觀／中性／樂觀避險 | −79.5／+25.8／+94.3 |
| 中性淨收益，若避險稅率用一般稅率 0.3% | −10.4（與零無顯著差異） |
| 樣本外毒性分數最毒減最不毒五分位（2026） | 36.1 |

- 毒性集中在到期 30 天內、價外與現貨剛變動後的成交。但高毒性成交佔成交金額的比例小，發行商的盈虧主要由避險方式決定。
- 對損益影響最大的是 2330 剛成交、權證報價尚未更新時進場的成交，屬報價延遲型的毒性。
- 權證淨 delta 流量對 2330 未來五分鐘報酬有統計上顯著的預測力，但幅度遠低於交易成本，無法用來獲利。
- 散戶扣除標的方向後，持有權證一至五個交易日沒有任何分組有顯著正報酬。同類權證中挑前一日價差最窄者，五日持有成本約少 1% 至 1.5%。

限制與穩健性見論文第 6 節與第 9.3 節。

## 程式結構

```
wtox/
  pricing.py, iv.py, greeks.py, warrant.py   定價、隱含波動率、Greeks
  data/          TEJ、TWSE、Shioaji 下載與已下市權證補抓（backfill）
  research/
    config.py    所有研究參數（期間、h、費率、門檻、樣本切點）
    terms.py     TWSE＋TEJ 點時條款
    trades.py    逐筆 panel：只含成交當下已知的資訊
    markout.py   labels：只含未來中價（唯一可以往未來看的模組）
    toxicity.py  價差拆解、去趨勢、避險成本、群聚標準誤
    flow.py      權證淨 delta 流量與 2330 報酬
    robustness.py, oos.py, hedging.py, retail.py, compare.py, magnitude.py
    pipeline.py  依序重跑 panel、labels、資料驗證與主分析
tests/           每個模組的合成資料測試
reports/         論文、圖表與彙總數字（numbers.md）
docs/decisions.md  事前登記與設計變更紀錄
```

特徵（panel）與標籤（labels）分檔存放，panel 不含任何成交時點之後的資訊。

## 重現

```bash
python -m venv .venv && .venv/bin/pip install -e ".[plot,dev]"
.venv/bin/python -m pytest
.venv/bin/python -m wtox.research.pipeline --data ../data     # panel、labels、資料驗證、第 3–4 階段、延伸分析
.venv/bin/python -m wtox.research.oos --data ../data          # 樣本外（第 5 階段）
.venv/bin/python -m wtox.research.retail --data ../data       # 散戶視角（加 --multiday 為跨日持有）
.venv/bin/python -m wtox.research.compare
.venv/bin/python -m wtox.research.magnitude
bash reports/build_pdf.sh
```

需要原始資料放在 `../data/`。樣本外評估設計為只執行一次，結果已存在時會拒絕重跑。論文中的數字皆由 `reports/make_numbers.py` 從結果檔產生，彙總於 [`reports/numbers.md`](reports/numbers.md)。PDF 以 [tectonic](https://tectonic-typesetting.github.io/) 編譯。
