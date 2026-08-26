/* col_picker.js — 表格欄位顯示設定（localStorage 共用） */
const ColPicker = {
  attach(host, config) {
    const {
      columnsKey,
      storageKey,
      tableSelector,
      wrapId,
      panelId,
      hostName,
    } = config;

    const getColumns = () => host[columnsKey] || [];

    host._colPickerBound = false;

    host._loadColPrefs = function _loadColPrefs() {
      try {
        const raw = localStorage.getItem(storageKey);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : null;
      } catch (e) {
        return null;
      }
    };

    host._saveColPrefs = function _saveColPrefs() {
      try {
        localStorage.setItem(storageKey, JSON.stringify(host._visibleCols));
      } catch (e) {}
    };

    host._initColPrefs = function _initColPrefs() {
      const columns = getColumns();
      const saved = host._loadColPrefs();
      const all = columns.map(c => c.id);
      const locked = columns.filter(c => c.locked).map(c => c.id);
      if (saved && saved.length) {
        const valid = saved.filter(id => all.includes(id));
        locked.forEach(id => { if (!valid.includes(id)) valid.push(id); });
        host._visibleCols = valid.length ? valid : [...all];
      } else {
        host._visibleCols = [...all];
      }
    };

    host.isColVisible = function isColVisible(id) {
      if (!host._visibleCols) host._initColPrefs();
      return host._visibleCols.includes(id);
    };

    host._visibleColCount = function _visibleColCount() {
      return getColumns().filter(c => host.isColVisible(c.id)).length;
    };

    host.applyColVisibility = function applyColVisibility() {
      const table = document.querySelector(tableSelector);
      if (!table) return;
      getColumns().forEach(col => {
        const show = host.isColVisible(col.id);
        table.querySelectorAll(`[data-col="${col.id}"]`).forEach(el => {
          el.classList.toggle('col-hidden', !show);
        });
      });
    };

    host.toggleColPicker = function toggleColPicker(ev) {
      ev?.stopPropagation();
      const panel = document.getElementById(panelId);
      if (!panel) return;
      const opening = panel.hidden;
      panel.hidden = !opening;
      if (opening) {
        host._renderColPicker();
        if (!host._colPickerBound) {
          host._colPickerBound = true;
          document.addEventListener('click', (e) => {
            const wrap = document.getElementById(wrapId);
            if (wrap && !wrap.contains(e.target)) panel.hidden = true;
          });
        }
      }
    };

    host._renderColPicker = function _renderColPicker() {
      const panel = document.getElementById(panelId);
      if (!panel) return;
      const items = getColumns().filter(c => !c.locked).map(col => {
        const checked = host.isColVisible(col.id) ? 'checked' : '';
        return `<label><input type="checkbox" ${checked} onchange="${hostName}.setColVisible('${col.id}', this.checked)"> ${col.label}</label>`;
      }).join('');
      panel.innerHTML = `
        <div class="col-picker-title">顯示欄位</div>
        ${items}
        <button type="button" class="btn btn-secondary btn-sm col-picker-reset" onclick="${hostName}.resetCols()">重設全部</button>`;
    };

    host.setColVisible = function setColVisible(id, visible) {
      if (!host._visibleCols) host._initColPrefs();
      const col = getColumns().find(c => c.id === id);
      if (!col || col.locked) return;
      const next = new Set(host._visibleCols);
      if (visible) next.add(id);
      else next.delete(id);
      const togglable = getColumns().filter(c => !c.locked);
      const visibleCount = togglable.filter(c => next.has(c.id)).length;
      if (visibleCount < 1) {
        toast('至少保留一欄', 'warning');
        host._renderColPicker();
        return;
      }
      getColumns().filter(c => c.locked).forEach(c => next.add(c.id));
      host._visibleCols = [...next];
      host._saveColPrefs();
      host.applyColVisibility();
      host._renderColPicker();
    };

    host.resetCols = function resetCols() {
      host._visibleCols = getColumns().map(c => c.id);
      host._saveColPrefs();
      host.applyColVisibility();
      host._renderColPicker();
    };

    return host;
  },
};
