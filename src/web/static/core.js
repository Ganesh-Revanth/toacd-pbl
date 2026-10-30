'use strict';
/* core.js — DOM helpers, API client, editor, diff view, tabs, shared state. No dependencies. */

const $ = (sel, root = document) => root.querySelector(sel);

/* append/prepend/replaceChildren would print "false", "null" or "[object ...]" for conditional children.
   Make them behave like el(): flatten arrays and skip null / undefined / false. */
(function () {
  const clean = (kids) => kids.flat(Infinity).filter(k => k != null && k !== false);
  for (const m of ['append', 'prepend', 'replaceChildren']) {
    const orig = Element.prototype[m];
    Element.prototype[m] = function (...kids) { return orig.apply(this, clean(kids)); };
  }
})();

/** Build a DOM node. Text is always inserted as text (never HTML), so code and diagnostics cannot inject markup. */
function el(tag, props, ...kids) {
  const n = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v == null || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2).toLowerCase(), v);
      else if (v === true) n.setAttribute(k, '');
      else n.setAttribute(k, v);
    }
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    n.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return n;
}
const SVGNS = 'http://www.w3.org/2000/svg';
function svg(tag, attrs, ...kids) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) n.setAttribute(k, v);
  for (const c of kids.flat(Infinity)) if (c != null) n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
}

function announce(msg) { const l = $('#live'); if (l) { l.textContent = ''; setTimeout(() => { l.textContent = msg; }, 30); } }

/* ── API ─────────────────────────────────────────────────────────────── */
async function call(path, body) {
  const opt = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  let r;
  try { r = await fetch(path, opt); } catch (e) { throw new Error('Cannot reach the local server. Is it still running?'); }
  let d;
  try { d = await r.json(); } catch (e) { throw new Error('The server sent an unexpected response.'); }
  if (!r.ok) throw new Error(d.error || ('Request failed (' + r.status + ')'));
  return d;
}

/** Disable buttons and show a busy state while an async job runs. Always restores them. */
async function busy(buttons, fn) {
  const list = [].concat(buttons).filter(Boolean);
  const before = list.map(b => b.disabled);       // restore exactly what each button was
  list.forEach(b => { b.disabled = true; });
  const main = list[0];
  if (main) main.setAttribute('aria-busy', 'true');
  try { return await fn(); }
  finally {
    list.forEach((b, i) => { b.disabled = before[i]; });
    if (main) main.removeAttribute('aria-busy');
  }
}

const notice = (kind, ...kids) => el('div', { class: 'notice ' + kind, role: kind === 'bad' ? 'alert' : 'status' }, ...kids);

/* ── Persistent-ish state ────────────────────────────────────────────── */
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage unavailable: fine */ } },
};

const state = {
  status: null,
  samples: [],
  cpp: { code: '', result: null, pending: null, lastCheckedCode: null },
  minic: { code: '', pipeline: null, pipelineFor: null },
  proposals: store.get('proposals', []),
  nextId: store.get('nextId', 1),
};
function saveProposals() {
  store.set('proposals', state.proposals.slice(-30));
  store.set('nextId', state.nextId);
}

