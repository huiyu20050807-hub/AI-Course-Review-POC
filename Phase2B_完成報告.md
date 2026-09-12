# Workshop-2.0 Phase 2B 完成報告

日期：2026-09-11。本階段僅本機 PDF 原文整理、確定性公式比對及人工確認；不是正式審查系統。

## 1. 候選規則盤點

共 20 個候選（按來源文件分開建版本，不表示 20 個互不重複的法律要求）：A 類 2、B 類 8、C 類 10。完整原文、來源 SHA-256、章節 ID、PDF 實體頁碼與 Excel 欄位映射保存於 candidate_rules.json。

| ID | 候選 | 類別 | 來源 PDF | 實體頁碼 |
|---|---|---|---|---|
| REV-001 | 民俗調理／推拿整復師資與技檢認列 | B | 116 年上半年各職類審查標準作業原則 | 1 |
| REV-002 | 師資佐證與課程關聯 | B | 116 年上半年訓練計畫審查標準作業程序 | 10 |
| REV-003 | 核定補助人數與例外 | C | 提升勞工自主學習計畫 | 4 |
| REV-004 | 班次時數與開課期間 | B | 提升勞工自主學習計畫 | 4 |
| REV-005 | 年度期別與開訓日期 | B | 提升勞工自主學習計畫 | 4 |
| REV-006 | 訓練地點與服務區域 | C | 提升勞工自主學習計畫 | 4 |
| REV-007 | 單一人時成本公式一致性 | A | 提升勞工自主學習計畫作業手冊 | 26 |
| REV-008 | 每日與時段訓練時數 | B | 提升勞工自主學習計畫作業手冊 | 6 |
| REV-009 | 室外教學時數比例 | C | 提升勞工自主學習計畫作業手冊 | 6 |
| REV-010 | 同一講師授課時數 | C | 提升勞工自主學習計畫作業手冊 | 6 |
| REV-011 | 行政管理費支用比例 | C | 提升勞工自主學習計畫作業手冊 | 27 |
| REV-012 | 核定補助人數與例外 | C | 產業人才投資計畫 | 4 |
| REV-013 | 班次時數與開課期間 | B | 產業人才投資計畫 | 4 |
| REV-014 | 年度期別與開訓日期 | B | 產業人才投資計畫 | 4 |
| REV-015 | 訓練地點與服務區域 | C | 產業人才投資計畫 | 4 |
| REV-016 | 單一人時成本公式一致性 | A | 產業人才投資計畫作業手冊 | 26 |
| REV-017 | 每日與時段訓練時數 | B | 產業人才投資計畫作業手冊 | 6 |
| REV-018 | 室外教學時數比例 | C | 產業人才投資計畫作業手冊 | 6 |
| REV-019 | 同一講師授課時數 | C | 產業人才投資計畫作業手冊 | 6 |
| REV-020 | 行政管理費支用比例 | C | 產業人才投資計畫作業手冊 | 27 |

A 指公式本身可完全計算，不表示文件版本或案件核定能自動判斷。B/C 目前僅提供原文與人工確認，沒有假裝完成法律檢核。這是第一批候選盤點，未宣稱完整涵蓋六份文件的所有條文。

## 2. 已實作的可執行規則

REV-007、REV-016，版本 2B.1。兩份手冊 PDF 實體第 26 頁均有「單一人時成本=固定費用÷人數÷時數」。

- 自主學習手冊 SHA-256：1f3bd64cfe4f0e267cb5e52a99c31954eed1ea3ba1e04375cbeeae4ac516ac8e。
- 產投手冊 SHA-256：4842ea67ebe4ae10145be49bee25a9c89af19e92bab10ec541f9f5a0a2c626cc。
- 映射：budget.fixed_total ÷ course.enrollment ÷ course.declared_hours，比對 budget.hourly_cost。
- 使用 Decimal 轉分數精確比較，不自行增加四捨五入容差。若差異可能來自顯示精度，仍提示人工核對，不作核定或退件結論。
- 缺資料為「資料不足」；無效數字或分母不正為「無法執行」。

另以 20 份 Excel 單獨測試公式 evaluator，得到 10 筆精確一致、10 筆「疑似不符合規則條件」。這只是原式精確比較，未儲存為使用者的文件適用確認，也不代表 10 件違規；差異須進一步核對原表計價與顯示精度。應用程式仍須先完成兩層人工確認才會計算。

## 3. 適用版本與資料限制

目前來源文件仍沒有足以自動認定 115 下半年適用的正文期間證據。所有候選在未經人工確認對應文件之前，都不會自動執行；計畫別不同亦阻擋。REV-007／016 除確認文件適用外，另須承辦人核對公式及欄位映射後採用。

