const treeEl = document.getElementById('tree');
const viewerEl = document.getElementById('viewer');
const crumbEl = document.getElementById('crumb');
const dlEl = document.getElementById('dl');
const revealBtn = document.getElementById('reveal');
const filterEl = document.getElementById('filter');
const pickBtn = document.getElementById('pick-root');
const rootPathEl = document.getElementById('root-path');
const preconvertEl = document.getElementById('preconvert');
const starBtn = document.getElementById('star');
const tagBtn = document.getElementById('tag-btn');
const noteBtn = document.getElementById('note-btn');
const tagCountEl = document.getElementById('tag-count');
const noteDotEl = document.getElementById('note-dot');
const tagPop = document.getElementById('tag-popover');
const notePop = document.getElementById('note-popover');
const tagChipsEl = document.getElementById('tag-chips');
const addTagBtn = document.getElementById('add-tag');
const notesEl = document.getElementById('notes');
const noteHintEl = document.getElementById('note-hint');

let currentPath = null;
// annotations cache for current root: { files: {path:{...}}, tag_palette: [...] }
let annoCache = { files: {}, tag_palette: [] };
// Paths flagged as scanned (image-only) PDFs.
let scannedPaths = new Set();
let currentView = 'all'; // all | starred | tagged
let currentRootKey = '';  // used for namespacing localStorage

const LS = {
  openDirs: () => `browse:openDirs:${currentRootKey}`,
  sidebarW: () => `browse:sidebarW`,
};

const ICON = { '.pdf':'📕','.md':'📝','.txt':'📄','.doc':'📘','.docx':'📘',
  '.xls':'📊','.xlsx':'📊','.ppt':'📙','.pptx':'📙',
  '.jpg':'🖼','.jpeg':'🖼','.png':'🖼','.gif':'🖼','.webp':'🖼' };

let activeEl = null;
let pathToLi = new Map();
let pathToDirLi = new Map();

async function refreshRoot() {
  const r = await fetch('/api/root');
  if (!r.ok) throw new Error(await apiErrorText(r));
  const d = await r.json();
  rootPathEl.textContent = d.root || '\u672a\u9009\u62e9\u8d44\u6599\u76ee\u5f55';
  rootPathEl.title = d.root || '';
  currentRootKey = d.root || '';
  return d;
}

function showNeedsRootState() {
  resetWorkspaceView();
  annoCache = { files: {}, tag_palette: [] };
  scannedPaths = new Set();
  treeEl.innerHTML = '<div class="empty-state">\u8bf7\u9009\u62e9\u8d44\u6599\u76ee\u5f55</div>';
  viewerEl.innerHTML = '<div class="empty-state"><h2>\u8bf7\u9009\u62e9\u8d44\u6599\u76ee\u5f55</h2><p>\u70b9\u51fb\u5de6\u4e0a\u89d2\u201c\u5207\u6362\u201d\u9009\u62e9\u4f60\u7684\u8d44\u6599\u6587\u4ef6\u5939\u3002</p></div>';
  preconvertEl.style.display = 'none';
}


function resetWorkspaceView() {
  currentPath = null;
  activeEl = null;
  pathToLi = new Map();
  pathToDirLi = new Map();
  viewerEl.innerHTML = '';
  crumbEl.textContent = '';
  dlEl.style.display = 'none';
  revealBtn.style.display = 'none';
  starBtn.style.display = 'none';
  tagBtn.style.display = 'none';
  noteBtn.style.display = 'none';
  searchInput.value = '';
  showTreeView();
}

// ---- Tree expand state persistence ----
function loadOpenDirSet() {
  try {
    const raw = localStorage.getItem(LS.openDirs());
    return new Set(raw ? JSON.parse(raw) : []);
  } catch { return new Set(); }
}
function saveOpenDirs() {
  const open = [];
  treeEl.querySelectorAll('li.dir.open').forEach(li => {
    if (li.dataset.dirPath) open.push(li.dataset.dirPath);
  });
  try { localStorage.setItem(LS.openDirs(), JSON.stringify(open)); } catch {}
}
let _saveOpenTimer = null;
function scheduleSaveOpenDirs() {
  clearTimeout(_saveOpenTimer);
  _saveOpenTimer = setTimeout(saveOpenDirs, 200);
}

async function loadTree() {
  treeEl.innerHTML = '\u52a0\u8f7d\u4e2d...';
  const r = await fetch('/api/tree?recursive=1');
  if (!r.ok) throw new Error(await apiErrorText(r));
  const data = await r.json();
  if (data.needs_root) {
    showNeedsRootState();
    return false;
  }
  pathToLi = new Map();
  pathToDirLi = new Map();
  treeEl.innerHTML = '';
  const openSet = loadOpenDirSet();
  treeEl.appendChild(renderNodes(data.children || [], openSet));
  return true;
}

async function loadDirChildren(li, sub) {
  if (li.dataset.loaded === '1') return;
  li.dataset.loading = '1';
  try {
    const r = await fetch('/api/tree?path=' + encodeURIComponent(li.dataset.dirPath || ''));
    if (!r.ok) throw new Error(await apiErrorText(r));
    const data = await r.json();
    const next = renderNodes(data.children || [], loadOpenDirSet());
    next.style.display = sub.style.display;
    sub.replaceWith(next);
    li.dataset.loaded = '1';
    refreshAllBadges();
  } finally {
    delete li.dataset.loading;
  }
}

function renderNodes(nodes, openSet) {
  const ul = document.createElement('ul');
  for (const n of nodes) {
    const li = document.createElement('li');
    li.className = n.type;
    const label = document.createElement('span');
    label.className = 'label';
    const icon = n.type === 'dir' ? '📁' : (ICON[n.ext] || '📄');
    if (n.type === 'file') {
      label.innerHTML = `<span class="icon">${icon}</span>${escapeHtml(n.name)}<span class="badges" data-badge-for="${escapeHtml(n.path)}"></span>`;
    } else {
      label.innerHTML = `<span class="icon">${icon}</span>${escapeHtml(n.name)}`;
    }
    li.appendChild(label);
    if (n.type === 'dir') {
      li.dataset.dirPath = n.path;
      pathToDirLi.set(n.path, li);
      const sub = renderNodes(n.children || [], openSet);
      li.dataset.loaded = Array.isArray(n.children) ? '1' : '0';
      const isOpen = li.dataset.loaded === '1' && openSet && openSet.has(n.path);
      sub.style.display = isOpen ? '' : 'none';
      if (isOpen) li.classList.add('open');
      li.appendChild(sub);
      label.addEventListener('click', async (e) => {
        e.stopPropagation();
        const currentSub = li.querySelector(':scope > ul');
        const opening = !li.classList.contains('open');
        li.classList.toggle('open', opening);
        if (currentSub) currentSub.style.display = opening ? '' : 'none';
        if (opening && currentSub && li.dataset.loading !== '1') {
          await loadDirChildren(li, currentSub);
        }
        // user explicit toggle clears auto-open mark
        delete li.dataset.autoOpen;
        scheduleSaveOpenDirs();
      });
    } else {
      pathToLi.set(n.path, li);
      li.dataset.path = n.path;
      label.addEventListener('click', (e) => {
        e.stopPropagation();
        openFile(n, li);
      });
    }
    ul.appendChild(li);
  }
  return ul;
}

