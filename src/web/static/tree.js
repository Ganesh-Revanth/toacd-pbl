'use strict';
/* tree.js — TreeView and clang AST normalizer for C++ Studio */

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
      li.hidden = !q || !own && !child;
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

