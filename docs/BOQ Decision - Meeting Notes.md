# BOQ 模組決策 — QS 會議紀錄

> **簡報**：[`BOQ Decision - QS Meeting Brief.md`](BOQ%20Decision%20-%20Meeting%20Brief.md)  
> **填寫說明**：會議中逐題記錄 QS 回答；最後勾選一項決策並更新 [`Open Questions.md`](Open%20Questions.md) Q5.2。

---

## 會議資訊

| 欄位 | 內容 |
|------|------|
| 日期 | |
| 與會者（QS） | |
| 與會者（開發） | |
| 紀錄人 | |

---

## A. 工作流程

### A1 — 中期糧款 A 行（合約工程量）來源

**QS 回答**：

- [ ] 判項報價總額 × 完成 %
- [ ] Excel 算好「今期暫批」後手填
- [ ] 其他：_________________________

**備註**：

---

### A2 — B 行（後加/改）VO 登記是否足夠

**QS 回答**：

- [ ] 足夠，VO 加總即可
- [ ] 不足，需 BOQ 逐項匯總

**備註**：

---

### A3 — C 行 Material On Site

**QS 回答**：

- [ ] 實務不用 C 行
- [ ] 用手填總額（不需 line-item）
- [ ] 需要物料清單 × 單價 × 在場比例

**備註**：

---

### A4 — 主合約 FAC Remeasurement / Provisional Qty

**QS 回答**：

- [ ] Excel BOQ 重算後只貼總數入系統
- [ ] 希望系統保存 BOQ 明細

**備註**：

---

## B. 資料載體

### B1 — SOT & SOR

**QS 回答**：

- [ ] 即公司 BOQ，只存附件／連結即可
- [ ] 需要系統解析／儲存 SOR 行項目

**備註**：

---

### B2 — OCR 報價明細

**QS 回答**：

- [ ] OCR 輔助一次填判項描述即可
- [ ] 需要持久化、可編輯明細（但不驅動糧款）
- [ ] 需要持久化且連動糧款

**備註**：

---

### B3 — 分判 FAC 物料/人工加減列

**QS 回答**：

- [ ] 幾個手填總額列（對齊 Excel R27–31）
- [ ] 需展開 BOQ 明細

**備註**：

---

## C. 優先級

### C1 — BOQ 相對其他待辦的優先序

| 待辦 | QS 排序（1=最高） |
|------|-------------------|
| Retention 連動 | |
| 主合約 FAC PDF | |
| 分判商主檔 | |
| 登入 / Audit | |
| BOQ 或輕量加強 | |

**QS 是否將 BOQ 列為「不做」**：[ ] 是  [ ] 否

---

### C2 — 第一期上線範圍（無 BOQ 模組）

**QS 回答**：

- [ ] 可接受：判項總額 + VO + Excel 糧期 + FAC 手填 B/E/F/G
- [ ] 不可接受，必須有 BOQ／line-item 能力

**備註**：

---

## 決策（勾選一項）

- [ ] **Out of scope** — 不做 BOQ；SOT/SOR 附件即可；總額 + Excel  workflow
- [ ] **輕量加強** — 接 C 行 MOS、SC FAC 物料列、FAC remeasurement UX；不建新 BOQ 引擎
- [ ] **報價明細子表** — 持久化 OCR 行，挂判項；不驅動糧款
- [ ] **完整 BOQ 模組** — qty×rate、完成 % 驅動 IP/Interim Cert（獨立 Phase）

**決策日期**：  
**QS 簽確認**（口頭/書面）：  

---

## 會後行動

| 行動 | 負責 | 完成 |
|------|------|------|
| 更新 `Open Questions.md` Q5.2 | | [ ] |
| 更新 `PENDING.md` BOQ 範圍備註 | | [ ] |
| 若輕量：排 [`Lightweight Scope`](BOQ%20Decision%20-%20Lightweight%20Scope.md) | | [ ] |
| 若完整 BOQ：Review [`Design Draft`](BOQ%20Module%20Design%20(Draft).md) | | [ ] |

---

*範本建立：2026-08-14*