/* ── Code editor ─────────────────────────────────────────────────────── */
function Editor({ value = '', label, onChange, onRun, onCursor }) {
  const gutter = el('div', { class: 'gutter', 'aria-hidden': 'true' });
  const ta = el('textarea', {
    class: 'code-area', spellcheck: 'false', wrap: 'off', autocapitalize: 'off',
    autocomplete: 'off', autocorrect: 'off', 'aria-label': label,
  });
  ta.value = value;
  const root = el('div', { class: 'editor' }, gutter, ta);
  let marks = {};
  let tabEscape = false;

  function paint() {
    const n = ta.value.split('\n').length;
    gutter.replaceChildren();
    for (let i = 1; i <= n; i++) gutter.append(el('span', { class: marks[i] || '', text: String(i) }));
    gutter.scrollTop = ta.scrollTop;
  }
  ta.addEventListener('input', () => { paint(); onChange && onChange(ta.value); });
  ta.addEventListener('scroll', () => { gutter.scrollTop = ta.scrollTop; });
  ta.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); onRun && onRun(e); return; }
    if (e.key === 'Escape') { tabEscape = true; return; }
    if (e.key === 'Tab' && !e.shiftKey && !tabEscape) {
      e.preventDefault();
      const s = ta.selectionStart, t = ta.selectionEnd;
      ta.setRangeText('    ', s, t, 'end');
      ta.dispatchEvent(new Event('input'));
    }
    if (e.key !== 'Tab' && e.key !== 'Escape') tabEscape = false;
  });
  const reportCursor = () => {
    if (!onCursor) return;
    const pos = ta.selectionStart, before = ta.value.slice(0, pos);
    onCursor(before.split('\n').length, pos - before.lastIndexOf('\n'));
  };
  ['keyup', 'click', 'focus', 'input'].forEach(ev => ta.addEventListener(ev, reportCursor));
  paint();

  return {
    root, textarea: ta,
    focus: () => ta.focus(),
    get: () => ta.value,
    set(v) { ta.value = v; paint(); onChange && onChange(v); },
    mark(map) { marks = map || {}; paint(); },
    goto(line) {
      const lines = ta.value.split('\n');
      if (line < 1 || line > lines.length) return;
      let start = 0;
      for (let i = 0; i < line - 1; i++) start += lines[i].length + 1;
      ta.focus();
      ta.setSelectionRange(start, start + lines[line - 1].length);
      ta.scrollTop = Math.max(0, (line - 4) * 20);
    },
  };
}

/* ── Diff view ───────────────────────────────────────────────────────── */
function DiffView(lines) {
  if (!lines || !lines.some(l => l.kind !== ' ')) return el('p', { class: 'muted', text: 'No differences.' });
  const rows = lines.map(l => el('tr', { class: l.kind === '+' ? 'add' : l.kind === '-' ? 'del' : '' },
    el('td', { class: 'ln', text: l.old ?? '' }),
    el('td', { class: 'ln', text: l.new ?? '' }),
    el('td', { class: 'sign', text: l.kind === ' ' ? '' : l.kind, 'aria-label': l.kind === '+' ? 'added' : l.kind === '-' ? 'removed' : 'unchanged' }),
    el('td', { class: 'txt', text: l.text }),
  ));
  return el('div', { class: 'diff-wrap', role: 'region', 'aria-label': 'Changes', tabindex: '0' }, el('table', { class: 'diff' }, el('tbody', null, rows)));
}
const diffStats = (lines) => ({
  add: (lines || []).filter(l => l.kind === '+').length,
  del: (lines || []).filter(l => l.kind === '-').length,
});

/* ── Tabs (keyboard accessible) ──────────────────────────────────────── */
function Tabs(items, initial) {
  const list = el('div', { class: 'tabs', role: 'tablist' });
  const panel = el('div', { class: 'tabpanel', role: 'tabpanel', tabindex: '0' });
  let current = initial || items[0].id;
  const btns = {};
  function select(id, focus) {
    current = id;
    for (const it of items) btns[it.id].setAttribute('aria-selected', String(it.id === id)), btns[it.id].tabIndex = it.id === id ? 0 : -1;
    const it = items.find(x => x.id === id);
    panel.replaceChildren(it.render());
    panel.setAttribute('aria-labelledby', 'tab-' + id);
    if (focus) btns[id].focus();
  }
  items.forEach((it, i) => {
    const b = el('button', { class: 'tab', role: 'tab', id: 'tab-' + it.id, onClick: () => select(it.id) }, it.label);
    b.addEventListener('keydown', (e) => {
      const k = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (k) { e.preventDefault(); select(items[(i + k + items.length) % items.length].id, true); }
    });
    btns[it.id] = b; list.append(b);
  });
  select(current);
  return { list, panel, select, refresh: () => select(current), get current() { return current; } };
}

