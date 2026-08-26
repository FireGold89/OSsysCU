# BOQ 決策 — 輕量加強範圍（若 QS 選「不做完整 BOQ」）

> **觸發條件**：QS 會議決策為「輕量加強」或「報價明細子表（不驅動糧款）」  
> **會議紀錄**：[`BOQ Decision - Meeting Notes.md`](BOQ%20Decision%20-%20Meeting%20Notes.md)  
> **不建 BOQ 引擎**：仍用 header-level 總額驅動糧款；只補 PPT/Excel 缺口與 code 未接線處。

---

## 1. 目標

在 **不新建 BOQ 模組** 前提下，滿足 QS 對 MOS、FAC remeasurement、分判 FAC 物料列的實務需求。

---

## 2. 優先序與工估

| 優先 | 項目 | 說明 | 涉及檔案 | 工估 |
|------|------|------|----------|------|
| P1 | **C 行 Material On Site 接線** | `vo_material` 套用至中期糧款時匯總入 C 行，取代恒 0 | `interim_cert_report.py`, `payments.js`, `sc_vo_templates.py` | 小（1–2 天） |
| P2 | **分判 FAC 物料/人工加減列** | Phase C：可編輯覆寫列（Excel R27–31 類），手填總額 | `sc_fac.py`, `sc_fac_pdf.py`, `frontend/js/sc_fac.js` | 小～中（2–3 天） |
| P3 | **主合約 FAC remeasurement UX** | B/E/F/G 手填欄加 Excel p19 對照提示、來源備註欄 | `main_con_fac.js`, `main_fac.py` | 小（1 天） |
| P4 | **報價明細子表（可選）** | OCR 行持久化挂 `subcontractors`，可編輯，**不**驅動 A/B/C | 新表 `sc_quotation_lines`, `database.py`, `app.py`, OCR UI | 中（3–5 天） |

**建議 sprint 順序**：P1 → P2 → P3；P4 僅在 QS 明確要「存明細但不計糧款」時做。

---

## 3. P1 — C 行 MOS 接線

### 現況 `[Code]`

- `sc_vo_templates.py`：`vo_material` → `cert_label: 'C. Material On Site'`
- `interim_cert_report.py` L141：`c_cur = c_prev = c_prov = 0.0`（硬編）

### 設計

1. 中期糧款套用 VO 時，依 `cert_label` 或 `code=vo_material` 分流：
   - 一般 VO → **B 行**（現行）
   - `vo_material` → **C 行** 累計
2. `build_interim_cert_model()`：從 `vo_items` 分離 MOS 金額計入 `c_prov` / `c_cur`
3. 前期累計：若需跨期 C 行累計，擴 `previous_c_cum`（與 A/B 一致）
4. PDF/XLSX：C 行顯示 MOS 備註（ref_no 串接，同 B 行邏輯）

### 驗收

- [ ] 選 `Material On Site` VO 套用後，計算書 C 行非 0
- [ ] 一般 VO 仍只進 B 行
- [ ] 累計糧款跨期 C 行正確

### 依賴

- 需 QS 確認 A3：實務會用 C 行（會議 Brief A3）

---

## 4. P2 — 分判 FAC 物料/人工加減列

### 現況 `[Code]`

- `PENDING.md` L190：Phase C 待做
- `sc_fac_pdf.py` 已有簡化扣款列；物料/人工加減未可編輯

### 設計

1. `subcontractors` 或 JSON 欄存 **手填調整列**（label + amount），對齊 Excel R27–31
2. UI：`sc_fac.js` 表格可增刪列（總額制，非 line-item）
3. PDF P3 帶入調整列，匯總 Outstanding

### 驗收

- [ ] 每判項可填 0–N 列物料/人工加減
- [ ] PDF 與 Excel 範本列名一致
- [ ] 不需 BOQ 表

### 依賴

- 需 QS 確認 B3：手填總額列即可

---

## 5. P3 — 主合約 FAC remeasurement UX

### 現況 `[Code]`

- `main_fac.py`：B/E/F/G 手填 REAL 欄
- 無來源說明、無 Excel 對照

### 設計

1. 各欄旁加 **? 提示**（p19 列名 + 「通常在 Excel BOQ 重算後貼總數」）
2. 可選：`fac_remeasurement_note` TEXT 備註（「依 SOR v2 2026-03」）
3. 不自動從 BOQ 計算

### 驗收

- [ ] QS 可在 UI 理解 B/E 與 Excel 對應
- [ ] 備註可存可顯示於匯出（若需要）

---

## 6. P4 — 報價明細子表（可選分支）

### 觸發

QS 選「持久化 OCR 明細，不驅動糧款」（決策矩陣第三行）。

### 最小 schema `[Inferred]`

```sql
CREATE TABLE sc_quotation_lines (
  id INTEGER PRIMARY KEY,
  subcontractor_id INTEGER NOT NULL REFERENCES subcontractors(id),
  line_no INTEGER,
  description TEXT,
  quantity REAL,
  unit TEXT,
  unit_rate REAL,
  amount REAL,
  source TEXT,           -- 'ocr' | 'manual'
  created_at TEXT,
  updated_at TEXT
);
```

### API（草案）

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/subcontractors/<id>/quotation-lines` | 列表 |
| PUT | `/api/subcontractors/<id>/quotation-lines` | 整批取代 |
| POST | `/api/ocr/.../apply-lines` | OCR 結果寫入子表 |

### 限制（刻意）

- **不**更新 `contract_amount` 自動
- **不**參與 `interim_cert_report` A/B/C
- 判項總額仍由 QS 手填或 OCR 總價欄

---

## 7. 明確不做（輕量範圍內）

- qty × rate 自動 remeasurement
- 行項目完成 % → IP 申請 %
- SOR 解析入庫（除非升級至完整 BOQ Phase）
- 新 BOQ 專用導航頁

---

## 8. 與其他待辦的關係

| 待辦 | 關係 |
|------|------|
| Retention 連動 | 獨立；P1 C 行接線後需確認 retention 基數是否含 C |
| Q1.1 A–E 雙公式 | 應先解再改匯總邏輯 |
| Q1.2 VO 計入口徑 | MOS 若算 VO 總額需對齊 |

---

*建立：2026-08-14 · 待 QS 會議勾選「輕量加強」後執行*
