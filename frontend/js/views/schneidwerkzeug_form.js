// Admin: Schneidwerkzeug anlegen oder bearbeiten.

import { api } from '../api.js';
import { btnClasses, escapeHtml, spinner, toast } from '../ui.js';
import { centAusEingabe, zahlAusEingabe } from '../schneidwerkzeug_helfer.js';

const feldCls = 'w-full bg-surface text-txt placeholder:text-muted border border-border rounded-xl px-3 py-3';
const komma = (v) => (v == null ? '' : String(v).replace('.', ','));

/** id = bearbeiten; kopieVon = neues Werkzeug mit den Daten eines vorhandenen (ohne Code). */
export async function renderSchneidwerkzeugForm(id, kopieVon = null) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;
  const main = app.querySelector('main');

  let werte;
  let w = null;
  let vorlage = null;
  try {
    werte = await api.get('/api/schneidwerkzeuge/stammwerte');
    if (id != null) w = await api.get(`/api/schneidwerkzeuge/${id}`);
    else if (kopieVon != null) vorlage = await api.get(`/api/schneidwerkzeuge/${kopieVon}`);
  } catch (err) {
    main.innerHTML = `<div class="text-broken">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
    return;
  }
  // q = Quelle der Vorbelegung: das Werkzeug selbst oder die Kopiervorlage (deren Code und Partner nicht übernommen werden).
  const q = w || (vorlage ? { ...vorlage, code: null, partner_code: null, lagerort: vorlage.lagerort } : null);
  const v = (name) => escapeHtml(q && q[name] != null ? String(q[name]) : '');
  const gewaehlt = new Set(String(q?.materialien || '').split(',').map((m) => m.trim()).filter(Boolean));
  const eigene = [...gewaehlt].filter((m) => !werte.materialien.includes(m));
  const feld = (name, label, { wert = v(name), typ = 'text', hinweis = '', extra = '' } = {}) => `
    <label class="block"><span class="block text-sm text-muted mb-1">${label}</span>
      <input name="${name}" type="${typ}" value="${wert}" class="${feldCls}" autocomplete="off" ${extra}>
      ${hinweis ? `<span class="block text-xs text-muted mt-1">${hinweis}</span>` : ''}</label>`;
  const zurueck = w ? `#/sw/${encodeURIComponent(w.code)}` : '#/schneidwerkzeuge';

  main.innerHTML = `
    <div class="flex items-center justify-between mb-4 gap-2">
      <h1 class="text-2xl font-bold text-txt">${w ? `${escapeHtml(w.code)} bearbeiten` : (vorlage ? `Kopie von ${escapeHtml(vorlage.code)}` : 'Neues Werkzeug')}</h1>
      <a href="${zurueck}" class="${btnClasses('secondary')} text-sm">Zurück</a>
    </div>
    <form id="sw-form" class="space-y-4" novalidate>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label class="block"><span class="block text-sm text-muted mb-1">Art</span>
          <select name="art" class="${feldCls}">${werte.arten.map((a) => `<option value="${a.key}"${q && q.art === a.key ? ' selected' : ''}>${escapeHtml(a.text)}</option>`).join('')}</select></label>
        ${feld('code', 'Code', { hinweis: 'Leer lassen = nächster freier Code', extra: 'placeholder="automatisch" style="text-transform:uppercase"' })}
      </div>
      ${feld('bezeichnung', 'Bezeichnung *', { extra: 'required placeholder="z. B. Plattenaufteilblatt 300 × 4,4 Z72"' })}
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        ${feld('hersteller', 'Hersteller')}${feld('artikelnummer', 'Artikelnummer', { hinweis: 'Gleiche Nummer = gleicher Typ (für die Ersatz-Warnung)' })}
        ${feld('schneidstoff', 'Schneidstoff', { extra: 'list="sw-stoffe" placeholder="HW, DP …"' })}
        ${feld('durchmesser_mm', 'Durchmesser (mm)', { wert: komma(q?.durchmesser_mm), extra: 'inputmode="decimal"' })}
        ${feld('schneidenlaenge_mm', 'Schnittbreite / Schneidenlänge (mm)', { wert: komma(q?.schneidenlaenge_mm), extra: 'inputmode="decimal"' })}
        ${feld('bohrung_schaft_mm', 'Bohrung / Schaft (mm)', { wert: komma(q?.bohrung_schaft_mm), extra: 'inputmode="decimal"' })}
        ${feld('zaehnezahl', 'Zähnezahl', { extra: 'inputmode="numeric"' })}
        ${feld('max_drehzahl', 'Höchstdrehzahl (1/min)', { extra: 'inputmode="numeric"', hinweis: 'n max laut Aufdruck auf dem Werkzeug' })}
        ${feld('max_schaerfungen', 'Wie oft schärfbar', { extra: 'inputmode="numeric"', hinweis: 'Leer = ohne Grenze. Richtwert: HW-Sägeblatt 15–20, DP-Fräser 2–3' })}
        ${feld('lagerort', 'Lagerfach', { extra: 'list="sw-orte" placeholder="z. B. Schrank 1 / Fach 3"' })}
        ${feld('partner_code', 'Gehört zusammen mit (Code)', { hinweis: 'z. B. Vorritzer zum Sägeblatt', extra: 'style="text-transform:uppercase"' })}
        ${feld('kaufdatum', 'Gekauft am', { typ: 'date' })}
        ${feld('kaufpreis', 'Kaufpreis (€)', { wert: q?.kaufpreis_cent != null ? komma((q.kaufpreis_cent / 100).toFixed(2)) : '', extra: 'inputmode="decimal"' })}
      </div>
      <fieldset class="bg-surface border border-border rounded-lg p-4 space-y-3">
        <legend class="font-semibold text-txt px-1">Einsatz &amp; Parameter</legend>
        <label class="block"><span class="block text-sm text-muted mb-1">Einsatzgebiet</span>
          <textarea name="einsatzgebiet" rows="2" class="${feldCls}" placeholder="z. B. Formatieren und Nuten von beschichteten Platten">${v('einsatzgebiet')}</textarea></label>
        <div><span class="block text-sm text-muted mb-1">Geeignet für</span>
          <div class="flex flex-wrap gap-x-4 gap-y-2">${werte.materialien.map((m) => `
            <label class="inline-flex items-center gap-2 text-sm text-txt"><input type="checkbox" name="material" value="${escapeHtml(m)}" class="w-5 h-5"${gewaehlt.has(m) ? ' checked' : ''}> ${escapeHtml(m)}</label>`).join('')}</div>
          <input name="material_sonst" value="${escapeHtml(eigene.join(', '))}" class="${feldCls} mt-2" placeholder="Weitere Materialien, mit Komma getrennt" autocomplete="off"></div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          ${feld('drehzahl_empfohlen', 'Empfohlene Drehzahl (1/min)', { extra: 'inputmode="numeric"' })}
          ${feld('vorschub_empfohlen', 'Empfohlener Vorschub (m/min)', { wert: komma(q?.vorschub_empfohlen), extra: 'inputmode="decimal"' })}
        </div>
        <label class="block"><span class="block text-sm text-muted mb-1">Hinweise zu den Parametern</span>
          <textarea name="parameter_notiz" rows="2" class="${feldCls}" placeholder="z. B. Zustellung max. 12 mm, Gegenlauf, nur mit Absaugung">${v('parameter_notiz')}</textarea></label>
      </fieldset>
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
      zaehnezahl: zahlAusEingabe(f('zaehnezahl')), max_drehzahl: zahlAusEingabe(f('max_drehzahl')), max_schaerfungen: zahlAusEingabe(f('max_schaerfungen')),
      drehzahl_empfohlen: zahlAusEingabe(f('drehzahl_empfohlen')), vorschub_empfohlen: zahlAusEingabe(f('vorschub_empfohlen')) };
    const kaufpreis = centAusEingabe(f('kaufpreis'));
    if (!f('bezeichnung')) { fehler.textContent = 'Bitte eine Bezeichnung eingeben.'; return; }
    if (Object.values(zahlen).some(Number.isNaN) || Number.isNaN(kaufpreis)) { fehler.textContent = 'Bitte bei Maßen, Zahlen und Preis nur Ziffern (mit Komma) eingeben.'; return; }
    for (const n of ['zaehnezahl', 'max_drehzahl', 'max_schaerfungen', 'drehzahl_empfohlen']) {
      if (zahlen[n] != null && !Number.isInteger(zahlen[n])) { fehler.textContent = 'Zähnezahl, Drehzahl und Schärfungen müssen ganze Zahlen sein.'; return; }
    }
    const daten = {
      art: f('art'), code: f('code').toUpperCase() || null, bezeichnung: f('bezeichnung'), hersteller: f('hersteller') || null,
      artikelnummer: f('artikelnummer') || null, schneidstoff: f('schneidstoff') || null, ...zahlen,
      lagerort: f('lagerort') || null, partner_code: f('partner_code').toUpperCase() || null,
      kaufdatum: f('kaufdatum') || null, kaufpreis_cent: kaufpreis, notiz: f('notiz') || null,
      einsatzgebiet: f('einsatzgebiet') || null, parameter_notiz: f('parameter_notiz') || null,
      materialien: [...[...form.querySelectorAll('input[name="material"]:checked')].map((c) => c.value), ...f('material_sonst').split(',').map((m) => m.trim()).filter(Boolean)].join(', ') || null,
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