/* ── Small shared pieces ─────────────────────────────────────────────── */
const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : /(ch|s|x)$/.test(w) ? 'es' : 's');
const pct = (v) => (v == null ? '—' : v.toFixed(1) + '%');
function timeLabel(ts) { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }

function SamplePicker(language, onPick) {
  const sel = el('select', { 'aria-label': 'Load an example' },
    el('option', { value: '', text: 'Load an example…' }),
    state.samples.filter(s => s.language === language).map((s, i) => el('option', { value: String(i), text: s.name })));
  sel.addEventListener('change', () => {
    if (sel.value === '') return;
    onPick(state.samples.filter(s => s.language === language)[Number(sel.value)]);
    sel.value = '';
  });
  return sel;
}

/** LCS line diff for short instruction lists. Returns {removed:Set(indices in a), added:Set(indices in b)}. */
function lcsMarks(a, b) {
  const n = a.length, m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const removed = new Set(), added = new Set();
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) removed.add(i++);
    else added.add(j++);
  }
  while (i < n) removed.add(i++);
  while (j < m) added.add(j++);
  return { removed, added };
}

function IRList(texts, marks, cls) {
  return el('pre', { class: 'ir', tabindex: '0', 'aria-label': 'Instruction list' },
    texts.map((t, i) => el('div', { class: marks && marks.has(i) ? cls : '' }, el('span', { text: String(i) }), el('span', { text: t }))));
}

/* ── Loading and saving files ────────────────────────────────────────── */
const MAX_FILE_BYTES = 200000;   // matches the server's 200 KB source limit

/** Read a user-chosen file as text, with friendly errors. Calls onLoad(text, name) or onError(message). */
async function handleFile(file, onLoad, onError) {
  const fail = (m) => { (onError || announce)(m); };
  if (file.size > MAX_FILE_BYTES) return fail('“' + file.name + '” is ' + Math.round(file.size / 1000) + ' KB. The limit is 200 KB.');
  let text;
  try { text = await file.text(); } catch (e) { return fail('Could not read “' + file.name + '”.'); }
  if (text.includes('\u0000')) return fail('“' + file.name + '” does not look like a text file.');
  onLoad(text.replace(/\r\n?/g, '\n'), file.name);
}

/** A button that opens the system file picker. */
function FileLoader({ accept, label = 'Open file', onLoad, onError }) {
  const input = el('input', { type: 'file', accept, hidden: true, tabindex: '-1', 'aria-hidden': 'true' });
  const btn = el('button', { class: 'btn', type: 'button', title: 'Open a file from your computer (or drop it on the editor)', onClick: () => input.click() }, label);
  input.addEventListener('change', () => { const f = input.files[0]; input.value = ''; if (f) handleFile(f, onLoad, onError); });
  return el('span', { class: 'file-loader' }, btn, input);
}

/** Let the user drop a file onto `node`. Adds .dropping while a file is dragged over it. */
function enableFileDrop(node, onLoad, onError) {
  const hasFiles = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files');
  let depth = 0;
  node.addEventListener('dragenter', (e) => { if (!hasFiles(e)) return; e.preventDefault(); depth++; node.classList.add('dropping'); });
  node.addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
  node.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) node.classList.remove('dropping'); });
  node.addEventListener('drop', (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth = 0; node.classList.remove('dropping');
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f, onLoad, onError);
  });
}

/** Save text to the user's computer as a file. */
function downloadText(name, text, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = el('a', { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* Close any open dropdown menu when clicking elsewhere or pressing Escape. */
document.addEventListener('click', (e) => {
  document.querySelectorAll('details.menu[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; });
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') document.querySelectorAll('details.menu[open]').forEach(d => { d.open = false; d.querySelector('summary')?.focus(); });
});
