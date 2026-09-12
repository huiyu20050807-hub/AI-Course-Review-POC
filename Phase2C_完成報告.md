# Workshop-2.0 Phase 2C — AI 語意輔助架構與本機 Mock

## 本輪邊界

僅實作 mock provider，未串接或呼叫外部模型、未加入 API Key、未新增網路套件。AI 不決定適用版本、不建立法規、不改數值門檻、不替代資料或規則檢核、不覆寫人工決定。沒有修改 20 份 Excel、6 份 PDF、既有 parser、rule engine 或 Workshop-1.0-FINAL。

產品名稱保留「AI 課程審查智慧助手」，實際功能標示「AI 示範模式」。真實案件得到的是固定流程提示，狀態為「AI 無法判斷」，不假裝已完成模型語意判讀。

## 四項流程與最小輸入

選擇案件 → 開始智慧檢核 → 結果頁按「執行 AI 語意輔助（示範模式）」→ 四張語意卡加入同一份結果與優先提醒 → 人工同意／不同意／補件／保留 → 系統摘要；符合完成條件後才顯示 AI 初審草稿入口。

| 檢核 | 僅使用案件欄位 |
|---|---|
| SEM-001 課程名稱與內容一致性 | course.name、sessions.*.content |
| SEM-002 訓練目標與內容一致性 | objectives.goals_raw、sessions.*.content |
| SEM-003 招生對象與內容合理性 | audience.education_raw、audience.qualification_raw、sessions.*.content |
| SEM-004 課程內容完整性／重複性 | sessions.*.content |

不送師資名冊、單位聯絡資料、整份 Excel、PDF 或與該語意問題無關的金額／日期。招生對象與先備條件沿用資格條件原文，不增加個人資格核定。

## 規定 context

只從目前仍存在且 SHA-256 與人工「確認適用」記錄一致的文件取段落。四項分別使用「課程內容／訓練目標／招生／課程大綱」做確定性文字篩選，最多 2 段，每段最多 1,600 字；超長段落略過，不截斷後假稱完整原文。未確認、保留待確認、確認不適用或雜湊不符者均不加入。

這是一般關鍵字選段，不是語意搜尋、RAG 或自動適用判定。沒有命中時 context 為空，不補造規定。Provider request 只含短參照碼及段落文字，文件名稱、頁碼、章節與雜湊留在本機證據。規定版本或輸入變更後，舊分析標記過期並保留歷史，不無聲覆寫。

## 資料安全

ai_data_policy.py 遞迴檢查最小輸入，遮罩常見 Email、電話、身分證／居留證、帶標籤或稱謂的姓名、地址及識別號碼。檢查報告只記欄位／類型／數量，不記錄被遮罩內容。拒絕 bytes、檔案等非允許資料型態；必要文字超過總長限制時停止，不偷偷送完整檔案。

規則比對無法保證找出所有未標記姓名、特殊格式或間接識別個資，可能誤遮罩，因此本輪任何非 mock provider 一律拒絕。這不是已通過外部傳輸安全認證的 DLP 系統。外部串接必須待 Phase 2C.1 人工審查資料政策與授權，不能單靠加入 Key 開啟。

Provider 前已遮罩，mock 自身亦再次套用資料政策。本機「查看 AI 分析依據」可回查 Excel 原始儲存格；本機證據不屬於 provider 的 request。

## Mock provider

ai_provider.py 提供 SemanticProvider 介面及 analyze_semantic_check(check_type, case_context, policy_context)。目前 get_provider 僅接受 mock。

四組獨立、虛構的固定輸入／輸出測試資料演示四種狀態。只有完全吻合測試輸入才回對應固定狀態；真實案件不吻合時均回「AI 無法判斷」及明確示範提示。沒有使用 DEMO-R01～R08，也不靠關鍵字假裝做了真實 AI 語意推論。

