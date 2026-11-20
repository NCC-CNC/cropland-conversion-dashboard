// Small inline icon set (24px grid, stroke based). Decorative: always aria-hidden.
const wrap = (d: string) =>
  `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${d}</svg>`;

export const ICONS = {
  polygon: wrap('<path d="M12 3.5 20 9l-3 10.5H7L4 9z"/>'),
  rectangle: wrap('<rect x="4" y="6" width="16" height="12" rx="1.5"/>'),
  edit: wrap('<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z"/><path d="m14.5 7.5 3 3"/>'),
  view: wrap('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
  clear: wrap('<path d="M5 7h14M10 11v6M14 11v6M6.5 7l1 12h9l1-12M9.5 7V4.5h5V7"/>'),
  download: wrap('<path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/>'),
  share: wrap('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>'),
  info: wrap('<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>'),
  check: wrap('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
};

export const LOGO = `<svg viewBox="0 0 32 32" width="32" height="32" aria-hidden="true" focusable="false"><rect width="32" height="32" rx="8" fill="var(--accent)"/><g fill="#fff"><rect x="6" y="6" width="9" height="9" rx="1.5" opacity=".45"/><rect x="17" y="6" width="9" height="9" rx="1.5" opacity=".45"/><rect x="6" y="17" width="9" height="9" rx="1.5" opacity=".45"/><rect x="17" y="17" width="9" height="9" rx="1.5"/></g></svg>`;
