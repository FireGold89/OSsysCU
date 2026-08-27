# Changelog

本專案變更記錄。格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)。

## [未發布]

`APP_VERSION`: `20260827-main-con-fac-pdf2`

### 修復
- **主合約 FAC PDF**：補回 `TOP_LOGO_ZONE` 匯入，修正生成失敗

`APP_VERSION`: `20260827-main-con-fac-pdf`

### 新增
- **主合約最終結算 PDF**：P1 工程帳目總結算 (A–K) + P2 關鍵日期 · 含內部簽名欄 · 預覽／下載

`APP_VERSION`: `20260827-vault-hold`

### 修復
- **登入開門**：動畫結束跳轉前不再彈回關門；主頁承接全開光效後淡入系統

`APP_VERSION`: `20260827-ux-desktop`

### 改善
- **桌面 UX Phase 1**：登入開門動畫可跳過並記住偏好；預設動畫縮短至 12 秒
- **切換項目**：內容區局部 loading（側欄／頂欄保持可操作）
- **項目下拉／徽章**：顯示報價編號（`quotation_no` 優先）
- **Dashboard**：最近付款列點擊直達該筆付款詳情
- **Topbar**：已選項目時於概覽／付款頁顯示「➕ 新增記錄」
- **長表**：sticky 表頭（付款、Master List、負責人、報表、分判 VO 等）
- **Modal**：Esc 關閉、開啟時自動 focus
- **Session**：閒置登出前 5 分鐘頂部預警，可一鍵延長
- **Toast**：`warn` 別名自動對應 `warning` 樣式

`APP_VERSION`: `20260827-staff-roster`

### 改善
- **項目負責人**：部門下拉（物業工程部、美博工程部、QS部、行政部、會計部）；權限角色（物業工程、美博工程、QS、行政、管理、唯讀）
- **修復**：中文姓名留空時不再误报「不要使用縮寫」；旧 `eng`/`工程部` 对应美博工程／美博工程部

`APP_VERSION`: `20260827-login-gate`

### 改善
- **登入前不閃主介面**：未登入訪問 `/` 直接導向 login；主頁 auth-pending 遮罩至驗證完成
- **夾萬開門**：转轮 90° 慢转 → 微开 → 停 2 秒 → 震動 → 慢速全开（16s）

`APP_VERSION`: `20260827-qs-mgmt`

### 改善
- **品牌名稱**：「QS付款管理」→「QS管理系統」（登入頁、側欄、報告頁腳）
- **夾萬轉輪**：登入開門動畫改為 180° 慢速旋轉（ease-out）

`APP_VERSION`: `20260827-session-idle`

### 改善
- **Session 保安**：最长 1 天（`AUTH_SESSION_DAYS`）；闲置自动登出 qs 60 分钟 / admin 30 分钟（`AUTH_IDLE_MINUTES*`）
- **本机 `.env`**：启动时自动读取

`APP_VERSION`: `20260827-vault-full`

### 改善
- **夾萬登入**：全屏金庫門背景；登入成功後轉輪 + 左右開門約 6.5 秒再進入系統

`APP_VERSION`: `20260827-vault-login`

### 新增
- **登入頁夾萬門**：金庫室背景、左右門扇與轉輪；登入成功後開門動畫，進入主頁時延續進場效果

`APP_VERSION`: `20260827-restore-ui`

### 改善
- **系統設定**：管理員可上傳 `qs_system.db` 還原線上資料庫（需 RESTORE_TOKEN）
- **腳本**：`scripts/push_db_to_zeabur.py` / `.ps1` 供 CLI 上傳（需 admin 登入 + token）
- **本機兼容**：`Auth.ensure()` 旧版后端无 `/api/auth/me` 时不阻断加载

`APP_VERSION`: `20260816-auth`

### 新增
- **简易登入**：Flask Session；Zeabur 设 `SECRET_KEY` + `APP_ADMIN_PASSWORD` / `APP_LOGIN_PASSWORD`；`admin` 可进系统设定与还原；`qs` 日常 QS；未设密码时本机仍免登入

`APP_VERSION`: `20260815-revert-infer`

### 修正
- **還原推斷修復**：當 SC 快照被污染（如 O-003：`pre_submit_sc_paid`=1919 但 cert 內 `net_payment`=1250.7），自動從 cert json 反推原列；列表載入時 backfill 會 commit 持久化；「重新提交 → 還原」恢復普通付款列

`APP_VERSION`: `20260815-revert-snapfix`

`APP_VERSION`: `20260815-revert-preserve`

`APP_VERSION`: `20260815-revert-row`

### 修正
- **還原計算書**：若由普通付款誤提交計算書，還原後 **恢復原本付款列**（類型、已付、餘額同提交前，如 O-003 雜項）；純新增糧款列仍為「待重新提交」

`APP_VERSION`: `20260815-restore-normal`

### 改善
- **還原後列表外觀**：已還原計算書列改與普通付款列一致（無黃底／標籤）；已付顯示 0、餘額為提交前；僅 ✏️ 編輯（重新啟用後可再提交）

`APP_VERSION`: `20260815-restore-btn`

### 改善
- **計算書還原**：有效糧款列加 **「還原」** 按鈕（保留記錄、數字回提交前）；已還原列顯示「已還原至提交前」+ **「重新提交」**；不再收合或刪除留底

`APP_VERSION`: `20260815-revoke-original`

### 改善
- **撤回計算書 · 還原至未提交前**：預設收合灰色留底列，列表外觀同未出糧；提示「已收合 N 筆」；可勾「顯示已撤回留底」；🗑️ 可刪除留底

`APP_VERSION`: `20260815-revoke-keep`

### 修正
- **撤回計算書**：不再隱藏記錄；列表保留該列，已付／餘額顯示 **提交前** 判項數字，標籤「已撤回（未生效）」

`APP_VERSION`: `20260815-revoke-never`

