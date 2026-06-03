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
  const d = await r.json();
  rootPathEl.textContent = d.root;
  rootPathEl.title = d.root;
  currentRootKey = d.root || '';
  return d;
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
  treeEl.innerHTML = '加载中…';
  const r = await fetch('/api/tree?recursive=1');
  const data = await r.json();
  pathToLi = new Map();
  pathToDirLi = new Map();
  treeEl.innerHTML = '';
  const openSet = loadOpenDirSet();
  treeEl.appendChild(renderNodes(data.children, openSet));
}

async function loadDirChildren(li, sub) {
  if (li.dataset.loaded === '1') return;
  li.dataset.loading = '1';
  try {
    const r = await fetch('/api/tree?path=' + encodeURIComponent(li.dataset.dirPath || ''));
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
  // Update star/tag badges for all rendered file items based on annoCache
  const badgeNodes = treeEl.querySelectorAll('[data-badge-for]');
  badgeNodes.forEach(node => {
    const path = node.getAttribute('data-badge-for');
    const a = (annoCache.files || {})[path] || {};
    let html = '';
    if (a.starred) html += '<span class="badge-star">★</span>';
    if (Array.isArray(a.tags)) {
      a.tags.forEach(t => { html += `<span class="badge-tag">${escapeHtml(t)}</span>`; });
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

  viewerEl.innerHTML = '<div class="loading">加载中…</div>';
  viewerEl.scrollTop = 0;

  // For office files, poll preconvert status and surface the queue
  // situation so the user knows why it's slow.
  const isOffice = /\.(doc|docx|xls|xlsx|ppt|pptx|odt|ods|odp|rtf)$/i.test(node.path);
  let pollTimer = null;
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
    updateLoading();
    pollTimer = setInterval(updateLoading, 1500);
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

pickBtn.addEventListener('click', async () => {
  pickBtn.disabled = true;
  pickBtn.textContent = '选择中…';
  try {
    const r = await fetch('/api/pick-folder', { method: 'POST' });
    const d = await r.json();
    if (!d.path) return;
    const r2 = await fetch('/api/root', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: d.path }),
    });
    if (!r2.ok) {
      const j = await r2.json().catch(() => ({}));
      alert('切换目录失败：' + (j.detail || r2.status));
      return;
    }
    resetWorkspaceView();
    await bootstrap();
  } catch (err) {
    alert('切换目录出错：' + err);
  } finally {
    pickBtn.disabled = false;
    pickBtn.textContent = '📁 切换';
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
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      alert('打开失败：' + (j.detail || r.status));
    }
  } catch (err) {
    alert('打开出错：' + err);
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
  annoCache = await r.json();
  refreshAllBadges();
  if (currentPath) renderAnnoBar();  // refresh anno panel for already-open file
}

async function patchAnno(path, partial) {
  const r = await fetch('/api/anno?path=' + encodeURIComponent(path), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(partial),
  });
  if (!r.ok) throw new Error('save failed: ' + r.status);
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

starBtn.addEventListener('click', toggleStar);

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

async function bootstrap() {
  const info = await refreshRoot();
  await loadTree();
  await loadAnno();
  if (info.last_file) {
    setTimeout(() => openFileByPath(info.last_file), 0);
  }
  pollPreconvert();
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
      try { it.action(); } catch (e) { console.error(e); }
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
        await fetch('/api/reveal', { method: 'POST', headers: {'Content-Type':'application/json'},
                                     body: JSON.stringify({ path }) });
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
  searchResultsEl.innerHTML = `<div class="sr-head"><span>搜索中…</span><button id="sr-close">× 返回</button></div>`;
  document.getElementById('sr-close').addEventListener('click', () => {
    searchInput.value = '';
    showTreeView();
  });
  try {
    const r = await fetch('/api/search?q=' + encodeURIComponent(q) + '&limit=80');
    const d = await r.json();
    renderSearchResults(d, q);
  } catch (err) {
    searchResultsEl.innerHTML = `<div class="sr-head"><span>搜索失败：${escapeHtml(String(err))}</span><button id="sr-close">× 返回</button></div>`;
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

bootstrap().catch(err => {
  treeEl.innerHTML = `<div style="padding:12px;color:#b00">加载失败：${escapeHtml(String(err))}</div>`;
});
