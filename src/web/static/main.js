'use strict';
/* main.js — navigation, router, status chips, theme, boot. */

const ROUTES = [
  { group: 'Work', items: [
    { id: 'workspace', label: 'Code Studio', title: 'Code Studio', icon: 'code', render: pageWorkspace },
    { id: 'ast', label: 'Syntax tree', title: 'Syntax tree', icon: 'tree', render: pageAst },
    { id: 'changes', label: 'Changes', title: 'Changes', icon: 'diff', badge: true, render: pageChanges },
  ] },
  { group: 'Evidence', items: [
    { id: 'benchmark', label: 'Benchmark', title: 'Benchmark', icon: 'chart', render: pageBenchmark },
    { id: 'architecture', label: 'Architecture', title: 'Architecture', icon: 'layers', render: pageArchitecture },
  ] },
];
const FLAT = ROUTES.flatMap(g => g.items);

/* ── Sidebar & Navigation ──────────────────────────────────────────────── */
function setRailState(collapsed) {
  document.documentElement.setAttribute('data-rail', collapsed ? 'collapsed' : 'expanded');
  try { localStorage.setItem('studio:rail', collapsed ? 'collapsed' : 'expanded'); } catch (e) {}
  const btn = $('.rail-toggle');
  if (btn) {
    btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    const label = collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)';
    btn.setAttribute('aria-label', label);
    btn.title = label;
  }
}

function toggleRail() {
  const isCollapsed = document.documentElement.getAttribute('data-rail') === 'collapsed';
  setRailState(!isCollapsed);
}

/* ── Mobile Drawer ─────────────────────────────────────────────────────── */
function openMobileDrawer() {
  const rail = $('#rail');
  const backdrop = $('#backdrop');
  const trigger = $('.menu-trigger');
  if (!rail || !backdrop) return;
  rail.classList.add('open');
  backdrop.classList.add('on');
  document.body.style.overflow = 'hidden';
  if (trigger) trigger.setAttribute('aria-expanded', 'true');
  try {
    const main = $('#main');
    const topbar = $('#topbar');
    if (main) main.inert = true;
    if (topbar) topbar.inert = true;
    rail.inert = false;
  } catch (e) {}
  const first = rail.querySelector('a, button');
  if (first) first.focus();
}

function closeMobileDrawer() {
  const rail = $('#rail');
  const backdrop = $('#backdrop');
  const trigger = $('.menu-trigger');
  if (!rail || !backdrop) return;
  if (!rail.classList.contains('open')) return;
  rail.classList.remove('open');
  backdrop.classList.remove('on');
  document.body.style.overflow = '';
  if (trigger) {
    trigger.setAttribute('aria-expanded', 'false');
    trigger.focus();
  }
  try {
    const main = $('#main');
    const topbar = $('#topbar');
    if (main) main.inert = false;
    if (topbar) topbar.inert = false;
    if (window.innerWidth <= 900) {
      rail.inert = true;
    }
  } catch (e) {}
}

function toggleMobileDrawer() {
  const rail = $('#rail');
  if (rail && rail.classList.contains('open')) closeMobileDrawer();
  else openMobileDrawer();
}

/* ── Collapsed Tooltip ─────────────────────────────────────────────────── */
let tipTimer = null;
function attachTooltip(target, getText) {
  const show = () => {
    const isCollapsed = document.documentElement.getAttribute('data-rail') === 'collapsed';
    if (!isCollapsed || window.innerWidth <= 900) return;
    const text = typeof getText === 'function' ? getText() : getText;
    if (!text) return;
    tipTimer = setTimeout(() => {
      const tip = $('#tip');
      if (!tip) return;
      tip.textContent = text;
      const rect = target.getBoundingClientRect();
      tip.style.left = (rect.right + 10) + 'px';
      tip.style.top = (rect.top + rect.height / 2) + 'px';
      tip.hidden = false;
      tip.classList.add('on');
    }, 150);
  };
  const hide = () => {
    if (tipTimer) { clearTimeout(tipTimer); tipTimer = null; }
    const tip = $('#tip');
    if (tip) {
      tip.classList.remove('on');
      tip.hidden = true;
    }
  };
  target.addEventListener('mouseenter', show);
  target.addEventListener('mouseleave', hide);
  target.addEventListener('focus', show);
  target.addEventListener('blur', hide);
}

