// Seite eines Schneidwerkzeugs: Stammdaten, Status-Aktionen, Schärfungen, Verlauf.

import { api, oeffneBlobImNeuenTab } from '../api.js';
import { btnClasses, confirmDialog, escapeHtml, formatDatum, modal, spinner, toast } from '../ui.js';
import { state } from '../app.js';
import { ergebnisText, euro, kenndaten, ortText, parameterText, schaerfText } from '../schneidwerkzeug_helfer.js';
import { schneidStatusBadge } from './schneidwerkzeuge.js';

const feldCls = 'w-full bg-surface text-txt placeholder:text-muted border border-border rounded-xl px-3 py-3';

/** Dialog „Einbauen": Maschine (mit Vorschlägen) + Platz. @returns {{maschine, platz}|null} */
async function frageEinbau() {
  let werte = { maschinen: [] };
  try { werte = await api.get('/api/schneidwerkzeuge/stammwerte'); } catch { /* ohne Vorschläge */ }
  const body = document.createElement('div');
  body.innerHTML = `
    <label class="block text-sm text-muted mb-1" for="sw-e-maschine">Maschine</label>
    <select id="sw-e-maschine" class="${feldCls} mb-3">
      <option value="">– bitte wählen –</option>
      ${werte.maschinen.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('')}
    </select>
    <label class="block text-sm text-muted mb-1" for="sw-e-platz">Platz / Werkzeugnummer (optional)</label>
    <input id="sw-e-platz" class="${feldCls}" placeholder="z. B. T12 oder Hauptsäge" autocomplete="off">`;
  const ok = await modal({ titel: 'In Maschine einbauen', body, buttons: [
    { label: 'Einbauen', variant: 'primary', value: true }, { label: 'Abbrechen', variant: 'secondary', value: null }] });
  if (!ok) return null;
  const maschine = body.querySelector('#sw-e-maschine').value.trim();
  if (!maschine) { toast('Bitte die Maschine wählen.', 'error'); return null; }
  return { maschine, platz: body.querySelector('#sw-e-platz').value.trim() };
}

/** Dialog mit optionaler Bemerkung. @returns {string|null} Text (auch leer) oder null bei Abbruch */
async function frageNotiz(titel, okLabel, platzhalter) {
  const feld = document.createElement('textarea');
  feld.className = feldCls;
  feld.rows = 2;
  feld.placeholder = platzhalter;
  const ok = await modal({ titel, body: feld, buttons: [
    { label: okLabel, variant: 'primary', value: true }, { label: 'Abbrechen', variant: 'secondary', value: null }] });
  return ok ? feld.value.trim() : null;
}

function zeile(label, wert) {
  if (wert == null || wert === '') return '';
  return `<div class="flex justify-between gap-3 py-1 border-b border-border/60 last:border-0">
    <dt class="text-muted">${escapeHtml(label)}</dt><dd class="text-txt text-right break-words min-w-0">${escapeHtml(String(wert))}</dd></div>`;
}

