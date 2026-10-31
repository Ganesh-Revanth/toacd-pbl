'use strict';
/* pages-cpp.js — C++ Studio (run, check, heal, accept/reject) and the Changes history. */

const pendingCount = () => state.proposals.filter(p => p.status === 'pending').length;
function updateNavCount() {
  const b = $('#nav-count');
  if (!b) return;
  const n = pendingCount();
  b.textContent = String(n);
  b.hidden = n === 0;
}

function createProposal(r) {
  const p = {
    id: state.nextId++, time: Date.now(), mode: r.mode,
    kind: r.mode === 'ai' ? 'C++ heal · Gemini agent' : 'C++ heal · rule-based',
    original: r.original, patched: r.patched, diff: r.diff, steps: r.steps || [],
    compiles: r.compiles, summary: r.summary || '', status: 'pending',
  };
  // A newer proposal supersedes any older pending one, so there is never an ambiguous choice.
  state.proposals.forEach(o => { if (o.status === 'pending') o.status = 'rejected'; });
  state.proposals.push(p);
  state.cpp.pending = p;
  saveProposals(); updateNavCount();
  return p;
}

/** Accept / reject / undo with safety checks. Returns {ok, msg}. */
function decide(p, action) {
  const s = state.cpp;
  if (action === 'accept') {
    if (s.code !== p.original) return { ok: false, msg: 'Your code changed after this proposal was made, so applying it could overwrite your edits. Run the heal again.' };
    s.code = p.patched; p.status = 'accepted'; s.result = null; saveDraft();
  } else if (action === 'reject') {
    p.status = 'rejected';
  } else if (action === 'undo') {
    if (s.code !== p.patched) return { ok: false, msg: 'The code has been edited since this change was accepted, so undoing it would discard those edits.' };
    s.code = p.original; p.status = 'undone'; s.result = null; saveDraft();
  }
  if (s.pending === p && p.status !== 'pending') s.pending = null;
  saveProposals(); updateNavCount();
  return { ok: true };
}

const STATUS_CHIP = { pending: ['warn', 'Awaiting your decision'], accepted: ['ok', 'Accepted'], rejected: ['plain', 'Rejected'], undone: ['plain', 'Undone'] };
const statusChip = (st) => el('span', { class: 'chip ' + STATUS_CHIP[st][0] }, el('i'), STATUS_CHIP[st][1]);

function StepsList(steps) {
  if (!steps || !steps.length) return null;
  return el('ol', { class: 'steps', 'aria-label': 'What the healer tried' }, steps.map(st => {
    if (st.thought !== undefined) return el('li', null, el('span', { class: 'ok', text: '•' }), el('span', null, el('b', { text: 'Step ' + st.attempt + ': ' }), st.thought));
    return el('li', null,
      el('span', { class: st.fixed ? 'ok' : 'no', text: st.fixed ? '✓' : '✕' }),
      el('span', null, el('b', { text: 'Line ' + st.line + ': ' }), st.message || '', st.fixed ? ' — patched' : ' — ' + (st.note || 'not fixed')));
  }));
}

/* ── C++ Studio ──────────────────────────────────────────────────────── */
const CPP_ACCEPT = '.cpp,.cc,.cxx,.c,.h,.hpp,.txt';
let draftTimer = null;
function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => store.set('cppDraft', { code: state.cpp.code, name: state.cpp.name }), 300);
}
const slug = (n) => (n.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'main') + '.cpp';