function refreshAllBadges() {
  // Update star/tag/scanned badges for all rendered file items based on annoCache + scanned set
  const badgeNodes = treeEl.querySelectorAll('[data-badge-for]');
  badgeNodes.forEach(node => {
    const path = node.getAttribute('data-badge-for');
    const a = (annoCache.files || {})[path] || {};
    let html = '';
    if (a.starred) html += '<span class="badge-star">★</span>';
    if (Array.isArray(a.tags)) {
      a.tags.forEach(t => { html += `<span class="badge-tag">${escapeHtml(t)}</span>`; });
    }
    if (scannedPaths.has(path)) {
      html += '<span class="badge-scanned" title="扫描版 PDF — 无文本层，不可搜索/AI 整理">📷</span>';
    }
    node.innerHTML = html;
  });
  applyView();
}

function applyView() {
  // First, undo previous auto-opens from view filtering (don't touch
  // user-opened dirs).
  treeEl.querySelectorAll('li.dir[data-auto-open]').forEach(li => {
    li.classList.remove('open');
    const sub = li.querySelector(':scope > ul');
    if (sub) sub.style.display = 'none';
    delete li.dataset.autoOpen;
  });

  // Mark files
  const allFiles = treeEl.querySelectorAll('li.file');
  allFiles.forEach(li => {
    const p = li.dataset.path;
    const a = (annoCache.files || {})[p] || {};
    let show = true;
    if (currentView === 'starred') show = !!a.starred;
    else if (currentView === 'tagged') show = Array.isArray(a.tags) && a.tags.length > 0;
    li.classList.toggle('view-hidden', !show);
  });
  // Hide / auto-open dirs based on visible-file count
  const allDirs = treeEl.querySelectorAll('li.dir');
  allDirs.forEach(li => {
    const visibleFiles = li.querySelectorAll('li.file:not(.view-hidden)').length;
    const empty = visibleFiles === 0 && currentView !== 'all';
    li.classList.toggle('view-hidden', empty);
    if (currentView !== 'all' && visibleFiles > 0 && !li.classList.contains('open')) {
      li.classList.add('open');
      li.dataset.autoOpen = '1';
      const sub = li.querySelector(':scope > ul');
      if (sub) sub.style.display = '';
    }
  });
  // Re-apply name filter on top
  applyFilter(treeEl, filterEl.value.trim().toLowerCase());
  // Restore current selection into view
  if (activeEl && !activeEl.classList.contains('view-hidden')) {
    activeEl.scrollIntoView({ block: 'nearest' });
  }
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function expandToFile(path) {
  // walk up the DOM ancestors and open parent <li class="dir">
  const li = pathToLi.get(path);
  if (!li) return false;
  let p = li.parentElement; // <ul>
  let opened = false;
  while (p && p !== treeEl) {
    if (p.tagName === 'UL') {
      const parentLi = p.parentElement;
      if (parentLi && parentLi.classList.contains('dir') && !parentLi.classList.contains('open')) {
        parentLi.classList.add('open');
        p.style.display = '';
        opened = true;
      }
    }
    p = p.parentElement;
  }
  li.scrollIntoView({ block: 'center' });
  if (opened) scheduleSaveOpenDirs();
  return true;
}

async function openFileByPath(path) {
  await ensurePathLoaded(path);
  const li = pathToLi.get(path);
  if (!li) return;
  expandToFile(path);
  const node = { path, name: path.split('/').pop(), ext: '.' + (path.split('.').pop() || '').toLowerCase() };
  openFile(node, li);
}

async function ensurePathLoaded(path) {
  const parts = path.split('/');
  let dirPath = '';
  for (let i = 0; i < parts.length - 1; i++) {
    dirPath = dirPath ? `${dirPath}/${parts[i]}` : parts[i];
    const dirLi = pathToDirLi.get(dirPath);
    if (!dirLi) return;
    const sub = dirLi.querySelector(':scope > ul');
    if (!sub) return;
    dirLi.classList.add('open');
    sub.style.display = '';
    await loadDirChildren(dirLi, sub);
  }
}

async function openFile(node, li) {
  if (activeEl) activeEl.classList.remove('active');
  li.classList.add('active');
  activeEl = li;

  currentPath = node.path;
  crumbEl.textContent = node.path;
  dlEl.href = '/api/raw?path=' + encodeURIComponent(node.path);
  dlEl.style.display = '';
  revealBtn.style.display = '';
  starBtn.style.display = '';
  tagBtn.style.display = '';
  noteBtn.style.display = '';
  renderAnnoBar();
  closePopovers();
  // AI panel: just show the button; DO NOT fetch eligibility here —
  // it triggers pypdf extraction on the server and competes with the
  // PDF download we're about to fire. Eligibility is loaded lazily
  // when the user actually opens the AI panel.
  if (typeof onFileSelected === 'function') {
    onFileSelected(node.path);
  }

  viewerEl.innerHTML = '<div class="loading">加载中…</div>';
  viewerEl.scrollTop = 0;

  // For office files, poll preconvert status and surface the queue
  // situation so the user knows why it's slow.
  const isOffice = /\.(doc|docx|xls|xlsx|ppt|pptx|odt|ods|odp|rtf)$/i.test(node.path);
  let pollTimer = null;
  let officeHintTimer = null;
  if (isOffice) {
    const loadingDiv = viewerEl.querySelector('.loading');
    const updateLoading = async () => {
      try {
        const s = await (await fetch('/api/preconvert/status')).json();
        if (!loadingDiv || !document.body.contains(loadingDiv)) return;
        if (s.running && s.current) {
          loadingDiv.textContent = `转换中…（后台预转换占用，当前正在转 ${s.current} · ${s.done}/${s.total}）`;
        } else {
          loadingDiv.textContent = '转换中（LibreOffice 首次启动较慢）…';
        }
      } catch {}
    };
    officeHintTimer = setTimeout(() => {
      updateLoading();
      pollTimer = setInterval(updateLoading, 1500);
    }, 900);
  }

  const url = '/api/file?path=' + encodeURIComponent(node.path);
  try {
    const r = await fetch(url);
    const ct = r.headers.get('Content-Type') || '';

    if (r.status === 415) {
      const j = await r.json();
      viewerEl.innerHTML = `<div class="error-box">暂不支持预览此格式（${escapeHtml(j.ext || '')}）。
        <br><br><a href="/api/raw?path=${encodeURIComponent(node.path)}" target="_blank">点此下载原文件</a></div>`;
      return;
    }
    if (!r.ok) {
      let msg = `加载失败：HTTP ${r.status}`;
      try { const j = await r.json(); if (j.message) msg += '\n' + j.message; } catch {}
      viewerEl.innerHTML = `<div class="error-box">${escapeHtml(msg)}</div>`;
      return;
    }

    viewerEl.innerHTML = '';
    viewerEl.scrollTop = 0;

    if (ct.includes('application/pdf')) {
      const f = document.createElement('iframe');
      f.src = url + '#toolbar=1&view=FitH&page=1';
      f.addEventListener('load', () => { viewerEl.scrollTop = 0; });
      viewerEl.appendChild(f);
    } else if (ct.startsWith('image/')) {
      const img = document.createElement('img');
      img.className = 'preview';
      img.src = url;
      img.addEventListener('load', () => { viewerEl.scrollTop = 0; });
      viewerEl.appendChild(img);
    } else if (ct.includes('text/html')) {
      const html = await r.text();
      const f = document.createElement('iframe');
      f.srcdoc = html;
      f.addEventListener('load', () => {
        viewerEl.scrollTop = 0;
        try { f.contentWindow.scrollTo(0, 0); } catch {}
      });
      viewerEl.appendChild(f);
    } else {
      viewerEl.innerHTML = `<div class="error-box">未知响应类型：${escapeHtml(ct)}</div>`;
    }
  } catch (err) {
    viewerEl.innerHTML = `<div class="error-box">请求出错：${escapeHtml(String(err))}</div>`;
  } finally {
    if (officeHintTimer) clearTimeout(officeHintTimer);
    if (pollTimer) clearInterval(pollTimer);
  }
}

filterEl.addEventListener('input', () => {
  const kw = filterEl.value.trim().toLowerCase();
  applyFilter(treeEl, kw);
});

function applyFilter(root, kw) {
  const lis = root.querySelectorAll(':scope > ul > li');
  let anyVisible = false;
  for (const li of lis) {
    const label = li.querySelector(':scope > .label');
    const text = label.textContent.toLowerCase();
    if (li.classList.contains('dir')) {
      const childVisible = applyFilter(li, kw);
      const selfMatch = !kw || text.includes(kw);
      const matched = childVisible || selfMatch;
      if (matched) {
        li.classList.remove('hidden');
        if (kw && childVisible) {
          if (!li.classList.contains('open')) {
            li.classList.add('open');
            li.dataset.autoOpen = '1';
            const sub = li.querySelector(':scope > ul');
            if (sub) sub.style.display = '';
          }
        }
      } else {
        li.classList.add('hidden');
      }
      // dir doesn't count as visible unless the view also allows it
      if (matched && !li.classList.contains('view-hidden')) anyVisible = true;
    } else {
      if (!kw || text.includes(kw)) {
        li.classList.remove('hidden');
        if (!li.classList.contains('view-hidden')) anyVisible = true;
      } else {
        li.classList.add('hidden');
      }
    }
  }
  return anyVisible;
}

async function apiErrorText(r) {
  const j = await r.json().catch(() => ({}));
  return j.detail || j.message || ('HTTP ' + r.status);
}

async function switchRootPath(path) {
  const r = await fetch('/api/root', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!r.ok) throw new Error(await apiErrorText(r));
  annoCache = { files: {}, tag_palette: [] };
  scannedPaths = new Set();
  if (typeof aiClearConv === 'function') aiClearConv();
  if (typeof onFileSelected === 'function') onFileSelected(null);
  resetWorkspaceView();
  await bootstrap();
}

async function promptRootPath(reason) {
  const fallback = (rootPathEl.textContent || '').trim();
  const manual = prompt(reason + '\n\n\u8bf7\u8f93\u5165\u8d44\u6599\u76ee\u5f55\u5b8c\u6574\u8def\u5f84:', fallback);
  if (!manual || !manual.trim()) return;
  await switchRootPath(manual.trim());
}

pickBtn.addEventListener('click', async () => {
  pickBtn.disabled = true;
  pickBtn.textContent = '\u9009\u62e9\u4e2d...';
  try {
    const r = await fetch('/api/pick-folder', { method: 'POST' });
    if (!r.ok) throw new Error(await apiErrorText(r));
    const d = await r.json();
    if (!d.path) return;
    await switchRootPath(d.path);
  } catch (err) {
    try {
      await promptRootPath('\u7cfb\u7edf\u76ee\u5f55\u9009\u62e9\u4e0d\u53ef\u7528: ' + (err.message || err));
    } catch (manualErr) {
      alert('\u5207\u6362\u76ee\u5f55\u5931\u8d25: ' + (manualErr.message || manualErr));
    }
  } finally {
    pickBtn.disabled = false;
    pickBtn.textContent = '\u5207\u6362';
  }
});

revealBtn.addEventListener('click', async () => {
  if (!currentPath) return;
  try {
    const r = await fetch('/api/reveal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: currentPath }),
    });
    if (!r.ok) alert('?????' + await apiErrorText(r));
  } catch (err) {
    alert('?????' + (err.message || err));
  }
});

