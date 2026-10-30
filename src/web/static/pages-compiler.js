'use strict';
/* pages-compiler.js — MiniC pipeline, AST explorer, AI insights. */

function minicEditor(onRun) {
  return Editor({ value: state.minic.code, label: 'MiniC source code', onChange: (v) => { state.minic.code = v; }, onRun });
}

function minicMarks(d) {
  const m = {};
  (d.lex_errors || []).forEach(e => { m[e.line] = 'err'; });
  (d.parse_errors || []).forEach(e => { m[e.line] = 'err'; });
  (d.semantic || []).forEach(e => { if (e.severity === 'error') m[e.line] = 'err'; else if (!m[e.line]) m[e.line] = 'warn'; });
  return m;
}

const MINIC_ACCEPT = '.c,.minic,.mc,.txt';
/** Open-file button for the MiniC editors; `after` runs once the code has been replaced. */
function minicLoader(ed, after) {
  return FileLoader({ accept: MINIC_ACCEPT, label: 'Open file',
    onLoad: (text) => { ed.set(text); ed.mark({}); after && after(); announce('File loaded'); },
    onError: (msg) => announce(msg) });
}

async function ensurePipeline(code) {
  const s = state.minic;
  if (s.pipeline && s.pipelineFor === code) return s.pipeline;
  const d = await call('/api/minic/pipeline', { code });
  s.pipeline = d; s.pipelineFor = code;
  return d;
}

/* ── Pipeline ────────────────────────────────────────────────────────── */
function stageModel(d) {
  const reached = d.stage_reached;
  const semErrors = (d.semantic || []).filter(x => x.severity === 'error').length;
  const hasSem = ['semantic', 'ir', 'executed'].includes(reached);
  const hasIR = ['ir', 'executed'].includes(reached);
  const irFail = d.runtime_error && String(d.runtime_error).startsWith('IR generation');
  return [
    { label: 'Lex', status: d.lex_errors.length ? 'error' : 'ok', note: d.lex_errors.length ? plural(d.lex_errors.length, 'error') : plural(Math.max(0, d.tokens.length - 1), 'token') },
    { label: 'Parse', status: d.parse_errors.length ? 'error' : 'ok', note: d.parse_errors.length ? plural(d.parse_errors.length, 'error') : 'AST built' },
    { label: 'Semantic', status: !hasSem ? 'skip' : semErrors ? 'error' : 'ok', note: !hasSem ? 'not reached' : semErrors ? plural(semErrors, 'error') : 'types & scopes ok' },
    { label: 'IR + optimize', status: irFail ? 'error' : hasIR ? 'ok' : 'skip', note: hasIR ? d.ir.length + ' → ' + d.optimized_ir.length + ' instr' : 'not reached' },
    { label: 'Run', status: reached === 'executed' ? 'ok' : (d.runtime_error && !irFail) ? 'error' : 'skip', note: reached === 'executed' ? plural((d.output || []).length, 'output line') : (d.runtime_error && !irFail) ? 'runtime error' : 'not reached' },
  ];
}

function Strip(d) {
  return el('ol', { class: 'strip', 'aria-label': 'Compiler phases', style: 'list-style:none;margin-left:0;padding-left:16px' },
    stageModel(d).map(st => el('li', { class: 'stage ' + st.status },
      el('span', { class: 'dot', 'aria-hidden': 'true', text: st.status === 'ok' ? '✓' : st.status === 'error' ? '✕' : '–' }),
      el('span', null, el('b', { text: st.label }), el('small', { text: st.note }),
        el('span', { class: 'sr', text: st.status === 'ok' ? 'passed' : st.status === 'error' ? 'failed' : 'not reached' })))));
}

const NOT_REACHED = (what) => el('p', { class: 'muted', text: 'Not reached — ' + what });

function ErrorList(items, ed, kind) {
  return el('div', null, items.map(e => el('div', { class: 'finding' },
    el('div', null, el('span', { class: 'sev ' + (e.severity || 'error'), text: e.severity || 'error' }), ' ',
      el('button', { class: 'linkish', text: 'line ' + e.line + ':' + e.column, onClick: () => ed.goto(e.line) })),
    el('div', { text: e.message }),
    e.expected ? el('div', { class: 'faint', text: 'expected: ' + e.expected }) : null)));
}

