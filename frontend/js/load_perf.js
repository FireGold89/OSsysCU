/* load_perf.js — 首屏／換項目 API 載入優化
 *
 * - fetchDeduped：進行中請求合併 + session 快取
 * - fetchDashboardOverview：單次 bundle（ISO · 文件 · FAC · summary）
 * - handleApiSuccess：寫入 API 成功後自動 invalidate（掛在 main.js api()）
 * - notifyProjectMutated：FormData 上傳等非 api() 路徑手動通知
 */
const LoadPerf = {
  SUMMARY_SLOT: 'reports-summary',
  BUNDLE_SLOT: 'dashboard-overview',
  DEFAULT_IDLE_TIMEOUT_MS: 2800,

  _MUTATION_PATH_RE: [
    /^\/payments(\/|$)/,
    /^\/interim-payments(\/|$)/,
    /^\/subcontractors(\/|$)/,
    /^\/sc-vo-records(\/|$)/,
    /^\/projects\/\d+\/(main-con-fac|iso-documents|iso-meta|documents|sc-vo-records|subcontractors)/,
    /^\/iso-documents\/\d+$/,
    /^\/import\/(payment|excel)/,
  ],

  _slots: Object.create(null),

  _ensureSlot(key) {
    if (!this._slots[key]) {
      this._slots[key] = { id: null, data: null, promise: null };
    }
    return this._slots[key];
  },

  /** @param {string} key @param {string|number|null} id 傳 null 表示整格清空 */
  invalidate(key, id = null) {
    const slot = this._slots[key];
    if (!slot) return;
    if (id == null || String(slot.id) === String(id)) {
      this._slots[key] = { id: null, data: null, promise: null };
    }
  },

  /** 換項目、寫入後：清 summary + 概覽 bundle */
  invalidateProjectCaches(projectId) {
    this.invalidate(this.SUMMARY_SLOT, projectId ?? null);
    this.invalidate(this.BUNDLE_SLOT, projectId ?? null);
  },

  /** @deprecated 别名；請用 invalidateProjectCaches */
  invalidateProjectSummary(projectId) {
    this.invalidateProjectCaches(projectId);
  },

  notifyProjectMutated(projectId) {
    const pid = Number(projectId);
    if (pid) this.invalidateProjectCaches(pid);
  },

  seedProjectSummary(projectId, summaryData) {
    if (!summaryData) return;
    const pid = Number(projectId);
    if (!pid || typeof App === 'undefined' || App.currentProject?.id !== pid) return;
    const slot = this._ensureSlot(this.SUMMARY_SLOT);
    slot.id = String(pid);
    slot.data = summaryData;
  },

  /**
   * @param {() => Promise<*>} fetchFn
   * @param {{ shouldCommit?: (id: string, data: *) => boolean }} opts
   */
  fetchDeduped(key, id, fetchFn, { shouldCommit } = {}) {
    const sid = id == null || id === '' ? null : String(id);
    if (sid == null) return Promise.resolve(null);

    const slot = this._ensureSlot(key);
    if (String(slot.id) === sid && slot.data != null) return Promise.resolve(slot.data);
    if (String(slot.id) === sid && slot.promise) return slot.promise;

    const commit = shouldCommit || (() => true);
    slot.id = sid;
    slot.data = null;
    slot.promise = Promise.resolve()
      .then(() => fetchFn())
      .then((data) => {
        if (String(slot.id) === sid && commit(sid, data)) slot.data = data;
        return data;
      })
      .catch((err) => {
        if (String(slot.id) === sid) slot.promise = null;
        throw err;
      })
      .finally(() => {
        if (String(slot.id) === sid) slot.promise = null;
      });
    return slot.promise;
  },

  _isCurrentProject(pid) {
    return typeof App !== 'undefined' && App.currentProject?.id === Number(pid);
  },

  fetchProjectSummary(projectId, { silent = true } = {}) {
    const pid = Number(projectId);
    if (!pid) return Promise.resolve(null);
    return this.fetchDeduped(
      this.SUMMARY_SLOT,
      pid,
      () => api('GET', `/reports/summary/${pid}`, null, { silent }),
      { shouldCommit: (sid) => this._isCurrentProject(sid) },
    );
  },

  fetchDashboardOverview(projectId, { silent = true } = {}) {
    const pid = Number(projectId);
    if (!pid) return Promise.resolve(null);
    return this.fetchDeduped(
      this.BUNDLE_SLOT,
      pid,
      () => api('GET', `/projects/${pid}/dashboard-overview`, null, { silent }),
      { shouldCommit: (sid) => this._isCurrentProject(sid) },
    ).then((bundle) => {
      if (bundle?.report_summary) this.seedProjectSummary(pid, bundle.report_summary);
      return bundle;
    });
  },

  _projectIdFromMutation(path, body, data) {
    const p = (path || '').split('?')[0];
    let m = p.match(/^\/projects\/(\d+)/);
    if (m) return Number(m[1]);
    if (body?.project_id != null) return Number(body.project_id);

    if (data?.summary?.project_id != null) return Number(data.summary.project_id);
    if (data?.project_id != null) return Number(data.project_id);

    const affects = this._MUTATION_PATH_RE.some((re) => re.test(p));
    if (affects && typeof App !== 'undefined' && App.currentProject?.id) {
      return App.currentProject.id;
    }
    return null;
  },

  /** api() 成功回傳後呼叫（非 GET） */
  handleApiSuccess(method, path, body, data) {
    const m = (method || 'GET').toUpperCase();
    if (m === 'GET' || m === 'HEAD') return;
    const pid = this._projectIdFromMutation(path, body, data);
    if (pid) this.invalidateProjectCaches(pid);
  },

  scheduleIdle(fn, timeoutMs = this.DEFAULT_IDLE_TIMEOUT_MS) {
    const run = () => {
      try { fn(); } catch (_) { /* ignore */ }
    };
    if (typeof requestIdleCallback === 'function') {
      requestIdleCallback(run, { timeout: timeoutMs });
    } else {
      setTimeout(run, Math.min(1200, timeoutMs));
    }
  },

  scheduleProjectSwitchPreloads({ switchSeq, activePage, preloadProjectLens }) {
    const loadLens = preloadProjectLens
      || ((seq) => {
        if (typeof Dashboard !== 'undefined') Dashboard.load(seq).catch(() => {});
      });
    this.scheduleIdle(() => {
      if (typeof App === 'undefined') return;
      if (switchSeq !== App._projectSwitchSeq || !App.currentProject?.id) return;
      if (activePage === 'project-lens') return;
      loadLens(switchSeq);
    });
  },

  getCachedSubcontractors(projectId, scList) {
    const pid = Number(projectId);
    if (!pid || !Array.isArray(scList) || !scList.length) return null;
    if (typeof App !== 'undefined' && App.currentProject?.id == pid) return scList;
    return null;
  },
};