### 改善
- **撤回計算書 · 等同未提交**：預設隱藏已撤回列；判項已付／餘額以「分判合約登記表」為準還原；已撤回列已付／餘額顯示「—」；可勾選「顯示已撤回」找回記錄

`APP_VERSION`: `20260815-revoke-presubmit`

### 修正
- **撤回計算書**：列表已付／餘額 **還原至提交前**（存快照；舊記錄撤回時自動反推）；等同「本期糧款從未發生」

`APP_VERSION`: `20260815-revoke-display`

### 修正
- **撤回計算書 · 列表已付／餘額**：已撤回列改顯示 **還原後判項累計已付** 及 **判項餘額**（唔再顯示「—」）；提交時記錄提交前快照供對照；撤回後刷新判項 `total_paid`

`APP_VERSION`: `20260815-revoke-rem`

### 修正
- **撤回計算書 · 餘額還原**：撤回後列表餘額改顯示判項還原餘額（不含本期）；已付欄顯示「—」；滑鼠提示說明

`APP_VERSION`: `20260815-cert-restore`

### 新增
- **已撤回計算書 · 還原並編輯**：清除撤回狀態、重新套用原 VO／扣款，可繼續修改並提交（列表 ✏️ 或預覽內按鈕）

`APP_VERSION`: `20260815-applied-link`

### 改善
- **VO／扣款「糧款套用」**：顯示套用於哪張中期糧款計算書（期次、日期）；**點擊可跳轉**付款登記並開啟計算書預覽

`APP_VERSION`: `20260815-cert-withdraw-keep`

### 變更
- **撤回計算書**：改為軟撤回（`revoked_at`），付款登記列表仍保留記錄並標示「已撤回」；VO／扣款解除套用、可再用於下一期
- **累計／已付**：已撤回計算書不計入判項已付、上一期累計及新期次編號
- **已撤回記錄**：僅可預覽／匯出；🗑️ 為永久刪除（需確認）

`APP_VERSION`: `20260815-svr-ref-auto`

### 修正
- **分判 VO／扣款登記**：範本 ref_no（如 `VO`、`CC`）僅為前綴佔位，新增／儲存時自動編號為 `VO-001`、`CC-001`…（按判項獨立序號）
- **編輯既有記錄**：若編號仍為佔位字樣，開啟編輯時會重新建議編號；儲存時後端亦會補全

`APP_VERSION`: `20260815-interim-std-restore`

### 修正
- **中期糧款計算書**：預覽按「返回修改」時還原標準調整項勾選及金額（修正 `selected_standard_codes: []` 導致全部取消勾選）
- **返回修改**：優先沿用預覽時的 `_pendingCert`（含剛勾選但未提交的標準項）

`APP_VERSION`: `20260815-interim-preview-fix`

### 修正
- **中期糧款計算書預覽**：改以付款記錄 `vo_ids`／表單勾選重建 model，不再只用舊 `interim_cert_json`
- **備註預填**：B 行 VO 備註優先用「變更內容」；扣款備註用「扣款內容」（顯示於減: 列）

`APP_VERSION`: `20260815-interim-auto-vo`

### 修正
- **中期糧款計算書**：新增（或編輯但未套用 VO／扣款）時，自動勾選該判項所有未套用登記項目

`APP_VERSION`: `20260815-interim-vo-remark`

### 新增
- **中期糧款計算書 Phase 2**：B 行改為每條 VO 獨立備註表（編號｜金額｜備註）· 存入 `vo_remarks` · 計算書展開 **B1/B2…** 分行 · 預覽／PDF／Word／Excel 同步

`APP_VERSION`: `20260815-interim-remark`

### 新增
- **中期糧款計算書 Phase 1**：A / B / C 行備註欄 · 系統自動填寫（A=% Work Done、B=VO 編號）· 手改後不再覆蓋 · 存入 `interim_cert_json.line_remarks` · 預覽／PDF／Word／Excel 同步

`APP_VERSION`: `20260815-qs-minus-hide`

### 修正
- **QS 匯報 PDF**：(E)=(A)-(D) 改用 ASCII 減號（避免 PDF 亂碼方塊）
- **前端**：隱藏 QS 匯報 Word 匯出按鈕

`APP_VERSION`: `20260815-qs-font-fix`

### 修正
- **QS 匯報 PDF**：修正 plain 金額儲存格未套用 8pt 字型導致數字變大

`APP_VERSION`: `20260815-qs-money-fmt`

### 修正
- **QS 匯報 PDF**：三～五節金額 HK$ 改列表頭 · 全報告負數改括號 `( )` 表示

`APP_VERSION`: `20260815-qs-sc-table`

### 修正
- **QS 匯報 PDF**：分判明細表公司欄加寬 · 金額 HK$ 改列於表頭 · 儲存格只顯示數字

`APP_VERSION`: `20260815-staff-quot`

### 新增
- **項目負責人**：點「使用情況」開啟報價清單 · 可編輯每筆報價 · 跳轉 Master List 篩選

`APP_VERSION`: `20260815-nav-settle`

### 新增
- **側欄**：工程項目下方「註冊及更新」快捷入口（當前開啟項目）

`APP_VERSION`: `20260815-qs-layout4`

### 修正
- **QS 匯報 PDF**：topMargin 增至 29mm（LOGO 區 14mm + 邊距 15mm），第一、二頁內容整體下移

`APP_VERSION`: `20260815-qs-layout3`

### 修正
- **QS 匯報 PDF**：還原第一頁段落間距（四節位置對齊上一版）· 分判表「類別」加寬至 20mm（其他支出不換行）

`APP_VERSION`: `20260815-qs-layout2`

### 修正
- **QS 匯報 PDF**：壓縮第一頁間距 · 四、費用類別概覽 KeepTogether 後強制分頁 · 分判表判項加寬（SC-004.1 不換行）· 金額欄調整