function pagePipeline(root) {
  const s = state.minic;
  const ed = minicEditor(() => run());
  const btn = el('button', { class: 'btn primary', onClick: () => run() }, 'Compile & run');
  const out = el('div');

  function render() {
    const d = s.pipeline;
    out.replaceChildren();
    if (!d) {
      out.append(el('div', { class: 'panel' }, el('div', { class: 'empty' }, el('b', { text: 'Run the pipeline to see each phase' }),
        'Press Compile & run (Ctrl+Enter). You will see the tokens, the syntax tree, the symbol table, the intermediate code before and after optimization, and the program output.')));
      return;
    }
    if (s.pipelineFor !== ed.get()) out.append(notice('warn', 'The code changed since this run. Press Compile & run to refresh.'));
    out.append(Strip(d));
    const semErrs = d.semantic.filter(x => x.severity === 'error');
    const initial = d.parse_errors.length || d.lex_errors.length ? 'syntax' : semErrs.length ? 'semantic' : d.stage_reached === 'executed' ? 'ir' : 'tokens';
    const tabs = Tabs([
      { id: 'tokens', label: 'Tokens', render: () => tokensView(d) },
      { id: 'syntax', label: 'Syntax', render: () => syntaxView(d, ed) },
      { id: 'semantic', label: 'Semantics & symbols', render: () => semanticView(d, ed) },
      { id: 'ir', label: 'IR & output', render: () => irView(d) },
    ], initial);
    out.append(el('div', { class: 'panel' }, tabs.list, tabs.panel));
  }

  async function run() {
    const code = ed.get();
    if (!code.trim()) { out.replaceChildren(notice('warn', 'Write or load some MiniC code first.')); return; }
    await busy([btn], async () => {
      try {
        const d = await call('/api/minic/pipeline', { code });
        s.pipeline = d; s.pipelineFor = code; ed.mark(minicMarks(d)); render();
        announce('Pipeline finished: ' + d.stage_reached);
      } catch (e) { out.replaceChildren(notice('bad', e.message)); }
    });
  }

  root.append(
    el('div', { class: 'page-head' },
      el('div', null, el('h1', { text: 'MiniC pipeline' }),
        el('p', { text: 'A small C-like language compiled by this project’s own front end: every phase below is code in src/core, not a wrapper around g++.' })),
      el('div', { class: 'actions' }, minicLoader(ed, () => { s.pipeline = null; render(); }), SamplePicker('minic', (smp) => { ed.set(smp.code); s.pipeline = null; ed.mark({}); render(); }), btn)),
    el('div', { class: 'split' },
      el('div', { class: 'panel' }, el('div', { class: 'panel-head' }, el('h2', { text: 'program.minic' })), ed.root,
        el('div', { class: 'panel-foot' }, el('span', { text: 'Ctrl+Enter to run' }), el('span', { text: 'Esc then Tab leaves the editor' }))),
      out));
  if (s.pipeline) ed.mark(minicMarks(s.pipeline));
  render();
}

function tokensView(d) {
  const toks = d.tokens.filter(t => t.type !== 'EOF');
  const shown = toks.slice(0, 600);
  return el('div', null,
    el('p', { class: 'muted', style: 'margin-bottom:12px', text: 'The lexer turns characters into tokens: the smallest meaningful pieces.' }),
    el('div', { class: 'scroll' }, el('table', { class: 'data' },
      el('thead', null, el('tr', null, el('th', { text: 'Type' }), el('th', { text: 'Text' }), el('th', { class: 'num', text: 'Line:col' }))),
      el('tbody', null, shown.map(t => el('tr', null, el('td', null, el('span', { class: 'tok', text: t.type })), el('td', { class: 'mono', text: t.lexeme }), el('td', { class: 'num faint', text: t.line + ':' + t.column })))))),
    toks.length > shown.length ? el('p', { class: 'faint', style: 'margin-top:8px', text: 'Showing the first ' + shown.length + ' of ' + toks.length + ' tokens.' }) : null);
}