// --- Keyboard navigation: ↑↓ to move file selection, Enter to open ---
document.addEventListener('keydown', (e) => {
  // ignore when typing in inputs
  const ae = document.activeElement;
  if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) return;
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
  e.preventDefault();

  // Collect all visible file <li> in DOM order
  const files = Array.from(treeEl.querySelectorAll('li.file'))
    .filter(li => _itemVisible(li));
  if (files.length === 0) return;

  let idx = activeEl ? files.indexOf(activeEl) : -1;
  if (e.key === 'ArrowDown') idx = Math.min(files.length - 1, idx + 1);
  if (e.key === 'ArrowUp') idx = Math.max(0, idx === -1 ? 0 : idx - 1);

  const li = files[idx];
  if (!li) return;
  li.querySelector(':scope > .label').click();
});

function _itemVisible(li) {
  if (li.classList.contains('hidden') || li.classList.contains('view-hidden')) return false;
  let p = li.parentElement;
  while (p && p !== treeEl) {
    if (p.tagName === 'LI' && (p.classList.contains('hidden') || p.classList.contains('view-hidden'))) return false;
    if (p.tagName === 'UL' && p.style.display === 'none') return false;
    p = p.parentElement;
  }
  return true;
}

// --- Annotations ---
async function loadAnno() {
  const r = await fetch('/api/anno/all');
  if (!r.ok) throw new Error(await apiErrorText(r));
  annoCache = await r.json();
  if (annoCache.needs_root) {
    annoCache = { files: {}, tag_palette: [] };
    return;
  }
  refreshAllBadges();
  if (currentPath) renderAnnoBar();  // refresh anno panel for already-open file
}

async function patchAnno(path, partial) {
  const r = await fetch('/api/anno?path=' + encodeURIComponent(path), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(partial),
  });
  if (!r.ok) throw new Error('save failed: ' + await apiErrorText(r));
  const entry = await r.json();
  // update local cache
  if (Object.keys(entry).length) {
    annoCache.files = annoCache.files || {};
    annoCache.files[path] = entry;
  } else if (annoCache.files) {
    delete annoCache.files[path];
  }
  refreshAllBadges();
  return entry;
}

function currentAnno() {
  if (!currentPath) return {};
  return (annoCache.files || {})[currentPath] || {};
}

function renderAnnoBar() {
  const a = currentAnno();
  // star
  starBtn.textContent = a.starred ? '★' : '☆';
  starBtn.classList.toggle('on', !!a.starred);
  // tag count badge
  const tagN = (a.tags || []).length;
  tagCountEl.textContent = tagN || '';
  tagCountEl.classList.toggle('show', tagN > 0);
  // note dot
  noteDotEl.classList.toggle('show', !!(a.notes && a.notes.length));
  // tag popover content
  const palette = (annoCache.tag_palette || []).slice();
  const active = new Set(a.tags || []);
  active.forEach(t => { if (!palette.includes(t)) palette.push(t); });
  tagChipsEl.innerHTML = '';
  palette.forEach(t => {
    const chip = document.createElement('span');
    chip.className = 'tag-chip' + (active.has(t) ? ' active' : '');
    chip.textContent = t;
    chip.addEventListener('click', () => toggleTag(t));
    tagChipsEl.appendChild(chip);
  });
  // notes popover content
  notesEl.value = a.notes || '';
  noteHintEl.textContent = a.updated_at
    ? new Date(a.updated_at * 1000).toLocaleString()
    : '';
}

function closePopovers() {
  tagPop.hidden = true;
  notePop.hidden = true;
}
function togglePop(pop) {
  const isHidden = pop.hidden;
  closePopovers();
  if (isHidden) pop.hidden = false;
}
tagBtn.addEventListener('click', (e) => { e.stopPropagation(); togglePop(tagPop); });
noteBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  const wasHidden = notePop.hidden;
  togglePop(notePop);
  if (wasHidden) setTimeout(() => notesEl.focus(), 50);
});
document.addEventListener('click', (e) => {
  if (tagPop.contains(e.target) || notePop.contains(e.target)) return;
  if (e.target === tagBtn || e.target === noteBtn) return;
  closePopovers();
});

