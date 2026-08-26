# Open Questions

> 需 **QS / Admin / 運維** 確認的事項。  
> 分類：**Verified 矛盾**（code 已顯示不一致）、**Unknown**（code 未明示）、**Inferred**（推論）。

不含 Token 值、密碼或客戶敏感資料。

---

## 1. 計算與報表

### Q1.1 A–E 以哪套公式為準？ `[Verified 矛盾]`

| 來源 | 函數 | B/C 邏輯不同 |
|------|------|-------------|
| Dashboard / QS PDF | `database.get_project_summary()` | excluded 併入 B/C |
| Cover 註冊及更新 | `project_cover.compute_settlement()` | M/SC/O 前綴分組 |

**需確認**：對外匯報、老闆 PDF 應跟 Excel 哪一頁？

**相關檔案**：`database.py` L4040–4049；`project_cover.py` L270–305

---

### Q1.2 判項金額是否應含 VO？ `[Verified 矛盾]`

| 場景 | 是否含 `vo_amount` |
|------|-------------------|
| `get_project_summary.sc_stats` | **否** |
| 中期糧款 `calcInterimAmounts()` | **是**（contract + vo） |
| 分判 FAC | **是**（original + VO） |

**需確認**：Dashboard 分判柱狀圖 / 未付餘額是否應加 VO？

**相關檔案**：`database.py` L4016–4031；`payments.js` L476–478

---

### Q1.3 保固金百分比來源？ `[Verified + Inferred]`

- Code：中期糧款 `retention_pct: 0.05` 硬編 — `payments.js` L653
- Code：`subcontractors.retention_sum` 欄存在但未讀 — `database.py` migration
- PENDING：Retention 連動未做 — `PENDING.md` L42–43

**需確認**：是否依判項／合約類型變動？是否讀 Excel 判項 J 欄？

---

### Q1.4 Material On Site（C 行） `[Verified]`

中期糧款 C 行恒 0 — `interim_cert_report.py` L141–142

**需確認**：是否永遠不用？或将来接入？

---

### Q1.5 糧期核對差異以誰為準？ `[Verified]`

`ip_reconcile.js` 唯讀；無覆寫 API。

**需確認**：地盤 IP vs Master 行政糧期不一致時，修正哪邊？

**相關**：`master_ip_reconcile.py`；`GET /api/projects/<id>/ip-reconciliation`

---

## 2. 編號與配對

### Q2.1 Q185 vs Q0185 是否同一宗？ `[Unknown]`

`master_link.find_project_for_quotation()` 含 4 位補零 MP 變體 — `master_link.py` L7–9

**需確認**：业务是否一律 4 位序號比對？

---

### Q2.2 項目編號尾碼 `_kp` 是否必須一致？ `[Inferred]`

`sc_contract_ref._project_core()` 可做 core 比對 — `sc_contract_ref.py`

**需確認**：是否允许跨負責人縮寫配對？

---

### Q2.3 一項目多報價時負責人顯示？ `[Unknown]`

Summary 已顯示 `person_in_charge` — `projects.js`

**需確認**：以 Master List 還是項目表為準？

---

## 3. 權限與安全

### Q3.1 上線前是否必须登入？ `[Verified + Unknown]`

- Code：无 login；全部 `/api/*` 除 restore 外无 auth — `app.py`
- 匯報：权限「尚未上线」— `docs/匯報-20260814.md` §3.3

**需確認**：Production 是否计划 `AUTH_ENABLED`？谁可改 Master List / 糧期？

---

### Q3.2 空庫 restore 免 Token 风险？ `[Verified]`

`restore_database()`：空庫可免 Token；非空库需 `RESTORE_TOKEN` — `app.py` L1873–1881

**需確認**：生產空庫部署流程是否可接受？

---

## 4. 資料維護

### Q4.1 staff 重複同名记录？ `[Inferred]`

`list_master_person_roster()` 已优先 `is_active=1` — `database.py`

**需確認**：是否清理停用重複列（如历史 Dennis Chan 多笔）？

---

### Q4.2 Ref Excel 同步責任？ `[Unknown]`

来源：`docs/匯報-20260814.md` §3.2

| 資料 | 同步 API |
|------|----------|
| Master List | `/api/master/sync` |
| MS/C | `/api/sc-contract-registry/sync` |
| Summary | `/api/import/summary/sync` |