export async function renderSchneidwerkzeug(code) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;
  const main = app.querySelector('main');

  let w;
  try {
    w = await api.get(`/api/schneidwerkzeuge/code/${encodeURIComponent(code)}`);
  } catch (err) {
    main.innerHTML = `<div class="text-broken mb-4">${escapeHtml(err.detail || 'Werkzeug nicht gefunden.')}</div>
      <a href="#/schneidwerkzeuge" class="${btnClasses('secondary')}">Zur Liste</a>`;
    return;
  }

  const setze = async (daten, meldung) => {
    try {
      await api.post(`/api/schneidwerkzeuge/${w.id}/status`, daten);
      toast(meldung, 'success');
      await renderSchneidwerkzeug(w.code);
    } catch (err) { toast(err.detail || 'Das hat nicht geklappt.', 'error'); }
  };

  const aktionen = [];
  const knopf = (id, label, variante = 'secondary') => { aktionen.push(`<button data-akt="${id}" class="${btnClasses(variante)} text-sm">${label}</button>`); };
  if (w.status === 'lager') { knopf('einbauen', 'In Maschine einbauen', 'primary'); knopf('stumpf', 'Stumpf melden'); knopf('sperren', 'Sperren'); }
  if (w.status === 'maschine') { knopf('lager', 'Ausbauen → Lager', 'primary'); knopf('stumpf', 'Stumpf melden'); knopf('sperren', 'Sperren'); }
  if (w.status === 'stumpf') { knopf('lager', 'Doch scharf → Lager'); if (state.istAdmin) aktionen.push(`<a href="#/schaerfauftraege" class="${btnClasses('primary')} text-sm">Zum Schärfdienst geben</a>`); }
  if (w.status === 'gesperrt') knopf('lager', 'Freigeben → Lager', 'primary');
  if (w.status === 'schaerfdienst' && state.istAdmin) aktionen.push(`<a href="#/schaerfauftraege" class="${btnClasses('primary')} text-sm">Rückkehr buchen</a>`);
  if (w.status === 'verschrottet' && state.istAdmin) knopf('lager', 'Reaktivieren → Lager');

  const s = schaerfText(w);
  main.innerHTML = `
    <div class="flex items-center justify-between mb-3 gap-2">
      <a href="#/schneidwerkzeuge" class="text-accent underline text-sm">← Sägeblätter &amp; Fräser</a>
      ${schneidStatusBadge(w)}
    </div>
    <h1 class="text-2xl font-bold text-txt break-words">${escapeHtml(w.bezeichnung)}</h1>
    <div class="text-muted mb-1 break-words">${escapeHtml(w.code)} · ${escapeHtml(kenndaten(w))}</div>
    <div class="text-txt-2 mb-4 break-words">${escapeHtml(ortText(w))}</div>

    ${s.erschoepft ? `<div class="border border-broken/30 bg-broken/10 rounded-lg p-3 mb-4 text-sm text-broken">
      Die vorgesehene Zahl an Schärfungen ist erreicht. Vor dem nächsten Schärfen prüfen, ob sich das noch lohnt.</div>` : ''}

    ${w.masse_pruefen ? `<div class="border border-maint/40 bg-maint/10 rounded-lg p-3 mb-4 text-sm text-txt flex items-center justify-between gap-3 flex-wrap">
      <span><strong>Maße an der CNC prüfen.</strong> Das Werkzeug war beim Schärfen und ist jetzt kleiner.</span>
      <button data-akt="masse" class="${btnClasses('primary')} text-sm">Geprüft und eingetragen</button></div>` : ''}

    ${aktionen.length ? `<div class="flex flex-wrap gap-2 mb-5">${aktionen.join('')}</div>` : ''}

    ${w.einsatzgebiet || w.materialien || parameterText(w) || w.parameter_notiz ? `<section class="bg-surface border border-border rounded-lg p-4 mb-4">
      <h2 class="font-semibold text-txt mb-2">Einsatz &amp; Parameter</h2>
      ${w.einsatzgebiet ? `<p class="text-txt mb-2 break-words whitespace-pre-line">${escapeHtml(w.einsatzgebiet)}</p>` : ''}
      ${w.materialien ? `<div class="flex flex-wrap gap-1 mb-2">${w.materialien.split(',').map((m) => `<span class="px-2 py-1 rounded-full text-xs bg-surface-2 text-txt-2">${escapeHtml(m.trim())}</span>`).join('')}</div>` : ''}
      <dl class="text-sm">
        ${zeile('Drehzahl', w.drehzahl_empfohlen ? `${w.drehzahl_empfohlen.toLocaleString('de-DE')} 1/min` : null)}
        ${zeile('Vorschub', w.vorschub_empfohlen ? `${String(w.vorschub_empfohlen).replace('.', ',')} m/min` : null)}
        ${zeile('Hinweise', w.parameter_notiz)}
      </dl>
    </section>` : (state.istAdmin ? `<a href="#/schneidwerkzeuge/${w.id}/edit" class="block border border-dashed border-border rounded-lg p-3 mb-4 text-sm text-muted">Einsatzgebiet und Parameter sind noch nicht hinterlegt. Jetzt eintragen →</a>` : '')}

    <section class="bg-surface border border-border rounded-lg p-4 mb-4">
      <h2 class="font-semibold text-txt mb-2">Daten</h2>
      <dl class="text-sm">
        ${zeile('Hersteller', w.hersteller)}${zeile('Artikelnummer', w.artikelnummer)}${zeile('Schneidstoff', w.schneidstoff)}
        ${zeile('Durchmesser', w.durchmesser_mm != null ? `${String(w.durchmesser_mm).replace('.', ',')} mm` : null)}
        ${zeile(w.art === 'saegeblatt' || w.art === 'vorritzer' ? 'Schnittbreite' : 'Schneidenlänge', w.schneidenlaenge_mm != null ? `${String(w.schneidenlaenge_mm).replace('.', ',')} mm` : null)}
        ${zeile(w.art === 'saegeblatt' || w.art === 'vorritzer' ? 'Bohrung' : 'Schaft', w.bohrung_schaft_mm != null ? `${String(w.bohrung_schaft_mm).replace('.', ',')} mm` : null)}
        ${zeile('Zähnezahl', w.zaehnezahl)}${zeile('Höchstdrehzahl', w.max_drehzahl != null ? `${w.max_drehzahl} 1/min` : null)}
        ${zeile('Lagerfach', w.lagerort)}${zeile('Gehört zusammen mit', w.partner_code)}
        ${zeile('Schärfungen', s.text)}${zeile('Schärfkosten bisher', w.schaerfkosten_cent ? euro(w.schaerfkosten_cent) : null)}
        ${zeile('Gekauft am', w.kaufdatum ? w.kaufdatum.split('-').reverse().join('.') : null)}${zeile('Kaufpreis', w.kaufpreis_cent != null ? euro(w.kaufpreis_cent) : null)}
        ${zeile('Notiz', w.notiz)}
      </dl>
      ${w.partner_code ? `<a href="#/sw/${encodeURIComponent(w.partner_code)}" class="text-accent underline text-sm">Zum Partner-Werkzeug ${escapeHtml(w.partner_code)}</a>` : ''}
    </section>

    ${w.schaerfpositionen.length ? `<section class="bg-surface border border-border rounded-lg p-4 mb-4">
      <h2 class="font-semibold text-txt mb-2">Schärfdienst</h2>
      <ul class="text-sm space-y-2">${w.schaerfpositionen.map((p) => `
        <li class="border-b border-border/60 last:border-0 pb-2">
          <div class="text-txt">${escapeHtml(p.dienst)} · abgegeben ${formatDatum(p.abgabe_zeitpunkt)}</div>
          <div class="text-muted">${p.zurueck_am
            ? `zurück ${formatDatum(p.zurueck_am)} · ${escapeHtml(ergebnisText(p.ergebnis))}${p.kosten_cent != null ? ` · ${euro(p.kosten_cent)}` : ''}`
            : 'noch nicht zurück'}${p.notiz ? ` · ${escapeHtml(p.notiz)}` : ''}</div>
        </li>`).join('')}</ul></section>` : ''}

    <section class="bg-surface border border-border rounded-lg p-4 mb-4">
      <h2 class="font-semibold text-txt mb-2">Verlauf</h2>
      <ul class="text-sm space-y-2">${w.ereignisse.map((e) => `
        <li><span class="text-muted">${formatDatum(e.zeitpunkt)}${e.benutzer_name ? ` · ${escapeHtml(e.benutzer_name)}` : ''}</span><br>
          <span class="text-txt break-words">${escapeHtml(e.text)}</span></li>`).join('')}</ul>
    </section>

    ${state.istAdmin ? `<div class="flex flex-wrap gap-2">
      <a href="#/schneidwerkzeuge/${w.id}/edit" class="${btnClasses('secondary')} text-sm">Bearbeiten</a>
      <a href="#/schneidwerkzeuge/neu?kopie=${w.id}" class="${btnClasses('secondary')} text-sm">Kopie anlegen</a>
      <button data-akt="qr" class="${btnClasses('secondary')} text-sm">QR-Etikett</button>
      ${w.status !== 'verschrottet' && w.status !== 'schaerfdienst' ? `<button data-akt="verschrotten" class="${btnClasses('ghost')} text-sm text-broken">Verschrotten</button>` : ''}
      ${w.schaerfpositionen.length ? '' : `<button data-akt="loeschen" class="${btnClasses('ghost')} text-sm text-broken">Löschen</button>`}
    </div>` : ''}`;

  const handler = {
    einbauen: async () => { const e = await frageEinbau(); if (e) await setze({ status: 'maschine', ...e }, 'Eingebaut.'); },
    lager: () => setze({ status: 'lager' }, 'Liegt jetzt im Lager.'),
    masse: async () => {
      try { await api.post(`/api/schneidwerkzeuge/${w.id}/masse-geprueft`); toast('Abgehakt.', 'success'); await renderSchneidwerkzeug(w.code); }
      catch (err) { toast(err.detail || 'Das hat nicht geklappt.', 'error'); }
    },
    stumpf: async () => { const n = await frageNotiz('Stumpf melden', 'Stumpf melden', 'Bemerkung (optional), z. B. Ausrisse an HPL'); if (n !== null) await setze({ status: 'stumpf', notiz: n }, 'Als stumpf gemeldet.'); },
    sperren: async () => { const n = await frageNotiz('Werkzeug sperren', 'Sperren', 'Grund (optional), z. B. Zahn ausgebrochen'); if (n !== null) await setze({ status: 'gesperrt', notiz: n }, 'Gesperrt.'); },
    verschrotten: async () => { if (await confirmDialog(`${w.code} wirklich verschrotten? Es verschwindet aus der Liste, bleibt aber in der Historie.`, { titel: 'Verschrotten?', okLabel: 'Verschrotten', dangerous: true })) await setze({ status: 'verschrottet' }, 'Verschrottet.'); },
    qr: () => oeffneBlobImNeuenTab(`/api/schneidwerkzeuge/${w.id}/qr-code`).catch((err) => toast(err.detail || 'Etikett konnte nicht erzeugt werden.', 'error')),
    loeschen: async () => {
      if (!await confirmDialog(`${w.code} endgültig löschen? Das ist nur für Fehleingaben gedacht.`, { titel: 'Löschen?', okLabel: 'Löschen', dangerous: true })) return;
      try { await api.del(`/api/schneidwerkzeuge/${w.id}`); toast('Gelöscht.', 'success'); location.hash = '#/schneidwerkzeuge'; }
      catch (err) { toast(err.detail || 'Löschen nicht möglich.', 'error'); }
    },
  };
  main.querySelectorAll('[data-akt]').forEach((b) => { b.onclick = () => Promise.resolve(handler[b.dataset.akt]()).catch((e) => console.error(e)); });
}
