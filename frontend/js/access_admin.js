/* access_admin.js — 帳號與權限、角色範本（管理員） */
const AccessAdmin = {
  catalog: null,
  users: [],
  templates: [],
  editingId: null,
  templateEditingId: null,

  async load() {
    const body = document.getElementById('accessUserBody');
    if (!body) return;
    if (typeof Auth !== 'undefined' && Auth.authRequired && !Auth.isAdmin()) {
      body.innerHTML = '<tr><td colspan="5"><div class="empty-state" style="padding:32px">需要管理員帳號</div></td></tr>';
      this._setTemplateMessage('需要管理員帳號');
      return;
    }
    body.innerHTML = '<tr><td colspan="5"><div class="empty-state" style="padding:32px">載入中…</div></td></tr>';
    this._setTemplateMessage('載入中…');
    try {
      this.catalog = await api('GET', '/admin/permission-catalog');
      this.users = await api('GET', '/admin/users') || [];
      this.templates = await api('GET', '/admin/role-templates') || [];
      this.render();
    } catch (e) {
      const msg = e?.message || '載入失敗';
      body.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:32px">${escHtml(msg)}</div></td></tr>`;
      this._setTemplateMessage(msg);
    }
  },

  _setTemplateMessage(text) {
    const body = document.getElementById('roleTemplateBody');
    if (!body) return;
    body.innerHTML = `<tr><td colspan="4"><div class="empty-state" style="padding:32px">${escHtml(text)}</div></td></tr>`;
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
    } else {
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
    }
    this.renderTemplates();
  },

  renderTemplates() {
    const body = document.getElementById('roleTemplateBody');
    if (!body) return;
    if (!this.templates.length) {
      this._setTemplateMessage('尚未建立角色範本');
      return;
    }
    body.innerHTML = this.templates.map((t) => {
      const names = (t.usernames || []).join('、');
      const action = t.locked ? '檢視' : '編輯';
      return `<tr>
        <td>${escHtml(t.label)}</td>
        <td>${escHtml(t.hint || '—')}</td>
        <td title="${escHtml(names)}">${t.user_count || 0} 人</td>
        <td><button type="button" class="btn btn-secondary btn-sm" onclick="AccessAdmin.openTemplate('${escHtml(t.id)}')">${action}</button></td>
      </tr>`;
    }).join('');
  },

  _matrixHtml(selected, cls) {
    const areas = this.catalog?.areas || [];
    const levels = this.catalog?.levels || [];
    return areas.map((area) => {
      const cur = selected?.[area.id] || 'none';
      const opts = levels.map((lv) => (
        `<option value="${lv.id}" ${lv.id === cur ? 'selected' : ''}>${escHtml(lv.label)}</option>`
      )).join('');
      return `<tr>
        <td>${escHtml(area.label)}<div class="form-hint">${escHtml(area.hint || '')}</div></td>
        <td><select class="form-input admin-input ${cls}" data-area="${escHtml(area.id)}">${opts}</select></td>
      </tr>`;
    }).join('');
  },

  _roleOptions(selected) {
    return (this.catalog?.presets || []).map((p) => (
      `<option value="${p.id}" ${p.id === selected ? 'selected' : ''}>${escHtml(p.label)} — ${escHtml(p.hint || '')}</option>`
    )).join('');
  },

  _readMatrix(selector) {
    const matrix = {};
    document.querySelectorAll(selector).forEach((el) => {
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
    this.closeTemplateEditor();
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
    this.closeTemplateEditor();
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
    document.getElementById('accessMatrix').innerHTML = this._matrixHtml(perms || row.permissions, 'access-level');
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
      permissions: this._readMatrix('#accessMatrix .access-level'),
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

  _templateById(id) {
    return this.templates.find((t) => t.id === id);
  },

  openCreateTemplate() {
    this.closeEditor();
    this.templateEditingId = null;
    this._showTemplateEditor({
      label: '',
      hint: '',
      matrix: (this.catalog?.matrices || {}).custom,
      locked: false,
      is_builtin: false,
      user_count: 0,
      usernames: [],
    }, true);
  },

  openTemplate(id) {
    const row = this._templateById(id);
    if (!row) return;
    this.closeEditor();
    this.templateEditingId = id;
    this._showTemplateEditor(row, false);
  },

  _showTemplateEditor(row, creating) {
    const box = document.getElementById('roleTemplateEditor');
    if (!box) return;
    box.style.display = '';
    const locked = !!row.locked;
    document.getElementById('roleTemplateTitle').textContent = creating
      ? '新增範本'
      : (locked ? `檢視 ${row.label}` : `編輯 ${row.label}`);
    const nameEl = document.getElementById('roleTemplateName');
    const hintEl = document.getElementById('roleTemplateHint');
    nameEl.value = row.label || '';
    hintEl.value = row.hint || '';
    nameEl.disabled = locked;
    hintEl.disabled = locked;
    const names = (row.usernames || []).join('、');
    const usersEl = document.getElementById('roleTemplateUsers');
    if (creating) {
      usersEl.textContent = '新範本預設全部不可見。儲存後可在帳號的角色範本選用。';
    } else if (locked) {
      usersEl.textContent = '管理員範本固定全部可編輯，不能改範圍。';
    } else if (row.user_count) {
      usersEl.textContent = `仍使用此範本：${names}`;
    } else {
      usersEl.textContent = '目前沒有帳號整套套用此範本。';
    }
    document.getElementById('roleTemplateMatrix').innerHTML = this._matrixHtml(row.matrix, 'role-template-level');
    document.querySelectorAll('#roleTemplateMatrix .role-template-level').forEach((el) => {
      el.disabled = locked;
    });
    const saveBtn = document.getElementById('roleTemplateSave');
    const restoreBtn = document.getElementById('roleTemplateRestore');
    const deleteBtn = document.getElementById('roleTemplateDelete');
    if (saveBtn) saveBtn.hidden = locked;
    if (restoreBtn) restoreBtn.hidden = creating || locked || !row.is_builtin;
    if (deleteBtn) deleteBtn.hidden = creating || locked || !!row.is_builtin;
    box.scrollIntoView({ block: 'nearest' });
  },

  closeTemplateEditor() {
    const box = document.getElementById('roleTemplateEditor');
    if (box) box.style.display = 'none';
    this.templateEditingId = null;
  },

  async saveTemplate() {
    const creating = !this.templateEditingId;
    const current = creating ? null : this._templateById(this.templateEditingId);
    if (current?.locked) return;
    const count = current?.user_count || 0;
    if (!creating) {
      const ok = confirm(`將更新仍使用此範本的 ${count} 個帳號。已自訂的帳號不會改。`);
      if (!ok) return;
    }
    const body = {
      label: document.getElementById('roleTemplateName').value.trim(),
      hint: document.getElementById('roleTemplateHint').value.trim(),
      permissions: this._readMatrix('#roleTemplateMatrix .role-template-level'),
    };
    try {
      if (creating) await api('POST', '/admin/role-templates', body);
      else await api('PUT', `/admin/role-templates/${this.templateEditingId}`, body);
      toast(creating ? '已新增範本' : '已儲存範本', 'success');
      this.closeTemplateEditor();
      await this.load();
    } catch (e) {
      toast(e?.message || '儲存失敗', 'error');
    }
  },

  async restoreTemplate() {
    const row = this._templateById(this.templateEditingId);
    if (!row || !row.is_builtin || row.locked) return;
    const count = row.user_count || 0;
    if (!confirm(`還原成系統預設，並更新仍使用此範本的 ${count} 個帳號？`)) return;
    try {
      await api('POST', `/admin/role-templates/${row.id}/restore`);
      toast('已還原預設', 'success');
      this.closeTemplateEditor();
      await this.load();
    } catch (e) {
      toast(e?.message || '還原失敗', 'error');
    }
  },

  async removeTemplate() {
    const row = this._templateById(this.templateEditingId);
    if (!row || row.is_builtin || row.locked) return;
    const count = row.user_count || 0;
    let path = `/admin/role-templates/${row.id}`;
    if (count) {
      if (!confirm(`仍有 ${count} 個帳號使用此範本。他們會改為自訂並保留目前權限，然後刪除範本。`)) return;
      path += '?detach=1';
    } else if (!confirm(`刪除範本「${row.label}」？`)) {
      return;
    }
    try {
      await api('DELETE', path);
      toast('已刪除範本', 'success');
      this.closeTemplateEditor();
      await this.load();
    } catch (e) {
      toast(e?.message || '刪除失敗', 'error');
    }
  },
};
