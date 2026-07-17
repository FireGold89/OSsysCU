/* staff.js — 項目負責人管理 */
const StaffRoster = {
  list: [],
  roles: [],

  async loadRoles() {
    if (this.roles.length) return this.roles;
    const data = await api('GET', '/staff/roles');
    this.roles = data?.roles || [];
    return this.roles;
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

  roleLabel(roleId) {
    const r = this.roles.find(x => x.id === roleId);
    return r ? r.label : roleId || '—';
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
      const picked = (wantName && (norm(s.name_en) === wantName || norm(s.name_zh) === wantName))
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
        subParts.push(`<div class="td-muted" style="font-size:11px">${s.variant_count} 種主檔寫法</div>`);
      }
      const sub = subParts.join('');
      let status;
      if (!s.in_staff_table) {
        status = '<span class="badge badge-info" title="僅 Master List 主檔">Master List</span>';
      } else if (s.is_active) {
        status = '<span class="badge badge-success">啟用</span>';
      } else {
        status = '<span class="badge badge-muted">停用</span>';
      }
      const role = s.in_staff_table
        ? `<span class="badge badge-info" title="預留權限">${escHtml(this.roleLabel(s.access_role))}</span>`
        : '<span class="td-muted">—</span>';
      const usage = `${s.quotation_count || 0} 報價 · ${s.project_count || 0} 項目`;
      const nameArg = escHtml(name).replace(/'/g, "\\'");
      const actions = s.id
        ? `<button class="btn btn-secondary btn-sm" onclick="StaffRoster.openEdit(${s.id})">編輯</button>
           ${s.is_active ? `<button class="btn btn-danger btn-sm" onclick="StaffRoster.deactivate(${s.id})">停用</button>` : ''}`
        : `<button class="btn btn-secondary btn-sm" onclick="StaffRoster.openAddFromMaster('${nameArg}')">建立對應</button>`;
      return `<tr class="${s.is_active || !s.in_staff_table ? '' : 'row-muted'}">
        <td><strong>${escHtml(name)}</strong>${sub}</td>
        <td>${escHtml(s.department || '—')}</td>
        <td class="td-muted">${escHtml(s.email || '—')}</td>
        <td>${role}</td>
        <td class="td-muted" style="font-size:12px">${usage}</td>
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
    ['staffNameEn', 'staffNameZh', 'staffEmail', 'staffPhone', 'staffDept', 'staffNotes'].forEach(id => {
      document.getElementById(id).value = '';
    });
    document.getElementById('staffRole').value = 'qs';
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
    document.getElementById('staffDept').value = s.department || '';
    document.getElementById('staffRole').value = s.access_role || 'qs';
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
      || (body.name_zh && body.name_zh.length <= 2)) {
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
};
