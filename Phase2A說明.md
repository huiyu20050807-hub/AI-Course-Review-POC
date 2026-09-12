
# Workshop-2.0 Phase 2A
本階段為規定來源、版本與適用性提示，不是正式法規判定。Phase 1 的 Excel parser、資料檢查、案件狀態及測試未修改。

## 使用方式
雙擊 start_poc.cmd，開啟 http://127.0.0.1:8502/，左側選「規定與審查依據」。
選擇適用性比對案件，查看六份文件、適用性理由、版本證據、章節段落及 PDF 實體頁碼。
搜尋「師資」「訓練時數」「經費」「招生」，可切換文件名稱、章節標題、段落全文；搜尋是忽略排版空白的一般字串比對。
新載入案件會帶入來源頁；來源頁內自行切換比對案件不修改原案件處理 state。
「下載原始 PDF 核對」提供相同 SHA-256 的封存原始檔。

## 文件結構與版本
policy_document.schema.json 說明標準欄位。日期為 ISO YYYY-MM-DD 或 unknown；適用年度為民國整數或 unknown。
正文證據在 metadata_evidence，檔名提示在 filename_hints，兩者不可互換。
pages 保存 1-based 實體頁碼、頁面文字、抽取方式與狀態。
sections 保留頁碼、原文與字元位置；section_id 是系統識別碼，不是法規條號。條號只在原文明確出現「第…條」時辨識。
段落按 PDF 頁切分；跨頁條文未自動合併。審查原則的表格內容保留為版面段落，不冒認職類與條文的結構關係。
policy_store 以 PDF SHA-256 分資料夾，保存原始 PDF 及各 parser 版本 JSON；檔案改版會新增快照，不覆蓋原版。
目前 parser 為 policy-2A.2；policy-2A.1 是未驗收的開發階段解析快照，介面不使用。來源 status=unverified 代表未經人工核定，與文字解析成功不同。
相對於首次來源路徑的 JSON 名稱還包含路徑指紋，避免同內容異路徑追溯混淆。

## 適用性規則
applicable：有正文明示的計畫別與年度／期別相符，或明示期間涵蓋整個案件期別。
possibly_applicable：有明示期間，但只涵蓋案件部分期別。
not_applicable：正文明示的計畫別不符，或明示期間不相交／年度期別不同。
unknown：缺少計畫或期間證據、來源衝突、無法解析或案件條件不足。
發布／修訂日期不當作生效起日，沒有結束日期也不擅自假定永久有效。以上為文件範圍提示，不是課程法規符合判定。

目前 6 份均未找到明確的適用期間；四份計畫／手冊確認修訂日 113/12/25，但不因此宣稱適用於115年。
兩份檔名為116上半年，正文未證實該期別，正文適用年度／期別保持unknown。
作業程序正文日期115.08.03，檔名日期1150902；兩者分存，revision_date為unknown。
審查原則正文日期2026/3/17，未說明是修訂日，所以revision_date為unknown。
對115下半年案件，同計畫文件為unknown，異計畫文件為not_applicable；兩份審查文件為unknown。沒有文件直接標適用。

## 模組
policy_parser.py：掃描、直接文字抽取、metadata、章節段落、不可覆蓋版本快照。
policy_applicability.py：案件欄位轉接與透明適用性提示。
policy_search.py：關鍵字搜尋。
policy_ui.py：獨立 Streamlit 來源頁。
app.py 僅增加新頁面入口與階段標示。既有 DATA-01～08 不引用 PDF。
run_tests.py 現在執行 Phase 1、Phase 2A 與全部原版 legacy unittest。
WORKSHOP_POLICY_DIR 可指定本機 PDF 資料夾；預設使用本目錄複製的「產投規定及審查原則」。

## 完整測試
.venv\Scripts\python.exe -B -X utf8 run_tests.py
完整結果：test-all-phase2a-results.txt。
保留原 Phase 1 25 項和 legacy 11 項；新增來源、頁碼、搜尋、unknown及多案件比對測試。

## 留待 Phase 2B
條文轉為可執行規則、DATA 檢查的條文連結、人工核定適用版本、表格職類關聯結構化與跨頁條文整併。
本階段沒有外部模型、OCR、RAG、Embedding、向量庫、語意搜尋或 AI 初審意見；未對任一課程作正式法規符合判定。
