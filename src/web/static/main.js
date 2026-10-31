'use strict';
/* main.js — navigation, router, status chips, theme, boot. */

const ROUTES = [
  { group: 'Work', items: [
    { id: 'workspace', label: 'C++ Studio', title: 'C++ Studio', render: pageWorkspace },
    { id: 'changes', label: 'Changes', title: 'Changes', render: pageChanges, badge: true },
  ] },
  { group: 'Evidence', items: [
    { id: 'benchmark', label: 'Benchmark', title: 'Benchmark', render: pageBenchmark },
    { id: 'architecture', label: 'Architecture', title: 'Architecture', render: pageArchitecture },
  ] },
];
const FLAT = ROUTES.flatMap(g => g.items);

function buildRail() {
  const rail = $('#rail');
  rail.replaceChildren(
    el('div', { class: 'brand' }, el('b', { text: 'Green Compiler Studio' }), el('span', { text: 'self-healing · AI-assisted' })),
    ROUTES.map(g => el('div', { class: 'nav-group' }, el('h2', { text: g.group }),
      g.items.map(it => el('a', { class: 'nav-link', href: '#/' + it.id, 'data-route': it.id },
        el('span', { text: it.label }),
        it.badge ? el('span', { class: 'count', id: 'nav-count', hidden: true, 'aria-label': 'awaiting decision' }) : null)))),
    el('div', { class: 'rail-foot' }, themeButton()));
  updateNavCount();
}

function themeButton() {
  const modes = ['auto', 'light', 'dark'];
  let mode = store.get('theme', 'auto');
  const btn = el('button', { class: 'btn quiet', style: 'justify-content:flex-start' });
  const apply = () => {
    if (mode === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', mode);
    btn.textContent = 'Theme: ' + mode;
  };
  btn.addEventListener('click', () => { mode = modes[(modes.indexOf(mode) + 1) % modes.length]; store.set('theme', mode); apply(); });
  apply();
  return btn;
}

function buildStatus() {
  const st = state.status;
  const chip = (cls, text) => el('span', { class: 'chip ' + cls }, el('i'), text);
  $('#topbar').replaceChildren(
    chip(st.gxx ? 'ok' : 'bad', st.gxx ? 'g++ found' : 'g++ missing'),
    chip(st.clang ? 'ok' : 'warn', st.clang ? 'clang++ found' : 'clang++ missing (C++ tree off)'),
    chip(st.llm_mock ? 'warn' : st.ai_ready ? 'ok' : 'warn', st.llm_mock ? 'AI: mock mode' : st.ai_ready ? 'AI: Gemini ready' : 'AI: no API key'));
  const banner = $('#banner');
  banner.replaceChildren();
  if (st.llm_mock) banner.append(notice('warn', el('b', { text: 'Mock mode is on. ' }), 'AI answers are canned examples, not real model output. Unset LLM_MOCK for real results.'));
  if (!st.gxx) banner.append(notice('bad', el('b', { text: 'g++ was not found. ' }), 'Install a C++ toolchain and restart; C++ checking and healing need it.'));
}

function route() {
  const id = (location.hash.replace(/^#\//, '') || 'workspace');
  const r = FLAT.find(x => x.id === id) || FLAT[0];
  document.querySelectorAll('.nav-link').forEach(a => {
    if (a.dataset.route === r.id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  const main = $('#main');
  main.replaceChildren();
  document.title = r.title + ' · Green Compiler Studio';
  try { r.render(main); }
  catch (e) { main.replaceChildren(notice('bad', el('b', { text: 'This page failed to load. ' }), e.message)); console.error(e); }
  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

async function boot() {
  buildRail();
  try {
    const [status, samples] = await Promise.all([call('/api/status'), call('/api/samples')]);
    state.status = status; state.samples = samples.samples;
  } catch (e) {
    $('#main').replaceChildren(notice('bad', el('b', { text: 'Could not start. ' }), e.message));
    return;
  }
  const firstCpp = state.samples.find(s => s.language === 'cpp');
  const draft = store.get('cppDraft', null);
  if (draft && typeof draft.code === 'string' && draft.code.trim()) { state.cpp.code = draft.code; state.cpp.name = draft.name || 'main.cpp'; }
  else if (firstCpp) { state.cpp.code = firstCpp.code; state.cpp.name = 'main.cpp'; }
  buildStatus();
  window.addEventListener('hashchange', route);
  route();
}
boot();
