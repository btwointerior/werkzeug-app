// Bootstrap, App-State, Hash-Router, Top-Bar + Bottom-Nav.

import { api, getToken, setToken, clearToken } from './api.js';
import { btnClasses, escapeHtml, modal, toast } from './ui.js';
import { scanQr } from './scanner.js';
import { passwortAendernDialog } from './passwort.js';
import { holeWerkzeugCode } from './scanner_quelle.js';
import { istNfcVerfuegbar, nfcLeseCode } from './nfc.js';

import { renderLogin } from './views/login.js';
import { renderMeine } from './views/meine.js';
import { renderGeraete } from './views/geraete.js';
import { renderMaschine } from './views/maschine.js';
import { renderAdminDashboard } from './views/admin_dashboard.js';
import { renderAdminMaschinen } from './views/admin_maschinen.js';
import { renderAdminMaschineForm } from './views/admin_maschine_form.js';
import { renderAdminHistorie } from './views/admin_historie.js';
import { renderAdminBenutzer } from './views/admin_benutzer.js';
import { renderAdminFreieAusgaben } from './views/admin_freie_ausgaben.js';
import { neueFreieAusgabe } from './views/freie_ausgabe.js';

// Portal b² (home.b2interior.de): im Web liegt die Oberfläche hinter dem Portal-Login;
// Abmelden führt dorthin. Die native App (WERKZEUG_API_BASE gesetzt) meldet sich weiter selbst an.
const PORTAL_URL = 'https://home.b2interior.de/';
const istWeb = () => !globalThis.WERKZEUG_API_BASE;

export const state = {
  benutzer: null,
  ssoHinweis: '',
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
  { pattern: /^#\/admin\/freie-ausgaben$/, admin: true, view: renderAdminFreieAusgaben },
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
      `<main class="max-w-md mx-auto pt-8 px-4 text-broken">${escapeHtml(err.detail || err.message)}</main>`;
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

  // Kopf: Marke (Bildmarke + Werkzeug + Untertitel) im b2-design-.brand-Stil, Link zur
  // Portal-Übersicht; Haus-Symbol 40 px rechts daneben (Regel b2-design/README „Home-Knopf").
  topbar.classList.remove('hidden');
  topbar.classList.add('brand-top', 'app-top');
  topbar.innerHTML = `
    <a class="brand" href="${PORTAL_URL}" aria-label="Zur Portal-Übersicht" style="flex:1 1 auto;min-width:0">
      <span class="brand-mark"><img src="/static/design/logo/bildmarke-hell-200.png" alt="b²"></span>
      <span><span class="brand-name">Werkzeug</span><span class="brand-sub">bühler² · Ausleihe &amp; Geräte</span></span>
    </a>
    <a class="home-btn" href="${PORTAL_URL}" title="Zur Übersicht" aria-label="Zur Übersicht" style="width:40px;height:40px">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M10 20v-5h4v5"/></svg>
    </a>
    <span class="text-sm text-muted hidden sm:inline" style="margin-left:var(--sp-3)">${escapeHtml(state.benutzer.voller_name)}</span>
    <button id="btn-passwort" aria-label="Passwort ändern" title="Passwort ändern"
            class="${btnClasses('ghost')} px-3 min-h-[40px] text-sm" style="margin-left:var(--sp-2)">🔑</button>
    <button id="btn-logout" class="${btnClasses('ghost')} px-3 min-h-[40px] text-sm">Abmelden</button>`;
  document.getElementById('btn-passwort').onclick = () =>
    passwortAendernDialog().catch((e) => console.error(e));
  document.getElementById('btn-logout').onclick = logout;

  const links = [
    { hash: '#/geraete', label: 'Geräte', icon: '🔧' },
    { hash: '#/meine',   label: 'Meine',  icon: '📋' },
    { label: 'Ausleihen', icon: '🔄', action: scanOrAsk },
  ];
  if (state.istAdmin) links.push({ hash: '#/admin', label: 'Admin', icon: '⚙️' });

  // Untere Navigation im .tabbar-Stil (hell, 44-px-Tap-Ziele, Safe-Area); Werkzeug hat
  // kein Seitenleisten-Gegenstück, daher bleibt die Leiste bei jeder Breite sichtbar
  // (Klasse `tabbar-fest` in index.html hebt die Mobil-Schwelle von `.tabbar` auf).
  bottomnav.classList.remove('hidden');
  bottomnav.classList.add('tabbar-fest');
  const aktivHash = location.hash.split('?')[0];
  bottomnav.innerHTML = `
    <div class="max-w-3xl mx-auto w-full grid"
         style="grid-template-columns: repeat(${links.length}, minmax(0, 1fr));">
      ${links.map((l, i) => {
        const aktiv = l.hash && aktivHash === l.hash;
        return `
        <button data-i="${i}" aria-label="${escapeHtml(l.label)}"${aktiv ? ' aria-current="page"' : ''}
                class="flex flex-col items-center justify-center text-xs gap-1 min-h-[44px] ${aktiv ? 'text-accent' : 'text-muted'} hover:bg-surface-2 active:scale-95 transition">
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
  const quelle = () => scanQr({
    nfc: istNfcVerfuegbar() ? nfcLeseCode : null,
    manuell: askCode,     // eigener Button im Overlay öffnet die Eingabe
    ohneCode: ohneCodeAusgeben,
  });
  const code = await holeWerkzeugCode(quelle);
  if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
  // "Abbrechen" bricht nur ab — keine automatische manuelle Eingabe mehr.
}

async function ohneCodeAusgeben() {
  const neu = await neueFreieAusgabe();
  if (neu) {
    if (location.hash === '#/meine') await route(); else location.hash = '#/meine';
  }
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
  if (istWeb()) { location.href = PORTAL_URL; return; }
  location.hash = '#/login';
}

// Portal-SSO (nur Web): Caddy hat das Portal-Cookie geprüft und reicht signierte Header
// durch; /sso/token tauscht sie gegen ein Werkzeug-Token (Benutzer per Kürzel).
async function portalAnmeldung() {
  try {
    const res = await fetch('/sso/token', { headers: { Accept: 'application/json' } });
    if (res.ok) {
      const d = await res.json();
      setToken(d.access_token);
      state.benutzer = d.benutzer;
    } else if (res.status === 401) {
      const d = await res.json().catch(() => ({}));
      state.ssoHinweis = d.detail || '';
    }
  } catch { /* ohne Portal: normaler Login */ }
}

async function bootstrap() {
  if (!getToken() && istWeb()) await portalAnmeldung();
  if (getToken() && !state.benutzer) {
    try {
      state.benutzer = await api.get('/api/me');
    } catch {
      // ApiError 401 wurde im api.js bereits behandelt (Token gelöscht).
    }
  }
  // 2026-10-28: Lag ein abgelaufenes Werkzeug-Token im Browser, landete man auf der
  // Anmeldemaske, obwohl das Portal-Cookie gültig war. Jetzt: nach dem Verwerfen
  // noch einmal das Portal fragen (einmal in der Portal-Übersicht angemeldet = überall drin).
  if (!state.benutzer && istWeb()) {
    await portalAnmeldung();
    if (getToken() && !state.benutzer) {
      try { state.benutzer = await api.get('/api/me'); } catch { /* bleibt Login */ }
    }
  }
  window.addEventListener('hashchange', route);
  route();
}

bootstrap();
