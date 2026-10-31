'use strict';
/* tree.js — C++ syntax tree explorer (visual graph and tree list) and clang AST normalizer */

const CPP_FILE_ACCEPT = '.cpp,.cc,.cxx,.c++,.c,.h,.hpp,.hh,.txt';

function normClang(n) {
  return {
    role: '',
    label: n.type,
    meta: n.label != null ? n.label : (n.details || ''),
    pos: n.line ? String(n.line) : '',
    line: n.line || null,
    endLine: n.end_line || n.line || null,
    children: (n.children || []).map(normClang)
  };
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

/* ── Dedicated AST page for compiled C++ programs ─────────────────────── */
function pageAst(root) {
  let viewMode = state.astView || 'graph';
  let orient = state.astOrient || 'lr';
  let graph = null, list = null, sourceView = null;

  const host = el('div');
  const emptyState = (title, hint) => el('div', { class: 'panel' }, el('div', { class: 'empty' }, el('b', { text: title }), hint));

  function applyCode(text, name) {
    const c = state.cpp;
    if (c.code.trim() && c.code !== c.baseline && c.code !== text) {
      if (!window.confirm('Replace the code in the C++ workspace? Your unsaved changes will be lost.')) return;
    }
    c.code = text;
    c.baseline = text;
    if (name) c.name = name;
    c.result = null;
    c.run = null;
    c.lastCheckedCode = null;
    load();
    announce('Loaded ' + (name || 'program'));
  }

  const loaderHost = el('span', { class: 'file-loader-host' });
  const pickerHost = el('span');
  const btnRefresh = el('button', { class: 'btn', title: 'Re-parse the current C++ program', onClick: () => load() }, 'Refresh');

  function rebuildPickers() {
    const currentLang = (state.cpp && state.cpp.language) || 'cpp';
    const ext = { cpp: '.cpp', c: '.c', python: '.py', java: '.java' }[currentLang] || '.cpp';
    loaderHost.replaceChildren(FileLoader({
      accept: '.cpp,.cc,.cxx,.c++,.c,.h,.hpp,.hh,.py,.pyw,.java,.txt',
      label: 'Open file',
      onLoad: (t, n) => applyCode(t, n),
      onError: (m) => { host.prepend(notice('bad', m)); announce(m); }
    }));
    pickerHost.replaceChildren(SamplePicker(currentLang, (smp) => {
      const slug = smp.filename || ((smp.name || 'sample').toLowerCase().replace(/[^a-z0-9]+/g, '_') + ext);
      applyCode(smp.code, slug);
    }));
  }

  async function load() {
    graph = null; list = null;
    host.replaceChildren(el('div', { class: 'working' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), 'Building the syntax tree…'));

    const currentLang = (state.cpp && state.cpp.language) || 'cpp';
    if (currentLang === 'java') {
      host.replaceChildren(
        el('div', { class: 'panel' },
          el('div', { class: 'empty' },
            el('b', { text: 'Syntax tree is not available for Java' }),
            el('p', { class: 'muted', style: 'margin-top:6px', text: 'Syntax tree visualization is not supported for Java yet. Switch to C++, C, or Python in Code Studio to inspect syntax trees.' }),
            el('p', { style: 'margin-top:16px' },
              el('button', { class: 'btn primary', onClick: () => { location.hash = '#/workspace'; } }, 'Go to Code Studio')
            )
          )
        )
      );
      return;
    }

    try {
      const code = (state.cpp && state.cpp.code) || '';
      if (!code.trim()) {
        host.replaceChildren(emptyState('No code loaded',
          'Write or compile code in Code Studio, or open a file / load an example above.'));
        return;
      }
      const d = await call('/api/cpp/ast', { code, language: currentLang });
      const roots = (d.tree || []).map(normClang);
      if (!roots.length) {
        host.replaceChildren(emptyState('Parser produced no tree',
          'The file may have fatal syntax errors or the toolchain is unavailable. Check it in Code Studio and fix the problems first.'));
        return;
      }
      build(roots, code);
    } catch (e) {
      if (e.message && (e.message.toLowerCase().includes('not supported') || e.message.toLowerCase().includes('no syntax tree'))) {
        host.replaceChildren(
          el('div', { class: 'panel' },
            el('div', { class: 'empty' },
              el('b', { text: 'Syntax tree is not available for ' + (currentLang.toUpperCase()) }),
              el('p', { class: 'muted', style: 'margin-top:6px', text: e.message })
            )
          )
        );
        return;
      }
      host.replaceChildren(
        notice('bad', e.message),
        !state.status.clang && currentLang === 'cpp'
          ? el('p', { class: 'muted', style: 'margin-top:12px', text: 'clang++ is not installed or not on PATH. Install clang and restart the server to enable C++ syntax tree visualization.' })
          : null
      );
    }
  }

  function build(roots, code) {
    sourceView = SourceView(code);
    const details = el('div', { class: 'ast-details' });
    const showDetails = (n) => {
      sourceView.highlight(n && n.line, n && n.endLine);
      if (!n) {
        details.replaceChildren(el('p', { class: 'muted', text: 'Click a node to inspect its type, kind, and source lines. Double-click or click − / + to fold a branch.' }));
        return;
      }
      const path = astPath(n);
      const kindInfo = AST_KINDS[n.kind] || AST_KINDS.other;
      details.replaceChildren(
        el('div', { class: 'ad-head' },
          el('b', { class: 'ad-type', text: n.type }),
          el('span', { class: 'kind-chip k-' + n.kind }, el('i'), (kindInfo.name || n.kind).replace(/s$/, ''))),
        n.details ? el('p', { class: 'ad-detail mono', text: n.details }) : null,
        el('dl', { class: 'kv ad-kv' },
          n.role ? el('div', null, el('dt', { text: 'Role' }), el('dd', { text: n.role })) : null,
          n.line ? el('div', null, el('dt', { text: 'Line' }), el('dd', { text: n.line + (n.endLine && n.endLine !== n.line ? '–' + n.endLine : '') })) : null,
          el('div', null, el('dt', { text: 'Children' }), el('dd', { text: String(n.children.length) })),
          n.children.length ? el('div', null, el('dt', { text: 'In subtree' }), el('dd', { text: String(n.size) })) : null),
        path.length > 1 ? el('div', { class: 'ad-path', 'aria-label': 'Path from root' },
          path.map((p, i) => [
            i ? icon('chevron-right', { size: 12, cls: 'faint' }) : null,
            p === n ? el('b', { text: p.type }) : el('button', { class: 'linkish', text: p.type, onClick: () => graph && graph.select(p, { center: true }) })
          ])) : null
      );
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
    search.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && viewMode === 'graph') { e.preventDefault(); graph.nextMatch(); }
    });

    const segView = el('div', { class: 'seg', role: 'group', 'aria-label': 'View' },
      el('button', { 'aria-pressed': String(viewMode === 'graph'), onClick: () => setView('graph') }, 'Graph'),
      el('button', { 'aria-pressed': String(viewMode === 'list'), onClick: () => setView('list') }, 'List'));
    const segOrient = el('div', { class: 'seg', role: 'group', 'aria-label': 'Direction' },
      el('button', { 'aria-pressed': String(orient === 'lr'), title: 'Root on the left', onClick: () => setOrient('lr') }, icon('chevron-right'), ' Left-right'),
      el('button', { 'aria-pressed': String(orient === 'td'), title: 'Root at the top', onClick: () => setOrient('td') }, icon('chevron-down'), ' Top-down'));
    const rolesBox = graph.hasRoles ? el('label', { class: 'check' }, el('input', { type: 'checkbox', checked: true, onChange: (e) => graph.setRoles(e.target.checked) }), 'Edge labels') : null;
    const btnExpand = el('button', { class: 'btn', onClick: () => viewMode === 'graph' ? graph.setAll(true) : list.setAll(true) }, 'Expand all');
    const btnCollapse = el('button', { class: 'btn', onClick: () => viewMode === 'graph' ? graph.setAll(false) : list.setAll(false) }, 'Collapse all');
    const zoom = el('div', { class: 'seg zoom', role: 'group', 'aria-label': 'Zoom' },
      el('button', { 'aria-label': 'Zoom out', title: 'Zoom out', onClick: () => graph.zoomOut() }, icon('minus')),
      el('button', { title: 'Fit the whole tree in view', onClick: () => graph.fit(false) }, icon('fit'), ' Fit'),
      el('button', { 'aria-label': 'Zoom in', title: 'Zoom in', onClick: () => graph.zoomIn() }, icon('plus')));
    const btnExport = el('button', { class: 'btn', title: 'Download the diagram as an SVG image', onClick: () => {
      downloadText('syntax-tree.svg', graph.exportSvg(), 'image/svg+xml;charset=utf-8'); announce('Diagram saved');
    } }, icon('download'), ' Export SVG');
    const graphOnly = [segOrient, rolesBox, zoom, btnExport].filter(Boolean);

    const legend = el('div', { class: 'ag-legend', 'aria-label': 'Colour key' },
      ['decl', 'stmt', 'expr', 'lit'].map(k => el('span', { class: 'kind-chip k-' + k, title: AST_KINDS[k].hint }, el('i'), AST_KINDS[k].name)));
    const foot = el('div', { class: 'panel-foot' },
      el('span', { class: 'ag-count' }),
      el('span', { text: 'From clang -ast-dump, filtered to your file' }));
    const stageHost = el('div', { class: 'ast-stage-host' });
    const toolbar = el('div', { class: 'toolbar ast-toolbar', role: 'toolbar', 'aria-label': 'Tree controls' },
      segView, ...graphOnly, el('span', { class: 'grow' }), search, hitInfo, btnExpand, btnCollapse);

    function refreshCount() {
      const cEl = foot.querySelector('.ag-count');
      if (cEl) {
        cEl.textContent = viewMode === 'graph'
          ? graph.visibleCount() + ' of ' + plural(graph.total, 'node') + ' shown'
          : plural(list.count, 'node');
      }
    }
    function setView(v) {
      viewMode = v; state.astView = v; search.value = ''; hitInfo.textContent = '';
      segView.children[0].setAttribute('aria-pressed', String(v === 'graph'));
      segView.children[1].setAttribute('aria-pressed', String(v === 'list'));
      graphOnly.forEach(x => { x.hidden = v !== 'graph'; });
      legend.hidden = v !== 'graph';
      if (v === 'graph') {
        graph.search('');
        stageHost.replaceChildren(graph.root);
        requestAnimationFrame(() => graph.fit(true));
      } else {
        stageHost.replaceChildren(el('div', { class: 'ast-list' }, list.root));
      }
      body.classList.toggle('list-mode', v === 'list');
      refreshCount();
    }
    function setOrient(o) {
      orient = o; state.astOrient = o; graph.setOrientation(o);
      segOrient.children[0].setAttribute('aria-pressed', String(o === 'lr'));
      segOrient.children[1].setAttribute('aria-pressed', String(o === 'td'));
    }
    onGraphChange = refreshCount;
    btnExpand.addEventListener('click', refreshCount);
    btnCollapse.addEventListener('click', refreshCount);

    const body = el('div', { class: 'ast-body' },
      el('div', { class: 'ast-main' }, stageHost, legend),
      el('aside', { class: 'ast-side', 'aria-label': 'Node details and source' },
        el('div', { class: 'ast-card' }, el('div', { class: 'section-title', text: 'Selected node' }), details),
        el('div', { class: 'ast-card' }, el('div', { class: 'section-title', text: 'Source' }), sourceView.root)));

    host.replaceChildren(el('div', { class: 'panel ast-panel' }, toolbar, body, foot));
    setView(viewMode);
  }

  root.append(
    el('div', { class: 'page-head compact' },
      el('div', null,
        el('h1', { text: 'Syntax tree' }),
        el('p', { text: 'Interactive AST diagram of your C++ program: see every declaration, statement, and expression node, inspect its source lines, or export as SVG.' })),
      el('div', { class: 'actions' }, loaderHost, pickerHost, btnRefresh)),
    host);
  rebuildPickers();
  load();
}