async function toggleStar() {
  if (!currentPath) return;
  const a = currentAnno();
  const next = !a.starred;
  await patchAnno(currentPath, { starred: next ? true : null });
  renderAnnoBar();
}

async function toggleTag(t) {
  if (!currentPath) return;
  const cur = (currentAnno().tags || []).slice();
  const idx = cur.indexOf(t);
  if (idx >= 0) cur.splice(idx, 1); else cur.push(t);
  await patchAnno(currentPath, { tags: cur.length ? cur : null });
  renderAnnoBar();
}

starBtn.addEventListener('click', () => {
  toggleStar().catch(err => alert('Save failed: ' + (err.message || err)));
});

addTagBtn.addEventListener('click', async () => {
  const name = (prompt('新标签名（之后所有文件都可用）：') || '').trim();
  if (!name) return;
  const palette = (annoCache.tag_palette || []).slice();
  if (palette.includes(name)) {
    // just apply to current file
  } else {
    palette.push(name);
    const r = await fetch('/api/anno/palette', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags: palette }),
    });
    if (!r.ok) throw new Error(await apiErrorText(r));
    const d = await r.json();
    annoCache.tag_palette = d.palette;
  }
  if (currentPath) {
    const cur = (currentAnno().tags || []).slice();
    if (!cur.includes(name)) cur.push(name);
    await patchAnno(currentPath, { tags: cur });
  }
  renderAnnoBar();
});

// Autosave notes (debounced)
let _noteTimer = null;
notesEl.addEventListener('input', () => {
  if (!currentPath) return;
  noteHintEl.textContent = '保存中…';
  clearTimeout(_noteTimer);
  _noteTimer = setTimeout(async () => {
    const txt = notesEl.value;
    try {
      await patchAnno(currentPath, { notes: txt || null });
      noteHintEl.textContent = '已保存 ' + new Date().toLocaleTimeString();
    } catch (e) {
      noteHintEl.textContent = '保存失败';
    }
  }, 600);
});

// View tabs (全部 / 收藏 / 已标)
document.querySelectorAll('.view-tabs .vt').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-tabs .vt').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentView = btn.dataset.view;
    applyView();
  });
});

// Keyboard: 'S' to toggle star
document.addEventListener('keydown', (e) => {
  const ae = document.activeElement;
  if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) return;
  if (e.key === 's' || e.key === 'S') {
    if (!currentPath) return;
    e.preventDefault();
    toggleStar();
  }
  if (e.key === 't' || e.key === 'T') {
    if (!currentPath) return;
    e.preventDefault();
    togglePop(tagPop);
  }
  if (e.key === 'n' || e.key === 'N') {
    if (!currentPath) return;
    e.preventDefault();
    const wasHidden = notePop.hidden;
    togglePop(notePop);
    if (wasHidden) setTimeout(() => notesEl.focus(), 50);
  }
  if (e.key === 'Escape') {
    closePopovers();
  }
});

// --- Preconvert status poll ---
async function pollPreconvert() {
  try {
    const r = await fetch('/api/preconvert/status');
    const s = await r.json();
    if (s.running && s.total) {
      preconvertEl.style.display = '';
      preconvertEl.textContent = `⚙ 后台预转换 ${s.done}/${s.total} · ${s.current || ''}`;
    } else {
      preconvertEl.style.display = 'none';
    }
  } catch {
    preconvertEl.style.display = 'none';
  }
}
setInterval(pollPreconvert, 1500);

// --- Scanned-PDF list poll ---
let _scannedPollTimer = null;
let _scannedPrebuildSeenDone = false;

async function loadScanned() {
  try {
    const r = await fetch('/api/search/scanned');
    if (!r.ok) throw new Error(await apiErrorText(r));
    const d = await r.json();
    if (d.needs_root) {
      scannedPaths = new Set();
      return;
    }
    const prevCount = scannedPaths.size;
    scannedPaths = new Set(d.scanned || []);
    if (scannedPaths.size !== prevCount) refreshAllBadges();
  } catch {}
}

async function _scannedPollStep() {
  await loadScanned();
  // Stop polling once prebuild finishes (the scanned set is stable from then on).
  try {
    const s = await (await fetch('/api/search/status')).json();
    if (!s.running && s.total > 0) {
      _scannedPrebuildSeenDone = true;
    }
  } catch {}
  if (_scannedPrebuildSeenDone) {
    if (_scannedPollTimer) { clearInterval(_scannedPollTimer); _scannedPollTimer = null; }
  }
}
// Only poll while the index is still building.
_scannedPollTimer = setInterval(_scannedPollStep, 5000);

async function bootstrap() {
  try {
    const info = await refreshRoot();
    if (info.needs_root) {
      showNeedsRootState();
      return;
    }
    const treeLoaded = await loadTree();
    if (!treeLoaded) return;
    await loadAnno();
    await loadScanned();
    if (info.last_file) {
      setTimeout(() => openFileByPath(info.last_file), 0);
    }
    pollPreconvert();
  } catch (err) {
    treeEl.innerHTML = '<div class="error-box">' + escapeHtml('???????' + (err.message || err)) + '</div>';
    viewerEl.innerHTML = '<div class="error-box">' + escapeHtml('???????' + (err.message || err)) + '</div>';
  }
}

// --- Right-click context menu on tree items ---
const ctxMenuEl = document.getElementById('ctx-menu');

function showCtxMenu(x, y, items) {
  ctxMenuEl.innerHTML = '';
  for (const it of items) {
    if (it === '-') {
      const sep = document.createElement('div');
      sep.className = 'sep';
      ctxMenuEl.appendChild(sep);
      continue;
    }
    const div = document.createElement('div');
    div.className = 'item';
    div.textContent = it.label;
    div.addEventListener('click', () => {
      hideCtxMenu();
      try {
        Promise.resolve(it.action()).catch(e => alert(e.message || e));
      } catch (e) { alert(e.message || e); }
    });
    ctxMenuEl.appendChild(div);
  }
  ctxMenuEl.style.left = x + 'px';
  ctxMenuEl.style.top = y + 'px';
  ctxMenuEl.hidden = false;
  // Re-position if overflowing
  const r = ctxMenuEl.getBoundingClientRect();
  if (r.right > window.innerWidth) ctxMenuEl.style.left = (window.innerWidth - r.width - 4) + 'px';
  if (r.bottom > window.innerHeight) ctxMenuEl.style.top = (window.innerHeight - r.height - 4) + 'px';
}
function hideCtxMenu() { ctxMenuEl.hidden = true; }

document.addEventListener('click', hideCtxMenu);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideCtxMenu(); });
window.addEventListener('scroll', hideCtxMenu, true);

