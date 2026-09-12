> 目前已新增 Phase 2A「規定與審查依據」頁面。操作及範圍請見 [Phase2A說明.md](Phase2A說明.md)，驗收見 [Phase2A驗收報告.md](Phase2A驗收報告.md)。下方保留 Phase 1 說明。

# Workshop-2.0 Phase 1
版本：Workshop-2.0-PHASE1。此目錄為獨立工作副本，並非 Workshop-1.0-FINAL 封版。

## 啟動
雙擊本目錄 start_poc.cmd，保留命令視窗，瀏覽器開啟 http://127.0.0.1:8502/ 。
1.0 使用 8501；2.0 使用 8502，兩者不共用案件狀態。

若換電腦，於此目錄建立獨立環境：
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\start_poc.cmd
```
目前環境：Python 3.14、Streamlit 1.63.0、openpyxl 3.1.5。
啟動僅監聽本機 127.0.0.1；不連 AI API，已關閉 Streamlit 使用統計。

## 操作
1.「選擇案件」自動掃描本目錄的「訓練班別計畫表」，顯示 20 份可辨識案件。
2. 下拉選單選案可先預覽；預覽不建立審查 state。
3. 按「載入此案件」才建立／取回該案件狀態。
4. 按「執行基本資料一致性檢查」顯示 DATA-01～08。
5. 選檢查項目，查看計算結果、檢查方法、Excel 證據，選擇處理結果、輸入備註並儲存。
6. 回「選擇案件」切換 A→B→A，已儲存資料按案件隔離保留。未儲存的表單編輯不算已處理。

可以用 WORKSHOP_EXCEL_DIR 環境變數指定其他唯讀來源資料夾，未設定則使用本副本的 20 份 Excel。
不將檔名中的「通過／未通過」當成判斷輸入；來源檔名只作追溯。
關閉連線、重開瀏覽器或關機後不保證保留處理狀態；本階段沒有資料庫或跨工作階段保存。

## 資料與解析
excel_parser.py：掃描、表頭定位、合併範圍讀取、區塊解析及技檢格式辨識。
不使用盤點列號派送 parser。第 17 份以「技檢訓練(時數)」表頭辨識，H 欄為技檢時數，I:L 為課程內容。
case_data 保存 source、plan、organization、course、objectives、audience、sessions、instructors、assistants、facilities、budget、other_sections、derived、field_sources、parse_report。
field_sources 保存相對檔名、sheet、儲存格、合併範圍、原始值與欄位狀態。
Decimal 用於計算；空白保存 None；無法解析數值／日期或公式不會當成有效值。
未知結構回報 failed 並禁止載入；個別型別錯誤回報 partial，相關檢查顯示「無法解析」。
中後段原文以區塊保留；材料明細尚未拆成完整的單價／數量表。
相對來源路徑、內容雜湊、sheet 與 parser 版本共同識別案件資料版本，來源更新不沿用舊處理結果。
st.cache_data 只快取解析結果（記憶體），建立案件時深複製；承辦人 state 不放全域快取。
金額比例原文保留，不擅自指定材料費占比分母。

## 檢查界線
data_checks.py 只計算時數、經費及資料提供情形。使用「資料一致／資料不一致／資料未提供／無法解析／待人工確認」。
DATA-01～08 不是 DEMO-R01～R08，也不是正式法規。資料未提供不等於不符合。
目前每份案件：前 5 項算術檢查及核心欄位有值，共 6 項資料一致；師資與課表教師／助教 2 項資料未提供。
不代表案件審查通過。
沒有 PDF 解析、RAG、向量庫、AI 語意判斷、正式歷史案例、AI 草稿或正式法規判定。

## 完整 unittest
```powershell
.\.venv\Scripts\python.exe -B -X utf8 run_tests.py
```
run_tests.py 執行 test_phase1.py，並以獨立程序與目錄執行 legacy_v1 的全部 11 項原有 unittest。
只測 Phase 1 可用 python -B -m unittest -v test_phase1。
測試中的異常資料只在記憶體改寫 XLSX XML，不寫回原始 Excel。
封版測試核對相鄰 AI_Course_Review_POC 與 legacy_v1 的 10 項雜湊，並核對原始／複製 20 份 Excel。
完整測試輸出見 test-results.txt。

## 1.0 保護
相鄰 AI_Course_Review_POC 保持封版不變。
legacy_v1 保存原版程式、DEMO-R01～R08、三筆虛構歷史案例、原測試及封版清單，僅供隔離回歸驗證。
2.0 應用不 import demo_data 或 review_logic，也不以示範值補入真實案件。
本目錄沿用的 1.0 說明文件均已移到 legacy_v1；本 README 才是 2.0 操作說明。
