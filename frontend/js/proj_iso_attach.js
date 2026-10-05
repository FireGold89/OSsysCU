/* ─── proj_iso_attach.js — 項目表單附件 ↔ ISO 主合約槽位 ─────────── */
const ProjIsoAttach = {
  /** 上傳 category → ISO */
  UPLOAD_MAP: {
    attachment1_main_contract: { scope: 'main', slot: 'main_contract_loa' },
    attachment1_loa: { scope: 'main', slot: 'main_contract_loa' },
    attachment1_signoff: { scope: 'main', slot: 'tender_signoff' },
    attachment1_related: { scope: 'main', slot: 'other' },
  },

  SLOT_LABELS: {
    main_contract_loa: '主合約/LOA',
    tender_signoff: '投標會簽',
    mepo_tmc: '美博招投標會議記錄',
    hkmo_tmc: '港澳招投標會議記錄',
    other: '其他',
    partner_list: '合作伙伴名單',
    mou_nda: '合作備忘錄及保密協議',
    supplemental_optional: '補充/Optional',
  },

  /** 概覽／表單四欄對應的 ISO 槽位 + legacy category */
  VIEW_GROUPS: {
    mainLoa: {
      slots: ['main_contract_loa'],
      legacy: ['attachment1_main_contract', 'attachment1_loa'],
    },
    signoff: {
      slots: ['tender_signoff'],
      legacy: ['attachment1_signoff'],
    },
    email: {
      slots: ['mepo_tmc', 'hkmo_tmc'],
      legacy: ['attachment1_email'],
    },
    related: {
      slots: ['other', 'partner_list', 'mou_nda'],
      legacy: ['attachment1_related'],
    },
    sotSor: {
      slots: ['supplemental_optional'],
      legacy: ['attachment3_sot_sor'],
    },
  },

  uploadTarget(category) {
    return this.UPLOAD_MAP[category] || null;
  },

  _isoHasFile(file) {
    if (!file) return false;
    if (file.storage_type === 'link') return !!(file.external_url || '').trim();
    return !!(file.file_path || '').trim();
  },

  _isoToDoc(file, docCategory, slot) {
    const isLink = file.storage_type === 'link';
    return {
      id: `iso-${file.id}`,
      doc_category: docCategory,
      file_path: isLink ? null : file.file_path,
      original_filename: file.link_label || file.original_filename || this.SLOT_LABELS[slot] || slot,
      external_url: file.external_url,
      storage_type: file.storage_type || (isLink ? 'link' : 'file'),
      _iso: true,
      _isoId: file.id,
      _isoSlot: slot,
      _slotLabel: this.SLOT_LABELS[slot] || slot,
    };
  },

  /**
   * 合併 ISO main_files；項目表單／概覽預設 isoOnly（不上傳、只顯示 ISO）。
   */
  mergeDocs(legacyDocs, mainFiles, opts = {}) {
    const isoOnly = opts.isoOnly !== false;
    const main = mainFiles || {};
    const out = [];
    const seenPath = new Set();
    const pushIso = (slot, docCategory) => {
      const raw = main[slot];
      const files = Array.isArray(raw) ? raw : (raw ? [raw] : []);
      files.forEach((file) => {
        if (!this._isoHasFile(file)) return;
        const d = this._isoToDoc(file, docCategory, slot);
        if (d.file_path && seenPath.has(d.file_path)) return;
        if (d.file_path) seenPath.add(d.file_path);
        out.push(d);
      });
    };

    pushIso('main_contract_loa', 'attachment1_main_contract');
    pushIso('tender_signoff', 'attachment1_signoff');
    ['mepo_tmc', 'hkmo_tmc'].forEach((slot) => pushIso(slot, 'attachment1_email'));
    ['other', 'partner_list', 'mou_nda'].forEach((slot) => {
      pushIso(slot, 'attachment1_related');
    });
    pushIso('supplemental_optional', 'attachment3_sot_sor');

    if (!isoOnly) {
      (legacyDocs || []).forEach((d) => {
        const path = (d.file_path || '').trim();
        if (path && seenPath.has(path)) return;
        out.push({ ...d, _iso: false });
      });
    } else {
      (legacyDocs || []).forEach((d) => {
        if ((d.doc_category || '').trim() !== 'attachment3_sot_sor') return;
        const path = (d.file_path || '').trim();
        if (path && seenPath.has(path)) return;
        out.push({ ...d, _iso: false });
      });
    }
    return out;
  },

  docsForGroup(mergedDocs, groupKey) {
    const g = this.VIEW_GROUPS[groupKey];
    if (!g) return [];
    return (mergedDocs || []).filter((d) =>
      g.legacy.includes(d.doc_category) || (d._isoSlot && g.slots.includes(d._isoSlot)),
    );
  },

  groupHasAny(mergedDocs, groupKey) {
    return this.docsForGroup(mergedDocs, groupKey).length > 0;
  },

  anyAttachment(mergedDocs) {
    return Object.keys(this.VIEW_GROUPS).some((k) => this.groupHasAny(mergedDocs, k));
  },

  displayName(doc) {
    if (doc._iso && doc._slotLabel && doc.doc_category === 'attachment1_email') {
      return `${doc._slotLabel} · ${doc.original_filename || '附件'}`;
    }
    if (doc._iso && doc._slotLabel && doc.doc_category === 'attachment1_related' && doc._isoSlot !== 'other') {
      return `${doc._slotLabel} · ${doc.original_filename || '附件'}`;
    }
    return doc.original_filename || doc.file_path || '附件';
  },

  /** 唯讀 HTML（概覽 · 僅萬字夾圖示，檔名在 title） */
  readonlyHtml(docs) {
    if (!docs.length) return '—';
    return `<span class="proj-doc-clip-row">${docs.map((d) => this._clipControl(d)).join('')}</span>`;
  },

  _clipControl(d) {
    const name = escHtml(this.displayName(d));
    const tip = ` title="${name}" aria-label="${name}"`;
    if (d.storage_type === 'link') {
      const href = IsoDocs?._safeHref?.(d.external_url) || d.external_url;
      if (href) {
        return `<a class="proj-doc-clip-btn" href="${escHtml(href)}" target="_blank" rel="noopener noreferrer"${tip}>📎</a>`;
      }
      return `<span class="proj-doc-clip-btn is-disabled"${tip}>📎</span>`;
    }
    const path = (d.file_path || '').replace(/"/g, '&quot;');
    if (!path) return `<span class="proj-doc-clip-btn is-disabled"${tip}>📎</span>`;
    return `<button type="button" class="proj-doc-clip-btn btn-view-pdf" data-pdf-path="${path}"
      data-doc-title="${name}"${tip}>📎</button>`;
  },

  /** 項目表單：唯讀預覽（無刪除 · 同概覽萬字夾） */
  modalListHtml(docs) {
    if (!docs.length) return '<span class="proj-iso-empty">—</span>';
    return `<span class="proj-doc-clip-row">${docs.map((d) => this._clipControl(d)).join('')}</span>`;
  },

  openIsoDocsHint() {
    toast('附件請於 ISO 文件登記上傳', 'info');
    if (App.currentProject?.id) {
      App.navigate('iso-docs');
      return;
    }
    const pid = document.getElementById('projModalId')?.value;
    if (pid) {
      Projects.closeModal();
      App.selectProject(pid).then(() => App.navigate('iso-docs'));
    }
  },
};
