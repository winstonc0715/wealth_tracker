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
