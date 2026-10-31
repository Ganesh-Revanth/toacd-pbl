'use strict';
/* pages-evidence.js — Benchmark results and Architecture (before / after). */

/* ── Benchmark ───────────────────────────────────────────────────────── */
function Bar(label, value, count, total, cls) {
  return el('div', { class: 'bar-row' },
    el('span', { text: label }),
    el('div', { class: 'bar-track', role: 'img', 'aria-label': label + ': ' + pct(value) }, el('div', { class: 'bar-fill ' + (cls || ''), style: 'width:' + (value || 0) + '%' })),
    el('span', { class: 'bar-val', text: pct(value) }));
}
const mark = (v) => v === 'yes' ? el('span', { class: 'mark y', 'aria-label': 'fixed', text: '✓' })
  : v === 'no' ? el('span', { class: 'mark n', 'aria-label': 'not fixed', text: '✕' })
  : el('span', { class: 'mark c', 'aria-label': 'not needed', text: '–' });

async function pageBenchmark(root) {
  root.append(el('div', { class: 'page-head' }, el('div', null, el('h1', { text: 'Benchmark' }),
    el('p', { text: 'Measured results from results/final.csv. Every figure here is recomputed from the raw rows when the page loads.' }))));
  const host = el('div'); root.append(host);
  let b;
  try { b = await call('/api/benchmark'); } catch (e) { host.append(notice('bad', e.message)); return; }
  const h = b.healing;

  host.append(
    el('p', { class: 'lede', text: 'Of ' + h.broken + ' C++ files that failed to compile, the rule-based healer fixed ' + h.rule_fixed + ' and the Gemini agent fixed ' + h.ai_fixed + '.' }),
    el('div', { class: 'bars' },
      Bar('Rule-based healer', h.rule_rate, h.rule_fixed, h.broken),
      Bar('Gemini agent', h.ai_rate, h.ai_fixed, h.ai_ran, 'ai')),
    el('p', { class: 'faint', style: 'max-width:70ch', text: 'Averages: ' + (h.rule_avg_s ?? '—') + 's per file for rules, ' + (h.ai_avg_s ?? '—') + 's for the agent. ' + h.note }),
    h.ai_guardrail_blocked ? el('p', { class: 'faint', style: 'max-width:70ch;margin-top:6px', text: h.ai_guardrail_blocked + ' of the agent’s ' + (h.ai_ran - h.ai_fixed) + ' misses came back almost instantly: the security guardrail refused those attack-test files on purpose, before any model call.' }) : null,
    el('p', { class: 'faint', style: 'max-width:70ch;margin-top:6px', text: h.already_clean + ' of ' + h.total_fixtures + ' fixtures already compiled and are left out of the rates. The error classifier matched its label on ' + pct(h.classifier_accuracy) + ' of files; those labels are partly guessed from file names, so treat that number loosely.' }));

  const onlyBroken = el('input', { type: 'checkbox', id: 'only-broken', checked: true });
  const tbody = el('tbody');
  const paint = () => {
    tbody.replaceChildren(...b.per_file.filter(r => !onlyBroken.checked || !r.baseline_clean).map(r => el('tr', null,
      el('td', { class: 'mono', text: r.file }),
      el('td', { class: 'num' }, r.baseline_clean ? mark('clean') : mark(r.rule)),
      el('td', { class: 'num' }, r.baseline_clean ? mark('clean') : mark(r.ai)),
      el('td', { class: 'num', text: r.baseline_clean ? '' : (r.rule_time ?? '').toString() }),
      el('td', { class: 'num', text: r.baseline_clean ? '' : (r.ai_time ?? '').toString() }))));
  };
  onlyBroken.addEventListener('change', paint); paint();
  host.append(
    el('div', { class: 'section-title', style: 'margin-top:32px', text: 'File by file' }),
    el('label', { style: 'display:flex;gap:8px;align-items:center;margin-bottom:8px' }, onlyBroken, 'Only files that needed repair'),
    el('div', { class: 'scroll' }, el('table', { class: 'data' },
      el('thead', null, el('tr', null, el('th', { text: 'File' }), el('th', { class: 'num', text: 'Rules' }), el('th', { class: 'num', text: 'Gemini' }), el('th', { class: 'num', text: 'Rules (s)' }), el('th', { class: 'num', text: 'Gemini (s)' }))), tbody)));
}

