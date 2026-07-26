# 定期定額匯入與後續更新

## Plan

- [x] 確認專案結構、Git 狀態與既有 DCA 初稿
- [x] 補齊 DCA CSV 解析器，支援標準與永豐欄位別名
- [x] 新增 DCA 匯入 upsert 服務，避免重複建立 schedule、execution、transaction
- [x] 新增匯入 API 與前端匯入入口
- [x] 補 DCA 資料表 Alembic migration
- [x] 新增匯入更新流程測試腳本
- [x] 執行後端語法檢查、匯入測試與前端建置驗證

## Review

- 匯入資料以「使用者、投資組合、券商、標的」合併為同一個定期定額計畫。
- 同一計畫與同一天執行紀錄重複匯入時，更新既有 execution。
- 若 execution 已有 transaction，後續匯入會更新該 transaction，不會重複入帳。
- 驗證已通過：Python 語法檢查、DCA 匯入重複更新測試、Alembic 空庫升級、Next.js production build、Playwright DCA 匯入 UI 檢查。

# 定期定額匯入後續增強（預覽、範本、欄位對照、文件）

## Plan

- [x] 後端新增匯入預覽（dry-run）端點 `POST /dca/import-csv/preview`
      （與正式匯入共用 `import_records`，加 `collect_details` 收集逐列明細後 rollback）
- [x] 後端新增 CSV 範本下載 `GET /dca/import-template` 與欄位對照 `GET /dca/import-columns`
      （單一資料來源：`dca_csv_parser.FIELD_ALIASES` / `FIELD_INFO`）
- [x] `DCAImportRecord` 增加 `source_row`，錯誤訊息與明細列號對齊實際 CSV 列
- [x] 前端匯入視窗：範本下載、欄位對照展開、預覽（逐列動作 + 完整錯誤明細）、
      預覽後按鈕轉為「確認匯入」；檔案或設定變更會使預覽失效
- [x] 錯誤顯示改為完整清單（可捲動），不再只顯示前 3 筆
- [x] 測試腳本補範本 round-trip、欄位對照、dry-run 預覽與 rollback 驗證
- [x] 新增使用說明與 API 文件 `docs/dca-import.md`

## Review

- 預覽與正式匯入走同一條程式路徑，僅差最後 rollback，試算結果與實際一致。
- 測試腳本補上 SQLite savepoint 官方設定（pysqlite 驅動會把 SAVEPOINT 隱式
  提交，導致外層 rollback 失效；正式環境 PostgreSQL 不受影響）。
- 已驗證通過：
  - `python3 scripts/test/test_dca_import_workflow.py`（含預覽 dry-run 斷言）
  - `tsc --noEmit`（strict 模式，含 dca/page.tsx 與 api-client.ts）
  - API router 載入、範本下載與欄位對照端點實際執行
  - Python 語法檢查、範本 CSV round-trip、中文別名與民國年日期解析
- 待本機順手確認：`npm run build --workspace apps/web`
  （型別檢查已通過，僅剩打包步驟未實際執行）。
