/* ─── main.js — 核心應用邏輯 ───────────────────────────── */
const API = `${window.location.origin}/api`;

function uploadUrl(filename) {
  if (!filename) return null;
  return `${window.location.origin}/api/uploads/${encodeURIComponent(filename)}`;
}

// ─── 工具函數 ──────────────────────────────────────────────
function fmt(num, decimals = 0) {
  if (num == null || num === '') return '—';
  const n = parseFloat(num);
  if (isNaN(n)) return '—';
  return 'HK$' + n.toLocaleString('en-HK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtDate(str) {
  if (!str) return '—';
  const d = new Date(str);
  if (isNaN(d)) return str;
  return d.toLocaleDateString('zh-HK', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

/** M-/SC-/O- 參考編號類型（對應 Excel 灰色提示） */
function refNoType(scNo) {
  const s = (scNo || '').toUpperCase().trim();
  if (/^M[-.]/.test(s) || s.startsWith('M')) return { label: '物料', badge: 'info' };
  if (/^SC[-.]/.test(s) || s.startsWith('SC')) return { label: '分判', badge: 'success' };
  if (/^O[-.]/.test(s) || s.startsWith('O')) return { label: '其他', badge: 'warning' };
  return { label: '', badge: 'muted' };
}

function fmtRefNo(scNo) {
  if (!scNo) return '—';
  const t = refNoType(scNo);
  const typeBadge = t.label
    ? `<span class="badge badge-${t.badge} ref-type-badge">${t.label}</span>`
    : '';
  return `<span class="ref-no-wrap"><span class="sc-no-chip">${scNo}</span>${typeBadge}</span>`;
}

function showLoading(text = '載入中...') {
  document.getElementById('loadingText').textContent = text;
  document.getElementById('loadingOverlay').classList.add('show');
}

function hideLoading() {
  document.getElementById('loadingOverlay').classList.remove('show');
}

function toast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(el);
  el.onclick = () => el.remove();
  setTimeout(() => el.remove(), 4000);
}

async function api(method, path, body) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(API + path, opts);
    const text = await r.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch (e) {
      throw new Error(r.ok ? '伺服器回應格式錯誤' : `伺服器錯誤 (${r.status})，請重新啟動系統後再試`);
    }
    if (!json.success) throw new Error(json.error || '操作失敗');
    return json.data;
  } catch (e) {
    toast(e.message, 'error');
    throw e;
  }
}

