# Phase 2A 驗收報告

完整 unittest：58 項全部通過（Phase 1 25＋legacy 11＋Phase 2A 22）。

6/6 PDF、234/234 頁直接文字解析成功；未使用 OCR。共 1701 個章節／段落切片，不代表同數量法規條文。

|文件標題|計畫別|正文年度／期別|頁數|切片數|115下半年產投案|115下半年自主案|
|---|---|---|---:|---:|---|---|
|產業人才投資方案各職類課程審查標準作業原則|unknown|unknown/unknown|2|23|unknown|unknown|
|產業人才投資方案訓練計畫審查標準作業程序|both|unknown/unknown|29|194|unknown|unknown|
|提升勞工自主學習計畫|self_learning|unknown/unknown|22|180|not_applicable|unknown|
|提升勞工自主學習計畫作業手冊|self_learning|unknown/unknown|80|560|not_applicable|unknown|
|產業人才投資計畫|industrial|unknown/unknown|22|185|unknown|not_applicable|
|產業人才投資計畫作業手冊|industrial|unknown/unknown|79|559|unknown|not_applicable|

## 搜尋驗收

- 師資：82 個段落命中；測試逐筆確認文件、頁碼與原文。
- 訓練時數：43 個段落命中；測試逐筆確認文件、頁碼與原文。
- 經費：106 個段落命中；測試逐筆確認文件、頁碼與原文。
- 招生：14 個段落命中；測試逐筆確認文件、頁碼與原文。

## 原始檔案與版本

### 116年度上半年產業人才投資方案各職類課程審查標準作業原則1150317.pdf
- SHA-256：49cd242c2787d66220ebb42b3d298b9bf5e3e9c6ec4ecfd158dc2b0b174663ef
- 正式標題：產業人才投資方案各職類課程審查標準作業原則
- 正文發布日：unknown
- 正文修訂日：unknown
- 正文所列日期（不推定性質）：2026-03-17
- 適用起迄：unknown / unknown
- 檔名提示：{"roc_year": 116, "period": "上半年", "date": "2026-03-17"}
- 解析：success，2/2 頁

### 116年度上半年產業人才投資方案訓練計畫職類審查標準作業程序1150902.pdf
- SHA-256：85949fa4738ec93ac86b46be0888afc4bf916e0eea70a04cc0fb3a02d47eca09
- 正式標題：產業人才投資方案訓練計畫審查標準作業程序
- 正文發布日：unknown
- 正文修訂日：unknown
- 正文所列日期（不推定性質）：2026-08-03
- 適用起迄：unknown / unknown
- 檔名提示：{"roc_year": 116, "period": "上半年", "date": "2026-09-02"}
- 解析：success，29/29 頁

### 提升勞工自主學習計畫.pdf
- SHA-256：c6b02e87d50d7a2c9c81215fe562dcbb07ef51237d3ad9062e1fc17ac0e00acd
- 正式標題：提升勞工自主學習計畫
- 正文發布日：2024-12-25
- 正文修訂日：2024-12-25
- 正文所列日期（不推定性質）：2024-12-25
- 適用起迄：unknown / unknown
- 檔名提示：{}
- 解析：success，22/22 頁

### 提升勞工自主學習計畫作業手冊.pdf
- SHA-256：1f3bd64cfe4f0e267cb5e52a99c31954eed1ea3ba1e04375cbeeae4ac516ac8e
- 正式標題：提升勞工自主學習計畫作業手冊
- 正文發布日：unknown
- 正文修訂日：2024-12-25
- 正文所列日期（不推定性質）：2024-12-25
- 適用起迄：unknown / unknown
- 檔名提示：{}
- 解析：success，80/80 頁

### 產業人才投資計畫.pdf
- SHA-256：ebd2df41ae2c6beacbbb2bbccf5feb5772262ddeb10ce775afbbbf3484ca8f88
- 正式標題：產業人才投資計畫
- 正文發布日：2024-12-25
- 正文修訂日：2024-12-25
- 正文所列日期（不推定性質）：2024-12-25
- 適用起迄：unknown / unknown
- 檔名提示：{}
- 解析：success，22/22 頁

### 產業人才投資計畫作業手冊.pdf
- SHA-256：4842ea67ebe4ae10145be49bee25a9c89af19e92bab10ec541f9f5a0a2c626cc
- 正式標題：產業人才投資計畫作業手冊
- 正文發布日：unknown
- 正文修訂日：2024-12-25
- 正文所列日期（不推定性質）：2024-12-25
- 適用起迄：unknown / unknown
- 檔名提示：{}
- 解析：success，79/79 頁

## 版本與適用性結論

沒有文件直接列為 applicable 或 possibly_applicable。四份計畫／手冊的修訂日期113/12/25不能當作115下半年適用證明；同計畫 unknown，異計畫 not_applicable。
兩份116上半年檔名文件，其正文沒有證實116上半年適用期間，所以正文 roc_year、period 保存 unknown，檔名提示另存116／上半年，不能套用到115案件。
審查原則的計畫別未明確辨識，unknown；作業程序首頁明示兩計畫，保存both。作業程序正文115.08.03與檔名1150902分開保存，未擅自判定哪個是修訂日期。

## 保護與限制

Phase 1 excel_parser.py、data_checks.py、case_state.py、test_phase1.py與起始雜湊一致；1.0封版10項及原始Excel雜湊通過。原始6份PDF與2.0複本的雜湊一致。
來源頁只查詢，不改案件審查結果，不讓DATA-01～08引用PDF。未知條號不產生假條號；表格職類關聯、跨頁合併留待後續確認。
未實作LLM、RAG、Embedding、向量資料庫、語意搜尋、AI初審意見或正式法規判定。
Phase 2B再處理經確認條文到規則的轉換與檢查依據連結。