function syntaxView(d, ed) {
  const errs = [...d.lex_errors.map(e => ({ ...e, severity: 'error' })), ...d.parse_errors.map(e => ({ ...e, severity: 'error' }))];
  if (errs.length) return el('div', null, el('p', { class: 'muted', style: 'margin-bottom:8px', text: 'The parser found these problems and kept going to report as many as it could.' }), ErrorList(errs, ed));
  const decls = (d.ast && d.ast.children || []).length;
  return el('div', null, notice('ok', el('b', { text: 'Parsed successfully. ' }), plural(decls, 'top-level declaration') + ' found.'),
    el('p', { style: 'margin-top:12px' }, el('a', { class: 'linkish', href: '#/ast', text: 'Explore the syntax tree →' })));
}

function semanticView(d, ed) {
  if (!['semantic', 'ir', 'executed'].includes(d.stage_reached)) return NOT_REACHED('fix the syntax errors first.');
  return el('div', null,
    el('div', { class: 'section-title', text: 'Checks' }),
    d.semantic.length ? ErrorList(d.semantic, ed) : notice('ok', 'No type, scope, or return-path problems found.'),
    el('div', { class: 'section-title', text: 'Symbol table' }),
    el('div', { class: 'scroll' }, el('table', { class: 'data' },
      el('thead', null, el('tr', null, ['Name', 'Kind', 'Type', 'Scope', 'Line'].map(h => el('th', { text: h })))),
      el('tbody', null, d.symbols.map(y => el('tr', null,
        el('td', { class: 'mono', text: y.name + (y.detail || '') }), el('td', { text: y.kind }), el('td', { class: 'mono', text: y.type }), el('td', { class: 'mono', text: y.scope }), el('td', { class: 'num', text: y.line })))))));
}

function irView(d) {
  if (!['ir', 'executed'].includes(d.stage_reached)) return NOT_REACHED(d.runtime_error || 'fix the earlier errors first.');
  const a = d.ir.map(x => x.text), b = d.optimized_ir.map(x => x.text);
  const m = lcsMarks(a, b);
  const st = d.opt_stats || {};
  const names = { constant_propagation: 'Constant propagation', constant_folding: 'Constant folding', algebraic_simplification: 'Algebraic simplification', common_subexpression_elimination: 'Common subexpressions', dead_code_elimination: 'Dead code removed' };
  return el('div', null,
    el('p', { class: 'muted', style: 'margin-bottom:12px', text: 'Three-address code is the compiler’s internal form. Five optimizer passes rewrite it, and the interpreter checks the program still behaves the same.' }),
    el('dl', { class: 'kv' }, Object.keys(names).map(k => el('div', null, el('dt', { text: names[k] }), el('dd', { text: String(st[k] ?? 0) })))),
    el('div', { class: 'cols2', style: 'margin-top:16px' },
      el('div', null, el('div', { class: 'section-title', text: 'Before · ' + a.length + ' instructions' }), IRList(a, m.removed, 'gone')),
      el('div', null, el('div', { class: 'section-title', text: 'After · ' + b.length + ' instructions' }), IRList(b, m.added, 'new'))),
    d.runtime_error ? notice('bad', el('b', { text: 'Runtime error: ' }), d.runtime_error) : el('div', null,
      el('div', { class: 'section-title', text: 'Program output' }),
      el('div', { class: 'cols2' },
        el('div', null, el('div', { class: 'faint', text: 'Before optimization' }), el('div', { class: 'out', text: (d.output || []).join('\n') || '(no output)' })),
        el('div', null, el('div', { class: 'faint', text: 'After optimization' }), el('div', { class: 'out', text: (d.optimized_output || []).join('\n') || '(no output)' }))),
      el('p', { style: 'margin-top:12px' }, d.equivalent
        ? el('span', { class: 'chip ok' }, el('i'), 'Same output before and after')
        : el('span', { class: 'chip bad' }, el('i'), 'Outputs differ — optimizer bug'))));
}

/* ── AST explorer ────────────────────────────────────────────────────── */
function miniMeta(attrs) {
  const entries = Object.entries(attrs || {});
  if (entries.length === 1) return String(entries[0][1]);
  return entries.map(([k, v]) => k + '=' + v).join(', ');
}
function normMini(n, role) {
  return { role, label: n.type, meta: miniMeta(n.attrs), pos: n.line ? n.line + ':' + n.column : '', line: n.line || null, endLine: n.line || null,
    children: (n.children || []).map(c => normMini(c.node, c.role)) };
}
function normClang(n) {
  return { role: '', label: n.type, meta: n.label != null ? n.label : (n.details || ''), pos: n.line ? String(n.line) : '', line: n.line || null, endLine: n.end_line || n.line || null,
    children: (n.children || []).map(normClang) };
}

