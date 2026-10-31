'use strict';
/* ast-graph.js — a node-and-edge syntax tree viewer.
   Pan (drag), zoom (wheel / buttons), collapse subtrees, search, keyboard navigation, export to SVG.
   Input is the normalised tree {role, label, meta, pos, line, endLine, children[]} produced in pages-compiler.js. */

/* ── Node categories (colour-coded) ──────────────────────────────────── */
const AST_KINDS = {
  decl:  { name: 'Declarations', hint: 'functions, variables, classes' },
  stmt:  { name: 'Statements', hint: 'if, loops, return, blocks' },
  expr:  { name: 'Expressions', hint: 'operators, calls, names' },
  lit:   { name: 'Literals', hint: 'numbers, strings, true/false' },
  other: { name: 'Other', hint: '' },
};
function astKind(type) {
  if (/Literal|^CXXBoolLiteralExpr$|^CXXNullPtrLiteralExpr$/.test(type)) return 'lit';
  if (/Stmt$|^(Block|If|While|For|Return|Print|Assign|Do|Switch|Case|Default|Break|Continue)$/.test(type)) return 'stmt';
  if (/Decl$|^(Program|FunctionDef|VarDecl|TranslationUnit|Translation unit)$/.test(type)) return 'decl';
  if (/Expr$|Operator$|^(BinaryOp|UnaryOp|Call|Identifier)$/.test(type)) return 'expr';
  return 'other';
}

/* ── Model ───────────────────────────────────────────────────────────── */
let astUid = 0;
function astModel(n, parent) {
  const m = {
    id: ++astUid, type: n.label, role: n.role || '', details: n.meta || '', pos: n.pos || '',
    line: n.line || null, endLine: n.endLine || n.line || null,
    kind: astKind(n.label), parent, children: [], collapsed: false,
  };
  m.children = (n.children || []).map(c => astModel(c, m));
  m.size = 1 + m.children.reduce((a, c) => a + c.size, 0);
  return m;
}
function astEach(n, fn) { fn(n); n.children.forEach(c => astEach(c, fn)); }
function astPath(n) { const p = []; for (let x = n; x; x = x.parent) p.unshift(x); return p; }

/* ── Layout ──────────────────────────────────────────────────────────── */
const AG = { H: 46, GAP_C: 16, GAP_D: 52, MIN_W: 92, MAX_W: 236, PAD: 40 };

function astNodeWidth(n) {
  const detail = Math.min(n.details.length, 30);
  return Math.round(Math.max(AG.MIN_W, Math.min(AG.MAX_W, Math.max(n.type.length * 8.2, detail * 6.7) + 28)));
}
function astDetailText(n) { return n.details.length > 30 ? n.details.slice(0, 29) + '…' : n.details; }

/** Assign x/y to every visible node. Returns {width, height, nodes[], edges[]}. */
function astLayout(root, orient, levelGap = AG.GAP_D + 20) {
  const td = orient === 'td';
  const nodes = [], edges = [];
  const cross = (n) => td ? n.w : AG.H;
  const measure = (n, depth) => {
    n.w = astNodeWidth(n); n.depth = depth;
    n.vis = n.collapsed ? [] : n.children;
    n.vis.forEach(c => measure(c, depth + 1));
    n.kidsExt = n.vis.reduce((a, c) => a + c.ext, 0) + Math.max(0, n.vis.length - 1) * AG.GAP_C;
    n.ext = Math.max(n.kidsExt, cross(n));
  };
  measure(root, 0);

  const levelW = [];
  const levels = (n) => { levelW[n.depth] = Math.max(levelW[n.depth] || 0, n.w); n.vis.forEach(levels); };
  levels(root);
  const levelX = []; let acc = 0;
  levelW.forEach((w, d) => { levelX[d] = acc; acc += w + levelGap; });

  const place = (n, start) => {
    const mid = start + n.ext / 2;
    if (td) { n.x = mid - n.w / 2; n.y = n.depth * (AG.H + AG.GAP_D); }
    else { n.x = levelX[n.depth]; n.y = mid - AG.H / 2; }
    nodes.push(n);
    let at = start + (n.ext - n.kidsExt) / 2;
    n.vis.forEach(c => { place(c, at); at += c.ext + AG.GAP_C; edges.push({ from: n, to: c }); });
  };
  place(root, 0);

  let maxX = 0, maxY = 0;
  nodes.forEach(n => { maxX = Math.max(maxX, n.x + n.w); maxY = Math.max(maxY, n.y + AG.H); });
  return { width: maxX, height: maxY, nodes, edges };
}