`APP_VERSION`: `20260815-qs-table-fix`

### 修正
- **QS 匯報 PDF**：全部表格統一全寬 180mm · 類別欄修復黑框（改回中文字型 Paragraph）· 四、費用類別概覽 KeepTogether 同頁 · 表頭白字右對齊

`APP_VERSION`: `20260814-qs-pdf-sync`

### 修正
- **QS 匯報 PDF 預覽**：對齊 Word 交回版 — KPI 僅首行深色表頭、糧期摘要+明細合併六欄表、表頭色統一 `#334155`、移除 A–E 結算多餘底色

`APP_VERSION`: `20260814-qs-docx-v2`

### 變更
- **QS 匯報 Word**：對照 QS 交回版（2026-08-14）調整版面 — 項目名稱中→英、KPI 表首行深色、糧期摘要+明細合併六欄表、統計行置於 KPI 表後

`APP_VERSION`: `20260814-qs-docx`

### 新增
- **QS 匯報 Word 匯出**：`qs_report_docx.py` · `GET /api/reports/boss-docx/<id>` · 項目概覽／財務報表「📝 Word」按鈕（供 QS 微調版面後交回對照 PDF）

`APP_VERSION`: `20260814-qs-pdf-layout`

### 修正
- **QS 匯報 PDF**：有 LOGO 時不再畫首頁橫線（避免遮蓋 LOGO）· 分判明細金額欄加寬並改純文字儲存格，避免換行

`APP_VERSION`: `20260814-qs-pdf-logo`

### 變更
- **QS 匯報 PDF**：每頁左上角加 Mepork LOGO（與分判結算一致）· 分判及支出明細「公司」欄中文優先、無則英文

`APP_VERSION`: `20260814-qs-preview`

### 變更
- **QS 匯報表**（項目概覽、財務報表）：改為應用內 **預覽**（`DocViewer`），與分判最終結算一致；預覽視窗可打印或下載 PDF

`APP_VERSION`: `20260814-iso-sprint-c2`

### 修正
- ISO 上傳實體檔名改為 `{槽位中文名}_{YYYYMMDD}_{短ID}.ext`（例：`主合約LOA_20260814_a1b2c3d4.pdf`）

`APP_VERSION`: `20260814-iso-sprint-c1`

### 修正
- ISO 上傳實體檔名改為 `{槽位}__{原檔名}__{短ID}.ext`（例：`main_contract_loa__主合約LOA__a1b2c3d4.pdf`），後台資料夾可辨識；畫面仍顯示原檔名

`APP_VERSION`: `20260814-iso-sprint-c`

### 新增
- **ISO Sprint C**：上傳改存 `uploads/iso/{project_code}/` · 只填 SharePoint/內網連結（不上傳副本）· 換檔/刪除保留歷史版本 · `/api/uploads/` 支援子路徑 · 歷史版本 Modal

`APP_VERSION`: `20260814-iso-sprint-b`

### 新增
- **ISO Sprint B**：主合約／分判 Tab 切換 · 主合約「合約文件／招標會議」子 Tab · 分判卡片式槽位 · 拖放上傳 · 寬表格收在「展開舊版矩陣」

`APP_VERSION`: `20260814-iso-sprint-a2`

### 修正
- ISO 文件：**補充合約金額** 欄 `<td>` 錯位已修正（數值輸入框歸位）· **其他** 維持選填（非必填）

`APP_VERSION`: `20260814-iso-sprint-a`

### 變更
- **ISO 文件登記 Sprint A**：完成度儀表板、必填/選填狀態色、表頭縮寫+tooltip、橫向捲動 sticky 首兩欄、分判列完成 % 徽章、上傳日期顯示

`APP_VERSION`: `20260813-eng-cat`

### 變更
- 「工作範疇（請重新輸入）」改名 **工程類別分類**（對應 Excel「分類清單」）
- 同步邏輯：工程類別以**分類清單**為主，另加歷史資料中未列入者（如機電工程、廣告招牌）為「資料補充」

`APP_VERSION`: `20260813-scope-grp`

### 新增
- I 欄工作範疇細項依 Excel **I→J 同列配對**自動歸入大類別（即 J 欄常見歸類）；表單可先選大類別再選細項

`APP_VERSION`: `20260813-trade-cols`

### 變更
- 工作範疇選項改為分別從 Excel **I 欄**（~1025 項細分）與 **J 欄**（~23 項歸類）已有資料同步，不再用「分類清單」sheet
- 表單：I 欄可搜尋 datalist + J 欄下拉；儲存 `trade_scope` / `trade_override` 兩欄

`APP_VERSION`: `20260813-trade-cats`

### 新增
- Master List **工作範疇分類主檔**：從 `Ref/… Quotation & Contract number.xlsx`「分類清單」同步，可新增／編輯／停用
- 新增／編輯報價／標書表單：**工作範疇**下拉 + **工作範疇（請重新輸入）**覆寫欄（對齊 Excel I/J 欄邏輯）

`APP_VERSION`: `20260813-quot-no-suggest`

### 新增
- 新增報價／標書：類型優先、自動建議編號（報價 MS/Q###、標書 MS/T###、尾碼為負責人縮寫）

`APP_VERSION`: `20260813-ui-terms`

### 變更
- UI 用語統一：「主檔」改為 **報價／標書**、**分判合約編號表** 等具體名稱

`APP_VERSION`: `20260813-master-add-icons`

### 新增
- Master List 工具列右側 **➕ 新增主檔**（手動單筆登記，有 API）
- Master List／項目負責人列表操作改為 icon 按鈕（hover 顯示 title）

`APP_VERSION`: `20260813-col-picker-all`

### 新增
- 分判合約編號、Master List、工程項目列表可自訂顯示欄位（⚙️ 欄位），設定儲存於本機
- 共用 `col_picker.js` 模組（付款登記、上述三頁一致）