function TreeView(roots) {
  const items = [];
  function build(n, depth) {
    const text = el('span', null,
      n.role ? el('span', { class: 'role', text: n.role + ': ' }) : null,
      el('span', { class: 'ty', text: n.label }), ' ',
      n.meta ? el('span', { class: 'attr', text: n.meta }) : null,
      n.pos ? el('span', { class: 'at', text: '  @' + n.pos }) : null);
    const li = el('li');
    let head;
    if (n.children.length) {
      head = el('summary', null, text);
      const det = el('details', { open: depth < 2 }, head, el('ul', null, n.children.map(c => build(c, depth + 1))));
      li.append(det); li._det = det;
    } else { head = el('div', { class: 'leaf' }, text); li.append(head); }
    li._text = ((n.role || '') + ' ' + n.label + ' ' + n.meta).toLowerCase();
    li._head = head; li._kids = () => [...li.querySelectorAll(':scope > details > ul > li')];
    items.push(li);
    return li;
  }
  const ul = el('ul', { class: 'tree', role: 'tree' }, roots.map(r => build(r, 0)));
  const none = el('p', { class: 'muted', hidden: true, text: 'No nodes match that filter.' });
  function filter(q) {
    q = q.trim().toLowerCase();
    let hits = 0;
    const visit = (li) => {
      const own = !!q && li._text.includes(q);
      if (own) hits++;
      let child = false;
      li._kids().forEach(k => { if (visit(k)) child = true; });
      li.hidden = !!q && !own && !child;
      li._head.classList.toggle('hit', own);
      if (li._det && q && child) li._det.open = true;
      return own || child;
    };
    [...ul.children].forEach(visit);
    none.hidden = !q || hits > 0;
    return hits;
  }
  const setAll = (open) => ul.querySelectorAll('details').forEach(d => { d.open = open; });
  return { root: el('div', null, none, ul), filter, setAll, count: items.length };
}