function astEdgePath(a, b, orient) {
  if (orient === 'td') {
    const x1 = a.x + a.w / 2, y1 = a.y + AG.H, x2 = b.x + b.w / 2, y2 = b.y, my = (y1 + y2) / 2;
    return `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;
  }
  const x1 = a.x + a.w, y1 = a.y + AG.H / 2, x2 = b.x, y2 = b.y + AG.H / 2, mx = (x1 + x2) / 2;
  return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
}

/* ── The viewer ──────────────────────────────────────────────────────── */
/**
 * ASTGraph(roots, opts) -> { root, select(id), setOrientation, search(q), exportSvg, ... }
 * opts: { onSelect(node|null), rootLabel, autoCollapseDepth }
 */
function ASTGraph(roots, opts = {}) {
  astUid = 0;
  const model = roots.length === 1 ? astModel(roots[0], null)
    : astModel({ label: opts.rootLabel || 'TranslationUnit', meta: '', children: roots }, null);
  const total = model.size;
  const all = []; astEach(model, n => all.push(n));
  const byId = new Map(all.map(n => [n.id, n]));
  const hasRoles = all.some(n => n.role);

  // Big trees start partly collapsed so the first view is readable.
  const limit = opts.autoCollapseDepth ?? (total > 160 ? 4 : total > 80 ? 6 : Infinity);
  astEach(model, n => { n.collapsed = n.children.length > 0 && astPath(n).length - 1 >= limit; });

  let orient = opts.orientation || 'td';
  let showRoles = hasRoles;
  let selected = null, query = '', matches = new Set();
  let view = { x: 0, y: 0, k: 1 };
  let layout = null;

  const gEdges = svg('g', { class: 'ag-edges' }), gLabels = svg('g', { class: 'ag-elabels' }), gNodes = svg('g', { class: 'ag-nodes' });
  const viewport = svg('g', { class: 'ag-viewport' }, gEdges, gLabels, gNodes);
  const canvas = svg('svg', { class: 'ag-canvas', role: 'group', 'aria-label': 'Syntax tree diagram. Drag to pan, scroll to zoom.', tabindex: '-1' }, viewport);
  const stage = el('div', { class: 'ag-stage' }, canvas);

  const apply = () => viewport.setAttribute('transform', `translate(${view.x},${view.y}) scale(${view.k})`);
  function size() { const r = canvas.getBoundingClientRect(); return { w: r.width || 800, h: r.height || 500 }; }

  /** Fit the whole tree in view. With `readable`, never shrink below a legible size: start at the root and let the user pan. */
  function fit(readable = false) {
    if (!layout) return;
    const { w, h } = size();
    const fitK = Math.min((w - 2 * AG.PAD) / layout.width, (h - 2 * AG.PAD) / layout.height, 1.15);
    const k = readable ? Math.max(fitK, 0.6) : fitK;
    view.k = Math.max(0.1, k);
    if (readable && k > fitK + 0.001) {
      view.x = AG.PAD;                                              // too big to fit: anchor at the root
      view.y = orient === 'td' ? AG.PAD : Math.max(AG.PAD * 0.5, h / 2 - (model.y + AG.H / 2) * view.k);
    } else {
      view.x = (w - layout.width * view.k) / 2;
      view.y = Math.max(AG.PAD * 0.6, (h - layout.height * view.k) / 2);
    }
    apply();
  }
  function zoomAt(factor, cx, cy) {
    const k = Math.min(3, Math.max(0.1, view.k * factor)), f = k / view.k;
    const { w, h } = size();
    cx = cx ?? w / 2; cy = cy ?? h / 2;
    view.x = cx - (cx - view.x) * f; view.y = cy - (cy - view.y) * f; view.k = k; apply();
  }
  function centerOn(n) {
    const { w, h } = size();
    view.x = w / 2 - (n.x + n.w / 2) * view.k; view.y = h / 2 - (n.y + AG.H / 2) * view.k; apply();
  }

  /* drawing */
  const pathSet = () => new Set(selected ? astPath(selected).map(n => n.id) : []);
  function draw() {
    // Edge labels need room between columns, or they collide with the fold buttons.
    layout = astLayout(model, orient, showRoles && hasRoles ? 124 : undefined);
    const onPath = pathSet(), searching = !!query;
    gEdges.replaceChildren(); gLabels.replaceChildren(); gNodes.replaceChildren();

    layout.edges.forEach(({ from, to }) => {
      gEdges.append(svg('path', { class: 'ag-edge' + (onPath.has(to.id) && onPath.has(from.id) ? ' on' : ''), d: astEdgePath(from, to, orient) }));
      if (showRoles && to.role) {
        const mx = orient === 'td' ? (from.x + from.w / 2 + to.x + to.w / 2) / 2 : (from.x + from.w + to.x) / 2;
        const my = orient === 'td' ? (from.y + AG.H + to.y) / 2 : (from.y + to.y) / 2 + AG.H / 2;
        gLabels.append(svg('text', { class: 'ag-elabel', x: mx, y: my + 3, 'text-anchor': 'middle' }, to.role));
      }
    });

    layout.nodes.forEach(n => {
      const cls = ['ag-node', 'k-' + n.kind];
      if (selected === n) cls.push('sel'); else if (onPath.has(n.id)) cls.push('path');
      if (searching) cls.push(matches.has(n.id) ? 'hit' : 'dim');
      const detail = astDetailText(n);
      const g = svg('g', { class: cls.join(' '), transform: `translate(${n.x},${n.y})`, tabindex: '0', role: 'button', 'data-id': n.id,
          'aria-label': n.type + (n.details ? ', ' + n.details : '') + (n.children.length ? ', ' + n.children.length + ' children, ' + (n.collapsed ? 'collapsed' : 'expanded') : ', no children') + (n.line ? ', line ' + n.line : '') },
        svg('title', {}, n.type + (n.details ? '\n' + n.details : '') + (n.line ? '\nline ' + n.line + (n.endLine && n.endLine !== n.line ? '–' + n.endLine : '') : '')),
        svg('rect', { class: 'ag-body', width: n.w, height: AG.H, rx: 8 }),
        svg('path', { class: 'ag-bar', d: `M8,0 H12 V${AG.H} H8 a8,8 0 0 1 -8,-8 V8 a8,8 0 0 1 8,-8 Z` }),
        svg('text', { class: 'ag-t1', x: 20, y: detail ? 19 : 28 }, n.type),
        detail ? svg('text', { class: 'ag-t2', x: 20, y: 35 }, detail) : null);
      if (n.children.length) {
        const tx = orient === 'td' ? n.w / 2 : n.w, ty = orient === 'td' ? AG.H : AG.H / 2;
        const label = n.collapsed ? '+' + (n.size - 1) : '−';
        const rw = Math.max(18, label.length * 7 + 10);
        const tog = svg('g', { class: 'ag-toggle', transform: `translate(${tx},${ty})`, 'data-toggle': n.id },
          svg('rect', { x: -rw / 2, y: -9, width: rw, height: 18, rx: 9 }), svg('text', { y: 4, 'text-anchor': 'middle' }, label));
        g.append(tog);
      }
      gNodes.append(g);
    });
    apply();
    if (opts.onChange) opts.onChange();
  }

  /* interactions */
  function select(n, { center = false, notify = true } = {}) {
    selected = n;
    if (n) { for (let p = n.parent; p; p = p.parent) p.collapsed = false; }
    draw();
    if (center && n) centerOn(n);
    if (notify && opts.onSelect) opts.onSelect(n);
    const f = n && gNodes.querySelector(`[data-id="${n.id}"]`);
    if (f && center) f.focus({ preventScroll: true });
  }
  function toggle(n) {
    if (!n.children.length) return;
    n.collapsed = !n.collapsed;
    if (n.collapsed && selected && astPath(selected).includes(n) && selected !== n) selected = n;
    draw();
    const f = gNodes.querySelector(`[data-id="${n.id}"]`); if (f) f.focus({ preventScroll: true });
  }

  let drag = null, moved = false;
  canvas.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || e.target.closest('.ag-node')) return;
    drag = { x: e.clientX - view.x, y: e.clientY - view.y }; moved = false;
    canvas.setPointerCapture(e.pointerId); canvas.classList.add('panning');
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!drag) return;
    moved = true; view.x = e.clientX - drag.x; view.y = e.clientY - drag.y; apply();
  });
  const endDrag = () => { drag = null; canvas.classList.remove('panning'); };
  canvas.addEventListener('pointerup', (e) => { if (drag && !moved) select(null); endDrag(); });
  canvas.addEventListener('pointercancel', endDrag);
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const r = canvas.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0016)), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  gNodes.addEventListener('click', (e) => {
    const tog = e.target.closest('.ag-toggle');
    if (tog) { e.stopPropagation(); toggle(byId.get(Number(tog.dataset.toggle))); return; }
    const g = e.target.closest('.ag-node'); if (g) select(byId.get(Number(g.dataset.id)));
  });
  gNodes.addEventListener('dblclick', (e) => { const g = e.target.closest('.ag-node'); if (g) toggle(byId.get(Number(g.dataset.id))); });
  gNodes.addEventListener('keydown', (e) => {
    const g = e.target.closest('.ag-node'); if (!g) return;
    const n = byId.get(Number(g.dataset.id));
    const down = orient === 'td' ? 'ArrowDown' : 'ArrowRight', up = orient === 'td' ? 'ArrowUp' : 'ArrowLeft';
    const next = orient === 'td' ? 'ArrowRight' : 'ArrowDown', prev = orient === 'td' ? 'ArrowLeft' : 'ArrowUp';
    let target = null;
    if (e.key === 'Enter') { e.preventDefault(); select(n, { center: true }); return; }
    if (e.key === ' ') { e.preventDefault(); toggle(n); return; }
    if (e.key === down) target = n.collapsed ? null : n.children[0];
    else if (e.key === up) target = n.parent;
    else if (e.key === next || e.key === prev) {
      const sib = n.parent ? n.parent.children : [n], i = sib.indexOf(n) + (e.key === next ? 1 : -1);
      target = sib[i];
    }
    if (target) {
      e.preventDefault();
      const f = gNodes.querySelector(`[data-id="${target.id}"]`);
      if (f) { f.focus({ preventScroll: true }); if (!inView(target)) centerOn(target); }
    }
  });
  function inView(n) {
    const { w, h } = size();
    const x = n.x * view.k + view.x, y = n.y * view.k + view.y;
    return x > 0 && y > 0 && x + n.w * view.k < w && y + AG.H * view.k < h;
  }

  /* public API */
  function search(q) {
    query = q.trim().toLowerCase(); matches = new Set();
    if (query) astEach(model, n => { if ((n.type + ' ' + n.details + ' ' + n.role).toLowerCase().includes(query)) matches.add(n.id); });
    if (query) matches.forEach(id => { for (let p = byId.get(id).parent; p; p = p.parent) p.collapsed = false; });
    draw();
    return matches.size;
  }
  function nextMatch() {
    if (!matches.size) return;
    const ids = [...matches], i = selected ? ids.indexOf(selected.id) : -1;
    select(byId.get(ids[(i + 1) % ids.length]), { center: true });
  }
  function setAll(open) { astEach(model, n => { n.collapsed = !open && n.children.length > 0 && n !== model; }); draw(); fit(true); }
  function setOrientation(o) { orient = o; draw(); fit(true); }
  function setRoles(v) { showRoles = v; draw(); }

  /** A standalone SVG string with every colour resolved, so it looks right outside the app. */
  function exportSvg() {
    const clone = canvas.cloneNode(true);
    const src = [canvas, ...canvas.querySelectorAll('*')], dst = [clone, ...clone.querySelectorAll('*')];
    const props = ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'font-family', 'font-size', 'font-weight', 'opacity', 'paint-order', 'stroke-linejoin'];
    src.forEach((s, i) => { const cs = getComputedStyle(s); props.forEach(p => dst[i].style.setProperty(p, cs.getPropertyValue(p))); });
    const pad = 24, W = Math.ceil(layout.width + 2 * pad), H = Math.ceil(layout.height + 2 * pad);
    clone.setAttribute('xmlns', SVGNS); clone.setAttribute('viewBox', `0 0 ${W} ${H}`);
    clone.setAttribute('width', W); clone.setAttribute('height', H);
    ['role', 'aria-label', 'tabindex', 'class'].forEach(a => clone.removeAttribute(a));
    clone.querySelectorAll('.ag-toggle').forEach(t => t.remove());
    clone.querySelector('.ag-viewport').setAttribute('transform', `translate(${pad},${pad})`);
    const bg = svg('rect', { width: W, height: H, fill: getComputedStyle(stage).backgroundColor });
    clone.insertBefore(bg, clone.firstChild);
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
  }

  draw();
  canvas.classList.add('ag-enter');
  setTimeout(() => canvas.classList.remove('ag-enter'), 400);
  // Fit once the stage has a real size (it is not in the document yet when this runs).
  const ro = new ResizeObserver(() => { if (size().w > 10) { fit(true); ro.disconnect(); } });
  ro.observe(canvas);

  return {
    root: stage, model, total, hasRoles, byId,
    get selected() { return selected; },
    get orientation() { return orient; },
    select, search, nextMatch, setAll, setOrientation, setRoles, fit,
    zoomIn: () => zoomAt(1.25), zoomOut: () => zoomAt(0.8), reset: () => { view.k = 1; view.x = AG.PAD; view.y = AG.PAD; apply(); },
    exportSvg, visibleCount: () => layout.nodes.length,
  };
}

/** A read-only code listing that can highlight a range of lines. */
function SourceView(code) {
  const lines = code.split('\n');
  const rows = lines.map((t, i) => el('div', { class: 'sv-line', 'data-n': i + 1 }, el('span', { class: 'sv-no', text: String(i + 1) }), el('span', { class: 'sv-txt', text: t || ' ' })));
  const root = el('div', { class: 'source-view', role: 'region', 'aria-label': 'Source code', tabindex: '0' }, rows);
  return {
    root,
    highlight(from, to) {
      rows.forEach(r => r.classList.remove('on'));
      if (!from) return;
      const end = Math.min(to || from, from + 40);
      for (let i = from; i <= end && i <= rows.length; i++) rows[i - 1].classList.add('on');
      const r = rows[from - 1];
      if (r) {
        const top = r.offsetTop, bottom = top + r.offsetHeight;
        if (top < root.scrollTop) root.scrollTop = Math.max(0, top - 8);
        else if (bottom > root.scrollTop + root.clientHeight) root.scrollTop = bottom - root.clientHeight + 8;
      }
    },
  };
}
