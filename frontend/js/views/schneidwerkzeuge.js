// Schneidwerkzeuge (Sägeblätter, Fräser …): Bestandsliste mit Übersicht, Suche und Filter.

import { api } from '../api.js';
import { btnClasses, escapeHtml, leerZustand, spinner } from '../ui.js';
import { state } from '../app.js';
import { kenndaten, ortText, parameterText, schaerfText } from '../schneidwerkzeug_helfer.js';

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
          ${w.einsatzgebiet || w.materialien ? `<div class="text-sm text-muted mt-1 break-words">${escapeHtml([w.einsatzgebiet, w.materialien].filter(Boolean).join(' · '))}</div>` : ''}
          ${parameterText(w) ? `<div class="text-sm text-muted break-words">${escapeHtml(parameterText(w))}</div>` : ''}
          ${w.masse_pruefen ? '<div class="text-sm text-maint font-semibold mt-1">Maße an der CNC prüfen</div>' : ''}
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
        <div class="flex gap-2 flex-wrap">
          <a href="#/verbrauchsteile" class="${btnClasses('secondary')} text-sm">Verbrauchsteile</a>
          ${state.istAdmin ? `<a href="#/schaerfauftraege" class="${btnClasses('secondary')} text-sm">Schärfaufträge</a>
          <a href="#/schneidwerkzeuge/neu" class="${btnClasses('primary')} text-sm">+ Neu</a>` : ''}
        </div>
      </div>
      <div id="sw-uebersicht" class="mb-4"></div>
      <div class="flex gap-2 mb-4" role="tablist" aria-label="Ansicht">
        <button id="sw-ans-liste" role="tab" class="flex-1 px-3 py-2 rounded-lg border border-border text-sm font-semibold">Liste</button>
        <button id="sw-ans-ort" role="tab" class="flex-1 px-3 py-2 rounded-lg border border-border text-sm font-semibold">Nach Ort</button>
      </div>
      <div id="sw-ort" class="hidden"></div>
      <div id="sw-filter" class="flex flex-wrap gap-2 mb-4">
        <input id="sw-suche" placeholder="Suche (Code, Name, Einsatz, Material, Maschine, Fach)…"
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
  const ortBox = document.getElementById('sw-ort');
  const filterBox = document.getElementById('sw-filter');
  const tabListe = document.getElementById('sw-ans-liste');
  const tabOrt = document.getElementById('sw-ans-ort');
  let timer = 0;

  // Ansicht merken, damit man nach dem Blick auf ein Werkzeug wieder dort landet.
  const zeigeAnsicht = (ansicht) => {
    const ort = ansicht === 'ort';
    ortBox.classList.toggle('hidden', !ort);
    filterBox.classList.toggle('hidden', ort);
    liste.classList.toggle('hidden', ort);
    for (const [tab, aktiv] of [[tabListe, !ort], [tabOrt, ort]]) {
      tab.setAttribute('aria-selected', String(aktiv));
      tab.classList.toggle('bg-accent', aktiv);
      tab.classList.toggle('text-accent-ink', aktiv);
      tab.classList.toggle('bg-surface', !aktiv);
      tab.classList.toggle('text-txt-2', !aktiv);
    }
    try { sessionStorage.setItem('sw-ansicht', ort ? 'ort' : 'liste'); } catch { /* ohne Speicher */ }
  };
  tabListe.onclick = () => zeigeAnsicht('liste');
  tabOrt.onclick = () => zeigeAnsicht('ort');
  let gemerkt = 'liste';
  try { gemerkt = sessionStorage.getItem('sw-ansicht') || 'liste'; } catch { /* ohne Speicher */ }
  zeigeAnsicht(gemerkt);

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
        </div>` : ''}
      ${u.fast_aufgebraucht.length ? `
        <div class="border border-maint/40 bg-maint/10 rounded-lg p-3 mt-3 text-sm text-txt">
          <div class="font-semibold mb-1">⚠️ Schärfungen fast aufgebraucht</div>
          <ul class="list-disc pl-5">${u.fast_aufgebraucht.map((w) => `<li><a class="underline" href="#/sw/${encodeURIComponent(w.code)}">${escapeHtml(w.code)}</a> ${escapeHtml(w.bezeichnung)} <span class="text-muted">(${w.rest === 0 ? 'keine mehr' : 'noch 1'})</span></li>`).join('')}</ul>
        </div>` : ''}
      ${u.masse_pruefen.length ? `
        <div class="border border-maint/40 bg-maint/10 rounded-lg p-3 mt-3 text-sm text-txt">
          <div class="font-semibold mb-1">⚠️ Maße an der CNC prüfen</div>
          <ul class="list-disc pl-5">${u.masse_pruefen.map((w) => `<li><a class="underline" href="#/sw/${encodeURIComponent(w.code)}">${escapeHtml(w.code)}</a> ${escapeHtml(w.bezeichnung)}</li>`).join('')}</ul>
        </div>` : ''}
      ${u.nachbestellen.length ? `
        <a href="#/verbrauchsteile" class="block border border-maint/40 bg-maint/10 rounded-lg p-3 mt-3 text-sm text-txt">
          <div class="font-semibold mb-1">⚠️ Verbrauchsteile nachbestellen</div>
          <ul class="list-disc pl-5">${u.nachbestellen.map((t) => `<li>${escapeHtml(t.bezeichnung)} <span class="text-muted">(${t.bestand} da, Mindestbestand ${t.mindestbestand})</span></li>`).join('')}</ul>
        </a>` : ''}`;
    // Ansicht „Nach Ort": je Maschine, was eingebaut ist; je Lagerfach, was dort liegt.
    const eintrag = (w) => `<li class="py-1"><a class="underline text-txt" href="#/sw/${encodeURIComponent(w.code)}">${escapeHtml(w.code)}</a>
      <span class="text-txt-2 break-words">${escapeHtml(w.bezeichnung)}</span>${w.platz ? ` <span class="text-muted">· Platz ${escapeHtml(w.platz)}</span>` : ''}</li>`;
    const block = (titel, werkzeuge, leer) => `
      <section class="bg-surface border border-border rounded-lg p-4 mb-3">
        <h3 class="font-semibold text-txt mb-1">${escapeHtml(titel)} <span class="text-muted font-normal">(${werkzeuge.length})</span></h3>
        ${werkzeuge.length ? `<ul class="text-sm">${werkzeuge.map(eintrag).join('')}</ul>` : `<div class="text-sm text-muted">${leer}</div>`}
      </section>`;
    ortBox.innerHTML = `
      <h2 class="text-lg font-semibold text-txt mb-2">In den Maschinen</h2>
      ${u.nach_ort.maschinen.map((m) => block(m.name, m.werkzeuge, 'Nichts eingebaut.')).join('')}
      <h2 class="text-lg font-semibold text-txt mb-2 mt-5">Im Lager (scharf)</h2>
      ${u.nach_ort.lager.length ? u.nach_ort.lager.map((l) => block(l.name, l.werkzeuge, '')).join('') : '<div class="text-sm text-muted mb-3">Kein scharfes Werkzeug im Lager.</div>'}
      ${state.istAdmin ? `<a href="#/schneidwerkzeuge/maschinen" class="${btnClasses('secondary')} text-sm">Maschinenliste bearbeiten</a>` : ''}`;
    kopf.querySelectorAll('[data-status]').forEach((b) => { b.onclick = () => { stat.value = b.dataset.status; zeigeAnsicht('liste'); laden(); }; });
  } catch { /* Liste funktioniert auch ohne Übersicht */ }

  suche.oninput = () => { clearTimeout(timer); timer = setTimeout(laden, 250); };
  stat.onchange = laden;
  art.onchange = laden;
  await laden();
}
