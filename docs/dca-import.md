# 定期定額（DCA）匯入功能使用說明

本文件說明 WealthTracker 的定期定額資料匯入功能：CSV 格式、欄位對照、
重複匯入的合併與更新規則，以及相關 API 端點。

## 功能入口

- 儀表板右上角的「定期定額」按鈕 → `/dashboard/dca`
- DCA 頁面右上角「匯入資料」開啟匯入視窗

匯入視窗提供：

- **下載 CSV 範本**：取得標準格式範本（含兩列範例資料）
- **支援欄位對照**：展開檢視每個欄位可用的名稱別名
- **預覽**：dry-run 試算，顯示逐列將發生的動作與錯誤，不寫入任何資料
- **開始匯入 / 確認匯入**：實際寫入

建議流程：選擇檔案 → 預覽 → 確認結果無誤後再匯入。

## CSV 格式

- 編碼必須是 UTF-8（含 BOM 亦可，Excel 匯出的「CSV UTF-8」格式即符合）。
- 第一列為標題列，欄位名稱比對寬鬆，支援中英文別名（見下表）。
- 每一列代表一次扣款（執行）紀錄。

### 欄位對照表

| 欄位 (key) | 中文名稱 | 必填 | 可用別名 | 說明 |
|---|---|---|---|---|
| `execution_date` | 扣款/成交日期 | ✅ | date、成交日期、交易日期、扣款日期、委託日期、申購日期 | 支援 `2026-05-03`、`2026/05/03`、`20260503`、民國年 `115/05/03` |
| `symbol` | 標的代碼 | ✅ | stock_id、ticker、股票代號、證券代號、標的代碼、商品代號 | 例如 2330、0050、AAPL |
| `asset_name` | 標的名稱 | | name、stock_name、股票名稱、證券名稱、標的名稱、商品名稱 | 顯示用，可留空 |
| `investment_type` | 投資方式 | | type、投資方式、扣款方式、委託類型 | `amount`（定額）/ `shares`（定股），也接受「定期定額 / 定期定股」等中文；未填預設定額 |
| `target_amount` | 每次投資金額 | | amount、每次投資金額、投資金額、委託金額、設定金額 | 未填時以扣款金額推導 |
| `target_shares` | 每次投資股數 | | shares、每次投資股數、投資股數、委託股數、設定股數 | 定股模式使用；未填時以成交股數推導 |
| `execution_days` | 每月扣款日 | | execution_day、扣款日、每月扣款日 | 多個日期以逗號分隔（如 `3,16`）；未填時以成交日期的「日」推導 |
| `actual_price` | 成交價格 | | price、成交價格、成交價、單價、成交單價 | 與股數擇一提供即可推導其餘欄位 |
| `quantity` | 成交股數 | | 成交股數、股數、成交數量、數量 | 此次實際成交股數 |
| `fee` | 手續費 | | 手續費、交易手續費 | 未填視為 0 |
| `total_cost` | 總扣款金額 | | 扣款金額、成交金額、總金額、總扣款金額、淨收付 | 含手續費總額；未填時自動計算 |
| `currency` | 幣別 | | 幣別、交易幣別 | 未填預設 `TWD` |
| `status` | 狀態 | | 狀態、入帳狀態 | `pending` / `confirmed` / `skipped` / `failed` 或中文「待確認、已確認、已入帳、已跳過、失敗」 |
| `note` | 備註 | | 備註、說明 | 寫入執行紀錄與交易備註 |
| `broker` | 券商 | | 券商、來源 | 未填時使用匯入視窗選擇的券商 |

> 欄位對照的單一資料來源是
> `apps/backend/app/broker/dca_csv_parser.py` 的 `FIELD_ALIASES`，
> 前端提示與 `GET /api/dca/import-columns` 都由它產生。

### 範例

```csv
execution_date,symbol,asset_name,investment_type,target_amount,target_shares,execution_days,actual_price,quantity,fee,total_cost,currency,status,note
2026-07-03,2330,台積電,amount,3000,,"3,16",1050,2,1,2101,TWD,confirmed,永豐定期定額
2026-07-16,0050,元大台灣50,amount,2000,,"3,16",203.5,9,1,1832.5,TWD,pending,
```

