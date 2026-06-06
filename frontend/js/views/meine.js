import { api } from '../api.js';
import {
  btnClasses, escapeHtml, leerZustand, spinner, statusBadge, zeitseit,
} from '../ui.js';

export async function renderMeine() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <h1 class="text-2xl font-bold text-txt mb-4">Meine Ausleihen</h1>
      <div class="bg-surface rounded-lg shadow-sm p-4 mb-4 border border-border">
        <label class="text-sm font-medium text-txt-2 mb-2 block" for="code-input">
          Maschinen-Code eingeben
        </label>
        <form id="code-form" class="flex gap-2">
          <input id="code-input" type="text" placeholder="z.B. M-0001"
                 class="flex-1 border border-border rounded-lg px-3 py-3 text-base uppercase bg-surface text-txt placeholder:text-muted-2">
          <button type="submit" class="${btnClasses('primary')} px-5">Öffnen</button>
        </form>
      </div>
      <div id="meine-liste">${spinner()}</div>
    </main>`;

  document.getElementById('code-form').onsubmit = (e) => {
    e.preventDefault();
    const code = document.getElementById('code-input').value.trim().toUpperCase();
    if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
  };

  const liste = document.getElementById('meine-liste');
  try {
    const ausleihen = await api.get('/api/maschinen/meine');
    if (!ausleihen.length) {
      liste.innerHTML = leerZustand('Du hast aktuell keine Maschine ausgeliehen.');
      return;
    }
    liste.innerHTML = ausleihen.map((a) => `
      <a href="#/m/${encodeURIComponent(a.maschine.maschinen_code)}"
         class="block bg-surface rounded-lg shadow-sm p-4 mb-3 border border-border hover:bg-surface-2">
        <div class="flex justify-between items-start gap-3">
          <div>
            <div class="font-semibold text-txt">${escapeHtml(a.maschine.name)}</div>
            <div class="text-sm text-muted">
              ${escapeHtml(a.maschine.maschinen_code)} · ${zeitseit(a.ausleih_zeitpunkt)}
            </div>
          </div>
          ${statusBadge(a.maschine.status)}
        </div>
      </a>`).join('');
  } catch (err) {
    liste.innerHTML =
      `<div class="p-4 text-rose-600">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
  }
}