function hideTip() {
  if (tipTimer) { clearTimeout(tipTimer); tipTimer = null; }
  const tip = $('#tip');
  if (tip) { tip.classList.remove('on'); tip.hidden = true; }
}

function buildRail() {
  const rail = $('#rail');
  const isCollapsed = document.documentElement.getAttribute('data-rail') === 'collapsed';

  const toggleBtn = el('button', {
    class: 'rail-toggle',
    type: 'button',
    'aria-expanded': isCollapsed ? 'false' : 'true',
    'aria-controls': 'rail',
    'aria-label': isCollapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)',
    title: isCollapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)',
    onclick: toggleRail
  }, icon('panel'));

  const head = el('div', { class: 'rail-head' },
    el('div', { class: 'brand' },
      el('b', { text: 'Green Compiler Studio' }),
      el('span', { text: 'self-healing · AI-assisted' })
    ),
    toggleBtn
  );

  const groups = ROUTES.map(g => el('div', { class: 'nav-group' },
    el('h2', { text: g.group }),
    g.items.map(it => {
      const link = el('a', {
        class: 'nav-link',
        href: '#/' + it.id,
        'data-route': it.id,
        'aria-label': it.label
      },
        el('span', { class: 'nav-icon' }, icon(it.icon)),
        el('span', { class: 'nav-label', text: it.label }),
        it.badge ? el('span', { class: 'count', id: 'nav-count', hidden: true, 'aria-label': 'awaiting decision' }) : null
      );
      attachTooltip(link, () => it.label);
      return link;
    })
  ));

  const footBtn = themeButton();
  attachTooltip(footBtn, () => footBtn.getAttribute('data-tip') || 'Theme');

  rail.replaceChildren(head, groups, el('div', { class: 'rail-foot' }, footBtn));
  if (typeof updateNavCount === 'function') updateNavCount();
}

