// Admin: Schärfaufträge – Werkzeuge an den Schärfdienst abgeben, Rückkehr mit Kosten buchen,
// Begleitliste drucken.

import { api } from '../api.js';
import { btnClasses, escapeHtml, formatDatum, leerZustand, modal, spinner, toast } from '../ui.js';
import { centAusEingabe, euro, kenndaten, ortText } from '../schneidwerkzeug_helfer.js';

const feldCls = 'w-full bg-surface text-txt placeholder:text-muted border border-border rounded-xl px-3 py-2';

/** Dialog „Neuer Schärfauftrag". @returns {boolean} true, wenn angelegt */
async function neuerAuftrag() {
  let werkzeuge;
  let werte;
  try {
    [werkzeuge, werte] = await Promise.all([api.get('/api/schneidwerkzeuge'), api.get('/api/schneidwerkzeuge/stammwerte')]);
  } catch (err) { toast(err.detail || 'Fehler beim Laden.', 'error'); return false; }
  // Stumpfe zuerst und vorausgewählt; alles andere (außer beim Schärfdienst) kann dazugenommen werden.
  const waehlbar = werkzeuge.filter((w) => w.status !== 'schaerfdienst')
    .sort((a, b) => (a.status === 'stumpf' ? 0 : 1) - (b.status === 'stumpf' ? 0 : 1) || a.code.localeCompare(b.code));
  if (!waehlbar.length) { toast('Es gibt kein Werkzeug, das abgegeben werden kann.', 'error'); return false; }
  const body = document.createElement('div');
  body.innerHTML = `
    <label class="block text-sm text-muted mb-1" for="sa-dienst">Schärfdienst</label>
    <input id="sa-dienst" list="sa-dienste" class="${feldCls} mb-3" value="${escapeHtml(werte.dienste[0] || '')}" placeholder="Name des Schärfdienstes" autocomplete="off">
    <datalist id="sa-dienste">${werte.dienste.map((d) => `<option value="${escapeHtml(d)}">`).join('')}</datalist>
    <div class="text-sm text-muted mb-1">Werkzeuge (stumpfe sind vorausgewählt)</div>
    <div class="border border-border rounded-xl max-h-64 overflow-y-auto mb-3">
      ${waehlbar.map((w) => `
        <label class="flex items-start gap-3 px-3 py-2 border-b border-border/60 last:border-0">
          <input type="checkbox" value="${w.id}" class="mt-1 w-5 h-5"${w.status === 'stumpf' ? ' checked' : ''}>
          <span class="min-w-0 text-sm"><span class="font-semibold text-txt">${escapeHtml(w.code)}</span> ${escapeHtml(w.bezeichnung)}
            <span class="block text-muted">${escapeHtml(w.status_text)} · ${escapeHtml(ortText(w))}</span></span>
        </label>`).join('')}
    </div>
    <label class="block text-sm text-muted mb-1" for="sa-notiz">Bemerkung (optional)</label>
    <input id="sa-notiz" class="${feldCls}" placeholder="z. B. Abholung Donnerstag" autocomplete="off">`;
  const ok = await modal({ titel: 'Neuer Schärfauftrag', body, buttons: [
    { label: 'Abgeben', variant: 'primary', value: true }, { label: 'Abbrechen', variant: 'secondary', value: null }] });
  if (!ok) return false;
  const dienst = body.querySelector('#sa-dienst').value.trim();
  const ids = [...body.querySelectorAll('input[type="checkbox"]:checked')].map((c) => +c.value);
  if (!dienst) { toast('Bitte den Schärfdienst angeben.', 'error'); return false; }
  if (!ids.length) { toast('Bitte mindestens ein Werkzeug auswählen.', 'error'); return false; }
  try {
    const a = await api.post('/api/schaerfauftraege', { dienst, werkzeug_ids: ids, notiz: body.querySelector('#sa-notiz').value.trim() || null });
    toast(`${a.anzahl} Werkzeug(e) abgegeben.`, 'success');
    return true;
  } catch (err) { toast(err.detail || 'Auftrag konnte nicht angelegt werden.', 'error'); return false; }
}

