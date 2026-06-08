import { api } from '../api.js';
import {
  escapeHtml, leerZustand, spinner, statusBadge,
} from '../ui.js';
import { filterMaschinen } from '../filter.js';

export async function renderGeraete() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <h1 class="text-2xl font-bold text-txt mb-4">Geräte</h1>
      <div class="flex gap-2 mb-4">
        <input id="g-suche" placeholder="Suche..."
               class="flex-1 border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        <select id="g-status" class="border border-border rounded-lg px-3 py-2 bg-surface text-txt">
          <option value="">Alle Status</option>
          <option value="verfuegbar">Verfügbar</option>
          <option value="ausgeliehen">Ausgeliehen</option>
          <option value="defekt">Defekt</option>
          <option value="wartung">In Wartung</option>
        </select>
      </div>
      <div id="g-liste">${spinner()}</div>
    </main>`;

  const suche = document.getElementById('g-suche');
  const stat  = document.getElementById('g-status');
  const liste = document.getElementById('g-liste');
  let alle = [];

  const render = () => {
    const treffer = filterMaschinen(alle, { suche: suche.value, status: stat.value });
    if (!treffer.length) {
      liste.innerHTML = leerZustand('Keine Geräte gefunden.');
      return;
    }
    liste.innerHTML = treffer.map((m) => `
      <a href="#/m/${encodeURIComponent(m.maschinen_code)}"
         class="block bg-surface rounded-lg shadow-sm p-4 mb-3 border border-border hover:bg-surface-2">
        <div class="flex justify-between items-start gap-3">
          <div class="min-w-0">
            <div class="font-semibold text-txt truncate">${escapeHtml(m.name)}</div>
            <div class="text-sm text-muted truncate">
              ${escapeHtml(m.maschinen_code)}${m.platznummer ? ` · ${escapeHtml(m.platznummer)}` : ''}
            </div>
          </div>
          ${statusBadge(m.status)}
        </div>
      </a>`).join('');
  };

  suche.oninput = render;
  stat.onchange = render;

  try {
    alle = await api.get('/api/maschinen');
    render();
  } catch (err) {
    liste.innerHTML =
      `<div class="p-4 text-rose-600">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
  }
}
