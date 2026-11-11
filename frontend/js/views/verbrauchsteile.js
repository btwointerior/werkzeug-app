// Verbrauchsteile (Messer der Kantenanleimmaschine, Wendeplatten …): nur Stückzahl, mit Entnahme,
// Zugang und Mindestbestand. Dazu die Verwaltung der Maschinenliste (Admin).

import { api } from '../api.js';
import { btnClasses, confirmDialog, escapeHtml, formatDatum, leerZustand, modal, spinner, toast } from '../ui.js';
import { state } from '../app.js';

const feldCls = 'w-full bg-surface text-txt placeholder:text-muted border border-border rounded-xl px-3 py-3';
const ganz = (text) => (/^\d+$/.test(String(text).trim()) ? parseInt(text, 10) : NaN);

/** Dialog Entnahme/Zugang. @returns {boolean} true, wenn gebucht */
async function bewegung(teil, richtung) {
  const entnahme = richtung < 0;
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-muted mb-3">${escapeHtml(teil.bezeichnung)} · aktuell ${teil.bestand} Stück</p>
    <label class="block text-sm text-muted mb-1" for="vt-menge">Stückzahl</label>
    <input id="vt-menge" class="${feldCls} mb-3" value="1" inputmode="numeric" autocomplete="off">
    <label class="block text-sm text-muted mb-1" for="vt-text">Bemerkung (optional)</label>
    <input id="vt-text" class="${feldCls}" placeholder="${entnahme ? 'z. B. Messer getauscht' : 'z. B. Lieferung'}" autocomplete="off">`;
  const ok = await modal({ titel: entnahme ? 'Entnehmen' : 'Zugang buchen', body, buttons: [
    { label: entnahme ? 'Entnehmen' : 'Buchen', variant: 'primary', value: true }, { label: 'Abbrechen', variant: 'secondary', value: null }] });
  if (!ok) return false;
  const menge = ganz(body.querySelector('#vt-menge').value);
  if (!(menge > 0)) { toast('Bitte eine Stückzahl ab 1 eingeben.', 'error'); return false; }
  try {
    await api.post(`/api/verbrauchsteile/${teil.id}/bewegung`, { menge: richtung * menge, text: body.querySelector('#vt-text').value.trim() || null });
    toast(entnahme ? `${menge} Stück entnommen.` : `${menge} Stück zugebucht.`, 'success');
    return true;
  } catch (err) { toast(err.detail || 'Das hat nicht geklappt.', 'error'); return false; }
}

/** Dialog Anlegen/Bearbeiten (Admin). @returns {boolean} true, wenn gespeichert */
async function teilFormular(teil, maschinen) {
  const v = (n) => escapeHtml(teil && teil[n] != null ? String(teil[n]) : '');
  const body = document.createElement('div');
  body.innerHTML = `
    <label class="block text-sm text-muted mb-1" for="vt-bez">Bezeichnung *</label>
    <input id="vt-bez" class="${feldCls} mb-3" value="${v('bezeichnung')}" placeholder="z. B. Fügemesser 20 mm" autocomplete="off">
    <div class="grid grid-cols-2 gap-2 mb-3">
      <div><label class="block text-sm text-muted mb-1" for="vt-her">Hersteller</label><input id="vt-her" class="${feldCls}" value="${v('hersteller')}" autocomplete="off"></div>
      <div><label class="block text-sm text-muted mb-1" for="vt-art">Artikelnummer</label><input id="vt-art" class="${feldCls}" value="${v('artikelnummer')}" autocomplete="off"></div>
    </div>
    <label class="block text-sm text-muted mb-1" for="vt-ma">Für Maschine</label>
    <select id="vt-ma" class="${feldCls} mb-3"><option value="">– keine –</option>
      ${maschinen.map((m) => `<option value="${escapeHtml(m)}"${teil && teil.maschine === m ? ' selected' : ''}>${escapeHtml(m)}</option>`).join('')}</select>
    <label class="block text-sm text-muted mb-1" for="vt-ort">Lagerfach</label>
    <input id="vt-ort" class="${feldCls} mb-3" value="${v('lagerort')}" autocomplete="off">
    <div class="grid grid-cols-2 gap-2">
      ${teil ? '' : `<div><label class="block text-sm text-muted mb-1" for="vt-best">Anfangsbestand</label><input id="vt-best" class="${feldCls}" value="0" inputmode="numeric" autocomplete="off"></div>`}
      <div><label class="block text-sm text-muted mb-1" for="vt-min">Mindestbestand</label><input id="vt-min" class="${feldCls}" value="${v('mindestbestand')}" placeholder="leer = keine Warnung" inputmode="numeric" autocomplete="off"></div>
    </div>`;
  const ok = await modal({ titel: teil ? 'Verbrauchsteil bearbeiten' : 'Neues Verbrauchsteil', body, buttons: [
    { label: teil ? 'Speichern' : 'Anlegen', variant: 'primary', value: true }, { label: 'Abbrechen', variant: 'secondary', value: null }] });
  if (!ok) return false;
  const w = (id) => body.querySelector(id)?.value.trim() ?? '';
  const mindest = w('#vt-min') === '' ? null : ganz(w('#vt-min'));
  const bestand = teil ? null : ganz(w('#vt-best') || '0');
  if (!w('#vt-bez')) { toast('Bitte eine Bezeichnung eingeben.', 'error'); return false; }
  if (Number.isNaN(mindest) || Number.isNaN(bestand)) { toast('Bestand und Mindestbestand bitte als ganze Zahl.', 'error'); return false; }
  const daten = { bezeichnung: w('#vt-bez'), hersteller: w('#vt-her') || null, artikelnummer: w('#vt-art') || null,
    maschine: w('#vt-ma') || null, lagerort: w('#vt-ort') || null, mindestbestand: mindest, bestand };
  try {
    if (teil) await api.put(`/api/verbrauchsteile/${teil.id}`, daten); else await api.post('/api/verbrauchsteile', daten);
    toast('Gespeichert.', 'success');
    return true;
  } catch (err) { toast(err.detail || 'Speichern fehlgeschlagen.', 'error'); return false; }
}

async function zeigeVerlauf(teil) {
  let d;
  try { d = await api.get(`/api/verbrauchsteile/${teil.id}`); } catch (err) { toast(err.detail || 'Fehler beim Laden.', 'error'); return; }
  const body = document.createElement('div');
  body.innerHTML = d.bewegungen.length ? `<ul class="text-sm space-y-2">${d.bewegungen.slice(0, 40).map((b) => `
    <li><span class="font-semibold ${b.menge < 0 ? 'text-broken' : 'text-ok'}">${b.menge > 0 ? '+' : ''}${b.menge}</span>
      <span class="text-muted">· ${formatDatum(b.zeitpunkt)}${b.benutzer_name ? ` · ${escapeHtml(b.benutzer_name)}` : ''}</span>
      ${b.text ? `<br><span class="text-txt break-words">${escapeHtml(b.text)}</span>` : ''}</li>`).join('')}</ul>` : '<p class="text-muted text-sm">Noch keine Bewegungen.</p>';
  await modal({ titel: `Verlauf: ${d.bezeichnung}`, body, buttons: [{ label: 'Schließen', variant: 'secondary', value: null }] });
}

export async function renderVerbrauchsteile() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <div class="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <h1 class="text-2xl font-bold text-txt">Verbrauchsteile</h1>
        <div class="flex gap-2 flex-wrap">
          <a href="#/schneidwerkzeuge" class="${btnClasses('secondary')} text-sm">Zurück</a>
          ${state.istAdmin ? `<button id="vt-neu" class="${btnClasses('primary')} text-sm">+ Neu</button>` : ''}
        </div>
      </div>
      <p class="text-sm text-muted mb-4">Teile, die getauscht statt geschärft werden – zum Beispiel die Messer der Kantenanleimmaschine. Geführt wird nur die Stückzahl.</p>
      <div id="vt-liste">${spinner()}</div>
    </main>`;
  const liste = document.getElementById('vt-liste');
  let teile = [];
  let maschinen = [];
  try { maschinen = (await api.get('/api/schneidwerkzeuge/stammwerte')).maschinen; } catch { /* Formular geht auch ohne Maschinenliste */ }

  async function laden() {
    try { teile = await api.get('/api/verbrauchsteile'); }
    catch (err) { liste.innerHTML = `<div class="p-4 text-broken">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`; return; }
    liste.innerHTML = teile.length ? teile.map((t) => `
      <section class="bg-surface border ${t.unter_mindestbestand ? 'border-maint' : 'border-border'} rounded-lg p-4 mb-3">
        <div class="flex justify-between items-start gap-3">
          <div class="min-w-0">
            <div class="font-semibold text-txt break-words">${escapeHtml(t.bezeichnung)}</div>
            <div class="text-sm text-muted break-words">${escapeHtml([t.hersteller, t.artikelnummer, t.maschine, t.lagerort ? `Fach ${t.lagerort}` : null].filter(Boolean).join(' · '))}</div>
            ${t.unter_mindestbestand ? `<div class="text-sm text-maint font-semibold mt-1">Nachbestellen – Mindestbestand ${t.mindestbestand}</div>` : ''}
          </div>
          <div class="text-right flex-shrink-0"><div class="text-2xl font-bold ${t.unter_mindestbestand ? 'text-maint' : 'text-txt'}">${t.bestand}</div><div class="text-xs text-muted">Stück</div></div>
        </div>
        <div class="flex flex-wrap gap-2 mt-3">
          <button data-akt="minus" data-id="${t.id}" class="${btnClasses('primary')} text-sm"${t.bestand === 0 ? ' disabled' : ''}>Entnehmen</button>
          <button data-akt="plus" data-id="${t.id}" class="${btnClasses('secondary')} text-sm">Zugang</button>
          <button data-akt="verlauf" data-id="${t.id}" class="${btnClasses('ghost')} text-sm">Verlauf</button>
          ${state.istAdmin ? `<button data-akt="edit" data-id="${t.id}" class="${btnClasses('ghost')} text-sm">Bearbeiten</button>
          <button data-akt="weg" data-id="${t.id}" class="${btnClasses('ghost')} text-sm text-broken">Löschen</button>` : ''}
        </div>
      </section>`).join('') : leerZustand(state.istAdmin ? 'Noch keine Verbrauchsteile. Über „+ Neu“ anlegen.' : 'Noch keine Verbrauchsteile angelegt.');
    liste.querySelectorAll('[data-akt]').forEach((b) => {
      b.onclick = async () => {
        const t = teile.find((x) => x.id === +b.dataset.id);
        if (!t) return;
        const akt = b.dataset.akt;
        if (akt === 'minus' && await bewegung(t, -1)) await laden();
        if (akt === 'plus' && await bewegung(t, 1)) await laden();
        if (akt === 'verlauf') await zeigeVerlauf(t);
        if (akt === 'edit' && await teilFormular(t, maschinen)) await laden();
        if (akt === 'weg' && await confirmDialog(`„${t.bezeichnung}“ mit seinem Verlauf endgültig löschen?`, { titel: 'Löschen?', okLabel: 'Löschen', dangerous: true })) {
          try { await api.del(`/api/verbrauchsteile/${t.id}`); toast('Gelöscht.', 'success'); await laden(); }
          catch (err) { toast(err.detail || 'Löschen nicht möglich.', 'error'); }
        }
      };
    });
  }
  const neu = document.getElementById('vt-neu');
  if (neu) neu.onclick = async () => { if (await teilFormular(null, maschinen)) await laden(); };
  await laden();
}

