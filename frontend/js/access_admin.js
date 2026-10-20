/* access_admin.js — 帳號與權限（管理員） */
const AccessAdmin = {
  catalog: null,
  users: [],
  editingId: null,

  async load() {
    const body = document.getElementById('accessUserBody');
    if (!body) return;
    if (typeof Auth !== 'undefined' && Auth.authRequired && !Auth.isAdmin()) {
      body.innerHTML = '<tr><td colspan="5"><div class="empty-state" style="padding:32px">需要管理員帳號</div></td></tr>';
      return;
    }
    body.innerHTML = '<tr><td colspan="5"><div class="empty-state" style="padding:32px">載入中…</div></td></tr>';
    try {
      this.catalog = await api('GET', '/admin/permission-catalog');
      this.users = await api('GET', '/admin/users') || [];
      this.render();
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:32px">${escHtml(e?.message || '載入失敗')}</div></td></tr>`;
    }
  },

  roleLabel(id) {
    const hit = (this.catalog?.presets || []).find((p) => p.id === id);
    return hit ? hit.label : (id || '—');
  },

  render() {
    const body = document.getElementById('accessUserBody');
    if (!body) return;
    if (!this.users.length) {
      body.innerHTML = '<tr><td colspan="5"><div class="empty-state" style="padding:32px">尚未建立系統內帳號。環境變數裡的管理員仍可登入。</div></td></tr>';
      return;
    }
    body.innerHTML = this.users.map((u) => `<tr>
      <td class="td-mono">${escHtml(u.username)}</td>
      <td>${escHtml(u.display_name || '—')}</td>
      <td>${escHtml(this.roleLabel(u.role))}</td>
      <td>${u.is_active ? '啟用' : '<span class="td-muted">停用</span>'}</td>
      <td>
        <button type="button" class="btn btn-secondary btn-sm" onclick="AccessAdmin.openEdit(${u.id})">編輯權限</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="AccessAdmin.remove(${u.id})">刪除</button>
      </td>
    </tr>`).join('');
  },

  _matrixHtml(selected) {
    const areas = this.catalog?.areas || [];
    const levels = this.catalog?.levels || [];
    return areas.map((area) => {
      const cur = selected?.[area.id] || 'none';
      const opts = levels.map((lv) => (
        `<option value="${lv.id}" ${lv.id === cur ? 'selected' : ''}>${escHtml(lv.label)}</option>`
      )).join('');
      return `<tr>
        <td>${escHtml(area.label)}<div class="form-hint">${escHtml(area.hint || '')}</div></td>
        <td><select class="form-input access-level" data-area="${escHtml(area.id)}">${opts}</select></td>
      </tr>`;
    }).join('');
  },

  _roleOptions(selected) {
    return (this.catalog?.presets || []).map((p) => (
      `<option value="${p.id}" ${p.id === selected ? 'selected' : ''}>${escHtml(p.label)} — ${escHtml(p.hint || '')}</option>`
    )).join('');
  },

  _readMatrix() {
    const matrix = {};
    document.querySelectorAll('#accessMatrix .access-level').forEach((el) => {
      matrix[el.dataset.area] = el.value;
    });
    return matrix;
  },

  applyPreset() {
    const role = document.getElementById('accessRole')?.value || 'qs';
    const matrix = (this.catalog?.matrices || {})[role] || {};
    document.querySelectorAll('#accessMatrix .access-level').forEach((el) => {
      if (matrix[el.dataset.area]) el.value = matrix[el.dataset.area];
      el.disabled = role === 'admin';
    });
  },

  openCreate() {
    this.editingId = null;
    this._showEditor({
      username: '',
      display_name: '',
      role: 'qs',
      is_active: true,
      permissions: (this.catalog?.matrices || {}).qs,
    }, true);
  },

  openEdit(id) {
    const row = this.users.find((u) => u.id === id);
    if (!row) return;
    this.editingId = id;
    const perms = row.permissions || (this.catalog?.matrices || {})[row.role] || {};
    this._showEditor(row, false, perms);
  },

  _showEditor(row, creating, perms) {
    const box = document.getElementById('accessEditor');
    if (!box) return;
    box.style.display = '';
    document.getElementById('accessEditorTitle').textContent = creating ? '新增帳號' : `編輯 ${row.username}`;
    const userEl = document.getElementById('accessUsername');
    userEl.value = row.username || '';
    userEl.disabled = !creating;
    document.getElementById('accessDisplayName').value = row.display_name || '';
    document.getElementById('accessPassword').value = '';
    document.getElementById('accessPasswordHint').textContent = creating ? '至少 6 個字元' : '留空表示不改密碼';
    document.getElementById('accessActive').checked = row.is_active !== false;
    const roleEl = document.getElementById('accessRole');
    roleEl.innerHTML = this._roleOptions(row.role || 'qs');
    document.getElementById('accessMatrix').innerHTML = this._matrixHtml(perms || row.permissions);
    this.applyPreset();
    if (!creating && row.role === 'custom' && row.permissions) {
      document.querySelectorAll('#accessMatrix .access-level').forEach((el) => {
        if (row.permissions[el.dataset.area]) el.value = row.permissions[el.dataset.area];
        el.disabled = false;
      });
    }
    box.scrollIntoView({ block: 'nearest' });
  },

  closeEditor() {
    const box = document.getElementById('accessEditor');
    if (box) box.style.display = 'none';
    this.editingId = null;
  },

  markCustom() {
    const roleEl = document.getElementById('accessRole');
    if (roleEl && roleEl.value !== 'custom') roleEl.value = 'custom';
    document.querySelectorAll('#accessMatrix .access-level').forEach((el) => {
      el.disabled = false;
    });
  },

  async save() {
    const creating = !this.editingId;
    const body = {
      username: document.getElementById('accessUsername').value.trim(),
      display_name: document.getElementById('accessDisplayName').value.trim(),
      role: document.getElementById('accessRole').value,
      password: document.getElementById('accessPassword').value,
      is_active: document.getElementById('accessActive').checked,
      permissions: this._readMatrix(),
    };
    try {
      if (creating) await api('POST', '/admin/users', body);
      else await api('PUT', `/admin/users/${this.editingId}`, body);
      toast('已儲存帳號權限', 'success');
      this.closeEditor();
      await this.load();
    } catch (e) {
      toast(e?.message || '儲存失敗', 'error');
    }
  },

  async remove(id) {
    const row = this.users.find((u) => u.id === id);
    if (!row) return;
    if (!confirm(`刪除帳號 ${row.username}？`)) return;
    try {
      await api('DELETE', `/admin/users/${id}`);
      toast('已刪除', 'success');
      if (this.editingId === id) this.closeEditor();
      await this.load();
    } catch (e) {
      toast(e?.message || '刪除失敗', 'error');
    }
  },
};
