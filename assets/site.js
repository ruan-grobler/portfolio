// Progressive enhancement only. Without JavaScript every card shows and the
// theme follows the system setting.
(() => {
  'use strict';

  const root = document.documentElement;

  // Theme toggle. The stored choice is applied in <head> before first paint.
  const toggle = document.querySelector('.theme-toggle');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  const isDark = () => (root.dataset.theme ? root.dataset.theme === 'dark' : prefersDark.matches);
  const syncToggle = () => {
    if (toggle) toggle.setAttribute('aria-pressed', String(isDark()));
  };
  if (toggle) {
    toggle.hidden = false;
    syncToggle();
    toggle.addEventListener('click', () => {
      const next = isDark() ? 'light' : 'dark';
      root.dataset.theme = next;
      try {
        localStorage.setItem('theme', next);
      } catch (e) {
        // Storage can be blocked. The toggle still works for this visit.
      }
      syncToggle();
    });
    prefersDark.addEventListener('change', syncToggle);
  }

  // Filter chips. ?filter=n8n opens the page already filtered.
  const bar = document.querySelector('.filters');
  const chips = bar ? Array.from(bar.querySelectorAll('[data-filter]')) : [];
  const cards = Array.from(document.querySelectorAll('.card[data-tags]'));
  const status = document.querySelector('.filter-status');
  if (!bar || chips.length === 0) return;

  const valid = new Set(chips.map((c) => c.dataset.filter));
  const apply = (id, fromUser, announce) => {
    const active = valid.has(id) ? id : 'all';
    let shown = 0;
    chips.forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.filter === active)));
    cards.forEach((card) => {
      const match = active === 'all' || card.dataset.tags.split(' ').includes(active);
      card.hidden = !match;
      if (match) shown += 1;
    });
    if (status && announce) {
      const label = chips.find((c) => c.dataset.filter === active).dataset.label;
      status.textContent = `Showing ${shown} ${shown === 1 ? 'project' : 'projects'}: ${label}.`;
    }
    if (fromUser) {
      const url = new URL(window.location.href);
      if (active === 'all') url.searchParams.delete('filter');
      else url.searchParams.set('filter', active);
      window.history.replaceState(null, '', url);
    }
  };

  bar.hidden = false;
  chips.forEach((c) => c.addEventListener('click', () => apply(c.dataset.filter, true, true)));
  const initial = new URLSearchParams(window.location.search).get('filter');
  apply(initial || 'all', false, Boolean(initial));
})();
