// Bootstrap, App-State, Hash-Router, Top-Bar + Bottom-Nav.

import { api, getToken, clearToken } from './api.js';
import { btnClasses, escapeHtml, logoMarkup, modal, toast } from './ui.js';
import { scanQr } from './scanner.js';
import { holeWerkzeugCode } from './scanner_quelle.js';

import { renderLogin } from './views/login.js';
import { renderMeine } from './views/meine.js';
import { renderGeraete } from './views/geraete.js';
import { renderMaschine } from './views/maschine.js';
import { renderAdminDashboard } from './views/admin_dashboard.js';
import { renderAdminMaschinen } from './views/admin_maschinen.js';
import { renderAdminMaschineForm } from './views/admin_maschine_form.js';
import { renderAdminHistorie } from './views/admin_historie.js';
import { renderAdminBenutzer } from './views/admin_benutzer.js';

export const state = {
  benutzer: null,
  get angemeldet() { return !!this.benutzer; },
  get istAdmin()   { return this.benutzer?.rolle === 'admin'; },
};

// Routen werden in Reihenfolge geprüft; der erste passende `pattern` gewinnt.
// - route(): bewirkt einen Redirect (Hash-Wechsel)
// - view(match): rendert; `match` ist das Regex-Resultat
const ROUTEN = [
  { pattern: /^#?\/?$/, route: () => state.angemeldet
                                  ? (state.istAdmin ? '#/admin' : '#/meine')
                                  : '#/login' },
  { pattern: /^#\/login$/, public: true, view: renderLogin },
  { pattern: /^#\/meine$/, view: renderMeine },
  { pattern: /^#\/geraete$/, view: renderGeraete },
  { pattern: /^#\/m\/(.+)$/, view: (m) => renderMaschine(decodeURIComponent(m[1])) },
  { pattern: /^#\/admin$/, admin: true, view: renderAdminDashboard },
  { pattern: /^#\/admin\/maschinen$/, admin: true, view: renderAdminMaschinen },
  { pattern: /^#\/admin\/maschinen\/neu$/, admin: true, view: () => renderAdminMaschineForm(null) },
  { pattern: /^#\/admin\/maschinen\/(\d+)\/edit$/, admin: true, view: (m) => renderAdminMaschineForm(+m[1]) },
  { pattern: /^#\/admin\/maschinen\/(\d+)\/historie$/, admin: true, view: (m) => renderAdminHistorie(+m[1]) },
  { pattern: /^#\/admin\/benutzer$/, admin: true, view: renderAdminBenutzer },
];

async function route() {
  const hash = location.hash || '#/';
  const eintrag = ROUTEN.find((r) => r.pattern.test(hash));

  if (!eintrag) {
    document.getElementById('app').innerHTML = `
      <main class="max-w-md mx-auto pt-16 px-4 text-center">
        <h1 class="text-xl font-semibold text-txt mb-2">Seite nicht gefunden</h1>
        <a href="#/" class="text-accent underline">Zur Startseite</a>
      </main>`;
    renderChrome();
    return;
  }

  if (eintrag.route) {
    location.hash = eintrag.route();
    return;
  }

  if (!eintrag.public && !state.angemeldet) {
    location.hash = '#/login';
    return;
  }

  if (eintrag.admin && !state.istAdmin) {
    toast('Keine Berechtigung für diesen Bereich.', 'error');
    location.hash = '#/meine';
    return;
  }

  const match = hash.match(eintrag.pattern);
  try {
    await eintrag.view(match);
  } catch (err) {
    document.getElementById('app').innerHTML =
      `<main class="max-w-md mx-auto pt-8 px-4 text-rose-600">${escapeHtml(err.detail || err.message)}</main>`;
  }
  renderChrome();
}

function renderChrome() {
  const topbar    = document.getElementById('topbar');
  const bottomnav = document.getElementById('bottomnav');

  if (!state.angemeldet) {
    topbar.classList.add('hidden');
    bottomnav.classList.add('hidden');
    return;
  }

  topbar.classList.remove('hidden');
  topbar.innerHTML = `
    <div class="max-w-3xl mx-auto px-4 h-14 flex items-center justify-between">
      <div class="flex items-center gap-2">
        ${logoMarkup('h-7 w-7 text-xs')}
        <span class="font-semibold text-txt">Werkzeug-Ausleihe</span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-muted hidden sm:inline">${escapeHtml(state.benutzer.voller_name)}</span>
        <button id="btn-logout" class="${btnClasses('ghost')} px-3 min-h-[40px] text-sm">Abmelden</button>
      </div>
    </div>`;
  document.getElementById('btn-logout').onclick = logout;

  const links = [
    { hash: '#/geraete', label: 'Geräte', icon: '🔧' },
    { hash: '#/meine',   label: 'Meine',  icon: '📋' },
    { label: 'Code',     icon: '🔍', action: scanOrAsk },
  ];
  if (state.istAdmin) links.push({ hash: '#/admin', label: 'Admin', icon: '⚙️' });

  bottomnav.classList.remove('hidden');
  const aktivHash = location.hash.split('?')[0];
  bottomnav.innerHTML = `
    <div class="max-w-3xl mx-auto h-16 border-t border-border bg-bg grid"
         style="grid-template-columns: repeat(${links.length}, minmax(0, 1fr));">
      ${links.map((l, i) => {
        const aktiv = l.hash && aktivHash === l.hash;
        return `
        <button data-i="${i}" aria-label="${escapeHtml(l.label)}"${aktiv ? ' aria-current="page"' : ''}
                class="flex flex-col items-center justify-center text-xs gap-1 ${aktiv ? 'text-accent' : 'text-muted'} hover:bg-surface-2 active:scale-95 transition">
          <span class="text-xl leading-none" aria-hidden="true">${l.icon}</span>
          <span>${l.label}</span>
        </button>`;
      }).join('')}
    </div>`;
  bottomnav.querySelectorAll('[data-i]').forEach((b) => {
    const i = +b.dataset.i;
    b.onclick = () => {
      if (links[i].action) Promise.resolve(links[i].action()).catch((e) => console.error(e));
      else if (links[i].hash) location.hash = links[i].hash;
    };
  });
}

async function scanOrAsk() {
  const code = await holeWerkzeugCode(scanQr);
  if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
  else await askCode();   // Abbruch/Kamera nicht möglich → manuelle Eingabe
}

async function askCode() {
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'z.B. M-0001';
  input.className =
    'w-full bg-surface text-txt placeholder:text-muted border border-border rounded-xl px-3 py-3 text-lg uppercase';
  input.onkeydown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const ok = input.closest('.fixed').querySelector('button');
      if (ok) ok.click();
    }
  };

  const result = await modal({
    titel: 'Maschinen-Code eingeben',
    body: input,
    buttons: [
      { label: 'Öffnen',    variant: 'primary',   value: 'go' },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  if (result === 'go') {
    const code = input.value.trim().toUpperCase();
    if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
  }
}

async function logout() {
  try { await api.post('/api/logout'); } catch { /* best effort */ }
  clearToken();
  state.benutzer = null;
  location.hash = '#/login';
}

async function bootstrap() {
  if (getToken()) {
    try {
      state.benutzer = await api.get('/api/me');
    } catch {
      // ApiError 401 wurde im api.js bereits behandelt (Token gelöscht).
    }
  }
  window.addEventListener('hashchange', route);
  route();
}

bootstrap();