`APP_VERSION`: `20260813-pay-col-picker`

### 新增
- 付款登記列表可自訂顯示欄位（⚙️ 欄位），設定儲存於本機

`APP_VERSION`: `20260813-table-fit`

### 修正
- 列表表格改回隨視窗自適應縮放（與分判合約編號相同：固定欄寬比例、長文字省略），不再改為橫向捲動

`APP_VERSION`: `20260813-table-scroll`

### 修正
- 列表表格縮窄視窗時可橫向捲動，避免最右欄被裁掉（付款登記及其他 table-wrap 頁面）

`APP_VERSION`: `20260813-pay-edit-form`

### 修正
- 付款登記：中期糧款計算書列的編輯鈕改開編輯表單，不再跳去預覽

`APP_VERSION`: `20260813-interim-cert-bold`

### 修正
- 中期糧款計算書 PDF：上期累計金額 HK$ 換行；Sub-total／總計整行粗體

`APP_VERSION`: `20260813-interim-cert-print`

### 修正
- 中期糧款計算書：logo 與標題隔兩至三行；打印改用 PDF，避免預覽 modal 印出空白

`APP_VERSION`: `20260813-interim-cert-logo`

### 修正
- 中期糧款計算書 PDF／打印 logo 按原圖比例縮放，避免被拉長走位

`APP_VERSION`: `20260813-interim-cert-amt`

### 修正
- 中期糧款計算書金額三欄：表頭置中、數字靠右；0／空白顯示 `-`；負數用括號

`APP_VERSION`: `20260813-interim-cert-align`

### 修正
- 中期糧款計算書：右兩欄對齊備註；金額三欄置中；表頭改淺色（預覽／打印／PDF／Word 一致）；隱藏 Excel；修正打印 logo 拉伸與標題 `<b>`；移除頁底 OSsysCU

`APP_VERSION`: `20260813-interim-cert-layout`

### 修正
- 承判商中期糧款計算書版面對齊使用者 Word 改版（欄寬、8pt、金額格式、小計／總計置中）；左上角沿用分判結算同一 Mepork logo 尺寸

`APP_VERSION`: `20260813-interim-cert-docx`

### 新增
- 承判商中期糧款計算書預覽可下載 Word（.docx），版面對齊 PDF，方便改完交回調格式

`APP_VERSION`: `20260810-sc-fac-p1-amtcol`

### 修正
- SC FAC P1 結算：三行標籤（中/英）粗體；HK$ 與金額數字分欄

`APP_VERSION`: `20260810-sc-fac-p1-revise`

### 修正
- SC FAC P1：移除三行免責聲明；內文 8 pt；三處結算金額粗體；分期標題/期數中文/刪除保證金備註

`APP_VERSION`: `20260810-sc-fac-text-black`

### 修正
- SC FAC 打印全文改黑色（移除灰色內文/英文副行；負數金額仍紅色）

`APP_VERSION`: `20260810-sc-fac-body-10pt`

### 修正
- SC FAC 打印內文中文字級改為 10 pt（英文副行 8 pt）

`APP_VERSION`: `20260810-sc-fac-body-12pt`

### 修正
- SC FAC 打印內文（表格、結算、聲明）中文字級改為 12 pt；雙語英文副行 10 pt

`APP_VERSION`: `20260810-sc-fac-p2-vo-text`

### 修正
- SC FAC 傳統會計 P2 頁底聲明：後加工程結算專用 wording

`APP_VERSION`: `20260810-sc-fac-p2-text`

### 修正
- SC FAC 傳統會計 P2 頁底聲明文字更新（與 P3 一致）

`APP_VERSION`: `20260810-sc-fac-p3-text`

### 修正
- SC FAC 傳統會計 P3 頁底聲明文字更新（Contra Charge 附錄）

`APP_VERSION`: `20260810-sc-fac-p3-spacer`

### 修正
- SC FAC 傳統會計 P3：總計上方單線僅 AMOUNT 欄，不延伸至空白欄

`APP_VERSION`: `20260810-sc-fac-amt-center`

### 修正
- SC FAC 傳統會計 P2/P3：AMOUNT 表頭欄內置中；附錄總計雙下框線填滿 AMOUNT 欄全寬（嵌套表強制欄寬）

`APP_VERSION`: `20260810-sc-fac-p3-amt-col`

### 修正
- SC FAC 傳統會計 P3（及 P2）附錄總計：雙下框線填滿 AMOUNT 欄全寬（修正 width=None 被誤用固定寬）

`APP_VERSION`: `20260810-sc-fac-p2-topline`

### 修正
- SC FAC 傳統會計 P2 附錄總計：UNIT/RATE/AMOUNT 三欄上方單線（對照 Word 範本）

`APP_VERSION`: `20260810-sc-fac-word-ref`

### 修正
- SC FAC 傳統會計 P2/P3 附錄表對照 Word 範本：P2 八欄（含 No.）· P3 四欄（NO/DESCRIPTION/AMOUNT）· 總計雙下框線

`APP_VERSION`: `20260810-sc-fac-docx`

### 新增
- 分判最終結算 **匯出 Word**（`python-docx`）：3 頁版面可於 Word 微調後交回對照 PDF

`APP_VERSION`: `20260810-sc-fac-classic5`

### 修正
- SC FAC 傳統會計：P2 表頭 UNIT/RATE/AMOUNT 下框線；P3 修正直向版型切換（表格不再错位）

`APP_VERSION`: `20260810-sc-fac-classic4`

### 修正
- SC FAC 傳統會計：P1 Statement 與表頭間距；分判合約編號改讀 `quotation_no`（非判項 sc_no）；P2 恢復七欄附錄表、總計僅 AMOUNT 雙下框線；P3 改直印 Contra Charge

`APP_VERSION`: `20260810-sc-fac-classic3`