Provider 輸出經狀態與必要欄位驗證；格式錯誤不視為分析成功。confidence 固定 null，risk_level 為 unknown，保存 limitations，不顯示準確率。提示邊界說明案件與文件文字是資料，不是可覆寫系統行為的指令；本機固定回應不執行輸入中的指令。

## Schema、人工處理與 Evidence

semantic_check.schema.json 與結果物件包含 semantic_check_id、check_name、category、input_fields、source_evidence、policy_context、prompt_version、model_name、analysis、status、risk_level、confidence、suggested_attention、limitations、human_result、human_note、created_at；另有 provider、raw_output、used_input、data_policy、completed、human_history。

結果按 case_id 留在原案件 state 的 semantic 區塊，每次重新執行建立新批次，舊批次保留於 semantic_history。human_result／human_note／confirmed_at 與 raw_output 分開；不同意 AI 建議不改原始分析。

四種 AI 狀態映射為既有卡片：未發現明顯問題→資料正常；建議確認／AI 無法判斷→待人工確認；需要補充資訊→資料不足。不因 AI 自動建立正式違規或不通過結果。真實案件目前 4 項都為示範待確認，並明示計數包含 mock 流程。

「查看 AI 分析依據」才顯示最小遮罩輸入、Excel 儲存格、已確認規定段落／頁碼、prompt version、provider、model、原始輸出、限制與資料安全檢查。第一層只顯示發現、注意原因及下一步，並說明顯示的案件文字不是 mock 已發現矛盾的證據。

## 初審草稿

必須完成資料品質檢查、可執行規則、四項有效語意示範，且所有列管項目都有已儲存的人工處理，才顯示「產生 AI 初審意見草稿」。未確認適用版本的規則仍阻擋，不會為了產生草稿自行採用文件。

草稿使用固定範本，僅取課名摘要、各層結果、語意提示、已保存人工結果及已確認規定來源；再套用遮罩。未儲存 widget 文字不進入草稿。五部分為案件摘要、系統檢核結果、建議關注事項、承辦人處理結果、待補充／待確認事項。

草稿保留「AI 產生之初審意見草稿，須經承辦人確認後始可使用」及「AI 示範模式／固定範本」標示，產生時 confirmed_at 必為 null。承辦人可編輯，需勾選核對並按保存確認；沒有自動確認、核定、寄送或提交。來源、批次或人工處理變更會使舊草稿過期，不能確認舊稿。

## 檔案

新增 ai_data_policy.py、ai_provider.py、semantic_checks.py、semantic_ui.py、semantic_check.schema.json、test_phase2c.py、phase2c_baseline.json 及本報告／測試紀錄。

修改 app.py 的階段標示，以及 workflow.py、workflow_ui.py 的第三層整合。沒有修改舊測試、Excel／PDF parser、data_checks.py、case_state.py、review_rules.py 或 candidate_rules.json。

## 驗證與後續

新增 27 項測試；完整 unittest 合計 123 項全部通過（112 項各 Phase 測試＋11 項原版測試），執行紀錄為 phase2c_tests.log。原有 Phase 1／2A／2B／2B.1 的 96 項完整回歸通過；Workshop-1.0-FINAL、20 Excel、6 PDF 及受保護核心雜湊比對通過。新增測試包含四項 schema、最小輸入、規定 context、來源追溯、個資遮罩、禁止外部 provider、禁止 socket 網路、固定輸出、提示注入作資料、人工否決、多案件隔離、草稿前置條件／五段內容／過期、實際 UI 人工編輯及確認。

Phase 2C.1 才評估：經授權的外部 provider、送出前人工審視資料、安全政策強化、真實模型提示與可靠性／幻覺測試、來源引用檢證及成本／失敗管理。尚未實作或驗證真實語意分析品質，沒有新增正式審查能力。

目前網址：http://127.0.0.1:8502/ 。原有跨連線限制不變，關機後不保證保留案件人工處理；沒有新增資料庫。
