import { api } from '../api.js';
import { escapeHtml, spinner, zeitseit } from '../ui.js';

export async function renderAdminDashboard() {
  const app = document.getElementById('app');
  app.innerHTML = `<main class="max-w-3xl mx-auto pb-24 pt-4 px-4">${spinner()}</main>`;

  let stats;
  try {
    stats = await api.get('/api/admin/statistiken');
  } catch (err) {
    app.querySelector('main').innerHTML =
      `<div class="text-broken">${escapeHtml(err.detail || 'Fehler')}</div>`;
    return;
  }

  app.querySelector('main').innerHTML = `
    <h1 class="text-2xl font-bold text-txt mb-4">Admin</h1>

    <div class="grid grid-cols-2 gap-3 mb-6">
      <a href="#/admin/maschinen" class="bg-surface border border-border rounded-lg p-4 text-center hover:bg-surface-2">
        <div class="text-2xl mb-1">🔧</div>
        <div class="font-medium text-txt">Maschinen</div>
      </a>
      <a href="#/admin/benutzer" class="bg-surface border border-border rounded-lg p-4 text-center hover:bg-surface-2">
        <div class="text-2xl mb-1">👥</div>
        <div class="font-medium text-txt">Benutzer</div>
      </a>
    </div>

    <section class="bg-surface border border-border rounded-lg p-4 mb-4">
      <h2 class="font-semibold text-txt mb-3">Top 10 meistgenutzte Maschinen</h2>
      ${stats.top_maschinen.length ? `
        <ol class="space-y-1">
          ${stats.top_maschinen.map((t, i) => `
            <li class="flex justify-between text-sm">
              <a href="#/m/${encodeURIComponent(t.maschinen_code)}" class="hover:underline text-txt truncate">
                ${i + 1}. ${escapeHtml(t.name)}
                <span class="text-muted-2">(${escapeHtml(t.maschinen_code)})</span>
              </a>
              <span class="text-muted ml-2 flex-shrink-0">${t.anzahl_ausleihen}×</span>
            </li>`).join('')}
        </ol>` : '<div class="text-sm text-muted">Noch keine Ausleihen.</div>'}
    </section>

    <section class="bg-surface border border-border rounded-lg p-4 mb-4">
      <h2 class="font-semibold text-txt mb-3">
        ${stats.ueberfaellige.length ? '⚠️ ' : ''}Überfällig (länger als 7 Tage)
      </h2>
      ${stats.ueberfaellige.length ? `
        <ul class="space-y-2">
          ${stats.ueberfaellige.map((u) => `
            <li class="border border-broken/30 bg-broken/10 rounded p-3 text-sm">
              <a href="#/m/${encodeURIComponent(u.maschine.maschinen_code)}" class="font-medium text-broken hover:underline">
                ${escapeHtml(u.maschine.name)} (${escapeHtml(u.maschine.maschinen_code)})
              </a>
              <div class="text-txt-2 mt-1">
                ${escapeHtml(u.benutzer.voller_name)} — ${zeitseit(u.ausleih_zeitpunkt)}
              </div>
            </li>`).join('')}
        </ul>` : '<div class="text-sm text-muted">Keine überfälligen Ausleihen.</div>'}
    </section>`;
}