function pageWorkspace(root) {
  const s = state.cpp;
  const st = state.status;
  const aiOK = st.ai_ready;
  let lastDecisionNote = null;
  let undoLoad = null;

  /* editor + status bar */
  const fileChip = el('span', { class: 'filename' });
  const dirtyChip = el('span', { class: 'chip warn', hidden: true }, el('i'), 'Edited since last compile');
  const posInfo = el('span', { class: 'faint', text: 'Ln 1, Col 1' });
  const loadNote = el('div', { class: 'loadnote', hidden: true });

  const ed = Editor({
    value: s.code, label: 'C++ source code', lang: 'cpp', accept: CPP_ACCEPT,
    onChange: (v) => {
      s.code = v; saveDraft();
      dirtyChip.hidden = !(s.result && v !== s.lastCheckedCode);
      if (!loadNote.hidden && undoLoad && v !== undoLoad.loaded) loadNote.hidden = true;
    },
    onRun: () => run(),
    onCursor: (c) => { posInfo.textContent = 'Ln ' + c.line + ', Col ' + c.col + (c.selected ? ' (' + c.selected + ' selected)' : ''); },
    onFile: (r) => r.error ? flash(notice('bad', r.error)) : openText(r.name, r.text),
  });
  const setName = (n) => { s.name = n; fileChip.textContent = n; saveDraft(); };
  setName(s.name || 'main.cpp');

  function flash(node) { loadNote.hidden = false; loadNote.replaceChildren(node); }
  function openText(name, text) {
    const prev = { code: ed.get(), name: s.name };
    const had = prev.code.trim() !== '';
    ed.set(text); setName(name);
    s.result = null; s.pending = null; s.run = null; s.ast = null; s.lastCheckedCode = null;
    dirtyChip.hidden = true; ed.mark({}); lastDecisionNote = null;
    undoLoad = { prev, loaded: text };
    flash(el('div', { class: 'notice ok loadnote-in', role: 'status' },
      el('span', null, el('b', { text: 'Opened ' + name + '. ' }), plural(text.split('\n').length, 'line') + '.'),
      had ? el('button', { class: 'linkish', text: 'Undo', onClick: () => {
        ed.set(undoLoad.prev.code); setName(undoLoad.prev.name); loadNote.hidden = true; refreshAll(); ed.focus();
      } }) : null,
      el('button', { class: 'linkish', text: 'Dismiss', onClick: () => { loadNote.hidden = true; } })));
    refreshAll(); announce('Opened ' + name);
  }

  /* toolbar */
  const btnOpen = el('button', { class: 'btn', onClick: async () => {
    const f = await pickFile(CPP_ACCEPT);
    if (!f) return;
    try { const r = await readTextFile(f); openText(r.name, r.text); } catch (e) { flash(notice('bad', e.message)); }
  } }, 'Open file…');
  const btnSave = el('button', { class: 'btn', onClick: () => {
    let n = (s.name || 'main.cpp').trim() || 'main.cpp';
    saveTextFile(n, ed.get()); announce('Saved ' + n);
  } }, 'Save');
  const samples = SamplePicker('cpp', (smp) => openText(slug(smp.name), smp.code));
  const btnRun = el('button', { class: 'btn primary', title: 'Compile and run (Ctrl+Enter)', onClick: () => run() }, el('span', { 'aria-hidden': 'true', text: '▶' }), 'Run');
  const btnCompile = el('button', { class: 'btn', title: 'Compile only, no run', onClick: () => compile() }, 'Compile');
  const btnRules = el('button', { class: 'btn', title: 'Try the built-in repair rules. You review the diff first.', onClick: () => heal('rules') }, 'Fix with rules');
  const btnAI = el('button', { class: 'btn', disabled: !aiOK, title: aiOK ? 'Ask the Gemini agent. You review the diff first.' : 'Needs a Gemini API key (see the status bar above)', onClick: () => heal('ai') }, 'Fix with AI');
  const all = () => [btnRun, btnCompile, btnRules, btnAI];

  /* right-hand panes */
  const problemsHost = el('div'), outputHost = el('div'), reviewHost = el('div'), astHost = el('div');
  const reviewBadge = el('span', { class: 'count', hidden: true, text: '1' });
  const probBadge = el('span', { class: 'count bad', hidden: true });
  const tabs = Tabs([
    { id: 'problems', label: el('span', { class: 'tab-l' }, 'Problems', probBadge), render: () => problemsHost },
    { id: 'output', label: 'Output', render: () => outputHost },
    { id: 'ast', label: 'Syntax tree', render: () => { loadAst(); return astHost; } },
    { id: 'review', label: el('span', { class: 'tab-l' }, 'Review fix', reviewBadge), render: () => reviewHost },
  ], 'problems');
  tabs.list.addEventListener('click', () => { s.tab = tabs.current; });
  const show = (id) => { s.tab = id; tabs.select(id); };

  function markEditor(r) {
    const m = {};
    for (const d of (r && r.diagnostics) || []) {
      if (!d.line) continue;
      if (d.type === 'error') m[d.line] = 'err'; else if (!m[d.line]) m[d.line] = 'warn';
    }
    ed.mark(m);
  }
  function setResult(r, code) {
    s.result = r; s.lastCheckedCode = code; dirtyChip.hidden = true; s.ast = null;
    markEditor(r); renderProblems();
  }

  /* Problems */
  function renderProblems() {
    const r = s.result;
    problemsHost.replaceChildren();
    probBadge.hidden = !(r && r.error_count); probBadge.textContent = r ? String(r.error_count) : '';
    if (!r) {
      problemsHost.append(el('div', { class: 'empty' }, el('b', { text: 'Not compiled yet' }),
        'Press Run to build and run your program, or Compile to only check it. Errors show up here with a plain-language explanation.'));
      return;
    }
    problemsHost.append(el('div', { class: 'summary ' + (r.ok ? 'good' : 'bad') },
      el('b', { text: r.ok ? (r.warning_count ? 'Compiles, with ' + plural(r.warning_count, 'warning') : 'Compiles cleanly') : plural(r.error_count, 'error') + (r.warning_count ? ', ' + plural(r.warning_count, 'warning') : '') }),
      el('span', { class: 'faint', text: r.elapsed_s + ' s' })));
    if (!r.ok) problemsHost.append(el('div', { class: 'fixbar' }, el('span', { class: 'muted', text: 'Want help?' }),
      el('button', { class: 'btn', onClick: () => heal('rules') }, 'Fix with rules'),
      el('button', { class: 'btn', disabled: !aiOK, onClick: () => heal('ai') }, 'Fix with AI')));
    if (!r.diagnostics.length) problemsHost.append(el('div', { class: 'empty' }, el('b', { text: 'No problems' }), 'g++ reported nothing for this file.'));
    r.diagnostics.forEach(d => problemsHost.append(Diagnostic(d, ed)));
    if (r.security && r.security.length) {
      problemsHost.append(el('div', { class: 'section-title pad', text: 'Security findings (' + r.security.length + ')' }));
      r.security.forEach(f => problemsHost.append(SecurityItem(f, ed)));
    }
  }

  /* Output */
  const stdinBox = el('textarea', { class: 'stdin', rows: '3', spellcheck: 'false', 'aria-label': 'Program input (stdin)', placeholder: 'Type input here if your program reads from the keyboard (cin, scanf…). Each line is one Enter press.' });
  stdinBox.value = s.stdin || '';
  stdinBox.addEventListener('input', () => { s.stdin = stdinBox.value; });
  const consoleHost = el('div');
  function renderOutput() {
    const r = s.run;
    consoleHost.replaceChildren();
    if (!r) {
      consoleHost.append(el('div', { class: 'empty' }, el('b', { text: 'Nothing has run yet' }), 'Press Run. The program’s output appears here.'));
      return;
    }
    const chips = [];
    if (r.timed_out) chips.push(['bad', 'Stopped after ' + st.run_timeout_s + ' s (still running)']);
    else if (r.truncated) chips.push(['warn', 'Stopped: too much output']);
    else if (r.crashed) chips.push(['bad', 'Crashed (exit code ' + r.exit_code + ')']);
    else chips.push([r.exit_code === 0 ? 'ok' : 'warn', 'Exited with code ' + r.exit_code]);
    chips.push(['plain', r.run_s + ' s']);
    consoleHost.append(el('div', { class: 'chips' }, chips.map(([k, t]) => el('span', { class: 'chip ' + k }, el('i'), t))));
    consoleHost.append(el('div', { class: 'section-title', text: 'Output' }),
      el('pre', { class: 'console', tabindex: '0', 'aria-label': 'Program output', text: r.stdout || (r.stderr ? '' : '(no output)') }));
    if (r.stderr) consoleHost.append(el('div', { class: 'section-title', text: 'Error stream (stderr)' }), el('pre', { class: 'console err', tabindex: '0', text: r.stderr }));
    if (r.timed_out) consoleHost.append(el('p', { class: 'faint', style: 'margin-top:8px', text: 'Likely an infinite loop, or the program is waiting for input that was not provided. Add input above and run again.' }));
  }
  function renderOutputPane() {
    outputHost.replaceChildren(
      el('div', { class: 'pad' },
        el('label', { class: 'field-label', for: 'stdin-box' }, 'Input for the program'), stdinBox,
        consoleHost,
        el('p', { class: 'faint', style: 'margin-top:12px', text: 'Run compiles your code and runs it on this computer with a ' + st.run_timeout_s + ' s limit. Only run code you trust.' })));
    stdinBox.id = 'stdin-box';
    renderOutput();
  }

  /* Syntax tree (C++ via clang) */
  let astTree = null;
  async function loadAst() {
    const code = ed.get();
    if (!code.trim()) { astHost.replaceChildren(el('div', { class: 'empty' }, el('b', { text: 'No code' }), 'Write or open some C++ first.')); return; }
    if (s.ast && s.ast.code === code) { paintAst(s.ast.data); return; }
    if (!st.clang) {
      astHost.replaceChildren(el('div', { class: 'pad' }, notice('warn', el('b', { text: 'The C++ syntax tree needs clang++. ' }),
        'It is not installed or not on PATH. On Windows with MSYS2: run pacman -S mingw-w64-ucrt-x86_64-clang, add C:\\msys64\\ucrt64\\bin to PATH, then restart this server.')));
      return;
    }
    astHost.replaceChildren(el('p', { class: 'pad muted', text: 'Parsing with clang…' }));
    try {
      const d = await call('/api/cpp/ast', { code });
      s.ast = { code, data: d };
      if (tabs.current === 'ast') paintAst(d);
    } catch (e) { astHost.replaceChildren(el('div', { class: 'pad' }, notice('bad', e.message))); }
  }
  function paintAst(d) {
    astTree = TreeView(d.tree.map(normClang));
    const q = el('input', { type: 'search', placeholder: 'Filter nodes…', 'aria-label': 'Filter syntax tree nodes' });
    const info = el('span', { class: 'faint' });
    q.addEventListener('input', () => { const n = astTree.filter(q.value); info.textContent = q.value.trim() ? plural(n, 'match') : ''; });
    astHost.replaceChildren(
      el('div', { class: 'treebar' }, q, info,
        el('button', { class: 'btn quiet', onClick: () => astTree.setAll(true) }, 'Expand all'),
        el('button', { class: 'btn quiet', onClick: () => astTree.setAll(false) }, 'Collapse all')),
      el('div', { class: 'pad tree-scroll' }, astTree.root),
      el('p', { class: 'pad faint', text: plural(astTree.count, 'node') + ' · from clang -ast-dump, limited to your file. Even code with errors may give a partial tree.' }));
  }

  /* Review */
  function renderReview() {
    const p = s.pending;
    reviewHost.replaceChildren();
    reviewBadge.hidden = !p;
    if (lastDecisionNote) reviewHost.append(el('div', { class: 'pad' }, lastDecisionNote));
    if (!p) {
      if (!lastDecisionNote) reviewHost.append(el('div', { class: 'empty' }, el('b', { text: 'No fix to review' }),
        'Use Fix with rules or Fix with AI. The proposed change appears here as a diff. Nothing touches your code until you accept it.'));
      return;
    }
    const d = diffStats(p.diff);
    const warn = st.llm_mock && p.mode === 'ai' ? notice('warn', el('b', { text: 'Mock mode: ' }), 'this is a canned response, not a real fix for your code.') : null;
    const msgHost = el('div');
    const accept = el('button', { class: 'btn primary', onClick: () => {
      const res = decide(p, 'accept');
      if (!res.ok) { msgHost.replaceChildren(notice('bad', res.msg)); return; }
      ed.set(s.code); ed.mark({}); lastDecisionNote = notice('ok', el('b', { text: 'Change accepted. ' }), 'Your code was updated. You can undo it from Changes.');
      renderReview(); announce('Change accepted'); compile(true);
    } }, 'Accept change');
    const reject = el('button', { class: 'btn', onClick: () => {
      decide(p, 'reject'); lastDecisionNote = notice('', 'Change rejected. Your code is unchanged.'); renderReview(); announce('Change rejected');
    } }, 'Reject');
    reviewHost.append(el('div', { class: 'pad' },
      el('div', { class: 'chips' },
        el('span', { class: 'chip plain' }, p.kind),
        el('span', { class: 'chip ' + (p.compiles ? 'ok' : 'warn') }, el('i'), p.compiles ? 'Compiles after change' : 'Still has errors after change')),
      warn && el('div', { style: 'height:12px' }), warn,
      el('div', { style: 'height:12px' }),
      StepsList(p.steps),
      p.summary && el('p', { class: 'muted', text: p.summary, style: 'margin-bottom:12px' }),
      el('p', { class: 'faint', style: 'margin-bottom:8px', text: '+' + d.add + ' added, −' + d.del + ' removed. Nothing changes until you accept.' }),
      DiffView(p.diff),
      el('div', { class: 'decision' }, accept, reject), msgHost));
  }

  function refreshAll() { renderProblems(); renderOutputPane(); renderReview(); dirtyChip.hidden = true; if (tabs.current === 'ast') loadAst(); }

  /* actions */
  const needCode = () => { if (ed.get().trim()) return true; show('problems'); problemsHost.replaceChildren(el('div', { class: 'pad' }, notice('warn', 'The editor is empty. Open a file, load an example, or type some code.'))); return false; };

  async function compile(quiet) {
    if (!needCode()) return;
    const code = ed.get();
    await busy([btnCompile, btnRun, btnRules, btnAI], async () => {
      try {
        const r = await call('/api/cpp/compile', { code });
        setResult(r, code);
        if (!quiet) show('problems');
        announce(r.ok ? 'Compiles' : plural(r.error_count, 'error') + ' found');
      } catch (e) { show('problems'); problemsHost.replaceChildren(el('div', { class: 'pad' }, notice('bad', e.message))); }
    });
  }

  async function run() {
    if (!needCode()) return;
    if (!st.run_enabled) { show('output'); consoleHost.replaceChildren(notice('bad', 'Running is switched off because the server is not limited to this computer.')); return; }
    const code = ed.get();
    await busy([btnRun, btnCompile, btnRules, btnAI], async () => {
      try {
        const r = await call('/api/cpp/run', { code, stdin: stdinBox.value });
        setResult(r, code);
        if (!r.ran) { show('problems'); announce(plural(r.error_count, 'error') + ' found. The program did not run.'); return; }
        s.run = r; renderOutput(); show('output');
        announce('Program finished with exit code ' + r.exit_code);
      } catch (e) { show('problems'); problemsHost.replaceChildren(el('div', { class: 'pad' }, notice('bad', e.message))); }
    });
  }

  async function heal(mode) {
    if (!needCode()) return;
    const code = ed.get();
    lastDecisionNote = null;
    await busy([mode === 'ai' ? btnAI : btnRules, btnRun, btnCompile, mode === 'ai' ? btnRules : btnAI], async () => {
      try {
        const r = await call('/api/cpp/heal', { mode, code });
        if (!r.changed) {
          s.pending = null;
          lastDecisionNote = el('div', null, el('b', { text: 'No change proposed. ' }),
            r.compiles ? 'The code already compiles, so there is nothing to fix.' : 'No automatic fix was found for the remaining problems. Read the explanations in Problems and edit the code, or try the AI fix.');
          if (!r.compiles) { const a = await call('/api/cpp/compile', { code }); setResult(a, code); }
          renderReview(); reviewHost.append(el('div', { class: 'pad' }, StepsList(r.steps)));
          show(r.compiles ? 'review' : 'problems'); announce('No change proposed');
          return;
        }
        createProposal(r); renderReview(); show('review'); announce('A change is proposed. Review the diff.');
      } catch (e) { reviewHost.replaceChildren(el('div', { class: 'pad' }, notice('bad', e.message))); show('review'); }
    });
  }

  root.append(
    el('div', { class: 'studio-head' },
      el('div', null, el('h1', { text: 'C++ Studio' }),
        el('p', { text: 'Open or write C++, then Run it. If it does not compile, the errors are explained and a fix can be reviewed before it touches your code.' }))),
    el('div', { class: 'toolbar', role: 'toolbar', 'aria-label': 'C++ actions' },
      el('div', { class: 'tb-group' }, btnRun, btnCompile),
      el('div', { class: 'tb-sep', 'aria-hidden': 'true' }),
      el('div', { class: 'tb-group' }, btnRules, btnAI),
      el('div', { class: 'tb-spacer' }),
      el('div', { class: 'tb-group' }, btnOpen, btnSave, samples)),
    !aiOK && el('p', { class: 'faint note-line', text: 'Fix with AI is off because no Gemini key is set. Run, Compile and Fix with rules work without one.' }),
    el('div', { class: 'studio' },
      el('section', { class: 'panel editor-panel', 'aria-label': 'Editor' },
        el('div', { class: 'editor-bar' }, fileChip, dirtyChip),
        loadNote, ed.root,
        el('div', { class: 'panel-foot' }, posInfo, el('span', { text: 'Ctrl+Enter runs · drop a file here to open it' }))),
      el('section', { class: 'panel result-panel', 'aria-label': 'Results' }, tabs.list, tabs.panel)));

  renderProblems(); renderOutputPane(); renderReview();
  if (s.result) markEditor(s.result);
  if (s.pending) tabs.select('review'); else if (s.tab && s.tab !== 'problems') tabs.select(s.tab);
}