## 匯入與更新（Upsert）規則

匯入的目的之一是讓同一份資料可以反覆匯入更新，不會重複入帳：

1. **計畫（Schedule）合併**：以「使用者 + 投資組合 + 券商 + 標的」為
   唯一鍵。已存在時更新目標金額/股數、標的名稱等欄位，並把新的扣款日
   合併進 `execution_days`；不存在時建立新計畫。
2. **執行紀錄（Execution）更新**：以「計畫 + 執行日期」判斷。同一天的
   紀錄再次匯入時更新原紀錄，不會新增第二筆。已確認的紀錄不會因為
   無狀態的重複匯入被降回待確認。
3. **交易（Transaction）同步**：狀態為 `confirmed`（或勾選「匯入後直接
   入帳」）時建立交易；若該執行已有對應交易，改為更新原交易，避免
   重複入帳。
4. **逐列 SAVEPOINT**：任何一列失敗只影響該列，不會留下半套資料，
   其他列照常匯入；失敗原因會出現在結果的錯誤明細。

## 匯入預覽（dry-run）

`POST /api/dca/import-csv/preview` 與正式匯入走完全相同的程式路徑
（同一個 `DCAService.import_records`），差別只在最後 rollback，
因此預覽數字與實際匯入結果一致。回應中的 `details` 提供逐列明細：

- `schedule_action`：`create` / `update` / `unchanged`
- `execution_action`：`create` / `update`
- `transaction_action`：`create` / `update` / `none`
- `status`：`ok` / `error`（`error` 時附錯誤訊息）

## API 端點

所有端點皆掛在 `/api/dca` 之下，除範本下載外都需要 Bearer Token。

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/import-template` | 下載 CSV 範本（無需登入，UTF-8 含 BOM） |
| GET | `/import-columns` | 欄位、必填狀態與別名對照（JSON） |
| POST | `/import-csv/preview` | 匯入預覽（dry-run），不寫入資料 |
| POST | `/import-csv` | 正式匯入 |
| POST | `/schedules` | 建立計畫 |
| GET | `/schedules` | 計畫列表 |
| PATCH | `/schedules/{id}` | 更新計畫 |
| DELETE | `/schedules/{id}` | 刪除計畫（連帶刪除執行紀錄） |
| POST | `/schedules/{id}/toggle` | 啟用/停用計畫 |
| GET | `/executions/pending` | 待確認執行紀錄 |
| GET | `/executions/history` | 執行歷史（分頁） |
| POST | `/executions/{id}/confirm` | 確認執行並建立交易 |
| POST | `/executions/{id}/skip` | 跳過執行 |
| POST | `/execute-now` | 手動觸發今日排程（除錯用） |

`import-csv` 與 `import-csv/preview` 皆為 `multipart/form-data`：

| 欄位 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `portfolio_id` | string | （必填） | 投資組合 ID |
| `category_id` | int | 1 | 預設資產類別（1 台股 / 2 美股 / 3 加密貨幣） |
| `broker_format` | string | `standard` | `standard` 或 `sinopac` |
| `broker` | string | `sinopac` | 券商代碼 |
| `auto_confirm` | bool | false | 匯入後直接入帳 |
| `file` | file | （必填） | CSV 檔案 |

## 排程行為

啟用中的計畫由背景排程每日 20:30（Asia/Taipei）檢查：當天是每月扣款日
且為交易日（非週末）時，建立待確認執行紀錄並取得預估收盤價；
設定 `auto_confirm` 的計畫會直接建立交易。

## 驗證

```bash
# 後端匯入/預覽工作流程測試（含範本、欄位對照、dry-run 驗證）
python3 scripts/test/test_dca_import_workflow.py

# 資料庫 migration
cd apps/backend && alembic upgrade head

# 前端建置
npm run build --workspace apps/web
```