/* ── Architecture diagrams ───────────────────────────────────────────── */
function Box(n) {
  const g = svg('g', { transform: 'translate(' + n.x + ',' + n.y + ')' });
  g.append(svg('rect', { class: 'box' + (n.isNew ? ' new' : ''), width: n.w, height: n.h, rx: 6 }));
  g.append(svg('text', { class: 't1', x: 12, y: n.sub ? n.h / 2 - 2 : n.h / 2 + 4.5 }, n.t));
  if (n.sub) g.append(svg('text', { class: 't2', x: 12, y: n.h / 2 + 15 }, n.sub));
  if (n.isNew) g.append(svg('text', { class: 'tag', x: n.w - 10, y: 14, 'text-anchor': 'end' }, 'NEW'));
  return g;
}
function Diagram(spec) {
  const root = svg('svg', { class: 'diagram', viewBox: '0 0 ' + spec.w + ' ' + spec.h, role: 'img', 'aria-label': spec.label });
  root.append(svg('defs', null,
    svg('marker', { id: 'arr-' + spec.id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, svg('path', { d: 'M0 0 L10 5 L0 10 z', fill: 'context-stroke' }))));
  (spec.bands || []).forEach(b => {
    root.append(svg('rect', { class: 'band', x: 8, y: b.y, width: spec.w - 16, height: b.h, rx: 10 }));
    root.append(svg('text', { class: 'band-title', x: 22, y: b.y + 20 }, b.t));
  });
  const byId = {}; spec.nodes.forEach(n => { byId[n.id] = n; });
  spec.edges.forEach(e => {
    root.append(svg('path', { class: 'edge' + (e.dash ? ' dash' : ''), d: e.d, 'marker-end': 'url(#arr-' + spec.id + ')' }));
    if (e.label) root.append(svg('text', { class: 'elabel', x: e.lx, y: e.ly }, e.label));
  });
  spec.nodes.forEach(n => root.append(Box(n)));
  return root;
}
const N = (id, x, y, w, h, t, sub, isNew) => ({ id, x, y, w, h, t, sub, isNew });

const BEFORE = {
  id: 'before', w: 1060, h: 360, label: 'Architecture before: C++ source goes through g++, an error parser, an ML classifier and explainer, then a rule-based healer and the PyQt GUI.',
  bands: [{ y: 14, h: 120, t: 'Diagnose' }, { y: 150, h: 112, t: 'Repair & present' }, { y: 278, h: 70, t: 'Side analyzers' }],
  nodes: [
    N('src', 24, 52, 176, 60, 'C++ source'),
    N('gxx', 224, 52, 176, 60, 'g++ runner', 'compiler_runner.py'),
    N('par', 424, 52, 176, 60, 'Error parser', 'error_parser, normalizer'),
    N('clf', 624, 52, 176, 60, 'ML classifier', 'scikit-learn, 67k rows'),
    N('exp', 824, 52, 212, 60, 'Explainer + glossary', 'error_explainer.py'),
    N('rul', 24, 188, 176, 60, 'Rule-based healer', 'auto_healer.py'),
    N('lop', 224, 188, 176, 60, 'Heal loop', 'up to 3 attempts'),
    N('dif', 424, 188, 176, 60, 'Diff viewer', 'diff_viewer.py'),
    N('gui', 624, 188, 176, 60, 'PyQt6 GUI', 'gui.py'),
    N('ast', 24, 300, 176, 38, 'clang AST extractor'),
    N('sec', 224, 300, 176, 38, 'Security analyzer'),
    N('cal', 424, 300, 176, 38, 'Call graph + energy'),
  ],
  edges: [
    { d: 'M200 82 H224' }, { d: 'M400 82 H424' }, { d: 'M600 82 H624' }, { d: 'M800 82 H824' },
    { d: 'M930 112 V150 H112 V188' },
    { d: 'M200 218 H224' }, { d: 'M400 218 H424' }, { d: 'M600 218 H624' },
  ],
};

const AFTER = {
  id: 'after', w: 1060, h: 480, label: 'Architecture after: C++ compiler pipeline with two-tier self-healing (rule-based and Gemini agent) with interactive diff review; backed by an LLM client and security guardrail; PyQt6 desktop app, web studio, and benchmark harness sit on top.',
  bands: [
    { y: 12, h: 188, t: 'C++ self-healing track' },
    { y: 212, h: 100, t: 'AI layer & security' },
    { y: 324, h: 140, t: 'Interfaces & evidence' }
  ],
  nodes: [
    N('src', 24, 56, 150, 60, 'C++ source'),
    N('gxx', 200, 56, 170, 60, 'g++ + diagnostics', 'runner, parser, normalizer'),
    N('clf', 396, 56, 170, 60, 'Classifier + explainer', 'ML + glossary'),
    N('rul', 612, 44, 200, 52, 'Tier 1: rule healer', 'auto_healer (deterministic)'),
    N('ai1', 612, 116, 200, 60, 'Tier 2: Gemini agent', 'ReAct loop, up to 6 steps'),
    N('acc', 850, 78, 186, 60, 'Diff → accept / reject', 'nothing applied silently', true),
    N('grd', 340, 236, 230, 60, 'Security guardrail', 'aai_guardrail.py (checks prompts/patches)'),
    N('llm', 612, 236, 200, 60, 'LLM client', 'cache · retry · mock mode', true),
    N('qt', 24, 360, 220, 60, 'PyQt6 desktop app', 'compiler, healing, AST, graph'),
    N('web', 270, 360, 220, 60, 'Web studio', 'C++ Studio · diffs · benchmark', true),
    N('bm', 516, 360, 250, 60, 'Benchmark harness', '51 C++ fixtures (healing suite)', true),
    N('csv', 792, 360, 244, 60, 'results/final.csv', 'accuracy & heal rate evidence', true),
  ],
  edges: [
    { d: 'M174 86 H200' }, { d: 'M370 86 H396' }, { d: 'M566 86 H612' }, { d: 'M566 96 H590 V146 H612' },
    { d: 'M812 70 H831 V108 H850' }, { d: 'M812 146 H831 V108' },
    { d: 'M712 176 V200 H455 V236', dash: true, label: 'calls checked by guardrail', lx: 470, ly: 195 },
    { d: 'M570 266 H612', dash: true },
    { d: 'M766 390 H792' },
  ],
};

function pageArchitecture(root) {
  let view = state.archView || 'after';
  const host = el('div');
  const b1 = el('button', { 'aria-pressed': 'false', onClick: () => set('before') }, 'Before');
  const b2 = el('button', { 'aria-pressed': 'false', onClick: () => set('after') }, 'After');
  function set(v) {
    view = v; state.archView = v;
    b1.setAttribute('aria-pressed', String(v === 'before')); b2.setAttribute('aria-pressed', String(v === 'after'));
    host.replaceChildren(
      el('div', { class: 'panel' }, el('div', { class: 'panel-body' }, Diagram(v === 'before' ? BEFORE : AFTER))),
      el('div', { class: 'legend' }, el('span', null, el('i'), 'Existing component'), v === 'after' ? el('span', null, el('i', { class: 'new' }), 'Added in this version') : null,
        v === 'after' ? el('span', null, el('i', { class: 'dash' }), 'Dashed line = AI traffic or verification') : null),
      el('p', { class: 'muted', style: 'margin-top:16px;max-width:72ch', text: v === 'before'
        ? 'The original tool wrapped g++: it parsed compiler messages, classified them, explained them and applied hand-written repair rules.'
        : 'The improved architecture wraps g++ with a two-tier self-healing pipeline: fast deterministic rule repair (Tier 1) backed by an LLM agent (Tier 2) when rules fail. Every AI call is protected by a security guardrail, all proposed patches require user approval via diff review before applying, and the system is verified by a 51-fixture benchmark harness across desktop PyQt and web studio interfaces.' }));
  }
  root.append(el('div', { class: 'page-head' }, el('div', null, el('h1', { text: 'Architecture' }),
    el('p', { text: 'How the project looked before this work and how it is organised now. Box subtitles name the source files.' })),
    el('div', { class: 'seg', role: 'group', 'aria-label': 'Version' }, b1, b2)), host);
  set(view);
}