function Diagnostic(d, ed) {
  const detail = el('div', { class: 'diag-detail', hidden: true },
    d.explanation && el('div', null, el('h4', { text: 'What it means' }), el('pre', { text: String(d.explanation).replace(/^What happened:\s*/i, '').trim() })),
    d.suggestion && el('div', null, el('h4', { text: 'Suggestion' }), el('pre', { text: d.suggestion })),
    d.context && d.context.lines && el('div', null, el('h4', { text: 'Source' }),
      el('pre', { class: 'mono', text: d.context.lines.map((ln, i) => String(d.context.start_line + i).padStart(3) + (d.context.start_line + i === d.line ? ' → ' : '   ') + ln.replace(/\s+$/, '')).join('\n') })));
  const row = el('button', { class: 'diag-row', 'aria-expanded': 'false', onClick: () => {
    const open = detail.hidden; detail.hidden = !open; row.setAttribute('aria-expanded', String(open));
    if (open && d.line) ed.goto(d.line);
  } },
    el('span', { class: 'sev ' + d.type, text: d.type }),
    el('span', null, el('span', { class: 'diag-msg', text: d.message }),
      el('span', { class: 'diag-meta' },
        d.line && el('span', { text: 'line ' + d.line + (d.column ? ':' + d.column : '') }),
        d.category && el('span', { text: d.category.replace(/_/g, ' ') + (d.confidence ? ' · ' + Math.round(d.confidence * 100) + '%' : '') }))),
    el('span', { class: 'faint', 'aria-hidden': 'true', text: '⌄' }));
  return el('div', { class: 'diag' }, row, detail);
}

