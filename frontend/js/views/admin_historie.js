import { api } from '../api.js';
import { btnClasses, escapeHtml, formatDatum, spinner } from '../ui.js';

const ZUSTAND_LABELS = {
  ok:      'OK',
  defekt:  'Defekt',
  wartung: 'Wartung nötig',
};

export async function renderAdminHistorie(maschineId) {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;

  try {
    const eintraege = await api.get(`/api/admin/maschinen/${maschineId}/historie`);
    app.querySelector('main').innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-2xl font-bold text-slate-900">Ausleih-Historie</h1>
        <a href="#/admin/maschinen" class="${btnClasses('secondary')} text-sm">Zurück</a>
      </div>
      ${eintraege.length ? `
        <div class="space-y-2">
          ${eintraege.map((e) => `
            <div class="bg-white border border-slate-200 rounded-lg p-3 text-sm">
              <div class="flex justify-between items-start gap-2">
                <div class="font-medium text-slate-900">${escapeHtml(e.benutzer.voller_name)}${
                  e.externes_team_name
                    ? ` <span class="font-normal text-slate-500">für</span> ${escapeHtml(e.externes_team_name)}`
                    : ''
                }</div>
                ${e.ist_offen ? '<span class="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800">offen</span>' : ''}
              </div>
              <div class="text-slate-600 text-xs mt-1">
                Ausgeliehen: ${formatDatum(e.ausleih_zeitpunkt)}<br>
                Zurück:&nbsp;&nbsp;&nbsp;&nbsp; ${e.rueckgabe_zeitpunkt ? formatDatum(e.rueckgabe_zeitpunkt) : '—'}
              </div>
              ${e.rueckgabe_zustand ? `
                <div class="text-xs mt-1">
                  Zustand: <strong>${ZUSTAND_LABELS[e.rueckgabe_zustand] || e.rueckgabe_zustand}</strong>
                </div>` : ''}
              ${e.rueckgabe_kommentar ? `
                <div class="text-xs mt-1 text-slate-700 italic">„${escapeHtml(e.rueckgabe_kommentar)}"</div>` : ''}
              <div class="text-xs text-slate-500 mt-1">
                Dauer: ${e.dauer_tage} Tag${e.dauer_tage === 1 ? '' : 'e'}
              </div>
            </div>`).join('')}
        </div>` : '<div class="text-center py-12 text-slate-500">Noch keine Ausleihen.</div>'}`;
  } catch (err) {
    app.querySelector('main').innerHTML =
      `<div class="text-rose-600 p-4">${escapeHtml(err.detail)}</div>`;
  }
}
