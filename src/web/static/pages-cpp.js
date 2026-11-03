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
    attack_blocked: r.attack_blocked,
    review_required: r.review_required,
    risk_level: r.risk_level,
    risk_score: r.risk_score,
    reason: r.reason,
    action_taken: r.action_taken,
    evidence: r.evidence,
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

/* ── Energy Telemetry Helpers ──────────────────────────────────────────── */
function getEnergyHistory() {
  try {
    const raw = localStorage.getItem('studio:energy_history');
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}
function pushEnergyHistory(entry) {
  try {
    const list = getEnergyHistory();
    list.push(entry);
    while (list.length > 20) list.shift();
    localStorage.setItem('studio:energy_history', JSON.stringify(list));
  } catch (e) {}
}
function clearEnergyHistory() {
  try {
    localStorage.removeItem('studio:energy_history');
  } catch (e) {}
}

function formatTime(s) {
  if (s == null) return '—';
  if (s < 0.001) return (s * 1000000).toFixed(0) + ' µs';
  if (s < 1) return (s * 1000).toFixed(1) + ' ms';
  return s.toFixed(3) + ' s';
}
function formatEnergy(j) {
  if (j == null) return '—';
  if (j < 0.001) return (j * 1000).toFixed(3) + ' mJ';
  if (j < 1) return (j * 1000).toFixed(2) + ' mJ';
  return j.toFixed(4) + ' J';
}
function formatCO2(mg) {
  if (mg == null) return '—';
  if (mg < 0.001) return (mg * 1000).toFixed(2) + ' µg';
  if (mg < 1) return mg.toFixed(3) + ' mg';
  return mg.toFixed(2) + ' mg';
}

function makePopover(title, rows) {
  const pop = el('div', { class: 'energy-popover' });
  const body = el('div', { class: 'energy-pop-body', hidden: true },
    rows.map(r => el('div', { class: 'energy-pop-row' }, el('b', { text: r[0] + ': ' }), r[1]))
  );
  const btn = el('span', {
    class: 'energy-pop-btn',
    role: 'button',
    tabindex: '0',
    'aria-expanded': 'false',
    onClick: () => {
      const open = body.hidden;
      body.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
      btn.textContent = open ? '▲ Hide assumptions' : '▼ View assumptions';
    }
  }, '▼ View assumptions');
  pop.append(btn, body);
  return pop;
}

function renderEnergyChart(history, onClear) {
  const chartCard = el('div', { class: 'panel energy-section-card' },
    el('div', { class: 'energy-sec-head' },
      el('h3', { text: 'Estimated Energy History (Last 20 Runs)' }),
      el('div', { class: 'actions' },
        el('button', {
          class: 'btn quiet',
          disabled: !history || history.length === 0,
          onClick: onClear
        }, 'Clear history')
      )
    )
  );

  const wrap = el('div', { class: 'energy-chart-wrap' });
  const w = 620, h = 180;
  const padL = 60, padR = 25, padT = 25, padB = 35;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const svgKids = [];

  // Axes lines
  svgKids.push(
    svg('line', { x1: padL, y1: padT, x2: padL, y2: padT + plotH, stroke: 'var(--line)', 'stroke-width': '1' }),
    svg('line', { x1: padL, y1: padT + plotH, x2: padL + plotW, y2: padT + plotH, stroke: 'var(--line)', 'stroke-width': '1' })
  );

  if (!history || history.length === 0) {
    svgKids.push(
      svg('text', {
        x: w / 2, y: padT + plotH / 2,
        fill: 'var(--ink-3)', 'font-size': '13',
        'text-anchor': 'middle'
      }, 'No runs recorded in history yet. Click Compile & Run to measure energy.')
    );
  } else {
    const maxVal = Math.max(...history.map(item => (typeof item.energy_j === 'number' ? item.energy_j : 0)), 0.0005);
    const yMax = maxVal * 1.2;

    const ticks = [0, yMax / 2, yMax];
    ticks.forEach(tVal => {
      const y = padT + plotH - (tVal / yMax) * plotH;
      svgKids.push(
        svg('line', { x1: padL - 4, y1: y, x2: padL + plotW, y2: y, stroke: 'var(--line)', 'stroke-dasharray': '2 3', 'stroke-width': '1' }),
        svg('text', { x: padL - 8, y: y + 4, fill: 'var(--ink-3)', 'font-size': '10', 'text-anchor': 'end' }, (tVal < 0.01 ? (tVal * 1000).toFixed(1) + ' mJ' : tVal.toFixed(3) + ' J'))
      );
    });

    const count = history.length;
    const slotW = plotW / Math.max(count, 10);
    const barW = Math.max(6, Math.min(26, slotW * 0.65));

    history.forEach((run, idx) => {
      const eVal = typeof run.energy_j === 'number' ? run.energy_j : 0;
      const barH = Math.max(2, (eVal / yMax) * plotH);
      const x = padL + idx * slotW + (slotW - barW) / 2;
      const y = padT + plotH - barH;

      const titleNode = svg('title', {}, `${run.label || 'Run ' + (idx + 1)}: ${formatEnergy(run.energy_j)} (CPU: ${formatTime(run.cpu_s)})`);
      svgKids.push(
        svg('rect', {
          class: 'energy-bar',
          x: x, y: y,
          width: barW, height: barH,
          rx: 3,
          fill: 'var(--accent)'
        }, titleNode),
        svg('text', {
          x: x + barW / 2, y: padT + plotH + 16,
          fill: 'var(--ink-3)', 'font-size': '10',
          'text-anchor': 'middle'
        }, `#${idx + 1}`)
      );
    });
  }

  svgKids.push(
    svg('text', {
      x: padL, y: padT - 8,
      fill: 'var(--ink-3)', 'font-size': '11', 'font-weight': '600',
      'text-anchor': 'start'
    }, 'Energy (J)')
  );

  const chartSvg = svg('svg', {
    viewBox: `0 0 ${w} ${h}`,
    class: 'energy-svg-chart',
    role: 'img',
    'aria-label': 'Estimated energy bar chart for last 20 runs'
  }, svgKids);

  wrap.append(chartSvg);
  chartCard.append(wrap);
  return chartCard;
}

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
  s.energy = s.energy || null;
  s.cfg = s.cfg || null;
  s.cfgLoading = false;
  s.cfgLastError = null;
  s.cfgSelectedFunc = s.cfgSelectedFunc || null;
  s.cfgSelectedBlock = s.cfgSelectedBlock || null;
  s.astData = s.astData || null;
  s.astLoading = false;
  s.astError = null;
  if (s.baseline === undefined) s.baseline = s.code;
  const aiOK = state.status.ai_ready;
  let working = null;          // null | 'compile' | 'run' | 'heal'
  let flash = null;            // a one-off message shown at the top of the Output tab
  let healNote = null;         // "no change proposed" explanation
  let lastDecisionNote = null;
  let cmpResult = null;
  let cmpLoading = false;
  let cmpError = null;

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
    s.result = null; s.run = null; s.energy = null; s.pending = null; s.lastCheckedCode = null;
    s.cfg = null; s.cfgLastError = null; s.cfgSelectedFunc = null; s.cfgSelectedBlock = null;
    s.astData = null; s.astError = null;
    cmpResult = null; cmpError = null;
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
    s.result = null; s.run = null; s.energy = null; s.pending = null; s.lastCheckedCode = null; s.tab = 'output';
    s.cfg = null; s.cfgLastError = null; s.cfgSelectedFunc = null; s.cfgSelectedBlock = null;
    s.astData = null; s.astError = null;
    cmpResult = null; cmpError = null;
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
  const TABS = [
    ['output', 'Output'],
    ['energy', 'Energy'],
    ['ast', 'Syntax tree'],
    ['cfg', 'Control flow'],
    ['problems', 'Problems'],
    ['fix', 'Fix']
  ];
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
    TABS.forEach(([id]) => {
      if (tabBtn[id]) {
        tabBtn[id].setAttribute('aria-selected', String(id === s.tab));
        tabBtn[id].tabIndex = id === s.tab ? 0 : -1;
      }
    });
    const n = r ? r.error_count + r.warning_count : 0;
    if (badge.problems) {
      badge.problems.hidden = !n;
      badge.problems.textContent = String(n);
      badge.problems.className = 'badge' + (r && r.error_count ? ' bad' : ' warn');
    }
    if (badge.fix) {
      badge.fix.hidden = !(s.pending && s.pending.status === 'pending');
      badge.fix.textContent = '1';
      badge.fix.className = 'badge ok';
    }
    if (badge.cfg) {
      const fnList = s.cfg?.functions || (s.cfg ? [s.cfg] : []);
      const hasUnreachable = fnList.some(f => f.unreachable && f.unreachable.length > 0);
      badge.cfg.hidden = !hasUnreachable;
      badge.cfg.textContent = '!';
      badge.cfg.className = 'badge warn';
      badge.cfg.title = 'Dead code detected';
    }
    panel.setAttribute('aria-labelledby', 'rtab-' + s.tab);
    panel.replaceChildren(
      s.tab === 'problems' ? problemsView() :
      s.tab === 'fix' ? fixView() :
      s.tab === 'energy' ? energyView() :
      s.tab === 'ast' ? astTabView() :
      s.tab === 'cfg' ? cfgView() :
      outputView()
    );
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
      el('h2', { text: r.ok ? (r.warning_count ? 'Compiles, with warnings' : 'Compiles cleanly') : plural(r.error_count || 0, 'error') + (r.warning_count ? ', ' + plural(r.warning_count, 'warning') : '') }),
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

    // Security Alert for flagged or blocked patches
    if (p.attack_blocked || p.review_required || (p.risk_level && ['MEDIUM', 'HIGH', 'CRITICAL'].includes(p.risk_level))) {
      const isBad = p.attack_blocked || p.risk_level === 'CRITICAL' || p.risk_level === 'HIGH';
      parts.push(
        notice(isBad ? 'bad' : 'warn',
          el('div', { class: 'security-alert-box' },
            el('div', { style: 'font-weight:600;margin-bottom:4px' },
              (isBad ? '🚨' : '⚠️') + ' Security Alert: [' + (p.risk_level || 'REVIEW') + '] Risk Score: ' + (p.risk_score != null ? p.risk_score : '—') + '/100'),
            el('div', { class: 'faint', text: 'Reason: ' + (p.reason || 'Flagged by AAI Guardrail for elevated security risk.') }),
            el('div', { class: 'faint', style: 'margin-top:2px', text: 'Action: ' + (p.action_taken || 'Manual inspection required before applying.') })
          )
        ),
        el('div', { style: 'height:10px' })
      );
    }

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

  /* ── Energy tab ── */
  async function runCompare() {
    const code = ed.get();
    if (!code.trim()) {
      flash = notice('warn', 'Write or open code first before comparing optimizations.');
      s.tab = 'output';
      renderResults();
      return;
    }
    cmpLoading = true;
    cmpError = null;
    cmpResult = null;
    renderResults();
    try {
      const data = await call('/api/energy/compare', {
        code,
        stdin: s.stdin,
        language: s.language
      });
      if (!data.ok) {
        cmpError = data.error || 'Optimization benchmark failed';
      } else {
        cmpResult = data;
      }
    } catch (err) {
      cmpError = err.message;
    } finally {
      cmpLoading = false;
      renderResults();
    }
  }

  function renderCompareSection() {
    const head = el('div', { class: 'energy-cmp-header' },
      el('div', null,
        el('h3', { text: 'Compiler Optimization Impact (-O0 vs -O2)' }),
        el('p', { class: 'muted', style: 'margin:2px 0 0', text: 'Builds and runs your code 3 times each with -O0 and -O2 to measure efficiency gains.' })
      ),
      el('button', {
        class: 'btn' + (cmpLoading ? ' busy' : ''),
        disabled: cmpLoading,
        onClick: runCompare
      }, cmpLoading ? el('span', { class: 'spinner' }) : icon('play'), cmpLoading ? ' Benchmarking…' : ' Compare -O0 and -O2')
    );

    const body = el('div');
    if (cmpError) {
      body.append(notice('bad', el('b', { text: 'Comparison failed: ' }), cmpError));
    } else if (cmpResult) {
      const parts = [];
      if (cmpResult.outputs_differ) {
        parts.push(notice('bad', el('b', { text: '⚠️ Potential Undefined Behaviour: ' }), cmpResult.diff_warning || 'The outputs of -O0 and -O2 differed!'));
      }
      const sv = cmpResult.saved || {};
      const pill = sv.energy_pct != null
        ? el('div', { style: 'margin-bottom:10px' },
            el('span', { class: 'chip ok energy-saved-pill' }, '⚡ ' + sv.energy_pct + '% estimated energy saved with -O2' + (sv.energy_j ? ' (' + sv.energy_j + ' J)' : ''))
          )
        : null;

      const tbl = el('table', { class: 'tbl energy-cmp-tbl' },
        el('thead', null,
          el('tr', null,
            el('th', { text: 'Metric (Median of 3)' }),
            el('th', { text: '-O0 (Baseline)' }),
            el('th', { text: '-O2 (Optimized)' }),
            el('th', { text: 'Savings' })
          )
        ),
        el('tbody', null,
          el('tr', null,
            el('td', null, el('b', { text: 'Estimated Energy' })),
            el('td', { text: formatEnergy(cmpResult.o0?.median_energy_j) }),
            el('td', { text: formatEnergy(cmpResult.o2?.median_energy_j) }),
            el('td', null, el('b', { text: sv.energy_pct != null ? sv.energy_pct + '%' : '—' }))
          ),
          el('tr', null,
            el('td', null, el('b', { text: 'CPU Time' })),
            el('td', { text: formatTime(cmpResult.o0?.median_cpu_s) }),
            el('td', { text: formatTime(cmpResult.o2?.median_cpu_s) }),
            el('td', { text: sv.cpu_pct != null ? sv.cpu_pct + '%' : '—' })
          ),
          el('tr', null,
            el('td', null, el('b', { text: 'Run Time (Wall)' })),
            el('td', { text: formatTime(cmpResult.o0?.median_wall_s) }),
            el('td', { text: formatTime(cmpResult.o2?.median_wall_s) }),
            el('td', { text: sv.wall_pct != null ? sv.wall_pct + '%' : '—' })
          )
        )
      );
      body.append(pill, tbl);
    }

    return el('div', { class: 'panel energy-section-card', style: 'margin-top:16px' }, head, body);
  }

  function energyView() {
    if (working === 'run') return workingView();
    const en = s.energy;
    const parts = [];

    if (!en && !s.run) {
      parts.push(el('div', { class: 'empty' },
        el('b', { text: 'No energy measurement yet' }),
        'Press ', el('b', { text: 'Compile & Run' }), ' to execute your program and measure CPU time, memory, estimated energy, and carbon footprint.'
      ));
    } else if (en) {
      const assump = en.assumptions || {};
      const cards = [
        el('div', { class: 'panel energy-card' },
          el('div', { class: 'energy-card-header' }, el('b', { text: 'Run time' })),
          el('div', { class: 'metric-val' }, formatTime(en.wall_s)),
          el('div', { class: 'energy-card-sub muted', text: en.compile_wall_s != null ? 'Compile: ' + formatTime(en.compile_wall_s) : 'Wall clock' })
        ),
        el('div', { class: 'panel energy-card' },
          el('div', { class: 'energy-card-header' }, el('b', { text: 'CPU time' })),
          el('div', { class: 'metric-val' }, formatTime(en.cpu_s)),
          el('div', { class: 'energy-card-sub muted', text: en.compile_cpu_s != null ? 'Compile: ' + formatTime(en.compile_cpu_s) : 'User + system' })
        ),
        el('div', { class: 'panel energy-card' },
          el('div', { class: 'energy-card-header' }, el('b', { text: 'Peak memory' })),
          el('div', { class: 'metric-val' }, en.peak_mem_mb != null ? en.peak_mem_mb.toFixed(2) + ' MB' : '—'),
          el('div', { class: 'energy-card-sub muted', text: 'Child process RSS' })
        ),
        el('div', { class: 'panel energy-card' },
          el('div', { class: 'energy-card-header' },
            el('b', { text: 'Estimated energy' }),
            el('span', { class: 'chip warn estimated-pill' }, 'Estimated')
          ),
          el('div', { class: 'metric-val' }, formatEnergy(en.est_energy_j)),
          el('div', { class: 'energy-est-expl', text: 'from CPU time, not a power meter' }),
          makePopover('Assumptions', [
            ['Method', en.method || 'estimated from CPU time'],
            ['Assumed CPU power', (assump.cpu_watts || 15) + ' W (ENERGY_CPU_WATTS)'],
            ['Formula', 'E (J) = CPU_time (s) × CPU_watts (W)']
          ])
        ),
        el('div', { class: 'panel energy-card' },
          el('div', { class: 'energy-card-header' },
            el('b', { text: 'Estimated CO₂' }),
            el('span', { class: 'chip warn estimated-pill' }, 'Estimated')
          ),
          el('div', { class: 'metric-val' }, formatCO2(en.est_co2_mg)),
          el('div', { class: 'energy-est-expl', text: 'from CPU time, not a power meter' }),
          makePopover('Assumptions', [
            ['Grid intensity', (assump.grid_g_per_kwh || 475) + ' g CO₂/kWh (GRID_G_CO2_PER_KWH)'],
            ['Grid source', assump.grid_source || 'CodeCarbon global average / IEA'],
            ['Formula', 'CO₂ (mg) = E (J) / 3.6e6 × intensity × 1000']
          ])
        ),
      ];

      if (en.rapl_j != null) {
        cards.push(
          el('div', { class: 'panel energy-card' },
            el('div', { class: 'energy-card-header' },
              el('b', { text: 'Measured energy (RAPL)' }),
              el('span', { class: 'chip ok' }, 'Hardware counter')
            ),
            el('div', { class: 'metric-val' }, en.rapl_j.toFixed(4) + ' J'),
            el('div', { class: 'energy-card-sub muted', text: 'Direct /sys/class/powercap reading' })
          )
        );
      }

      parts.push(el('div', { class: 'energy-grid' }, cards));

      if (en.rapl_j == null) {
        parts.push(el('div', { class: 'energy-rapl-quiet', text: 'Hardware energy counters are not available on this computer' }));
      }
    }

    // SVG Bar Chart of last 20 runs
    const history = getEnergyHistory();
    parts.push(renderEnergyChart(history, () => {
      clearEnergyHistory();
      renderResults();
    }));

    // Optimization Comparison (-O0 vs -O2, hidden for Python and Java)
    if (s.language === 'cpp' || s.language === 'c') {
      parts.push(renderCompareSection());
    }

    return el('div', { class: 'stack-sm' }, parts);
  }

  /* ── Syntax Tree Tab View ── */
  function astTabView() {
    if (s.language === 'java') {
      return el('div', { class: 'empty' },
        el('b', { text: 'Syntax tree is not available for Java' }),
        el('p', { class: 'muted', style: 'margin-top:6px', text: 'Syntax tree visualization is not supported for Java yet. Switch to C++, C, or Python in Code Studio to inspect syntax trees.' })
      );
    }
    const code = s.code ? s.code.trim() : '';
    if (!code) {
      return emptyState('No code in editor', 'Write or paste code in the editor to view its syntax tree.');
    }
    if (s.astLoading) {
      return el('div', { class: 'working' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), 'Building the syntax tree…');
    }
    if (s.astError) {
      return el('div', { class: 'panel' },
        el('div', { class: 'empty' },
          el('b', { text: 'Syntax tree unavailable' }),
          el('p', { class: 'muted', style: 'margin-top:6px', text: s.astError }),
          el('div', { style: 'margin-top:12px' },
            el('button', { class: 'btn', onClick: () => { s.astData = null; s.astError = null; fetchAst(); } }, 'Retry')
          )
        )
      );
    }
    if (!s.astData) {
      fetchAst();
      return el('div', { class: 'working' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), 'Loading syntax tree…');
    }

    const roots = (s.astData.tree || []).map(normClang);
    if (!roots.length) {
      return emptyState('Parser produced no tree', 'Check syntax or toolchain.');
    }
    const treeObj = TreeView(roots);
    return el('div', { class: 'ast-tab-host' },
      el('div', { class: 'ast-tab-bar' },
        el('span', { class: 'chip' }, el('b', { text: String(s.astData.node_count || treeObj.count) }), ' nodes'),
        el('button', { class: 'btn quiet', onClick: () => { s.astData = null; s.astError = null; fetchAst(); } }, icon('sparkle'), ' Refresh')
      ),
      treeObj.root
    );
  }

  async function fetchAst() {
    if (s.astLoading) return;
    s.astLoading = true;
    s.astError = null;
    renderResults();
    try {
      const d = await call('/api/cpp/ast', { code: s.code, language: s.language });
      s.astData = d;
      s.astLoading = false;
    } catch (e) {
      s.astLoading = false;
      s.astError = e.message || 'Failed to load syntax tree.';
    }
    renderResults();
  }

  /* ── Control Flow Graph (CFG) Tab View ── */
  function cfgView() {
    if (s.language !== 'cpp' && s.language !== 'c') {
      return el('div', { class: 'empty' },
        el('b', { text: 'Control flow graphs are available for C and C++' }),
        el('p', { class: 'muted', style: 'margin-top:6px', text: 'Control flow analysis via LLVM IR is currently supported for C and C++. Switch language in the toolbar above.' })
      );
    }
    const code = s.code ? s.code.trim() : '';
    if (!code) {
      return emptyState('No code in editor', 'Write or paste C/C++ code, or load an example to view its control flow graph.');
    }
    if (s.cfgLoading) {
      return el('div', { class: 'working' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), 'Extracting control flow graph with clang…');
    }
    if (s.cfgLastError) {
      return el('div', { class: 'panel' },
        el('div', { class: 'empty' },
          el('b', { text: 'Control flow graph unavailable' }),
          el('p', { class: 'muted', style: 'margin-top:6px', text: s.cfgLastError }),
          el('div', { style: 'margin-top:12px' },
            el('button', { class: 'btn', onClick: () => { s.cfg = null; s.cfgLastError = null; fetchCfg(); } }, 'Retry')
          )
        )
      );
    }
    if (!s.cfg) {
      fetchCfg();
      return el('div', { class: 'working' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), 'Loading control flow graph…');
    }

    const fnList = (s.cfg.functions && s.cfg.functions.length) ? s.cfg.functions : [s.cfg];
    let activeFn = fnList.find(f => f.function === s.cfgSelectedFunc) || fnList[0];
    if (!activeFn) {
      return emptyState('No functions found', 'No user-defined functions were discovered in this translation unit.');
    }
    s.cfgSelectedFunc = activeFn.function;

    const m = activeFn.metrics || { blocks: 0, edges: 0, cyclomatic: 1, loops: 0 };
    const blocks = activeFn.blocks || [];
    const edges = activeFn.edges || [];
    const unreachable = activeFn.unreachable || [];

    // 1. One-sentence explainer at the top
    const explainer = el('p', { class: 'cfg-explainer' },
      'Each box is a stretch of code that runs straight through; arrows show where the program can go next.'
    );

    // 2. Toolbar: Function selector, metric chips, refresh
    const toolbar = el('div', { class: 'cfg-toolbar' });
    if (fnList.length > 1) {
      const select = el('select', {
        class: 'cfg-func-select select',
        'aria-label': 'Select function',
        onChange: (e) => {
          s.cfgSelectedFunc = e.target.value;
          s.cfgSelectedBlock = null;
          renderResults();
        }
      }, fnList.map(f => el('option', { value: f.function, selected: f.function === activeFn.function }, `Function: ${f.function}()`)));
      toolbar.append(select);
    } else {
      toolbar.append(el('span', { class: 'cfg-func-badge' }, el('b', { text: `Function: ${activeFn.function}()` })));
    }

    const chips = el('div', { class: 'cfg-chips' },
      el('span', { class: 'chip' }, el('b', { text: String(m.blocks) }), ' blocks'),
      el('span', { class: 'chip' }, el('b', { text: String(m.edges) }), ' edges'),
      el('span', { class: 'chip' }, el('b', { text: String(m.cyclomatic) }), ' cyclomatic complexity'),
      el('span', { class: 'chip' + (m.loops > 0 ? ' ok' : '') }, el('b', { text: String(m.loops) }), ' ' + (m.loops === 1 ? 'loop' : 'loops'))
    );
    toolbar.append(chips);

    const btnRefresh = el('button', {
      class: 'btn quiet',
      title: 'Re-extract control flow graph from current editor code',
      onClick: () => { s.cfg = null; s.cfgLastError = null; fetchCfg(); }
    }, icon('sparkle'), ' Refresh');
    toolbar.append(btnRefresh);

    // 3. Block selection
    let selBlock = blocks.find(b => b.id === s.cfgSelectedBlock);
    if (!selBlock && blocks.length > 0) {
      selBlock = blocks[0];
      s.cfgSelectedBlock = selBlock.id;
    }

    // 4. Adjacency maps
    const outEdges = {}, inEdges = {};
    blocks.forEach(b => { outEdges[b.id] = []; inEdges[b.id] = []; });
    edges.forEach(e => {
      if (outEdges[e.from]) outEdges[e.from].push(e);
      if (inEdges[e.to]) inEdges[e.to].push(e);
    });

    // 5. Layer assignment via BFS from entry
    const layerMap = {};
    const entryId = blocks.length ? blocks[0].id : null;
    if (entryId) {
      layerMap[entryId] = 0;
      const q = [entryId];
      while (q.length) {
        const cur = q.shift();
        const curL = layerMap[cur];
        (outEdges[cur] || []).forEach(e => {
          if (layerMap[e.to] === undefined) {
            layerMap[e.to] = curL + 1;
            q.push(e.to);
          }
        });
      }
    }
    let maxL = 0;
    Object.values(layerMap).forEach(l => { if (l > maxL) maxL = l; });
    blocks.forEach(b => {
      if (layerMap[b.id] === undefined) layerMap[b.id] = maxL + 1;
    });

    const layers = [];
    blocks.forEach(b => {
      const l = layerMap[b.id];
      if (!layers[l]) layers[l] = [];
      layers[l].push(b);
    });

    // 6. Coordinates calculation
    const NODE_W = 186;
    const NODE_H = 74;
    const GAP_X = 36;
    const GAP_Y = 56;
    const PAD_X = 36;
    const PAD_Y = 28;

    let maxRowW = 0;
    layers.forEach(row => {
      if (!row) return;
      const rowW = row.length * NODE_W + (row.length - 1) * GAP_X;
      if (rowW > maxRowW) maxRowW = rowW;
    });

    const svgW = Math.max(540, maxRowW + PAD_X * 2 + 80);
    const totalL = layers.length;
    const svgH = Math.max(260, PAD_Y * 2 + totalL * NODE_H + Math.max(0, totalL - 1) * GAP_Y + 20);

    const coords = {};
    layers.forEach((row, lIdx) => {
      if (!row) return;
      const rowW = row.length * NODE_W + (row.length - 1) * GAP_X;
      const startX = PAD_X + (maxRowW - rowW) / 2;
      const y = PAD_Y + lIdx * (NODE_H + GAP_Y);
      row.forEach((b, i) => {
        const x = startX + i * (NODE_W + GAP_X);
        coords[b.id] = { x, y, w: NODE_W, h: NODE_H, layer: lIdx };
      });
    });

    // 7. SVG Defs (Markers)
    const defs = svg('defs', null,
      svg('marker', { id: 'cfg-arrow-true', viewBox: '0 0 10 10', refX: '8', refY: '5', markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse' },
        svg('path', { d: 'M 0 1 L 10 5 L 0 9 z', fill: 'var(--ok, #24b47e)' })),
      svg('marker', { id: 'cfg-arrow-false', viewBox: '0 0 10 10', refX: '8', refY: '5', markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse' },
        svg('path', { d: 'M 0 1 L 10 5 L 0 9 z', fill: 'var(--bad, #e5484d)' })),
      svg('marker', { id: 'cfg-arrow-jump', viewBox: '0 0 10 10', refX: '8', refY: '5', markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse' },
        svg('path', { d: 'M 0 1 L 10 5 L 0 9 z', fill: 'var(--ink-3, #8a8a8a)' })),
      svg('marker', { id: 'cfg-arrow-switch', viewBox: '0 0 10 10', refX: '8', refY: '5', markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse' },
        svg('path', { d: 'M 0 1 L 10 5 L 0 9 z', fill: 'var(--ink-2, #666666)' }))
    );

    // 8. Edges
    const edgesGroup = svg('g', { class: 'cfg-edges-group' });
    const edgeLabelsGroup = svg('g', { class: 'cfg-edge-labels-group' });

    edges.forEach(e => {
      const A = coords[e.from];
      const B = coords[e.to];
      if (!A || !B) return;

      const isDownward = B.layer > A.layer;
      let dStr = '';
      let markerKind = e.kind;
      if (markerKind !== 'true' && markerKind !== 'false' && markerKind !== 'switch') {
        markerKind = 'jump';
      }

      if (isDownward) {
        const x1 = A.x + A.w / 2;
        const y1 = A.y + A.h;
        const x2 = B.x + B.w / 2;
        const y2 = B.y;
        const my = (y1 + y2) / 2;
        dStr = `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;

        if (e.kind === 'true' || e.kind === 'false') {
          const lx = x1 + (x2 - x1) * 0.35 + (e.kind === 'true' ? -18 : 14);
          const ly = y1 + 18;
          edgeLabelsGroup.append(
            svg('text', {
              class: 'cfg-edge-text ' + e.kind,
              x: lx,
              y: ly,
              'text-anchor': 'middle'
            }, e.kind)
          );
        }
      } else {
        // Back edge / Loop
        const x1 = A.x + A.w;
        const y1 = A.y + A.h / 2;
        const x2 = B.x + B.w;
        const y2 = B.y + B.h / 2;
        const arcX = Math.max(A.x + A.w, B.x + B.w) + 40;
        dStr = `M ${x1} ${y1} C ${arcX} ${y1}, ${arcX} ${y2}, ${x2} ${y2}`;

        if (e.kind === 'true' || e.kind === 'false') {
          edgeLabelsGroup.append(
            svg('text', {
              class: 'cfg-edge-text ' + e.kind,
              x: arcX - 8,
              y: (y1 + y2) / 2,
              'text-anchor': 'end'
            }, e.kind)
          );
        }
      }

      edgesGroup.append(
        svg('path', {
          class: 'cfg-edge cfg-edge-' + e.kind,
          d: dStr,
          'marker-end': `url(#cfg-arrow-${markerKind})`
        })
      );
    });

    // 9. Nodes
    const nodesGroup = svg('g', { class: 'cfg-nodes-group' });
    blocks.forEach(b => {
      const p = coords[b.id];
      if (!p) return;
      const isSel = (selBlock && selBlock.id === b.id);
      const isUnreach = !b.reachable;

      const nodeG = svg('g', {
        class: 'cfg-node' + (isSel ? ' selected' : '') + (isUnreach ? ' unreachable' : '') + (b.is_entry ? ' entry' : '') + (b.is_exit ? ' exit' : ''),
        transform: `translate(${p.x}, ${p.y})`,
        tabindex: '0',
        role: 'button',
        'aria-label': `${b.friendly} (${b.id}), ${b.instructions.length} instructions${isUnreach ? ', unreachable' : ''}`
      });

      const rect = svg('rect', {
        width: p.w,
        height: p.h,
        rx: '7',
        ry: '7',
        class: 'cfg-node-rect'
      });

      const titleTxt = svg('text', { class: 'cfg-node-title', x: 12, y: 22 }, b.friendly);
      const idTxt = svg('text', { class: 'cfg-node-id mono', x: 12, y: 42 }, '%' + b.id);
      const metaTxt = svg('text', { class: 'cfg-node-meta', x: 12, y: 60 },
        `${b.instructions.length} insts${b.is_entry ? ' · entry' : b.is_exit ? ' · exit' : ''}${isUnreach ? ' · DEAD' : ''}`
      );

      const onSelect = () => {
        s.cfgSelectedBlock = b.id;
        renderResults();
      };
      nodeG.addEventListener('click', onSelect);
      nodeG.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          onSelect();
        }
      });

      nodeG.append(rect, titleTxt, idTxt, metaTxt);
      nodesGroup.append(nodeG);
    });

    const svgElem = svg('svg', {
      class: 'cfg-graph-svg',
      viewBox: `0 0 ${svgW} ${svgH}`,
      width: svgW,
      height: svgH,
      role: 'img',
      'aria-label': `Control flow graph for ${activeFn.function}`
    }, defs, edgesGroup, edgeLabelsGroup, nodesGroup);

    const svgWrap = el('div', { class: 'cfg-svg-scroll' }, svgElem);

    // 10. Legend
    const legend = el('div', { class: 'cfg-legend' },
      el('span', { class: 'cfg-leg-item' }, el('span', { class: 'cfg-leg-line true' }), 'True branch'),
      el('span', { class: 'cfg-leg-item' }, el('span', { class: 'cfg-leg-line false' }), 'False branch'),
      el('span', { class: 'cfg-leg-item' }, el('span', { class: 'cfg-leg-line jump' }), 'Jump / Switch'),
      el('span', { class: 'cfg-leg-item' }, el('span', { class: 'cfg-leg-box unreach' }), 'Unreachable block')
    );

    // 11. Unreachable warning line under the graph
    let warningLine = null;
    if (unreachable.length > 0) {
      const msgs = unreachable.map(id => `Block ${id} can never run`);
      warningLine = el('div', { class: 'cfg-unreachable-warn' },
        el('span', { class: 'cfg-warn-icon' }, '⚠️'),
        el('span', { class: 'cfg-warn-msg', text: msgs.join('. ') + '.' })
      );
    }

    const graphPane = el('div', { class: 'cfg-graph-pane' },
      svgWrap,
      legend,
      warningLine
    );

    // 12. Side panel: Instructions & details
    const sidePane = el('aside', { class: 'cfg-side-pane', 'aria-label': 'Basic block details' });
    if (selBlock) {
      const inList = inEdges[selBlock.id] || [];
      const outList = outEdges[selBlock.id] || [];

      const head = el('div', { class: 'cfg-side-head' },
        el('div', null,
          el('h4', { class: 'cfg-side-title', text: selBlock.friendly }),
          el('div', { class: 'cfg-side-sub mono muted', text: '%' + selBlock.id })
        ),
        el('span', {
          class: 'badge ' + (selBlock.reachable ? (selBlock.is_entry ? 'ok' : 'info') : 'bad'),
          text: selBlock.reachable ? (selBlock.is_entry ? 'Entry' : 'Reachable') : 'Unreachable'
        })
      );

      const navSection = el('div', { class: 'cfg-side-nav' });
      if (inList.length) {
        navSection.append(
          el('div', { class: 'cfg-nav-row' },
            el('b', { text: 'Predecessors: ' }),
            ...inList.map(e => el('button', {
              class: 'linkish',
              onClick: () => { s.cfgSelectedBlock = e.from; renderResults(); }
            }, `%${e.from} (${e.kind})`))
          )
        );
      }
      if (outList.length) {
        navSection.append(
          el('div', { class: 'cfg-nav-row' },
            el('b', { text: 'Successors: ' }),
            ...outList.map(e => el('button', {
              class: 'linkish',
              onClick: () => { s.cfgSelectedBlock = e.to; renderResults(); }
            }, `%${e.to} (${e.kind})`))
          )
        );
      }
      if (selBlock.is_exit) {
        navSection.append(el('div', { class: 'cfg-nav-row muted' }, el('i', { text: 'Function exit block (return)' })));
      }

      const insts = selBlock.instructions || [];
      const instBox = el('div', { class: 'cfg-side-insts' },
        el('div', { class: 'cfg-side-inst-head' },
          el('span', { class: 'muted', text: `LLVM IR Instructions (${insts.length}):` })
        ),
        el('pre', { class: 'cfg-inst-code mono' },
          insts.length ? insts.map((ln, idx) => el('div', { class: 'cfg-inst-line' },
            el('span', { class: 'cfg-inst-no muted' }, String(idx + 1).padStart(2, ' ') + '  '),
            el('span', { text: ln })
          )) : el('div', { class: 'muted', text: '(no instructions in block)' })
        )
      );

      sidePane.append(head, navSection, instBox);
    } else {
      sidePane.append(el('div', { class: 'empty' }, 'Click any block in the graph to view its instructions.'));
    }

    const mainLayout = el('div', { class: 'cfg-main-layout' }, graphPane, sidePane);

    return el('div', { class: 'cfg-view' },
      explainer,
      toolbar,
      mainLayout
    );
  }

  async function fetchCfg() {
    if (s.cfgLoading) return;
    s.cfgLoading = true;
    s.cfgLastError = null;
    renderResults();
    try {
      const d = await call('/api/cfg', { code: s.code, language: s.language, function: s.cfgSelectedFunc });
      s.cfg = d;
      s.cfgLoading = false;
      if (d.function && !s.cfgSelectedFunc) {
        s.cfgSelectedFunc = d.function;
      }
    } catch (e) {
      s.cfgLoading = false;
      s.cfgLastError = e.message || 'Failed to extract control flow graph.';
    }
    renderResults();
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
          s.energy = d.energy || (d.run && d.run.energy) || null;
          if (s.energy && s.energy.est_energy_j != null) {
            pushEnergyHistory({
              time: Date.now(),
              label: (s.language || 'cpp').toUpperCase() + ' ' + (new Date()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
              lang: s.language || 'cpp',
              energy_j: s.energy.est_energy_j,
              cpu_s: s.energy.cpu_s,
              wall_s: s.energy.wall_s,
              peak_mem_mb: s.energy.peak_mem_mb,
              co2_mg: s.energy.est_co2_mg
            });
          }
        } else {
          s.result = await call('/api/cpp/analyze', { code, language: s.language });
          s.run = null;
          s.energy = null;
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
          if (r.attack_blocked) {
            healNote = el('div', null,
              notice('bad',
                el('div', { class: 'security-alert-box' },
                  el('div', { style: 'font-weight:600;margin-bottom:4px' }, '🚨 Security Alert: [' + (r.risk_level || 'CRITICAL') + '] Attack Blocked (Risk: ' + (r.risk_score != null ? r.risk_score : 100) + '/100)'),
                  el('div', { class: 'faint', text: 'Reason: ' + (r.reason || 'Malicious prompt injection or unsafe construct detected by AAI Guardrail.') }),
                  el('div', { class: 'faint', style: 'margin-top:2px', text: 'Action: ' + (r.action_taken || 'Execution halted. Malicious patch discarded.') })
                )
              ),
              el('div', { style: 'height:12px' }), StepsList(r.steps));
          } else {
            healNote = el('div', null,
              notice(r.compiles ? 'ok' : 'warn', el('b', { text: 'No change proposed. ' }),
                r.compiles ? 'The code already compiles, so there is nothing to fix.' : 'No automatic fix was found for the remaining problems. Read the explanations in Problems and edit the code, or try the AI fix.'),
              el('div', { style: 'height:12px' }), StepsList(r.steps));
          }
          if (!r.compiles) { s.result = await call('/api/cpp/analyze', { code, language: s.language }); s.run = null; s.lastCheckedCode = code; markEditor(s.result); }
          announce(r.attack_blocked ? 'Malicious attack blocked by guardrail' : 'No change proposed');
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
