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
      el('div', { class: 'actions' }, SamplePicker('minic', (smp) => { ed.set(smp.code); s.pipeline = null; ed.mark({}); render(); }), btn)),
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
function normMini(n, role) {
  const attrs = Object.entries(n.attrs || {}).map(([k, v]) => k + '=' + JSON.stringify(v)).join('  ');
  return { role, label: n.type, meta: attrs, pos: n.line ? n.line + ':' + n.column : '', children: (n.children || []).map(c => normMini(c.node, c.role)) };
}
function normClang(n) {
  return { role: '', label: n.type, meta: n.details || '', pos: '', children: (n.children || []).map(normClang) };
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
  let source = state.astSource || 'minic';
  const host = el('div');
  const segMini = el('button', { 'aria-pressed': 'false', onClick: () => pick('minic') }, 'MiniC');
  const segCpp = el('button', { 'aria-pressed': 'false', onClick: () => pick('cpp') }, 'C++ (clang)');
  const search = el('input', { type: 'search', placeholder: 'Filter nodes…', 'aria-label': 'Filter nodes' });
  const btnOpen = el('button', { class: 'btn', onClick: () => tree && tree.setAll(true) }, 'Expand all');
  const btnClose = el('button', { class: 'btn', onClick: () => tree && tree.setAll(false) }, 'Collapse all');
  const hitInfo = el('span', { class: 'faint' });
  let tree = null;
  search.addEventListener('input', () => { if (tree) { const n = tree.filter(search.value); hitInfo.textContent = search.value.trim() ? plural(n, 'match') : ''; } });

  function pick(src) { source = src; state.astSource = src; load(); }

  async function load() {
    segMini.setAttribute('aria-pressed', String(source === 'minic'));
    segCpp.setAttribute('aria-pressed', String(source === 'cpp'));
    tree = null; search.value = ''; hitInfo.textContent = '';
    host.replaceChildren(el('p', { class: 'muted', text: 'Loading…' }));
    try {
      let roots, info;
      if (source === 'minic') {
        const code = state.minic.code;
        if (!code.trim()) { host.replaceChildren(el('div', { class: 'panel' }, el('div', { class: 'empty' }, el('b', { text: 'No MiniC code yet' }), 'Write a program on the MiniC pipeline page first.'))); return; }
        const d = await ensurePipeline(code);
        if (!d.ast) throw new Error('No syntax tree was produced.');
        roots = [normMini(d.ast, '')];
        info = d.parse_errors.length || d.lex_errors.length ? notice('warn', 'The program has syntax errors, so this tree is partial.') : null;
      } else {
        const code = state.cpp.code;
        if (!code.trim()) { host.replaceChildren(el('div', { class: 'panel' }, el('div', { class: 'empty' }, el('b', { text: 'No C++ code yet' }), 'Load or write code in the C++ workspace first.'))); return; }
        const d = await call('/api/cpp/ast', { code });
        roots = d.tree.map(normClang);
        info = null;
      }
      tree = TreeView(roots);
      host.replaceChildren(info, el('div', { class: 'panel' }, el('div', { class: 'panel-body' }, tree.root),
        el('div', { class: 'panel-foot' }, el('span', { text: plural(tree.count, 'node') }), el('span', { text: source === 'minic' ? 'From the project’s own parser' : 'From clang -ast-dump, filtered to your file' }))));
    } catch (e) { host.replaceChildren(notice('bad', e.message)); }
  }

  root.append(
    el('div', { class: 'page-head' },
      el('div', null, el('h1', { text: 'Syntax tree' }),
        el('p', { text: 'The abstract syntax tree is what the parser builds from your code. Choose the MiniC tree from this project’s parser, or the C++ tree from clang.' })),
      el('div', { class: 'actions' }, el('div', { class: 'seg', role: 'group', 'aria-label': 'Tree source' }, segMini, segCpp), search, hitInfo, btnOpen, btnClose)),
    host);
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
      el('div', { class: 'actions' }, SamplePicker('minic', (smp) => { ed.set(smp.code); ed.mark({}); tabs.refresh(); }))),
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