function pageAst(root) {
  let source = state.astSource || (state.status.clang ? 'cpp' : 'minic');
  let viewMode = state.astView || 'graph';
  let orient = state.astOrient || 'lr';
  let graph = null, list = null, sourceView = null;

  const codeOf = () => source === 'minic' ? state.minic.code : state.cpp.code;
  const host = el('div');
  const segMini = el('button', { 'aria-pressed': 'false', onClick: () => pick('minic') }, 'MiniC');
  const segCpp = el('button', { 'aria-pressed': 'false', onClick: () => pick('cpp') }, 'C++ (clang)');
  const sourceChoice = el('div', { class: 'seg', role: 'group', 'aria-label': 'Language' }, segMini, segCpp);

  function pick(src) { source = src; state.astSource = src; rebuildPicker(); load(); }

  function applyCode(text, name) {
    if (source === 'cpp') {
      const c = state.cpp;
      if (c.code.trim() && c.code !== c.baseline && c.code !== text && !window.confirm('Replace the code in the C++ workspace? Your unsaved changes will be lost.')) return;
      c.code = text; c.baseline = text; if (name) c.filename = name;
      c.result = null; c.run = null; c.lastCheckedCode = null;
    } else {
      state.minic.code = text; state.minic.pipeline = null; state.minic.pipelineFor = null;
    }
    load(); announce('Loaded ' + (name || 'example'));
  }
  const loaderHost = el('span', { class: 'file-loader-host' });
  const pickerHost = el('span');
  function rebuildPicker() {
    loaderHost.replaceChildren(FileLoader({ accept: source === 'cpp' ? CPP_ACCEPT : MINIC_ACCEPT, label: 'Open file',
      onLoad: (t, n) => applyCode(t, n), onError: (m) => { host.prepend(notice('bad', m)); announce(m); } }));
    pickerHost.replaceChildren(SamplePicker(source, (smp) => applyCode(smp.code, source === 'cpp' ? fileSlug(smp.name) : undefined)));
    segMini.setAttribute('aria-pressed', String(source === 'minic'));
    segCpp.setAttribute('aria-pressed', String(source === 'cpp'));
  }

  const emptyState = (title, hint) => el('div', { class: 'panel' }, el('div', { class: 'empty' }, el('b', { text: title }), hint));

  async function load() {
    graph = null; list = null;
    host.replaceChildren(el('div', { class: 'working' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), 'Building the syntax tree…'));
    try {
      const code = codeOf();
      if (!code.trim()) {
        host.replaceChildren(emptyState(source === 'minic' ? 'No MiniC code yet' : 'No C++ code yet',
          'Use Open file or the examples menu above, or write code in the ' + (source === 'minic' ? 'MiniC pipeline' : 'C++ workspace') + '.'));
        return;
      }
      let roots, info = null;
      if (source === 'minic') {
        const d = await ensurePipeline(code);
        if (!d.ast) throw new Error('No syntax tree was produced.');
        roots = [normMini(d.ast, '')];
        if (d.parse_errors.length || d.lex_errors.length) info = notice('warn', 'The program has syntax errors, so this tree is partial.');
      } else {
        const d = await call('/api/cpp/ast', { code });
        roots = d.tree.map(normClang);
        if (!roots.length) { host.replaceChildren(emptyState('clang produced no tree', 'The file may have fatal errors. Compile it in the C++ workspace and fix the problems first.')); return; }
      }
      build(roots, code, info);
    } catch (e) {
      host.replaceChildren(notice('bad', e.message), source === 'cpp' && !state.status.clang
        ? el('p', { class: 'muted', style: 'margin-top:12px', text: 'clang++ is not installed or not on PATH. Switch to MiniC above, or install clang and restart the server.' }) : null);
    }
  }

  function build(roots, code, info) {
    sourceView = SourceView(code);
    const details = el('div', { class: 'ast-details' });
    const showDetails = (n) => {
      sourceView.highlight(n && n.line, n && n.endLine);
      if (!n) { details.replaceChildren(el('p', { class: 'muted', text: 'Click a node to see its details and the code it came from. Double-click or use the small − / + button to fold a branch.' })); return; }
      const path = astPath(n);
      details.replaceChildren(
        el('div', { class: 'ad-head' }, el('b', { class: 'ad-type', text: n.type }), el('span', { class: 'kind-chip k-' + n.kind }, el('i'), AST_KINDS[n.kind].name.replace(/s$/, ''))),
        n.details ? el('p', { class: 'ad-detail mono', text: n.details }) : null,
        el('dl', { class: 'kv ad-kv' },
          n.role ? el('div', null, el('dt', { text: 'Role' }), el('dd', { text: n.role })) : null,
          n.line ? el('div', null, el('dt', { text: 'Line' }), el('dd', { text: n.line + (n.endLine && n.endLine !== n.line ? '–' + n.endLine : '') })) : null,
          el('div', null, el('dt', { text: 'Children' }), el('dd', { text: String(n.children.length) })),
          n.children.length ? el('div', null, el('dt', { text: 'In subtree' }), el('dd', { text: String(n.size) })) : null),
        path.length > 1 ? el('div', { class: 'ad-path', 'aria-label': 'Path from the root' },
          path.map((p, i) => [i ? el('span', { class: 'faint', 'aria-hidden': 'true', text: ' › ' }) : null,
            p === n ? el('b', { text: p.type }) : el('button', { class: 'linkish', text: p.type, onClick: () => graph && graph.select(p, { center: true }) })])) : null);
    };

    let onGraphChange = () => {};
    graph = ASTGraph(roots, { orientation: orient, rootLabel: 'TranslationUnit', onSelect: showDetails, onChange: () => onGraphChange() });
    list = TreeView(roots);
    showDetails(null);

    const hitInfo = el('span', { class: 'faint ag-hits', role: 'status' });
    const search = el('input', { type: 'search', placeholder: 'Find a node…', 'aria-label': 'Find a node' });
    search.addEventListener('input', () => {
      const q = search.value;
      const n = viewMode === 'graph' ? graph.search(q) : list.filter(q);
      hitInfo.textContent = q.trim() ? plural(n, 'match') : '';
    });
    search.addEventListener('keydown', (e) => { if (e.key === 'Enter' && viewMode === 'graph') { e.preventDefault(); graph.nextMatch(); } });

    const segView = el('div', { class: 'seg', role: 'group', 'aria-label': 'View' },
      el('button', { 'aria-pressed': String(viewMode === 'graph'), onClick: () => setView('graph') }, 'Graph'),
      el('button', { 'aria-pressed': String(viewMode === 'list'), onClick: () => setView('list') }, 'List'));
    const segOrient = el('div', { class: 'seg', role: 'group', 'aria-label': 'Direction' },
      el('button', { 'aria-pressed': String(orient === 'lr'), title: 'Root on the left', onClick: () => setOrient('lr') }, '→ Left-right'),
      el('button', { 'aria-pressed': String(orient === 'td'), title: 'Root at the top', onClick: () => setOrient('td') }, '↓ Top-down'));
    const rolesBox = graph.hasRoles ? el('label', { class: 'check' }, el('input', { type: 'checkbox', checked: true, onChange: (e) => graph.setRoles(e.target.checked) }), 'Edge labels') : null;
    const btnExpand = el('button', { class: 'btn', onClick: () => viewMode === 'graph' ? graph.setAll(true) : list.setAll(true) }, 'Expand all');
    const btnCollapse = el('button', { class: 'btn', onClick: () => viewMode === 'graph' ? graph.setAll(false) : list.setAll(false) }, 'Collapse all');
    const zoom = el('div', { class: 'seg zoom', role: 'group', 'aria-label': 'Zoom' },
      el('button', { 'aria-label': 'Zoom out', title: 'Zoom out', onClick: () => graph.zoomOut() }, '−'),
      el('button', { title: 'Fit the whole tree in view', onClick: () => graph.fit(false) }, 'Fit'),
      el('button', { 'aria-label': 'Zoom in', title: 'Zoom in', onClick: () => graph.zoomIn() }, '+'));
    const btnExport = el('button', { class: 'btn', title: 'Download the diagram as an SVG image', onClick: () => {
      downloadText('syntax-tree.svg', graph.exportSvg(), 'image/svg+xml;charset=utf-8'); announce('Diagram saved'); } }, 'Export SVG');
    const graphOnly = [segOrient, rolesBox, zoom, btnExport].filter(Boolean);

    const legend = el('div', { class: 'ag-legend', 'aria-label': 'Colour key' },
      ['decl', 'stmt', 'expr', 'lit'].map(k => el('span', { class: 'kind-chip k-' + k, title: AST_KINDS[k].hint }, el('i'), AST_KINDS[k].name)));
    const foot = el('div', { class: 'panel-foot' }, el('span', { class: 'ag-count' }),
      el('span', { text: source === 'minic' ? 'From the project’s own parser' : 'From clang -ast-dump, filtered to your file' }));
    const stageHost = el('div', { class: 'ast-stage-host' });
    const toolbar = el('div', { class: 'toolbar ast-toolbar', role: 'toolbar', 'aria-label': 'Tree controls' },
      segView, ...graphOnly, el('span', { class: 'grow' }), search, hitInfo, btnExpand, btnCollapse);

    function refreshCount() {
      foot.querySelector('.ag-count').textContent = viewMode === 'graph'
        ? graph.visibleCount() + ' of ' + plural(graph.total, 'node') + ' shown' : plural(list.count, 'node');
    }
    function setView(v) {
      viewMode = v; state.astView = v; search.value = ''; hitInfo.textContent = '';
      segView.children[0].setAttribute('aria-pressed', String(v === 'graph'));
      segView.children[1].setAttribute('aria-pressed', String(v === 'list'));
      graphOnly.forEach(x => { x.hidden = v !== 'graph'; });
      legend.hidden = v !== 'graph';
      if (v === 'graph') { graph.search(''); stageHost.replaceChildren(graph.root); requestAnimationFrame(() => graph.fit(true)); }
      else stageHost.replaceChildren(el('div', { class: 'ast-list' }, list.root));
      body.classList.toggle('list-mode', v === 'list');
      refreshCount();
    }
    function setOrient(o) {
      orient = o; state.astOrient = o; graph.setOrientation(o);
      segOrient.children[0].setAttribute('aria-pressed', String(o === 'lr'));
      segOrient.children[1].setAttribute('aria-pressed', String(o === 'td'));
    }
    onGraphChange = refreshCount;
    btnExpand.addEventListener('click', refreshCount);       // the list view has no change callback
    btnCollapse.addEventListener('click', refreshCount);

    const body = el('div', { class: 'ast-body' },
      el('div', { class: 'ast-main' }, stageHost, legend),
      el('aside', { class: 'ast-side', 'aria-label': 'Node details and source' },
        el('div', { class: 'ast-card' }, el('div', { class: 'section-title', text: 'Selected node' }), details),
        el('div', { class: 'ast-card' }, el('div', { class: 'section-title', text: 'Source' }), sourceView.root)));

    host.replaceChildren(info, el('div', { class: 'panel ast-panel' }, toolbar, body, foot));
    setView(viewMode);
  }

  root.append(
    el('div', { class: 'page-head compact' },
      el('div', null, el('h1', { text: 'Syntax tree' }),
        el('p', { text: 'See how the parser understands your code: every declaration, statement and expression becomes a node, joined to the node that contains it.' })),
      el('div', { class: 'actions' }, sourceChoice, loaderHost, pickerHost)),
    host);
  rebuildPicker();
  load();
}