/** Dialog „Rückkehr buchen" für die noch offenen Positionen. @returns {boolean} true, wenn gebucht */
async function rueckkehrBuchen(a) {
  const offen = a.positionen.filter((p) => !p.zurueck_am);
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-muted mb-3">Haken bei allem, was zurück ist. Der Rest bleibt offen.</p>
    ${offen.map((p) => `
      <div class="border border-border rounded-xl p-3 mb-2" data-pos="${p.werkzeug_id}">
        <label class="flex items-start gap-3">
          <input type="checkbox" class="mt-1 w-5 h-5" data-f="da" checked>
          <span class="text-sm min-w-0"><span class="font-semibold text-txt">${escapeHtml(p.werkzeug_code)}</span> ${escapeHtml(p.werkzeug_bezeichnung)}</span>
        </label>
        <div class="grid grid-cols-2 gap-2 mt-2">
          <select data-f="ergebnis" aria-label="Ergebnis" class="${feldCls}"><option value="geschaerft">geschärft</option><option value="ausgemustert">ausgemustert</option></select>
          <input data-f="kosten" aria-label="Kosten in Euro" class="${feldCls}" placeholder="Kosten €" inputmode="decimal" autocomplete="off">
        </div>
      </div>`).join('')}`;
  const ok = await modal({ titel: `Rückkehr von ${a.dienst}`, body, buttons: [
    { label: 'Buchen', variant: 'primary', value: true }, { label: 'Abbrechen', variant: 'secondary', value: null }] });
  if (!ok) return false;
  const positionen = [];
  for (const box of body.querySelectorAll('[data-pos]')) {
    if (!box.querySelector('[data-f="da"]').checked) continue;
    const kosten = centAusEingabe(box.querySelector('[data-f="kosten"]').value);
    if (Number.isNaN(kosten)) { toast('Bitte die Kosten als Betrag eingeben, z. B. 14,50.', 'error'); return false; }
    positionen.push({ werkzeug_id: +box.dataset.pos, ergebnis: box.querySelector('[data-f="ergebnis"]').value, kosten_cent: kosten });
  }
  if (!positionen.length) { toast('Nichts ausgewählt.', 'error'); return false; }
  try {
    await api.post(`/api/schaerfauftraege/${a.id}/rueckgabe`, { positionen });
    toast(`${positionen.length} Werkzeug(e) zurückgebucht.`, 'success');
    return true;
  } catch (err) { toast(err.detail || 'Rückkehr konnte nicht gebucht werden.', 'error'); return false; }
}

function auftragKarte(a) {
  return `
    <section class="bg-surface border border-border rounded-lg p-4 mb-3">
      <div class="flex justify-between items-start gap-3 flex-wrap">
        <div class="min-w-0">
          <div class="font-semibold text-txt break-words">${escapeHtml(a.dienst)}</div>
          <div class="text-sm text-muted">abgegeben ${formatDatum(a.abgabe_zeitpunkt)} · ${a.anzahl_zurueck} von ${a.anzahl} zurück${a.kosten_cent ? ` · ${euro(a.kosten_cent)}` : ''}</div>
          ${a.notiz ? `<div class="text-sm text-txt-2 break-words">${escapeHtml(a.notiz)}</div>` : ''}
        </div>
        <span class="px-2 py-1 rounded-full text-xs font-semibold bg-surface-2 ${a.ist_offen ? 'text-maint' : 'text-ok'}">${a.ist_offen ? 'Offen' : 'Abgeschlossen'}</span>
      </div>
      <ul class="text-sm mt-3 space-y-1">${a.positionen.map((p) => `
        <li class="flex justify-between gap-3"><a href="#/sw/${encodeURIComponent(p.werkzeug_code)}" class="text-txt hover:underline min-w-0 break-words">${escapeHtml(p.werkzeug_code)} ${escapeHtml(p.werkzeug_bezeichnung)}</a>
          <span class="text-muted flex-shrink-0">${p.zurueck_am ? `${p.ergebnis === 'ausgemustert' ? 'ausgemustert' : 'geschärft'}${p.kosten_cent != null ? ` · ${euro(p.kosten_cent)}` : ''}` : 'noch weg'}</span></li>`).join('')}</ul>
      <div class="flex flex-wrap gap-2 mt-3">
        ${a.ist_offen ? `<button data-rueck="${a.id}" class="${btnClasses('primary')} text-sm">Rückkehr buchen</button>` : ''}
        <a href="#/schaerfauftraege/${a.id}/druck" class="${btnClasses('secondary')} text-sm">Begleitliste</a>
      </div>
    </section>`;
}

export async function renderSchaerfauftraege() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <h1 class="text-2xl font-bold text-txt">Schärfaufträge</h1>
        <div class="flex gap-2 flex-wrap">
          <a href="#/schneidwerkzeuge" class="${btnClasses('secondary')} text-sm">Zurück</a>
          <button id="sa-neu" class="${btnClasses('primary')} text-sm">+ Neuer Auftrag</button>
        </div>
      </div>
      <div id="sa-liste">${spinner()}</div>
    </main>`;
  const liste = document.getElementById('sa-liste');
  let auftraege = [];

  async function laden() {
    try {
      auftraege = await api.get('/api/schaerfauftraege');
    } catch (err) {
      liste.innerHTML = `<div class="p-4 text-broken">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
      return;
    }
    // Offene zuerst, innerhalb davon neueste oben (so liefert es der Server).
    auftraege.sort((a, b) => Number(b.ist_offen) - Number(a.ist_offen));
    liste.innerHTML = auftraege.length ? auftraege.map(auftragKarte).join('') : leerZustand('Noch kein Schärfauftrag. Stumpfe Werkzeuge über „Neuer Auftrag“ abgeben.');
    liste.querySelectorAll('[data-rueck]').forEach((b) => {
      b.onclick = async () => { const a = auftraege.find((x) => x.id === +b.dataset.rueck); if (a && await rueckkehrBuchen(a)) await laden(); };
    });
  }
  document.getElementById('sa-neu').onclick = async () => { if (await neuerAuftrag()) await laden(); };
  await laden();
}

/** Druckansicht: Begleitliste für die Abgabe (Browser-Druck → Papier oder PDF). */
export async function renderSchaerfDruck(id) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;
  const main = app.querySelector('main');
  let a;
  let werkzeuge;
  try {
    [a, werkzeuge] = await Promise.all([api.get(`/api/schaerfauftraege/${id}`), api.get('/api/schneidwerkzeuge?status=alle')]);
  } catch (err) {
    main.innerHTML = `<div class="text-broken">${escapeHtml(err.detail || 'Auftrag nicht gefunden.')}</div>`;
    return;
  }
  const nach = Object.fromEntries(werkzeuge.map((w) => [w.id, w]));
  main.innerHTML = `
    <div class="flex gap-2 mb-4 no-print">
      <a href="#/schaerfauftraege" class="${btnClasses('secondary')} text-sm">Zurück</a>
      <button id="sa-drucken" class="${btnClasses('primary')} text-sm">Drucken</button>
    </div>
    <div class="druckblatt">
      <h1 class="text-xl font-bold text-txt">Begleitliste Schärfdienst</h1>
      <p class="text-sm text-txt-2 mb-1">bühler² interior GmbH · Bachstraße 10 · 72119 Ammerbuch</p>
      <p class="text-sm text-txt mb-3">An: <strong>${escapeHtml(a.dienst)}</strong> · Abgabe ${formatDatum(a.abgabe_zeitpunkt)} · Auftrag Nr. ${a.id} · ${a.anzahl} Werkzeug(e)</p>
      ${a.notiz ? `<p class="text-sm text-txt mb-3">Bemerkung: ${escapeHtml(a.notiz)}</p>` : ''}
      <table class="w-full text-sm border-collapse">
        <thead><tr class="text-left border-b-2 border-border"><th class="py-1 pr-2">Nr.</th><th class="py-1 pr-2">Code</th><th class="py-1 pr-2">Werkzeug</th><th class="py-1 pr-2">Kenndaten</th><th class="py-1">Schärfung</th></tr></thead>
        <tbody>${a.positionen.map((p, i) => {
          const w = nach[p.werkzeug_id] || {};
          return `<tr class="border-b border-border align-top"><td class="py-1 pr-2">${i + 1}</td><td class="py-1 pr-2 font-semibold whitespace-nowrap">${escapeHtml(p.werkzeug_code)}</td>
            <td class="py-1 pr-2">${escapeHtml(p.werkzeug_bezeichnung)}${w.hersteller ? `<br><span class="text-muted">${escapeHtml(w.hersteller)}${w.artikelnummer ? ` ${escapeHtml(w.artikelnummer)}` : ''}</span>` : ''}</td>
            <td class="py-1 pr-2">${w.art_text ? escapeHtml(kenndaten(w)) : ''}</td>
            <td class="py-1 whitespace-nowrap">${w.anzahl_schaerfungen != null ? `Nr. ${w.anzahl_schaerfungen + (p.zurueck_am ? 0 : 1)}${w.max_schaerfungen != null ? ` von ${w.max_schaerfungen}` : ''}` : ''}</td></tr>`;
        }).join('')}</tbody>
      </table>
      <p class="text-sm text-txt mt-8">Übergeben am: ____________________ &nbsp;&nbsp; Unterschrift: ____________________</p>
    </div>`;
  document.getElementById('sa-drucken').onclick = () => window.print();
}