### 修正
- SC FAC 傳統會計：P1 表頭四項資料欄恢復底框線；P2/P3 章節標題靠左；附錄表改三欄 NO./DESCRIPTION/AMOUNT

`APP_VERSION`: `20260810-sc-fac-classic2`

### 修正
- SC FAC 傳統會計：Word 式雙下框線（1/2 pt）；文字底線取代框線；P1 Statement 底線+空行；P2/P3 附錄標題列；P3 改 SUMMARY OF CONTRA CHARGE（Appendix II）

`APP_VERSION`: `20260810-sc-fac-classic`

### 修正
- SC FAC **傳統會計**主題對齊 PPT p20/p22：表頭資料底線；結算表三欄（中/英/金額）；括號負數紅色；結算總額／剩餘應付／Total Outstanding 數值上框+雙下框；P2/P3 移除 FINAL ACCOUNT、附錄標題列、表頭底線、VO 總計對齊 DESCRIPTION 欄

`APP_VERSION`: `20260810-sc-fac-themes`

### 新增
- SC FAC **打印主題**：駿昇格線（預設格線版）／傳統會計（PPT p20 正文無框線）；預覽可切換；匯出沿用所選主題

`APP_VERSION`: `20260810-sc-fac-logo`

### 修正
- SC FAC：P1 簽名 72mm／日期 52mm；P2/P3 雙簽 88mm
- P2 VO 表頭改淺灰底深字；三頁左上角加 Mepork LOGO（`assets/mepork_logo.png`）

`APP_VERSION`: `20260810-sc-fac-sig2`

### 修正
- SC FAC 簽名線：P1 簽名 62mm／日期 42mm；P2/P3 雙簽 68mm；移除中間直線分隔

`APP_VERSION`: `20260810-sc-fac-sig`

### 修正
- SC FAC PDF：P1 內部簽名（編制者／合約部／項目部／總經理）固定於頁底 footer；P2/P3 分判商簽名底線縮短

`APP_VERSION`: `20260808-sc-fac-v2`

### 修正
- 分判 FAC 預覽：改 fetch → blob URL 載入 iframe（避免 Chrome 直接下載）
- PDF 結算表：雙欄格線表格、表頭框線、負數括號格式；P1 無分判商頁腳

`APP_VERSION`: `20260808-sc-fac-preview`

### 新增
- 分判最終結算：**預覽 → 匯出 / 打印**（應用內 PDF 預覽器；預覽用 `inline=1`，每次帶時間戳避免快取舊檔）

`APP_VERSION`: `20260808-sc-fac`

### 新增
- 左欄 **分判最終結算**（SC Final Account · PPT 第20–21頁）
- **每判項一 PDF**（3 頁）：P1 直向結算+簽名（編制者／合約部／項目部／總經理）· P2 橫向 VO 摘要 · P3 直向 MP 結算
- 對照 Final Account Excel 範本；自動帶入合約價、VO、扣款、已付
- API：`GET /api/projects/<id>/sc-fac`、`GET .../subcontractors/<id>/sc-fac/pdf`

`APP_VERSION`: `20260808-main-con-fac`

### 新增
- 左欄 **最終結算**（Main Con Final Account · PPT 第19頁）
- 工程帳目總結算表 (A)–(K)：自動帶入承建金額、補充合約、VO 變更、扣款、糧期已批款；可手動覆寫
- 工程完工關鍵日期總覽 + 結算書／PC／Make Good 證書上傳
- API：`GET/POST /api/projects/<id>/main-con-fac`、`POST .../main-con-fac/upload`

`APP_VERSION`: `20260808-sc-vo-phase-c`

### 新增
- **分判變更以及扣款登記** Phase C：關鍵字搜尋、類型篩選、**匯出 CSV**（對齊 p16 矩陣欄）
- 舊頁 **分判變更扣款** 加提示橫幅，連結至新頁正式登記

`APP_VERSION`: `20260808-sc-vo-ref-auto`

### 新增
- **變更工程編號 / 扣款編號** 按 **判項 + 類型** 自動遞增（`VO-001`、`CC-001` 各自獨立；序號仍為項目全局）
- API：`GET /api/projects/<id>/sc-vo-records/next-ref?sc_no=&record_type=`；新增時留空則後端自動分配

`APP_VERSION`: `20260808-sc-vo-reg-modal`

### 變更
- **新增變更登記** modal 對齊 **分判付款登記**：序號、發票日期／號碼、報價單、判項、公司名、工程描述、OA、備注
- 金額區：變更工程 → 變更金額／變更內容／VO 編號；扣款 → 扣款金額／扣款內容／CC 編號（隱藏報價單、付款授權）
- 變更工程專用：主合約變更編號、審批表 PDF、報價單 PDF 上傳
- DB：`sc_vo_records` 擴充上述欄位；API `POST /api/sc-vo-records/<id>/upload`

`APP_VERSION`: `20260807-sc-vo-reg`

### 新增
- 左欄 **分判變更扣款** 下新增 **分判變更以及扣款登記**（`sc-vo-reg`）；舊頁保留作模板／糧款套用對照
- PPT p16 矩陣表：判項分組 · 變更工程欄 + 扣款欄並列；新增 modal 支援 **1.變更工程** / **2.扣款** radio（Phase A：無附件）
- 前端模組 `sc_vo_reg.js`；共用既有 `sc_vo_records` API

`APP_VERSION`: `20260807-doc-settings`

### 變更
- **文件管理設定** 集中於 **系統設定** 獨立卡片：全局文件庫 URL + 各項目 URL 表格（搜尋、一次儲存）
- API：`GET/POST /api/settings/doc-library`；工程項目 modal 移除文件庫欄位

`APP_VERSION`: `20260807-doc-library`