treeEl.addEventListener('contextmenu', (e) => {
  const li = e.target.closest('li.file');
  if (!li) return;
  e.preventDefault();
  const path = li.dataset.path;
  const a = (annoCache.files || {})[path] || {};
  const ext = ('.' + (path.split('.').pop() || '')).toLowerCase();
  const isOffice = ['.doc','.docx','.xls','.xlsx','.ppt','.pptx','.odt','.ods','.odp','.rtf'].includes(ext);

  const items = [
    { label: a.starred ? '取消收藏' : '★ 收藏', action: async () => {
        await patchAnno(path, { starred: a.starred ? null : true });
        if (path === currentPath) renderAnnoBar();
    } },
    { label: '📂 在资源管理器打开', action: async () => {
        const r = await fetch('/api/reveal', { method: 'POST', headers: {'Content-Type':'application/json'},
                                               body: JSON.stringify({ path }) });
        if (!r.ok) alert('Open failed: ' + await apiErrorText(r));
    } },
    { label: '📋 复制路径', action: async () => {
        const fullPath = (rootPathEl.textContent || '') + '\\' + path.replace(/\//g, '\\');
        try { await navigator.clipboard.writeText(fullPath); }
        catch { prompt('复制此路径：', fullPath); }
    } },
  ];
  if (isOffice) {
    items.push('-');
    items.push({ label: '🔄 重新转换（清除负缓存）', action: () => {
        // Force-reload via api with ?force=1
        if (path === currentPath) {
          viewerEl.innerHTML = '<div class="loading">重新转换中…</div>';
          fetch('/api/file?force=1&path=' + encodeURIComponent(path))
            .then(r => r.ok ? openFileByPath(path) : alert('重转失败：HTTP ' + r.status));
        } else {
          fetch('/api/file?force=1&remember=0&path=' + encodeURIComponent(path))
            .then(r => alert(r.ok ? '已重新转换' : ('重转失败：HTTP ' + r.status)));
        }
    } });
  }
  showCtxMenu(e.clientX, e.clientY, items);
});

// --- Content search ---
const searchInput = document.getElementById('search-content');
const searchResultsEl = document.getElementById('search-results');

function showTreeView() {
  searchResultsEl.hidden = true;
  treeEl.style.display = '';
}
function showSearchView() {
  treeEl.style.display = 'none';
  searchResultsEl.hidden = false;
}

function highlightQ(text, q) {
  if (!q) return escapeHtml(text);
  const lc = text.toLowerCase();
  const qlc = q.toLowerCase();
  let out = '';
  let i = 0;
  while (i < text.length) {
    const idx = lc.indexOf(qlc, i);
    if (idx < 0) { out += escapeHtml(text.slice(i)); break; }
    out += escapeHtml(text.slice(i, idx));
    out += '<mark>' + escapeHtml(text.slice(idx, idx + q.length)) + '</mark>';
    i = idx + q.length;
  }
  return out;
}

async function runContentSearch() {
  const q = searchInput.value.trim();
  if (!q) { showTreeView(); return; }
  showSearchView();
  searchResultsEl.innerHTML = '<div class="sr-head"><span>???...</span><button id="sr-close">? ??</button></div>';
  document.getElementById('sr-close').addEventListener('click', () => {
    searchInput.value = '';
    showTreeView();
  });
  try {
    const r = await fetch('/api/search?q=' + encodeURIComponent(q) + '&limit=80');
    if (!r.ok) throw new Error(await apiErrorText(r));
    const d = await r.json();
    renderSearchResults(d, q);
  } catch (err) {
    searchResultsEl.innerHTML = '<div class="sr-head"><span>' + escapeHtml('?????' + (err.message || err)) + '</span><button id="sr-close">? ??</button></div>';
    document.getElementById('sr-close').addEventListener('click', () => {
      searchInput.value = '';
      showTreeView();
    });
  }
}

function renderSearchResults(data, q) {
  const head = document.createElement('div');
  head.className = 'sr-head';
  head.innerHTML = `<span>找到 ${data.count} 个文件（已索引 ${data.index.cached_files} 个）</span><button id="sr-close">× 返回</button>`;
  searchResultsEl.innerHTML = '';
  searchResultsEl.appendChild(head);
  document.getElementById('sr-close').addEventListener('click', () => {
    searchInput.value = '';
    showTreeView();
  });
  for (const r of data.results) {
    const it = document.createElement('div');
    it.className = 'sr-item';
    it.innerHTML = `
      <div><span class="sr-name">${escapeHtml(r.name)}</span><span class="sr-hits">${r.hits} 处命中</span></div>
      <div class="sr-path">${escapeHtml(r.path)}</div>
      ${r.snippets.map(s => `<div class="sr-snippet">${highlightQ(s, q)}</div>`).join('')}
    `;
    it.addEventListener('click', () => {
      openFileByPath(r.path);
    });
    searchResultsEl.appendChild(it);
  }
  if (data.count === 0) {
    const empty = document.createElement('div');
    empty.style.padding = '24px';
    empty.style.color = '#999';
    empty.style.textAlign = 'center';
    empty.textContent = '没有匹配的文档';
    searchResultsEl.appendChild(empty);
  }
}

searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    runContentSearch();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    searchInput.value = '';
    showTreeView();
  }
});

// --- Sidebar drag-to-resize ---
(function setupResizer() {
  const sidebar = document.getElementById('sidebar');
  const resizer = document.getElementById('resizer');
  if (!resizer || !sidebar) return;

  // restore saved width
  const saved = parseInt(localStorage.getItem(LS.sidebarW()) || '', 10);
  if (Number.isFinite(saved) && saved >= 180 && saved <= 720) {
    sidebar.style.width = saved + 'px';
  }

  let dragging = false;
  resizer.addEventListener('mousedown', (e) => {
    dragging = true;
    document.body.classList.add('resizing');
    resizer.classList.add('dragging');
    e.preventDefault();
  });
  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const w = Math.max(180, Math.min(720, e.clientX));
    sidebar.style.width = w + 'px';
  });
  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('resizing');
    resizer.classList.remove('dragging');
    try {
      localStorage.setItem(LS.sidebarW(), String(sidebar.getBoundingClientRect().width | 0));
    } catch {}
  });
})();

// =====================================================================
// AI panel
// =====================================================================
const aiBtn         = document.getElementById('ai-btn');
const aiDot         = document.getElementById('ai-dot');
const aiPanel       = document.getElementById('ai-panel');
const aiResizer     = document.getElementById('ai-resizer');
const aiDockToggle  = document.getElementById('ai-dock-toggle');
const aiClose       = document.getElementById('ai-close');
const aiProviderEl  = document.getElementById('ai-provider');
const aiEligibility = document.getElementById('ai-eligibility');
const aiConv        = document.getElementById('ai-conv');
const aiInput       = document.getElementById('ai-input');
const aiSend        = document.getElementById('ai-send');
const aiSummarize   = document.getElementById('ai-summarize');
const aiTtsLast     = document.getElementById('ai-tts-last');
const aiClear       = document.getElementById('ai-clear');
const mainBodyEl    = document.querySelector('.main-body');

let aiStatusCache = null;        // /api/ai/status response
let aiEligibilityCache = null;   // /api/file/ai-eligibility for currentPath
let aiConversation = [];         // [{role, content}]
let aiBusy = false;

const AI_LS = {
  width:    'browse:aiPanelW',
  mode:     'browse:aiPanelMode',    // 'dock' | 'float'
};

