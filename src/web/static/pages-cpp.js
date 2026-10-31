'use strict';
/* pages-cpp.js — C++ workspace (check, heal, accept/reject) and the Changes history. */

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
    kind: (state.cpp.language || 'cpp').toUpperCase() + ' heal · ' + (r.mode === 'ai' ? 'Gemini agent' : 'rule-based'),
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
    s.code = p.patched; p.status = 'accepted'; s.result = null;
  } else if (action === 'reject') {
    p.status = 'rejected';
  } else if (action === 'undo') {
    if (s.code !== p.patched) return { ok: false, msg: 'The code has been edited since this change was accepted, so undoing it would discard those edits.' };
    s.code = p.original; p.status = 'undone'; s.result = null;
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
      el('span', { class: st.fixed ? 'ok' : 'no' }, typeof icon === 'function' ? icon(st.fixed ? 'check' : 'x', { size: 12 }) : null),
      el('span', null, el('b', { text: 'Line ' + st.line + ': ' }), st.message || '', st.fixed ? ' — patched' : ' — ' + (st.note || 'not fixed')));
  }));
}

/* ── Code Studio Workspace ────────────────────────────────────────────── */
const INPUT_RE = /\bcin\b|\bgetline\s*\(|\bscanf\s*\(|\bgets\s*\(|\bgetchar\s*\(|\binput\s*\(|\bScanner\b/;
const SUPPORTED_LANGUAGES = [
  { id: 'cpp', name: 'C++', ext: '.cpp', defaultFile: 'main.cpp', toolchain: 'g++' },
  { id: 'c', name: 'C', ext: '.c', defaultFile: 'main.c', toolchain: 'gcc' },
  { id: 'python', name: 'Python', ext: '.py', defaultFile: 'main.py', toolchain: 'python' },
  { id: 'java', name: 'Java', ext: '.java', defaultFile: 'Main.java', toolchain: 'javac' },
];
const DEFAULT_FILENAMES = { cpp: 'main.cpp', c: 'main.c', python: 'main.py', java: 'Main.java' };
const CODE_ACCEPT = '.cpp,.cc,.cxx,.c++,.c,.h,.hpp,.hh,.py,.pyw,.java,.txt';

function detectLanguageFromFilename(filename) {
  if (!filename) return null;
  const ext = '.' + filename.split('.').pop().toLowerCase();
  if (['.cpp', '.cc', '.cxx', '.c++', '.hpp', '.hh'].includes(ext)) return 'cpp';
  if (['.c', '.h'].includes(ext)) return 'c';
  if (['.py', '.pyw'].includes(ext)) return 'python';
  if (['.java'].includes(ext)) return 'java';
  return null;
}

function fileSlug(name, lang = 'cpp') {
  const ext = DEFAULT_FILENAMES[lang] ? '.' + DEFAULT_FILENAMES[lang].split('.').pop() : '.cpp';
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') + ext;
}

function pageWorkspace(root) {
  const s = state.cpp;
  s.language = s.language || 'cpp';
  s.filename = s.filename || DEFAULT_FILENAMES[s.language] || 'main.cpp';
  s.stdin = s.stdin || '';
  s.tab = s.tab || 'output';
  if (s.baseline === undefined) s.baseline = s.code;
  const aiOK = state.status.ai_ready;
  let working = null;          // null | 'compile' | 'run' | 'heal'
  let flash = null;            // a one-off message shown at the top of the Output tab
  let healNote = null;         // "no change proposed" explanation
  let lastDecisionNote = null;

  /* ── editor ── */
  const cursorInfo = el('span', { text: 'Ln 1, Col 1' });
  const staleChip = el('span', { class: 'chip warn', hidden: true }, el('i'), 'Edited since last build');
  const ed = Editor({
    value: s.code, label: (s.language || 'Code') + ' source code', language: s.language,
    onChange: (v) => {
      s.code = v;
      try {
        localStorage.setItem('studio:draft:' + s.language, JSON.stringify({
          code: v, filename: s.filename
        }));
      } catch (e) {}
      updateStale(); updateInputHint();
    },
    onRun: (e) => (e && e.shiftKey) ? runJob('compile') : runJob('run'),
    onCursor: (ln, col) => { cursorInfo.textContent = 'Ln ' + ln + ', Col ' + col; },
  });
  const updateStale = () => { staleChip.hidden = !s.result || s.code === s.lastCheckedCode; };

  /* ── toolbar ── */
  const fileName = el('span', { class: 'file-name', text: s.filename });
  const btnCompile = el('button', { class: 'btn', title: 'Check code with toolchain (Ctrl+Shift+Enter)', onClick: () => runJob('compile') }, 'Compile');
  const btnRun = el('button', { class: 'btn primary run', title: 'Compile, then run the program (Ctrl+Enter)', onClick: () => runJob('run') },
    icon('play'), 'Compile & Run');
  const itemRules = el('button', { class: 'menu-item', role: 'menuitem', onClick: (e) => { closeMenu(e); heal('rules'); } },
    el('b', { text: 'Rule-based fix' }), el('small', { text: 'Fast, works offline' }));
  const itemAI = el('button', { class: 'menu-item', role: 'menuitem', disabled: !aiOK, onClick: (e) => { closeMenu(e); heal('ai'); } },
    el('b', { text: 'AI fix (Gemini)' }), el('small', { text: aiOK ? 'Slower, handles harder errors' : 'Needs a Gemini API key' }));
  const closeMenu = (e) => { const d = e.target.closest('details'); if (d) d.open = false; };
  const fixMenu = el('details', { class: 'menu' },
    el('summary', { class: 'btn', title: 'Propose a fix. Nothing changes until you accept.' }, icon('sparkle'), ' Suggest fix ', icon('chevron-down')),
    el('div', { class: 'menu-pop', role: 'menu' }, itemRules, itemAI));
  const allButtons = () => [btnRun, btnCompile, itemRules, itemAI];

  function setFile(name) { s.filename = name; fileName.textContent = name; }

  const langSelector = el('select', {
    class: 'lang-selector',
    'aria-label': 'Select programming language',
    title: 'Programming language',
    onChange: (e) => switchLanguage(e.target.value)
  },
    SUPPORTED_LANGUAGES.map(lang => {
      const info = (state.status?.languages || []).find(l => l.id === lang.id);
      const available = info ? info.available : true;
      const opt = el('option', {
        value: lang.id,
        text: lang.name + (!available ? ' (unavailable)' : '')
      });
      if (!available) {
        opt.disabled = true;
        opt.title = `${lang.toolchain} is missing from PATH`;
      }
      if (lang.id === s.language) opt.selected = true;
      return opt;
    })
  );

  async function switchLanguage(newLang, opts = {}) {
    const oldLang = s.language || 'cpp';
    if (newLang === oldLang && !opts.force) return;

    // 1. Save old draft
    try {
      localStorage.setItem('studio:draft:' + oldLang, JSON.stringify({
        code: s.code, filename: s.filename || DEFAULT_FILENAMES[oldLang]
      }));
    } catch (e) {}

    // 2. Set new language
    s.language = newLang;
    store.set('studio:lang', newLang);
    langSelector.value = newLang;
    ed.setLanguage(newLang);

    // 3. Load examples for new language
    try {
      const data = await call('/api/samples?language=' + newLang);
      if (data && data.samples) {
        state.samples = data.samples;
        picker.setLanguage(newLang);
      }
    } catch (e) {
      console.warn('Failed to load examples for ' + newLang, e);
    }

    // 4. Decide code to display
    if (opts.newCode !== undefined) {
      s.code = opts.newCode;
      s.filename = opts.newFilename || DEFAULT_FILENAMES[newLang];
    } else {
      let draft = null;
      try {
        const saved = localStorage.getItem('studio:draft:' + newLang);
        if (saved) draft = JSON.parse(saved);
      } catch (e) {}

      if (draft && typeof draft.code === 'string' && draft.code.trim()) {
        s.code = draft.code;
        s.filename = draft.filename || DEFAULT_FILENAMES[newLang];
      } else {
        const first = (state.samples || []).find(x => x.language === newLang);
        if (first) {
          s.code = first.code;
          s.filename = first.filename || DEFAULT_FILENAMES[newLang];
        } else {
          s.code = '';
          s.filename = DEFAULT_FILENAMES[newLang];
        }
      }
    }

    // 5. Update editor & view
    ed.set(s.code);
    setFile(s.filename);
    s.baseline = s.code;
    s.result = null; s.run = null; s.pending = null; s.lastCheckedCode = null;
    s.tab = 'output'; flash = null; healNote = null; lastDecisionNote = null;
    ed.mark({}); renderResults(); updateStale(); updateInputHint();
    announce('Switched to ' + (SUPPORTED_LANGUAGES.find(l => l.id === newLang)?.name || newLang));
  }

  function loadCode(text, name) {
    const detected = detectLanguageFromFilename(name);
    if (detected && detected !== s.language) {
      switchLanguage(detected, { newCode: text, newFilename: name });
      return;
    }
    if (s.code.trim() && s.code !== s.baseline && s.code !== text &&
        !window.confirm('Replace the code in the editor? Your unsaved changes will be lost.')) return;
    ed.set(text); setFile(name || s.filename); s.baseline = text;
    s.result = null; s.run = null; s.pending = null; s.lastCheckedCode = null; s.tab = 'output';
    flash = null; healNote = null; lastDecisionNote = null; ed.mark({});
    renderResults(); updateStale(); announce('Loaded ' + (name || 'example'));
  }
  const onFileError = (msg) => { flash = notice('bad', msg); s.tab = 'output'; renderResults(); announce(msg); };

  const loader = FileLoader({ accept: CODE_ACCEPT, label: 'Open file', onLoad: (t, n) => loadCode(t, n), onError: onFileError });
  const picker = SamplePicker(s.language || 'cpp', (smp) => loadCode(smp.code, smp.filename || fileSlug(smp.name, s.language)));
  const btnSave = el('button', { class: 'btn', title: 'Download the code as a file', onClick: () => {
    const ext = SUPPORTED_LANGUAGES.find(l => l.id === s.language)?.ext || '.cpp';
    const name = /\.[A-Za-z0-9+]+$/.test(s.filename) ? s.filename : s.filename + ext;
    downloadText(name, ed.get()); s.baseline = ed.get(); announce('Saved ' + name);
  } }, icon('save'), 'Save');

  /* ── program input ── */
  const inputHint = el('span', { class: 'chip warn', hidden: true }, el('i'), 'Your program reads input');
  const stdinArea = el('textarea', { class: 'stdin-area', spellcheck: 'false', rows: '3', placeholder: 'Type what the program should read, one value per line, for example:\n12\n30', 'aria-label': 'Program input' });
  stdinArea.value = s.stdin;
  stdinArea.addEventListener('input', () => { s.stdin = stdinArea.value; updateInputHint(); });
  const stdinBox = el('details', { class: 'stdin-box', open: !!s.stdin },
    el('summary', null, 'Program input (stdin)', inputHint), stdinArea);
  function updateInputHint() { inputHint.hidden = !(INPUT_RE.test(s.code) && !s.stdin.trim()); }

  /* ── results tabs ── */
  const TABS = [['output', 'Output'], ['problems', 'Problems'], ['fix', 'Fix']];
  const tabBtn = {}, badge = {};
  const tabList = el('div', { class: 'tabs', role: 'tablist', 'aria-label': 'Results' });
  const indicator = el('div', { class: 'tab-indicator', 'aria-hidden': 'true' });
  const panel = el('div', { class: 'tabpanel results-body', role: 'tabpanel', tabindex: '0' });
  TABS.forEach(([id, label], i) => {
    badge[id] = el('span', { class: 'badge', hidden: true });
    const b = el('button', { class: 'tab', role: 'tab', id: 'rtab-' + id, onClick: () => { s.tab = id; renderResults(); } }, label, badge[id]);
    b.addEventListener('keydown', (e) => {
      const k = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (k) { e.preventDefault(); s.tab = TABS[(i + k + TABS.length) % TABS.length][0]; renderResults(); tabBtn[s.tab].focus(); }
    });
    tabBtn[id] = b; tabList.append(b);
  });
  tabList.append(indicator);

  function updateIndicator() {
    const active = tabBtn[s.tab];
    if (!active || !tabList.offsetParent) return;
    const lRect = tabList.getBoundingClientRect();
    const bRect = active.getBoundingClientRect();
    const x = bRect.left - lRect.left + tabList.scrollLeft;
    const w = bRect.width;
    indicator.style.transform = `translateX(${x}px) scaleX(${w})`;
  }
  window.addEventListener('resize', updateIndicator);

  function renderResults() {
    const r = s.result;
    TABS.forEach(([id]) => { tabBtn[id].setAttribute('aria-selected', String(id === s.tab)); tabBtn[id].tabIndex = id === s.tab ? 0 : -1; });
    const n = r ? r.error_count + r.warning_count : 0;
    badge.problems.hidden = !n; badge.problems.textContent = String(n);
    badge.problems.className = 'badge' + (r && r.error_count ? ' bad' : ' warn');
    badge.fix.hidden = !(s.pending && s.pending.status === 'pending'); badge.fix.textContent = '1'; badge.fix.className = 'badge ok';
    panel.setAttribute('aria-labelledby', 'rtab-' + s.tab);
    panel.replaceChildren(s.tab === 'problems' ? problemsView() : s.tab === 'fix' ? fixView() : outputView());
    requestAnimationFrame(updateIndicator);
  }

  function markEditor(r) {
    const m = {};
    for (const d of (r && r.diagnostics) || []) {
      if (!d.line) continue;
      if (d.type === 'error') m[d.line] = 'err'; else if (!m[d.line]) m[d.line] = 'warn';
    }
    ed.mark(m);
  }

  /* ── Output tab ── */
  function workingView() {
    const text = working === 'run' ? 'Compiling and running…' : working === 'heal' ? 'Looking for a fix…' : 'Compiling…';
    return el('div', { class: 'working', role: 'status' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), text);
  }

  function consoleView(run) {
    if (!run) return el('div', { class: 'empty' }, el('b', { text: 'No program output' }));
    const outStr = typeof run.stdout === 'string' ? run.stdout : '';
    const errStr = typeof run.stderr === 'string' ? run.stderr : '';
    const hasOut = outStr.length > 0, hasErr = errStr.length > 0;
    let chip;
    if (run.timed_out) chip = el('span', { class: 'chip bad' }, el('i'), 'Stopped after ' + (run.timeout_s || 5) + ' s');
    else if (run.output_flood) chip = el('span', { class: 'chip bad' }, el('i'), 'Stopped: too much output');
    else if (run.signal) chip = el('span', { class: 'chip bad' }, el('i'), 'Crashed · ' + run.signal);
    else if (run.exit_code === 0) chip = el('span', { class: 'chip ok' }, el('i'), 'Exited with code 0');
    else chip = el('span', { class: 'chip warn' }, el('i'), 'Exited with code ' + (run.exit_code != null ? run.exit_code : 1));
    const warns = s.result && s.result.warning_count;
    const notes = [];
    if (run.timed_out) notes.push(notice('warn', el('b', { text: 'Your program did not finish. ' }),
      INPUT_RE.test(s.code) && !s.stdin.trim()
        ? 'It reads input but none was given. Add values in “Program input” above and run again.'
        : 'It may contain an infinite loop, or be waiting for input.'));
    if (run.signal_hint) notes.push(notice('bad', run.signal_hint));
    if (run.truncated) notes.push(notice('warn', 'Output was cut at 64 KB.'));
    const timeText = run.elapsed_ms != null ? run.elapsed_ms + ' ms' : (run.elapsed_s != null ? Math.round(run.elapsed_s * 1000) + ' ms' : '');
    return el('div', { class: 'stack-sm' },
      el('div', { class: 'run-meta' }, chip, timeText ? el('span', { class: 'faint', text: timeText }) : null,
        warns ? el('button', { class: 'linkish', text: plural(warns, 'warning'), onClick: () => { s.tab = 'problems'; renderResults(); } }) : null),
      el('div', { class: 'console', role: 'log', tabindex: '0', 'aria-label': 'Program output' },
        hasOut && hasErr ? el('div', { class: 'c-label', text: 'stdout' }) : null,
        hasOut ? el('pre', { class: 'c-out', text: outStr }) : null,
        hasErr ? el('div', { class: 'c-label', text: 'stderr' }) : null,
        hasErr ? el('pre', { class: 'c-err', text: errStr }) : null,
        !hasOut && !hasErr ? el('span', { class: 'c-dim', text: '(the program printed nothing)' }) : null),
      notes);
  }

  function outputView() {
    if (working) return workingView();
    const r = s.result;
    const parts = [flash];
    if (!r) {
      parts.push(el('div', { class: 'empty' },
        el('b', { text: 'Nothing has run yet' }),
        'Press ', el('b', { text: 'Compile & Run' }), ' to build and run your program, or ', el('b', { text: 'Compile' }),
        ' to only check it. Output appears here.'));
    } else if (!r.ok) {
      parts.push(notice('bad', el('b', { text: 'Build failed. ' }), plural(r.error_count || 0, 'error') + ' to fix before the program can run. '),
        el('p', { style: 'margin-top:12px' }, el('button', { class: 'btn', onClick: () => { s.tab = 'problems'; renderResults(); } }, 'See problems')));
    } else if (!s.run) {
      parts.push(notice('ok', el('b', { text: 'Compiled successfully' }), r.warning_count ? ' with ' + plural(r.warning_count, 'warning') + '.' : '. No errors or warnings.'),
        el('p', { class: 'muted', style: 'margin-top:12px', text: 'Press Compile & Run to run it.' }));
    } else {
      parts.push(consoleView(s.run));
    }
    return el('div', null, parts);
  }

  /* ── Problems tab ── */
  function problemsView() {
    const r = s.result;
    if (!r) return el('div', { class: 'empty' }, el('b', { text: 'No problems to show' }), 'Compile your code and any errors or warnings are listed here, explained in plain language.');
    const head = el('div', { class: 'prob-head' },
      el('h2', { text: r.ok ? (r.warning_count ? 'Compiles, with warnings' : 'No problems found') : plural(r.error_count || 0, 'error') + (r.warning_count ? ', ' + plural(r.warning_count, 'warning') : '') }),
      el('span', { class: 'faint', text: (r.elapsed_s != null ? r.elapsed_s + ' s' : '') }));
    const list = el('div', { class: 'prob-list' });
    const diags = r.diagnostics || [];
    if (!diags.length) list.append(el('div', { class: 'empty' }, el('b', { text: 'No diagnostics' }), 'No problems reported for this file.'));
    diags.forEach(d => list.append(Diagnostic(d, ed)));
    const secs = el('div');
    const secList = r.security || [];
    if (secList.length) {
      secs.append(el('div', { class: 'section-title', text: 'Security findings · ' + secList.length }));
      secList.forEach(f => secs.append(SecurityItem(f, ed)));
    }
    return el('div', null, head, list, secs);
  }

  /* ── Fix tab ── */
  function fixView() {
    if (working === 'heal') return workingView();
    const p = s.pending;
    const parts = [lastDecisionNote];
    if (!p) {
      parts.push(healNote || el('div', { class: 'empty' },
        el('b', { text: 'No fix proposed' }),
        'Choose ', el('b', { text: 'Suggest fix' }), ' in the toolbar. You will review a diff here, and nothing changes until you accept it.'));
      return el('div', null, parts);
    }
    const st = diffStats(p.diff);
    const msgHost = el('div');
    const accept = el('button', { class: 'btn primary', onClick: () => {
      const res = decide(p, 'accept');
      if (!res.ok) { msgHost.replaceChildren(notice('bad', res.msg)); return; }
      ed.set(s.code); ed.mark({});
      lastDecisionNote = notice('ok', el('b', { text: 'Change accepted. ' }), 'Editor updated. You can undo it from Changes.');
      announce('Change accepted'); runJob('compile');
    } }, icon('check'), 'Accept change');
    const reject = el('button', { class: 'btn', onClick: () => {
      decide(p, 'reject'); lastDecisionNote = notice('', 'Change rejected. Your code is unchanged.'); renderResults(); announce('Change rejected');
    } }, icon('x'), 'Reject');
    parts.push(
      el('div', { class: 'run-meta' },
        el('span', { class: 'chip plain' }, p.kind),
        el('span', { class: 'chip ' + (p.compiles ? 'ok' : 'warn') }, el('i'), p.compiles ? 'Compiles after change' : 'Still has errors after change')),
      state.status.llm_mock && p.mode === 'ai' ? notice('warn', el('b', { text: 'Mock mode: ' }), 'this result is a canned response, not a real fix for your code.') : null,
      el('div', { style: 'height:12px' }),
      StepsList(p.steps),
      p.summary && el('p', { class: 'muted', text: p.summary, style: 'margin-bottom:12px' }),
      el('p', { class: 'faint', style: 'margin-bottom:8px', text: '+' + st.add + ' added, −' + st.del + ' removed. Nothing changes until you accept.' }),
      DiffView(p.diff),
      el('div', { class: 'decision' }, accept, reject), msgHost);
    return el('div', null, parts);
  }

  /* ── actions ── */
  async function runJob(kind) {
    const code = ed.get();
    flash = null;
    if (!code.trim()) { flash = notice('warn', 'Write, open or load some code first.'); s.tab = 'output'; renderResults(); return; }
    if (kind === 'run' && INPUT_RE.test(code) && !s.stdin.trim()) stdinBox.open = true;
    working = kind; s.tab = 'output'; renderResults();
    await busy(kind === 'run' ? allButtons() : [btnCompile, btnRun, itemRules, itemAI], async () => {
      try {
        if (kind === 'run') {
          const d = await call('/api/cpp/run', { code, stdin: s.stdin, language: s.language });
          s.result = d.analysis || d;
          s.run = d.run || (d.ran ? d : null);
        } else {
          s.result = await call('/api/cpp/analyze', { code, language: s.language });
          s.run = null;
        }
        if (!s.result) s.result = { ok: false, error_count: 0, warning_count: 0, diagnostics: [] };
        s.lastCheckedCode = code; markEditor(s.result);
        s.tab = s.result.ok ? 'output' : 'problems';
        announce(s.result.ok ? (kind === 'run' ? 'Program finished' : 'Compiled successfully') : plural(s.result.error_count || 0, 'error') + ' found');
      } catch (e) { s.result = null; s.run = null; flash = notice('bad', e.message); s.tab = 'output'; }
      finally { working = null; }
    });
    renderResults(); updateStale();
  }

  async function heal(mode) {
    const code = ed.get();
    if (!code.trim()) { flash = notice('warn', 'Write, open or load some code first.'); s.tab = 'output'; renderResults(); return; }
    lastDecisionNote = null; healNote = null;
    working = 'heal'; s.tab = 'fix'; renderResults();
    await busy(allButtons(), async () => {
      try {
        const r = await call('/api/cpp/heal', { mode, code, language: s.language });
        if (!r.changed) {
          s.pending = null;
          healNote = el('div', null,
            notice(r.compiles ? 'ok' : 'warn', el('b', { text: 'No change proposed. ' }),
              r.compiles ? 'The code already compiles, so there is nothing to fix.' : 'No automatic fix was found for the remaining problems. Read the explanations in Problems and edit the code, or try the AI fix.'),
            el('div', { style: 'height:12px' }), StepsList(r.steps));
          if (!r.compiles) { s.result = await call('/api/cpp/analyze', { code, language: s.language }); s.run = null; s.lastCheckedCode = code; markEditor(s.result); }
          announce('No change proposed');
        } else {
          createProposal(r); announce('A change is proposed. Review the diff.');
        }
      } catch (e) { healNote = notice('bad', e.message); s.pending = null; }
      finally { working = null; }
    });
    renderResults(); updateStale();
  }

  /* ── layout ── */
  const editorWrap = el('div', { class: 'editor-wrap' }, ed.root,
    el('div', { class: 'drop-hint', 'aria-hidden': 'true' }, el('b', { text: 'Drop a code file to open it' }), el('span', { text: '.cpp  .c  .py  .java' })));
  enableFileDrop(editorWrap, (t, n) => loadCode(t, n), onFileError);

  root.append(
    el('div', { class: 'page-head compact' },
      el('div', null, el('h1', { text: 'Code Studio' }),
        el('p', { text: 'Write or open code in C++, C, Python, or Java, build it, run it, and get every problem explained.' })),
      el('div', { class: 'actions build-actions', role: 'group', 'aria-label': 'Build' }, fixMenu, btnCompile, btnRun)),
    !aiOK && el('p', { class: 'faint', style: 'margin:-12px 0 16px', text: 'AI fixes are off because no Gemini key is configured. Rule-based fixes work without one.' }),
    el('div', { class: 'ws' },
      el('section', { class: 'panel ide', 'aria-label': 'Code editor' },
        el('div', { class: 'toolbar', role: 'toolbar', 'aria-label': 'Editor actions' },
          langSelector,
          el('span', { class: 'file-pill' }, icon('file'), fileName),
          loader, picker, btnSave),
        editorWrap, stdinBox,
        el('div', { class: 'panel-foot' },
          el('span', { class: 'foot-left' }, cursorInfo, staleChip),
          el('span', { text: 'Ctrl+Enter run · Ctrl+Shift+Enter compile only · Esc then Tab leaves the editor' }))),
      el('section', { class: 'panel results', 'aria-label': 'Results' }, tabList, panel)));
  renderResults(); updateStale(); updateInputHint();
  if (s.result) markEditor(s.result);
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
        'When a fix is suggested in the C++ workspace it appears here with its diff. Nothing is applied until you accept it, and accepted changes can be undone.')));
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
      if (p.status === 'pending') act.append(
        el('button', { class: 'btn primary', onClick: () => run('accept') }, icon('check'), 'Accept'),
        el('button', { class: 'btn', onClick: () => run('reject') }, icon('x'), 'Reject')
      );
      if (p.status === 'accepted') act.append(
        el('button', { class: 'btn', onClick: () => run('undo') }, icon('undo'), 'Undo')
      );
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
