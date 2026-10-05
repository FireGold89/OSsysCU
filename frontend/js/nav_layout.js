/* ─── nav_layout.js — 主要功能拖放排序（編輯模式 · 側欄 + 項目視角） ── */
const NavLayout = {
  STORAGE_KEY: 'qs_main_nav_order_v1',
  editMode: false,
  _launcherGridBound: false,

  catalog: {
    dashboard: { icon: '📊', label: '項目概覽', needsProject: false },
    'iso-docs': { icon: '📑', label: 'ISO 文件', needsProject: true },
    payments: { icon: '💰', label: '分判付款登記', needsProject: true, badgeId: 'payBadge' },
    'sc-vo-reg': { icon: '📋', label: '變更以及扣款登記', needsProject: true },
    'ip-period': { icon: '🏗️', label: '糧期狀況', needsProject: true },
    'main-con-fac': { icon: '📑', label: '主合約最終結算', needsProject: true },
    'sc-fac': { icon: '📋', label: '分判最終結算', needsProject: true },
    reports: { icon: '📈', label: '財務報表', needsProject: true },
  },

  defaultOrder() {
    return Object.keys(this.catalog);
  },

  getOrder() {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      if (!raw) return this.defaultOrder();
      const ids = JSON.parse(raw);
      if (!Array.isArray(ids)) return this.defaultOrder();
      const known = new Set(this.defaultOrder());
      const out = ids.filter((id) => known.has(id));
      this.defaultOrder().forEach((id) => {
        if (!out.includes(id)) out.push(id);
      });
      return out;
    } catch {
      return this.defaultOrder();
    }
  },

  saveOrder(ids) {
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(ids));
  },

  orderFromContainer(container) {
    return [...container.querySelectorAll('.nav-item[data-page]')]
      .map((el) => el.getAttribute('data-page'))
      .filter(Boolean);
  },

  init() {
    const main = document.getElementById('navSortableMain');
    if (!main) return;
    this.applySidebarOrder(main);
    this._bindSidebarNav(main);
    this._bindSidebarDrag(main);
    this._bindLauncherGridOnce();
    this.setEditMode(false, { silent: true });
    this.renderDashboardLauncher();
    this._bindEditControls();
  },

  _bindEditControls() {
    document.getElementById('navLayoutEditMain')?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.enterEdit();
    });
    document.getElementById('dashNavLayoutEdit')?.addEventListener('click', (e) => {
      e.preventDefault();
      this.enterEdit();
    });
    document.getElementById('navLayoutDoneMain')?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.finishEdit();
    });
    document.getElementById('dashNavLayoutDone')?.addEventListener('click', (e) => {
      e.preventDefault();
      this.finishEdit();
    });
    document.getElementById('navLayoutResetMain')?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.reset();
    });
    document.getElementById('dashNavLayoutReset')?.addEventListener('click', (e) => {
      e.preventDefault();
      this.reset();
    });
  },

  enterEdit() {
    if (htmlSidebarCollapsed()) {
      toast('請先展開側欄再編輯順序', 'warning');
      return;
    }
    this.setEditMode(true);
    toast('拖曳調整順序，完成後按「完成」固定', 'info');
  },

  finishEdit() {
    const main = document.getElementById('navSortableMain');
    const grid = document.getElementById('dashNavLauncherGrid');
    if (grid?.querySelector('.nav-launcher-tile')) {
      const ids = [...grid.querySelectorAll('.nav-launcher-tile[data-page]')]
        .map((el) => el.getAttribute('data-page'));
      this.saveOrder(ids);
      if (main) this.applySidebarOrder(main);
    } else if (main) {
      this.saveOrder(this.orderFromContainer(main));
      this.renderDashboardLauncher();
    }
    this.setEditMode(false);
    toast('主要功能順序已固定', 'success');
  },

  setEditMode(editing, opts = {}) {
    this.editMode = !!editing;
    document.documentElement.classList.toggle('nav-layout-editing', this.editMode);
    this._applyDraggableState();
    this._syncEditButtons();
    this._syncHints();
    if (!opts.silent && !this.editMode) {
      this.renderDashboardLauncher();
    }
  },

  _syncEditButtons() {
    const show = (id, on) => {
      const el = document.getElementById(id);
      if (el) el.hidden = !on;
    };
    show('navLayoutEditMain', !this.editMode);
    show('dashNavLayoutEdit', !this.editMode);
    show('navLayoutDoneMain', this.editMode);
    show('dashNavLayoutDone', this.editMode);
    show('navLayoutResetMain', this.editMode);
    show('dashNavLayoutReset', this.editMode);
  },

  _syncHints() {
    const sub = document.querySelector('.nav-launcher-sub');
    if (sub) {
      sub.textContent = this.editMode
        ? '編輯中：拖曳卡片排序（左側選單同步）'
        : '點擊進入模組；按「編輯」可調整順序';
    }
  },

  reset() {
    if (!this.editMode) return;
    this.saveOrder(this.defaultOrder());
    const main = document.getElementById('navSortableMain');
    if (main) this.applySidebarOrder(main);
    this.renderDashboardLauncher();
    toast('已還原預設順序（尚未完成前可繼續調整）', 'success');
  },

  applySidebarOrder(container) {
    const order = this.getOrder();
    const byPage = {};
    container.querySelectorAll('.nav-item[data-page]').forEach((el) => {
      byPage[el.getAttribute('data-page')] = el;
    });
    order.forEach((id) => {
      if (byPage[id]) container.appendChild(byPage[id]);
    });
  },

  _applyDraggableState() {
    const collapsed = htmlSidebarCollapsed();
    const allow = this.editMode && !collapsed;
    document.querySelectorAll('#navSortableMain .nav-item[data-page]').forEach((el) => {
      el.draggable = allow;
    });
    document.querySelectorAll('#dashNavLauncherGrid .nav-launcher-tile').forEach((el) => {
      el.draggable = this.editMode;
    });
  },

  _bindSidebarNav(container) {
    container.addEventListener('click', (e) => {
      if (this.editMode) return;
      if (e.target.closest('.nav-drag-handle')) return;
      const item = e.target.closest('.nav-item[data-page]');
      if (!item) return;
      App.navigate(item.getAttribute('data-page'));
    });
  },

  _bindSidebarDrag(container) {
    let dragEl = null;

    container.addEventListener('dragstart', (e) => {
      if (!this.editMode) {
        e.preventDefault();
        return;
      }
      const item = e.target.closest('.nav-item[data-page]');
      if (!item || htmlSidebarCollapsed()) {
        e.preventDefault();
        return;
      }
      dragEl = item;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', item.getAttribute('data-page') || '');
      item.classList.add('nav-dragging');
    });

    container.addEventListener('dragover', (e) => {
      if (!dragEl || !this.editMode) return;
      e.preventDefault();
      const over = e.target.closest('.nav-item[data-page]');
      if (!over || over === dragEl) return;
      over.classList.add('nav-drop-target');
      const rect = over.getBoundingClientRect();
      const after = e.clientY > rect.top + rect.height / 2;
      container.insertBefore(dragEl, after ? over.nextSibling : over);
    });

    container.addEventListener('dragleave', (e) => {
      e.target.closest('.nav-item[data-page]')?.classList.remove('nav-drop-target');
    });

    container.addEventListener('drop', (e) => {
      e.preventDefault();
      container.querySelectorAll('.nav-drop-target').forEach((el) => el.classList.remove('nav-drop-target'));
    });

    container.addEventListener('dragend', () => {
      dragEl?.classList.remove('nav-dragging');
      container.querySelectorAll('.nav-drop-target').forEach((el) => el.classList.remove('nav-drop-target'));
      dragEl = null;
      if (!this.editMode) return;
      const grid = document.getElementById('dashNavLauncherGrid');
      if (grid?.children.length) {
        this.renderDashboardLauncher();
      }
    });
  },

  renderDashboardLauncher() {
    const grid = document.getElementById('dashNavLauncherGrid');
    if (!grid) return;

    const order = this.getOrder();
    const hasProject = !!App.currentProject;

    grid.innerHTML = order.map((id) => {
      const meta = this.catalog[id];
      if (!meta) return '';
      const disabled = !this.editMode && meta.needsProject && !hasProject;
      const badge = meta.badgeId
        ? `<span class="nav-launcher-badge" id="dashLauncher_${meta.badgeId}"></span>`
        : '';
      return `<button type="button" class="nav-launcher-tile${disabled ? ' is-disabled' : ''}"
        data-page="${escHtml(id)}" draggable="false" title="${escHtml(meta.label)}">
        <span class="nav-launcher-grip" aria-hidden="true">⠿</span>
        <span class="nav-launcher-icon">${meta.icon}</span>
        <span class="nav-launcher-label">${escHtml(meta.label)}</span>
        ${badge}
      </button>`;
    }).join('');

    this._syncLauncherBadges();
    this._applyDraggableState();
  },

  _syncLauncherBadges() {
    const paySrc = document.getElementById('payBadge');
    const payDst = document.getElementById('dashLauncher_payBadge');
    if (paySrc && payDst) {
      payDst.textContent = paySrc.textContent || '';
      payDst.style.display = paySrc.style.display;
    }
  },

  refreshBadges() {
    this._syncLauncherBadges();
  },

  onSidebarCollapse(collapsed) {
    if (collapsed && this.editMode) {
      this.finishEdit();
      return;
    }
    this._applyDraggableState();
  },

  _bindLauncherGridOnce() {
    if (this._launcherGridBound) return;
    const grid = document.getElementById('dashNavLauncherGrid');
    if (!grid) return;
    this._launcherGridBound = true;
    let dragEl = null;

    grid.addEventListener('click', (e) => {
      if (this.editMode) return;
      const tile = e.target.closest('.nav-launcher-tile[data-page]');
      if (!tile) return;
      const page = tile.getAttribute('data-page');
      const meta = this.catalog[page];
      if (meta?.needsProject && !App.currentProject) {
        toast('請先選擇項目', 'warning');
        return;
      }
      App.navigate(page);
    });

    grid.addEventListener('dragstart', (e) => {
      if (!this.editMode) {
        e.preventDefault();
        return;
      }
      const tile = e.target.closest('.nav-launcher-tile');
      if (!tile) {
        e.preventDefault();
        return;
      }
      dragEl = tile;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', tile.getAttribute('data-page') || '');
      tile.classList.add('nav-dragging');
    });

    grid.addEventListener('dragover', (e) => {
      if (!dragEl || !this.editMode) return;
      e.preventDefault();
      const over = e.target.closest('.nav-launcher-tile');
      if (!over || over === dragEl) return;
      const rect = over.getBoundingClientRect();
      const after = e.clientX > rect.left + rect.width / 2;
      grid.insertBefore(dragEl, after ? over.nextSibling : over);
    });

    grid.addEventListener('dragend', () => {
      dragEl?.classList.remove('nav-dragging');
      dragEl = null;
      if (!this.editMode) return;
      const main = document.getElementById('navSortableMain');
      if (main) {
        const order = [...grid.querySelectorAll('.nav-launcher-tile[data-page]')]
          .map((el) => el.getAttribute('data-page'));
        const byPage = {};
        main.querySelectorAll('.nav-item[data-page]').forEach((el) => {
          byPage[el.getAttribute('data-page')] = el;
        });
        order.forEach((id) => {
          if (byPage[id]) main.appendChild(byPage[id]);
        });
      }
    });
  },
};

function htmlSidebarCollapsed() {
  return document.documentElement.classList.contains('sidebar-collapsed');
}
