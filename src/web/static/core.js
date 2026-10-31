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
  proposals: store.get('proposals', []),
  nextId: store.get('nextId', 1),
};
function saveProposals() {
  store.set('proposals', state.proposals.slice(-30));
  store.set('nextId', state.nextId);
}

/* ── Files: open, save, drop ─────────────────────────────────────────── */
const MAX_FILE_BYTES = 500 * 1024;
function readTextFile(file) {
  return new Promise((resolve, reject) => {
    if (file.size > MAX_FILE_BYTES) { reject(new Error(file.name + ' is larger than 500 KB. Open a smaller source file.')); return; }
    const r = new FileReader();
    r.onload = () => {
      const t = String(r.result);
      if (t.includes('\u0000')) { reject(new Error(file.name + ' looks like a binary file, not source code.')); return; }
      resolve({ name: file.name, text: t.replace(/\r\n/g, '\n') });
    };
    r.onerror = () => reject(new Error('Could not read ' + file.name + '.'));
    r.readAsText(file);
  });
}
function pickFile(accept) {
  return new Promise((resolve) => {
    const inp = el('input', { type: 'file', accept: accept || '', hidden: true });
    inp.addEventListener('change', () => { resolve(inp.files[0] || null); inp.remove(); });
    inp.addEventListener('cancel', () => { resolve(null); inp.remove(); });
    document.body.append(inp); inp.click();
  });
}
function saveTextFile(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const a = el('a', { href: url, download: name, hidden: true });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ── Syntax colouring (display only; the textarea stays the source of truth) ─ */
const CPP_KW = new Set('alignas auto bool break case catch char class const constexpr continue default delete do double else enum explicit extern false float for friend goto if inline int long namespace new noexcept nullptr operator private protected public return short signed sizeof static struct switch template this throw true try typedef typename union unsigned using virtual void volatile while'.split(' '));
const TOKEN_RE = /(\/\/[^\n]*|\/\*[\s\S]*?(?:\*\/|$))|("(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?)|(^[ \t]*#[^\n]*)|(\b\d[\w.]*)|([A-Za-z_]\w*)/gm;
function highlight(code) {
  const kw = CPP_KW;
  const frag = document.createDocumentFragment();
  if (code.length > 200000) { frag.append(code); return frag; }
  let last = 0, m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(code))) {
    if (m[0] === '') { TOKEN_RE.lastIndex++; continue; }
    if (m.index > last) frag.append(code.slice(last, m.index));
    let cls = null;
    if (m[1]) cls = 'c'; else if (m[2]) cls = 's'; else if (m[3]) cls = 'p'; else if (m[4]) cls = 'n';
    else if (m[5] && kw.has(m[5])) cls = 'k';
    frag.append(cls ? el('span', { class: 'hl-' + cls, text: m[0] }) : m[0]);
    last = m.index + m[0].length;
  }
  if (last < code.length) frag.append(code.slice(last));
  return frag;
}

/* ── Code editor ─────────────────────────────────────────────────────── */
function Editor({ value = '', label, lang = 'cpp', onChange, onRun, onCursor, onFile, accept }) {
  const gutter = el('div', { class: 'gutter', 'aria-hidden': 'true' });
  const paintLayer = el('pre', { class: 'code-paint', 'aria-hidden': 'true' });
  const ta = el('textarea', {
    class: 'code-area', spellcheck: 'false', wrap: 'off', autocapitalize: 'off',
    autocomplete: 'off', autocorrect: 'off', 'aria-label': label,
  });
  ta.value = value;
  const dropHint = el('div', { class: 'drop-hint', 'aria-hidden': 'true' }, 'Drop a file to open it');
  const root = el('div', { class: 'editor' }, gutter, el('div', { class: 'code-wrap' }, paintLayer, ta), dropHint);
  let marks = {};
  let tabEscape = false;

  function paint() {
    const lines = ta.value.split('\n');
    gutter.replaceChildren();
    for (let i = 1; i <= lines.length; i++) gutter.append(el('span', { class: marks[i] || '', text: String(i) }));
    paintLayer.replaceChildren(highlight(ta.value, lang), '\n');
    sync();
  }
  function sync() {
    gutter.scrollTop = ta.scrollTop;
    paintLayer.style.transform = 'translate(' + (-ta.scrollLeft) + 'px,' + (-ta.scrollTop) + 'px)';
  }
  function cursor() {
    if (!onCursor) return;
    const pos = ta.selectionStart, before = ta.value.slice(0, pos).split('\n');
    onCursor({ line: before.length, col: before[before.length - 1].length + 1, selected: Math.abs(ta.selectionEnd - ta.selectionStart) });
  }
  ta.addEventListener('input', () => { paint(); onChange && onChange(ta.value); cursor(); });
  ta.addEventListener('scroll', sync);
  for (const ev of ['keyup', 'click', 'select', 'focus']) ta.addEventListener(ev, cursor);
  ta.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); onRun && onRun(); return; }
    if (e.key === 'Escape') { tabEscape = true; return; }
    if (e.key === 'Tab' && !e.shiftKey && !tabEscape) {
      e.preventDefault();
      ta.setRangeText('    ', ta.selectionStart, ta.selectionEnd, 'end');
      ta.dispatchEvent(new Event('input'));
    }
    if (e.key !== 'Tab' && e.key !== 'Escape') tabEscape = false;
  });

  // Drag and drop a file onto the editor.
  let depth = 0;
  const hasFiles = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');
  root.addEventListener('dragenter', (e) => { if (hasFiles(e)) { e.preventDefault(); depth++; root.classList.add('dropping'); } });
  root.addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
  root.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) root.classList.remove('dropping'); });
  root.addEventListener('drop', async (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth = 0; root.classList.remove('dropping');
    const f = e.dataTransfer.files[0];
    if (!f) return;
    try { const r = await readTextFile(f); onFile && onFile(r); }
    catch (err) { onFile && onFile({ error: err.message }); }
  });
  paint();

  return {
    root, textarea: ta,
    get: () => ta.value,
    set(v) { ta.value = v; marks = {}; paint(); onChange && onChange(v); cursor(); },
    mark(map) { marks = map || {}; paint(); },
    focus() { ta.focus(); },
    goto(line) {
      const lines = ta.value.split('\n');
      if (line < 1 || line > lines.length) return;
      let start = 0;
      for (let i = 0; i < line - 1; i++) start += lines[i].length + 1;
      ta.focus();
      ta.setSelectionRange(start, start + lines[line - 1].length);
      ta.scrollTop = Math.max(0, (line - 4) * 20);
      sync(); cursor();
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
    el('option', { value: '', text: 'Examples…' }),
    state.samples.filter(s => s.language === language).map((s, i) => el('option', { value: String(i), text: s.name })));
  sel.addEventListener('change', () => {
    if (sel.value === '') return;
    onPick(state.samples.filter(s => s.language === language)[Number(sel.value)]);
    sel.value = '';
  });
  return sel;
}