// ---------- minimal Markdown renderer (handles common AI output) ----------
// Supports: code fences, inline code, headings, bold/italic, lists (ul/ol),
// blockquotes, horizontal rules, line breaks. Safe by HTML-escaping all text
// before inserting markup.
function renderMarkdown(src) {
  if (!src) return '';
  const escape = (s) => s.replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // 1. Pull out fenced code blocks first (so their content isn't touched)
  const codeBlocks = [];
  let s = src.replace(/```([a-zA-Z0-9_+-]*)\r?\n([\s\S]*?)```/g, (_, lang, code) => {
    const i = codeBlocks.length;
    codeBlocks.push(`<pre><code>${escape(code.replace(/\r?\n$/, ''))}</code></pre>`);
    return `__CODE_BLOCK_${i}__`;
  });

  // 2. Escape everything else
  s = escape(s);

  // 3. Inline code `…`
  s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');

  // 4. Bold ** and italic *
  s = s.replace(/\*\*\*([^*\n]+)\*\*\*/g, '<strong><em>$1</em></strong>');
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');

  // 5. Headings (h1-h4)
  s = s.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
  s = s.replace(/^###\s+(.+)$/gm,  '<h3>$1</h3>');
  s = s.replace(/^##\s+(.+)$/gm,   '<h2>$1</h2>');
  s = s.replace(/^#\s+(.+)$/gm,    '<h1>$1</h1>');

  // 6. Horizontal rule
  s = s.replace(/^---+$/gm, '<hr>');

  // 7. Lists & blockquotes (per-line state machine)
  const lines = s.split('\n');
  const out = [];
  let listType = null;     // 'ul' | 'ol' | null
  let inBq = false;
  function closeList() { if (listType) { out.push(`</${listType}>`); listType = null; } }
  function closeBq()   { if (inBq) { out.push('</blockquote>'); inBq = false; } }
  for (const raw of lines) {
    const line = raw;
    const ulM = line.match(/^[-*+]\s+(.+)$/);
    const olM = line.match(/^(\d+)\.\s+(.+)$/);
    const bqM = line.match(/^&gt;\s?(.*)$/);
    if (ulM) {
      closeBq();
      if (listType !== 'ul') { closeList(); out.push('<ul>'); listType = 'ul'; }
      out.push(`<li>${ulM[1]}</li>`);
    } else if (olM) {
      closeBq();
      if (listType !== 'ol') { closeList(); out.push('<ol>'); listType = 'ol'; }
      out.push(`<li>${olM[2]}</li>`);
    } else if (bqM) {
      closeList();
      if (!inBq) { out.push('<blockquote>'); inBq = true; }
      out.push(bqM[1] || '');
    } else {
      closeList(); closeBq();
      out.push(line);
    }
  }
  closeList(); closeBq();
  s = out.join('\n');

  // 8. Paragraphs (split on blank line; don't wrap block-level elements)
  s = s.split(/\n{2,}/).map(block => {
    block = block.trim();
    if (!block) return '';
    if (/^<(h[1-6]|ul|ol|blockquote|pre|hr)\b/.test(block) || /^__CODE_BLOCK_\d+__/.test(block)) {
      return block;
    }
    return `<p>${block.replace(/\n/g, '<br>')}</p>`;
  }).join('\n');

  // 9. Restore code blocks
  s = s.replace(/__CODE_BLOCK_(\d+)__/g, (_, i) => codeBlocks[parseInt(i, 10)]);

  return s;
}

async function fetchAiStatus() {
  try {
    const r = await fetch('/api/ai/status');
    if (!r.ok) return null;
    aiStatusCache = await r.json();
    return aiStatusCache;
  } catch { return null; }
}

function aiCanText()  { return !!(aiStatusCache && aiStatusCache.text); }
function aiCanTts()   { return !!(aiStatusCache && aiStatusCache.tts);  }

async function loadEligibility(path) {
  if (!path) return null;
  try {
    const r = await fetch('/api/file/ai-eligibility?path=' + encodeURIComponent(path));
    if (!r.ok) return null;
    aiEligibilityCache = await r.json();
    return aiEligibilityCache;
  } catch { return null; }
}

function updateAiButton() {
  // Always show the button when a file is open so the entry is discoverable.
  // The actual availability check (provider configured + file eligible)
  // happens lazily when the user clicks it.
  if (!currentPath) {
    aiBtn.style.display = 'none';
    return;
  }
  aiBtn.style.display = '';
  if (!aiCanText()) {
    aiBtn.style.opacity = '0.55';
    aiBtn.title = 'AI 未配置：在 config.json 的 ai 块填好 api_key 后重启服务（参考 config.example.json）';
    return;
  }
  // Configured but eligibility not yet checked — neutral state
  if (!aiEligibilityCache) {
    aiBtn.style.opacity = '1';
    aiBtn.title = 'AI 助手 (A)';
    return;
  }
  const ok = aiEligibilityCache.supported;
  aiBtn.style.opacity = ok ? '1' : '0.55';
  aiBtn.title = ok ? 'AI 助手 (A)' :
    'AI 不可用: ' + ((aiEligibilityCache.reasons || []).join('; '));
}

function renderEligibilityNotice() {
  if (!aiEligibilityCache) { aiEligibility.textContent = ''; return; }
  const reasons = aiEligibilityCache.reasons || [];
  if (reasons.length === 0 || aiEligibilityCache.mode === 'direct') {
    aiEligibility.textContent = '';
    return;
  }
  aiEligibility.textContent = '⚠ ' + reasons.join('；');
}

function renderProviderInfo() {
  if (!aiStatusCache || !aiStatusCache.text) {
    aiProviderEl.textContent = '未配置';
    return;
  }
  const t = aiStatusCache.text;
  const tts = aiCanTts() ? ' · TTS:' + aiStatusCache.tts.name : '';
  aiProviderEl.textContent = `text:${t.name}${tts}`;
}

function aiAppendMessage(role, content, { streaming = false } = {}) {
  const el = document.createElement('div');
  el.className = 'ai-msg ' + role + (streaming ? ' streaming' : '');
  const label = document.createElement('div');
  label.className = 'role-label';
  label.textContent = role === 'user' ? '我' : 'AI';
  el.appendChild(label);
  const body = document.createElement('div');
  body.className = 'msg-body md-body';
  // Track the raw text separately from the rendered markdown so copy/tts
  // operate on plain text, not HTML.
  body.dataset.raw = content || '';
  body.innerHTML = role === 'user'
    ? `<p>${escapeHtml(content || '').replace(/\n/g, '<br>')}</p>`
    : renderMarkdown(content || '');
  el.appendChild(body);
  if (role === 'assistant') {
    const actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML = '<button class="copy" type="button">📋 复制</button>' +
                       (aiCanTts() ? '<button class="tts" type="button">🔊 朗读</button>' : '');
    el.appendChild(actions);
    actions.querySelector('.copy').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(body.dataset.raw || ''); } catch {}
    });
    const ttsBtn = actions.querySelector('.tts');
    if (ttsBtn) {
      ttsBtn.addEventListener('click', () => {
        // If already playing this very message, stop. Otherwise start fresh.
        if (_ttsCurrent && _ttsCurrent.btn === ttsBtn) {
          _ttsStop();
        } else {
          aiPlayTts(body.dataset.raw || '', ttsBtn);
        }
      });
    }
  }
  aiConv.appendChild(el);
  aiConv.scrollTop = aiConv.scrollHeight;
  return { el, body };
}

// Update body for streaming: update both raw text + re-render markdown.
// Throttled with rAF so re-rendering doesn't fire on every token.
let _renderTimer = null;
function aiUpdateStreaming(body, raw) {
  body.dataset.raw = raw;
  if (_renderTimer) return;
  _renderTimer = requestAnimationFrame(() => {
    _renderTimer = null;
    body.innerHTML = renderMarkdown(body.dataset.raw);
    aiConv.scrollTop = aiConv.scrollHeight;
  });
}
function aiFinalizeStreaming(body) {
  if (_renderTimer) { cancelAnimationFrame(_renderTimer); _renderTimer = null; }
  body.innerHTML = renderMarkdown(body.dataset.raw || '');
  aiConv.scrollTop = aiConv.scrollHeight;
}

function aiClearConv() {
  aiConv.innerHTML = '';
  aiConversation = [];
}

