// Admin: Schneidwerkzeug anlegen oder bearbeiten.

import { api } from '../api.js';
import { btnClasses, escapeHtml, spinner, toast } from '../ui.js';
import { centAusEingabe, zahlAusEingabe } from '../schneidwerkzeug_helfer.js';

const feldCls = 'w-full bg-surface text-txt placeholder:text-muted border border-border rounded-xl px-3 py-3';
const komma = (v) => (v == null ? '' : String(v).replace('.', ','));

export async function renderSchneidwerkzeugForm(id) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;
  const main = app.querySelector('main');

  let werte;
  let w = null;
  try {
    werte = await api.get('/api/schneidwerkzeuge/stammwerte');
    if (id != null) w = await api.get(`/api/schneidwerkzeuge/${id}`);
  } catch (err) {
    main.innerHTML = `<div class="text-broken">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
    return;
  }
  const v = (name) => escapeHtml(w && w[name] != null ? String(w[name]) : '');
  const feld = (name, label, { wert = v(name), typ = 'text', hinweis = '', extra = '' } = {}) => `
    <label class="block"><span class="block text-sm text-muted mb-1">${label}</span>
      <input name="${name}" type="${typ}" value="${wert}" class="${feldCls}" autocomplete="off" ${extra}>
      ${hinweis ? `<span class="block text-xs text-muted mt-1">${hinweis}</span>` : ''}</label>`;
  const zurueck = w ? `#/sw/${encodeURIComponent(w.code)}` : '#/schneidwerkzeuge';

  main.innerHTML = `
    <div class="flex items-center justify-between mb-4 gap-2">
      <h1 class="text-2xl font-bold text-txt">${w ? `${escapeHtml(w.code)} bearbeiten` : 'Neues Werkzeug'}</h1>
      <a href="${zurueck}" class="${btnClasses('secondary')} text-sm">Zurück</a>
    </div>
    <form id="sw-form" class="space-y-4" novalidate>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label class="block"><span class="block text-sm text-muted mb-1">Art</span>
          <select name="art" class="${feldCls}">${werte.arten.map((a) => `<option value="${a.key}"${w && w.art === a.key ? ' selected' : ''}>${escapeHtml(a.text)}</option>`).join('')}</select></label>
        ${feld('code', 'Code', { hinweis: 'Leer lassen = nächster freier Code', extra: 'placeholder="automatisch" style="text-transform:uppercase"' })}
      </div>
      ${feld('bezeichnung', 'Bezeichnung *', { extra: 'required placeholder="z. B. Plattenaufteilblatt 300 × 4,4 Z72"' })}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        ${feld('hersteller', 'Hersteller')}${feld('artikelnummer', 'Artikelnummer', { hinweis: 'Gleiche Nummer = gleicher Typ (für die Ersatz-Warnung)' })}
        ${feld('schneidstoff', 'Schneidstoff', { extra: 'list="sw-stoffe" placeholder="HW, DP …"' })}
        ${feld('durchmesser_mm', 'Durchmesser (mm)', { wert: komma(w?.durchmesser_mm), extra: 'inputmode="decimal"' })}
        ${feld('schneidenlaenge_mm', 'Schnittbreite / Schneidenlänge (mm)', { wert: komma(w?.schneidenlaenge_mm), extra: 'inputmode="decimal"' })}
        ${feld('bohrung_schaft_mm', 'Bohrung / Schaft (mm)', { wert: komma(w?.bohrung_schaft_mm), extra: 'inputmode="decimal"' })}
        ${feld('zaehnezahl', 'Zähnezahl', { extra: 'inputmode="numeric"' })}
        ${feld('max_drehzahl', 'Höchstdrehzahl (1/min)', { extra: 'inputmode="numeric"', hinweis: 'n max laut Aufdruck auf dem Werkzeug' })}
        ${feld('max_schaerfungen', 'Wie oft schärfbar', { extra: 'inputmode="numeric"', hinweis: 'Leer = ohne Grenze. Richtwert: HW-Sägeblatt 15–20, DP-Fräser 2–3' })}
        ${feld('lagerort', 'Lagerfach', { extra: 'list="sw-orte" placeholder="z. B. Schrank 1 / Fach 3"' })}
        ${feld('partner_code', 'Gehört zusammen mit (Code)', { hinweis: 'z. B. Vorritzer zum Sägeblatt', extra: 'style="text-transform:uppercase"' })}
        ${feld('kaufdatum', 'Gekauft am', { typ: 'date' })}
        ${feld('kaufpreis', 'Kaufpreis (€)', { wert: w?.kaufpreis_cent != null ? komma((w.kaufpreis_cent / 100).toFixed(2)) : '', extra: 'inputmode="decimal"' })}
      </div>
      <label class="block"><span class="block text-sm text-muted mb-1">Notiz</span>
        <textarea name="notiz" rows="3" class="${feldCls}">${v('notiz')}</textarea></label>
      <datalist id="sw-stoffe"><option value="HW"><option value="DP"><option value="HSS"></datalist>
      <datalist id="sw-orte">${werte.lagerorte.map((o) => `<option value="${escapeHtml(o)}">`).join('')}</datalist>
      <div id="sw-fehler" class="text-broken text-sm" role="alert"></div>
      <div class="flex gap-2">
        <button type="submit" class="${btnClasses('primary')}">${w ? 'Speichern' : 'Anlegen'}</button>
        <a href="${zurueck}" class="${btnClasses('secondary')}">Abbrechen</a>
      </div>
    </form>`;

  const form = document.getElementById('sw-form');
  const fehler = document.getElementById('sw-fehler');
  const artFeld = form.elements.art;
  const codeFeld = form.elements.code;
  const zeigeVorschlag = () => { if (!w) codeFeld.placeholder = `automatisch: ${werte.naechste_codes[artFeld.value] || ''}`; };
  artFeld.onchange = zeigeVorschlag;
  zeigeVorschlag();

  form.onsubmit = async (e) => {
    e.preventDefault();
    fehler.textContent = '';
    const f = (n) => form.elements[n].value.trim();
    const zahlen = { durchmesser_mm: zahlAusEingabe(f('durchmesser_mm')), schneidenlaenge_mm: zahlAusEingabe(f('schneidenlaenge_mm')), bohrung_schaft_mm: zahlAusEingabe(f('bohrung_schaft_mm')),
      zaehnezahl: zahlAusEingabe(f('zaehnezahl')), max_drehzahl: zahlAusEingabe(f('max_drehzahl')), max_schaerfungen: zahlAusEingabe(f('max_schaerfungen')) };
    const kaufpreis = centAusEingabe(f('kaufpreis'));
    if (!f('bezeichnung')) { fehler.textContent = 'Bitte eine Bezeichnung eingeben.'; return; }
    if (Object.values(zahlen).some(Number.isNaN) || Number.isNaN(kaufpreis)) { fehler.textContent = 'Bitte bei Maßen, Zahlen und Preis nur Ziffern (mit Komma) eingeben.'; return; }
    for (const n of ['zaehnezahl', 'max_drehzahl', 'max_schaerfungen']) {
      if (zahlen[n] != null && !Number.isInteger(zahlen[n])) { fehler.textContent = 'Zähnezahl, Drehzahl und Schärfungen müssen ganze Zahlen sein.'; return; }
    }
    const daten = {
      art: f('art'), code: f('code').toUpperCase() || null, bezeichnung: f('bezeichnung'), hersteller: f('hersteller') || null,
      artikelnummer: f('artikelnummer') || null, schneidstoff: f('schneidstoff') || null, ...zahlen,
      lagerort: f('lagerort') || null, partner_code: f('partner_code').toUpperCase() || null,
      kaufdatum: f('kaufdatum') || null, kaufpreis_cent: kaufpreis, notiz: f('notiz') || null,
    };
    const knopf = form.querySelector('button[type="submit"]');
    knopf.disabled = true;
    try {
      const neu = w ? await api.put(`/api/schneidwerkzeuge/${w.id}`, daten) : await api.post('/api/schneidwerkzeuge', daten);
      toast(w ? 'Gespeichert.' : `${neu.code} angelegt.`, 'success');
      location.hash = `#/sw/${encodeURIComponent(neu.code)}`;
    } catch (err) {
      fehler.textContent = err.detail || 'Speichern fehlgeschlagen.';
      knopf.disabled = false;
    }
  };
}