/* ── AI insights ─────────────────────────────────────────────────────── */
function pageAI(root) {
  const s = state.minic;
  s.ai = s.ai || {};
  const ed = minicEditor(() => {});
  const ready = state.status.ai_ready;

  function runner(action, label, renderResult) {
    return () => {
      const host = el('div');
      const note = el('p', { class: 'muted', style: 'margin-bottom:12px' });
      const btn = el('button', { class: 'btn primary', disabled: !ready, onClick: go }, label);
      const stale = () => s.ai[action] && s.ai[action].code !== ed.get();
      function paint() {
        host.replaceChildren();
        const r = s.ai[action];
        if (!r) return;
        if (stale()) host.append(notice('warn', 'The code changed since this result. Run again to refresh.'), el('div', { style: 'height:12px' }));
        if (state.status.llm_mock) host.append(notice('warn', el('b', { text: 'Mock mode: ' }), 'these answers are canned, not from a real model.'), el('div', { style: 'height:12px' }));
        host.append(renderResult(r.data, ed));
      }
      async function go() {
        const code = ed.get();
        if (!code.trim()) { host.replaceChildren(notice('warn', 'Write or load some MiniC code first.')); return; }
        await busy([btn], async () => {
          try {
            const d = await call('/api/minic/ai', { action, code });
            s.ai[action] = { code, data: d.result, secs: d.elapsed_s }; paint(); announce('AI result ready');
          } catch (e) { host.replaceChildren(notice('bad', e.message)); }
        });
      }
      note.textContent = ready ? '' : 'AI features need a Gemini API key. Set GEMINI_API_KEY and restart the server (see the top bar). For an offline demo, start the server with LLM_MOCK=1.';
      paint();
      return el('div', null, el('div', { class: 'actions', style: 'margin-bottom:12px' }, btn, s.ai[action] ? el('span', { class: 'faint', text: 'Last run took ' + s.ai[action].secs + 's' }) : null), note.textContent ? note : null, host);
    };
  }

  const tabs = Tabs([
    { id: 'explain', label: 'Explain phases', render: runner('explain', 'Explain this program', renderExplain) },
    { id: 'optimize', label: 'Optimize', render: runner('optimize', 'Ask AI to optimize', renderOptimize) },
    { id: 'bugs', label: 'Find bugs', render: runner('bugs', 'Look for bugs', renderBugs) },
  ], state.aiTab);
  tabs.list.addEventListener('click', () => { state.aiTab = tabs.current; });

  root.append(
    el('div', { class: 'page-head' },
      el('div', null, el('h1', { text: 'AI insights' }),
        el('p', { text: 'The model explains, proposes and reviews. It never has the last word: optimizations are kept only if the program’s output is unchanged, and bug reports must point at real lines.' })),
      el('div', { class: 'actions' }, minicLoader(ed, () => tabs.refresh()), SamplePicker('minic', (smp) => { ed.set(smp.code); ed.mark({}); tabs.refresh(); }))),
    el('div', { class: 'split' },
      el('div', { class: 'panel' }, el('div', { class: 'panel-head' }, el('h2', { text: 'program.minic' })), ed.root),
      el('div', { class: 'panel' }, tabs.list, tabs.panel)));
}

