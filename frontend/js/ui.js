// UI-Bausteine: Toast, Modal, Bestätigen, Formatter, Buttons
//
// Alle Komponenten sind reine Vanilla-DOM-Helfer. Sie nutzen Tailwind-Klassen
// und vermeiden externe Libraries, damit der Build trivial bleibt.

export function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function btnClasses(variant = 'primary') {
  const base =
    'inline-flex items-center justify-center min-h-[48px] px-4 rounded-lg ' +
    'font-medium transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-slate-200 hover:bg-slate-300 text-slate-900',
    success: 'bg-emerald-600 hover:bg-emerald-700 text-white',
    warning: 'bg-orange-500 hover:bg-orange-600 text-white',
    danger: 'bg-rose-600 hover:bg-rose-700 text-white',
    ghost: 'bg-transparent hover:bg-slate-100 text-slate-700',
  };
  return `${base} ${variants[variant] || variants.primary}`;
}

const TOAST_VARIANTS = {
  success: 'bg-emerald-600',
  error: 'bg-rose-600',
  info: 'bg-slate-800',
};

export function toast(text, typ = 'info', dauerMs = 3500) {
  const root = document.getElementById('toasts');
  if (!root) return;
  const el = document.createElement('div');
  el.className =
    `${TOAST_VARIANTS[typ] || TOAST_VARIANTS.info} text-white rounded-lg shadow-lg ` +
    'px-4 py-3 text-base mb-2 max-w-sm pointer-events-auto';
  el.textContent = text;
  root.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity 250ms';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 250);
  }, dauerMs);
}

// modal({ titel, body, buttons }) — body = HTMLElement | string
// buttons: [{ label, variant, value, onClick: () => any|false }]
// onClick liefert `false` → Modal bleibt offen. Sonst schließt es mit `value`.
// Returns Promise mit dem `value` des geklickten Buttons (oder null bei ESC/Backdrop).
export function modal({ titel, body, buttons = [] }) {
  return new Promise((resolve) => {
    const root = document.getElementById('modal-root');
    const backdrop = document.createElement('div');
    backdrop.className =
      'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4';

    const card = document.createElement('div');
    card.className =
      'bg-white rounded-xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col';

    const header = document.createElement('div');
    header.className = 'px-5 py-4 border-b border-slate-200';
    header.innerHTML = `<h2 class="text-lg font-semibold text-slate-900">${escapeHtml(titel)}</h2>`;

    const content = document.createElement('div');
    content.className = 'px-5 py-4 overflow-y-auto';
    if (typeof body === 'string') content.innerHTML = body;
    else content.appendChild(body);

    const footer = document.createElement('div');
    footer.className =
      'px-5 py-4 border-t border-slate-200 flex flex-row-reverse gap-2 flex-shrink-0';

    const close = (value) => {
      backdrop.remove();
      document.removeEventListener('keydown', onKey);
      resolve(value);
    };
    const onKey = (e) => { if (e.key === 'Escape') close(null); };
    document.addEventListener('keydown', onKey);

    buttons.forEach((b) => {
      const btn = document.createElement('button');
      btn.className = btnClasses(b.variant || 'secondary');
      btn.textContent = b.label;
      btn.onclick = async () => {
        const result = b.onClick ? await b.onClick() : true;
        if (result === false) return;
        close(b.value !== undefined ? b.value : result);
      };
      footer.appendChild(btn);
    });

    card.appendChild(header);
    card.appendChild(content);
    if (buttons.length) card.appendChild(footer);
    backdrop.appendChild(card);
    backdrop.onclick = (e) => { if (e.target === backdrop) close(null); };
    root.appendChild(backdrop);

    const firstInput = content.querySelector('input, textarea, select');
    if (firstInput) firstInput.focus();
  });
}

export function confirmDialog(text, opts = {}) {
  const { titel = 'Bestätigen?', okLabel = 'OK', dangerous = false } = opts;
  return modal({
    titel,
    body: `<p class="text-slate-700">${escapeHtml(text)}</p>`,
    buttons: [
      { label: okLabel, variant: dangerous ? 'danger' : 'primary', value: true },
      { label: 'Abbrechen', variant: 'secondary', value: false },
    ],
  });
}

export function statusBadge(status) {
  const map = {
    verfuegbar:  { text: 'Verfügbar',   cls: 'bg-emerald-100 text-emerald-800' },
    ausgeliehen: { text: 'Ausgeliehen', cls: 'bg-blue-100 text-blue-800' },
    defekt:      { text: 'Defekt',      cls: 'bg-rose-100 text-rose-800' },
    wartung:     { text: 'In Wartung',  cls: 'bg-amber-100 text-amber-800' },
  };
  const m = map[status] || { text: status, cls: 'bg-slate-100 text-slate-800' };
  return `<span class="inline-block px-2 py-1 rounded text-xs font-semibold ${m.cls}">${m.text}</span>`;
}

export function formatDatum(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
}

// "gerade eben" / "seit X Stunden" / "seit X Tagen"
export function zeitseit(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 3600_000) return 'gerade eben';
  const stunden = Math.floor(diffMs / 3600_000);
  if (stunden < 24) return `seit ${stunden} Stunde${stunden === 1 ? '' : 'n'}`;
  const tage = Math.floor(stunden / 24);
  return `seit ${tage} Tag${tage === 1 ? '' : 'en'}`;
}

export function spinner() {
  return (
    '<div class="flex justify-center py-12">' +
    '<div class="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full"></div>' +
    '</div>'
  );
}

export function leerZustand(text) {
  return `<div class="text-center py-12 text-slate-500">${escapeHtml(text)}</div>`;
}
