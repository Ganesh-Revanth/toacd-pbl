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
      el('span', { class: st.fixed ? 'ok' : 'no', text: st.fixed ? '✓' : '✕' }),
      el('span', null, el('b', { text: 'Line ' + st.line + ': ' }), st.message || '', st.fixed ? ' — patched' : ' — ' + (st.note || 'not fixed')));
  }));
}

/* ── C++ Workspace ───────────────────────────────────────────────────── */
function pageWorkspace(root) {
  const s = state.cpp;
  const aiOK = state.status.ai_ready;
  let lastDecisionNote = null;

  const ed = Editor({
    value: s.code, label: 'C++ source code',
    onChange: (v) => { s.code = v; if (s.result && diagHost) { staleNote.hidden = v === s.lastCheckedCode; } },
    onRun: () => check(),
  });
  const staleNote = el('span', { class: 'chip warn', hidden: true }, el('i'), 'Edited since last check');
  const btnCheck = el('button', { class: 'btn primary', onClick: () => check() }, 'Check');
  const btnRules = el('button', { class: 'btn', onClick: () => heal('rules') }, 'Suggest fix (rules)');
  const btnAI = el('button', { class: 'btn', disabled: !aiOK, title: aiOK ? '' : 'Needs a Gemini API key', onClick: () => heal('ai') }, 'Suggest fix (AI)');
  const proposalHost = el('div');
  const diagHost = el('div');

  function markEditor(r) {
    const m = {};
    for (const d of (r && r.diagnostics) || []) {
      if (!d.line) continue;
      if (d.type === 'error') m[d.line] = 'err'; else if (!m[d.line]) m[d.line] = 'warn';
    }
    ed.mark(m);
  }

  function renderProposal() {
    const p = s.pending;
    proposalHost.replaceChildren();
    if (lastDecisionNote) proposalHost.append(lastDecisionNote);
    if (!p) return;
    const st = diffStats(p.diff);
    const warn = state.status.llm_mock && p.mode === 'ai'
      ? notice('warn', el('b', { text: 'Mock mode: ' }), 'this result is a canned response, not a real fix for your code.') : null;
    const msgHost = el('div');
    const accept = el('button', { class: 'btn primary', onClick: () => {
      const res = decide(p, 'accept');
      if (!res.ok) { msgHost.replaceChildren(notice('bad', res.msg)); return; }
      ed.set(s.code); ed.mark({}); lastDecisionNote = notice('ok', el('b', { text: 'Change accepted. ' }), 'Editor updated. You can undo it from Changes.');
      renderProposal(); announce('Change accepted'); check();
    } }, 'Accept change');
    const reject = el('button', { class: 'btn', onClick: () => {
      decide(p, 'reject'); lastDecisionNote = notice('', 'Change rejected. Your code is unchanged.'); renderProposal(); announce('Change rejected');
    } }, 'Reject');
    proposalHost.append(el('section', { class: 'panel proposal', 'aria-label': 'Proposed change' },
      el('div', { class: 'panel-head' },
        el('h2', { text: 'Proposed change' }),
        el('div', { class: 'actions' },
          el('span', { class: 'chip plain' }, p.kind),
          el('span', { class: 'chip ' + (p.compiles ? 'ok' : 'warn') }, el('i'), p.compiles ? 'Compiles after change' : 'Still has errors after change'))),
      el('div', { class: 'panel-body' },
        warn, warn && el('div', { style: 'height:12px' }),
        StepsList(p.steps),
        p.summary && el('p', { class: 'muted', text: p.summary, style: 'margin-bottom:12px' }),
        el('p', { class: 'faint', style: 'margin-bottom:8px', text: '+' + st.add + ' added, −' + st.del + ' removed. Nothing changes until you accept.' }),
        DiffView(p.diff),
        el('div', { class: 'decision' }, accept, reject),
        msgHost)));
  }

  function renderDiag() {
    const r = s.result;
    diagHost.replaceChildren();
    if (!r) {
      diagHost.append(el('div', { class: 'panel' }, el('div', { class: 'empty' },
        el('b', { text: 'Nothing checked yet' }),
        'Load an example or paste C++ code, then press Check (Ctrl+Enter). Errors are explained in plain language and can be fixed with a reviewable diff.')));
      return;
    }
    const head = el('div', { class: 'panel-head' },
      el('h2', { text: r.ok ? (r.warning_count ? 'Compiles, with warnings' : 'Compiles cleanly') : plural(r.error_count, 'error') + (r.warning_count ? ', ' + plural(r.warning_count, 'warning') : '') }),
      el('span', { class: 'faint', text: r.elapsed_s + 's' }));
    const list = el('div');
    if (!r.diagnostics.length) list.append(el('div', { class: 'empty' }, el('b', { text: 'No diagnostics' }), 'g++ reported nothing for this file.'));
    r.diagnostics.forEach(d => list.append(Diagnostic(d, ed)));
    const secs = el('div');
    if (r.security.length) {
      secs.append(el('div', { class: 'panel-head' }, el('h2', { text: 'Security findings' }), el('span', { class: 'faint', text: String(r.security.length) })));
      r.security.forEach(f => secs.append(SecurityItem(f, ed)));
    }
    diagHost.append(el('div', { class: 'panel' }, head, list, secs));
  }

  async function check() {
    const code = ed.get();
    if (!code.trim()) { diagHost.replaceChildren(notice('warn', 'Write or load some code first.')); return; }
    await busy([btnCheck, btnRules, btnAI], async () => {
      try {
        const r = await call('/api/cpp/analyze', { code });
        s.result = r; s.lastCheckedCode = code; staleNote.hidden = true;
        markEditor(r); renderDiag();
        announce(r.ok ? 'Compiles' : plural(r.error_count, 'error') + ' found');
      } catch (e) { diagHost.replaceChildren(notice('bad', e.message)); }
    });
  }

  async function heal(mode) {
    const code = ed.get();
    if (!code.trim()) { diagHost.replaceChildren(notice('warn', 'Write or load some code first.')); return; }
    lastDecisionNote = null;
    await busy([mode === 'ai' ? btnAI : btnRules, btnCheck, mode === 'ai' ? btnRules : btnAI], async () => {
      try {
        const r = await call('/api/cpp/heal', { mode, code });
        if (!r.changed) {
          s.pending = null;
          proposalHost.replaceChildren(el('section', { class: 'panel' },
            el('div', { class: 'panel-head' }, el('h2', { text: 'No change proposed' })),
            el('div', { class: 'panel-body' },
              el('p', { class: 'muted', text: r.compiles ? 'The code already compiles, so there is nothing to fix.' : 'No automatic fix was found for the remaining problems. Read the explanations below and edit the code, or try the AI fix.' }),
              StepsList(r.steps))));
          if (!r.compiles) { s.result = await call('/api/cpp/analyze', { code }); s.lastCheckedCode = code; markEditor(s.result); renderDiag(); }
          announce('No change proposed');
          return;
        }
        createProposal(r); renderProposal(); announce('A change is proposed. Review the diff.');
      } catch (e) { proposalHost.replaceChildren(notice('bad', e.message)); }
    });
  }

  root.append(
    el('div', { class: 'page-head' },
      el('div', null, el('h1', { text: 'C++ workspace' }),
        el('p', { text: 'Check a C++ file with g++, read each problem explained, and review any suggested fix as a diff before it touches your code.' })),
      el('div', { class: 'actions' }, SamplePicker('cpp', (smp) => {
        ed.set(smp.code); s.result = null; s.pending = null; ed.mark({}); lastDecisionNote = null; renderProposal(); renderDiag();
      }), btnCheck, btnRules, btnAI)),
    !aiOK && el('p', { class: 'faint', style: 'margin:-12px 0 16px', text: 'AI fixes are off because no Gemini key is configured. Rule-based fixes work without one.' }),
    el('div', { class: 'split' },
      el('div', { class: 'panel' },
        el('div', { class: 'panel-head' }, el('h2', { text: 'main.cpp' }), staleNote),
        ed.root,
        el('div', { class: 'panel-foot' }, el('span', { text: 'Ctrl+Enter to check' }), el('span', { text: 'Esc then Tab leaves the editor' }))),
      el('div', { class: 'stack' }, proposalHost, diagHost)));
  renderProposal(); renderDiag();
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
