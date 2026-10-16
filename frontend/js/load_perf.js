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
  SC_VO_TEMPLATES_SLOT: 'sc-vo-templates',
  SC_VO_TEMPLATES_MANAGE_SLOT: 'sc-vo-templates-manage',
  GLOBAL_CACHE_ID: 'global',
  DEFAULT_IDLE_TIMEOUT_MS: 2800,
  /** 輕量全域 GET（範本目錄等）逾時 */
  LIGHT_GET_TIMEOUT_MS: 15000,
  AUTH_ME_TIMEOUT_MS: 18000,
  INIT_BOOT_TIMEOUT_MS: 25000,
  AUTO_PROJECT_LOAD_TIMEOUT_MS: 35000,
  /** 切換項目整段流程逾時（避免 Chrome 等瀏覽器 hung fetch 一直顯示載入中） */
  PROJECT_SWITCH_TIMEOUT_MS: 28000,
  /** dashboard-overview / summary 單次請求逾時 */
  OVERVIEW_FETCH_TIMEOUT_MS: 22000,
  /** 主合約／分判 FAC PDF 生成逾時 */
  PDF_FETCH_TIMEOUT_MS: 90000,
  /** 試跑：切項目後勿 idle 預載「項目視角」(避免多打 summary + portfolio) */
  IDLE_PRELOAD_PROJECT_LENS: false,

  _pdfAbortController: null,

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

  withTimeout(promise, ms, message = '載入逾時') {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const err = new Error(message);
        err.code = 'LOAD_TIMEOUT';
        reject(err);
      }, ms);
      Promise.resolve(promise).then(
        (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        (err) => {
          clearTimeout(timer);
          reject(err);
        },
      );
    });
  },

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

  _apiGet(path, { silent = true, timeoutMs = 0 } = {}) {
    const run = () => api('GET', path, null, { silent, useProjectSwitchSignal: true });
    if (timeoutMs > 0) {
      return this.withTimeout(run(), timeoutMs, '載入逾時').catch((err) => {
        if (err.code === 'LOAD_TIMEOUT') return null;
        throw err;
      });
    }
    return run();
  },

  fetchProjectSummary(projectId, { silent = true } = {}) {
    const pid = Number(projectId);
    if (!pid) return Promise.resolve(null);
    return this.fetchDeduped(
      this.SUMMARY_SLOT,
      pid,
      () => this._apiGet(`/reports/summary/${pid}`, {
        silent,
        timeoutMs: this.OVERVIEW_FETCH_TIMEOUT_MS,
      }),
      { shouldCommit: (sid) => this._isCurrentProject(sid) },
    );
  },

  fetchDashboardOverview(projectId, { silent = true } = {}) {
    const pid = Number(projectId);
    if (!pid) return Promise.resolve(null);
    return this.fetchDeduped(
      this.BUNDLE_SLOT,
      pid,
      () => this._apiGet(`/projects/${pid}/dashboard-overview`, {
        silent,
        timeoutMs: this.OVERVIEW_FETCH_TIMEOUT_MS,
      }),
      { shouldCommit: (sid) => this._isCurrentProject(sid) },
    ).then((bundle) => {
      if (bundle?.report_summary) this.seedProjectSummary(pid, bundle.report_summary);
      return bundle;
    });
  },

  fetchScVoTemplates({ manage = false, silent = true } = {}) {
    const slot = manage ? this.SC_VO_TEMPLATES_MANAGE_SLOT : this.SC_VO_TEMPLATES_SLOT;
    const path = manage ? '/sc-vo-templates?manage=1' : '/sc-vo-templates';
    return this.fetchDeduped(
      slot,
      this.GLOBAL_CACHE_ID,
      () => this.withTimeout(
        api('GET', path, null, { silent }),
        this.LIGHT_GET_TIMEOUT_MS,
        '載入逾時',
      ),
      { shouldCommit: (sid, data) => sid === this.GLOBAL_CACHE_ID && Array.isArray(data) },
    ).then((rows) => rows || []);
  },

  invalidateScVoTemplateCaches() {
    this.invalidate(this.SC_VO_TEMPLATES_SLOT, this.GLOBAL_CACHE_ID);
    this.invalidate(this.SC_VO_TEMPLATES_MANAGE_SLOT, this.GLOBAL_CACHE_ID);
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
    const p = (path || '').split('?')[0];
    if (/^\/sc-vo-templates(\/|$)/.test(p)) {
      this.invalidateScVoTemplateCaches();
    }
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
    if (!this.IDLE_PRELOAD_PROJECT_LENS && !preloadProjectLens) return;
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

  abortPdfFetch() {
    if (!this._pdfAbortController) return;
    try {
      this._pdfAbortController.abort();
    } catch (_) { /* ignore */ }
    this._pdfAbortController = null;
  },

  /**
   * PDF 預覽／下載用 fetch（含逾時；新請求會 abort 上一個 PDF fetch）
   * @returns {Promise<Response>}
   */
  async fetchPdf(url, { timeoutMs } = {}) {
    this.abortPdfFetch();
    const controller = new AbortController();
    this._pdfAbortController = controller;
    const ms = timeoutMs > 0 ? timeoutMs : this.PDF_FETCH_TIMEOUT_MS;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, ms);
    try {
      const r = await fetch(url, { credentials: 'include', signal: controller.signal });
      return r;
    } catch (e) {
      if (e?.name === 'AbortError') {
        throw new Error(timedOut ? 'PDF 生成逾時，請稍後再試' : 'PDF 載入已取消');
      }
      throw e;
    } finally {
      clearTimeout(timer);
      if (this._pdfAbortController === controller) this._pdfAbortController = null;
    }
  },

  getCachedSubcontractors(projectId, scList) {
    const pid = Number(projectId);
    if (!pid || !Array.isArray(scList) || !scList.length) return null;
    if (typeof App !== 'undefined' && App.currentProject?.id == pid) return scList;
    return null;
  },
};
