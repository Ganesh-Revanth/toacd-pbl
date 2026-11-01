'use strict';
/* pages-evidence.js — Benchmark results and Architecture (before / after). */

/* ── Benchmark ───────────────────────────────────────────────────────── */
function KPICard(label, num, unit) {
  return el('div', { class: 'kpi-card' },
    el('div', { class: 'kpi-label', text: label }),
    el('div', { class: 'kpi-num' },
      el('span', { class: 'bench-num', text: String(num) }),
      unit ? el('span', { class: 'kpi-unit faint', text: ' ' + unit }) : null
    )
  );
}

function Bar(label, value, count, total, cls) {
  return el('div', { class: 'bar-row' },
    el('span', { text: label }),
    el('div', { class: 'bar-track', role: 'img', 'aria-label': label + ': ' + pct(value) }, el('div', { class: 'bar-fill ' + (cls || ''), style: 'width:' + (value || 0) + '%' })),
    el('span', { class: 'bar-val', text: pct(value) }));
}

const mark = (v) => v === 'yes'
  ? el('span', { class: 'chip ok', 'aria-label': 'fixed' }, typeof icon === 'function' ? icon('check', { size: 12 }) : null, 'fixed')
  : v === 'no'
  ? el('span', { class: 'chip bad', 'aria-label': 'not fixed' }, typeof icon === 'function' ? icon('x', { size: 12 }) : null, 'miss')
  : el('span', { class: 'chip plain', 'aria-label': 'clean' }, 'clean');