**需確認**：誰負責定期 sync？年份檔更新流程？

---

### Q4.3 Master List 財務子表「需重 sync」？ `[Inferred]`

匯報 L116 主观成熟度；code 有 finance API 但数据新鲜度未知。

**需確認**：上次完整 sync 時間与验证方式？

---

## 5. 功能范围

### Q5.1 主合約 FAC PDF 是否仍需要？ `[Unknown]`

- UI 表单已有 — `main_con_fac.js`
- PENDING 标 HOLD — `PENDING.md` L193
- 匯報成熟度 ●●○○ — `docs/匯報-20260814.md` L122

**需確認**：是否对齐 Excel p19 打印版？

---

### Q5.2 是否需要 BOQ 模組？ `[Verified 不存在]` · **待 QS 會議**

Code 无 BOQ 表、无 BOQ API（见 `docs/BOQ Workflow.md`）。

**现状**：PPT 第一期（p5、p15–18、p19–21）与 `PENDING.md` 均未列 BOQ；系统以 header-level 总额（判项价、VO、Excel 粮期、FAC 手填 B/E/F/G）运作。

**会议材料**：

- 简报：[`docs/BOQ Decision - QS Meeting Brief.md`](BOQ%20Decision%20-%20Meeting%20Brief.md)
- 纪录模板：[`docs/BOQ Decision - Meeting Notes.md`](BOQ%20Decision%20-%20Meeting%20Notes.md)

**决策选项**（会后在 Meeting Notes 勾选一项并更新本节）：

| 选项 | 动作 | 后续文件 |
|------|------|----------|
| Out of scope | 不做 BOQ；SOT/SOR 附件即可 | 更新 `PENDING.md` 备注 |
| 轻量加强 | C 行 MOS、SC FAC 物料列、FAC remeasurement UX | [`BOQ Decision - Lightweight Scope.md`](BOQ%20Decision%20-%20Lightweight%20Scope.md) |
| 报价明细子表 | OCR 行持久化挂判项，不驱动粮款 | Lightweight Scope §4 |
| 完整 BOQ 模块 | qty×rate、完成 % 驱动 IP/Interim Cert | [`BOQ Module Design (Draft).md`](BOQ%20Module%20Design%20(Draft).md) |

**暂定建议（会前）**：暂不开发完整 BOQ，待 QS 确认 A/B/C 行来源与 SOT/SOR 用法后再定。

**QS 确认结果**：_（填 Meeting Notes 后更新）_

**最终决策**：_（Out of scope / 轻量 / 明细子表 / 完整 BOQ）_

**决策日期**：_

---

### Q5.3 分判商主檔优先级？ `[Inferred]`

匯報 Phase 2 规划 `subcontractor_companies` — code 未建表。

**需確認**：MS/C「外判公司」下拉是否优先于 FAC Phase C？

---

## 6. 文件與版本

### Q6.1 PENDING.md 版本字串过时 `[Verified]`

`PENDING.md` L226 写 `20260807-doc-settings`；实际 `startup.APP_VERSION = '20260813-eng-cat'`

**需確認**：文档维护责任。

---

## 問題索引表

| ID | 主题 | 类型 | 阻塞 |
|----|------|------|------|
| Q1.1 | A–E 双公式 | Verified | 报表一致性 |
| Q1.2 | VO 是否计入 sc_stats | Verified | Dashboard 准确性 |
| Q1.3 | 保固金 % | Verified+Inferred | 中期粮款 |
| Q1.4 | MOS C 行 | Verified | 模板完整度 |
| Q1.5 | 粮期核对权威 | Verified | 对账流程 |
| Q2.1 | 序号补零 | Unknown | 自动配对 |
| Q2.2 | 尾缀 kp | Inferred | MS/C 链接 |
| Q3.1 | 登入 | Verified+Unknown | 上线安全 |
| Q5.1 | 主合约 FAC PDF | Unknown | p19 交付 |
| Q5.2 | BOQ | Verified | 产品范围 |

---

## 建议汇報时优先确认（Top 5）`[Inferred]`

1. Q1.1 — A–E 公式以 Excel 哪页为准  
2. Q3.1 — 是否上线前必须登入  
3. Q2.1 — Q185 / Q0185 统一规则  
4. Q1.3 — 保固金 5% 是否固定  
5. Q4.2 — Ref Excel 谁负责 sync  