### 新增
- **文件庫連結（兩層）**：系統設定 **公司文件庫 URL（全局）**；工程項目 **ISO／文件庫連結（本項目）**
- ISO 文件頁：**開本項目文件庫**（優先）、**開公司文件庫**（全局 fallback）
- DB：`projects.doc_library_url`；settings `doc_library_url`

`APP_VERSION`: `20260805-iso-docs`

### 新增
- 左欄 **項目概覽** 下新增 **ISO 文件**；頁面 **ISO文件登記**
- **ISO 文件上傳**：主合約表格（LOA、Optional、MOU、NDA、TMC 會議記錄、投標會簽表等）及分判商表格（投標確認單、領取標書、開標記錄、合約會簽表等）
- API：`GET/POST /api/projects/<id>/iso-documents`、`POST .../upload`、`DELETE /api/iso-documents/<id>`、`PATCH .../iso-meta`
- DB：`iso_document_files` 表；`projects.supplemental_contract_amount`

`APP_VERSION`: `20260805-sc-contract`

### 變更
- 分判付款登記 Tab／Card 改名 **分判合約登記表**；按鈕 **新增合約／判項**
- 新增判項表單：**判項類型**（報價單／分判合約）；合約模式：合約編號、Retention Sum、隱藏報價日期／累計已付／OA 狀態編號
- DB：`subcontractors.sc_entry_type`、`retention_sum`

`APP_VERSION`: `20260805-pay-tabs`

### 變更
- **分判付款登記** 整合 **判項及支出**：頁內分頁（判項及支出｜付款登記），左欄移除獨立「分判及支出」選單
- 判項分頁：**新增判項**；付款分頁：**新增記錄**（原功能不變）

`APP_VERSION`: `20260805-ip-search`

### 新增
- 糧期狀況：**搜尋**（期數、日期、金額、收款、IP Cert.、分判編號）；同步篩選分包矩陣與糧期核對

`APP_VERSION`: `20260805-ip-cert`

### 新增
- 糧期狀況：**IP Cert. 附件上傳**（PDF/圖片）；表格 **IP Cert.** 欄顯示 📄 預覽
- API：`POST/DELETE /api/interim-payments/<id>/ip-cert-attachment`

`APP_VERSION`: `20260804-ip-receipt`

### 新增
- 糧期狀況：**則師批款** 改名 **業主批款**；新增 **收款記錄（支票／過數）** 欄
- 糧期編輯：支票號碼／銀行／日期（格式 `#828310 , 003, 22/3/2025`）或過數備註；**上傳支票附件**（PDF/圖片）
- API：`POST/DELETE /api/interim-payments/<id>/receipt-attachment`
- 糧期收款 **銀行** 下拉：HKICL 全港持牌／虛擬銀行清算代碼一覽（可搜尋）

`APP_VERSION`: `20260804-summary-import`

### 新增
- **`summary_importer.py`**：匯入 `Ref/Summary.xlsx`（拆行、客方續行、N23 多 Q 編號）
- API：`POST /api/import/summary`、`POST /api/import/summary/sync`
- 工程項目頁：**列表 / 卡片** 切換（二選一）；**同步 Ref/Summary.xlsx** 按鈕
- Summary 拆行：**客方** vs **主承判商** 分欄；**多 MP 編號**（`project_mp_contracts` 子表，如 N23）
- **雙客方**：`client_secondary` 欄位；Excel 客方續行（非主承判商）→ 第二客方；列表 / 卡片 / 編輯表單分欄顯示
- 編輯項目：**MP合約編號多選**（標籤式加入／移除／設主編號；同步 `project_mp_contracts`）
- Summary 列表：多 MP 項目（如 N23）**收合/展開**子列，樣式對齊分判分組
- 工程項目新增/編輯表：依 Cover Page PPT 重排欄位；附件上傳；保固金退還第一/二期日期可並存

`APP_VERSION`: `20260804-cover-page-ui`

### 新增（Cover Page · 工程項目 UI）
- 工程項目頁：**Summary 全公司總表**（第2頁欄位）
- 新增/編輯項目：**Cover Page 主檔**分頁（會計編號、工期、保固金、里程碑等）
- 項目卡片 + Summary：**註冊及更新** → **項目金額結算**頁（第5頁 A–E）
- 結算頁可覆寫 C、結算工程總額、FAC 日期

`APP_VERSION`: `2026-08-04-cover-page-db`

### 新增（Cover Page · 工程項目主檔 DB）
- **`project_cover.py`**：Summary 列格式、Cover Page payload、A–E 結算（B=分判 / C=物料及其他）
- `projects` 表擴充 25 欄（會計編號、MP合約編號、落標價、工期日期、保固金、FAC 等）
- 新表 **`project_documents`**（Cover Page 附件1／附件3 分類）
- API：`GET /api/company-summary`、`GET /api/projects/<id>/cover-page`、項目文件 CRUD

`APP_VERSION`: `2026-08-03-pay-interim-pick-tick`

### 變更
- 中期糧款：標準調整項併入勾選清單（checkbox），**勾選才顯示**於計算書表格

`APP_VERSION`: `2026-08-03-pay-interim-line-catalog`

### 新增
- **`sc_vo_templates.py`**：VO／扣款／計算書標準行項目目錄（罰款、CP & FM、Rounding、徵稅等）
- 分判變更扣款：範本下拉 + 快速新增按鈕
- 中期糧款表單：**標準調整項**金額輸入（對齊駿昇 Excel 固定列）
- 計算書輸出：保固金自動 + 標準行有金額才顯示累計

`APP_VERSION`: `2026-08-03-pay-interim-vo-unified`

### 變更
- 中期糧款表單：VO 與扣款合併為**單一多選清單**（`[VO]` / `[扣款]` 標籤），下方仍分開顯示 B 行及扣款合計

`APP_VERSION`: `2026-08-03-pay-interim-vo-mgmt`

