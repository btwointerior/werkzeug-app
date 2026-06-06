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
    'inline-flex items-center justify-center min-h-[48px] px-4 rounded-xl ' +
    'font-semibold transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed';
  const variants = {
    primary:   'bg-accent text-accent-ink hover:brightness-95',
    secondary: 'bg-surface-2 text-txt-2 hover:brightness-110',
    success:   'bg-ok text-accent-ink hover:brightness-95',
    warning:   'bg-maint text-accent-ink hover:brightness-95',
    danger:    'bg-broken text-accent-ink hover:brightness-95',
    ghost:     'bg-transparent text-txt-2 hover:bg-surface-2',
  };
  return `${base} ${variants[variant] || variants.primary}`;
}

// Platzhalter-Logo. Späterer Austausch gegen echtes B2-Interior-Logo NUR hier.
export function logoMarkup(sizeCls = 'h-8 w-8 text-sm') {
  return `<span class="inline-flex items-center justify-center ${sizeCls} rounded-lg ` +
         `bg-accent text-accent-ink font-extrabold tracking-tight">B2</span>`;
}

const TOAST_VARIANTS = {
  success: 'bg-ok text-accent-ink',
  error: 'bg-broken text-accent-ink',
  info: 'bg-surface-2 text-txt',
};

export function toast(text, typ = 'info', dauerMs = 3500) {
  const root = document.getElementById('toasts');
  if (!root) return;
  const el = document.createElement('div');
  el.className =
    `${TOAST_VARIANTS[typ] || TOAST_VARIANTS.info} rounded-xl shadow-lg ` +
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
      'bg-surface border border-border rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col';

    const header = document.createElement('div');
    header.className = 'px-5 py-4 border-b border-border';
    header.innerHTML = `<h2 class="text-lg font-semibold text-txt">${escapeHtml(titel)}</h2>`;

    const content = document.createElement('div');
    content.className = 'px-5 py-4 overflow-y-auto';
    if (typeof body === 'string') content.innerHTML = body;
    else content.appendChild(body);

    const footer = document.createElement('div');
    footer.className =
      'px-5 py-4 border-t border-border flex flex-row-reverse gap-2 flex-shrink-0';

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
    body: `<p class="text-txt-2">${escapeHtml(text)}</p>`,
    buttons: [
      { label: okLabel, variant: dangerous ? 'danger' : 'primary', value: true },
      { label: 'Abbrechen', variant: 'secondary', value: false },
    ],
  });
}

export function statusBadge(status) {
  const map = {
    verfuegbar:  { text: 'Verfügbar',   cls: 'text-ok' },
    ausgeliehen: { text: 'Ausgeliehen', cls: 'text-lent' },
    defekt:      { text: 'Defekt',      cls: 'text-broken' },
    wartung:     { text: 'In Wartung',  cls: 'text-maint' },
  };
  const m = map[status] || { text: status, cls: 'text-muted' };
  return `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold bg-surface-2 ${m.cls}">` +
         `<span class="text-[8px] leading-none">●</span>${m.text}</span>`;
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
    '<div class="animate-spin h-10 w-10 border-4 border-accent border-t-transparent rounded-full"></div>' +
    '</div>'
  );
}

export function leerZustand(text) {
  return `<div class="text-center py-12 text-muted">${escapeHtml(text)}</div>`;
}
