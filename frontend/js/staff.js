/* staff.js — 項目負責人管理 */
const StaffRoster = {
  list: [],
  roles: [],
  departments: [],
  _quotPerson: null,
  _quotOffset: 0,
  _quotLimit: 50,

  async loadRoles() {
    if (this.roles.length && this.departments.length) {
      return { roles: this.roles, departments: this.departments };
    }
    const data = await api('GET', '/staff/roles');
    this.roles = data?.roles || [];
    this.departments = data?.departments || [];
    return { roles: this.roles, departments: this.departments };
  },

  normalizeRoleId(roleId) {
    const aliases = {
      admin: 'mgr',
      finance: 'ga',
      engineering: 'mepork_eng',
      eng: 'mepork_eng',
    };
    const r = (roleId || '').trim().toLowerCase();
    return aliases[r] || r;
  },

  roleLabel(roleId) {
    const rid = this.normalizeRoleId(roleId);
    const r = this.roles.find(x => x.id === rid);
    if (r) return r.label;
    const legacy = {
      admin: '管理',
      finance: '行政',
      engineering: '美博工程',
      eng: '美博工程',
      prop_eng: '物業工程',
      mepork_eng: '美博工程',
      ga: '行政',
      mgr: '管理',
      viewer: '唯讀',
      qs: 'QS',
    };
    return legacy[rid] || roleId || '—';
  },

  syncModalSelects(selectedRole = 'qs', selectedDept = '') {
    const roleEl = document.getElementById('staffRole');
    const deptEl = document.getElementById('staffDept');
    const roleId = this.normalizeRoleId(selectedRole) || 'qs';
    const dept = (selectedDept || '').trim();

    if (roleEl) {
      let html = '';
      (this.roles || []).forEach((r) => {
        html += `<option value="${escHtml(r.id)}">${escHtml(r.label)}</option>`;
      });
      if (selectedRole && roleId !== selectedRole && !this.roles.find((r) => r.id === selectedRole)) {
        html += `<option value="${escHtml(selectedRole)}">${escHtml(this.roleLabel(selectedRole))}（舊）</option>`;
      }
      roleEl.innerHTML = html;
      roleEl.value = this.roles.find((r) => r.id === roleId) ? roleId : (selectedRole || 'qs');
    }

    if (deptEl) {
      let html = '<option value="">— 選擇部門 —</option>';
      (this.departments || []).forEach((d) => {
        html += `<option value="${escHtml(d.id)}">${escHtml(d.label)}</option>`;
      });
      if (dept && !this.departments.find((d) => d.id === dept)) {
        html += `<option value="${escHtml(dept)}">${escHtml(dept)}（舊）</option>`;
      }
      deptEl.innerHTML = html;
      if (dept) deptEl.value = dept;
    }
  },

  async load(activeOnly = false) {
    const q = activeOnly ? '?active=1' : '';
    this.list = await api('GET', `/staff${q}`) || [];
    return this.list;
  },

  displayName(row) {
    if (!row) return '—';
    return row.person_name || row.name_en || row.name_zh || '—';
  },

  nameFor(code) {
    const c = (code || '').toLowerCase();
    const row = this.list.find(s => s.code === c);
    if (row) return this.displayName(row);
    return c ? c.toUpperCase() : '—';
  },

  findByName(name) {
    const n = (name || '').trim().toLowerCase();
    if (!n) return null;
    return this.list.find(s =>
      (s.name_en || '').trim().toLowerCase() === n
      || (s.name_zh || '').trim().toLowerCase() === n
    ) || null;
  },

  fillPersonSelect(selectEl, { selectedStaffId, selectedName } = {}, { allowEmpty = true } = {}) {
    if (!selectEl) return;
    const norm = (s) => (s || '').trim().toLowerCase();
    const wantName = norm(selectedName);
    let html = allowEmpty ? '<option value="">— 選擇項目負責人 —</option>' : '';
    const seen = new Set();
    (this.list.filter(s => s.is_active !== 0 && s.is_active !== false) || this.list).forEach(s => {
      const name = (s.person_name || this.displayName(s)).trim();
      const key = name.trim().toLowerCase();
      if (!key || seen.has(key)) return;
      seen.add(key);
      const sub = s.name_en && s.name_zh && s.name_en !== s.name_zh ? `（${s.name_zh}）` : '';
      const label = `${name}${sub}`;
      const picked = (wantName && (norm(name) === wantName || norm(s.name_en) === wantName || norm(s.name_zh) === wantName))
        || (selectedStaffId && String(s.id) === String(selectedStaffId));
      html += `<option value="${escHtml(name)}"${picked ? ' selected' : ''}>${escHtml(label)}</option>`;
    });
    selectEl.innerHTML = html;
  },

  staffFromSelect(selectEl) {
    const norm = (s) => (s || '').trim().toLowerCase();
    const val = norm(selectEl?.value);
    if (!val) return null;
    return this.list.find(s =>
      norm(s.name_en) === val || norm(s.name_zh) === val
    ) || null;
  },

  async loadQsStaff(force = false) {
    if (!force && this.list.length) return this.list;
    return this.load(true);
  },

  fillQsSelect(selectEl, { selectedName } = {}) {
    if (!selectEl) return;
    const norm = (s) => (s || '').trim().toLowerCase();
    const want = norm(selectedName);
    let html = '<option value="">— 選擇負責 QS —</option>';
    const seen = new Set();
    (this.list.filter(s => s.is_active !== 0 && s.is_active !== false) || this.list).forEach((s) => {
      const name = (s.person_name || this.displayName(s)).trim();
      const key = norm(name);
      if (!key || seen.has(key)) return;
      seen.add(key);
      const sub = s.name_en && s.name_zh && s.name_en !== s.name_zh ? `（${s.name_zh}）` : '';
      const picked = want && (norm(name) === want || norm(s.name_en) === want || norm(s.name_zh) === want);
      html += `<option value="${escHtml(name)}"${picked ? ' selected' : ''}>${escHtml(name + sub)}</option>`;
    });
    if (want && !seen.has(want)) {
      const legacy = (selectedName || '').trim();
      html += `<option value="${escHtml(legacy)}" selected>${escHtml(legacy)}（舊資料）</option>`;
    }
    selectEl.innerHTML = html;
  },

  async refresh() {
    await this.loadRoles();
    await this.load();
    this.render();
  },

  render() {
    const tbody = document.getElementById('staffTableBody');
    if (!tbody) return;
    const inRoster = this.list.filter(s => s.in_staff_table && s.is_active);
    document.getElementById('staffStatActive').textContent = inRoster.length;
    document.getElementById('staffStatTotal').textContent = this.list.length;

    if (!this.list.length) {
      tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state" style="padding:32px">Master List 尚無項目負責人資料</div></td></tr>';
      return;
    }

    tbody.innerHTML = this.list.map(s => {
      const name = this.displayName(s);
      const subParts = [];
      if (s.name_zh && s.name_en && s.name_en !== s.name_zh) {
        subParts.push(`<div class="td-muted" style="font-size:11px">${escHtml(s.name_zh)}</div>`);
      }
      if ((s.variant_count || 0) > 1) {
        subParts.push(`<div class="td-muted" style="font-size:11px">${s.variant_count} 種拼寫</div>`);
      }
      const sub = subParts.join('');
      let status;
      if (!s.in_staff_table) {
        status = '<span class="badge badge-info" title="僅出現在報價／標書清單，尚未建檔">僅清單</span>';
      } else if (s.is_active) {
        status = '<span class="badge badge-success">啟用</span>';
      } else {
        status = '<span class="badge badge-muted">停用</span>';
      }
      const role = s.in_staff_table
        ? `<span class="badge badge-info" title="權限角色">${escHtml(this.roleLabel(s.access_role))}</span>`
        : '<span class="td-muted">—</span>';
      const usage = `${s.quotation_count || 0} 報價 · ${s.project_count || 0} 項目`;
      const usageCell = (s.quotation_count || 0) > 0
        ? `<button type="button" class="staff-usage-link" title="查看及編輯報價" onclick="StaffRoster.openQuotations('${escHtml(name).replace(/'/g, "\\'")}')">${usage}</button>`
        : `<span class="td-muted">${usage}</span>`;
      const nameArg = escHtml(name).replace(/'/g, "\\'");
      const actions = s.id
        ? `<div class="table-row-actions">
            <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯" onclick="StaffRoster.openEdit(${s.id})">✏️</button>
            ${s.is_active ? `<button type="button" class="btn btn-icon btn-danger btn-sm" title="停用" onclick="StaffRoster.deactivate(${s.id})">🚫</button>` : ''}
          </div>`
        : `<div class="table-row-actions">
            <button type="button" class="btn btn-icon btn-secondary btn-sm" title="建立對應" onclick="StaffRoster.openAddFromMaster('${nameArg}')">➕</button>
          </div>`;
      return `<tr class="${s.is_active || !s.in_staff_table ? '' : 'row-muted'}">
        <td><strong>${escHtml(name)}</strong>${sub}</td>
        <td>${escHtml(s.department || '—')}</td>
        <td class="td-muted">${escHtml(s.email || '—')}</td>
        <td>${role}</td>
        <td class="td-muted" style="font-size:12px">${usageCell}</td>
        <td>${status}</td>
        <td>${actions}</td>
      </tr>`;
    }).join('');
  },

  openAddFromMaster(name) {
    this.openAdd();
    if (name) document.getElementById('staffNameEn').value = name;
  },

  openAdd() {
    document.getElementById('staffModalTitle').textContent = '新增項目負責人';
    document.getElementById('staffModalId').value = '';
    ['staffNameEn', 'staffNameZh', 'staffEmail', 'staffPhone', 'staffNotes'].forEach(id => {
      document.getElementById(id).value = '';
    });
    this.syncModalSelects('qs', '');
    document.getElementById('staffActive').checked = true;
    document.getElementById('staffModal').classList.add('open');
  },

  async openEdit(id) {
    const s = await api('GET', `/staff/${id}`);
    if (!s) return;
    document.getElementById('staffModalTitle').textContent = '編輯項目負責人';
    document.getElementById('staffModalId').value = s.id;
    document.getElementById('staffNameEn').value = s.name_en || '';
    document.getElementById('staffNameZh').value = s.name_zh || '';
    document.getElementById('staffEmail').value = s.email || '';
    document.getElementById('staffPhone').value = s.phone || '';
    this.syncModalSelects(s.access_role || 'qs', s.department || '');
    document.getElementById('staffNotes').value = s.notes || '';
    document.getElementById('staffActive').checked = !!s.is_active;
    document.getElementById('staffModal').classList.add('open');
  },

  closeModal() {
    document.getElementById('staffModal').classList.remove('open');
  },

  async saveModal() {
    const id = document.getElementById('staffModalId').value;
    const body = {
      name_en: document.getElementById('staffNameEn').value.trim(),
      name_zh: document.getElementById('staffNameZh').value.trim(),
      email: document.getElementById('staffEmail').value.trim(),
      phone: document.getElementById('staffPhone').value.trim(),
      department: document.getElementById('staffDept').value.trim(),
      access_role: document.getElementById('staffRole').value,
      is_active: document.getElementById('staffActive').checked ? 1 : 0,
      notes: document.getElementById('staffNotes').value.trim(),
    };
    if (!body.name_en && !body.name_zh) {
      toast('請填寫項目負責人全名（英文或中文）', 'warning');
      return;
    }
    if ((body.name_en && body.name_en.length <= 4 && !body.name_en.includes(' '))
      || (body.name_zh && body.name_zh.length > 0 && body.name_zh.length <= 2)) {
      toast('請填寫全名，不要使用縮寫（如 EC、KM）', 'warning');
      return;
    }
    try {
      if (id) {
        await api('PUT', `/staff/${id}`, body);
        toast('項目負責人已更新', 'success');
      } else {
        await api('POST', '/staff', body);
        toast('項目負責人已新增', 'success');
      }
      this.closeModal();
      await this.refresh();
      if (typeof MasterList !== 'undefined' && MasterList.load) MasterList.load();
    } catch (e) {}
  },

  async deactivate(id) {
    const s = this.list.find(x => x.id === id);
    const label = this.displayName(s) || id;
    if (!confirm(`停用項目負責人「${label}」？\n既有 Master List 記錄不受影響，但新工程項目將無法選用。`)) return;
    await api('DELETE', `/staff/${id}`);
    toast('已停用', 'success');
    await this.refresh();
  },

  async openQuotations(personName) {
    const name = (personName || '').trim();
    if (!name) return;
    this._quotPerson = name;
    this._quotOffset = 0;
    document.getElementById('staffQuotModalTitle').textContent = `報價清單 · ${name}`;
    document.getElementById('staffQuotModalSub').textContent = '載入中…';
    document.getElementById('staffQuotTableBody').innerHTML =
      '<tr><td colspan="7"><div class="empty-state" style="padding:32px">載入中…</div></td></tr>';
    document.getElementById('staffQuotModal').classList.add('open');
    await this.loadQuotations();
  },

  closeQuotModal() {
    document.getElementById('staffQuotModal').classList.remove('open');
    this._quotPerson = null;
  },

  openInMasterList() {
    const person = this._quotPerson;
    if (!person) return;
    this.closeQuotModal();
    if (typeof MasterList !== 'undefined') {
      MasterList._pendingPersonFilter = person;
    }
    App.navigate('master-list');
  },

  async loadQuotations() {
    const person = this._quotPerson;
    const tbody = document.getElementById('staffQuotTableBody');
    const sub = document.getElementById('staffQuotModalSub');
    if (!person || !tbody) return;
    const params = new URLSearchParams({
      person,
      limit: String(this._quotLimit),
      offset: String(this._quotOffset),
    });
    const data = await api('GET', `/staff/quotations?${params}`);
    if (!data || person !== this._quotPerson) return;
    const total = data.total || 0;
    const items = data.items || [];
    const shown = this._quotOffset + items.length;
    sub.textContent = total
      ? `共 ${total} 筆 · 點 ✏️ 可編輯報價內容及項目負責人`
      : '尚無報價記錄';
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state" style="padding:32px">此負責人尚無報價／標書</div></td></tr>';
      this._renderQuotPagination(total);
      return;
    }
    tbody.innerHTML = items.map(r => {
      const awarded = r.awarded === '中'
        ? '<span class="badge badge-success">中</span>'
        : '<span class="td-muted">—</span>';
      const linked = r.project_id
        ? `<span class="sc-no-chip">${escHtml((r.account_code || r.mp_contract_code || r.project_code || '—').trim())}</span>`
        : '<span class="badge badge-warning">未配對</span>';
      const desc = [r.site_name, r.description].filter(Boolean).join(' · ');
      return `<tr>
        <td><code>${escHtml(r.quotation_no || '—')}</code></td>
        <td>${escHtml(r.quote_date || '—')}</td>
        <td>${escHtml(r.doc_type || '—')}</td>
        <td class="td-muted" style="max-width:220px">${escHtml(desc || '—')}</td>
        <td>${awarded}</td>
        <td>${linked}</td>
        <td>
          <button type="button" class="btn btn-icon btn-secondary btn-sm" title="編輯報價" onclick="StaffRoster.editQuotation(${r.id})">✏️</button>
        </td>
      </tr>`;
    }).join('');
    this._renderQuotPagination(total);
  },

  _renderQuotPagination(total) {
    const el = document.getElementById('staffQuotPagination');
    if (!el) return;
    if (total <= this._quotLimit) {
      el.innerHTML = '';
      return;
    }
    const page = Math.floor(this._quotOffset / this._quotLimit) + 1;
    const pages = Math.ceil(total / this._quotLimit);
    el.innerHTML = `
      <button type="button" class="btn btn-secondary btn-sm" ${this._quotOffset <= 0 ? 'disabled' : ''} onclick="StaffRoster.quotPrev()">上一頁</button>
      <span style="font-size:12px;color:var(--text-muted);padding:0 8px">${page} / ${pages}</span>
      <button type="button" class="btn btn-secondary btn-sm" ${this._quotOffset + this._quotLimit >= total ? 'disabled' : ''} onclick="StaffRoster.quotNext()">下一頁</button>`;
  },

  quotPrev() {
    if (this._quotOffset <= 0) return;
    this._quotOffset = Math.max(0, this._quotOffset - this._quotLimit);
    this.loadQuotations();
  },

  quotNext() {
    this._quotOffset += this._quotLimit;
    this.loadQuotations();
  },

  async editQuotation(rowId) {
    if (typeof MasterList === 'undefined' || !MasterList.openEdit) {
      toast('Master List 模組未載入', 'warning');
      return;
    }
    await MasterList.openEdit(rowId);
  },
};