檔名 116 上半年的 REV-001／002 不會自動套用 115 下半年，且本階段本來就是人工候選。其他文件也不因修訂日期早於案件而自行視為持續有效。

缺資料項目：REV-003／012 缺核定補助人數及例外核准；REV-006／015 缺核定服務區域／附件；REV-009／018 缺室外標記；REV-010／019 缺教師身分；REV-011／020 缺實際支用明細。不得拿計畫人數冒充核定人數，亦不得拿預算冒充支出。REV-001／002 另缺師資資格佐證，且需要人工判讀。

## 4. 檔案與 schema

新增：build_candidate_rules.py、candidate_rules.json、review_rules.py、review_ui.py、test_phase2b.py、rule_store/ 規則定義快照、本報告、phase2b_tests.log。來源驗證亦沿用 policy_store/ 的雜湊 PDF 與解析快照。

修改：app.py（新增導覽分支）、policy_ui.py（加入人工確認區）、run_tests.py（更新結果標籤）。未修改 excel_parser.py、data_checks.py、case_state.py、test_phase1.py、test_phase2a.py 或 Workshop-1.0-FINAL。

review_rule 欄位：rule_id、rule_name、category、description、rule_type、severity、applicable_plan_types、required_case_fields、evaluation_method、parameters、source_documents、source_sections、source_pages、source_text、version、status、created_from、created_at、requires_human_confirmation、notes；另有 fully_programmable、requires_human_interpretation、numeric_threshold、data_sufficiency。

rule_type 結構接受 arithmetic、presence、consistency、threshold、cross_field、manual；本輪僅啟用已核對的 hourly_formula evaluator，其餘不是已實作的任意規則引擎。未支援的方法不能藉 schema 類型直接執行。numeric_threshold 對 B/C 僅整理原文提示，不作執行參數。

## 5. 證據鏈與狀態

每次執行深複製案件值、Excel 檔案／sheet／儲存格來源、完整規則定義、規則內容摘要、PDF 雜湊／章節／頁碼／原文、計算方式、system_result，再另存 human_result／human_note／時間與歷史。

session_state.rule_cases[case_id] 與 Phase 1 的 cases 分開。documents 保存原始 system_applicability 及人工結果；document_history 保留修改歷程。approvals 按完整規則摘要隔離。runs 保存每次執行的文件確認、規則確認及結果快照。

人工改判不刪 system_result；切 A→B→A 不共用確認。修改文件確認後 revision 增加，舊結果標示過期且不能再確認，需重跑；舊歷史仍存在。rule_store/rule_id/version/definition.json 固定同版定義，變更必須新版本。PDF 更新造成來源雜湊不符／來源版本不在清單時阻擋，不替換舊案件依據。

保存範圍為本次 Streamlit 連線：頁面切換可保留，關機或新連線不保證保留；規則定義和 PDF 快照則在本機磁碟。尚無跨連線案件資料庫、身分驗證及正式稽核簽章。

## 6. 測試

執行 `.venv\Scripts\python.exe -X utf8 -B run_tests.py`：本次新增 23 項 unittest，總數 81，全部通過（70 項 Phase 測試＋11 項原版測試）。原有 Phase 1／2A 共 58 項完整回歸通過。

測試包括 20 個候選真實來源、頁碼與原文、缺來源／虛構參數拒絕、unknown 阻擋、人工確認／不適用、公式確認、資料檢查分離、改判保留系統結果、多案件隔離、舊快照不變、同版禁止替换、PDF 更新阻擋、過期確認阻擋、缺資料／零分母／數字差異、不同計畫、20 案公式及儲存格證據。Streamlit AppTest 實際完成載入案件→確認文件→採用公式→執行→查看結果→改判→跨頁返回。

Workshop-1.0-FINAL 及 legacy_v1 封版 SHA-256 比對測試通過；原有 20 份 Excel 雜湊、Phase 1 核心模組雜湊亦保持一致。詳細輸出在 phase2b_tests.log。

## 7. 操作與後續

網址：http://127.0.0.1:8502/。

選擇案件並載入 →「規定與審查依據」核對並儲存適用文件 →「審查規則檢核」核對並採用對應計畫的公式 → 執行規則檢核 → 下拉選 REV-007 或 REV-016 查看證據鏈 → 輸入人工確認／改判與備註。

留待 Phase 2C：經業務確認後擴充條件與例外、補齊佐證／核定資料、確認費用精度與規則解讀、更多 evaluator，以及另行評估案件持久儲存與正式治理。未實作任何外部 LLM、RAG、AI 初審意見或相似案例；本階段沒有自動法規適用認定。