async function aiStream(url, payload, onDelta, onEvent = null) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const t = await r.text().catch(() => '');
    throw new Error('HTTP ' + r.status + ' ' + t.slice(0, 200));
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buf = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 2);
      if (!frame.startsWith('data:')) continue;
      const data = frame.slice(5).trim();
      if (data === '[DONE]') return;
      try {
        const obj = JSON.parse(data);
        if (onEvent) onEvent(obj);
        if (obj.delta) onDelta(obj.delta);
        if (obj.error) throw new Error(obj.error);
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

async function ensureEligible() {
  if (!currentPath) return false;
  if (!aiEligibilityCache) {
    await loadEligibility(currentPath);
    renderEligibilityNotice();
    updateAiButton();
  }
  if (!aiEligibilityCache || !aiEligibilityCache.supported) {
    alert((aiEligibilityCache && aiEligibilityCache.reasons || ['AI 不可用']).join('\n'));
    return false;
  }
  return true;
}

async function aiSendQuestion() {
  if (aiBusy || !currentPath) return;
  if (!(await ensureEligible())) return;
  const q = aiInput.value.trim();
  if (!q) return;
  aiInput.value = '';
  aiAppendMessage('user', q);
  aiConversation.push({ role: 'user', content: q });
  const { el, body } = aiAppendMessage('assistant', '', { streaming: true });
  aiBusy = true; aiSend.disabled = true;
  let acc = '';
  try {
    await aiStream('/api/ai/chat', {
      path: currentPath,
      question: q,
      history: aiConversation.slice(0, -1),
      stream: true,
    }, (d) => {
      acc += d;
      aiUpdateStreaming(body, acc);
    });
    aiFinalizeStreaming(body);
    aiConversation.push({ role: 'assistant', content: acc });
  } catch (err) {
    body.dataset.raw = '⚠ ' + (err.message || err);
    body.innerHTML = `<p>${escapeHtml(body.dataset.raw)}</p>`;
  } finally {
    el.classList.remove('streaming');
    aiBusy = false; aiSend.disabled = false;
  }
}

async function aiDoSummarize() {
  if (aiBusy || !currentPath) return;
  if (scannedPaths && scannedPaths.has(currentPath)) {
    aiAppendMessage('assistant', '\u8fd9\u662f\u626b\u63cf\u7248 PDF\uff0c\u6ca1\u6709\u53ef\u63d0\u53d6\u7684\u6587\u672c\u5c42\uff0c\u6682\u4e0d\u652f\u6301 AI \u6574\u7406\u3002\u53ef\u5148\u901a\u8fc7 OCR \u8f6c\u6210\u53ef\u590d\u5236\u6587\u672c\u540e\u518d\u4f7f\u7528\u3002');
    return;
  }
  if (!(await ensureEligible())) return;
  const { el, body } = aiAppendMessage('assistant', '\u51c6\u5907\u6574\u7406\u672c\u6587\u6863...', { streaming: true });
  aiBusy = true; aiSummarize.disabled = true;
  let acc = '';
  let stage = '';
  try {
    await aiStream('/api/ai/summarize', {
      path: currentPath, stream: true, force: false,
    }, (d) => {
      acc += d;
      aiUpdateStreaming(body, acc);
    }, (evt) => {
      if (evt.stage) {
        stage = evt.stage;
        if (!acc) aiUpdateStreaming(body, stage + '...');
      }
    });
    aiFinalizeStreaming(body);
    if (acc) aiConversation.push({ role: 'assistant', content: acc });
  } catch (err) {
    body.dataset.raw = '\u26a0 ' + (stage ? stage + '\n' : '') + (err.message || err);
    body.innerHTML = `<p>${escapeHtml(body.dataset.raw)}</p>`;
  } finally {
    el.classList.remove('streaming');
    aiBusy = false; aiSummarize.disabled = false;
  }
}

// ---------- TTS singleton ----------
// Only one Audio plays at a time. Buttons toggle between play / stop.
let _ttsCurrent = null;   // { audio, url, btn }
let _ttsLoading = null;   // path-like key to dedupe concurrent fetches

function _ttsStop() {
  if (!_ttsCurrent) return;
  try { _ttsCurrent.audio.pause(); } catch {}
  if (_ttsCurrent.url) URL.revokeObjectURL(_ttsCurrent.url);
  if (_ttsCurrent.btn) {
    _ttsCurrent.btn.classList.remove('playing');
    _ttsCurrent.btn.textContent = '🔊 朗读';
  }
  _ttsCurrent = null;
}

async function aiPlayTts(text, btn) {
  if (!aiCanTts() || !text) return;
  // Stop any current playback first.
  _ttsStop();
  // Dedupe rapid double-clicks while the audio is still downloading.
  if (_ttsLoading === text) return;
  _ttsLoading = text;
  if (btn) {
    btn.classList.add('playing');
    btn.textContent = '⏳ 生成…';
  }
  try {
    const r = await fetch('/api/ai/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.slice(0, 4000) }),
    });
    if (_ttsLoading !== text) return;  // user clicked another in the meantime
    if (!r.ok) {
      const t = await r.text().catch(() => '');
      alert('TTS 失败：HTTP ' + r.status + ' ' + t.slice(0, 200));
      return;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    _ttsCurrent = { audio, url, btn };
    if (btn) btn.textContent = '⏹ 停止';
    audio.addEventListener('ended', () => _ttsStop());
    audio.addEventListener('error', () => _ttsStop());
    await audio.play().catch(err => {
      console.error('audio play failed', err);
      _ttsStop();
    });
  } catch (err) {
    alert('TTS 出错: ' + (err.message || err));
    _ttsStop();
  } finally {
    if (_ttsLoading === text) _ttsLoading = null;
  }
}

// ---------- AI panel dock/float + width persistence ----------
function _applyAiMode() {
  const mode = localStorage.getItem(AI_LS.mode) || 'dock';
  mainBodyEl.classList.toggle('float-mode', mode === 'float');
  aiDockToggle.title = mode === 'dock'
    ? '点击切换为浮层模式（不挤压主区）'
    : '点击切换为侧栏模式（挤压主区）';
  aiDockToggle.textContent = mode === 'dock' ? '⇆' : '◧';
}
function _applyAiWidth() {
  const w = parseInt(localStorage.getItem(AI_LS.width) || '', 10);
  if (Number.isFinite(w) && w >= 280 && w <= 900) {
    aiPanel.style.width = w + 'px';
  }
}
_applyAiMode();
_applyAiWidth();

async function aiOpenPanel() {
  // Refuse to open if AI not configured — give the user a clear, copyable hint
  if (!aiCanText()) {
    alert(
      'AI 尚未启用。\n\n' +
      '1) 复制 config.example.json 里的 ai 块到你的 config.json\n' +
      '2) 设置环境变量 MINIMAX_API_KEY（在 start.bat 加 set ... 或者系统设置）\n' +
      '3) 重启服务'
    );
    return;
  }
  aiPanel.hidden = false;
  // Only show the resizer when docked.
  aiResizer.hidden = mainBodyEl.classList.contains('float-mode');
  // Lazy eligibility fetch — runs in background, doesn't block panel open
  if (!aiEligibilityCache && currentPath) {
    loadEligibility(currentPath).then(() => {
      renderEligibilityNotice();
      updateAiButton();
    });
  }
  setTimeout(() => aiInput.focus(), 50);
}
function aiClosePanel() {
  aiPanel.hidden = true;
  aiResizer.hidden = true;
}

aiDockToggle.addEventListener('click', () => {
  const cur = localStorage.getItem(AI_LS.mode) || 'dock';
  const next = cur === 'dock' ? 'float' : 'dock';
  localStorage.setItem(AI_LS.mode, next);
  _applyAiMode();
  // re-evaluate resizer visibility
  if (!aiPanel.hidden) {
    aiResizer.hidden = next === 'float';
  }
});

// AI panel resize handle
(function setupAiResizer() {
  let dragging = false;
  aiResizer.addEventListener('mousedown', (e) => {
    if (aiPanel.hidden) return;
    dragging = true;
    document.body.classList.add('resizing');
    aiResizer.classList.add('dragging');
    e.preventDefault();
  });
  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const rect = mainBodyEl.getBoundingClientRect();
    // panel sits at the right; width = rect.right - mouseX
    const w = Math.max(280, Math.min(900, rect.right - e.clientX));
    aiPanel.style.width = w + 'px';
  });
  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('resizing');
    aiResizer.classList.remove('dragging');
    try {
      localStorage.setItem(AI_LS.width,
        String(aiPanel.getBoundingClientRect().width | 0));
    } catch {}
  });
})();