### 新增
- **分判變更以及扣款登記**頁：管理 VO（後加/更改）與扣款，支援參考編號、描述、金額
- 中期糧款計算書可**多選 VO**（B 行）及**多選扣款**（獨立減:列）
- 輸出格式對齊駿昇第十期：保固金按合約總價 5% 上限、上期累計自動承接
- `vo_ids_json` 欄位；套用後標記 `applied_payment_id`

`APP_VERSION`: `2026-08-03-pay-interim-excel-report`

### 新增
- 中期糧款計算書輸出對齊 QS Excel 範本（綽達第六期／滙力第二期／駿昇第十期）
- 新模組 `interim_cert_report.py`：A/B/C 明細、保固金、扣款列、總計、簽署區
- 預覽 / PDF / **Excel 下載**（`POST /api/payments/interim-cert/xlsx`）

`APP_VERSION`: `2026-08-03-pay-interim-step2`

### 新增（QS 優化第一期 · Step 2）
- 普通付款：隱藏 MC IP No.、Sub-IP No.
- 中期糧款計算書：金額欄唯讀自動計算；未扣款多選 + 本期總扣款；下一步 → 計算書預覽（提交／打印／下載 PDF）
- 新表 `sc_vo_records`（未扣款項來源）；`payment_records` 加 `deduction_*`、`interim_cert_json`

`APP_VERSION`: `2026-08-03-pay-normal-step1`

### 新增（QS 優化第一期 · Step 1）
- 分判付款登記：頂部「選擇付款類型」（普通付款 / 中期糧款計算書佔位）
- 普通付款：Backcharge to Sub 改為判項下拉；新增 Backcharge 金額欄（獨立儲存）
- DB：`payment_records.payment_type`、`payment_records.backcharge_amount`

`APP_VERSION`: `2026-07-17-master-year-filter`

### 改善
- Master List 預設只載入當前年份（localStorage 記住選擇）；`quotation_registry` 加索引加速篩選

`APP_VERSION`: `2026-07-15-ip-phase234`

### 新增
- 分包糧期 Phase 2：Summary row 41 工種簡稱匯入 `trade_label`；矩陣表頭三行（SC／工種／公司）
- 分包糧期 Phase 3：點擊矩陣 cell drill-down 付款登記；糧期矩陣 vs Sub-IP 明細核對
- 分包糧期 Phase 4：按期／按分判視圖切換；超付分判警示（餘額 < 0）

`APP_VERSION`: `2026-07-15-sc-matrix-phase1`

### 新增
- 分包糧期矩陣 Phase 1：表頭顯示分判商公司名（join subcontractors）；表尾加判項金額／付款登記／餘額；糧期合計 vs 付款登記核對標籤

`APP_VERSION`: `2026-07-15-ip-sc-matrix`

### 新增
- 分包糧期矩陣：`interim_payment_sc_lines` 表；Excel Summary 匯入各 SC 欄（SC-004…）及總支出（M 欄）；糧期頁「分包糧期明細」矩陣表
- 主糧期「分包總支出」改讀 Summary 總計欄（修正先前誤取第一個 SC 欄）

`APP_VERSION`: `2026-07-06-ip-reconcile`

### 新增
- 糧期核對：地盤 QS（申請／批款）↔ 行政 Master（開票／收票）並排對照；狀態標籤（一致、金額差、僅行政、僅地盤）；只讀不覆寫；Master 編輯「糧期核對」分頁 + 糧期狀況頁面

`APP_VERSION`: `2026-07-04-qs-subcon-lines`

### 修正
- Master List 來源檔名正規化為 `YYYY Quotation & Contract number.xlsx`（含 DB 舊 `(新)…as 27.8.2024` 檔名遷移）

### 新增
- Master List QS 主分判：Excel 欄 X/Y 多行（例 MS/Q1241/24/kp 四家分判商）解析至 `master_qs_subcon_lines`；編輯畫面新增「主分判 QS」分頁；Admin 分判付款「主分判 ✓」對照全部 QS 主分判

`APP_VERSION`: `2026-07-03-finance-display`

### 修正
- Master List 財務明細：業主糧期、分判付款、支票統一結構化解析（A , B, C 格式）；日期顯示 dd/m/yyyy

### 修正
- Master List 支票明細：解析為支票號碼／銀行／日期三欄（例 `#828310 , 003, 22/3/2025`）

### 修正
- Master List Phase 2 財務：新增 `sync-finance` 重匯糧期／分判付款／支票；編輯畫面無明細時提示重新同步

### 修正
- 項目負責人管理：只顯示全名；停用縮寫（EC、KM 等）與同名重複；新增時禁止縮寫

### 修正
- Master List：負責人篩選改以主檔 `person_in_charge` 全名為準（下拉與列表一致）；縮寫主檔自動正規化為全名；不再以 staff id／尾碼區分

### 修正
- Master List 負責人篩選：統計與列表同一套 `person_in_charge` 比對；支援 staff id／舊縮寫參數；選負責人時不再重刷下拉

### 修正
- Master List 負責人篩選：下拉只顯示項目負責人管理全名，依 `person_in_charge` 比對（不用報價尾碼／縮寫分組）

### 修正
- 報價編號尾碼與項目負責人脫鉤：尾碼僅編號慣例；跟進人以 Master List 姓名為準，可由不同同事接手
- 項目負責人管理：移除報價尾碼欄；篩選／統計改依 `person_in_charge` 全名

### 修正
- 「負責人名單」改為「**項目負責人管理**」：以姓名為主、報價尾碼為輔；表格與說明文案同步調整

### 修正
- Master List：項目負責人以主檔全名為主，編輯／列表不顯示英文縮寫

### 修正
- 工程項目：變更項目代碼或從 Master List 帶入不同報價時須確認，避免誤改（例 Q1241→Q001）

### 修正
- 工程項目／Master List：項目負責人改為從負責人名單以**姓名**選擇，縮寫自動帶入