function SecurityItem(f, ed) {
  return el('div', { class: 'diag' }, el('div', { class: 'diag-row', style: 'cursor:default' },
    el('span', { class: 'sev ' + String(f.severity).toLowerCase(), text: f.severity }),
    el('span', null, el('b', { text: f.vulnerability_type }), el('br'), el('span', { class: 'diag-msg muted', text: f.description }),
      el('span', { class: 'diag-meta' }, el('span', { text: f.recommendation }))),
    f.line ? el('button', { class: 'linkish', text: 'line ' + f.line, onClick: () => ed.goto(f.line) }) : el('span')));
}

/* ── Changes history ─────────────────────────────────────────────────── */
function pageChanges(root) {
  const host = el('div');
  function render() {
    host.replaceChildren();
    const list = state.proposals.slice().reverse();
    if (!list.length) {
      host.append(el('div', { class: 'panel' }, el('div', { class: 'empty' }, el('b', { text: 'No proposed changes yet' }),
        'When a fix is suggested in C++ Studio it appears here with its diff. Nothing is applied until you accept it, and accepted changes can be undone.')));
      return;
    }
    list.forEach(p => {
      const st = diffStats(p.diff);
      const msg = el('div');
      const body = el('div', { class: 'change-body', hidden: p.status !== 'pending' }, StepsList(p.steps), DiffView(p.diff), msg);
      const toggle = el('button', { class: 'btn quiet', 'aria-expanded': String(p.status === 'pending'), onClick: () => {
        body.hidden = !body.hidden; toggle.setAttribute('aria-expanded', String(!body.hidden)); toggle.textContent = body.hidden ? 'Show diff' : 'Hide diff';
      } }, p.status === 'pending' ? 'Hide diff' : 'Show diff');
      const act = el('div', { class: 'actions' }, toggle);
      const run = (action) => { const r = decide(p, action); if (!r.ok) { msg.replaceChildren(notice('bad', r.msg)); return; } render(); announce('Change ' + action); };
      if (p.status === 'pending') act.append(el('button', { class: 'btn primary', onClick: () => run('accept') }, 'Accept'), el('button', { class: 'btn', onClick: () => run('reject') }, 'Reject'));
      if (p.status === 'accepted') act.append(el('button', { class: 'btn', onClick: () => run('undo') }, 'Undo'));
      host.append(el('article', { class: 'change' },
        el('div', { class: 'change-head' },
          el('div', null, el('h3', { text: p.kind }),
            el('div', { class: 'diag-meta' }, el('span', { text: timeLabel(p.time) }), el('span', { text: '+' + st.add + ' −' + st.del }), p.compiles ? el('span', { text: 'compiled after change' }) : null)),
          el('div', { class: 'actions' }, statusChip(p.status), act)),
        body));
    });
  }
  root.append(
    el('div', { class: 'page-head' },
      el('div', null, el('h1', { text: 'Changes' }),
        el('p', { text: 'Every fix the tool has proposed, what it would change, and what you decided.' })),
      state.proposals.length ? el('button', { class: 'btn quiet', onClick: () => { state.proposals = state.proposals.filter(p => p.status === 'pending'); saveProposals(); render(); } }, 'Clear finished items') : null),
    host);
  render();
}