aiBtn.addEventListener('click', aiOpenPanel);
aiClose.addEventListener('click', aiClosePanel);
aiSend.addEventListener('click', aiSendQuestion);
aiInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    aiSendQuestion();
  } else if (e.key === 'Escape') {
    aiClosePanel();
  }
});
aiSummarize.addEventListener('click', aiDoSummarize);
aiClear.addEventListener('click', aiClearConv);
aiTtsLast.addEventListener('click', () => {
  // Toolbar 朗读 toggles: if anything is currently playing, stop. Otherwise
  // play the latest AI message.
  if (_ttsCurrent) { _ttsStop(); return; }
  const last = [...aiConv.querySelectorAll('.ai-msg.assistant .msg-body')].pop();
  if (last) aiPlayTts(last.dataset.raw || '', aiTtsLast);
});

document.addEventListener('keydown', (e) => {
  const ae = document.activeElement;
  if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) return;
  if (e.key === 'a' || e.key === 'A') {
    if (!currentPath) return;
    e.preventDefault();
    if (aiPanel.hidden) aiOpenPanel(); else aiClosePanel();
  }
});

// Called after each openFile completes. Intentionally cheap — does NOT
// hit any API. Eligibility is loaded lazily inside aiOpenPanel().
function onFileSelected(path) {
  aiEligibilityCache = null;     // stale; will reload when needed
  aiEligibility.textContent = '';
  updateAiButton();
}

(async () => {
  await fetchAiStatus();
  renderProviderInfo();
  updateAiButton();
})();

// =====================================================================
// Sidebar cache footer + details popover
// =====================================================================
const cacheFooterBtn  = document.getElementById('cache-footer-btn');
const cacheFooterSize = document.getElementById('cache-footer-size');
const cachePop        = document.getElementById('cache-pop');
const cachePopClose   = document.getElementById('cache-pop-close');
const cachePopTable   = document.getElementById('cache-pop-table');
const cacheCleanupBtn = document.getElementById('cache-cleanup-btn');
const cacheClearPdfBtn = document.getElementById('cache-clear-pdf-btn');
const cacheClearTtsBtn = document.getElementById('cache-clear-tts-btn');

function fmtBytes(n) {
  if (!n) return '0 B';
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB';
  return (n / 1024 / 1024 / 1024).toFixed(2) + ' GB';
}

async function fetchCacheStats() {
  try {
    const r = await fetch('/api/cache/stats');
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function renderCacheFooter(stats) {
  if (!stats) { cacheFooterSize.textContent = '—'; return; }
  cacheFooterSize.textContent = '已用 ' + fmtBytes(stats.total_bytes || 0);
}

function renderCachePopTable(stats) {
  if (!stats) { cachePopTable.innerHTML = ''; return; }
  const rows = [
    { label: '📕 Office → PDF', s: stats.office_pdf, useLimit: true },
    { label: '🔊 TTS 音频',     s: stats.tts_audio, useLimit: true },
    { label: '🔍 全文索引',     s: stats.search_index, useLimit: false },
    { label: '📜 日志',         s: stats.logs, useLimit: false },
  ];
  let html = '<thead><tr><th>类别</th><th class="size">大小</th><th>占用</th></tr></thead><tbody>';
  for (const r of rows) {
    const used = r.s.bytes || 0;
    const limit = r.useLimit ? (r.s.limit_bytes || 0) : 0;
    const ratio = limit ? Math.min(1, used / limit) : 0;
    const over = limit && used > limit * 0.85;
    let bar = '';
    if (limit) {
      bar = `<div class="bar${over ? ' over' : ''}"><span style="width:${(ratio*100).toFixed(1)}%"></span></div>
             <div style="font-size:10px;color:#aaa">上限 ${fmtBytes(limit)}</div>`;
    }
    html += `<tr><td>${r.label}<div style="font-size:10px;color:#aaa">${r.s.files} 个文件</div></td>` +
            `<td class="size">${fmtBytes(used)}</td>` +
            `<td class="bar-cell">${bar}</td></tr>`;
  }
  html += `<tr><td><strong>合计</strong></td><td class="size"><strong>${fmtBytes(stats.total_bytes || 0)}</strong></td><td></td></tr>`;
  html += '</tbody>';
  cachePopTable.innerHTML = html;
}

async function refreshCacheUi() {
  const stats = await fetchCacheStats();
  renderCacheFooter(stats);
  if (!cachePop.hidden) renderCachePopTable(stats);
  return stats;
}

cacheFooterBtn.addEventListener('click', async (e) => {
  e.stopPropagation();
  cachePop.hidden = !cachePop.hidden;
  if (!cachePop.hidden) await refreshCacheUi();
});
cachePopClose.addEventListener('click', () => { cachePop.hidden = true; });
document.addEventListener('click', (e) => {
  if (cachePop.hidden) return;
  if (cachePop.contains(e.target) || e.target === cacheFooterBtn) return;
  cachePop.hidden = true;
});

async function _busyAround(btn, label, fn) {
  const orig = btn.textContent;
  btn.disabled = true; btn.textContent = label;
  try { return await fn(); }
  finally { btn.disabled = false; btn.textContent = orig; }
}

cacheCleanupBtn.addEventListener('click', async () => {
  await _busyAround(cacheCleanupBtn, '清理中…', async () => {
    const r = await fetch('/api/cache/cleanup', { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    const a = (d.office_pdf || {}).removed || 0;
    const b = (d.tts_audio  || {}).removed || 0;
    alert(`已清理：PDF ${a} 项 / TTS ${b} 项`);
    await refreshCacheUi();
  });
});

cacheClearPdfBtn.addEventListener('click', async () => {
  if (!confirm('完全清空 Office→PDF 缓存？下次打开 doc/docx/xlsx 等会重新转换（慢一次）。')) return;
  await _busyAround(cacheClearPdfBtn, '清空中…', async () => {
    const r = await fetch('/api/cache/clear', { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    alert(`已清空：${d.removed || 0} 项${d.skipped ? `（${d.skipped} 项被占用未删）` : ''}`);
    await refreshCacheUi();
  });
});

cacheClearTtsBtn.addEventListener('click', async () => {
  if (!confirm('完全清空 TTS 音频缓存？下次朗读会重新调用 API（花一次 token）。')) return;
  await _busyAround(cacheClearTtsBtn, '清空中…', async () => {
    const r = await fetch('/api/ai/tts/clear', { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    alert(`已清空：${d.removed || 0} 项`);
    await refreshCacheUi();
  });
});

// Initial fetch + refresh every 30s while window is visible.
refreshCacheUi();
setInterval(() => {
  if (document.visibilityState === 'visible') refreshCacheUi();
}, 30_000);

bootstrap().catch(err => {
  treeEl.innerHTML = `<div style="padding:12px;color:#b00">加载失败：${escapeHtml(String(err))}</div>`;
});
