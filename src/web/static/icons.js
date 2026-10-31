'use strict';
/* icons.js — inline SVG icons for Green Compiler Studio.
   Derived from Lucide (ISC licence: Copyright (c) 2022-2024 Lucide Contributors). */

const ICONS = {
  // Navigation
  'code': '<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>',
  'diff': '<rect width="18" height="18" x="3" y="3" rx="2"></rect><line x1="9" y1="9" x2="15" y2="9"></line><line x1="12" y1="6" x2="12" y2="12"></line><line x1="9" y1="17" x2="15" y2="17"></line>',
  'pipeline': '<rect x="2" y="7" width="5" height="10" rx="1"></rect><rect x="10" y="7" width="5" height="10" rx="1"></rect><rect x="18" y="7" width="5" height="10" rx="1"></rect><line x1="7" y1="12" x2="10" y2="12"></line><line x1="15" y1="12" x2="18" y2="12"></line>',
  'tree': '<circle cx="12" cy="5" r="3"></circle><circle cx="6" cy="19" r="3"></circle><circle cx="18" cy="19" r="3"></circle><path d="M12 8v4"></path><path d="M6 16v-1a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v1"></path>',
  'sparkle': '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"></path>',
  'chart': '<path d="M3 3v18h18"></path><path d="M18 17V9"></path><path d="M13 17V5"></path><path d="M8 17v-3"></path>',
  'layers': '<polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline>',

  // Chrome
  'panel': '<rect width="18" height="18" x="3" y="3" rx="2"></rect><path d="M9 3v18"></path>',
  'menu': '<line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="18" x2="20" y2="18"></line>',
  'sun': '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>',
  'moon': '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>',
  'monitor': '<rect width="20" height="14" x="2" y="3" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line>',

  // Actions
  'play': '<polygon points="6 3 20 12 6 21 6 3"></polygon>',
  'check': '<polyline points="20 6 9 17 4 12"></polyline>',
  'x': '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>',
  'undo': '<path d="M3 7v6h6"></path><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"></path>',
  'search': '<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>',
  'plus': '<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>',
  'minus': '<line x1="5" y1="12" x2="19" y2="12"></line>',
  'fit': '<path d="M8 3H5a2 2 0 0 0-2 2v3"></path><path d="M21 8V5a2 2 0 0 0-2-2h-3"></path><path d="M3 16v3a2 2 0 0 0 2 2h3"></path><path d="M16 21h3a2 2 0 0 0 2-2v-3"></path>',
  'download': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line>',
  'file': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>',
  'folder-open': '<path d="M2 9a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H4a2 2 0 0 0-2 2v-3Z"></path><path d="M2 13h20l-2 7a2 2 0 0 1-2 1H4a2 2 0 0 1-2-1l-2-7Z"></path>',
  'save': '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline>',
  'chevron-down': '<polyline points="6 9 12 15 18 9"></polyline>',
  'chevron-right': '<polyline points="9 18 15 12 9 6"></polyline>',
  'alert': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>',
  'info': '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>'
};

/**
 * Returns an inline SVG element for the requested icon.
 * @param {string} name - Icon key from ICONS
 * @param {object} [opts] - Options: size (default 16), cls (extra class)
 * @returns {SVGElement}
 */
function icon(name, { size = 16, cls = '' } = {}) {
  const inner = ICONS[name] || '';
  const node = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  node.setAttribute('viewBox', '0 0 24 24');
  node.setAttribute('width', String(size));
  node.setAttribute('height', String(size));
  node.setAttribute('fill', 'none');
  node.setAttribute('stroke', 'currentColor');
  node.setAttribute('stroke-width', '1.75');
  node.setAttribute('stroke-linecap', 'round');
  node.setAttribute('stroke-linejoin', 'round');
  node.setAttribute('aria-hidden', 'true');
  node.setAttribute('focusable', 'false');
  const classList = ['icon', 'icon-' + name];
  if (cls) classList.push(cls);
  node.setAttribute('class', classList.join(' '));
  if (inner) node.innerHTML = inner;
  return node;
}

icon.html = (name, opts) => icon(name, opts).outerHTML;

