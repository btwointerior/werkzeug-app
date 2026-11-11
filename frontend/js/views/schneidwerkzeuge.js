// Schneidwerkzeuge (Sägeblätter, Fräser …): Bestandsliste mit Übersicht, Suche und Filter.

import { api } from '../api.js';
import { btnClasses, escapeHtml, leerZustand, spinner } from '../ui.js';
import { state } from '../app.js';
import { kenndaten, ortText, schaerfText } from '../schneidwerkzeug_helfer.js';

const STATUS_FARBE = {
  lager: 'text-ok', maschine: 'text-lent', stumpf: 'text-maint',
  schaerfdienst: 'text-maint', gesperrt: 'text-broken', verschrottet: 'text-muted',
};

export function schneidStatusBadge(w) {
  return `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold bg-surface-2 whitespace-nowrap ${STATUS_FARBE[w.status] || 'text-muted'}">` +
         `<span class="text-[8px] leading-none">●</span>${escapeHtml(w.status_text)}</span>`;
}

export function schneidwerkzeugKarte(w) {
  const s = schaerfText(w);
  return `
    <a href="#/sw/${encodeURIComponent(w.code)}"
       class="block bg-surface rounded-lg shadow-sm p-4 mb-3 border border-border hover:bg-surface-2">
      <div class="flex justify-between items-start gap-3">
        <div class="min-w-0">
          <div class="font-semibold text-txt break-words">${escapeHtml(w.bezeichnung)}</div>
          <div class="text-sm text-muted break-words">${escapeHtml(w.code)} · ${escapeHtml(kenndaten(w))}</div>
          <div class="text-sm text-txt-2 mt-1 break-words">${escapeHtml(ortText(w))}
            <span class="${s.erschoepft ? 'text-broken font-semibold' : 'text-muted'}"> · ${escapeHtml(s.text)}</span></div>
        </div>
        ${schneidStatusBadge(w)}
      </div>
    </a>`;
}

export async function renderSchneidwerkzeuge() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <h1 class="text-2xl font-bold text-txt">Sägeblätter &amp; Fräser</h1>
        ${state.istAdmin ? `<div class="flex gap-2 flex-wrap">
          <a href="#/schaerfauftraege" class="${btnClasses('secondary')} text-sm">Schärfaufträge</a>
          <a href="#/schneidwerkzeuge/neu" class="${btnClasses('primary')} text-sm">+ Neu</a>
        </div>` : ''}
      </div>
      <div id="sw-uebersicht" class="mb-4"></div>
      <div class="flex flex-wrap gap-2 mb-4">
        <input id="sw-suche" placeholder="Suche (Code, Name, Hersteller, Maschine, Fach)…"
               class="flex-1 min-w-0 basis-full sm:basis-0 border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        <select id="sw-status" aria-label="Status" class="flex-1 min-w-0 border border-border rounded-lg px-3 py-2 bg-surface text-txt">
          <option value="">Alle (ohne Verschrottete)</option>
        </select>
        <select id="sw-art" aria-label="Art" class="flex-1 min-w-0 border border-border rounded-lg px-3 py-2 bg-surface text-txt">
          <option value="">Alle Arten</option>
        </select>
      </div>
      <div id="sw-liste">${spinner()}</div>
    </main>`;

  const suche = document.getElementById('sw-suche');
  const stat = document.getElementById('sw-status');
  const art = document.getElementById('sw-art');
  const liste = document.getElementById('sw-liste');
  const kopf = document.getElementById('sw-uebersicht');
  let timer = 0;

  async function laden() {
    const p = new URLSearchParams();
    if (suche.value.trim()) p.set('suche', suche.value.trim());
    if (stat.value) p.set('status', stat.value);
    if (art.value) p.set('art', art.value);
    try {
      const eintraege = await api.get(`/api/schneidwerkzeuge?${p}`);
      liste.innerHTML = eintraege.length
        ? eintraege.map(schneidwerkzeugKarte).join('')
        : leerZustand(suche.value || stat.value || art.value ? 'Keine Werkzeuge gefunden.' : 'Noch keine Werkzeuge angelegt.');
    } catch (err) {
      liste.innerHTML = `<div class="p-4 text-broken">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
    }
  }

  try {
    const [werte, u] = await Promise.all([api.get('/api/schneidwerkzeuge/stammwerte'), api.get('/api/schneidwerkzeuge/uebersicht')]);
    stat.insertAdjacentHTML('beforeend', werte.status.map((s) => `<option value="${s.key}">${escapeHtml(s.text)}</option>`).join('') + '<option value="alle">Alle inkl. Verschrottete</option>');
    art.insertAdjacentHTML('beforeend', werte.arten.map((a) => `<option value="${a.key}">${escapeHtml(a.text)}</option>`).join(''));
    const texte = Object.fromEntries(werte.status.map((s) => [s.key, s.text]));
    kopf.innerHTML = `
      <div class="flex flex-wrap gap-2">
        ${Object.entries(u.je_status).filter(([, n]) => n > 0).map(([k, n]) => `
          <button data-status="${escapeHtml(k)}" class="px-3 py-2 rounded-lg border border-border bg-surface text-sm ${STATUS_FARBE[k] || ''}">
            <span class="font-semibold">${n}</span> ${escapeHtml(texte[k] || k)}</button>`).join('')}
      </div>
      ${u.ohne_ersatz.length ? `
        <div class="border border-maint/40 bg-maint/10 rounded-lg p-3 mt-3 text-sm text-txt">
          <div class="font-semibold mb-1">⚠️ Kein scharfes Ersatzwerkzeug im Lager</div>
          <ul class="list-disc pl-5">${u.ohne_ersatz.map((g) => `<li>${escapeHtml(g.bezeichnung)} <span class="text-muted">(${escapeHtml(g.art_text)}, ${g.maschine} in Maschine)</span></li>`).join('')}</ul>
        </div>` : ''}`;
    kopf.querySelectorAll('[data-status]').forEach((b) => { b.onclick = () => { stat.value = b.dataset.status; laden(); }; });
  } catch { /* Liste funktioniert auch ohne Übersicht */ }

  suche.oninput = () => { clearTimeout(timer); timer = setTimeout(laden, 250); };
  stat.onchange = laden;
  art.onchange = laden;
  await laden();
}