function renderExplain(r) {
  const P = r.phases || {};
  const rows = [
    ['Lexical analysis', P.lexical_analysis && plural(P.lexical_analysis.token_count, 'token'), P.lexical_analysis && P.lexical_analysis.explanation],
    ['Syntax analysis', P.syntax_analysis && P.syntax_analysis.ast_summary, P.syntax_analysis && P.syntax_analysis.explanation],
    ['Semantic analysis', P.semantic_analysis && ((P.semantic_analysis.symbols_declared || []).join(', ') || 'no symbols'), P.semantic_analysis && P.semantic_analysis.explanation],
    ['IR generation', P.ir_generation && plural(P.ir_generation.instruction_count, 'instruction'), P.ir_generation && P.ir_generation.explanation],
  ];
  return el('div', null, el('p', { class: 'lede', style: 'margin-bottom:16px', text: r.program_summary || '' }),
    rows.map(([t, sub, body]) => el('div', { class: 'phase' }, el('div', null, el('h3', { text: t }), el('div', { class: 'sub', text: sub || '' })), el('p', { text: body || '' }))));
}

function renderOptimize(r) {
  const accepted = r.accepted || [], rejected = r.rejected || [];
  return el('div', null,
    r.analysis ? el('p', { class: 'muted', style: 'margin-bottom:12px', text: r.analysis }) : null,
    el('dl', { class: 'kv' },
      el('div', null, el('dt', { text: 'Instructions' }), el('dd', { text: r.initial_count + ' → ' + r.final_count })),
      el('div', null, el('dt', { text: 'Kept' }), el('dd', { text: String(accepted.length) })),
      el('div', null, el('dt', { text: 'Rejected' }), el('dd', { text: String(rejected.length) })),
      el('div', null, el('dt', { text: 'Output unchanged' }), el('dd', { text: r.equivalence_verified ? 'yes' : 'NO' }))),
    el('p', { class: 'faint', style: 'margin:8px 0 0', text: 'Only the intermediate code changes. Your source is untouched. Each suggestion was run against the original and dropped if the output differed.' }),
    accepted.length ? el('div', null, el('div', { class: 'section-title', text: 'Kept suggestions' }),
      accepted.map(a => el('div', { class: 'finding' }, el('div', null, el('b', { text: a.suggestion_id }), el('span', { class: 'faint', text: '  ' + (a.instruction_delta || 0) + ' instructions' })), el('div', { class: 'muted', text: a.description })))) : null,
    rejected.length ? el('div', null, el('div', { class: 'section-title', text: 'Rejected suggestions' }),
      rejected.map(a => el('div', { class: 'finding' }, el('div', null, el('b', { text: a.suggestion_id })), el('div', { class: 'muted', text: a.description }), el('div', { class: 'faint', text: 'Why: ' + a.reason })))) : null,
    !accepted.length && !rejected.length ? el('p', { class: 'muted', style: 'margin-top:12px', text: 'The model found nothing to improve here.' }) : null,
    el('div', { class: 'section-title', text: 'Change to the intermediate code' }), DiffView(r.ir_diff));
}

function renderBugs(r, ed) {
  const bugs = r.bugs || [];
  return el('div', null,
    r.summary ? el('p', { class: 'lede', style: 'margin-bottom:12px', text: r.summary }) : null,
    bugs.length ? bugs.map(b => el('div', { class: 'finding' },
      el('div', null, el('span', { class: 'sev ' + String(b.severity || 'low').toLowerCase(), text: b.severity || 'low' }), ' ',
        el('button', { class: 'linkish', text: 'line ' + b.line, onClick: () => ed.goto(b.line) }), el('span', { class: 'faint', text: '  ' + String(b.category || '').replace(/_/g, ' ') })),
      el('div', { text: b.description }), b.fix_suggestion ? el('div', { class: 'muted', text: 'Suggestion: ' + b.fix_suggestion }) : null))
      : notice('ok', 'No likely bugs reported.'),
    r.discarded_bug_count ? el('p', { class: 'faint', style: 'margin-top:12px', text: plural(r.discarded_bug_count, 'finding') + ' dropped because they pointed at lines that do not exist in the parsed program.' }) : null);
}