// ─── App 主控制器 ───────────────────────────────────────────
const App = {
  currentProject: null,
  projects: [],
  scList: [],

  async init() {
    await this.loadProjects();
    const saved = localStorage.getItem('qs_project_id');
    if (saved && this.projects.find(p => p.id == saved)) {
      await this.selectProject(saved);
    } else if (this.projects.length > 0) {
      await this.selectProject(this.projects[0].id);
    }
    this.navigate('dashboard');
  },

  async loadProjects() {
    this.projects = await api('GET', '/projects') || [];
    const sel = document.getElementById('projectSelect');
    sel.innerHTML = '<option value="">— 請選擇項目 —</option>';
    this.projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.project_code} ${p.project_name ? '— ' + p.project_name.substring(0, 30) : ''}`;
      sel.appendChild(opt);
    });
    // 更新項目管理頁
    Projects.render(this.projects);
  },

  async selectProject(id) {
    if (!id) {
      this.currentProject = null;
      this.scList = [];
      document.getElementById('projectSelect').value = '';
      document.getElementById('currentProjectBadge').style.display = 'none';
      document.getElementById('btnQuickAdd').style.display = 'none';
      return;
    }
    const fresh = await api('GET', `/projects/${id}`);
    if (!fresh) return;
    this.currentProject = fresh;
    const idx = this.projects.findIndex(p => p.id == id);
    if (idx >= 0) this.projects[idx] = fresh;

    localStorage.setItem('qs_project_id', id);
    document.getElementById('projectSelect').value = id;
    document.getElementById('currentProjectCode').textContent = this.currentProject.project_code;
    document.getElementById('currentProjectBadge').style.display = '';
    document.getElementById('btnQuickAdd').style.display = '';

    // 載入分判商
    this.scList = await api('GET', `/projects/${id}/subcontractors`) || [];

    // 刷新各頁面
    await Dashboard.load();
    Payments.populateScFilter();
    OCR.populateScOptions();
  },

  navigate(page) {
    // 隱藏所有頁面
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    // 顯示目標頁面
    document.getElementById(`page-${page}`)?.classList.add('active');
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');

    // 更新頁面標題
    const titles = {
      dashboard: ['儀表板', '項目財務總覽'],
      payments: ['付款記錄', '管理所有付款'],
      subcontractors: ['合同項目', 'M=物料 · SC=分判 · O=其他'],
      ocr: ['PDF OCR識別', '自動提取發票資料'],
      reports: ['財務報表', '付款統計分析'],
      projects: ['項目管理', '管理所有工程項目'],
      settings: ['系統設定', 'OCR與系統配置'],
    };
    const [title, sub] = titles[page] || ['', ''];
    document.getElementById('pageTitle').textContent = title;
    document.getElementById('pageSubtitle').textContent = sub;

    // 載入頁面數據
    if (page === 'payments') Payments.load();
    else if (page === 'subcontractors') SC.load();
    else if (page === 'reports') Reports.load();
    else if (page === 'settings') Settings.load();
  },

  quickAddPayment() {
    App.navigate('payments');
    setTimeout(() => Payments.openAdd(), 100);
  },

  importExcel() {
    document.getElementById('importModal').classList.add('open');
  },

  async onImportFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    document.getElementById('importStatus').style.display = '';
    const formData = new FormData();
    formData.append('file', file);

    try {
      const r = await fetch(`${API}/import/excel`, { method: 'POST', body: formData });
      const json = await r.json();
      if (json.success) {
        toast('Excel匯入成功！', 'success');
        document.getElementById('importModal').classList.remove('open');
        await App.loadProjects();
        if (json.data?.project_id) await App.selectProject(json.data.project_id);
      } else {
        toast('匯入失敗: ' + json.error, 'error');
      }
    } catch (e) {
      toast('匯入錯誤: ' + e.message, 'error');
    } finally {
      document.getElementById('importStatus').style.display = 'none';
      event.target.value = '';
    }
  },
};

// ─── Dashboard ─────────────────────────────────────────────
const Dashboard = {
  charts: {},

  async load() {
    const p = App.currentProject;
    if (!p) {
      document.getElementById('dashboardNoProject').style.display = '';
      document.getElementById('dashboardContent').style.display = 'none';
      return;
    }
    document.getElementById('dashboardNoProject').style.display = 'none';
    document.getElementById('dashboardContent').style.display = '';

    const summary = await api('GET', `/reports/summary/${p.id}`);
    if (!summary) return;

    // 統計卡片
    const totalPaid = summary.total_paid || 0;
    const totalRem = summary.total_remainder || 0;
    const contractAmt = summary.project?.contract_amount || p.contract_amount || 0;
    const progress = contractAmt > 0 ? ((totalPaid / contractAmt) * 100).toFixed(1) : '—';

    document.getElementById('dashContractAmt').textContent = fmt(contractAmt);
    document.getElementById('dashTotalPaid').textContent = fmt(totalPaid);
    document.getElementById('dashRemainder').textContent = fmt(totalRem);
    document.getElementById('dashProgress').textContent = progress !== '—' ? `${progress}%` : '—';

    // 付款記錄統計
    const payments = await api('GET', `/projects/${p.id}/payments`);
    document.getElementById('dashPayCount').textContent = payments?.length || 0;
    document.getElementById('payBadge').textContent = payments?.length || 0;
    document.getElementById('dashScCount').textContent = App.scList?.length || 0;

    // 最近記錄
    const recent = (payments || []).slice(0, 8);
    const tbody = document.getElementById('dashRecentPayments');
    if (recent.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state" style="padding:24px">暫無付款記錄</div></td></tr>`;
    } else {
      tbody.innerHTML = recent.map(r => `
        <tr onclick="App.navigate('payments')">
          <td class="td-muted">${fmtDate(r.invoice_date)}</td>
          <td>${fmtRefNo(r.sc_no)}</td>
          <td>${r.company_name_en || r.company_name_zh || '—'}</td>
          <td class="td-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.description || '—'}</td>
          <td class="td-amount positive">${fmt(r.paid_amount)}</td>
          <td class="td-mono td-muted">${r.invoice_no || '—'}</td>
        </tr>
      `).join('');
    }

    // 圖表
    this.renderCharts(summary.sc_stats || []);
  },

  renderCharts(scStats) {
    const stats = scStats.filter(s => s.contract_amount > 0).slice(0, 10);
    const labels = stats.map(s => s.sc_no || s.company_name_en?.substring(0, 15));
    const paid = stats.map(s => s.total_paid || 0);
    const remaining = stats.map(s => Math.max(0, (s.contract_amount || 0) - (s.total_paid || 0)));

    // 銷毀舊圖表
    Object.values(this.charts).forEach(c => c?.destroy());
    this.charts = {};

    // 橫條圖 - 付款狀況
    const ctx1 = document.getElementById('chartPayment').getContext('2d');
    this.charts.payment = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: '已付', data: paid, backgroundColor: '#10b981', borderRadius: 4 },
          { label: '未付', data: remaining, backgroundColor: '#374151', borderRadius: 4 },
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
        scales: {
          x: { stacked: true, ticks: { color: '#8b949e', font: { size: 10 }, callback: v => 'HK$' + (v/1000).toFixed(0) + 'K' }, grid: { color: '#21262d' } },
          y: { stacked: true, ticks: { color: '#e6edf3', font: { size: 11 } }, grid: { display: false } },
        }
      }
    });

    // 圓餅圖 - 類別分佈
    const categories = {};
    scStats.forEach(s => {
      const key = refNoType(s.sc_no).label || '其他';
      categories[key] = (categories[key] || 0) + (s.total_paid || 0);
    });

    const ctx2 = document.getElementById('chartCategory').getContext('2d');
    this.charts.category = new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: Object.keys(categories),
        datasets: [{
          data: Object.values(categories),
          backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
          borderWidth: 0, hoverOffset: 8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#8b949e', font: { size: 11 }, padding: 12 } },
          tooltip: {
            callbacks: { label: ctx => `${ctx.label}: HK$${ctx.raw.toLocaleString()}` }
          }
        }
      }
    });
  }
};