### 修正
- Master List 編輯：列表快取直接開啟表單；API 改 query `?id=`（避免 path 含 `/` 或 `id/` 被誤判）
- JS 加版本參數強制刷新快取

### 修正
- Master List 編輯／配對：改以數字 id 呼叫 API，避免報價編號含 `/` 在 Zeabur 上 404

### 新增（Master List Phase 2 試行）
- 財務明細子表：主分判合約、業主糧期／發票、分判付款、支票
- 匯入時拆開 Excel 多行儲存格（2022+）；主檔 `subcon_company` 僅保留 QS 主分判欄
- 編輯 Master List 可檢視糧期／分判付款／支票分頁

### 修正
- 分判欄位全年匯入：外判公司→`分判商`、外判金額/分判金額→`分判金額`（2019–2021 依表頭自動對應）
- Master List 編輯：標籤統一為「分判商／分判金額」

### 修正（2026-06-27）
- 2018 Master List 補齊欄位：業主、報業主/大判、外判與否、外判公司、外判金額（及利潤）
- 2017 同步補齊業主／外判等欄位（欄位位置與 2018 不同）

### 修正（2026-06-27）
- Master List 匯入**「中標項目」**工作表（2019–2021 中標清單；2022+ 仍用報價 F 欄「中」）
- 固定 sheet 處理順序（報價→合約→中標項目），避免中標標記被覆蓋

### 修正（2026-06-27）
- Master List 匯入改依**表頭**辨識版型（不再用資料行猜測）：
  - **modern**（2022–2026）：F=中標、G=報價/標書
  - **transitional_site**（2019–2020）：F=屋苑/地點、G=工作範疇
  - **transitional_2021**（2021）：F=報價/標書、G=屋苑/地點
  - **legacy_english**（2017–2018）
- 2019–2020 可正確讀取業主、金額；合約 sheet E 欄屋苑不再誤併入報價編號
- `sync-all` 預設路徑改為專案內 `Ref/`

### 新增
- **負責人名單**（`staff_members` 表）：縮寫、姓名、部門、電郵、權限角色（預留）
- 側欄「負責人名單」頁：新增／編輯／停用；Master List 與工程項目負責人下拉改讀名單
- `master_ref` 全名對照改為優先讀資料庫名單

### 新增（2026-06-27）
- Master List 每筆可編輯（`PUT /api/master/quotations/...`）
- 工程項目：`quotation_no`、負責人欄位；配對 Master List 時同步項目代碼與負責人
- 儀表板顯示項目負責人；工程項目可「從 Master List 選擇」

### 新增（Master List Phase 1）
- 公司級 `Quotation & Contract number.xlsx` 匯入（`master_list_importer.py`）
- 資料表 `quotation_registry`、`master_list_imports`；前端 Master List 頁
- 唯一鍵：完整報價編號（例 `MS/Q001/26/jy`）；財務 Admin 欄位留待 Phase 2
- 支援 2017–2018 英文欄位及「合約」工作表；負責人縮寫見 `master_ref.py`

### 變更
- 現有地盤 Payment Excel 匯入保留為 `excel_importer_payment.py`（可獨立執行、對照用）
- `excel_importer.py` 改為相容入口（轉呼叫 payment 模組）

---

## [2026-06-08] — 版本基線與備份機制

`APP_VERSION`: `2026-06-08-fix-project-payment-progress`  
`Git tag`: `release/2026-06-08`

### 新增
- `VERSION`、`RELEASE.md` 發行基線說明
- `scripts/backup_release.ps1` / `backup_release.sh` 一鍵完整備份（原始碼 zip + MANIFEST + 本機 DB）
- `.gitignore` 排除 `_backup/`、`_releases/`

---

`APP_VERSION`: `2026-06-08-fix-project-payment-progress`

### 修復
- 工程項目卡片「累計已付」因 JOIN 判項與付款而重複加總
- 付款進度不再硬上限 100%；超過承建金額時顯示提示及橙色進度條

---

## [2026-06-08] — Light / Dark 主題

`APP_VERSION`: `2026-06-08-light-dark-theme`

### 新增
- 頂部欄 ☀️ / 🌙 主題切換（淺色 / 深色）
- 主題偏好存入 `localStorage`（`qs_theme`）；首次造訪跟隨系統 `prefers-color-scheme`
- 儀表板 Chart.js 隨主題更新配色

### 變更
- `style.css` 重構為 `[data-theme="light"|"dark"]` CSS 變數

---

## [2026-06-13] — QS 匯報表 PDF 中文修復

`APP_VERSION`: `2026-06-13-pdf-chinese-font-v3`

### 修復
- PDF 中文亂碼：改為嵌入 TrueType（Windows `msjh.ttc`、Linux `fonts-wqy-zenhei`）
- Docker 安裝 `fonts-wqy-zenhei`；移除失效的 Noto 下載與 MSung CID 字型

### 新增
- 一鍵 **QS 匯報表** A4 PDF（重點摘要、關注事項、A–E 結算、糧期、分判明細）
- API：`GET /api/reports/boss-pdf/<project_id>`
- 關注事項：系統規則判斷（利潤率、墊支、未付比例、判項付款進度等）

---

## [2026-06] — UI 術語與雙語項目

### 新增
- 項目名稱中英分欄（`project_name_en` / `project_name_zh`）及 DB 遷移
- 發票 / 報價 OCR：文件類型判斷、判項建議、發票重複檢查、雙按鈕儲存（報價 / 發票）

### 變更
- 介面對齊香港 SME QS 用語（分判及支出、判項編號、付款登記、糧期狀況等）

---

## 部署核對清單

1. `git push origin main`
2. 等待 Zeabur 重建（約 1–3 分鐘）
3. `GET https://ossys.zeabur.app/api/system/status` → 確認 `app_version`
4. 瀏覽器 **Ctrl+F5** 強制重新整理靜態資源