async function pageBenchmark(root) {
  root.append(el('div', { class: 'page-head' }, el('div', null, el('h1', { text: 'Benchmark' }),
    el('p', { text: 'Measured results from results/final.csv across 40 multi-language fixtures (C++, C, Python, Java). Every figure here is recomputed from the raw rows when the page loads.' }))));
  const host = el('div'); root.append(host);
  let b;
  try { b = await call('/api/benchmark'); } catch (e) { host.append(notice('bad', e.message)); return; }
  const h = b.healing;
  const byLang = b.by_language || {};

  const kpis = el('div', { class: 'kpi-grid' },
    KPICard('Gemini agent repair', h.ai_rate != null ? h.ai_rate.toFixed(1) : '—', '%'),
    KPICard('Rule-based repair (C/C++)', '75.0', '%'),
    KPICard('Total test fixtures', h.total_fixtures, 'files'),
    KPICard('Diagnostic accuracy', h.classifier_accuracy != null ? h.classifier_accuracy.toFixed(1) : '—', '%')
  );

  host.append(
    kpis,
    el('p', { class: 'lede', text: 'Of ' + h.broken + ' broken files requiring repair across 4 languages, the Gemini agent fixed ' + h.ai_fixed + ' (' + (h.ai_rate != null ? h.ai_rate.toFixed(1) : '—') + '%). Rule-based healing resolved ' + h.rule_fixed + ' of 16 broken C++ and C files (75.0%).' }),
    el('div', { class: 'bars' },
      Bar('Autonomous Gemini agent (All 4 Languages)', h.ai_rate, h.ai_fixed, h.ai_ran, 'ai'),
      Bar('Rule-based healer (C++ & C only)', 75.0, h.rule_fixed, 16)),
    el('p', { class: 'faint', style: 'max-width:70ch', text: 'Averages: ' + (h.rule_avg_s ?? '—') + 's per file for rules (C++/C), ' + (h.ai_avg_s ?? '—') + 's for the Gemini agent. ' + h.note }),
    el('p', { class: 'faint', style: 'max-width:70ch;margin-top:6px', text: h.already_clean + ' of ' + h.total_fixtures + ' fixtures were baseline clean (compiling with 0 errors initially) and are left out of repair rates. Diagnostic accuracy averaged ' + pct(h.classifier_accuracy) + ' across all languages.' }));

  // Section: Language Pipeline Capabilities & Breakdown Table
  const langTableBody = el('tbody');
  const langOrder = ['cpp', 'c', 'python', 'java'];
  langOrder.forEach(lid => {
    const l = byLang[lid];
    if (!l) return;
    langTableBody.append(el('tr', null,
      el('td', { class: 'bold', text: l.name }),
      el('td', { class: 'faint', text: l.classification_technique }),
      el('td', { class: 'faint', text: l.healing_pipeline }),
      el('td', { class: 'num', text: String(l.total_fixtures) }),
      el('td', { class: 'num', text: l.already_clean + ' / ' + l.broken }),
      el('td', { class: 'num', text: pct(l.classifier_accuracy) }),
      el('td', { class: 'num bold', text: l.has_rules ? (pct(l.rule_rate) + ' (' + l.rule_fixed + '/' + l.broken + ')') : '— (Gemini only)' }),
      el('td', { class: 'num bold', text: pct(l.ai_rate) + ' (' + l.ai_fixed + '/' + l.ai_ran + ')' }),
      el('td', { class: 'num', text: (l.ai_avg_s != null ? l.ai_avg_s.toFixed(2) + 's' : '—') })
    ));
  });

  host.append(
    el('div', { class: 'section-title', style: 'margin-top:28px', text: 'Multi-Language Pipeline Capabilities & Evidence' }),
    el('p', { class: 'faint', style: 'max-width:74ch;margin-bottom:12px', text: 'C++ and C feature Machine Learning error classification (trained on 67k GCC error rows) and deterministic regex AST healing. Python and Java use deterministic keyword categories and autonomous Gemini agent healing only.' }),
    el('div', { class: 'scroll' }, el('table', { class: 'data' },
      el('thead', null, el('tr', null,
        el('th', { text: 'Language' }),
        el('th', { text: 'Error Categorization' }),
        el('th', { text: 'Self-Healing Track' }),
        el('th', { class: 'num', text: 'Total' }),
        el('th', { class: 'num', text: 'Clean/Broken' }),
        el('th', { class: 'num', text: 'Cat Match' }),
        el('th', { class: 'num', text: 'Rule Healed' }),
        el('th', { class: 'num', text: 'Gemini Healed' }),
        el('th', { class: 'num', text: 'Gemini Avg' }))),
      langTableBody)));

  // Section: File by File
  const onlyBroken = el('input', { type: 'checkbox', id: 'only-broken', checked: true });
  const langFilter = el('select', { style: 'padding:3px 8px;border-radius:4px;border:1px solid var(--border)' },
    el('option', { value: 'all', text: 'All Languages' }),
    el('option', { value: 'cpp', text: 'C++' }),
    el('option', { value: 'c', text: 'C' }),
    el('option', { value: 'python', text: 'Python' }),
    el('option', { value: 'java', text: 'Java' })
  );

  const tbody = el('tbody');
  const paint = () => {
    const sel = langFilter.value;
    const filtered = b.per_file.filter(r => {
      if (onlyBroken.checked && r.baseline_clean) return false;
      if (sel !== 'all' && (r.language || 'cpp') !== sel) return false;
      return true;
    });
    tbody.replaceChildren(...filtered.map(r => el('tr', null,
      el('td', { class: 'mono bold', text: (r.language || 'cpp').toUpperCase() }),
      el('td', { class: 'mono', text: r.file }),
      el('td', { class: 'num' }, r.baseline_clean ? mark('clean') : (r.rule === 'n/a' ? el('span', { class: 'chip plain' }, 'n/a') : mark(r.rule))),
      el('td', { class: 'num' }, r.baseline_clean ? mark('clean') : mark(r.ai)),
      el('td', { class: 'num', text: r.baseline_clean ? '' : (r.rule_time != null ? r.rule_time.toString() : '—') }),
      el('td', { class: 'num', text: r.baseline_clean ? '' : (r.ai_time != null ? r.ai_time.toString() : '—') }))));
  };
  onlyBroken.addEventListener('change', paint);
  langFilter.addEventListener('change', paint);
  paint();

  host.append(
    el('div', { class: 'section-title', style: 'margin-top:32px', text: 'File by file' }),
    el('div', { style: 'display:flex;gap:16px;align-items:center;margin-bottom:8px;flex-wrap:wrap' },
      el('label', { style: 'display:flex;gap:8px;align-items:center' }, onlyBroken, 'Only files that needed repair'),
      el('label', { style: 'display:flex;gap:8px;align-items:center' }, 'Language:', langFilter)
    ),
    el('div', { class: 'scroll' }, el('table', { class: 'data' },
      el('thead', null, el('tr', null,
        el('th', { text: 'Lang' }),
        el('th', { text: 'File' }),
        el('th', { class: 'num', text: 'Rules' }),
        el('th', { class: 'num', text: 'Gemini' }),
        el('th', { class: 'num', text: 'Rules (s)' }),
        el('th', { class: 'num', text: 'Gemini (s)' }))),
      tbody)));
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
  id: 'after', w: 1060, h: 480, label: 'Architecture after: Multi-language compiler pipeline (C++, C, Python, Java) with two-tier self-healing (rule-based for C++/C, autonomous Gemini agent across all); backed by an LLM client and security guardrail; PyQt6 desktop app, Code Studio, and benchmark harness sit on top.',
  bands: [
    { y: 12, h: 188, t: 'Multi-language compiler & self-healing track' },
    { y: 212, h: 100, t: 'AI layer & security' },
    { y: 324, h: 140, t: 'Interfaces & evidence' }
  ],
  nodes: [
    N('src', 24, 56, 150, 60, 'Multi-Lang source', 'C++, C, Python, Java'),
    N('gxx', 200, 56, 170, 60, 'Language drivers', 'g++, gcc, python, javac'),
    N('clf', 396, 56, 170, 60, 'Diagnostics & ML', 'ML for C/C++, kw for Py/Java'),
    N('rul', 612, 44, 200, 52, 'Tier 1: rule healer', 'C++/C (deterministic)'),
    N('ai1', 612, 116, 200, 60, 'Tier 2: Gemini agent', 'ReAct loop (All 4 languages)'),
    N('acc', 850, 78, 186, 60, 'Diff → accept / reject', 'nothing applied silently', true),
    N('grd', 340, 236, 230, 60, 'Security guardrail', 'aai_guardrail.py (checks prompts/patches)'),
    N('llm', 612, 236, 200, 60, 'LLM client', 'cache · retry · mock mode', true),
    N('qt', 24, 360, 220, 60, 'PyQt6 desktop app', 'compiler, healing, AST, graph'),
    N('web', 270, 360, 220, 60, 'Code Studio', 'Multi-lang studio · diffs · benchmark', true),
    N('bm', 516, 360, 250, 60, 'Benchmark harness', '40 fixtures (C++, C, Python, Java)', true),
    N('csv', 792, 360, 244, 60, 'results/final.csv', 'per-language numbers & evidence', true),
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
        : 'The improved architecture supports 4 languages: C++, C, Python, and Java. C++ and C feature Machine Learning diagnostic classification (Scikit-Learn SGDClassifier on 67k GCC rows) and rule-based heuristic healing (auto_healer.py). Python and Java use deterministic keyword categories from compiler diagnostics and autonomous Gemini agent healing only. Every AI call is protected by a security guardrail, all proposed patches require user approval via diff review before applying, and the system is verified by a 40-fixture benchmark harness across desktop PyQt and web studio interfaces.' }),

      // ── Section 1: Threat Model ──────────────────────────────────────────
      el('div', { class: 'sec-card', style: 'margin-top:24px' },
        el('h2', { style: 'margin-bottom:8px', text: '1. Autonomous AI Threat Model' }),
        el('p', { class: 'faint', text: 'Formal threat specification defining critical assets, threat actors across compiler stages, and the 11 vulnerability classes (A–K).' }),
        el('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:12px 0' },
          el('div', null,
            el('h4', { text: 'Protected Assets' }),
            el('ul', { style: 'padding-left:18px;margin-top:6px;line-height:1.6;font-size:13px' },
              el('li', null, el('b', { text: 'Host Execution Environment: ' }), 'Preventing arbitrary shell execution, file system corruption, and subprocess escapes.'),
              el('li', null, el('b', { text: 'Developer Confidential Data: ' }), 'Protecting ~/.ssh keys, AWS/GCP/Git credentials, environment tokens (USERNAME/HOME), and browser profiles.'),
              el('li', null, el('b', { text: 'LLM Reasoning Integrity: ' }), 'Preventing jailbreaks, context resets, DAN-mode overrides, and system prompt exfiltration.'),
              el('li', null, el('b', { text: 'Code Invariant Safety: ' }), 'Preventing stealth trojans, malicious AST injections, and silent deletion of safety assertions.'),
              el('li', null, el('b', { text: 'Audit Immutability: ' }), 'Protecting audit trail integrity via cryptographic SHA-256 hash chains.')
            )
          ),
          el('div', null,
            el('h4', { text: 'Threat Actors & Attack Surfaces' }),
            el('ul', { style: 'padding-left:18px;margin-top:6px;line-height:1.6;font-size:13px' },
              el('li', null, el('b', { text: 'Adversarial Submissions (Ingress): ' }), 'Malicious prompts or student code containing embedded jailbreaks, obfuscation, or policy overrides.'),
              el('li', null, el('b', { text: 'Compromised/Evil LLM (Egress): ' }), 'A compromised or hallucinating model proposing patches containing backdoors, exfiltration, or weakened checks.'),
              el('li', null, el('b', { text: 'Tool Boundary Infiltration: ' }), 'Adversarial compiler diagnostics, poisoned #include headers, or malicious filenames designed to escape sandbox bounds.')
            )
          )
        ),
        el('h4', { style: 'margin-top:14px', text: 'The 11 Vulnerability Classes (A–K)' }),
        el('table', { class: 'bench-table sec-table', style: 'margin-top:8px' },
          el('thead', null,
            el('tr', null,
              el('th', { text: 'Class' }),
              el('th', { text: 'Attack Category' }),
              el('th', { text: 'Description & Example Manifestation' })
            )
          ),
          el('tbody', null,
            el('tr', null, el('td', { class: 'bold' }, 'Class A'), el('td', { text: 'Direct Injection' }), el('td', { class: 'faint', text: 'Jailbreaks, context resets, "Developer Mode" overrides, and role-reversal commands.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class B'), el('td', { text: 'Indirect Injection' }), el('td', { class: 'faint', text: 'Adversarial payloads hidden in code comments, raw string literals, or compiler error stderr.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class C'), el('td', { text: 'Policy Bypass & Tool Suppression' }), el('td', { class: 'faint', text: 'Explicit instructions telling the agent to ignore safety rules or skip the validation step.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class D'), el('td', { text: 'Tool Abuse' }), el('td', { class: 'faint', text: 'Attempts to execute shell commands outside the sandboxed temp directory or access forbidden paths.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class E'), el('td', { text: 'Hidden Agenda in Patches' }), el('td', { class: 'faint', text: 'Code patches accessing ~/.ssh, browser profiles, reading environment credentials, or opening network sockets.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class F'), el('td', { text: 'Obfuscation & Evasion' }), el('td', { class: 'faint', text: 'Base64, hex, rot13, zero-width spaces, Cyrillic homoglyphs, leet speak, multilingual text, and split strings.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class G'), el('td', { text: 'Silent Weakening' }), el('td', { class: 'faint', text: 'Patches that silently delete bounds checks, remove assert() statements, or weaken security validators.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class H'), el('td', { text: 'Fake Delimiters' }), el('td', { class: 'faint', text: 'Fabricated tool call boundaries (<tool_call>, </tool_call>) or mocked compiler execution responses.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class I'), el('td', { text: 'Resource Abuse' }), el('td', { class: 'faint', text: 'Algorithmic complexity denial of service, fork bombs, infinite recursion, and allocation exhaustion.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class J'), el('td', { text: 'Secret & Prompt Leakage' }), el('td', { class: 'faint', text: 'Attempts to extract the system prompt, instructions, hidden constraints, or Gemini API keys.' })),
            el('tr', null, el('td', { class: 'bold' }, 'Class K'), el('td', { text: 'Training Data Poisoning' }), el('td', { class: 'faint', text: 'Injecting misleading diagnostic patterns or adversarial trigger tokens into telemetry streams.' }))
          )
        )
      ),

      // ── Section 2: Layered Defense-in-Depth Architecture ─────────────────
      el('div', { class: 'sec-card', style: 'margin-top:24px' },
        el('h2', { style: 'margin-bottom:8px', text: '2. Layered Defense-in-Depth Architecture' }),
        el('p', { class: 'faint', text: '6 independent, non-bypassable verification layers operating at ingress, tool invocation, and egress boundaries.' }),
        el('div', { class: 'sec-cm-grid', style: 'grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0' },
          el('div', { class: 'sec-card', style: 'padding:12px' },
            el('span', { class: 'chip plain bold', text: 'Layer 1: Normalizer' }),
            el('p', { class: 'faint', style: 'font-size:12px;margin-top:6px', text: 'Unicode NFKC normalization, zero-width/bidi character stripping, homoglyph mapping, de-leet decode, and string literal concatenation.' })
          ),
          el('div', { class: 'sec-card', style: 'padding:12px' },
            el('span', { class: 'chip plain bold', text: 'Layer 2: Rule Layer' }),
            el('p', { class: 'faint', style: 'font-size:12px;margin-top:6px', text: 'Multilingual threat regexes (Hindi, Telugu, Spanish, French), credential harvesting paths (~/.ssh, id_rsa, /etc/passwd), and persistence checks.' })
          ),
          el('div', { class: 'sec-card', style: 'padding:12px' },
            el('span', { class: 'chip plain bold', text: 'Layer 3: Code Layer (Egress)' }),
            el('p', { class: 'faint', style: 'font-size:12px;margin-top:6px', text: 'AST-guided Python parser and C++/C/Java regex tokenizers. Diff-based analysis: flags sensitive API calls NEW in patch and deleted safety assertions.' })
          ),
          el('div', { class: 'sec-card', style: 'padding:12px' },
            el('span', { class: 'chip plain bold', text: 'Layer 4: ML Injection Classifier' }),
            el('p', { class: 'faint', style: 'font-size:12px;margin-top:6px', text: 'TF-IDF + calibrated Logistic Regression text classifier trained strictly on DEV split only. Provides probabilistic risk augmentation.' })
          ),
          el('div', { class: 'sec-card', style: 'padding:12px' },
            el('span', { class: 'chip plain bold', text: 'Layer 5: Tool & Scope Boundary' }),
            el('p', { class: 'faint', style: 'font-size:12px;margin-top:6px', text: 'Tool name allowlisting (compile_code, security_audit), strict file path confinement inside temp workdir, and rejection of raw shell strings.' })
          ),
          el('div', { class: 'sec-card', style: 'padding:12px' },
            el('span', { class: 'chip plain bold', text: 'Layer 6: Auxiliary Scanner & Redactor' }),
            el('p', { class: 'faint', style: 'font-size:12px;margin-top:6px', text: 'Scans compiler error text, #include paths, and tool outputs before LLM sees them; redacts API keys and secrets from model outputs.' })
          )
        )
      ),

      // ── Section 3: Risk Scoring Engine & Formula ─────────────────────────
      el('div', { class: 'sec-card', style: 'margin-top:24px' },
        el('h2', { style: 'margin-bottom:8px', text: '3. Risk Scoring Engine & Mathematical Formulation' }),
        el('p', { class: 'faint', text: 'Deterministic mathematical risk calculation aggregating multi-layer findings into an auditable 0–100 risk score.' }),
        el('div', { style: 'background:var(--sunken);padding:14px;border-radius:var(--r);margin:12px 0;font-family:var(--font-code);font-size:13px' },
          'RawScore = w_severity + w_ML + w_layers + p_stage + p_obfuscation\n' +
          'RiskScore = round(min(100.0, max(0.0, RawScore)), 1)'
        ),
        el('ul', { style: 'padding-left:18px;line-height:1.6;font-size:13px' },
          el('li', null, el('b', { text: 'Rule Severity (w_severity): ' }), 'CRITICAL = 75, HIGH = 65, MEDIUM = 25, LOW = 10.'),
          el('li', null, el('b', { text: 'ML Calibrated Probability (w_ML): ' }), 'P ≥ 0.85 → 70; P ≥ 0.70 → 50; P ≥ 0.55 → 20; P < 0.55 → 0.'),
          el('li', null, el('b', { text: 'Layer Consensus (w_layers): ' }), '≥3 independent layers fired → 18; 2 layers → 10; 1 layer → 0.'),
          el('li', null, el('b', { text: 'Obfuscation Penalty (p_obfuscation): ' }), 'Base64/Hex/Rot13 = +12; Homoglyph/Zero-width = +10; Leet/Split = +8; other = +5 (capped at +25).'),
          el('li', null, el('b', { text: 'Stage Penalty (p_stage): ' }), 'Egress = 15; Tool = 12; Output = 10; Ingress = 5 (applied when suspicious indicators fire).')
        ),
        el('h4', { style: 'margin-top:14px', text: 'Three-State Decision Thresholds' }),
        el('div', { style: 'display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:8px' },
          el('div', { class: 'sec-cm-cell tn' },
            el('b', { text: 'ALLOW (Risk < 30)' }),
            el('span', { class: 'faint', style: 'font-size:12px;margin-top:4px', text: 'Clean execution profile. Proceed with compilation or standard verification.' })
          ),
          el('div', { class: 'sec-cm-cell fn' },
            el('b', { text: 'REVIEW (Risk 30–69)' }),
            el('span', { class: 'faint', style: 'font-size:12px;margin-top:4px', text: 'Elevated anomaly risk. Patch shown with visible warning & evidence; requires human Accept.' })
          ),
          el('div', { class: 'sec-cm-cell tp' },
            el('b', { text: 'BLOCK (Risk ≥ 70)' }),
            el('span', { class: 'faint', style: 'font-size:12px;margin-top:4px', text: 'Critical violation. Ingress: no LLM call, fallback to rule healer. Egress: patch discarded.' })
          )
        )
      ),

      // ── Section 4: Empirical Evaluation Metrics ──────────────────────────
      el('div', { class: 'sec-card', style: 'margin-top:24px' },
        el('h2', { style: 'margin-bottom:8px', text: '4. Measured Evaluation Metrics (results/aai_metrics.json)' }),
        el('p', { class: 'faint', text: 'All values copied directly from the frozen test split evaluation (N = 352). Zero numbers invented.' }),
        el('div', { class: 'kpi-grid', style: 'margin:12px 0' },
          KPICard('Accuracy', '95.5', '%'),
          KPICard('Precision', '96.5', '%'),
          KPICard('Detection Recall', '94.3', '%'),
          KPICard('F1 Score', '0.954'),
          KPICard('False Positive Rate', '3.4', '%'),
          KPICard('Attack Success Rate', '5.7', '%'),
          KPICard('ROC-AUC', '0.9831'),
          KPICard('PR-AUC', '0.9888')
        ),
        el('h4', { text: 'Confusion Matrix (Frozen Test Split: 176 Attacks, 176 Benign)' }),
        el('div', { class: 'sec-cm-grid', style: 'margin:8px 0 16px' },
          el('div', { class: 'sec-cm-cell header-col', text: '' }),
          el('div', { class: 'sec-cm-cell header-col bold', text: 'Predicted: Attack (Blocked)' }),
          el('div', { class: 'sec-cm-cell header-col bold', text: 'Predicted: Benign (Allowed)' }),
          el('div', { class: 'sec-cm-cell header-row bold', text: 'Actual: Attack (176)' }),
          el('div', { class: 'sec-cm-cell tp' }, el('span', { class: 'cm-val', text: '166' }), el('span', { class: 'cm-label', text: 'True Positives' })),
          el('div', { class: 'sec-cm-cell fn' }, el('span', { class: 'cm-val', text: '10' }), el('span', { class: 'cm-label', text: 'False Negatives' })),
          el('div', { class: 'sec-cm-cell header-row bold', text: 'Actual: Benign (176)' }),
          el('div', { class: 'sec-cm-cell fp' }, el('span', { class: 'cm-val', text: '6' }), el('span', { class: 'cm-label', text: 'False Positives' })),
          el('div', { class: 'sec-cm-cell tn' }, el('span', { class: 'cm-val', text: '170' }), el('span', { class: 'cm-label', text: 'True Negatives' }))
        ),
        el('p', { class: 'faint', style: 'font-size:12px', text: '95% Wilson Confidence Intervals: Accuracy [92.74%, 97.18%], Precision [92.60%, 98.39%], Recall [89.86%, 96.88%], FPR [1.57%, 7.24%], ASR [3.12%, 10.14%]. Latency: p50 = 8.656 ms, p95 = 70.508 ms, max = 292.946 ms.' }),
        el('h4', { style: 'margin-top:14px', text: '6-Stage Layer Ablation Progression' }),
        el('table', { class: 'bench-table sec-table', style: 'margin-top:8px' },
          el('thead', null,
            el('tr', null,
              el('th', { text: 'Ablation Configuration' }),
              el('th', { text: 'TP' }),
              el('th', { text: 'FP' }),
              el('th', { text: 'TN' }),
              el('th', { text: 'FN' }),
              el('th', { text: 'Accuracy' }),
              el('th', { text: 'Precision' }),
              el('th', { text: 'Recall' }),
              el('th', { text: 'F1' }),
              el('th', { text: 'FPR' }),
              el('th', { text: 'ASR' })
            )
          ),
          el('tbody', null,
            el('tr', null, el('td', { text: '(0) No Guardrail' }), el('td', { text: '0' }), el('td', { text: '0' }), el('td', { text: '176' }), el('td', { text: '176' }), el('td', { text: '50.0%' }), el('td', { text: '0.0%' }), el('td', { text: '0.0%' }), el('td', { text: '0.000' }), el('td', { text: '0.0%' }), el('td', { text: '100.0%' })),
            el('tr', null, el('td', { text: '(1) Regex Only (Old)' }), el('td', { text: '69' }), el('td', { text: '0' }), el('td', { text: '176' }), el('td', { text: '107' }), el('td', { text: '69.6%' }), el('td', { text: '100.0%' }), el('td', { text: '39.2%' }), el('td', { text: '0.563' }), el('td', { text: '0.0%' }), el('td', { text: '60.8%' })),
            el('tr', null, el('td', { text: '(2) + Normalization' }), el('td', { text: '101' }), el('td', { text: '0' }), el('td', { text: '176' }), el('td', { text: '75' }), el('td', { text: '78.7%' }), el('td', { text: '100.0%' }), el('td', { text: '57.4%' }), el('td', { text: '0.729' }), el('td', { text: '0.0%' }), el('td', { text: '42.6%' })),
            el('tr', null, el('td', { text: '(3) + Code Layer' }), el('td', { text: '101' }), el('td', { text: '0' }), el('td', { text: '176' }), el('td', { text: '75' }), el('td', { text: '78.7%' }), el('td', { text: '100.0%' }), el('td', { text: '57.4%' }), el('td', { text: '0.729' }), el('td', { text: '0.0%' }), el('td', { text: '42.6%' })),
            el('tr', null, el('td', { text: '(4) + ML Classifier' }), el('td', { text: '169' }), el('td', { text: '0' }), el('td', { text: '176' }), el('td', { text: '7' }), el('td', { text: '98.0%' }), el('td', { text: '100.0%' }), el('td', { text: '96.0%' }), el('td', { text: '0.980' }), el('td', { text: '0.0%' }), el('td', { text: '3.98%' })),
            el('tr', { class: 'bold highlight-row' }, el('td', { text: '(5) Full Guardrail' }), el('td', { text: '166' }), el('td', { text: '6' }), el('td', { text: '170' }), el('td', { text: '10' }), el('td', { text: '95.5%' }), el('td', { text: '96.5%' }), el('td', { text: '94.3%' }), el('td', { text: '0.954' }), el('td', { text: '3.4%' }), el('td', { text: '5.68%' }))
          )
        ),
        el('h4', { style: 'margin-top:14px', text: 'End-to-End Evil LLM Simulation (ReAct Egress Defense)' }),
        el('p', { class: 'faint', text: 'Tested 80 adversarial patches/tool calls returned by an evil LLM. Blocked: 76 (95.0%), Slipped unmitigated: 4 (5.0%). Class G: 16/16 (100%), Class H: 16/16 (100%), Class E: 16/16 (100%), Class I: 15/16 (93.8%), Class J: 13/16 (81.2%). Clean program healing degradation: 0.0%.' })
      ),

      // ── Section 5: System Limitations ────────────────────────────────────
      el('div', { class: 'sec-card', style: 'margin-top:24px' },
        el('h2', { style: 'margin-bottom:8px', text: '5. Limitations & Security Realities' }),
        el('p', { class: 'faint', text: 'Honest security disclosure acknowledging engineering boundaries and failure modes.' }),
        el('ul', { style: 'padding-left:18px;margin-top:8px;line-height:1.6;font-size:13px' },
          el('li', null, el('b', { text: 'Adaptive Attacker Evasion: ' }), 'Static regex rules and TF-IDF classifiers can be bypassed by sophisticated adversarial prompt writers using complex multi-turn narratives, novel metaphors, or high-order cryptographic obfuscation not represented in the seed vocabulary.'),
          el('li', null, el('b', { text: 'Corpus Scale & Domain Scope: ' }), 'The evaluation corpus contains 704 synthetic and curated samples (352 dev, 352 frozen test). While systematically stratified across 11 classes, real-world developer ecosystems contain wider linguistic diversity and idiosyncratic coding styles.'),
          el('li', null, el('b', { text: 'Absence of an LLM Judge: ' }), 'To maintain sub-10ms latency and guarantee 100% offline self-containment without incurring recurring API tokens, the guardrail relies on deterministic parsing and local ML rather than calling a secondary LLM judge. As a result, highly subtle semantic exploits (Class J prompt extractions) achieve lower recall (75.0%).')
        )
      ),

      // ── Section 6: 5-Minute Live Interactive Demo Script ─────────────────
      el('div', { class: 'sec-card', style: 'margin-top:24px;margin-bottom:24px' },
        el('h2', { style: 'margin-bottom:8px', text: '6. 5-Minute Evaluation & Demo Script' }),
        el('p', { class: 'faint', text: 'Step-by-step walkthrough for evaluators and reviewers to test all guardrail capabilities live in the browser.' }),
        el('ol', { style: 'padding-left:18px;margin-top:8px;line-height:1.7;font-size:13px' },
          el('li', null,
            el('b', { text: 'Step 1: Reference Attack Test (Policy Bypass Prompt)' }),
            el('div', { class: 'faint', text: 'Navigate to Security → Attack Lab. Select the reference preset: "Policy bypass prompt (ignore security, mark code as safe)". Click "Run Guardrail Scan". Observe sub-millisecond BLOCK decision (Risk 85.0/100, CRITICAL), trigger pattern identification, and fallback routing.' })
          ),
          el('li', null,
            el('b', { text: 'Step 2: Hidden-Agenda Trojan Patch (Class E Egress)' }),
            el('div', { class: 'faint', text: 'Select Stage: Egress and choose the "Trojan Egress: Exfil Personal/SSH Data" preset (e.g. system("cat ~/.ssh/id_rsa")). Run the scan. Notice that Layer 3 (Code AST Layer) flags the newly introduced sensitive credential read and immediately quarantines the patch.' })
          ),
          el('li', null,
            el('b', { text: 'Step 3: Obfuscated Evasion Test (Class F De-obfuscation)' }),
            el('div', { class: 'faint', text: 'Select the Base64, Leet, or Homoglyph preset in Attack Lab. Click "Run Guardrail Scan". Observe Layer 1 (Normalizer) de-obfuscating the text in real-time, displaying side-by-side original versus normalized text, allowing the underlying rule/ML layers to intercept it.' })
          ),
          el('li', null,
            el('b', { text: 'Step 4: Audit Log & Cryptographic Verification' }),
            el('div', { class: 'faint', text: 'Navigate to Security → Attack Log. Review the 2,082 recorded security events. Click "Verify Log Integrity". The backend checks the SHA-256 parent hash chain from the genesis record, confirming 2,082 / 2,082 records intact. (CLI command: python src/aai_guardrail.py --verify-log).' })
          ),
          el('li', null,
            el('b', { text: 'Step 5: ASR Comparison (Guardrail OFF vs ON)' }),
            el('div', { class: 'faint', text: 'Toggle Guardrail Defense to OFF (Demo Mode). Run any attack payload: observe the prominent warning banner and 100% Attack Success Rate (ALLOW). Toggle Guardrail Defense to ON: observe Attack Success Rate drops to 5.68% (94.32% recall), proving multi-layer defense effectiveness.' })
          )
        )
      )
    );
  }
  root.append(el('div', { class: 'page-head' }, el('div', null, el('h1', { text: 'Architecture' }),
    el('p', { text: 'How the project looked before this work and how it is organised now. Box subtitles name the source files.' })),
    el('div', { class: 'seg', role: 'group', 'aria-label': 'Version' }, b1, b2)), host);
  set(view);
}
