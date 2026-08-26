# Calculation Rules

> 各報表／頁面使用的 **金額公式** 與 **code 位置**。  
> 標示已知 **公式不一致** 處。

---

## 1. 財務報表 / Dashboard — `get_project_summary()` `[Code]`

**函數**：`database.get_project_summary(project_id)` L4007–4070  
**API**：`GET /api/reports/summary/<id>`  
**前端**：`Dashboard.load()`, `Reports.load()` — `main.js`, `reports.js`

### 合約結算 A–E（Excel Project Summary 右下角）

| 代號 | 公式 | Code |
|------|------|------|
| A | `projects.contract_amount` | L4048 |
| B | `SUM(subcontractors.contract_amount)` where `NOT is_excluded` | L4044 |
| C | `−SUM(contract_amount)` where `is_excluded` | L4045 |
| D | `B + C + labour_allocation` | L4047 |
| E | `A − D` | L4049 |
| 利率 | `E / A × 100` | L4050 |

### 分判統計（sc_stats）

每判項：

- `contract_amount` — **不含** `vo_amount`
- `total_paid` — `SUM(payment_records.paid_amount)` by sc_no
- `remainder` — `contract_amount − total_paid`

**證據**：L4016–4031 SQL

---

## 2. Cover Page 結算 — `compute_settlement()` `[Code]`

**函數**：`project_cover.compute_settlement(project, subcontractors)` L270–320  
**用途**：註冊及更新頁、Cover Page 第 5–6 頁

| 代號 | 公式 | Code |
|------|------|------|
| A | `contract_amount` | L279 |
| B | `SUM(contract_amount)` — SC 類判項（`_sc_charge_group == 'B'`），不含 excluded | L286–293 |
| C | M/O 類 + `labour_allocation` − excluded；可手覆 `material_other_expenses` | L294–302 |
| D | `A − B − C` | L304 |
| E | `D / A × 100` | L305 |

### SC 分組規則 `[Code]`

`_sc_charge_group(sc_no)` — 依 M-/SC-/O- 前綴：

- `'B'` → 分判承包價
- 其他 → 物料及其他

**證據**：`project_cover.py`

---

## ⚠️ 公式不一致（Verified）

| 項目 | `get_project_summary` | `compute_settlement` |
|------|----------------------|----------------------|
| B 定義 | 全部非 excluded 判項 | 僅 SC 類 |
| C 定義 | 負的 excluded 合計 | M/O + labour − excluded |
| D / 利潤 | `A − (B+C+labour)` | `A − B − C` |

**影響**：Dashboard／QS PDF 與 Cover Page 註冊及更新可能顯示不同利潤數字。

---

## 3. 中期糧款 — `build_interim_cert_model()` `[Code]`

**函數**：`interim_cert_report.build_interim_cert_model(cert)` L120+

| 項目 | 公式 |
|------|------|
| `sc_total` | `sc_contract_sum + vo_amount` |
| B 今期 | `SUM(勾選 vo_items.amount)` |
| B 累計 | `b_prev + b_prov` |
| 保固金 | `_retention_cumulative(sub_cum + b_prov, sc_total, retention_pct)` → 負數，上限 `sc_total × pct` |
| C (MOS) | `0` |
| A 反推 | `net − b_prov − ret_prov − ded − std`（若未手填 `a_current_provisional`） |
| 總計 | A+B 小計 + 保固金 + 扣款 + 標準行 |

**預設 retention_pct**：`0.05` — 前端 `payments.js` L653 硬編；後端 `_f(cert.get('retention_pct'), 0.05)`

**未使用**：`subcontractors.retention_sum` 欄（欄位存在，中期糧款 model 未讀）

---

## 4. 前端中期糧款聯動 — `calcInterimAmounts()` `[Code]`

**函數**：`payments.js` L466–491

```
totalContract = contract_sum + vo_amount
balance = totalContract - prevPaid - scDeductions
thisPay = balance + adjNet + voProv
```

**與報表差異**：此处 `totalContract` **含 VO**；`get_project_summary.sc_stats` **不含 VO**。

---

## 5. 地盤 IP 累計 % — `calc_ip_cumulative_pcts()` `[Code]`

**函數**：`database.py` L3538–3554

```
application_pct = 累計 application_amount / contract_amount × 100
certified_income_pct = 累計 certified_income / contract_amount × 100
```

---

## 6. 主合約 FAC — `build_main_con_fac()` `[Code]`

**函數**：`main_fac.py` L70–100

| 行 | 來源 |
|----|------|
| H | `A + B + C + D + E + F + G` |
| D | VO 自動或 `fac_variations_d_override` |
| I | `ip_total_income` 或 interim sum 或 override |
| J | 扣款自動或 `fac_contra_charge_j_override` |
| K | `H − I − J` |

B/E/F/G：**手填**，非 BOQ 匯總。

---

## 7. 分判 FAC — `build_sc_fac()` `[Code]`

**函數**：`sc_fac.py`

```
final_sum = original_contract + vo_total
outstanding = final_sum - total_paid - |deductions|
```

VO / 扣款明細：`_vo_appendix_rows()`, `_deduction_appendix_rows()`

---

## 8. QS 匯報 PDF 關注事項 — `_attention_items()` `[Code]`

**函數**：`qs_report_pdf._attention_items(summary, sc_list)` L244+

規則型（非 AI），例如：

- `profit_e < 0` → 負利潤警示
- `profit_rate < 5` → 低利潤率
- `advance > 0` → 墊支
- 高 remainder 比例 → 未付偏多

輸入來自 `get_project_summary()` 的 `contract_calc`, `ip_period`, `total_paid`。

---

## 9. VO 金額同步 — `sync_sc_vo_amount()` `[Code]`

```
subcontractors.vo_amount = SUM(sc_vo_records.amount) WHERE record_type='vo' AND sc_no=...
```

扣款不計入 `vo_amount`（deduction 為負數行，匯總邏輯見 `sum_sc_vo_amount()`）。

---

## 10. Master List 財務

**模組**：`master_finance.py`, `master_ip_reconcile.py`  
**API**：`/api/master/item/.../finance`, `/ip-reconcile`

與地盤 `interim_payments` **對照**，不參與上述 A–E 公式。

---

## 計算規則速查表

| 場景 | 主函數 | 檔案 |
|------|--------|------|
| Dashboard A–E | `get_project_summary` | `database.py` |
| Cover 註冊及更新 A–E | `compute_settlement` | `project_cover.py` |
| 中期糧款行 | `build_interim_cert_model` | `interim_cert_report.py` |
| IP 累計 % | `calc_ip_cumulative_pcts` | `database.py` |
| 主合約 FAC | `build_main_con_fac` | `main_fac.py` |
| 分判 FAC | `build_sc_fac` | `sc_fac.py` |
| QS 關注事項 | `_attention_items` | `qs_report_pdf.py` |

---

## `[Inferred]`

- Excel 地盤表為各公式的设计基准；code 注释「駿昇第十期」指中期糧款模板来源。
- 统一 A–E 应选定 `get_project_summary` 或 `compute_settlement` 之一为 canonical，需 QS 业务确认（见 Open Questions.md）。