function themeButton() {
  const modes = ['auto', 'light', 'dark'];
  let mode = store.get('theme', 'auto');
  const iconWrap = el('span', { class: 'nav-icon' });
  const labelSpan = el('span', { class: 'theme-label' });
  const btn = el('button', {
    class: 'theme-btn',
    type: 'button',
    onclick: () => {
      mode = modes[(modes.indexOf(mode) + 1) % modes.length];
      store.set('theme', mode);
      apply();
    }
  }, iconWrap, labelSpan);

  const apply = () => {
    if (mode === 'auto') {
      document.documentElement.removeAttribute('data-theme');
      iconWrap.replaceChildren(icon('monitor'));
      labelSpan.textContent = 'Auto theme';
      btn.setAttribute('aria-label', 'Theme: auto. Switch to light');
      btn.setAttribute('data-tip', 'Theme: auto (follow OS)');
    } else if (mode === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      iconWrap.replaceChildren(icon('sun'));
      labelSpan.textContent = 'Light theme';
      btn.setAttribute('aria-label', 'Theme: light. Switch to dark');
      btn.setAttribute('data-tip', 'Theme: light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      iconWrap.replaceChildren(icon('moon'));
      labelSpan.textContent = 'Dark theme';
      btn.setAttribute('aria-label', 'Theme: dark. Switch to auto');
      btn.setAttribute('data-tip', 'Theme: dark');
    }
  };
  apply();
  return btn;
}

function buildStatus() {
  const st = state.status || {};
  const chip = (cls, text, tip) => el('span', { class: 'chip ' + cls, title: tip || text }, el('i'), text);

  const hamburger = el('button', {
    class: 'menu-trigger',
    type: 'button',
    'aria-label': 'Open navigation drawer',
    'aria-expanded': 'false',
    'aria-controls': 'rail',
    onclick: toggleMobileDrawer
  }, icon('menu'));

  const toolchainNames = { cpp: 'g++', c: 'gcc', python: 'python', java: 'javac' };
  const languagesList = st.languages || [
    { id: 'cpp', name: 'C++', available: !!st.gxx },
    { id: 'c', name: 'C', available: true },
    { id: 'python', name: 'Python', available: true },
    { id: 'java', name: 'Java', available: true },
  ];

  const toolchainChips = languagesList.map(l => {
    const tc = toolchainNames[l.id] || l.name;
    const label = `${tc} ${l.available ? 'found' : 'missing'}`;
    const tip = `${l.name} (${tc}): ${l.available ? 'toolchain available' : 'toolchain missing'}`;
    return chip(l.available ? 'ok' : 'bad', label, tip);
  });

  const aiChip = chip(
    st.llm_mock ? 'warn' : st.ai_ready ? 'ok' : 'warn',
    st.llm_mock ? 'AI: mock mode' : st.ai_ready ? 'AI: Gemini ready' : 'AI: no API key'
  );

  $('#topbar').replaceChildren(
    el('div', { class: 'topbar-left' }, hamburger),
    ...toolchainChips,
    aiChip
  );

  const banner = $('#banner');
  banner.replaceChildren();
  if (st.llm_mock) banner.append(notice('warn', el('b', { text: 'Mock mode is on. ' }), 'AI answers are canned examples, not real model output. Unset LLM_MOCK for real results.'));
  languagesList.filter(l => !l.available).forEach(l => {
    const tc = toolchainNames[l.id] || l.name;
    banner.append(notice('bad', el('b', { text: `${tc} was not found. ` }), `${l.name} checking and healing need it.`));
  });
}

function route() {
  if (window.innerWidth <= 900) closeMobileDrawer();
  hideTip();

  const id = (location.hash.replace(/^#\//, '') || 'workspace');
  const r = FLAT.find(x => x.id === id) || FLAT[0];
  document.querySelectorAll('.nav-link').forEach(a => {
    if (a.dataset.route === r.id) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });

  const main = $('#main');
  main.replaceChildren();
  main.classList.remove('page-enter');
  void main.offsetWidth; // trigger reflow for clean CSS animation
  main.classList.add('page-enter');
  main.addEventListener('animationend', () => {
    main.classList.remove('page-enter');
  }, { once: true });

  document.title = r.title + ' · Green Compiler Studio';
  try {
    r.render(main);
  } catch (e) {
    main.replaceChildren(notice('bad', el('b', { text: 'This page failed to load. ' }), e.message));
    console.error(e);
  }
  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

// Global listeners
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
    e.preventDefault();
    if (window.innerWidth <= 900) toggleMobileDrawer();
    else toggleRail();
  }
  if (e.key === 'Escape') {
    closeMobileDrawer();
    hideTip();
  }
});

$('#backdrop')?.addEventListener('click', closeMobileDrawer);

window.addEventListener('resize', () => {
  const rail = $('#rail');
  if (!rail) return;
  if (window.innerWidth > 900) {
    try {
      rail.inert = false;
      const main = $('#main');
      const topbar = $('#topbar');
      if (main) main.inert = false;
      if (topbar) topbar.inert = false;
    } catch (e) {}
    closeMobileDrawer();
  } else {
    if (!rail.classList.contains('open')) {
      try { rail.inert = true; } catch (e) {}
    }
  }
});

async function boot() {
  buildRail();
  requestAnimationFrame(() => {
    document.documentElement.classList.add('rail-ready');
  });

  try {
    const [status, samples] = await Promise.all([call('/api/status'), call('/api/samples')]);
    state.status = status;
    state.samples = samples.samples;
  } catch (e) {
    $('#main').replaceChildren(notice('bad', el('b', { text: 'Could not start. ' }), e.message));
    return;
  }

  const lang = store.get('studio:lang', 'cpp');
  state.cpp.language = lang;
  try {
    const samplesData = await call('/api/samples?language=' + lang);
    if (samplesData && samplesData.samples) state.samples = samplesData.samples;
  } catch (e) {}

  const defaultFiles = { cpp: 'main.cpp', c: 'main.c', python: 'main.py', java: 'Main.java' };
  const draft = store.get('studio:draft:' + lang, null) || (lang === 'cpp' ? store.get('cppDraft', null) : null);
  if (draft && typeof draft.code === 'string' && draft.code.trim()) {
    state.cpp.code = draft.code;
    state.cpp.filename = draft.filename || draft.name || defaultFiles[lang] || 'main.cpp';
  } else {
    const first = (state.samples || []).find(s => s.language === lang) || (state.samples || [])[0];
    if (first) {
      state.cpp.code = first.code;
      state.cpp.filename = first.filename || defaultFiles[lang] || 'main.cpp';
    } else {
      state.cpp.filename = defaultFiles[lang] || 'main.cpp';
    }
  }

  buildStatus();
  window.addEventListener('hashchange', route);
  route();
}

boot();