/** Admin: Maschinenliste pflegen (umbenennen, abschalten, ergänzen). */
export async function renderSchneidMaschinen() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <div class="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <h1 class="text-2xl font-bold text-txt">Maschinenliste</h1>
        <a href="#/schneidwerkzeuge" class="${btnClasses('secondary')} text-sm">Zurück</a>
      </div>
      <p class="text-sm text-muted mb-4">Diese Maschinen stehen beim Einbauen zur Auswahl. Umbenennen ändert auch die eingebauten Werkzeuge mit.</p>
      <div id="ma-liste">${spinner()}</div>
      <form id="ma-neu" class="flex gap-2 mt-4">
        <input name="name" class="${feldCls}" placeholder="Neue Maschine" autocomplete="off" aria-label="Name der neuen Maschine">
        <button class="${btnClasses('primary')} text-sm" type="submit">Hinzufügen</button>
      </form>
    </main>`;
  const liste = document.getElementById('ma-liste');

  async function laden() {
    let maschinen;
    try { maschinen = await api.get('/api/schneidwerkzeuge/maschinen'); }
    catch (err) { liste.innerHTML = `<div class="p-4 text-broken">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`; return; }
    liste.innerHTML = maschinen.map((m) => `
      <form data-id="${m.id}" class="flex gap-2 mb-2 items-center">
        <input name="name" value="${escapeHtml(m.name)}" class="${feldCls} ${m.aktiv ? '' : 'opacity-60'}" autocomplete="off" aria-label="Name der Maschine">
        <button type="submit" class="${btnClasses('secondary')} text-sm">Speichern</button>
        <button type="button" data-aktiv="${m.aktiv ? '0' : '1'}" class="${btnClasses('ghost')} text-sm whitespace-nowrap">${m.aktiv ? 'Abschalten' : 'Einschalten'}</button>
      </form>`).join('');
    liste.querySelectorAll('form').forEach((f) => {
      const id = +f.dataset.id;
      const m = maschinen.find((x) => x.id === id);
      const speichern = async (aktiv) => {
        const name = f.elements.name.value.trim();
        if (!name) { toast('Der Name darf nicht leer sein.', 'error'); return; }
        try { await api.put(`/api/schneidwerkzeuge/maschinen/${id}`, { name, aktiv }); toast('Gespeichert.', 'success'); await laden(); }
        catch (err) { toast(err.detail || 'Speichern fehlgeschlagen.', 'error'); }
      };
      f.onsubmit = (e) => { e.preventDefault(); speichern(m.aktiv); };
      f.querySelector('[data-aktiv]').onclick = () => speichern(f.querySelector('[data-aktiv]').dataset.aktiv === '1');
    });
  }
  document.getElementById('ma-neu').onsubmit = async (e) => {
    e.preventDefault();
    const feld = e.target.elements.name;
    const name = feld.value.trim();
    if (!name) return;
    try { await api.post('/api/schneidwerkzeuge/maschinen', { name, aktiv: true }); feld.value = ''; toast('Hinzugefügt.', 'success'); await laden(); }
    catch (err) { toast(err.detail || 'Das hat nicht geklappt.', 'error'); }
  };
  await laden();
}