// ─── Settings ──────────────────────────────────────────────
const Settings = {
  async load() {
    const data = await api('GET', '/settings');
    if (data) {
      document.getElementById('settingApiKey').value = data.gemini_api_key || '';
      document.getElementById('settingQuarkId').value = data.quark_client_id || '';
      document.getElementById('settingQuarkKey').value = data.quark_client_key || '';
      document.getElementById('settingQuarkApiKey').value = data.quark_api_key || '';
      document.getElementById('settingOcrMode').value = data.ocr_mode || 'auto';
      document.getElementById('settingCompany').value = data.company_name || '';
    }
    // 顯示OCR引擎狀態
    try {
      const engRes = await api('GET', '/ocr/engines');
      const engines = engRes?.engines || [];
      const el = document.getElementById('engineStatus');
      if (el) {
        if (engines.length === 0) {
          el.innerHTML = '<span class="badge badge-danger">⚠️ 無可用OCR引擎</span>';
        } else {
          el.innerHTML = engines.map(e => {
            const icon = e.includes('夸克') ? '🔮' :
                         e.includes('RapidOCR') ? '🐉' :
                         e.includes('pdfplumber') || e.includes('PyMuPDF') ? '📝' :
                         e.includes('Gemini') ? '🤖' : '👁️';
            const cls  = e.includes('夸克') && !e.includes('未設定') ? 'success' :
                         e.includes('RapidOCR') ? 'success' :
                         e.includes('Gemini') && e.includes('已設定') ? 'info' :
                         e.includes('未設定') || e.includes('未安裝') ? 'warning' : 'muted';
            return `<span class="badge badge-${cls}" style="margin:2px 4px 2px 0">${icon} ${e}</span>`;
          }).join('');
        }
      }
    } catch (e) {}
  },
  async save() {
    await api('POST', '/settings', {
      gemini_api_key: document.getElementById('settingApiKey').value,
      quark_client_id: document.getElementById('settingQuarkId').value.trim(),
      quark_client_key: document.getElementById('settingQuarkKey').value.trim(),
      quark_api_key: document.getElementById('settingQuarkApiKey').value.trim(),
      ocr_mode: document.getElementById('settingOcrMode').value,
      company_name: document.getElementById('settingCompany').value,
    });
    toast('設定已儲存', 'success');
  }
};

// ─── 初始化 ────────────────────────────────────────────────
window.addEventListener('load', () => App.init());
